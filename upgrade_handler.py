import telebot
from telebot import types
import sqlite3
from upgrade_system import UpgradeSystem

class UpgradeHandler:
    def __init__(self, bot, db_path="bot_database.db"):
        self.bot = bot
        self.db_path = db_path
        self.upgrade_system = UpgradeSystem(main_db_path=db_path)
        
    def upgrades_command(self, message):
        """Handle the /upgrades command to show the upgrades menu"""
        chat_id = message.chat.id
        
        # Check if user is linked
        user_data = self.get_telegram_user(chat_id)
        if not user_data or not user_data[2]:  # Not linked
            message_text = "Ваш аккаунт не привязан. Используйте команду /link для привязки."
            
            keyboard = types.InlineKeyboardMarkup()
            back_button = types.InlineKeyboardButton(
                text="🔙 Назад в меню", 
                callback_data="main_menu"
            )
            keyboard.add(back_button)
            
            try:
                sent_message = self.bot.send_message(chat_id, message_text, reply_markup=keyboard)
                # Store message ID if needed for future edits
            except:
                pass
            return
        
        twitch_username = user_data[2]
        
        # Show upgrades menu
        self.show_upgrades_menu(chat_id, twitch_username)
    
    def show_upgrades_menu(self, chat_id, twitch_username):
        """Display the main upgrades menu"""
        # Get user's current upgrades
        user_upgrades = self.upgrade_system.get_user_upgrades(twitch_username)
        if not user_upgrades:
            self.upgrade_system.initialize_user_upgrades(twitch_username)
            user_upgrades = self.upgrade_system.get_user_upgrades(twitch_username)
        
        points_balance = user_upgrades['points_balance']
        
        message_text = "📈 <b>Система прокачки</b>\n\n"
        message_text += f"Доступно очков прокачки: <b>{points_balance}</b>\n\n"
        message_text += "Выберите улучшение:"
        
        keyboard = types.InlineKeyboardMarkup()
        
        # Add buttons for each upgrade type
        upgrades_info = self.upgrade_system.get_all_upgrade_info()
        for upgrade_key, upgrade_info in upgrades_info.items():
            current_level = user_upgrades[upgrade_key]
            upgrade_name = upgrade_info['name']
            max_level = upgrade_info['max_level']
            
            # Show current level and max level
            button_text = f"{upgrade_name} [{current_level}/{max_level}]"
            callback_data = f"upgrade_detail:{upgrade_key}"
            
            keyboard.add(types.InlineKeyboardButton(text=button_text, callback_data=callback_data))
        
        # Add button to buy upgrade points
        keyboard.add(types.InlineKeyboardButton(
            text="💰 Купить очки прокачки", 
            callback_data="buy_upgrade_points"
        ))
        
        # Add back button
        keyboard.add(types.InlineKeyboardButton(
            text="🔙 Назад в меню", 
            callback_data="main_menu"
        ))
        
        try:
            sent_message = self.bot.send_message(chat_id, message_text, reply_markup=keyboard, parse_mode='HTML')
            # Store message ID if needed for future edits
        except:
            pass
    
    def show_upgrade_detail(self, chat_id, twitch_username, upgrade_type):
        """Show detail information about a specific upgrade"""
        # Get upgrade info
        upgrade_info = self.upgrade_system.get_upgrade_info(upgrade_type)
        if not upgrade_info:
            self.bot.send_message(chat_id, "Ошибка: Неверный тип прокачки")
            return
        
        # Get user's current level
        user_upgrades = self.upgrade_system.get_user_upgrades(twitch_username)
        if not user_upgrades:
            self.upgrade_system.initialize_user_upgrades(twitch_username)
            user_upgrades = self.upgrade_system.get_user_upgrades(twitch_username)
        
        current_level = user_upgrades[upgrade_type]
        max_level = upgrade_info['max_level']
        upgrade_name = upgrade_info['name']
        description = upgrade_info['description']
        
        message_text = f"📈 <b>{upgrade_name}</b>\n\n"
        message_text += f"{description}\n\n"
        message_text += f"Текущий уровень: <b>{current_level}</b>\n"
        message_text += f"Максимальный уровень: <b>{max_level}</b>\n\n"
        
        keyboard = types.InlineKeyboardMarkup()
        
        # Show upgrade button if not max level
        if current_level < max_level:
            cost = self.upgrade_system.get_upgrade_cost(upgrade_type, current_level)
            points_balance = user_upgrades['points_balance']
            
            if points_balance >= cost:
                button_text = f"⬆️ Улучшить за {cost} очков"
                callback_data = f"upgrade_skill:{upgrade_type}"
                keyboard.add(types.InlineKeyboardButton(text=button_text, callback_data=callback_data))
            else:
                message_text += f"Недостаточно очков для улучшения. Нужно: <b>{cost}</b>\n"
                message_text += f"У вас: <b>{points_balance}</b>\n\n"
        else:
            message_text += "✅ Достигнут максимальный уровень\n\n"
        
        # Navigation buttons
        keyboard.add(types.InlineKeyboardButton(
            text="📋 Все улучшения", 
            callback_data="upgrades"
        ))
        
        keyboard.add(types.InlineKeyboardButton(
            text="🔙 Назад в меню", 
            callback_data="main_menu"
        ))
        
        try:
            sent_message = self.bot.send_message(chat_id, message_text, reply_markup=keyboard, parse_mode='HTML')
            # Store message ID if needed for future edits
        except:
            pass
    
    def buy_upgrade_points_menu(self, chat_id, twitch_username):
        """Show menu to buy upgrade points"""
        message_text = "💰 <b>Покупка очков прокачки</b>\n\n"
        message_text += "Выберите пакет очков прокачки:\n\n"
        message_text += "🔹 100 очков - 100 LC\n"
        message_text += "🔹 250 очков - 240 LC\n"
        message_text += "🔹 500 очков - 450 LC\n"
        message_text += "🔹 1000 очков - 850 LC\n"
        
        keyboard = types.InlineKeyboardMarkup()
        
        # Add purchase options
        keyboard.add(types.InlineKeyboardButton(
            text="🔹 100 очков - 100 LC", 
            callback_data="purchase_points:100:100"
        ))
        
        keyboard.add(types.InlineKeyboardButton(
            text="🔹 250 очков - 240 LC", 
            callback_data="purchase_points:250:240"
        ))
        
        keyboard.add(types.InlineKeyboardButton(
            text="🔹 500 очков - 450 LC", 
            callback_data="purchase_points:500:450"
        ))
        
        keyboard.add(types.InlineKeyboardButton(
            text="🔹 1000 очков - 850 LC", 
            callback_data="purchase_points:1000:850"
        ))
        
        # Back button
        keyboard.add(types.InlineKeyboardButton(
            text="🔙 Назад", 
            callback_data="upgrades"
        ))
        
        try:
            sent_message = self.bot.send_message(chat_id, message_text, reply_markup=keyboard, parse_mode='HTML')
            # Store message ID if needed for future edits
        except:
            pass
    
    def purchase_upgrade_points(self, chat_id, twitch_username, points_amount, lc_cost):
        """Handle purchase of upgrade points"""
        success, message = self.upgrade_system.purchase_upgrade_points(twitch_username, points_amount, lc_cost)
        
        if success:
            message_text = f"✅ {message}\n\n"
            message_text += f"Получено: <b>{points_amount}</b> очков прокачки\n"
            message_text += f"Списано: <b>{lc_cost}</b> LC\n"
            
            # Show new balance
            user_upgrades = self.upgrade_system.get_user_upgrades(twitch_username)
            if user_upgrades:
                points_balance = user_upgrades['points_balance']
                message_text += f"Текущий баланс: <b>{points_balance}</b> очков\n"
        else:
            message_text = f"❌ Ошибка: {message}"
        
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(types.InlineKeyboardButton(
            text="📋 Все улучшения", 
            callback_data="upgrades"
        ))
        
        keyboard.add(types.InlineKeyboardButton(
            text="🔙 Назад в меню", 
            callback_data="main_menu"
        ))
        
        try:
            sent_message = self.bot.send_message(chat_id, message_text, reply_markup=keyboard, parse_mode='HTML')
            # Store message ID if needed for future edits
        except:
            pass
    
    def upgrade_skill(self, chat_id, twitch_username, upgrade_type):
        """Handle upgrading a specific skill"""
        success, message = self.upgrade_system.upgrade_skill(twitch_username, upgrade_type)
        
        if success:
            message_text = f"✅ {message}\n"
        else:
            message_text = f"❌ {message}\n"
        
        # Get updated info
        user_upgrades = self.upgrade_system.get_user_upgrades(twitch_username)
        if user_upgrades:
            points_balance = user_upgrades['points_balance']
            message_text += f"\nТекущий баланс: <b>{points_balance}</b> очков"
        
        keyboard = types.InlineKeyboardMarkup()
        
        # If successful, show the same upgrade again
        if success:
            keyboard.add(types.InlineKeyboardButton(
                text="📈 Продолжить прокачку", 
                callback_data=f"upgrade_detail:{upgrade_type}"
            ))
        
        keyboard.add(types.InlineKeyboardButton(
            text="📋 Все улучшения", 
            callback_data="upgrades"
        ))
        
        keyboard.add(types.InlineKeyboardButton(
            text="🔙 Назад в меню", 
            callback_data="main_menu"
        ))
        
        try:
            sent_message = self.bot.send_message(chat_id, message_text, reply_markup=keyboard, parse_mode='HTML')
            # Store message ID if needed for future edits
        except:
            pass
    
    def get_telegram_user(self, chat_id):
        """Get Telegram user data"""
        try:
            conn = sqlite3.connect(self.db_path)
            print("Connected to the database")
            print(chat_id)
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM telegram_users WHERE chat_id = ?', (chat_id,))
            user_data = cursor.fetchone()
            conn.close()
            return user_data
        except sqlite3.Error:
            return None