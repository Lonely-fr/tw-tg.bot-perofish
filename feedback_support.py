import telebot
from telebot import types
import sqlite3
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class FeedbackSupportModule:
    def __init__(self, bot, db_path):
        self.bot = bot
        self.db_path = db_path
        self.awaiting_feedback = set()
        self.user_messages = {}
    
    def contact_lonely(self, message):
        """Обработка связи с Лонли"""
        chat_id = message.chat.id
        
        message_text = "✉️ <b>Связь с Лонли</b>\n\n"
        message_text += "Вы можете отправить сообщение Лонли.\n"
        message_text += "Пожалуйста, опишите ваш вопрос, предложение или сообщите об ошибке.\n\n"
        message_text += "Напишите ваше сообщение в следующем сообщении:"
        
        # Добавляем кнопки
        keyboard = types.InlineKeyboardMarkup()
        cancel_button = types.InlineKeyboardButton(
            text="❌ Отмена", 
            callback_data="main_menu"
        )
        keyboard.add(cancel_button)
        
        try:
            sent_message = self.bot.send_message(message.chat.id, message_text, reply_markup=keyboard, parse_mode='HTML')
            self.user_messages[chat_id] = sent_message.message_id
            # Добавляем пользователя в список ожидающих отправки сообщения
            self.awaiting_feedback.add(chat_id)
        except:
            pass
    
    def support_lonely(self, message):
        """Показать опции поддержки Лонли"""
        chat_id = message.chat.id
        
        message_text = "💖 <b>Поддержать Лонли</b>\n\n"
        message_text += "Если вам нравится бот и вы хотите поддержать Лонли, вы можете сделать пожертвование через одну из платформ:\n\n"
        
        # Создаем кнопки для донатов
        keyboard = types.InlineKeyboardMarkup()
        
        yoomoney_button = types.InlineKeyboardButton(
            text="ЮMoney", 
            url="https://yoomoney.ru/fundraise/1CI4P0D5VGR.250903"
        )
        
        donationalerts_button = types.InlineKeyboardButton(
            text="DonationAlerts", 
            url="https://www.donationalerts.com/r/lonely_friend"
        )
        
        menu_button = types.InlineKeyboardButton(
            text="🔙 Назад в меню", 
            callback_data="main_menu"
        )
        
        keyboard.add(yoomoney_button)
        keyboard.add(donationalerts_button)
        keyboard.add(menu_button)
        
        try:
            sent_message = self.bot.send_message(message.chat.id, message_text, reply_markup=keyboard, parse_mode='HTML')
            self.user_messages[chat_id] = sent_message.message_id
        except:
            pass
    
    def process_feedback(self, message):
        """Обработка сообщения обратной связи от пользователя"""
        chat_id = message.chat.id
        
        # Проверяем, что пользователь находится в состоянии ожидания обратной связи
        if chat_id not in self.awaiting_feedback:
            return
            
        try:
            # Удаляем пользователя из состояния ожидания
            self.awaiting_feedback.remove(chat_id)
            
            # Получаем текст сообщения пользователя
            feedback_text = message.text
            
            # Проверяем, что сообщение не пустое
            if not feedback_text.strip():
                error_text = "❌ Невозможно отправить пустое сообщение.\nПожалуйста, напишите ваше сообщение Лонли."
                self.bot.send_message(chat_id, error_text)
                return
                
            # Сохраняем сообщение в базу данных
            self._save_feedback_message(chat_id, feedback_text)
            
            # Подтверждаем получение пользователю
            confirmation_text = "✅ Ваше сообщение отправлено Лонли.\nСпасибо за обратную связь!"
            self.bot.send_message(chat_id, confirmation_text)
            
        except Exception as e:
            logger.error("Error processing feedback from user %s: %s", chat_id, str(e))
            self.bot.send_message(chat_id, f"❌ Ошибка при обработке вашего сообщения: {str(e)}")
    
    def _save_feedback_message(self, chat_id, message_text):
        """Сохраняет сообщение обратной связи в базу данных"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Создаем таблицу, если она не существует
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS feedback_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id INTEGER NOT NULL,
                    message TEXT NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Вставляем новое сообщение
            cursor.execute("""
                INSERT INTO feedback_messages (chat_id, message)
                VALUES (?, ?)
            """, (chat_id, message_text))
            
            conn.commit()
    
    def init_db(self):
        """Инициализирует базу данных при старте бота"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Создаем таблицу сообщений обратной связи
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS feedback_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id INTEGER NOT NULL,
                    message TEXT NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            conn.commit()
    
    def handle_callback_query(self, call):
        """Обработка callback query для модуля обратной связи и поддержки"""
        chat_id = call.message.chat.id
        data = call.data
        
        try:
            # Отвечаем на запрос, чтобы убрать "часики"
            self.bot.answer_callback_query(call.id)
        except:
            pass
            
        if data == "contact_lonely":
            # Связь с Лонли
            logger.info("User %s navigated to contact lonely", chat_id)
            self.contact_lonely(call.message)
            return True
            
        elif data == "support_lonely":
            # Донат Лонли
            logger.info("User %s navigated to support lonely", chat_id)
            self.support_lonely(call.message)
            return True
            
        return False  # Если не обработано этим модулем