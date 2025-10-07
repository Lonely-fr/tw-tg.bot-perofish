import telebot
from telebot import types
import json
import logging

logger = logging.getLogger(__name__)

class HelpInfoModule:
    def __init__(self, bot, db_path):
        self.bot = bot
        self.db_path = db_path
        self.user_messages = {}
        # These would need to be passed from the main bot
        self.FISH_RARITY_WEIGHTS = None
        self.RARITY_NAMES_RU = None
        self.FISHING_COOLDOWN = None
        self.CURRENCY_NAME = None
    
    def get_fish_drop_chances(self):
        """Получить шансы выпадения рыбы по редкости"""
        if not self.FISH_RARITY_WEIGHTS:
            return {}
            
        rarity_info = self.FISH_RARITY_WEIGHTS
        total_weight = sum(rarity_info.values())
        chances = {}
        
        for rarity, weight in rarity_info.items():
            chance = (weight / total_weight) * 100
            chances[rarity] = {
                'weight': weight,
                'chance': chance
            }
        
        return chances

    def info_command(self, message):
        """Обработка команды /info - показ информации о боте"""
        chat_id = message.chat.id
        
        # Получаем информацию о редкости рыбы и шансах выпадения
        rarity_info = self.get_fish_drop_chances()
        
        message_text = "ℹ️ <b>Информация о системе рыбалки</b>\n\n"
        message_text += "<b>Команды:</b>\n"
        message_text += "/start - Главное меню\n"
        message_text += "/link - Привязать аккаунт\n"
        message_text += "/fish - Посмотреть пойманную рыбу\n"
        message_text += "/catch - Поймать рыбу (раз в час)\n"
        message_text += "/duplicates - Управление дубликатами рыбы\n"
        message_text += "/balance - Проверить баланс\n"
        message_text += "/info - Эта справка\n\n"
        
        if rarity_info:
            message_text += "<b>Шансы выпадения рыбы по редкости:</b>\n"
            # Сортируем по убыванию шансов
            sorted_rarities = sorted(rarity_info.items(), key=lambda x: x[1]['chance'], reverse=True)
            for rarity, data in sorted_rarities:
                chance = data['chance']
                rarity_name = self.RARITY_NAMES_RU.get(rarity, rarity) if self.RARITY_NAMES_RU else rarity
                message_text += f"{rarity_name}: {chance:.3f}% (вес: {data['weight']})\n"
        
        if self.FISHING_COOLDOWN:
            message_text += f"\n<b>Кулдаун:</b>\n"
            message_text += f"Между ловлей рыбы должен пройти {self.FISHING_COOLDOWN//3600} час (в секундах: {self.FISHING_COOLDOWN})\n\n"
        
        if self.CURRENCY_NAME:
            message_text += "<b>Примечания:</b>\n"
            message_text += f"• Рыба продается по номинальной стоимости в {self.CURRENCY_NAME}\n"
            message_text += "• Дубликаты можно продать все сразу\n"
            message_text += f"• Баланс измеряется в {self.CURRENCY_NAME} (Lonely Coins)\n"
        
        # Добавляем кнопку возврата в меню
        keyboard = types.InlineKeyboardMarkup()
        back_button = types.InlineKeyboardButton(
            text="🔙 Назад в меню", 
            callback_data="main_menu"
        )
        keyboard.add(back_button)
        
        try:
            sent_message = self.bot.send_message(message.chat.id, message_text, reply_markup=keyboard, parse_mode='HTML')
            self.user_messages[chat_id] = sent_message.message_id
        except:
            pass

    def help_command(self, message):
        """Обработка команды /help - показ полной информации о функционале бота"""
        chat_id = message.chat.id
        
        try:
            # Загружаем информацию о функционале бота из JSON файла
            with open('bot_functionality.json', 'r', encoding='utf-8') as f:
                bot_info = json.load(f)
            
            message_text = f"📖 <b>{bot_info['bot_name']}</b>\n\n"
            message_text += f"{bot_info['description']}\n\n"
            
            # Добавляем информацию по разделам
            for section_key, section_data in bot_info['sections'].items():
                message_text += f"<b>{section_data['title']}</b>\n"
                message_text += f"{section_data['description']}\n\n"
                
                # Добавляем функции в разделе
                for feature in section_data['features']:
                    if 'command' in feature:
                        message_text += f"• <code>{feature['command']}</code> - {feature['description']}\n"
                    elif 'commands' in feature:
                        commands_str = ', '.join([f"<code>{cmd}</code>" for cmd in feature['commands']])
                        message_text += f"• {commands_str} - {feature['description']}\n"
                    else:
                        message_text += f"• {feature['description']}\n"
                message_text += "\n"
            
            # Добавляем техническую информацию
            message_text += "<b>🔧 Техническая информация:</b>\n"
            for cooldown_name, cooldown_value in bot_info['technical_info']['cooldowns'].items():
                message_text += f"• {cooldown_name}: {cooldown_value}\n"
            
            message_text += f"\n💰 Валюта: {bot_info['technical_info']['currency']}\n"
            
            # Добавляем кнопку возврата в меню
            keyboard = types.InlineKeyboardMarkup()
            back_button = types.InlineKeyboardButton(
                text="🔙 Назад в меню", 
                callback_data="main_menu"
            )
            keyboard.add(back_button)
            
            try:
                sent_message = self.bot.send_message(message.chat.id, message_text, reply_markup=keyboard, parse_mode='HTML')
                self.user_messages[chat_id] = sent_message.message_id
            except:
                pass
                
        except FileNotFoundError:
            # Если файл не найден, показываем простое сообщение
            message_text = "❌ Файл с информацией о функционале бота не найден."
            try:
                sent_message = self.bot.send_message(message.chat.id, message_text)
                self.user_messages[chat_id] = sent_message.message_id
            except:
                pass
        except json.JSONDecodeError:
            # Если файл поврежден, показываем сообщение об ошибке
            message_text = "❌ Ошибка чтения файла с информацией о функционале бота."
            try:
                sent_message = self.bot.send_message(message.chat.id, message_text)
                self.user_messages[chat_id] = sent_message.message_id
            except:
                pass
        except Exception as e:
            # При других ошибках также показываем сообщение
            message_text = "❌ Произошла ошибка при попытке загрузить информацию о функционале бота."
            try:
                sent_message = self.bot.send_message(message.chat.id, message_text)
                self.user_messages[chat_id] = sent_message.message_id
            except:
                pass
    
    def handle_callback_query(self, call):
        """Обработка callback query для модуля помощи и информации"""
        chat_id = call.message.chat.id
        data = call.data
        
        try:
            # Отвечаем на запрос, чтобы убрать "часики"
            self.bot.answer_callback_query(call.id)
        except:
            pass
            
        if data == "view_info":
            # Просмотр информации о боте
            logger.info("User %s navigated to view info", chat_id)
            self.info_command(call.message)
            return True
            
        elif data == "view_help":
            # Просмотр помощи
            logger.info("User %s navigated to view help", chat_id)
            self.help_command(call.message)
            return True
            
        return False  # Если не обработано этим модулем