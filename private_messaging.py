import sqlite3
import telebot
from telebot import types
import logging
from datetime import datetime

# Configure logging for private messages
pm_logger = logging.getLogger('private_messages')
pm_logger.setLevel(logging.INFO)

# Create file handler for private messages
fh = logging.FileHandler('private_messages.log', encoding='utf-8')
fh.setLevel(logging.INFO)

# Create formatter and add it to the handler
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
fh.setFormatter(formatter)

# Add handler to the logger
pm_logger.addHandler(fh)


class PrivateMessagingSystem:
    def __init__(self, bot, db_path='bot_database.db'):
        self.bot = bot
        self.db_path = db_path
        # Dictionary to store user states for private messaging
        self.user_states = {}
        # Dictionary to store last message senders (for /reply_to_last command)
        self.last_message_senders = {}
        # Items per page for user list
        self.ITEMS_PER_PAGE = 40
        
    def create_private_messages_table(self):
        """Create table for storing private message metadata"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS private_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sender_chat_id INTEGER,
                receiver_chat_id INTEGER,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                message_type TEXT,
                action_log TEXT
            )
        ''')
        
        conn.commit()
        conn.close()
        
    def log_action(self, sender_chat_id, receiver_chat_id, action, message_type="action"):
        """Log an action in the private messaging system"""
        # Log to file
        pm_logger.info(f"sender:{sender_chat_id} receiver:{receiver_chat_id} action:{action}")
        
        # Save to database
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO private_messages 
            (sender_chat_id, receiver_chat_id, message_type, action_log)
            VALUES (?, ?, ?, ?)
        ''', (sender_chat_id, receiver_chat_id, message_type, action))
        
        conn.commit()
        conn.close()
        
    def get_twitch_username(self, chat_id):
        """Get Twitch username for a Telegram chat ID"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT twitch_username FROM telegram_users WHERE chat_id = ?
        ''', (chat_id,))
        
        result = cursor.fetchone()
        conn.close()
        
        return result[0] if result else None
        
    def get_all_linked_users(self, page=0):
        """Get all linked users for the user selection UI"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        offset = page * self.ITEMS_PER_PAGE
        cursor.execute('''
            SELECT chat_id, twitch_username FROM telegram_users 
            WHERE twitch_username IS NOT NULL
            ORDER BY twitch_username
            LIMIT ? OFFSET ?
        ''', (self.ITEMS_PER_PAGE, offset))
        
        users = cursor.fetchall()
        conn.close()
        
        return users
        
    def get_total_linked_users(self):
        """Get total count of linked users"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT COUNT(*) FROM telegram_users 
            WHERE twitch_username IS NOT NULL
        ''')
        
        count = cursor.fetchone()[0]
        conn.close()
        
        return count
        
    def show_user_selection_ui(self, chat_id, page=0):
        """Show UI for selecting a user to message"""
        users = self.get_all_linked_users(page)
        total_users = self.get_total_linked_users()
        total_pages = (total_users + self.ITEMS_PER_PAGE - 1) // self.ITEMS_PER_PAGE
        
        if not users:
            self.bot.send_message(chat_id, "❌ Нет доступных пользователей для отправки сообщения.")
            return
            
        keyboard = types.InlineKeyboardMarkup()
        
        # Add user buttons (2 per row)
        user_buttons = []
        for user_chat_id, twitch_username in users:
            # Skip the current user
            if user_chat_id != chat_id:
                button = types.InlineKeyboardButton(
                    text=twitch_username,
                    callback_data=f"pm_select_user:{user_chat_id}"
                )
                user_buttons.append(button)
        
        # Group buttons in pairs
        for i in range(0, len(user_buttons), 2):
            if i + 1 < len(user_buttons):
                keyboard.row(user_buttons[i], user_buttons[i + 1])
            else:
                keyboard.row(user_buttons[i])
        
        # Add navigation buttons
        nav_buttons = []
        if page > 0:
            nav_buttons.append(types.InlineKeyboardButton(
                text="⬅️ Назад",
                callback_data=f"pm_user_page:{page-1}"
            ))
            
        if page < total_pages - 1:
            nav_buttons.append(types.InlineKeyboardButton(
                text="Вперёд ➡️",
                callback_data=f"pm_user_page:{page+1}"
            ))
            
        if nav_buttons:
            keyboard.row(*nav_buttons)
            
        # Cancel button
        keyboard.add(types.InlineKeyboardButton(
            text="❌ Отмена",
            callback_data="pm_cancel"
        ))
        
        message_text = f"Выберите пользователя для отправки сообщения (страница {page+1}/{total_pages}):"
        self.bot.send_message(chat_id, message_text, reply_markup=keyboard)
        
    def show_chat_menu(self, chat_id):
        """Show the main chat menu with buttons"""
        keyboard = types.InlineKeyboardMarkup()
        
        # Add chat options (grouped in pairs)
        new_message_btn = types.InlineKeyboardButton(
            text="✉️ Новое сообщение",
            callback_data="pm_new_message"
        )
        
        reply_to_last_btn = types.InlineKeyboardButton(
            text="↩️ Ответить последнему",
            callback_data="pm_reply_to_last"
        )
        
        end_chat_btn = types.InlineKeyboardButton(
            text="🔚 Завершить чат",
            callback_data="pm_end_chat"
        )
        
        back_btn = types.InlineKeyboardButton(
            text="🔙 Назад",
            callback_data="main_menu"
        )
        
        keyboard.row(new_message_btn, reply_to_last_btn)
        keyboard.row(end_chat_btn, back_btn)
        
        message_text = "💬 <b>Приватные сообщения</b>\n\n" \
                       "Выберите действие:"
        
        self.bot.send_message(chat_id, message_text, reply_markup=keyboard, parse_mode='HTML')
        
    def initiate_private_chat_silent(self, sender_chat_id, target_chat_id):
        """Initiate a private chat silently (only sender knows about it)"""
        # Get usernames for logging
        sender_username = self.get_twitch_username(sender_chat_id)
        target_username = self.get_twitch_username(target_chat_id)
        
        # Set up the conversation state for sender only
        self.user_states[sender_chat_id] = {
            "in_private_chat": True,
            "partner": target_chat_id,
            "is_initiator": True
        }
        
        # Log the action
        self.log_action(sender_chat_id, target_chat_id, 
                       f"Silently initiated private chat from {sender_username} to {target_username}")
        
        # Notify sender
        message = "✅ Чат открыт!\n" \
                  "Введите /pm_menu для возврата в меню чата."
                  
        self.bot.send_message(sender_chat_id, message)
        
    def send_private_message(self, sender_chat_id, message_text):
        """Send a private message to the chat partner"""
        # Check if user is in a private chat
        if sender_chat_id not in self.user_states or not self.user_states[sender_chat_id].get("in_private_chat"):
            # Don't send error message here as it might interfere with regular commands
            return False
            
        partner_chat_id = self.user_states[sender_chat_id]["partner"]
        
        # Get usernames for logging
        sender_username = self.get_twitch_username(sender_chat_id)
        receiver_username = self.get_twitch_username(partner_chat_id)
        
        # Log the action
        self.log_action(sender_chat_id, partner_chat_id, 
                       f"Message sent from {sender_username} to {receiver_username}")
        
        # Send message to receiver with sender info
        message_to_receiver = f"✉️ Новое сообщение от пользователя {sender_username}:\n\n{message_text}"
        try:
            self.bot.send_message(partner_chat_id, message_to_receiver)
            # Confirm to sender
            self.bot.send_message(sender_chat_id, "✅ Сообщение отправлено.")
            
            # Record the last sender for the receiver
            self.last_message_senders[partner_chat_id] = sender_chat_id
        except Exception as e:
            self.bot.send_message(sender_chat_id, "❌ Ошибка при отправке сообщения.")
            return False
            
        return True
        
    def reply_to_last_sender(self, chat_id, message_text):
        """Reply to the last person who sent you a message"""
        if chat_id not in self.last_message_senders:
            self.bot.send_message(chat_id, "❌ Нет последнего отправителя для ответа.")
            return False
            
        partner_chat_id = self.last_message_senders[chat_id]
        
        # Get usernames for logging
        sender_username = self.get_twitch_username(chat_id)
        receiver_username = self.get_twitch_username(partner_chat_id)
        
        # Log the action
        self.log_action(chat_id, partner_chat_id, 
                       f"Reply to last sender from {sender_username} to {receiver_username}")
        
        # Send message to receiver with sender info
        message_to_receiver = f"✉️ Новое сообщение от пользователя {sender_username}:\n\n{message_text}"
        try:
            self.bot.send_message(partner_chat_id, message_to_receiver)
            # Confirm to sender
            self.bot.send_message(chat_id, "✅ Сообщение отправлено.")
            
            # Update the last sender record
            self.last_message_senders[partner_chat_id] = chat_id
        except Exception as e:
            self.bot.send_message(chat_id, "❌ Ошибка при отправке сообщения.")
            return False
            
        return True
        
    def end_private_chat(self, chat_id):
        """End a private chat"""
        if chat_id not in self.user_states or not self.user_states[chat_id].get("in_private_chat"):
            self.bot.send_message(chat_id, "❌ У вас нет активного приватного чата.")
            return
            
        partner_chat_id = self.user_states[chat_id]["partner"]
        
        # Log the action
        sender_username = self.get_twitch_username(chat_id)
        receiver_username = self.get_twitch_username(partner_chat_id)
        self.log_action(chat_id, partner_chat_id, 
                       f"Ended private chat between {sender_username} and {receiver_username}")
        
        # Notify sender
        self.bot.send_message(chat_id, "✅ Приватный чат завершён.")
        
        # Clean up
        if chat_id in self.user_states:
            del self.user_states[chat_id]