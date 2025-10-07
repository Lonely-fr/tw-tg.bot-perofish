import sqlite3
import secrets
import subprocess
import telebot
from telebot import types
import threading
import time
import random
import json
from datetime import datetime
import logging
from trade_system import trade_system
# Import new modules for feedback/support and help/info
from feedback_support import FeedbackSupportModule
from help_info import HelpInfoModule
# Import private messaging module
from private_messaging import PrivateMessagingSystem
from tgw_past_def import *

# Import upgrade system
from upgrade_system import UpgradeSystem
from upgrade_handler import UpgradeHandler

# Configure logging
logging.basicConfig(
    filename='tg_bot.log',
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO, 
    encoding="utf-8"
)

logger = logging.getLogger(__name__)


class TelegramBot:
    def __init__(self, token: str, db_path: str = 'bot_database.db'):
        
        self.token = token
        self.db_path = db_path
        self.bot = telebot.TeleBot(token)
        self.pending_links = {}  # Store pending link requests
        self.user_states = {}    # Store user states (for pagination, etc.)
        self.user_messages = {}  # Store last message IDs for each chat
        self.ITEMS_PER_PAGE = 5  # Number of fish per page
        trade_system.add_trade_methods(TelegramBot)
        logger.info("Initializing TelegramBot with token and db_path=%s", db_path)
        self.upgrade_system = UpgradeSystem(main_db_path=db_path)
        # Initialize new modules
        self.feedback_support = FeedbackSupportModule(self.bot, self.db_path)
        self.help_info = HelpInfoModule(self.bot, self.db_path)
        self.private_messaging = PrivateMessagingSystem(self.bot, self.db_path)
        self.upgrade_handler = UpgradeHandler(self.bot, self.db_path)
        
        # Create tables
        self.private_messaging.create_private_messages_table()
        self.create_telegram_table()
        self.create_cooldown_table()
        self.create_settings_table()
        self.create_fishing_notifications_table()
        
        # Редкость рыбы и их веса для выбора
        self.FISH_RARITY_WEIGHTS = {
            "common": 3000,
            "uncommon": 2500,
            "rare": 2000,
            "epic": 1500,
            "legendary": 800,
            "immortal": 200,
            "mythical": 100,
            "arcane": 50,
            "ultimate": 10
        }
        
        # Перевод названий редкости на русский язык
        self.RARITY_NAMES_RU = {
            "common": "Обычная",
            "uncommon": "Необычная", 
            "rare": "Редкая",
            "epic": "Эпическая",
            "legendary": "Легендарная",
            "immortal": "Бессмертная",
            "mythical": "Мифическая",
            "arcane": "Волшебная",
            "ultimate": "Ультимативная"
        }
        
        self.buy_fish_price = {
            "common": 100,
            "uncommon": 200,
            "rare": 400,
            "epic": 800,
            "legendary": 1500,
            "immortal": 2500,
            "mythical": 4000,
            "arcane": 5000,
            "ultimate": 10000
        }
        # Кулдаун для рыбалки (в секундах)
        self.FISHING_COOLDOWN = 3600  # 1 час
        
        # Валюта бота
        self.CURRENCY_NAME = "LC"  # Lonely Coins
        
        # Pass data to help_info module
        self.help_info.FISH_RARITY_WEIGHTS = self.FISH_RARITY_WEIGHTS
        self.help_info.RARITY_NAMES_RU = self.RARITY_NAMES_RU
        self.help_info.FISHING_COOLDOWN = self.FISHING_COOLDOWN
        self.help_info.CURRENCY_NAME = self.CURRENCY_NAME
        
        # Load mini collections
        self.mini_collections = self.load_mini_collections()
        
        # Register command handlers
        self.bot.message_handler(commands=['start'])(self.start_command)
        self.bot.message_handler(commands=['link'])(self.link_command)
        self.bot.message_handler(commands=['fish'])(self.fish_command)
        self.bot.message_handler(commands=['catch'])(self.fish_telegram)  # New fishing command
        self.bot.message_handler(commands=['duplicates'])(self.duplicates_command)  # New duplicates command
        self.bot.message_handler(commands=['balance'])(self.balance_command)  # New balance command
        self.bot.message_handler(commands=['info'])(self.info_command)  # New info command
        self.bot.message_handler(commands=['help'])(self.help_command)  # Help command
        self.bot.message_handler(commands=['contact'])(self.contact_lonely)  # Contact Lonely command
        self.bot.message_handler(commands=['support'])(self.support_lonely)  # Support command
        self.bot.message_handler(commands=['trade'])(self.trade_command)
        self.bot.message_handler(commands=['msg'])(self.start_private_chat)  # Private messaging command
        self.bot.message_handler(commands=['reply_to_last'])(self.reply_to_last_command)  # Reply to last sender
        self.bot.message_handler(commands=['end_chat'])(self.end_private_chat)  # End private chat command
        self.bot.message_handler(commands=['pm_menu'])(self.show_pm_menu)  # Show private messaging menu
        self.bot.message_handler(commands=['reboot'])(self.reboot)
        self.bot.message_handler(commands=['upgrades'])(self.upgrades_command)  # Upgrades command
        self.bot.callback_query_handler(func=lambda call: True)(self.handle_callback_query)
        self.bot.message_handler(func=lambda message: True)(self.handle_message)
        
        logger.info("TelegramBot initialized successfully")
    
    def reboot(self, message):
        logger.info("Перезапуск бота...")
        if self.can_reboot(message.chat.id):
            subprocess.Popen(["tw.exe"])
    def start_fishing_notification_checker(self):
        """Запустить проверку уведомлений о рыбалке"""
        def check_fishing_notifications():
            while True:
                try:
                    # Получаем пользователей с включенными уведомлениями
                    users = self.get_users_for_fishing_notification()
                    for chat_id, twitch_username in users:
                        # Проверяем, может ли пользователь рыбачить
                        if twitch_username != None:
                            if self.can_fish(twitch_username):
                                # Проверяем, отправлялось ли уже уведомление
                                if not self.was_fishing_notification_sent(chat_id):
                                    try:
                                        # Получаем настройки пользователя для проверки звука
                                        user_settings = self.get_user_settings(chat_id)
                                        disable_notification = not user_settings.get('fishing_sound', True)
                                        self.record_fishing_notification(chat_id)
                                        # Отправляем уведомление
                                        message = "🎣 Доступна рыбалка! Пришло время порыбачить!"
                                        self.bot.send_message(chat_id, message, disable_notification=disable_notification)
                                        
                                        logger.info(f"Fishing notification sent to chat_id={chat_id}")
                                    except Exception as e:
                                        logger.error(f"Failed to send fishing notification to chat_id={chat_id}: {e}")
                                        self.clear_fishing_notification(chat_id)
                
                except Exception as e:
                    logger.error(f"Error in fishing notification checker: {e}")
                
                # Ждем 10 секунд перед следующей проверкой
                time.sleep(60)
        
        # Запускаем проверку в отдельном потоке
        notification_thread = threading.Thread(target=check_fishing_notifications, daemon=True)
        notification_thread.start()
        logger.info("Fishing notification checker started")
    
    def load_mini_collections(self):
        """Загрузка мини-коллекций из JSON файла"""
        try:
            with open('mini_collections.json', 'r', encoding='utf-8') as f:
                collections = json.load(f)
            
            # Calculate rarity for each collection based on fish rarity
            for collection in collections:
                rarities = []
                for fish_id in collection['fish_ids']:
                    fish = self.get_fish_by_id_from_db(fish_id)
                    if fish and fish[4]:  # fish[4] is rarity
                        rarities.append(fish[4])
                
                # Determine collection rarity based on most common fish rarity
                if rarities:
                    collection_rarity = max(set(rarities), key=rarities.count)
                else:
                    collection_rarity = "common"
                
                collection['rarity'] = collection_rarity
            
            return collections
        except Exception as e:
            logger.error("Failed to load mini collections: %s", str(e))
            return []
    
    def get_fish_by_id_from_db(self, fish_id):
        """Получение рыбы по ID из базы данных"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM items WHERE id = ?', (fish_id,))
            fish = cursor.fetchone()
            conn.close()
            return fish
        except Exception as e:
            logger.error("Failed to get fish by id %s: %s", fish_id, str(e))
            return None
    
    def generate_link_code(self) -> str:
        """Генерация уникального кода для привязки аккаунтов"""
        return secrets.token_hex(4).upper()
    
    def create_telegram_table(self):
        """Создание таблицы для хранения пользователей Telegram"""
        logger.info("Creating telegram_users table if it doesn't exist")
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS telegram_users (
                chat_id INTEGER PRIMARY KEY,
                link_code TEXT,
                twitch_username TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(twitch_username) REFERENCES players(username) ON DELETE SET NULL
            )
        ''')
        
        conn.commit()
        conn.close()
        logger.info("telegram_users table created or already exists")
    
    def create_cooldown_table(self):
        """Создание таблицы для хранения времени кулдауна пользователей"""
        logger.info("Creating cooldowns table if it doesn't exist")
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cooldowns (
                username TEXT PRIMARY KEY,
                last_used INTEGER DEFAULT 0,
                FOREIGN KEY(username) REFERENCES players(username) ON DELETE CASCADE
            )
        ''')
        
        conn.commit()
        conn.close()
        logger.info("cooldowns table created or already exists")
    
    def create_settings_table(self):
        """Создание таблицы для хранения пользовательских настроек"""
        logger.info("Creating settings table if it doesn't exist")
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_settings (
                chat_id INTEGER PRIMARY KEY,
                fishing_notifications INTEGER DEFAULT 1,
                fishing_sound INTEGER DEFAULT 0,
                FOREIGN KEY(chat_id) REFERENCES telegram_users(chat_id) ON DELETE CASCADE
            )
        ''')
        
        conn.commit()
        conn.close()
        logger.info("settings table created or already exists")
    
    def create_fishing_notifications_table(self):
        """Создание таблицы для отслеживания уведомлений о рыбалке"""
        logger.info("Creating fishing notifications table if it doesn't exist")
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS fishing_notifications (
                chat_id INTEGER PRIMARY KEY,
                last_sent TIMESTAMP DEFAULT NULL,
                FOREIGN KEY(chat_id) REFERENCES telegram_users(chat_id) ON DELETE CASCADE
            )
        ''')
        
        conn.commit()
        conn.close()
        logger.info("fishing_notifications table created or already exists")
    
    def save_telegram_user(self, chat_id: int, link_code: str = None):
        """Сохранение или обновление пользователя Telegram в базе данных"""
        logger.info("Saving telegram user with chat_id=%s and link_code=%s", chat_id, link_code)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO telegram_users (chat_id, link_code)
            VALUES (?, ?)
        ''', (chat_id, link_code))
        
        # Initialize user settings if they don't exist
        cursor.execute('''
            INSERT OR IGNORE INTO user_settings (chat_id)
            VALUES (?)
        ''', (chat_id,))
        
        conn.commit()
        conn.close()
        logger.info("Telegram user saved successfully")
    
    def get_user_settings(self, chat_id: int):
        """Получение настроек пользователя"""
        logger.info("Getting settings for chat_id=%s", chat_id)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                SELECT fishing_notifications, fishing_sound 
                FROM user_settings 
                WHERE chat_id = ?
            ''', (chat_id,))
            
            result = cursor.fetchone()
            
            if result:
                settings = {
                    'fishing_notifications': bool(result[0]),
                    'fishing_sound': bool(result[1])
                }
                conn.close()
                logger.info("Retrieved settings for chat_id=%s: %s", chat_id, settings)
                return settings
            else:
                # If user settings don't exist, create them with default values
                logger.info("No settings found for chat_id=%s, creating new record", chat_id)
                cursor.execute('''
                    INSERT OR IGNORE INTO user_settings (chat_id, fishing_notifications, fishing_sound)
                    VALUES (?, 1, 0)
                ''', (chat_id,))
                
                conn.commit()
                
                # Return default settings
                settings = {
                    'fishing_notifications': True,
                    'fishing_sound': False
                }
                logger.info("Created default settings for chat_id=%s: %s", chat_id, settings)
                conn.close()
                return settings
        except Exception as e:
            logger.error("Error getting/creating user settings for chat_id=%s: %s", chat_id, str(e))
            conn.close()
            # Return default settings in case of error
            default_settings = {
                'fishing_notifications': True,
                'fishing_sound': False
            }
            logger.info("Returning default settings for chat_id=%s due to error: %s", chat_id, default_settings)
            return default_settings
        
    def ensure_user_settings_exist(self, chat_id: int):
        """Убедиться, что у пользователя есть запись в таблице настроек"""
        logger.info("Ensuring settings record exists for chat_id=%s", chat_id)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Проверяем, существует ли запись для данного пользователя
            cursor.execute('''
                SELECT COUNT(*) FROM user_settings WHERE chat_id = ?
            ''', (chat_id,))
            
            result = cursor.fetchone()
            
            # Если записи нет, создаем её с настройками по умолчанию
            if result[0] == 0:
                logger.info("Creating new settings record for chat_id=%s", chat_id)
                cursor.execute('''
                    INSERT INTO user_settings (chat_id, fishing_notifications, fishing_sound)
                    VALUES (?, 1, 0)
                ''', (chat_id,))
                conn.commit()
                logger.info("Settings record created successfully for chat_id=%s", chat_id)
        except Exception as e:
            logger.error("Error ensuring/creating settings record for chat_id=%s: %s", chat_id, str(e))
        finally:
            conn.close()
            
    def update_user_setting(self, chat_id: int, setting_name: str, value: bool):
        """Обновление настройки пользователя"""
        logger.info("Updating setting %s for chat_id=%s to %s", setting_name, chat_id, value)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Make sure user settings row exists
            cursor.execute('''
                INSERT OR IGNORE INTO user_settings (chat_id)
                VALUES (?)
            ''', (chat_id,))
            
            # Update the specific setting
            cursor.execute(f'''
                UPDATE user_settings 
                SET {setting_name} = ?
                WHERE chat_id = ?
            ''', (int(value), chat_id))
            
            conn.commit()
            conn.close()
            logger.info("Setting updated successfully")
            return True
        except Exception as e:
            logger.error("Error updating setting %s for chat_id=%s: %s", setting_name, chat_id, str(e))
            conn.rollback()
            conn.close()
            return False
    
    def get_telegram_user(self, chat_id: int):
        """Получение данных пользователя Telegram"""
        logger.info("Getting telegram user with chat_id=%s", chat_id)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM telegram_users WHERE chat_id = ?', (chat_id,))
        result = cursor.fetchone()
        
        conn.close()
        logger.info("Retrieved telegram user data: %s", result)
        return result
    
    def is_user_linked(self, chat_id: int):
        """Проверка, привязан ли пользователь к Twitch аккаунту"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT twitch_username FROM telegram_users 
            WHERE chat_id = ? AND twitch_username IS NOT NULL
        ''', (chat_id,))
        
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else None
        
    def link_accounts(self, chat_id: int, twitch_username: str):
        """Привязка аккаунта Telegram к аккаунту Twitch"""
        logger.info("Linking telegram chat_id=%s to twitch_username=%s", chat_id, twitch_username)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Проверка существования пользователя Twitch
        cursor.execute('SELECT username FROM players WHERE username = ?', (twitch_username.lower(),))
        user_exists = cursor.fetchone()
        if not user_exists:
            conn.close()
            logger.warning("Twitch user %s does not exist in players table", twitch_username)
            return False
        
        # Привязка аккаунтов
        cursor.execute('''
            UPDATE telegram_users 
            SET twitch_username = ?, link_code = NULL 
            WHERE chat_id = ?
        ''', (twitch_username.lower(), chat_id))
        
        conn.commit()
        conn.close()
        logger.info("Accounts linked successfully")
        return True
    
    def get_user_inventory(self, twitch_username: str):
        """Получение инвентаря рыбы пользователя"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM inventory 
            WHERE username = ? AND item_type = 'fish'
            ORDER BY obtained_at DESC
        ''', (twitch_username.lower(),))
        
        results = cursor.fetchall()
        conn.close()
        return results
    
    def get_fish_by_id(self, fish_id: int):
        """Получение рыбы по ID"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM inventory 
            WHERE id = ? AND item_type = 'fish'
        ''', (fish_id,))
        
        result = cursor.fetchone()
        conn.close()
        return result
    
    def get_user_cooldown(self, twitch_username: str):
        """Получение времени последней рыбалки пользователя"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT last_used FROM cooldowns WHERE username = ?
        ''', (twitch_username.lower(),))
        
        result = cursor.fetchone()
        conn.close()
        return int(result[0]) if result and result[0] else 0

    def update_user_cooldown(self, twitch_username: str, timestamp: int):
        """Обновление времени последней рыбалки пользователя"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO cooldowns (username, last_used)
            VALUES (?, ?)
        ''', (twitch_username.lower(), timestamp))
        
        conn.commit()
        conn.close()

    def can_fish(self, twitch_username: str):
        """Проверка, может ли пользователь рыбачить (прошел ли кулдаун)"""
        import time
        last_fish_time = self.get_user_cooldown(twitch_username)
        current_time = int(time.time())
        try:
            cd_um=self.upgrade_system.get_user_upgrades(twitch_username)
            cd=cd_um['fishing_cooldown_reduction']
            cd = int(self.FISHING_COOLDOWN-self.FISHING_COOLDOWN*cd*0.001)
        except:
            cd=self.FISHING_COOLDOWN
        # 1 hour cooldown = 3600 seconds
        return (current_time - last_fish_time) >= cd
    
    def record_fishing_notification(self, chat_id: int):
        """Записать время отправки уведомления о рыбалке"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO fishing_notifications (chat_id, last_sent)
            VALUES (?, datetime('now'))
        ''', (chat_id,))
        
        conn.commit()
        conn.close()
    
    def clear_fishing_notification(self, chat_id: int):
        """Очистить запись об отправке уведомления (когда пользователь порыбачил)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            DELETE FROM fishing_notifications WHERE chat_id = ?
        ''', (chat_id,))
        
        conn.commit()
        conn.close()
    
    def was_fishing_notification_sent(self, chat_id: int):
        """Проверить, было ли отправлено уведомление о рыбалке"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT last_sent FROM fishing_notifications WHERE chat_id = ?
        ''', (chat_id,))
        
        result = cursor.fetchone()
        conn.close()
        
        return result is not None
    
    def get_users_for_fishing_notification(self):
        """Получить список пользователей, которым нужно отправить уведомление о рыбалке"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT ts.chat_id, ts.twitch_username
            FROM telegram_users ts
            JOIN user_settings us ON ts.chat_id = us.chat_id
            WHERE us.fishing_notifications = 1
        ''')
        
        results = cursor.fetchall()
        conn.close()
        
        return results
    
    RARITY_NAMES_RU = {
        'common': 'Обычная',
        'uncommon': 'Необычная',
        'rare': 'Редкая',
        'epic': 'Эпическая',
        'legendary': 'Легендарная'
    }
    
    FISHING_COOLDOWN = 3600  # 1 hour in seconds
    CURRENCY_NAME = 'LC'  # Lonely Coins
    
    def get_fish_drop_chances(self):
        """Получить шансы выпадения рыбы по редкости"""
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
        self.help_info.info_command(message)

    def help_command(self, message):
        """Обработка команды /help - показ полной информации о функционале бота"""
        self.help_info.help_command(message)

    def contact_lonely(self, message):
        """Обработка связи с Лонли"""
        self.feedback_support.contact_lonely(message)

    def support_lonely(self, message):
        """Показать опции поддержки Лонли"""
        self.feedback_support.support_lonely(message)

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
            url="https://dalink.to/lonely_friend"
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

    def get_fish_data(self,message):
        """Получение данных о доступной рыбе из таблицы items с учетом редкости"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        chat_id=message.chat.id
        user_data = self.get_telegram_user(chat_id)
        twitch_username = user_data[2]
        
        cursor.execute('''
            SELECT * FROM items 
            WHERE type = 'fish'
            ORDER BY id
        ''')
        
        all_fish = cursor.fetchall()
        conn.close()
        
        if not all_fish:
            return None
        
        # Создаем взвешенный список рыбы на основе редкости
        weighted_fish_pool = []
        try:
            fdc =self.upgrade_system.get_user_upgrades(twitch_username)
            fish_chances = fdc.get("rare_fish_chance")
        except:
            fish_chances = 0
        for fish in all_fish:
            # fish[4] это редкость (rarity)
            rarity = fish[4] if fish[4] else "common"
            weight = self.FISH_RARITY_WEIGHTS.get(rarity, 1)+fish_chances
            if fish[6] == 1:
                continue
            # Добавляем рыбу в пул в соответствии с её весом
            weighted_fish_pool.extend([fish] * weight)
        
        # Если пул пустой, возвращаем случайную рыбу из всех доступных
        if not weighted_fish_pool:
            return random.choice(all_fish)
        
        # Возвращаем случайную рыбу из взвешенного пула
        return random.choice(weighted_fish_pool)

    def get_duplicate_fish(self, twitch_username: str):
        """Получение дубликатов рыбы пользователя"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT item_name, COUNT(*) as count, 
                   GROUP_CONCAT(id) as ids, 
                   GROUP_CONCAT(rarity) as rarities,
                   GROUP_CONCAT(value) as fish_values
            FROM inventory 
            WHERE username = ? AND item_type = 'fish'
            GROUP BY item_name
            HAVING COUNT(*) > 1
            ORDER BY MAX(value) ASC
        ''', (twitch_username.lower(),))
        
        results = cursor.fetchall()
        conn.close()
        return results

    def get_user_balance(self, twitch_username: str):
        """Получение баланса пользователя"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT balance FROM players WHERE username = ?
        ''', (twitch_username.lower(),))
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            try:
                return int(result[0]) if result[0] is not None and result[0] != '' else 0
            except (ValueError, TypeError):
                return 0
        return 0

    def get_user_queue_passes(self, twitch_username: str):
        """Получение количества пропусков пользователя"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT passes FROM queue_passes WHERE username = ?
        ''', (twitch_username.lower(),))
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            try:
                return int(result[0]) if result[0] is not None and result[0] != '' else 0
            except (ValueError, TypeError):
                return 0
        return 0

    def add_coins(self, twitch_username: str, amount: int):
        """Добавление или вычитание монет у пользователя"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Получаем текущий баланс
            cursor.execute('''
                SELECT balance FROM players WHERE username = ?
            ''', (twitch_username.lower(),))
            
            result = cursor.fetchone()
            if not result:
                conn.close()
                return 0
            
            try:
                current_balance = int(result[0]) if result[0] is not None and result[0] != '' else 0
            except (ValueError, TypeError):
                current_balance = 0
            
            # Обновляем баланс
            new_balance = current_balance + amount
            cursor.execute('''
                UPDATE players SET balance = ? WHERE username = ?
            ''', (new_balance, twitch_username.lower()))
            
            conn.commit()
            conn.close()
            return new_balance
        except Exception as e:
            conn.rollback()
            conn.close()
            return 0

    def add_queue_pass(self, twitch_username: str, amount: int = 1):
        """Добавление пропусков в очередь пользователю"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Проверяем, существует ли запись
            cursor.execute('''
                SELECT passes FROM queue_passes WHERE username = ?
            ''', (twitch_username.lower(),))
            
            result = cursor.fetchone()
            if result:
                # Обновляем существующую запись
                current_passes = result[0] if result[0] is not None else 0
                new_passes = current_passes + amount
                cursor.execute('''
                    UPDATE queue_passes SET passes = ? WHERE username = ?
                ''', (new_passes, twitch_username.lower()))
            else:
                # Создаем новую запись
                new_passes = amount
                cursor.execute('''
                    INSERT INTO queue_passes (username, passes) VALUES (?, ?)
                ''', (twitch_username.lower(), new_passes))
            
            conn.commit()
            conn.close()
            return new_passes
        except Exception as e:
            conn.rollback()
            conn.close()
            return 0

    def add_fish_to_inventory(self, twitch_username: str, fish_data: dict):
        """Добавление рыбы в инвентарь пользователя"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT INTO inventory 
                (username, item_type, item_id, item_name, rarity, value, obtained_at)
                VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
            ''', (
                twitch_username.lower(), 
                'fish', 
                fish_data.get('id'), 
                fish_data.get('name'), 
                fish_data.get('rarity'), 
                fish_data.get('base_price'),
            ))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            conn.rollback()
            conn.close()
            return False

    def get_unique_untaken_fish(self):
        """Получение списка уникальной (ultimate) рыбы, которая еще не была поймана"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM items WHERE type = "fish" AND rarity = "ultimate" AND is_caught = 0
        ''')
        
        results = cursor.fetchall()
        conn.close()
        
        # Преобразуем результаты в словари
        fish_list = []
        for fish in results:
            fish_dict = {
                'id': fish[0],
                'name': fish[1],
                'type': fish[2],
                'base_price': fish[3],
                'rarity': fish[4],
                'is_unique': fish[5],
                'is_caught': fish[6],
            }
            fish_list.append(fish_dict)
        
        return fish_list

    def mark_fish_as_caught(self, fish_id: int):
        """Пометить рыбу как пойманную"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE items SET is_caught = 1 WHERE id = ?
        ''', (fish_id,))
        
        conn.commit()
        conn.close()

    def get_total_fish_count_by_rarity(self):
        """Получение общего количества рыб по каждой редкости"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT rarity, COUNT(*) as total_count
            FROM items 
            WHERE type = 'fish'
            GROUP BY rarity
        ''')
        
        results = cursor.fetchall()
        conn.close()
        
        # Преобразуем в словарь
        rarity_counts = {}
        for row in results:
            rarity_counts[row[0]] = row[1]
        
        return rarity_counts

    def get_user_unique_fish_by_rarity(self, twitch_username: str, rarity: str):
        """Получение уникальных рыб пользователя по определенной редкости (без повторов)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT DISTINCT item_name
            FROM inventory 
            WHERE username = ? AND item_type = 'fish' AND rarity = ?
            ORDER BY item_name
        ''', (twitch_username.lower(), rarity))
        
        results = cursor.fetchall()
        conn.close()
        
        # Возвращаем список названий рыб
        return [row[0] for row in results]

    def get_user_fish_by_rarity(self, twitch_username: str, rarity: str):
        """Получение списка рыб пользователя по определенной редкости"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT DISTINCT item_name
            FROM inventory 
            WHERE username = ? AND item_type = 'fish' AND rarity = ?
            ORDER BY item_name
        ''', (twitch_username.lower(), rarity))
        
        results = cursor.fetchall()
        conn.close()
        
        # Возвращаем список названий рыб
        return [row[0] for row in results]

    def get_all_fish_names_by_rarity(self, rarity: str):
        """Получение списка всех рыб определенной редкости"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT DISTINCT name
            FROM items 
            WHERE type = 'fish' AND rarity = ?
            ORDER BY name
        ''', (rarity,))
        
        results = cursor.fetchall()
        conn.close()
        
        # Возвращаем список названий рыб
        return [row[0] for row in results]

    def get_all_fish_with_caught_info(self):
        """Получение списка всей рыбы с информацией о том, кто её поймал (для уникальной рыбы)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Получаем все рыбы из таблицы items
        cursor.execute('''
            SELECT * FROM items 
            WHERE type = 'fish'
            ORDER BY 
                CASE rarity
                    WHEN 'common' THEN 1
                    WHEN 'uncommon' THEN 2
                    WHEN 'rare' THEN 3
                    WHEN 'epic' THEN 4
                    WHEN 'legendary' THEN 5
                    WHEN 'immortal' THEN 6
                    WHEN 'mythical' THEN 7
                    WHEN 'arcane' THEN 8
                    WHEN 'ultimate' THEN 9
                END,
                name
        ''')
        
        results = cursor.fetchall()
        conn.close()
        
        # Преобразуем результаты в словари
        fish_list = []
        for fish in results:
            fish_dict = {
                'id': fish[0],
                'name': fish[1],
                'type': fish[2],
                'base_price': fish[3],
                'rarity': fish[4],
                'is_unique': fish[5],
                'is_caught': fish[6],
                'caught_by': None  # Будем заполнять позже для уникальных рыб
            }
            
            # Для уникальных (ultimate) рыб проверяем, кто их поймал
            if fish_dict['rarity'] == 'ultimate' and fish_dict['is_caught'] == 1:
                # Ищем владельца рыбы в таблице inventory
                owner_conn = sqlite3.connect(self.db_path)
                owner_cursor = owner_conn.cursor()
                owner_cursor.execute('''
                    SELECT username FROM inventory 
                    WHERE item_id = ? AND item_type = 'fish'
                    LIMIT 1
                ''', (fish_dict['id'],))
                
                owner_result = owner_cursor.fetchone()
                owner_conn.close()
                
                if owner_result:
                    fish_dict['caught_by'] = owner_result[0]
                else:
                    # Если рыба помечена как пойманная, но владельца нет, исправляем это
                    update_conn = sqlite3.connect(self.db_path)
                    update_cursor = update_conn.cursor()
                    update_cursor.execute('''
                        UPDATE items 
                        SET is_caught = 0 
                        WHERE id = ?
                    ''', (fish_dict['id'],))
                    update_conn.commit()
                    update_conn.close()
                    fish_dict['is_caught'] = 0
            
            fish_list.append(fish_dict)
        
        return fish_list

    def get_user_fish_collection(self, twitch_username: str):
        """Получение коллекции рыбы пользователя, сгруппированной по редкости"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT rarity, COUNT(*) as count, 
                   COUNT(DISTINCT item_name) as unique_count
            FROM inventory 
            WHERE username = ? AND item_type = 'fish'
            GROUP BY rarity
            ORDER BY 
                CASE rarity
                    WHEN 'ultimate' THEN 1
                    WHEN 'arcane' THEN 2
                    WHEN 'mythical' THEN 3
                    WHEN 'immortal' THEN 4
                    WHEN 'legendary' THEN 5
                    WHEN 'epic' THEN 6
                    WHEN 'rare' THEN 7
                    WHEN 'uncommon' THEN 8
                    WHEN 'common' THEN 9
                END
        ''', (twitch_username.lower(),))
        
        results = cursor.fetchall()
        conn.close()
        
        # Преобразуем результаты в словари
        collection = []
        for row in results:
            collection.append({
                'rarity': row[0],
                'total_count': row[1],
                'unique_count': row[2]
            })
        
        return collection


    def sell_fish(self, fish_id: int):
        """Продажа рыбы и увеличение баланса пользователя"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Получаем информацию о рыбе
            cursor.execute('''
                SELECT * FROM inventory 
                WHERE id = ? AND item_type = 'fish'
            ''', (fish_id,))
            
            fish = cursor.fetchone()
            if not fish:
                conn.close()
                return False, "Рыба не найдена"
            
            twitch_username = fish[1]  # имя пользователя
            
            # Проверяем и конвертируем стоимость рыбы
            try:
                fish_value = int(fish[6]) if fish[6] is not None and fish[6] != '' else 0
            except (ValueError, TypeError):
                fish_value = 0
            try:
                fish_modi=self.upgrade_system.get_user_upgrades(twitch_username)
                fish_price += int(fish_value *fish_modi.get("sale_price_increase")*0.001)
            except :
                pass
            # Получаем текущий баланс пользователя из таблицы players
            cursor.execute('''
                SELECT balance FROM players WHERE username = ?
            ''', (twitch_username,))
            
            balance_row = cursor.fetchone()
            if not balance_row:
                conn.close()
                return False, "Пользователь не найден"
            
            # Проверяем и конвертируем текущий баланс
            try:
                current_balance = int(balance_row[0]) if balance_row[0] is not None and balance_row[0] != '' else 0
            except (ValueError, TypeError):
                current_balance = 0
            
            # Удаляем рыбу из инвентаря
            cursor.execute('''
                DELETE FROM inventory 
                WHERE id = ? AND item_type = 'fish'
            ''', (fish_id,))
            
            if cursor.rowcount == 0:
                conn.close()
                return False, "Рыба не найдена"
            
            # Увеличиваем баланс пользователя
            new_balance = current_balance + fish_value
            cursor.execute('''
                UPDATE players 
                SET balance = ? 
                WHERE username = ?
            ''', (new_balance, twitch_username))
            
            conn.commit()
            conn.close()
            return True, f"Рыба продана за {fish_value} LC. Ваш баланс: {new_balance} LC"
            
        except Exception as e:
            conn.rollback()
            conn.close()
            return False, f"Ошибка при продаже рыбы: {str(e)}"
    
    def buy_fish_item(self, chat_id, fish_id):
        """Покупка рыбы"""
        # Получаем данные пользователя
        user_data = self.get_telegram_user(chat_id)
        if not user_data or not user_data[2]:
            try:
                if chat_id in self.user_messages:
                    self.bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=self.user_messages[chat_id],
                        text="❌ Ваш аккаунт не привязан."
                    )
                else:
                    sent_message = self.bot.send_message(chat_id, "❌ Ваш аккаунт не привязан.")
                    self.user_messages[chat_id] = sent_message.message_id
            except:
                sent_message = self.bot.send_message(chat_id, "❌ Ваш аккаунт не привязан.")
                self.user_messages[chat_id] = sent_message.message_id
            return
        
        twitch_username = user_data[2]
        
        # Получаем информацию о рыбе
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM items WHERE id = ?', (fish_id,))
        fish_data = cursor.fetchone()
        conn.close()
        
        if not fish_data:
            try:
                if chat_id in self.user_messages:
                    self.bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=self.user_messages[chat_id],
                        text="❌ Рыба не найдена."
                    )
                else:
                    sent_message = self.bot.send_message(chat_id, "❌ Рыба не найдена.")
                    self.user_messages[chat_id] = sent_message.message_id
            except:
                sent_message = self.bot.send_message(chat_id, "❌ Рыба не найдена.")
                self.user_messages[chat_id] = sent_message.message_id
            return
        
        # Преобразуем данные рыбы в словарь
        fish_dict = {
            'id': fish_data[0],
            'name': fish_data[1],
            'type': fish_data[2],
            'base_price': fish_data[3],
            'rarity': fish_data[4],
            'is_unique': fish_data[5],
            'is_caught': fish_data[6],
        }
        
        fish_name = fish_dict['name']
        fish_rarity = fish_dict['rarity']
        is_unique = fish_dict['rarity'] == 'ultimate'
        is_caught = fish_dict['is_caught'] == 1
        
        skidka = self.upgrade_system.get_user_upgrades(twitch_username)
        skidka = int(skidka.get('shop_discount', 0))*0.00017
        # Получаем цену рыбы из словаря цен
        fish_price = self.buy_fish_price.get(fish_rarity, 100)  # По умолчанию 100
        fish_price= int(fish_price-fish_price*skidka)
        # Проверяем, является ли рыба уникальной и уже пойманной
        if is_unique and is_caught:
            message_text = f"❌ Уникальная рыба <b>{fish_name}</b> уже кем-то поймана и не может быть куплена."
            
            # Создаем клавиатуру
            keyboard = types.InlineKeyboardMarkup()
            
            # Кнопка возврата к покупке рыб
            back_button = types.InlineKeyboardButton(
                text="🔙 Назад к покупке рыб",
                callback_data="buy_fish"
            )
            keyboard.add(back_button)
            
            # Кнопка возврата в меню
            menu_button = types.InlineKeyboardButton(
                text="🏠 В меню",
                callback_data="main_menu"
            )
            keyboard.add(menu_button)
            
            try:
                if chat_id in self.user_messages:
                    try:
                        self.bot.edit_message_text(
                            chat_id=chat_id,
                            message_id=self.user_messages[chat_id],
                            text=message_text,
                            reply_markup=keyboard,
                            parse_mode='HTML'
                        )
                    except telebot.apihelper.ApiException:
                        sent_message = self.bot.send_message(chat_id, message_text, reply_markup=keyboard, parse_mode='HTML')
                        self.user_messages[chat_id] = sent_message.message_id
                else:
                    sent_message = self.bot.send_message(chat_id, message_text, reply_markup=keyboard, parse_mode='HTML')
                    self.user_messages[chat_id] = sent_message.message_id
            except:
                sent_message = self.bot.send_message(chat_id, message_text, parse_mode='HTML')
                self.user_messages[chat_id] = sent_message.message_id
            return
        
        # Показываем подтверждение покупки
        message_text = f"Вы уверены, что хотите купить рыбу <b>{fish_name}</b> за {fish_price} LC?\n"
        message_text += f"Редкость: {self.RARITY_NAMES_RU.get(fish_rarity, fish_rarity)}\n"
        
        
        # Создаем клавиатуру с подтверждением
        keyboard = types.InlineKeyboardMarkup()
        
        # Кнопки подтверждения и отмены
        confirm_button = types.InlineKeyboardButton(
            text="✅ Да, купить", 
            callback_data=f"confirm_buy_fish:{fish_id}"
        )
        cancel_button = types.InlineKeyboardButton(
            text="❌ Отмена", 
            callback_data="buy_fish"
        )
        menu_button = types.InlineKeyboardButton(
            text="🏠 В меню", 
            callback_data="main_menu"
        )
        
        keyboard.add(confirm_button, cancel_button)
        keyboard.add(menu_button)
        
        try:
            if chat_id in self.user_messages:
                try:
                    self.bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=self.user_messages[chat_id],
                        text=message_text,
                        reply_markup=keyboard,
                        parse_mode='HTML'
                    )
                except telebot.apihelper.ApiException:
                    sent_message = self.bot.send_message(chat_id, message_text, reply_markup=keyboard, parse_mode='HTML')
                    self.user_messages[chat_id] = sent_message.message_id
            else:
                sent_message = self.bot.send_message(chat_id, message_text, reply_markup=keyboard, parse_mode='HTML')
                self.user_messages[chat_id] = sent_message.message_id
        except:
            sent_message = self.bot.send_message(chat_id, message_text, parse_mode='HTML')
            self.user_messages[chat_id] = sent_message.message_id

    def confirm_buy_fish(self, chat_id, fish_id):
        """Подтверждение покупки рыбы"""
        # Получаем данные пользователя
        user_data = self.get_telegram_user(chat_id)
        if not user_data or not user_data[2]:
            try:
                if chat_id in self.user_messages:
                    self.bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=self.user_messages[chat_id],
                        text="❌ Ваш аккаунт не привязан."
                    )
                else:
                    sent_message = self.bot.send_message(chat_id, "❌ Ваш аккаунт не привязан.")
                    self.user_messages[chat_id] = sent_message.message_id
            except:
                sent_message = self.bot.send_message(chat_id, "❌ Ваш аккаунт не привязан.")
                self.user_messages[chat_id] = sent_message.message_id
            return
        
        twitch_username = user_data[2]
        
        # Получаем информацию о рыбе
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM items WHERE id = ?', (fish_id,))
        fish_data = cursor.fetchone()
        conn.close()
        
        if not fish_data:
            try:
                if chat_id in self.user_messages:
                    self.bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=self.user_messages[chat_id],
                        text="❌ Рыба не найдена."
                    )
                else:
                    sent_message = self.bot.send_message(chat_id, "❌ Рыба не найдена.")
                    self.user_messages[chat_id] = sent_message.message_id
            except:
                sent_message = self.bot.send_message(chat_id, "❌ Рыба не найдена.")
                self.user_messages[chat_id] = sent_message.message_id
            return
        
        # Преобразуем данные рыбы в словарь
        fish_dict = {
            'id': fish_data[0],
            'name': fish_data[1],
            'type': fish_data[2],
            'base_price': 0,
            'rarity': fish_data[4],
            'is_unique': fish_data[5],
            'is_caught': fish_data[6],
        }
        
        fish_name = fish_dict['name']
        fish_rarity = fish_dict['rarity']
        is_unique = fish_dict['rarity'] == 'ultimate'
        is_caught = fish_dict['is_caught'] == 1
        
        # Получаем цену рыбы из словаря цен
        fish_price = self.buy_fish_price.get(fish_rarity, 100)  # По умолчанию 100
        skidka = self.upgrade_system.get_user_upgrades(twitch_username)
        skidka = int(skidka.get('shop_discount', 0))*0.00017
        fish_price = int(fish_price - fish_price*skidka)
        # Проверяем, является ли рыба уникальной и уже пойманной
        if is_unique and is_caught:
            message_text = f"❌ Уникальная рыба <b>{fish_name}</b> уже кем-то поймана и не может быть куплена."
            
            # Создаем клавиатуру
            keyboard = types.InlineKeyboardMarkup()
            
            # Кнопка возврата к покупке рыб
            back_button = types.InlineKeyboardButton(
                text="🔙 Назад к покупке рыб",
                callback_data="buy_fish"
            )
            keyboard.add(back_button)
            
            # Кнопка возврата в меню
            menu_button = types.InlineKeyboardButton(
                text="🏠 В меню",
                callback_data="main_menu"
            )
            keyboard.add(menu_button)
            
            try:
                if chat_id in self.user_messages:
                    try:
                        self.bot.edit_message_text(
                            chat_id=chat_id,
                            message_id=self.user_messages[chat_id],
                            text=message_text,
                            reply_markup=keyboard,
                            parse_mode='HTML'
                        )
                    except telebot.apihelper.ApiException:
                        sent_message = self.bot.send_message(chat_id, message_text, reply_markup=keyboard, parse_mode='HTML')
                        self.user_messages[chat_id] = sent_message.message_id
                else:
                    sent_message = self.bot.send_message(chat_id, message_text, reply_markup=keyboard, parse_mode='HTML')
                    self.user_messages[chat_id] = sent_message.message_id
            except:
                sent_message = self.bot.send_message(chat_id, message_text, parse_mode='HTML')
                self.user_messages[chat_id] = sent_message.message_id
            return
        
        # Получаем баланс пользователя
        balance = self.get_user_balance(twitch_username)
        
        # Проверяем, достаточно ли средств
        if balance < fish_price:
            message_text = f"❌ Недостаточно LC. Нужно {fish_price} LC, у вас {balance} LC"
            
            # Создаем клавиатуру
            keyboard = types.InlineKeyboardMarkup()
            
            # Кнопка возврата к покупке рыб
            back_button = types.InlineKeyboardButton(
                text="🔙 Назад к покупке рыб",
                callback_data="buy_fish"
            )
            keyboard.add(back_button)
            
            # Кнопка возврата в меню
            menu_button = types.InlineKeyboardButton(
                text="🏠 В меню",
                callback_data="main_menu"
            )
            keyboard.add(menu_button)
            
            try:
                if chat_id in self.user_messages:
                    try:
                        self.bot.edit_message_text(
                            chat_id=chat_id,
                            message_id=self.user_messages[chat_id],
                            text=message_text,
                            reply_markup=keyboard,
                            parse_mode='HTML'
                        )
                    except telebot.apihelper.ApiException:
                        sent_message = self.bot.send_message(chat_id, message_text, reply_markup=keyboard, parse_mode='HTML')
                        self.user_messages[chat_id] = sent_message.message_id
                else:
                    sent_message = self.bot.send_message(chat_id, message_text, reply_markup=keyboard, parse_mode='HTML')
                    self.user_messages[chat_id] = sent_message.message_id
            except:
                sent_message = self.bot.send_message(chat_id, message_text, parse_mode='HTML')
                self.user_messages[chat_id] = sent_message.message_id
            return
        
        # Покупка рыбы
        try:
            # Списываем деньги
            new_balance = self.add_coins(twitch_username, -fish_price)
            
            # Если рыба уникальная, помечаем как пойманную
            if is_unique:
                self.mark_fish_as_caught(fish_id)
            user_data = self.get_telegram_user(chat_id)
            twitch_username = user_data[2]
            # Добавляем рыбу в инвентарь пользователя
            self.add_fish_to_inventory(twitch_username, fish_dict)
            
            # Формируем сообщение об успешной покупке
            message_text = f"🎉 Вы успешно купили рыбу: <b>{fish_name}</b>!\n"
            message_text += f"💰 Стоимость: {fish_price} LC\n"
            message_text += f"💳 Ваш баланс: {new_balance} LC\n"
            message_text += "Рыба добавлена в ваш инвентарь!"
            
            # Создаем клавиатуру
            keyboard = types.InlineKeyboardMarkup()
            
            # Кнопка продолжения покупок
            continue_button = types.InlineKeyboardButton(
                text="🛒 Продолжить покупки",
                callback_data="buy_fish"
            )
            keyboard.add(continue_button)
            
            # Кнопка возврата в меню
            menu_button = types.InlineKeyboardButton(
                text="🏠 В меню",
                callback_data="main_menu"
            )
            keyboard.add(menu_button)
            
            try:
                if chat_id in self.user_messages:
                    try:
                        self.bot.edit_message_text(
                            chat_id=chat_id,
                            message_id=self.user_messages[chat_id],
                            text=message_text,
                            reply_markup=keyboard,
                            parse_mode='HTML'
                        )
                    except telebot.apihelper.ApiException:
                        sent_message = self.bot.send_message(chat_id, message_text, reply_markup=keyboard, parse_mode='HTML')
                        self.user_messages[chat_id] = sent_message.message_id
                else:
                    sent_message = self.bot.send_message(chat_id, message_text, reply_markup=keyboard, parse_mode='HTML')
                    self.user_messages[chat_id] = sent_message.message_id
            except:
                sent_message = self.bot.send_message(chat_id, message_text, parse_mode='HTML')
                self.user_messages[chat_id] = sent_message.message_id
                
        except Exception as e:
            # Обработка ошибок
            message_text = "❌ Произошла ошибка при покупке рыбы. Попробуйте еще раз."
            
            # Создаем клавиатуру
            keyboard = types.InlineKeyboardMarkup()
            
            # Кнопка возврата к покупке рыб
            back_button = types.InlineKeyboardButton(
                text="🔙 Назад к покупке рыб",
                callback_data="buy_fish"
            )
            keyboard.add(back_button)
            
            # Кнопка возврата в меню
            menu_button = types.InlineKeyboardButton(
                text="🏠 В меню",
                callback_data="main_menu"
            )
            keyboard.add(menu_button)
            
            try:
                if chat_id in self.user_messages:
                    try:
                        self.bot.edit_message_text(
                            chat_id=chat_id,
                            message_id=self.user_messages[chat_id],
                            text=message_text,
                            reply_markup=keyboard,
                            parse_mode='HTML'
                        )
                    except telebot.apihelper.ApiException:
                        sent_message = self.bot.send_message(chat_id, message_text, reply_markup=keyboard, parse_mode='HTML')
                        self.user_messages[chat_id] = sent_message.message_id
                else:
                    sent_message = self.bot.send_message(chat_id, message_text, reply_markup=keyboard, parse_mode='HTML')
                    self.user_messages[chat_id] = sent_message.message_id
            except:
                sent_message = self.bot.send_message(chat_id, message_text, parse_mode='HTML')
                self.user_messages[chat_id] = sent_message.message_id

    def show_paste_suggestions(self, call):
        """Show paste suggestions for moderation"""
        try:
            suggestions = get_all_suggestions()
            
            if not suggestions:
                self.bot.answer_callback_query(call.id, "Нет предложений для модерации")
                return
            
            # Create inline keyboard markup
            markup = types.InlineKeyboardMarkup()
            
            # Add buttons for each suggestion
            for suggestion in suggestions:
                markup.add(types.InlineKeyboardButton(
                    f"Просмотреть {suggestion['name']}", 
                    callback_data=f"view_suggestion_{suggestion['id']}"))
            
            markup.add(types.InlineKeyboardButton("Назад", callback_data="aprovemenu"))
            
            # Send the menu message
            self.bot.edit_message_text(
                "Предложения для модерации:",
                call.message.chat.id,
                call.message.message_id,
                reply_markup=markup
            )
        except Exception as e:
            logger.error(f"Error in show_paste_suggestions: {e}")
            self.bot.answer_callback_query(call.id, "Произошла ошибка при обработке запроса.")

    def approve_paste_suggestion(self, call):
        """Approve a paste suggestion"""
        try:
            suggestion_id = int(call.data.split("_")[2])
            
            if approve_suggestion(suggestion_id):
                self.bot.answer_callback_query(call.id, "Паста одобрена")
                # Refresh the suggestions view
                self.show_paste_suggestions(call)
            else:
                self.bot.answer_callback_query(call.id, "Ошибка при одобрении пасты")
        except Exception as e:
            logger.error(f"Error in approve_paste_suggestion: {e}")
            self.bot.answer_callback_query(call.id, "Произошла ошибка")

    def reject_paste_suggestion(self, call):
        """Reject a paste suggestion"""
        try:
            suggestion_id = int(call.data.split("_")[2])
            
            if reject_suggestion(suggestion_id):
                self.bot.answer_callback_query(call.id, "Паста отклонена")
                # Refresh the suggestions view
                self.show_paste_suggestions(call)
            else:
                self.bot.answer_callback_query(call.id, "Ошибка при отклонении пасты")
        except Exception as e:
            logger.error(f"Error in reject_paste_suggestion: {e}")
            self.bot.answer_callback_query(call.id, "Произошла ошибка")

    def show_pastes(self, chat_id, page=0):
        """Show the list of available pastes"""
        try:
            pastes = get_all_approved_pastes()
            
            if not pastes:
                self.bot.send_message(chat_id, "Пока нет ни одной пасты.")
                return
            
            # Pagination variables
            ITEMS_PER_PAGE = 5
            total_pages = (len(pastes) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
            
            if page < 0:
                page = 0
            elif page >= total_pages:
                page = total_pages - 1
            
            start_index = page * ITEMS_PER_PAGE
            end_index = min(start_index + ITEMS_PER_PAGE, len(pastes))
            page_pastes = pastes[start_index:end_index]
            
            # Format the list
            response = f"Список доступных паст (Страница {page + 1}/{total_pages}):\n\n"
            for paste in page_pastes:
                response += f"{paste['paste_num']}. {paste['name']}\n {paste['text']}\n"
            
            # Create inline keyboard markup
            markup = types.InlineKeyboardMarkup()
            
            # Navigation buttons
            nav_buttons = []
            if page > 0:
                nav_buttons.append(types.InlineKeyboardButton(
                    "⬅️ Назад", 
                    callback_data=f"pastes_page:{page - 1}"))
            
            if page < total_pages - 1:
                nav_buttons.append(types.InlineKeyboardButton(
                    "Вперёд ➡️", 
                    callback_data=f"pastes_page:{page + 1}"))
            
            if nav_buttons:
                markup.row(*nav_buttons)
            
            markup.add(types.InlineKeyboardButton("Назад", callback_data="main_menu"))
            
            self.bot.send_message(chat_id, response, reply_markup=markup)
        except Exception as e:
            logger.error(f"Error in show_pastes: {e}")
            self.bot.send_message(chat_id, "Произошла ошибка при отображении списка паст.")

    def show_manage_pastes_menu(self, call):
        """Show menu for managing existing pastes"""
        try:
            pastes = get_all_approved_pastes()
            
            if not pastes:
                self.bot.answer_callback_query(call.id, "Нет паст для управления")
                return
            
            # Pagination variables
            ITEMS_PER_PAGE = 5
            page = 0
            
            # Check if page number is specified in callback data
            if ":" in call.data:
                page = int(call.data.split(":")[1])
            
            total_pages = (len(pastes) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
            start_index = page * ITEMS_PER_PAGE
            end_index = min(start_index + ITEMS_PER_PAGE, len(pastes))
            page_pastes = pastes[start_index:end_index]
            
            # Format the list
            response = f"Управление пастами (Страница {page + 1}/{total_pages}):\n\n"
            for paste in page_pastes:
                response += f"{paste['paste_num']}. {paste['name']}\n {paste['text']}\n"
            
            # Create inline keyboard markup
            markup = types.InlineKeyboardMarkup()
            
            # Add a button for each paste to view/delete
            for paste in page_pastes:
                markup.add(types.InlineKeyboardButton(
                    f"Удалить {paste['name']}", 
                    callback_data=f"delete_paste_{paste['paste_num']}"))
            
            # Add navigation buttons
            nav_buttons = []
            if page > 0:
                nav_buttons.append(types.InlineKeyboardButton(
                    "⬅️ Назад", 
                    callback_data=f"manage_pastes_page:{page - 1}"))
            
            if page < total_pages - 1:
                nav_buttons.append(types.InlineKeyboardButton(
                    "Вперёд ➡️", 
                    callback_data=f"manage_pastes_page:{page + 1}"))
            
            if nav_buttons:
                markup.row(*nav_buttons)
            
            markup.add(types.InlineKeyboardButton("Назад", callback_data="aprovemenu"))
            
            # Edit the message with the new content and buttons
            self.bot.edit_message_text(
                response,
                call.message.chat.id,
                call.message.message_id,
                reply_markup=markup
            )
        except Exception as e:
            logger.error(f"Error in show_manage_pastes_menu: {e}")
            self.bot.answer_callback_query(call.id, "Произошла ошибка")

    def is_paste_moder(self, chat_id):
        user_data = self.get_telegram_user(chat_id)
        channel_owners = ["perolya", "lonely_fr", "lizamoloko"]
        if user_data and user_data[2] in channel_owners:
            return True
    
    def can_reboot(self, chat_id):
        user_data = self.get_telegram_user(chat_id)
        channel_owners = ["perolya", "lonely_fr"]
        if user_data and user_data[2] in channel_owners:
            return True
        
    def pastes_menu(self, chat_id):
        """Show the pastes menu to the user"""
        try:
            # Create inline keyboard markup
            markup = types.InlineKeyboardMarkup()
            
            # Add buttons for paste functionality
            markup.add(types.InlineKeyboardButton("Просмотреть пасты", callback_data="pastes_page:0"))
            markup.add(types.InlineKeyboardButton("Предложить пасту", callback_data="suggest_paste"))
            markup.add(types.InlineKeyboardButton("Назад", callback_data="main_menu"))
            
            # Send the menu message
            self.bot.send_message(
                chat_id, 
                "📋 Меню паст:\n\n"
                "• Просмотреть пасты - Посмотреть список доступных паст\n"
                "• Предложить пасту - Предложить свою пасту на рассмотрение",
                reply_markup=markup
            )
        except Exception as e:
            logger.error(f"Error in pastes_menu: {e}")

    def aprove_menu(self, chat_id):
        """Show the paste approval menu (for moderators)"""
        try:
            # Create inline keyboard markup
            markup = types.InlineKeyboardMarkup()
            
            # Add buttons for moderator functionality
            markup.add(types.InlineKeyboardButton("Просмотреть предложения", callback_data="mod_suggestions"))
            markup.add(types.InlineKeyboardButton("Управление пастами", callback_data="manage_pastes_page:0"))
            markup.add(types.InlineKeyboardButton("Назад", callback_data="main_menu"))
            
            # Send the menu message
            self.bot.send_message(
                chat_id,
                "🔒 Меню модератора паст:\n\n"
                "• Просмотреть предложения - Посмотреть пасты, предложенные пользователями\n"
                "• Управление пастами - Управление уже одобренными пастами",
                reply_markup=markup
            )
        except Exception as e:
            logger.error(f"Error in aprove_menu: {e}")

    def balance_command(self, message):
        """Обработка команды /balance"""
        chat_id = message.chat.id
        
        # Проверяем, привязан ли пользователь
        user_data = self.get_telegram_user(chat_id)
        
        if not user_data or not user_data[2]:  # Не привязан
            message_text = "Ваш аккаунт не привязан. Используйте команду /link для привязки."
            
            # Добавляем кнопку возврата в меню
            keyboard = types.InlineKeyboardMarkup()
            back_button = types.InlineKeyboardButton(
                text="🔙 Назад в меню", 
                callback_data="main_menu"
            )
            keyboard.add(back_button)
            
            try:
                sent_message = self.bot.send_message(message.chat.id, message_text, reply_markup=keyboard)
                self.user_messages[chat_id] = sent_message.message_id
            except:
                pass
            return
        
        # Получаем баланс пользователя
        twitch_username = user_data[2]
        balance = self.get_user_balance(twitch_username)
        passes = self.get_user_passes(twitch_username)
        
        message_text = f"💳 Ваш текущий баланс: {balance} LC\n"
        message_text += f"🎟 Ваши пропуски: {passes} шт."
        
        # Добавляем кнопки
        keyboard = types.InlineKeyboardMarkup()
        
        # Кнопка продажи пропуска (только если есть пропуски)
        if passes > 0:
            sell_pass_button = types.InlineKeyboardButton(
                text="💰 Продать 1 пропуск (2250 LC)", 
                callback_data="sell_pass"
            )
            keyboard.add(sell_pass_button)
        
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


    def suggest_paste(self, chat_id):
        """Start the process of suggesting a new paste"""
        try:
            # Ask for paste name
            msg = self.bot.send_message(chat_id, "Введите название для новой пасты (не более 35 символов):")
            self.bot.register_next_step_handler(msg, self.process_paste_name_step)
        except Exception as e:
            logger.error(f"Error in suggest_paste: {e}")
            self.bot.send_message(chat_id, "Произошла ошибка при обработке запроса.")

    def process_paste_name_step(self, message):
        """Process paste name input"""
        try:
            name = message.text.strip()
            
            if len(name) > 35:
                self.bot.reply_to(message, "Название слишком длинное. Попробуйте ещё раз команду")
                return
            
            if len(name) == 0:
                self.bot.reply_to(message, "Название не может быть пустым. Попробуйте ещё раз команду")
                return
            
            # Store name in user state and ask for text
            chat_id = message.chat.id
            if chat_id not in self.user_states:
                self.user_states[chat_id] = {}
            
            self.user_states[chat_id]['paste_name'] = name
            
            msg = self.bot.reply_to(message, "Введите текст пасты (не более 450 символов):")
            self.bot.register_next_step_handler(msg, self.process_paste_text_step)
        except Exception as e:
            logger.error(f"Error in process_paste_name_step: {e}")
            self.bot.reply_to(message, "Произошла ошибка при обработке запроса.")

    def process_paste_text_step(self, message):
        """Process paste text input"""
        try:
            chat_id = message.chat.id
            name = self.user_states.get(chat_id, {}).get('paste_name', '')
            
            if not name:
                self.bot.reply_to(message, "Произошла ошибка. Попробуйте ещё раз команду")
                return
            
            text = message.text.strip()
            
            if len(text) > 450:
                self.bot.reply_to(message, "Текст слишком длинный. Попробуйте ещё раз")
                return
            
            if len(text) == 0:
                self.bot.reply_to(message, "Текст не может быть пустым. Попробуйте ещё раз")
                return
            
            # Get Twitch username if linked
            user_data = self.get_telegram_user(chat_id)
            twitch_username = user_data[2] if user_data and len(user_data) > 2 else None
            
            # Suggest the paste
            if suggest_paste(twitch_username or f"tg_{chat_id}", name, text):
                self.bot.reply_to(message, "Ваша паста отправлена на модерацию. Спасибо за предложение!")
            else:
                self.bot.reply_to(message, "Паста с таким названием уже существует. Попробуйте другое название.")
            
            # Clear user state
            if chat_id in self.user_states:
                self.user_states[chat_id].pop('paste_name', None)
        except Exception as e:
            logger.error(f"Error in process_paste_text_step: {e}")
            self.bot.reply_to(message, "Произошла ошибка при обработке запроса.")

    def get_user_passes(self, twitch_username: str):
        """Получение количества пропусков пользователя"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT passes FROM queue_passes WHERE username = ?
        ''', (twitch_username.lower(),))
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            try:
                return int(result[0]) if result[0] is not None and result[0] != '' else 0
            except (ValueError, TypeError):
                return 0
        return 0

    def change_setting(self, chat_id, setting_name, call_id=None):
        """Изменить конкретную настройку пользователя"""
        # Получаем текущие настройки
        settings = self.get_user_settings(chat_id)
        
        # Получаем текущее значение настройки
        current_value = settings.get(setting_name, False)
        
        # Инвертируем значение
        new_value = not current_value
        
        # Обновляем настройку в базе данных
        self.update_user_setting(chat_id, setting_name, new_value)
        
        # Логируем изменение
        logger.info("User %s changed setting %s from %s to %s", chat_id, setting_name, current_value, new_value)
        
        # Отправляем подтверждение действия
        if call_id:
            status_text = ""
            if setting_name == 'fishing_notifications':
                status_text = "включены" if new_value else "выключены"
                feedback_text = f"Уведомления {status_text}"
            elif setting_name == 'fishing_sound':
                status_text = "включен" if new_value else "выключен"
                feedback_text = f"Звук уведомлений {status_text}"
            
            try:
                self.bot.answer_callback_query(call_id, feedback_text, show_alert=False)
            except:
                pass
        
        # Показываем обновленное меню настроек
        self.show_settings_menu(chat_id)

    def upgrades_command(self, message):
        """Handle the /upgrades command"""
        self.upgrade_handler.upgrades_command(message)

    def toggle_fishing_notifications(self, chat_id, call_id=None):
        """Переключить настройку уведомлений о рыбалке"""
        self.change_setting(chat_id, 'fishing_notifications', call_id)
    
    def toggle_fishing_sound(self, chat_id, call_id=None):
        """Переключить настройку звука уведомлений"""
        self.change_setting(chat_id, 'fishing_sound', call_id)
    
    def show_settings_menu(self, chat_id):
        """Показать меню настроек"""
        # Убедимся, что у пользователя есть запись в таблице настроек
        self.ensure_user_settings_exist(chat_id)
        
        # Получаем текущие настройки пользователя
        settings = self.get_user_settings(chat_id)
        
        # Формируем текст сообщения
        message_text = "⚙️ <b>Настройки</b>\n\n"
        message_text += "Здесь вы можете настроить уведомления и другие параметры бота:\n\n"
        
        # Формируем статус настроек
        notifications_status = "включены" if settings['fishing_notifications'] else "выключены"
        sound_status = "включен" if settings['fishing_sound'] else "выключен"
        
        message_text += f"• Уведомления о готовности рыбалки: <b>{notifications_status}</b>\n"
        message_text += f"• Звук уведомлений: <b>{sound_status}</b>\n\n"
        
        # Создаем клавиатуру с кнопками настроек
        keyboard = types.InlineKeyboardMarkup()
        
        # Кнопка для переключения уведомлений
        if settings['fishing_notifications']:
            notifications_button = types.InlineKeyboardButton(
                text="🔔 Уведомления: ВКЛ (нажмите для выключения)",
                callback_data="toggle_fishing_notifications"
            )
        else:
            notifications_button = types.InlineKeyboardButton(
                text="🔕 Уведомления: ВЫКЛ (нажмите для включения)",
                callback_data="toggle_fishing_notifications"
            )
        keyboard.add(notifications_button)
        
        # Кнопка для переключения звука
        if settings['fishing_sound']:
            sound_button = types.InlineKeyboardButton(
                text="🔊 Звук: ВКЛ (нажмите для выключения)",
                callback_data="toggle_fishing_sound"
            )
        else:
            sound_button = types.InlineKeyboardButton(
                text="🔇 Звук: ВЫКЛ (нажмите для включения)",
                callback_data="toggle_fishing_sound"
            )
        keyboard.add(sound_button)
        
        # Кнопка для перепривязки аккаунта
        relink_button = types.InlineKeyboardButton(
            text="🔄 Перепривязать аккаунт",
            callback_data="relink_account"
        )
        keyboard.add(relink_button)
        
        # Кнопка возврата в меню
        menu_button = types.InlineKeyboardButton(
            text="🔙 Назад в меню", 
            callback_data="main_menu"
        )
        keyboard.add(menu_button)
        
        try:
            if chat_id in self.user_messages:
                try:
                    self.bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=self.user_messages[chat_id],
                        text=message_text,
                        reply_markup=keyboard,
                        parse_mode='HTML'
                    )
                except telebot.apihelper.ApiException:
                    sent_message = self.bot.send_message(chat_id, message_text, reply_markup=keyboard, parse_mode='HTML')
                    self.user_messages[chat_id] = sent_message.message_id
            else:
                sent_message = self.bot.send_message(chat_id, message_text, reply_markup=keyboard, parse_mode='HTML')
                self.user_messages[chat_id] = sent_message.message_id
        except:
            sent_message = self.bot.send_message(chat_id, message_text, parse_mode='HTML')
            self.user_messages[chat_id] = sent_message.message_id
    
    def sell_pass(self, chat_id):
        """Продажа одного пропуска за 2250 LC"""
        # Получаем данные пользователя
        user_data = self.get_telegram_user(chat_id)
        if not user_data or not user_data[2]:
            try:
                if chat_id in self.user_messages:
                    self.bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=self.user_messages[chat_id],
                        text="❌ Ваш аккаунт не привязан."
                    )
                else:
                    sent_message = self.bot.send_message(chat_id, "❌ Ваш аккаунт не привязан.")
                    self.user_messages[chat_id] = sent_message.message_id
            except:
                sent_message = self.bot.send_message(chat_id, "❌ Ваш аккаунт не привязан.")
                self.user_messages[chat_id] = sent_message.message_id
            return
        
        twitch_username = user_data[2]
        passes = self.get_user_passes(twitch_username)
        keyboard = types.InlineKeyboardMarkup()
        back_button = types.InlineKeyboardButton(
                text="🔙 Назад в меню", 
                callback_data="main_menu"
            )
        # Проверяем, есть ли у пользователя пропуски
        if passes <= 0:
            message_text = "❌ У вас нет пропусков для продажи."
            
            # Создаем клавиатуру
            keyboard = types.InlineKeyboardMarkup()
            back_button = types.InlineKeyboardButton(
                text="🔙 Назад в меню", 
                callback_data="main_menu"
            )
            keyboard.add(back_button)
            
            try:
                if chat_id in self.user_messages:
                    self.bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=self.user_messages[chat_id],
                        text=message_text,
                        reply_markup=keyboard
                    )
                else:
                    sent_message = self.bot.send_message(chat_id, message_text, reply_markup=keyboard)
                    self.user_messages[chat_id] = sent_message.message_id
            except:
                sent_message = self.bot.send_message(chat_id, message_text, reply_markup=keyboard)
                self.user_messages[chat_id] = sent_message.message_id
            return
        
        # Продаем пропуск
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Уменьшаем количество пропусков на 1
            new_passes = passes - 1
            cursor.execute('''
                INSERT OR REPLACE INTO queue_passes (username, passes)
                VALUES (?, ?)
            ''', (twitch_username.lower(), new_passes))
            
            # Добавляем 2250 LC на баланс
            conn.commit()
            conn.close()
            reward = 2250
            try:
                fish_modi=self.upgrade_system.get_user_upgrades(twitch_username)
                reward += int(reward *fish_modi.get("sale_price_increase")*0.001)
            except :
                pass
            new_balance = self.add_coins(twitch_username, reward)
                        
            # Формируем сообщение об успешной продаже
            message_text = f"✅ Вы успешно продали 1 пропуск за {reward} LC!\n"
            message_text += f"💳 Ваш новый баланс: {new_balance} LC\n"
            message_text += f"🎟 Ваши пропуски: {new_passes} шт."
            
            # Если остались пропуски, добавляем кнопку для повторной продажи
            if new_passes > 0:
                sell_pass_button = types.InlineKeyboardButton(
                    text="💰 Продать 1 пропуск (2250 LC)", 
                    callback_data="sell_pass"
                )
                keyboard.add(sell_pass_button)
            
            
            try:
                if chat_id in self.user_messages:
                    self.bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=self.user_messages[chat_id],
                        text=message_text,
                        reply_markup=keyboard,
                        parse_mode='HTML'
                    )
                else:
                    sent_message = self.bot.send_message(chat_id, message_text, reply_markup=keyboard, parse_mode='HTML')
                    self.user_messages[chat_id] = sent_message.message_id
            except:
                sent_message = self.bot.send_message(chat_id, message_text, reply_markup=keyboard, parse_mode='HTML')
                self.user_messages[chat_id] = sent_message.message_id
                
        except Exception as e:
            conn.rollback()
            message_text = f"❌ Ошибка при продаже пропуска: {str(e)}"
            keyboard = types.InlineKeyboardMarkup()
            back_button = types.InlineKeyboardButton(
                text="🔙 Назад в меню", 
                callback_data="main_menu"
            )
            keyboard.add(back_button)
            
            try:
                sent_message = self.bot.send_message(chat_id, message_text, reply_markup=keyboard)
                self.user_messages[chat_id] = sent_message.message_id
            except:
                pass
        finally:
            conn.close()
            # Кнопка возврата в меню
            menu_button = types.InlineKeyboardButton(
                text="🏠 В меню",
                callback_data="main_menu"
            )
            keyboard.add(menu_button)
            
            try:
                if chat_id in self.user_messages:
                    try:
                        self.bot.edit_message_text(
                            chat_id=chat_id,
                            message_id=self.user_messages[chat_id],
                            text=message_text,
                            reply_markup=keyboard,
                            parse_mode='HTML'
                        )
                    except telebot.apihelper.ApiException:
                        sent_message = self.bot.send_message(chat_id, message_text, reply_markup=keyboard, parse_mode='HTML')
                        self.user_messages[chat_id] = sent_message.message_id
                else:
                    sent_message = self.bot.send_message(chat_id, message_text, reply_markup=keyboard, parse_mode='HTML')
                    self.user_messages[chat_id] = sent_message.message_id
            except:
                sent_message = self.bot.send_message(chat_id, message_text, parse_mode='HTML')
                self.user_messages[chat_id] = sent_message.message_id

    def link_command(self, message):
        """Обработка команды /link"""
        chat_id = message.chat.id
        logger.info("Handling /link command from chat_id=%s", chat_id)
        
        # Проверяем, привязан ли пользователь
        existing_link = self.is_user_linked(chat_id)
        if existing_link:
            # Если уже привязан, спрашиваем подтверждение
            logger.info("User %s is already linked to twitch user %s", chat_id, existing_link)
            confirm_message = (
                f"Ваш аккаунт уже привязан к Twitch аккаунту: {existing_link}\n"
                "Хотите изменить привязку?"
            )
            
            # Создаем клавиатуру с подтверждением
            keyboard = types.InlineKeyboardMarkup()
            confirm_button = types.InlineKeyboardButton(
                text="✅ Да, изменить", 
                callback_data="confirm_relink:yes"
            )
            cancel_button = types.InlineKeyboardButton(
                text="❌ Отмена", 
                callback_data="confirm_relink:no"
            )
            back_button = types.InlineKeyboardButton(
                text="🔙 Назад в меню", 
                callback_data="main_menu"
            )
            keyboard.add(confirm_button, cancel_button)
            keyboard.add(back_button)
            
            # Сохраняем состояние пользователя
            self.user_states[chat_id] = {
                'state': 'confirm_relink',
                'message_id': message.message_id
            }
            
            try:
                sent_message = self.bot.reply_to(
                    message, 
                    confirm_message, 
                    reply_markup=keyboard
                )
                self.user_messages[chat_id] = sent_message.message_id
                logger.info("Sent relink confirmation message to chat_id=%s", chat_id)
            except Exception as e:
                logger.error("Failed to send relink confirmation to chat_id=%s: %s", chat_id, str(e))
                pass
            return
        
        # Генерация кода привязки
        link_code = self.generate_link_code()
        logger.info("Generated link code %s for chat_id=%s", link_code, chat_id)
        
        # Сохранение пользователя с кодом привязки
        self.save_telegram_user(chat_id, link_code)
        
        # Сохранение в ожидаемых привязках
        self.pending_links[link_code] = chat_id
        
        link_message = (
            f"Ваш код для привязки аккаунта: !linktg {link_code}\n"
            "Отправьте этот код в чат Twitch, чтобы подтвердить привязку аккаунта.\n"
            "После этого вы сможете просматривать свою рыбу здесь."
        )
        
        # Добавляем кнопку возврата в меню
        keyboard = types.InlineKeyboardMarkup()
        back_button = types.InlineKeyboardButton(
            text="🔙 Назад в меню", 
            callback_data="main_menu"
        )
        keyboard.add(back_button)
        
        try:
            sent_message = self.bot.send_message(message.chat.id, link_message, reply_markup=keyboard)
            self.user_messages[chat_id] = sent_message.message_id
            logger.info("Sent link code %s to chat_id=%s", link_code, chat_id)
        except Exception as e:
            logger.error("Failed to send link code to chat_id=%s: %s", chat_id, str(e))
            pass
    
    def all_fish_command(self, message):
        """Обработка команды для отображения всех рыб"""
        chat_id = message.chat.id
        
        # Получаем все рыбы
        all_fish = self.get_all_fish_with_caught_info()
        
        if not all_fish:
            message_text = "В базе данных нет рыбы."
            try:
                sent_message = self.bot.send_message(chat_id, message_text)
                self.user_messages[chat_id] = sent_message.message_id
            except:
                pass
            return
        
        # Отображаем первую страницу
        self.show_all_fish_page(chat_id, all_fish, 0)

    def my_collection_command(self, message):
        """Обработка команды для отображения коллекции пользователя"""
        chat_id = message.chat.id
        
        # Проверяем, привязан ли пользователь
        user_data = self.get_telegram_user(chat_id)
        
        if not user_data or not user_data[2]:  # Не привязан
            message_text = "Ваш аккаунт не привязан. Используйте команду /link для привязки."
            
            # Добавляем кнопку возврата в меню
            keyboard = types.InlineKeyboardMarkup()
            back_button = types.InlineKeyboardButton(
                text="🔙 Назад в меню", 
                callback_data="main_menu"
            )
            keyboard.add(back_button)
            
            try:
                sent_message = self.bot.send_message(message.chat.id, message_text, reply_markup=keyboard)
                self.user_messages[chat_id] = sent_message.message_id
            except:
                pass
            return
        
        # Получаем коллекцию пользователя
        twitch_username = user_data[2]
        
        # Получаем общее количество рыб по редкостям
        total_fish_by_rarity = self.get_total_fish_count_by_rarity()
        
        # Формируем сообщение
        message_text = "📊 <b>Ваша коллекция рыб</b>\n\n"
        
        # Сортируем редкости по порядку от самой обычной к самой редкой
        rarity_order = [
            'common', 'uncommon', 'rare', 'epic', 
            'legendary', 'immortal', 'mythical', 'arcane', 'ultimate'
        ]
        
        keyboard = types.InlineKeyboardMarkup()
        has_collection = False
        
        for rarity in rarity_order:
            # Получаем все рыбы этой редкости
            all_rarity_fish = self.get_all_fish_names_by_rarity(rarity)
            total_count = len(all_rarity_fish)
            
            # Получаем уникальные рыбы этой редкости у пользователя (без повторов)
            user_rarity_fish = self.get_user_unique_fish_by_rarity(twitch_username, rarity)
            user_count = len(user_rarity_fish)
            
            # Проверяем, есть ли рыбы этой редкости в базе данных
            if total_count > 0:
                has_collection = True
                rarity_name = self.RARITY_NAMES_RU.get(rarity, rarity)
                message_text += f"<b>{rarity_name}</b> - {user_count} из {total_count}\n"
                
                # Добавляем кнопку для просмотра недостающих рыб этой редкости
                if user_count < total_count:
                    missing_button = types.InlineKeyboardButton(
                        text=f"🔎 {rarity_name} (не хватает {total_count - user_count})",
                        callback_data=f"missing_fish:{rarity}"
                    )
                    keyboard.add(missing_button)
                message_text += "\n"
        
        if not has_collection:
            message_text = "У вас пока нет рыбы в коллекции."
        
        # Добавляем кнопку возврата в меню
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
    

    def fish_command(self, message):
        """Обработка команды /fish"""
        print (1)
        chat_id = message.chat.id
        logger.info("Handling /fish command from chat_id=%s", chat_id)
        
        # Сохраняем ID сообщения
        try:
            self.user_messages[chat_id] = message.message_id
        except:
            pass
        
        # Проверяем, привязан ли пользователь
        user_data = self.get_telegram_user(chat_id)
        
        if not user_data or not user_data[2]:  # Не привязан
            message_text = "Ваш аккаунт не привязан. Используйте команду /link для привязки."
            logger.warning("User %s tried to view fish but is not linked", chat_id)
            try:
                sent_message = self.bot.send_message(chat_id, message_text)
                self.user_messages[chat_id] = sent_message.message_id
                logger.info("Sent not linked message to chat_id=%s", chat_id)
            except Exception as e:
                logger.error("Failed to send not linked message to chat_id=%s: %s", chat_id, str(e))
                pass
            return
        
        # Получаем инвентарь пользователя
        inventory = self.get_user_inventory(user_data[2])  # user_data[2] это twitch_username
        logger.info("Retrieved inventory for user %s, found %d fish", user_data[2], len(inventory))
        
        if not inventory:
            message_text = "У вас пока нет рыбы."
            try:
                sent_message = self.bot.send_message(chat_id, message_text)
                self.user_messages[chat_id] = sent_message.message_id
                logger.info("Sent no fish message to chat_id=%s", chat_id)
            except Exception as e:
                logger.error("Failed to send no fish message to chat_id=%s: %s", chat_id, str(e))
                pass
            return
        
        # Отображаем первую страницу
        logger.info("Showing fish page 0 to chat_id=%s", chat_id)
        self.show_fish_page(chat_id, inventory, 0)
    
    @staticmethod
    def calculate_remaining_cooldown(last_used_time, cooldown_duration):
        """Calculate remaining cooldown time"""
        import time
        current_time = int(time.time())
        elapsed_time = current_time - last_used_time
        remaining_time = max(0, cooldown_duration - elapsed_time)
        return remaining_time

    def fish_telegram(self, message):
        """Обработчик команды рыбалки в Telegram"""
        chat_id = message.chat.id
        logger.info("Handling /catch command from chat_id=%s", chat_id)
        keyboard = types.InlineKeyboardMarkup()
        # Кнопка возврата в меню
        menu_button = types.InlineKeyboardButton(
            text="🔙 Назад в меню", 
            callback_data="main_menu"
        )
        keyboard.add(menu_button)
        # Проверяем, привязан ли аккаунт пользователя
        user_data = self.get_telegram_user(chat_id)
        if not user_data or not user_data[2]:  # twitch_username is None or empty
            message_text = "Ваш аккаунт не привязан. Используйте команду /link для привязки."
            logger.warning("User %s tried to catch fish but is not linked", chat_id)
            try:
                sent_message = self.bot.send_message(message.chat.id, message_text, reply_markup=keyboard)
                self.user_messages[chat_id] = sent_message.message_id
                logger.info("Sent not linked message to chat_id=%s", chat_id)
            except Exception as e:
                logger.error("Failed to send not linked message to chat_id=%s: %s", chat_id, str(e))
                pass
            return
        
        twitch_username = user_data[2]
        
        # Проверяем кулдаун
        last_fish_time = self.get_user_cooldown(twitch_username)
        if not self.can_fish(twitch_username) and twitch_username !="lonely_fr":
            try:
                cd_um=self.upgrade_system.get_user_upgrades(twitch_username)
                cd=cd_um.get('fishing_cooldown_reduction', 0)
                cd = self.FISHING_COOLDOWN-self.FISHING_COOLDOWN*cd*0.001
            except:
                cd=self.FISHING_COOLDOWN
            remaining_time = self.calculate_remaining_cooldown(last_fish_time, cd)
            hours = remaining_time // 3600
            minutes = (remaining_time % 3600) // 60
            secundes = ((remaining_time % 3600) % 60 )
            cooldown_message = f"⏳ Подождите перед следующей рыбалкой. Осталось: {int(minutes)}м {int(secundes)}с"
            logger.info("User %s is on cooldown, remaining time: %d seconds", twitch_username, remaining_time)
            
            try:
                sent_message = self.bot.send_message(message.chat.id, cooldown_message, reply_markup=keyboard)
                self.user_messages[chat_id] = sent_message.message_id
                logger.info("Sent cooldown message to chat_id=%s", chat_id)
            except Exception as e:
                logger.error("Failed to send cooldown message to chat_id=%s: %s", chat_id, str(e))
                pass
            return
        try:
            self.add_fish_to_user(message)
            try:
                fish_multiply=self.upgrade_system.get_user_upgrades(twitch_username)
                fishi_fishi = fish_multiply.get("double_catch_chance")
                for i in range(4):
                    if random.random() < fishi_fishi*0.001:
                        self.add_fish_to_user(message)
                    fishi_fishi-=1
                    if fishi_fishi<=0:
                        break
            except:
                pass
        except:
            pass
        try:
            # Обновляем кулдаун пользователя
            self.update_user_cooldown(twitch_username, int(time.time()))
            
            # Очищаем запись об отправке уведомления
            self.clear_fishing_notification(chat_id)
        except sqlite3.Error as e:
            # Обработка ошибок базы данных
            logger.error("Database error while catching fish for chat_id=%s: %s", chat_id, str(e))
            try:
                sent_message = self.bot.send_message(message.chat.id, "❌ Произошла ошибка при добавлении рыбы в инвентарь.", reply_markup=keyboard)
                self.user_messages[chat_id] = sent_message.message_id
                logger.info("Sent database error message to chat_id=%s", chat_id)
            except Exception as e:
                logger.error("Failed to send database error message to chat_id=%s: %s", chat_id, str(e))
                pass
            logger.error(f"Database error in fish_telegram: {e}")

    def add_fish_to_user(self, message):
        keyboard = types.InlineKeyboardMarkup()
        # Кнопка возврата в меню
        menu_button = types.InlineKeyboardButton(
            text="🔙 Назад в меню", 
            callback_data="main_menu"
        )
        keyboard.add(menu_button)
        chat_id=message.chat.id
        user_data = self.get_telegram_user(chat_id)
        twitch_username = user_data[2]
        
        fish_data = self.get_fish_data(message)
        if not fish_data:
            logger.warning("No fish data available for chat_id=%s", chat_id)
            try:
                sent_message = self.bot.send_message(message.chat.id, "❌ Больше нет доступной рыбы для ловли.", reply_markup=keyboard)
                self.user_messages[chat_id] = sent_message.message_id
                logger.info("Sent no fish available message to chat_id=%s", chat_id)
            except Exception as e:
                logger.error("Failed to send no fish available message to chat_id=%s: %s", chat_id, str(e))
                pass
            return
        # Добавляем рыбу в инвентарь
        # fish_data contains: id, name, type, base_price, rarity, is_unique, is_caught, description
        fish_id = fish_data[0]
        fish_name = fish_data[1] 
        fish_type = fish_data[2]
        fish_price = fish_data[3]
        fish_rarity = fish_data[4]
        is_unique = fish_data[5]
        is_caught = fish_data[6] 
        logger.info("User %s caught fish: %s (rarity: %s, price: %s)", twitch_username, fish_name, fish_rarity, fish_price)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Добавляем рыбу в инвентарь пользователя
            cursor.execute('''
                INSERT INTO inventory 
                (username, item_type, item_id, item_name, rarity, value, obtained_at)
                VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
            ''', (twitch_username, 'fish', fish_id, fish_name, fish_rarity, fish_price))
            
            conn.commit()
            if is_caught==1:
                self.mark_fish_as_caught(fish_id)
            catch_message = f"🎉 Вы поймали рыбу: <b>{fish_name}</b> ({self.RARITY_NAMES_RU.get(fish_rarity, fish_rarity)})!\n"
            catch_message += f"💰 Стоимость: {fish_price} LC\n"
            
            try:
                sent_message = self.bot.send_message(message.chat.id, catch_message, parse_mode='HTML', reply_markup=keyboard)
                self.user_messages[chat_id] = sent_message.message_id
                logger.info("Sent catch success message to chat_id=%s", chat_id)
            except Exception as e:
                logger.error("Failed to send catch success message to chat_id=%s: %s", chat_id, str(e))
                pass
        except Exception as e:
            # Обработка ошибок базы данных
            logger.error("Database error while catching fish for chat_id=%s: %s", chat_id, str(e))
            try:
                sent_message = self.bot.send_message(message.chat.id, "❌ Произошла ошибка при добавлении рыбы в инвентарь.", reply_markup=keyboard)
                self.user_messages[chat_id] = sent_message.message_id
                logger.info("Sent database error message to chat_id=%s", chat_id)
            except Exception as e:
                logger.error("Failed to send database error message to chat_id=%s: %s", chat_id, str(e))
        finally:
            conn.close()
        
        
        
        
    def show_fish_page(self, chat_id, inventory, page):
        """Отображение страницы с рыбой"""
        # Получаем имя пользователя и баланс
        user_data = self.get_telegram_user(chat_id)
        twitch_username = user_data[2] if user_data and len(user_data) > 2 else None  # 3rd column is twitch_username
        balance = self.get_user_balance(twitch_username) if twitch_username else 0
        
        ITEMS_PER_PAGE = 5
        total_items = len(inventory)
        total_pages = (total_items + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
        
        if page < 0:
            page = 0
        elif page >= total_pages:
            page = total_pages - 1
        
        start_index = page * ITEMS_PER_PAGE
        end_index = min(start_index + ITEMS_PER_PAGE, total_items)
        page_items = inventory[start_index:end_index]
        
        # Сохраняем состояние пользователя
        self.user_states[chat_id] = {
            'inventory': inventory,
            'current_page': page
        }
        
        # Формируем сообщение
        message_text = f"🐟 <b>Ваша рыба</b> (Страница {page + 1}/{total_pages})\n"
        message_text += f"💳 <b>Баланс:</b> {balance} LC\n\n"
        
        keyboard = types.InlineKeyboardMarkup()
        
        for i, item in enumerate(page_items):
            fish_id = item[0]  # ID записи
            fish_name = item[4]  # Название рыбы
            fish_rarity = item[5]  # Редкость
            fish_value = item[6]  # Значение
            
            # Добавляем рыбу в сообщение
            message_text += f"{i + 1+5*page}. <b>{fish_name}</b> ({fish_rarity}) - {fish_value} LC\n"
            
            # Добавляем кнопку для каждой рыбы
            button = types.InlineKeyboardButton(
                text=f"ℹ️ {fish_name}", 
                callback_data=f"fish_info:{fish_id}"
            )
            keyboard.add(button)
        
        # Кнопки навигации
        nav_buttons = []
        if page > 0:
            nav_buttons.append(types.InlineKeyboardButton(
                text="⬅️ Назад", 
                callback_data=f"fish_page:{page - 1}"
            ))
        
        if page < total_pages - 1:
            nav_buttons.append(types.InlineKeyboardButton(
                text="Вперёд ➡️", 
                callback_data=f"fish_page:{page + 1}"
            ))
        
        if nav_buttons:
            keyboard.row(*nav_buttons)
        
        # Кнопка возврата в меню
        menu_button = types.InlineKeyboardButton(
            text="🔙 Назад в меню", 
            callback_data="main_menu"
        )
        keyboard.add(menu_button)
        
        # Редактируем сообщение или отправляем новое
        try:
            if chat_id in self.user_messages:
                # Пытаемся редактировать существующее сообщение
                try:
                    edited_message = self.bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=self.user_messages[chat_id],
                        text=message_text,
                        reply_markup=keyboard,
                        parse_mode='HTML'
                    )
                except telebot.apihelper.ApiException:
                    # Если не удалось редактировать, отправляем новое сообщение
                    sent_message = self.bot.send_message(
                        chat_id, 
                        message_text, 
                        reply_markup=keyboard, 
                        parse_mode='HTML'
                    )
                    # Сохраняем ID нового сообщения
                    self.user_messages[chat_id] = sent_message.message_id
            else:
                # Отправляем новое сообщение и сохраняем его ID
                sent_message = self.bot.send_message(
                    chat_id, 
                    message_text, 
                    reply_markup=keyboard, 
                    parse_mode='HTML'
                )
                self.user_messages[chat_id] = sent_message.message_id
        except Exception as e:
            # Если возникла любая ошибка, отправляем обычным текстом
            sent_message = self.bot.send_message(
                chat_id, 
                message_text,
                parse_mode='HTML'
            )
            self.user_messages[chat_id] = sent_message.message_id
    
    def show_fish_details(self, chat_id, fish_id):
        """Отображение подробной информации о рыбе"""
        fish = self.get_fish_by_id(fish_id)
        
        if not fish:
            try:
                if chat_id in self.user_messages:
                    self.bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=self.user_messages[chat_id],
                        text="Рыба не найдена."
                    )
                else:
                    sent_message = self.bot.send_message(chat_id, "Рыба не найдена.")
                    self.user_messages[chat_id] = sent_message.message_id
            except:
                sent_message = self.bot.send_message(chat_id, "Рыба не найдена.")
                self.user_messages[chat_id] = sent_message.message_id
            return
        
        # Формируем подробное сообщение
        message_text = f"🐟 <b>{fish[4]}</b>\n\n"  # Название рыбы
        message_text += f"<b>Редкость:</b> {fish[5]}\n"  # Редкость
        message_text += f"<b>Стоимость:</b> {fish[6]} LC\n"  # Стоимость
        message_text += f"<b>Дата поимки:</b> {fish[7]}\n"  # Дата поимки
        
        # Создаем клавиатуру с действиями
        keyboard = types.InlineKeyboardMarkup()
        
        # Кнопка продажи рыбы
        sell_button = types.InlineKeyboardButton(
            text="💰 Продать рыбу", 
            callback_data=f"fish_sell:{fish_id}"
        )
        
        keyboard.add(sell_button)
        
        # Кнопка возврата к списку
        back_button = types.InlineKeyboardButton(
            text="🔙 Назад к списку", 
            callback_data="fish_list"
        )
        keyboard.add(back_button)
        
        # Кнопка возврата в меню
        menu_button = types.InlineKeyboardButton(
            text="🏠 В меню", 
            callback_data="main_menu"
        )
        keyboard.add(menu_button)
        
        # Редактируем сообщение или отправляем новое
        try:
            if chat_id in self.user_messages:
                # Пытаемся редактировать существующее сообщение
                try:
                    edited_message = self.bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=self.user_messages[chat_id],
                        text=message_text,
                        reply_markup=keyboard,
                        parse_mode='HTML'
                    )
                except telebot.apihelper.ApiException:
                    # Если не удалось редактировать, отправляем новое сообщение
                    sent_message = self.bot.send_message(
                        chat_id, 
                        message_text, 
                        reply_markup=keyboard, 
                        parse_mode='HTML'
                    )
                    # Сохраняем ID нового сообщения
                    self.user_messages[chat_id] = sent_message.message_id
            else:
                # Отправляем новое сообщение и сохраняем его ID
                sent_message = self.bot.send_message(
                    chat_id, 
                    message_text, 
                    reply_markup=keyboard, 
                    parse_mode='HTML'
                )
                self.user_messages[chat_id] = sent_message.message_id
        except Exception as e:
            # Если возникла любая ошибка, отправляем обычным текстом
            sent_message = self.bot.send_message(
                chat_id, 
                message_text,
                parse_mode='HTML'
            )
            self.user_messages[chat_id] = sent_message.message_id
    
    def sell_fish_confirm(self, chat_id, fish_id):
        """Подтверждение продажи рыбы"""
        fish = self.get_fish_by_id(fish_id)
        
        if not fish:
            try:
                if chat_id in self.user_messages:
                    self.bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=self.user_messages[chat_id],
                        text="Рыба не найдена."
                    )
                else:
                    sent_message = self.bot.send_message(chat_id, "Рыба не найдена.")
                    self.user_messages[chat_id] = sent_message.message_id
            except:
                sent_message = self.bot.send_message(chat_id, "Рыба не найдена.")
                self.user_messages[chat_id] = sent_message.message_id
            return
        
        message_text = f"Вы уверены, что хотите продать рыбу <b>{fish[4]}</b> за {fish[6]} LC?"
        
        # Создаем клавиатуру с подтверждением
        keyboard = types.InlineKeyboardMarkup()
        
        # Кнопки подтверждения и отмены
        confirm_button = types.InlineKeyboardButton(
            text="✅ Да, продать", 
            callback_data=f"fish_sell_confirm:{fish_id}"
        )
        cancel_button = types.InlineKeyboardButton(
            text="❌ Отмена", 
            callback_data="fish_list"
        )
        menu_button = types.InlineKeyboardButton(
            text="🏠 В меню", 
            callback_data="main_menu"
        )
        
        keyboard.add(confirm_button, cancel_button)
        keyboard.add(menu_button)
        
        # Редактируем сообщение или отправляем новое
        try:
            if chat_id in self.user_messages:
                # Пытаемся редактировать существующее сообщение
                try:
                    edited_message = self.bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=self.user_messages[chat_id],
                        text=message_text,
                        reply_markup=keyboard,
                        parse_mode='HTML'
                    )
                except telebot.apihelper.ApiException:
                    # Если не удалось редактировать, отправляем новое сообщение
                    sent_message = self.bot.send_message(
                        chat_id, 
                        message_text, 
                        reply_markup=keyboard, 
                        parse_mode='HTML'
                    )
                    # Сохраняем ID нового сообщения
                    self.user_messages[chat_id] = sent_message.message_id
            else:
                # Отправляем новое сообщение и сохраняем его ID
                sent_message = self.bot.send_message(
                    chat_id, 
                    message_text, 
                    reply_markup=keyboard, 
                    parse_mode='HTML'
                )
                self.user_messages[chat_id] = sent_message.message_id
        except Exception as e:
            # Если возникла любая ошибка, отправляем обычным текстом
            sent_message = self.bot.send_message(
                chat_id, 
                message_text,
                parse_mode='HTML'
            )
            self.user_messages[chat_id] = sent_message.message_id
    
    def show_missing_fish_by_rarity(self, chat_id, rarity):
        """Показать список рыб определенной редкости, которых не хватает пользователю"""
        # Проверяем, привязан ли пользователь
        user_data = self.get_telegram_user(chat_id)
        
        if not user_data or not user_data[2]:  # Не привязан
            message_text = "Ваш аккаунт не привязан. Используйте команду /link для привязки."
            
            # Добавляем кнопку возврата в меню
            keyboard = types.InlineKeyboardMarkup()
            back_button = types.InlineKeyboardButton(
                text="🔙 Назад в меню", 
                callback_data="main_menu"
            )
            keyboard.add(back_button)
            
            try:
                if chat_id in self.user_messages:
                    try:
                        self.bot.edit_message_text(
                            chat_id=chat_id,
                            message_id=self.user_messages[chat_id],
                            text=message_text,
                            reply_markup=keyboard
                        )
                    except telebot.apihelper.ApiException:
                        sent_message = self.bot.send_message(chat_id, message_text, reply_markup=keyboard)
                        self.user_messages[chat_id] = sent_message.message_id
                else:
                    sent_message = self.bot.send_message(chat_id, message_text, reply_markup=keyboard)
                    self.user_messages[chat_id] = sent_message.message_id
            except:
                pass
            return
        
        twitch_username = user_data[2]
        
        # Получаем все рыбы этой редкости
        all_rarity_fish = self.get_all_fish_names_by_rarity(rarity)
        
        # Получаем уникальные рыбы этой редкости у пользователя
        user_rarity_fish = self.get_user_unique_fish_by_rarity(twitch_username, rarity)
        
        # Определяем недостающие рыбы
        missing_fish = set(all_rarity_fish) - set(user_rarity_fish)
        
        # Формируем сообщение
        rarity_name = self.RARITY_NAMES_RU.get(rarity, rarity)
        message_text = f"📋 <b>Недостающие рыбы редкости {rarity_name}</b>\n\n"
        
        if missing_fish:
            message_text += "Вам не хватает следующих рыб:\n\n"
            for fish_name in sorted(missing_fish):
                message_text += f"• {fish_name}\n"
        else:
            message_text += "🎉 Поздравляем! У вас есть все рыбы этой редкости.\n"
        
        # Создаем клавиатуру
        keyboard = types.InlineKeyboardMarkup()
        
        # Кнопка возврата к коллекции
        back_button = types.InlineKeyboardButton(
            text="🔙 Назад к коллекции", 
            callback_data="view_my_collection"
        )
        keyboard.add(back_button)
        
        # Кнопка возврата в меню
        menu_button = types.InlineKeyboardButton(
            text="🏠 В меню", 
            callback_data="main_menu"
        )
        keyboard.add(menu_button)
        
        # Редактируем сообщение или отправляем новое
        try:
            if chat_id in self.user_messages:
                # Пытаемся редактировать существующее сообщение
                try:
                    edited_message = self.bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=self.user_messages[chat_id],
                        text=message_text,
                        reply_markup=keyboard,
                        parse_mode='HTML'
                    )
                except telebot.apihelper.ApiException:
                    # Если не удалось редактировать, отправляем новое сообщение
                    sent_message = self.bot.send_message(
                        chat_id, 
                        message_text, 
                        reply_markup=keyboard, 
                        parse_mode='HTML'
                    )
                    # Сохраняем ID нового сообщения
                    self.user_messages[chat_id] = sent_message.message_id
            else:
                # Отправляем новое сообщение и сохраняем его ID
                sent_message = self.bot.send_message(
                    chat_id, 
                    message_text, 
                    reply_markup=keyboard, 
                    parse_mode='HTML'
                )
                self.user_messages[chat_id] = sent_message.message_id
        except Exception as e:
            # Если возникла любая ошибка, отправляем обычным текстом
            sent_message = self.bot.send_message(
                chat_id, 
                message_text,
                parse_mode='HTML'
            )
            self.user_messages[chat_id] = sent_message.message_id

    def buy_fish_command(self, message):
        """Обработка команды покупки рыбы"""
        chat_id = message.chat.id
        
        # Проверяем, привязан ли пользователь
        user_data = self.get_telegram_user(chat_id)
        
        if not user_data or not user_data[2]:  # Не привязан
            message_text = "Ваш аккаунт не привязан. Используйте команду /link для привязки."
            
            # Добавляем кнопку возврата в меню
            keyboard = types.InlineKeyboardMarkup()
            back_button = types.InlineKeyboardButton(
                text="🔙 Назад в меню", 
                callback_data="main_menu"
            )
            keyboard.add(back_button)
            
            try:
                sent_message = self.bot.send_message(message.chat.id, message_text, reply_markup=keyboard)
                self.user_messages[chat_id] = sent_message.message_id
            except:
                pass
            return
        
        # Получаем все рыбы из базы данных
        all_fish = self.get_all_fish_with_caught_info()
        
        if not all_fish:
            message_text = "❌ В базе данных нет рыб для покупки."
            
            # Добавляем кнопку возврата в меню
            keyboard = types.InlineKeyboardMarkup()
            back_button = types.InlineKeyboardButton(
                text="🔙 Назад в меню", 
                callback_data="main_menu"
            )
            keyboard.add(back_button)
            
            try:
                sent_message = self.bot.send_message(message.chat.id, message_text, reply_markup=keyboard)
                self.user_messages[chat_id] = sent_message.message_id
            except:
                pass
            return
        
        # Отображаем первую страницу с рыбами
        self.show_buy_fish_page(chat_id, all_fish, 0)

    def handle_callback_query_part_1(self, call):
        """Обработка первой части callback query"""
        chat_id = call.message.chat.id
        data = call.data
        message_id = call.message.message_id
        logger.info("Handling callback query part 1 from chat_id=%s with data=%s", chat_id, data)
        
        # Сохраняем ID сообщения
        self.user_messages[chat_id] = message_id
        
        try:
            # Отвечаем на запрос, чтобы убрать "часики"
            self.bot.answer_callback_query(call.id)
        except:
            pass
            
        if data == "main_menu":
            # Возвращаемся в главное меню
            logger.info("User %s navigated to main menu", chat_id)
            self.start_command(call.message)
            return
            
        elif data == "link_account":
            # Переход к привязке аккаунта
            logger.info("User %s navigated to link account", chat_id)
            self.link_command(call.message)
            return
            
        elif data == "view_fish":
            # Просмотр рыбы
            logger.info("User %s navigated to view fish", chat_id)
            self.fish_command(call.message)
            return
            
        elif data == "catch_fish":
            # Ловля рыбы
            logger.info("User %s initiated fish catch", chat_id)
            self.fish_telegram(call.message)
            return
            
        elif data == "view_duplicates":
            # Просмотр дубликатов
            logger.info("User %s navigated to view duplicates", chat_id)
            self.duplicates_command(call.message)
            return
            
        elif data == "view_balance":
            # Просмотр баланса
            logger.info("User %s navigated to view balance", chat_id)
            self.balance_command(call.message)
            return
            
        elif data == "sell_pass":
            # Продажа пропуска
            logger.info("User %s initiated pass sale", chat_id)
            self.sell_pass(chat_id)
            return
            
        elif data == "view_info":
            # Просмотр информации о боте
            logger.info("User %s navigated to view info", chat_id)
            self.info_command(call.message)
            return
            
        elif data == "view_help":
            # Просмотр помощи
            logger.info("User %s navigated to view help", chat_id)
            self.help_command(call.message)
            return
            
        elif data == "contact_lonely":
            # Связь с Лонли
            logger.info("User %s navigated to contact lonely", chat_id)
            self.contact_lonely(call.message)
            return
        
        elif data == "support_lonely":
            # Донат Лонли
            logger.info("User %s navigated to support lonely", chat_id)
            self.support_lonely(call.message)
            return

        elif data == "view_settings":
            # Просмотр настроек
            logger.info("User %s navigated to settings", chat_id)
            self.show_settings_menu(chat_id)
            return
            
        elif data == "toggle_fishing_notifications":
            # Переключение уведомлений о рыбалке
            logger.info("User %s toggling fishing notifications", chat_id)
            self.toggle_fishing_notifications(chat_id, call.id)
            return
            
        elif data == "toggle_fishing_sound":
            # Переключение звука уведомлений
            logger.info("User %s toggling fishing sound", chat_id)
            self.toggle_fishing_sound(chat_id, call.id)
            return
            
        elif data == "relink_account":
            # Перепривязка аккаунта
            logger.info("User %s requesting account relink", chat_id)
            self.link_command(call.message)
            return

        elif data == "view_all_fish":
            # Просмотр всех рыб
            logger.info("User %s navigated to view all fish", chat_id)
            self.all_fish_command(call.message)
            return

        elif data == "view_my_collection":
            # Просмотр коллекции пользователя
            logger.info("User %s navigated to view my collection", chat_id)
            self.my_collection_command(call.message)
            return
            
        elif data == "buy_fish":
            # Покупка рыб
            logger.info("User %s navigated to buy fish", chat_id)
            self.buy_fish_command(call.message)
            return
        elif data == "view_mini_collections":
            # Просмотр мини-коллекций
            logger.info("User %s navigated to view mini collections", chat_id)
            self.show_mini_collections(chat_id)
            return
            
        elif data == "private_messages":
            # Переход к приватным сообщениям
            logger.info("User %s navigated to private messages", chat_id)
            self.private_messaging.show_chat_menu(chat_id)
            return
        elif data == "trademenu":
            # Переход к приватным сообщениям
            logger.info("User %s navigated to trademenu", chat_id)
            self.show_trade_menu(chat_id)
            return
        elif data == "pastemenu":
            # Переход к приватным сообщениям
            logger.info("User %s navigated to pastemenu", chat_id)
            self.pastes_menu(chat_id)
            return
        elif data == "aprovemenu":
            # Переход к приватным сообщениям
            logger.info("User %s navigated to aprovemenu", chat_id)
            self.aprove_menu(chat_id)
            return
        elif data.startswith("manage_pastes_page:"):
            # Handle pagination for manage pastes menu
            try:
                page = int(data.split(":")[1])
                self.show_manage_pastes_menu(call)  # This will now handle pagination
            except (ValueError, IndexError):
                self.bot.answer_callback_query(call.id, "Ошибка навигации по страницам")
        elif data.startswith("pastes_page:"):
            # Handle pagination for user paste view
            try:
                page = int(data.split(":")[1])
                self.show_pastes(call.message.chat.id, page)
            except (ValueError, IndexError):
                self.bot.answer_callback_query(call.id, "Ошибка навигации по страницам")
        elif data.startswith("aprove_suggestion:"):
            id=data.split(":")[1]
            if approve_suggestion(int(id)):
                self.bot.answer_callback_query(call.id, "Паста одобрена")
            else:
                self.bot.answer_callback_query(call.id, "Ошибка при одобрении пасты")
        elif data == "suggest_paste":
            self.suggest_paste(call.message.chat.id)
        elif data == "mod_suggestions":
            self.show_paste_suggestions(call)
        elif data.startswith("aprove_suggestion:"):
            id=data.split(":")[1]
            if approve_suggestion(int(id)):
                self.bot.answer_callback_query(call.id, "Паста одобрена")
            else:
                self.bot.answer_callback_query(call.id, "Ошибка при одобрении пасты")
            
        elif data.startswith("delete_paste_"):
            paste_id = data.split("_")[2]
            if delete_paste(int(paste_id)):
                self.bot.answer_callback_query(call.id, "Паста удалена")
                # Refresh the manage pastes menu
                self.show_manage_pastes_menu(call)
            else:
                self.bot.answer_callback_query(call.id, "Ошибка при удалении пасты")
                
        elif data.startswith("show_paste:"):
            num = data.split(":")[1]
            paste = get_paste_by_num(int(num))
            if paste is not None:
                response = f"{paste['name']}:\n{paste['text']}"
                self.bot.answer_callback_query(call.id, response)
            else:
                self.bot.answer_callback_query(call.id, "Паста не найдена")
        
        elif data.startswith("view_suggestion_"):
            suggestion_id = int(data.split("_")[2])
            # Show details of a specific suggestion
            suggestions = get_all_suggestions()
            suggestion = next((s for s in suggestions if s['id'] == suggestion_id), None)
            
            if suggestion:
                response = f"Предложенная паста:\n\n"
                response += f"Название: {suggestion['name']}\n"
                response += f"Текст: {suggestion['text']}\n"
                response += f"Предложил: {suggestion['username']}\n"
                response += f"Дата: {suggestion['suggested_at']}"
                
                markup = types.InlineKeyboardMarkup()
                markup.add(
                    types.InlineKeyboardButton("Одобрить", callback_data=f"approve_suggestion_{suggestion_id}"),
                    types.InlineKeyboardButton("Отклонить", callback_data=f"reject_suggestion_{suggestion_id}")
                )
                markup.add(types.InlineKeyboardButton("Назад", callback_data="mod_suggestions"))
                
                self.bot.edit_message_text(
                    response,
                    call.message.chat.id,
                    call.message.message_id,
                    reply_markup=markup
                )
            else:
                self.bot.answer_callback_query(call.id, "Предложение не найдено")
                
        elif data.startswith("approve_suggestion_"):
            suggestion_id = int(data.split("_")[2])
            if approve_suggestion(suggestion_id):
                self.bot.answer_callback_query(call.id, "Паста одобрена")
                # Refresh suggestions view
                self.show_paste_suggestions(call)
            else:
                self.bot.answer_callback_query(call.id, "Ошибка при одобрении пасты")
                
        elif data.startswith("reject_suggestion_"):
            suggestion_id = int(data.split("_")[2])
            if reject_suggestion(suggestion_id):
                self.bot.answer_callback_query(call.id, "Паста отклонена")
                # Refresh suggestions view
                self.show_paste_suggestions(call)
            else:
                self.bot.answer_callback_query(call.id, "Ошибка при отклонении пасты")
                
        elif data.startswith("view_paste_"):
            paste_id = int(data.split("_")[2])
            paste = get_paste_by_id(paste_id)
            if paste:
                response = f"{paste['name']}:\n{paste['text']}"
                
                markup = types.InlineKeyboardMarkup()
                markup.add(types.InlineKeyboardButton("Назад", callback_data="manage_pastes_page:0"))
                
                self.bot.edit_message_text(
                    response,
                    call.message.chat.id,
                    call.message.message_id,
                    reply_markup=markup
                )
            else:
                self.bot.answer_callback_query(call.id, "Паста не найдена")
        elif data.startswith("upgrademenu"):
            twitch_username=self.get_twitch_username(chat_id)
            self.upgrade_handler.show_upgrades_menu(chat_id, twitch_username)
        
    def handle_callback_query_part_2(self, call):
        chat_id = call.message.chat.id
        data = call.data
        message_id = call.message.message_id
        logger.info("Handling callback query from chat_id=%s with data=%s", chat_id, data)
        # Сохраняем ID сообщения
        self.user_messages[chat_id] = message_id
        try:
            # Отвечаем на запрос, чтобы убрать "часики"
            self.bot.answer_callback_query(call.id)
        except:
            pass
            
        # Handle private messaging callbacks
        if data.startswith("pm_select_user:"):
            # User selected another user to message
            target_chat_id = int(data.split(":")[1])
            logger.info("User %s selected user %s for private messaging", chat_id, target_chat_id)
            
            # Initiate silent private chat
            self.private_messaging.initiate_private_chat_silent(chat_id, target_chat_id)
            
            # Delete the user selection message
            try:
                self.bot.delete_message(chat_id, message_id)
            except:
                pass
                
            return
            
        elif data.startswith("pm_user_page:"):
            # Navigate to another page of users
            page = int(data.split(":")[1])
            logger.info("User %s navigating to user page %s", chat_id, page)
            
            # Delete the current message and show the new page
            try:
                self.bot.delete_message(chat_id, message_id)
            except:
                pass
                
            self.private_messaging.show_user_selection_ui(chat_id, page)
            return
            
        elif data == "pm_cancel":
            # Cancel private message selection
            logger.info("User %s cancelled private message selection", chat_id)
            
            try:
                self.bot.delete_message(chat_id, message_id)
                self.bot.send_message(chat_id, "❌ Выбор пользователя отменён.")
            except:
                pass
                
            return
            
        elif data == "pm_new_message":
            # Start new message
            logger.info("User %s starting new message", chat_id)
            self.private_messaging.show_user_selection_ui(chat_id)
            return
            
        elif data == "pm_reply_to_last":
            # Reply to last sender
            logger.info("User %s replying to last sender", chat_id)
            
            # Ask for message content
            self.bot.send_message(chat_id, "Введите сообщение для отправки последнему собеседнику:")
            # Set state to waiting for reply
            self.user_states[chat_id] = {"state": "waiting_for_reply_to_last"}
            return
            
        elif data == "pm_end_chat":
            # End current chat
            logger.info("User %s ending chat", chat_id)
            self.private_messaging.end_private_chat(chat_id)
            return
            
        if data.startswith("trade_"):
            self.handle_trade_callback(chat_id, data)
            return
        elif data.startswith("view_mini_collection:"):
            # Просмотр конкретной мини-коллекции
            collection_id = int(data.split(":")[1])
            logger.info("User %s viewing mini collection %s", chat_id, collection_id)
            self.show_mini_collection_details(chat_id, collection_id)
            return
        elif data.startswith("buy_fish_item:"):
            # Покупка конкретной рыбы (показ подтверждения)
            fish_id = int(data.split(":")[1])
            logger.info("User %s attempting to buy fish_id=%s", chat_id, fish_id)
            self.buy_fish_item(chat_id, fish_id)
            return
        elif data.startswith("confirm_buy_fish:"):
            # Подтверждение покупки рыбы
            fish_id = int(data.split(":")[1])
            logger.info("User %s confirmed purchase of fish_id=%s", chat_id, fish_id)
            self.confirm_buy_fish(chat_id, fish_id)
            return
        elif data.startswith("buy_fish_page:"):
            # Переход на другую страницу покупки рыб
            page = int(data.split(":")[1])
            logger.info("User %s navigating to buy fish page %s", chat_id, page)
            
            # Получаем состояние пользователя
            user_state = self.user_states.get(chat_id)
            if user_state and 'buy_fish' in user_state:
                all_fish = user_state['buy_fish']
                self.show_buy_fish_page(chat_id, all_fish, page)
            return
        elif data.startswith("buy_item:"):
            # Покупка товара
            item_id = int(data.split(":")[1])
            logger.info("User %s attempting to buy item_id=%s", chat_id, item_id)
            self.buy_item(chat_id, item_id)
            return
        elif data.startswith("confirm_relink:"):
            self.confirm_relink(data, chat_id, message_id)      
        if data.startswith("fish_page:"):
            page = int(data.split(":")[1])
            logger.info("User %s navigating to fish page %s", chat_id, page)
            user_state = self.user_states.get(chat_id)
            if user_state and 'inventory' in user_state:
                inventory = user_state['inventory']
                self.show_fish_page(chat_id, inventory, page)        
        elif data.startswith("fish_info:"):
            # Просмотр информации о рыбе
            fish_id = int(data.split(":")[1])
            logger.info("User %s viewing fish info for fish_id=%s", chat_id, fish_id)
            self.show_fish_details(chat_id, fish_id)       
        elif data.startswith("fish_sell:"):
            # Подтверждение продажи рыбы
            fish_id = int(data.split(":")[1])
            logger.info("User %s confirming fish sale for fish_id=%s", chat_id, fish_id)
            self.sell_fish_confirm(chat_id, fish_id)        
        elif data.startswith("fish_sell_confirm:"):
            self.fish_sell_confirm(data, chat_id, message_id)
            
        elif data.startswith("fish_list"):
            # Возврат к списку рыб
            logger.info("User %s returning to fish list", chat_id)
            self.send_fish_list(chat_id)

            
        elif data.startswith("missing_fish:"):
            # Просмотр недостающих рыб определенной редкости
            rarity = data.split(":")[1]
            logger.info("User %s viewing missing fish for rarity %s", chat_id, rarity)
            self.show_missing_fish_by_rarity(chat_id, rarity)
            return
        elif data.startswith("duplicates_page:"):
            # Переход на другую страницу дубликатов
            page = int(data.split(":")[1])
            logger.info("User %s navigating to duplicates page %s", chat_id, page)
            
            # Получаем состояние пользователя
            user_state = self.user_states.get(chat_id)
            if user_state and user_state.get('state') == 'duplicates' and 'duplicates' in user_state:
                duplicates = user_state['duplicates']
                self.show_duplicates_page(chat_id, duplicates, page)
            return
        elif data.startswith("duplicates:"):
            # Просмотр дубликатов
            page = int(data.split(":")[1])
            logger.info("User %s viewing duplicates page %s", chat_id, page)
            user_state = self.user_states.get(chat_id)
            if user_state and 'duplicates' in user_state:
                duplicates = user_state['duplicates']
                self.show_duplicates_page(chat_id, duplicates, page)
            return
            return
        elif data.startswith("select_fish_duplicates:"):
            # Выбор конкретной рыбы для просмотра дубликатов
            fish_index = int(data.split(":")[1])
            logger.info("User %s selecting fish duplicates for index %s", chat_id, fish_index)
            self.show_fish_duplicates_details(chat_id, fish_index, data)
            return      
        elif data.startswith("all_fish_page:"):
            # Переход на другую страницу списка всех рыб
            page = int(data.split(":")[1])
            logger.info("User %s navigating to all fish page %s", chat_id, page)
            
            # Получаем состояние пользователя
            user_state = self.user_states.get(chat_id)
            if user_state and 'all_fish' in user_state:
                all_fish = user_state['all_fish']
                self.show_all_fish_page(chat_id, all_fish, page)
            return
        elif data.startswith("sell_fish_duplicates:"):
            # Продажа дубликатов конкретной рыбы
            self.sell_fish_duplicates(data, chat_id, message_id)
        elif data == "upgrades":
            # Show upgrades menu
            user_data = self.get_telegram_user(chat_id)
            if user_data and user_data[2]:
                self.upgrade_handler.show_upgrades_menu(chat_id, user_data[2])
            else:
                self.bot.send_message(chat_id, "❌ Ваш аккаунт не привязан.")
            return
            
        elif data == "buy_upgrade_points":
            # Show buy upgrade points menu
            user_data = self.get_telegram_user(chat_id)
            if user_data and user_data[2]:
                self.upgrade_handler.buy_upgrade_points_menu(chat_id, user_data[2])
            else:
                self.bot.send_message(chat_id, "❌ Ваш аккаунт не привязан.")
            return
            
        elif data.startswith("upgrade_detail:"):
            # Show upgrade detail
            upgrade_type = data.split(":")[1]
            user_data = self.get_telegram_user(chat_id)
            if user_data and user_data[2]:
                self.upgrade_handler.show_upgrade_detail(chat_id, user_data[2], upgrade_type)
            else:
                self.bot.send_message(chat_id, "❌ Ваш аккаунт не привязан.")
            return
            
        elif data.startswith("purchase_points:"):
            # Purchase upgrade points
            parts = data.split(":")
            points_amount = int(parts[1])
            lc_cost = int(parts[2])
            user_data = self.get_telegram_user(chat_id)
            if user_data and user_data[2]:
                self.upgrade_handler.purchase_upgrade_points(chat_id, user_data[2], points_amount, lc_cost)
            else:
                self.bot.send_message(chat_id, "❌ Ваш аккаунт не привязан.")
            return
            
        elif data.startswith("upgrade_skill:"):
            # Upgrade a specific skill
            upgrade_type = data.split(":")[1]
            user_data = self.get_telegram_user(chat_id)
            if user_data and user_data[2]:
                self.upgrade_handler.upgrade_skill(chat_id, user_data[2], upgrade_type)
            else:
                self.bot.send_message(chat_id, "❌ Ваш аккаунт не привязан.")
            return
            
            
    def get_twitch_username(self, chat_id):
        user_data = self.get_telegram_user(chat_id)
        if user_data and user_data[2]:
            twitch_username = user_data[2]
            return twitch_username
        return None
    def handle_callback_query(self, call):
        """Обработка нажатий на кнопки"""
        # Try to handle with feedback_support module first
        if self.feedback_support.handle_callback_query(call):
            return
            
        # Try to handle with help_info module next
        if self.help_info.handle_callback_query(call):
            return
        
        # Handle other callbacks with existing logic
        self.handle_callback_query_part_1(call)
        self.handle_callback_query_part_2(call)
    def fish_sell_confirm(self, data, chat_id, message_id):
        fish_id = int(data.split(":")[1])
        logger.info("User %s selling fish_id=%s", chat_id, fish_id)
        success, message = self.sell_fish(fish_id)
        # Отправляем результат как новое сообщение
        try:
            if chat_id in self.user_messages:
                try:
                    self.bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=self.user_messages[chat_id],
                        text=message,
                        parse_mode='HTML'
                    )
                    logger.info("Edited message with fish sale result for chat_id=%s", chat_id)
                except telebot.apihelper.ApiException:
                    sent_message = self.bot.send_message(chat_id, message, parse_mode='HTML')
                    self.user_messages[chat_id] = sent_message.message_id
                    logger.info("Sent fish sale result as new message to chat_id=%s", chat_id)
            else:
                sent_message = self.bot.send_message(chat_id, message, parse_mode='HTML')
                self.user_messages[chat_id] = sent_message.message_id
                logger.info("Sent fish sale result as new message to chat_id=%s", chat_id)
        except Exception as e:
            logger.error("Failed to send fish sale result to chat_id=%s: %s", chat_id, str(e))
            sent_message = self.bot.send_message(chat_id, message, parse_mode='HTML')
            self.user_messages[chat_id] = sent_message.message_id
        
        # Возвращаемся к списку
        logger.info("User %s returning to fish list after sale", chat_id)
        self.send_fish_list(chat_id)        
    def confirm_relink(self, data, chat_id, message_id):
        confirm = data.split(":")[1]
        logger.info("User %s confirmed relink with option=%s", chat_id, confirm)
        if confirm == "yes":
            # Генерация кода привязки
            link_code = self.generate_link_code()
            
            # Сохранение пользователя с кодом привязки
            self.save_telegram_user(chat_id, link_code)
            
            # Сохранение в ожидаемых привязках
            self.pending_links[link_code] = chat_id
            
            link_message = (
                f"Ваш новый код для привязки аккаунта: {link_code}\n"
                "Отправьте этот код в чат Twitch, чтобы подтвердить привязку аккаунта.\n"
                "После этого вы сможете просматривать свою рыбу здесь."
            )
            
            try:
                self.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=link_message
                )
                logger.info("Sent new link code %s to chat_id=%s", link_code, chat_id)
            except telebot.apihelper.ApiException:
                try:
                    sent_message = self.bot.send_message(chat_id, link_message)
                    self.user_messages[chat_id] = sent_message.message_id
                    logger.info("Sent new link code as new message to chat_id=%s", chat_id)
                except Exception as e:
                    logger.error("Failed to send new link code to chat_id=%s: %s", chat_id, str(e))
                    pass
        else:
            # Отмена повторной привязки
            logger.info("User %s cancelled relink", chat_id)
            try:
                self.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text="Привязка аккаунта отменена."
                )
                logger.info("Sent relink cancellation message to chat_id=%s", chat_id)
            except telebot.apihelper.ApiException:
                try:
                    sent_message = self.bot.send_message(chat_id, "Привязка аккаунта отменена.")
                    self.user_messages[chat_id] = sent_message.message_id
                    logger.info("Sent relink cancellation as new message to chat_id=%s", chat_id)
                except Exception as e:
                    logger.error("Failed to send relink cancellation message to chat_id=%s: %s", chat_id, str(e))
                    pass
        
        # Очищаем состояние пользователя
        if chat_id in self.user_states:
            del self.user_states[chat_id]
        return         
    def sell_fish_duplicates(self, data, chat_id, message_id):
        # Получаем состояние пользователя
        fish_index = int(data.split(":")[1])
        logger.info("User %s selling fish duplicates for index %s", chat_id, fish_index)
        user_state = self.user_states.get(chat_id)
        if not user_state or user_state.get('state') != 'duplicates' or 'duplicates' not in user_state:
            logger.warning("User %s attempted to sell duplicates without proper state", chat_id)
            return
        
        duplicates = user_state['duplicates']
        if fish_index >= len(duplicates):
            logger.warning("User %s attempted to sell duplicates with invalid index %s", chat_id, fish_index)
            return
        
        item = duplicates[fish_index]
        fish_name = item[0]  # Название рыбы
        fish_count = item[1]  # Количество
        fish_ids = item[2].split(',')  # Список ID
        fish_values = item[4].split(',')  # Список значений
        
        # Создаем пары (id, value) и сортируем по возрастанию стоимости (дешевый первый)
        fish_pairs = list(zip(fish_ids, fish_values))
        # Преобразуем значения в числа и сортируем по возрастанию стоимости
        fish_pairs = [(int(fish_id), int(fish_value)) for fish_id, fish_value in fish_pairs]
        fish_pairs.sort(key=lambda x: x[1])  # Сортируем по стоимости (по возрастанию)
        # Оставляем один экземпляр (самый дешевый), остальные добавляем в список для удаления
        ids_to_remove = [str(fish_id) for fish_id, _ in fish_pairs[1:]]  # Все кроме первого (самого дешевого)
        values_to_sum = [fish_value for _, fish_value in fish_pairs[1:]]  # Значения всех кроме первого (самого дешевого)
        
        if ids_to_remove:
            deleted_count = self.remove_fish_duplicates(ids_to_remove)
            
            # Считаем общую стоимость дубликатов
            total_value = sum(values_to_sum)
            try:
                fish_modi=self.upgrade_system.get_user_upgrades(twitch_username)
                total_value += int(total_value *fish_modi.get("sale_price_increase")*0.001)
            except :
                pass
            # Обновляем баланс пользователя
            user_data = self.get_telegram_user(chat_id)
            if user_data and user_data[2]:
                twitch_username = user_data[2]
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                try:
                    # Получаем текущий баланс
                    cursor.execute('''
                        SELECT balance FROM players WHERE username = ?
                    ''', (twitch_username,))
                    
                    balance_row = cursor.fetchone()
                    if balance_row:
                        try:
                            current_balance = int(balance_row[0]) if balance_row[0] is not None and balance_row[0] != '' else 0
                        except (ValueError, TypeError):
                            current_balance = 0
                        
                        # Увеличиваем баланс на общую стоимость дубликатов
                        new_balance = current_balance + total_value
                        cursor.execute('''
                            UPDATE players 
                            SET balance = ? 
                            WHERE username = ?
                        ''', (new_balance, twitch_username))
                        
                        conn.commit()
                        logger.info("Updated balance for user %s after selling duplicates: %s -> %s", twitch_username, current_balance, new_balance)
                        
                        message_text = f"✅ Успешно удалено {deleted_count} дубликатов.\n"
                        message_text += f"💰 Вы получили {total_value} LC за продажу дубликатов.\n"
                        message_text += f"💳 Ваш баланс: {new_balance} LC"
                    else:
                        message_text = f"✅ Успешно удалено {deleted_count} дубликатов.\n"
                        message_text += f"💰 Вы получили {total_value} LC за продажу дубликатов."
                    
                    try:
                        self.bot.edit_message_text(
                            chat_id=chat_id,
                            message_id=message_id,
                            text=message_text,
                            parse_mode='HTML'
                        )
                        logger.info("Sent duplicate sale success message to chat_id=%s", chat_id)
                    except telebot.apihelper.ApiException:
                        try:
                            sent_message = self.bot.send_message(chat_id, message_text, parse_mode='HTML')
                            self.user_messages[chat_id] = sent_message.message_id
                            logger.info("Sent duplicate sale success as new message to chat_id=%s", chat_id)
                        except Exception as e:
                            logger.error("Failed to send duplicate sale success message to chat_id=%s: %s", chat_id, str(e))
                            pass
                    
                    # Обновляем список дубликатов
                    updated_duplicates = self.get_duplicate_fish(twitch_username)
                    
                    if updated_duplicates and len(updated_duplicates) > 0:
                        self.user_states[chat_id] = {
                            'state': 'duplicates',
                            'duplicates': updated_duplicates,
                            'current_page': 0
                        }
                        # Возвращаемся к списку дубликатов
                        self.show_duplicates_page(chat_id, updated_duplicates, 0)
                    else:
                        # Если больше нет дубликатов, показываем сообщение
                        final_message = "🎉 Поздравляем! У вас больше нет дубликатов рыбы."
                        try:
                            keyboard = types.InlineKeyboardMarkup()
                            # Кнопка возврата в меню
                            menu_button = types.InlineKeyboardButton(
                                text="🔙 Назад в меню", 
                                callback_data="main_menu"
                            )
                            keyboard.add(menu_button)
                            sent_message = self.bot.send_message(chat_id, final_message, parse_mode='HTML', reply_markup=keyboard)
                            self.user_messages[chat_id] = sent_message.message_id
                            logger.info("Sent no more duplicates message to chat_id=%s", chat_id)
                        except Exception as e:
                            logger.error("Failed to send no more duplicates message to chat_id=%s: %s", chat_id, str(e))
                            pass
                except Exception as e:
                    conn.rollback()
                    logger.error("Database error while selling duplicates for chat_id=%s: %s", chat_id, str(e))
                    message_text = f"❌ Ошибка при продаже дубликатов. Попробуйте ещё раз."
                    try:
                        self.bot.edit_message_text(
                            chat_id=chat_id,
                            message_id=message_id,
                            text=message_text,
                            parse_mode='HTML'
                        )
                        logger.info("Sent duplicate sale error message to chat_id=%s", chat_id)
                    except telebot.apihelper.ApiException:
                        try:
                            sent_message = self.bot.send_message(chat_id, message_text, parse_mode='HTML')
                            self.user_messages[chat_id] = sent_message.message_id
                            logger.info("Sent duplicate sale error as new message to chat_id=%s", chat_id)
                        except Exception as e:
                            logger.error("Failed to send duplicate sale error message to chat_id=%s: %s", chat_id, str(e))
                            pass
                finally:
                    conn.close()
        return
    def send_fish_list(self, chat_id):
        """Отправка списка рыб (обновление)"""
        # Проверяем, привязан ли пользователь
        user_data = self.get_telegram_user(chat_id)
        
        if not user_data or not user_data[2]:  # Не привязан
            message_text = "Ваш аккаунт не привязан. Используйте команду /link для привязки."
            try:
                if chat_id in self.user_messages:
                    try:
                        self.bot.edit_message_text(
                            chat_id=chat_id,
                            message_id=self.user_messages[chat_id],
                            text=message_text
                        )
                    except telebot.apihelper.ApiException:
                        sent_message = self.bot.send_message(chat_id, message_text)
                        self.user_messages[chat_id] = sent_message.message_id
                else:
                    sent_message = self.bot.send_message(chat_id, message_text)
                    self.user_messages[chat_id] = sent_message.message_id
            except:
                sent_message = self.bot.send_message(chat_id, message_text)
                self.user_messages[chat_id] = sent_message.message_id
            return
        
        # Получаем инвентарь пользователя
        inventory = self.get_user_inventory(user_data[2])
        
        if not inventory:
            message_text = "У вас пока нет рыбы."
            try:
                if chat_id in self.user_messages:
                    try:
                        self.bot.edit_message_text(
                            chat_id=chat_id,
                            message_id=self.user_messages[chat_id],
                            text=message_text
                        )
                    except telebot.apihelper.ApiException:
                        sent_message = self.bot.send_message(chat_id, message_text)
                        self.user_messages[chat_id] = sent_message.message_id
                else:
                    sent_message = self.bot.send_message(chat_id, message_text)
                    self.user_messages[chat_id] = sent_message.message_id
            except:
                sent_message = self.bot.send_message(chat_id, message_text)
                self.user_messages[chat_id] = sent_message.message_id
            return
        
        # Отображаем первую страницу
        self.show_fish_page(chat_id, inventory, 0)
    def start_private_chat(self, message):
        """Start a private chat with another user via UI"""
        chat_id = message.chat.id
        
        # Check if user is linked
        twitch_username = self.is_user_linked(chat_id)
        if not twitch_username:
            self.bot.reply_to(message, "❌ Вы должны быть привязаны к Twitch аккаунту для использования этой функции. Используйте /link для привязки.")
            return
            
        # Show user selection UI
        self.private_messaging.show_user_selection_ui(chat_id)
    
    def reply_to_last_command(self, message):
        """Reply to the last person who sent you a message"""
        chat_id = message.chat.id
        
        # Check if user is linked
        twitch_username = self.is_user_linked(chat_id)
        if not twitch_username:
            self.bot.reply_to(message, "❌ Вы должны быть привязаны к Twitch аккаунту для использования этой функции. Используйте /link для привязки.")
            return
            
        self.bot.send_message(chat_id, "Введите сообщение для отправки последнему собеседнику:")
        # Set state to waiting for reply
        self.user_states[chat_id] = {"state": "waiting_for_reply_to_last"}
        
    def show_pm_menu(self, message):
        """Show the private messaging menu"""
        chat_id = message.chat.id
        
        # Check if user is linked
        twitch_username = self.is_user_linked(chat_id)
        if not twitch_username:
            self.bot.reply_to(message, "❌ Вы должны быть привязаны к Twitch аккаунту для использования этой функции. Используйте /link для привязки.")
            return
            
        self.private_messaging.show_chat_menu(chat_id)
    
    def end_private_chat(self, message):
        """End a private chat"""
        chat_id = message.chat.id
        self.private_messaging.end_private_chat(chat_id)
        
    def handle_message(self, message):
        """Обработка входящих сообщений"""
        chat_id = message.chat.id
        message_text = message.text.strip() if message.text else ""
        
        # Обработка команд с reply keyboard
        if message_text == "🎣 Рыбалка":
            # Создаем "message-like" объект для передачи в существующую функцию
           
                
            
            message_stub = MessageStub(chat_id)
            self.fish_telegram(message_stub)
            return
            
        elif message_text == "🐟 Рыба":
            # Создаем "message-like" объект для передачи в существующую функцию
           
            message_stub = MessageStub(chat_id)
            self.fish_command(message_stub)
            return
            
        elif message_text == "📚 Меню":
            self.start_command(message)
            return
            
        elif message_text == "💝 Поддержать Лонли":
            # Создаем "message-like" объект для передачи в существующую функцию
           
                
            
            message_stub = MessageStub(chat_id)
            self.support_lonely(message_stub)
            return
        
        # Check if user is in a special state
        if chat_id in self.user_states:
            user_state = self.user_states[chat_id]
            
            # Handle reply to last sender
            if user_state.get("state") == "waiting_for_reply_to_last":
                if self.private_messaging.reply_to_last_sender(chat_id, message_text):
                    # Clear state
                    if chat_id in self.user_states:
                        del self.user_states[chat_id]
                return
                
        # Check if this is a private message
        if self.private_messaging.send_private_message(chat_id, message_text):
            # Message was handled as a private message
            return
        
        # Проверка, является ли сообщение кодом привязки
        if message_text in self.pending_links:
            # Это код привязки, обрабатываем привязку
            expected_chat_id = self.pending_links[message_text]
            
            if chat_id == expected_chat_id:
                # Это тот же пользователь, но ему нужно отправить код из Twitch
                self.bot.reply_to(
                    message,
                    "Пожалуйста, отправьте этот код из чата Twitch, а не из Telegram."
                )
            else:
                # Кто-то другой отправил код - привязываем аккаунты
                # В реальной реализации Twitch бот бы отправлял имя пользователя
                # Здесь мы используем упрощенный вариант

                # Здесь мы используем упрощенный вариант
                twitch_username = message_text.lower()
                
                if self.link_accounts(chat_id, twitch_username):
                    # Удаляем из ожидаемых привязок
                    del self.pending_links[message_text]
                    
                    self.bot.reply_to(
                        message,
                        f"Аккаунты успешно связаны! Теперь вы можете просматривать свою рыбу с помощью команды /fish."
                    )
                else:
                    self.bot.reply_to(
                        message,
                        "Ошибка при привязке аккаунтов. Проверьте, что пользователь существует в системе."
                    )
        elif chat_id in self.feedback_support.awaiting_feedback:
            # Обрабатываем сообщение обратной связи
            self.process_feedback(message)
        user_state = self.user_states.get(chat_id, {})
        if user_state.get('awaiting_coin_input'):
            self.handle_trade_message(message)
            return
        else:
            # Обычное сообщение, показываем приветствие
            self.start_command(message)

    def process_feedback(self, message):
        """Обработка сообщения обратной связи от пользователя"""
        chat_id = message.chat.id
        user_data = self.get_telegram_user(chat_id)
        twitch_username = user_data[2] if user_data and len(user_data) > 2 else "Неизвестный пользователь"
        
        # Удаляем пользователя из списка ожидающих
        self.feedback_support.awaiting_feedback.discard(chat_id)
        
        try:
            # Получаем информацию о Лонли (lonely_fr)
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                SELECT chat_id FROM telegram_users 
                WHERE twitch_username = ?
            ''', ("lonely_fr",))
            
            dev_result = cursor.fetchone()
            conn.close()
            
            if not dev_result:
                self.bot.send_message(message.chat.id, "❌ Не удалось найти Лонли для отправки сообщения.")
                return
                
            dev_chat_id = dev_result[0]
            
            # Формируем сообщение для Лонли
            feedback_text = "✉️ <b>Новое сообщение от пользователя</b>\n\n"
            feedback_text += f"<b>Пользователь:</b> {twitch_username}\n"
            feedback_text += f"<b>Chat ID:</b> {chat_id}\n"
            feedback_text += f"<b>Время:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            feedback_text += "<b>Сообщение:</b>\n"
            feedback_text += message.text if message.text else "[Нет текста]"
            
            # Отправляем сообщение Лонли
            self.bot.send_message(dev_chat_id, feedback_text, parse_mode='HTML')
            
            # Подтверждаем получение пользователю
            confirmation_text = "✅ Ваше сообщение отправлено Лонли.\nСпасибо за обратную связь!"
            self.bot.send_message(message.chat.id, confirmation_text)
            
        except Exception as e:
            self.bot.send_message(message.chat.id, f"❌ Ошибка при отправке сообщения Лонли: {str(e)}")

    def run(self):
        """Запуск бота"""
        # Запускаем проверку уведомлений о рыбалке
        self.start_fishing_notification_checker()
        try:
            self.bot.polling(none_stop=True, timeout=150)
        except Exception as e:
            logger.error(f"Ошибка бота: {e}")
            time.sleep(3)
            self.run()

    def remove_fish_duplicates(self, fish_ids_to_remove: list):
        """Удаление дубликатов рыбы, оставляя только по одному экземпляру"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Convert to integers for safety
        fish_ids_to_remove = [int(id) for id in fish_ids_to_remove]
        
        # Create placeholders for the query
        placeholders = ','.join('?' * len(fish_ids_to_remove))
        
        cursor.execute(f'''
            DELETE FROM inventory 
            WHERE id IN ({placeholders})
        ''', fish_ids_to_remove)
        
        deleted_count = cursor.rowcount
        conn.commit()
        conn.close()
        return deleted_count

    def duplicates_command(self, message):
        """Обработка команды /duplicates"""
        chat_id = message.chat.id
        
        # Проверяем, привязан ли пользователь
        user_data = self.get_telegram_user(chat_id)
        
        if not user_data or not user_data[2]:  # Не привязан
            message_text = "Ваш аккаунт не привязан. Используйте команду /link для привязки."
            try:
                sent_message = self.bot.send_message(chat_id, message_text)
                self.user_messages[chat_id] = sent_message.message_id
            except:
                pass
            return
        
        # Получаем дубликаты рыбы пользователя
        duplicates = self.get_duplicate_fish(user_data[2])  # user_data[2] это twitch_username
        
        if not duplicates:
            message_text = "У вас нет дубликатов рыбы. Все экземпляры уникальны!"
            try:
                sent_message = self.bot.send_message(chat_id, message_text)
                self.user_messages[chat_id] = sent_message.message_id
            except:
                pass
            return
        
        # Сохраняем состояние пользователя
        self.user_states[chat_id] = {
            'state': 'duplicates',
            'duplicates': duplicates
        }
        
        # Отображаем дубликаты
        self.show_duplicates_page(chat_id, duplicates, 0)

    def show_buy_fish_page(self, chat_id, all_fish, page):
        """Отображение страницы с рыбами для покупки"""
        ITEMS_PER_PAGE = 40
        total_items = len(all_fish)
        total_pages = (total_items + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
        
        if page < 0:
            page = 0
        elif page >= total_pages:
            page = total_pages - 1
        
        start_index = page * ITEMS_PER_PAGE
        end_index = min(start_index + ITEMS_PER_PAGE, total_items)
        page_items = all_fish[start_index:end_index]
        
        # Сохраняем состояние пользователя
        self.user_states[chat_id] = {
            'buy_fish': all_fish,
            'current_page': page
        }
        
        # Получаем баланс пользователя
        user_data = self.get_telegram_user(chat_id)
        twitch_username = user_data[2] if user_data and len(user_data) > 2 else None
        balance = self.get_user_balance(twitch_username) if twitch_username else 0
        skidka = self.upgrade_system.get_user_upgrades(twitch_username)
        skidka = int(skidka["shop_discount"])*0.00017*100

        # Формируем сообщение
        message_text = f"💰 <b>Купить рыбу</b> (Страница {page + 1}/{total_pages})\n"
        message_text += f"💳 <b>Ваш баланс:</b> {balance} LC\n\n"
        message_text +=f"Ваша скидка: {skidka}%"
        keyboard = types.InlineKeyboardMarkup()
        
        for i, fish in enumerate(page_items):
            fish_id = fish['id']
            fish_name = fish['name']
            fish_rarity = self.RARITY_NAMES_RU.get(fish['rarity'], fish['rarity'])
            # Получаем цену рыбы из словаря цен
            fish_price = self.buy_fish_price.get(fish['rarity'], 100)  # По умолчанию 100
            
            # Проверяем, является ли рыба уникальной и пойманной
            is_unique_caught = fish['rarity'] == 'ultimate' and fish.get('caught_by') is not None
            
            # Формируем текст кнопки
            if is_unique_caught:
                button_text = f"❌ {fish_name} ({fish_rarity}) - {fish_price} LC (Поймана)"
            else:
                button_text = f"💰 {fish_name} ({fish_rarity}) - {fish_price} LC"
            
            # Добавляем кнопку для каждой рыбы
            button = types.InlineKeyboardButton(
                text=button_text,
                callback_data=f"buy_fish_item:{fish_id}" if not is_unique_caught else "fish_caught"
            )
            
            # Добавляем кнопку только если рыба не поймана
            if not is_unique_caught:
                keyboard.add(button)
        
        # Кнопки навигации
        nav_buttons = []
        if page > 0:
            nav_buttons.append(types.InlineKeyboardButton(
                text="⬅️ Назад", 
                callback_data=f"buy_fish_page:{page - 1}"
            ))
        
        if page < total_pages - 1:
            nav_buttons.append(types.InlineKeyboardButton(
                text="Вперёд ➡️", 
                callback_data=f"buy_fish_page:{page + 1}"
            ))
        
        if nav_buttons:
            keyboard.row(*nav_buttons)
        
        # Кнопка возврата в меню
        menu_button = types.InlineKeyboardButton(
            text="🔙 Назад в меню", 
            callback_data="main_menu"
        )
        keyboard.add(menu_button)
        
        # Редактируем сообщение или отправляем новое
        try:
            if chat_id in self.user_messages:
                # Пытаемся редактировать существующее сообщение
                try:
                    edited_message = self.bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=self.user_messages[chat_id],
                        text=message_text,
                        reply_markup=keyboard,
                        parse_mode='HTML'
                    )
                    return
                except telebot.apihelper.ApiTelegramException as e:
                    if e.result.status_code == 400 and "message is not modified" in e.result.description:
                        return
                    else:
                        raise e
        
        except telebot.apihelper.ApiTelegramException as e:
            if e.result.status_code == 400 and "message is not modified" in e.result.description:
                return
            else:
                raise e
        
        # Если сообщение не может быть отредактировано, отправляем новое
        message = self.bot.send_message(
            chat_id=chat_id,
            text=message_text,
            reply_markup=keyboard,
            parse_mode='HTML'
        )
        self.user_messages[chat_id] = message.message_id

    def show_duplicates_page(self, chat_id, duplicates, page):
        """Отображение страницы с дубликатами рыбы"""
        ITEMS_PER_PAGE = 5
        total_items = len(duplicates)
        total_pages = (total_items + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
        
        if page < 0:
            page = 0
        elif page >= total_pages:
            page = total_pages - 1
        
        start_index = page * ITEMS_PER_PAGE
        end_index = min(start_index + ITEMS_PER_PAGE, total_items)
        page_items = duplicates[start_index:end_index]
        
        # Сохраняем состояние пользователя
        self.user_states[chat_id] = {
            'state': 'duplicates',
            'duplicates': duplicates,
            'current_page': page
        }
        
        # Формируем сообщение
        message_text = f"🐟 <b>Дубликаты рыбы</b> (Страница {page + 1}/{total_pages})\n\n"
        message_text += "Эти виды рыбы присутствуют в вашем инвентаре в нескольких экземплярах.\n"
        message_text += "Выберите рыбу, чтобы просмотреть и удалить дубликаты.\n\n"
        
        keyboard = types.InlineKeyboardMarkup()
        
        for i, item in enumerate(page_items):
            fish_name = item[0]  # Название рыбы
            fish_count = item[1]  # Количество
            
            # Добавляем кнопку для выбора конкретной рыбы
            button = types.InlineKeyboardButton(
                text=f"🐟 {fish_name} ({fish_count} шт.)", 
                callback_data=f"select_fish_duplicates:{start_index + i}"
            )
            keyboard.add(button)
        
        # Кнопки навигации
        nav_buttons = []
        if page > 0:
            nav_buttons.append(types.InlineKeyboardButton(
                text="⬅️ Назад", 
                callback_data=f"duplicates_page:{page - 1}"
            ))
        
        if page < total_pages - 1:
            nav_buttons.append(types.InlineKeyboardButton(
                text="Вперёд ➡️", 
                callback_data=f"duplicates_page:{page + 1}"
            ))
        
        if nav_buttons:
            keyboard.row(*nav_buttons)
        
        # Кнопка возврата к основному меню
        menu_button = types.InlineKeyboardButton(
                text="🏠 В меню",
                callback_data="main_menu"
            )
        keyboard.add(menu_button)
        
        # Редактируем сообщение или отправляем новое
        try:
            if chat_id in self.user_messages:
                # Пытаемся редактировать существующее сообщение
                try:
                    edited_message = self.bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=self.user_messages[chat_id],
                        text=message_text,
                        reply_markup=keyboard,
                        parse_mode='HTML'
                    )
                except telebot.apihelper.ApiException:
                    # Если не удалось редактировать, отправляем новое сообщение
                    sent_message = self.bot.send_message(
                        chat_id, 
                        message_text, 
                        reply_markup=keyboard, 
                        parse_mode='HTML'
                    )
                    # Сохраняем ID нового сообщения
                    self.user_messages[chat_id] = sent_message.message_id
            else:
                # Отправляем новое сообщение и сохраняем его ID
                sent_message = self.bot.send_message(
                    chat_id, 
                    message_text, 
                    reply_markup=keyboard, 
                    parse_mode='HTML'
                )
                self.user_messages[chat_id] = sent_message.message_id
        except Exception as e:
            # Если возникла любая ошибка, отправляем обычным текстом
            sent_message = self.bot.send_message(
                chat_id, 
                message_text,
                parse_mode='HTML'
            )
            self.user_messages[chat_id] = sent_message.message_id


    def show_all_fish_page(self, chat_id, all_fish, page):
        """Отображение страницы со всеми рыбами"""
        ITEMS_PER_PAGE = 25
        total_items = len(all_fish)
        total_pages = (total_items + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
        
        if page < 0:
            page = 0
        elif page >= total_pages:
            page = total_pages - 1
        
        start_index = page * ITEMS_PER_PAGE
        end_index = min(start_index + ITEMS_PER_PAGE, total_items)
        page_items = all_fish[start_index:end_index]
        
        # Получаем Twitch имя пользователя, если он привязан
        user_fish_names = set()
        user_data = self.get_telegram_user(chat_id)
        if user_data and user_data[2]:  # user_data[2] это twitch_username
            # Получаем инвентарь пользователя
            user_inventory = self.get_user_inventory(user_data[2])
            # Создаем множество названий рыб в инвентаре пользователя
            user_fish_names = {item[4] for item in user_inventory}  # 
        # Сохраняем состояние пользователя
        self.user_states[chat_id] = {
            'all_fish': all_fish,
            'current_page': page
        }
        
        # Формируем сообщение
        message_text = f"📚 <b>Все доступные рыбы</b> (Страница {page + 1}/{total_pages})\n\n"
        
        # Добавляем информацию о каждой рыбе
        for fish in page_items:
            fish_name = fish['name']
            fish_rarity = self.RARITY_NAMES_RU.get(fish['rarity'], fish['rarity'])
            
            # Проверяем, есть ли рыба у пользователя
            has_fish = fish_name in user_fish_names
            fish_marker = "✅" if has_fish else "❌"
            
            message_text += f"{fish_marker} <b>{fish_name}</b> ({fish_rarity})\n"
            
            # Если рыба уникальная и поймана, добавляем информацию о том, кто её поймал
            if fish['rarity'] == 'ultimate' and fish['caught_by']:
                message_text += f"    Поймана: {fish['caught_by']}\n"
            elif fish['rarity'] == 'ultimate':
                message_text += "    Не поймана\n"
        
        # Создаем клавиатуру
        keyboard = types.InlineKeyboardMarkup()
        
        # Кнопки навигации
        nav_buttons = []
        if page > 0:
            nav_buttons.append(types.InlineKeyboardButton(
                text="⬅️ Назад", 
                callback_data=f"all_fish_page:{page - 1}"
            ))
        
        if page < total_pages - 1:
            nav_buttons.append(types.InlineKeyboardButton(
                text="Вперёд ➡️", 
                callback_data=f"all_fish_page:{page + 1}"
            ))
        if page < total_pages - 1:
            nav_buttons.append(types.InlineKeyboardButton(
                text="К последней ➡️", 
                callback_data=f"all_fish_page:{total_pages-1}"
            ))
        if nav_buttons:
            keyboard.row(*nav_buttons)
        
        # Кнопка возврата в меню
        menu_button = types.InlineKeyboardButton(
            text="🔙 Назад в меню", 
            callback_data="main_menu"
        )
        keyboard.add(menu_button)
        
        # Редактируем сообщение или отправляем новое
        try:
            if chat_id in self.user_messages:
                # Пытаемся редактировать существующее сообщение
                try:
                    edited_message = self.bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=self.user_messages[chat_id],
                        text=message_text,
                        reply_markup=keyboard,
                        parse_mode='HTML'
                    )
                except telebot.apihelper.ApiException:
                    # Если не удалось редактировать, отправляем новое сообщение
                    sent_message = self.bot.send_message(
                        chat_id, 
                        message_text, 
                        reply_markup=keyboard, 
                        parse_mode='HTML'
                    )
                    # Сохраняем ID нового сообщения
                    self.user_messages[chat_id] = sent_message.message_id
            else:
                # Отправляем новое сообщение и сохраняем его ID
                sent_message = self.bot.send_message(
                    chat_id, 
                    message_text, 
                    reply_markup=keyboard, 
                    parse_mode='HTML'
                )
                self.user_messages[chat_id] = sent_message.message_id
        except Exception as e:
            # Если возникла любая ошибка, отправляем обычным текстом
            sent_message = self.bot.send_message(
                chat_id, 
                message_text,
                parse_mode='HTML'
            )
            self.user_messages[chat_id] = sent_message.message_id


    def start_command(self, message):
        """Обработка команды /start"""
        chat_id = message.chat.id
        logger.info("Handling /start command from chat_id=%s", chat_id)
        
        # Сохраняем ID сообщения
        self.user_messages[chat_id] = message.message_id
        
        # Создаем клавиатуру с кнопками
        keyboard = types.InlineKeyboardMarkup()
        
        # Проверяем, привязан ли пользователь
        is_linked = self.is_user_linked(chat_id)
        
        # Создаем reply keyboard для быстрого доступа к функциям
        reply_keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
        menu_button = types.KeyboardButton("📚 Меню")
        reply_keyboard.add(menu_button)
        second_row = [types.KeyboardButton("🎣 Рыбалка"), types.KeyboardButton("🐟 Рыба"), types.KeyboardButton("💝 Поддержать Лонли")]
        reply_keyboard.add(*second_row)
        
        if not is_linked:
            # Если пользователь не привязан, показываем только кнопку привязки
            link_button = types.InlineKeyboardButton(text="🔗 Привязать аккаунт", callback_data="link_account")
            keyboard.add(link_button)
        else:
            # Если пользователь привязан, показываем полное меню без кнопки привязки
            fish_button = types.InlineKeyboardButton(text="🐟 Посмотреть рыбу",callback_data="view_fish")
            catch_button = types.InlineKeyboardButton(text="🎣 Поймать рыбу", callback_data="catch_fish")
            collection_button = types.InlineKeyboardButton(text="📚 Моя коллекция", callback_data="view_my_collection")
            trade_button = types.InlineKeyboardButton(text="🐟<-->🐟 Обменник", callback_data="trademenu")
            all_fish_button = types.InlineKeyboardButton(text="📖 Все рыбы", callback_data="view_all_fish")
            duplicates_button = types.InlineKeyboardButton(text="🔢 Дубликаты", callback_data="view_duplicates")
            buy_fish_button = types.InlineKeyboardButton(text="🛒 Купить рыбу", callback_data="buy_fish")
            mini_collections_button = types.InlineKeyboardButton(text="📦 Мини-коллекции", callback_data="view_mini_collections")
            
            # Дополнительные кнопки
            balance_button = types.InlineKeyboardButton(text="💰 Баланс", callback_data="view_balance")
            chat_button = types.InlineKeyboardButton(text="💬 Чат", callback_data="private_messages")
            info_button = types.InlineKeyboardButton(text="ℹ️ Информация", callback_data="view_info")
            help_button = types.InlineKeyboardButton(text="❓ Помощь", callback_data="view_help")
            contact_button = types.InlineKeyboardButton(text="✉️ Связь с Лонли", callback_data="contact_lonely")
            support_button = types.InlineKeyboardButton(text="💝 Поддержать Лонли", callback_data="support_lonely")
            settings_button = types.InlineKeyboardButton(text="⚙️ Настройки", callback_data="view_settings")
            paste_button = types.InlineKeyboardButton(text="📋 Копипасты", callback_data="pastemenu")
            upgrade_button = types.InlineKeyboardButton(text="Upgrade", callback_data="upgrademenu")
            # Добавляем кнопки в клавиатуру
            keyboard.add(fish_button, catch_button)
            keyboard.add(all_fish_button, duplicates_button)
            keyboard.add(buy_fish_button, mini_collections_button)
            keyboard.add(trade_button, collection_button) 
            keyboard.add(balance_button, chat_button)
            keyboard.add(info_button, help_button)
            keyboard.add(contact_button, support_button)
            keyboard.add(settings_button, paste_button)
            keyboard.add(upgrade_button)

            if self.is_paste_moder(chat_id):
                paste_mod_button =types.InlineKeyboardButton(text="⚙️ Управление пастами", callback_data="aprovemenu")
                keyboard.add(paste_mod_button)
        # Формируем приветственное сообщение
        welcome_text = (
            "👋 Добро пожаловать в бота!\n\n"
        )
        
        # Редактируем сообщение или отправляем новое
        try:
            if chat_id in self.user_messages:
                # Пытаемся редактировать существующее сообщение
                try:
                    edited_message = self.bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=self.user_messages[chat_id],
                        text=welcome_text,
                        reply_markup=keyboard,
                        parse_mode='HTML'
                    )
                except telebot.apihelper.ApiException:
                    # Если не удалось редактировать, отправляем новое сообщение
                    sent_message = self.bot.send_message(
                        chat_id, 
                        welcome_text, 
                        reply_markup=keyboard,
                        parse_mode='HTML'
                    )
                    # Сохраняем ID нового сообщения
                    self.user_messages[chat_id] = sent_message.message_id
            else:
                # Отправляем новое сообщение и сохраняем его ID
                sent_message = self.bot.send_message(
                    chat_id, 
                    welcome_text, 
                    reply_markup=keyboard,
                    parse_mode='HTML'
                )
                self.user_messages[chat_id] = sent_message.message_id
                
            # Отправляем reply keyboard отдельным сообщением
        except Exception as e:
            # Если возникла любая ошибка, отправляем обычным текстом
            sent_message = self.bot.send_message(
                chat_id, 
                welcome_text,
                parse_mode='HTML'
            )
            self.user_messages[chat_id] = sent_message.message_id

    def show_fish_duplicates_details(self, chat_id, fish_index, data):
        """Отображение подробной информации о дубликатах конкретной рыбы"""
        # Получаем состояние пользователя
        fish_index = int(data.split(":")[1])
        user_state = self.user_states.get(chat_id)
        if not user_state or user_state.get('state') != 'duplicates':
            return
        
        duplicates = user_state['duplicates']
        if fish_index >= len(duplicates):
            return
        
        item = duplicates[fish_index]
        fish_name = item[0]  # Название рыбы
        fish_count = item[1]  # Количество
        fish_ids = item[2].split(',')  # Список ID
        fish_rarities = item[3].split(',')  # Список редкостей
        fish_values = item[4].split(',')  # Список значений
        
        # Создаем список всех экземпляров для сортировки
        all_instances = []
        for i in range(len(fish_ids)):
            if i < len(fish_rarities) and i < len(fish_values):
                all_instances.append({
                    'id': fish_ids[i],
                    'rarity': fish_rarities[i],
                    'value': int(fish_values[i])
                })
        
        # Сортируем все экземпляры по возрастанию стоимости
        all_instances.sort(key=lambda x: x['value'])
        
        # Первый экземпляр оставляем, остальные - дубликаты для удаления
        main_instance = all_instances[0]  # Самый дешевый экземпляр оставляем
        duplicates_list = all_instances[1:]  # Все остальные - дубликаты
        
        # Получаем ID для удаления и считаем общую стоимость
        ids_to_remove = [dup['id'] for dup in duplicates_list]
        values_to_sum = [dup['value'] for dup in duplicates_list]
        duplicate_value = sum(values_to_sum)
        
        # Формируем сообщение
        message_text = f"🐟 <b>{fish_name}</b>\n\n"
        message_text += f"Общее количество: {fish_count}\n"
        message_text += f"Дубликатов для удаления: {len(ids_to_remove)}\n"
        message_text += f"Суммарная стоимость дубликатов: {duplicate_value} LC\n\n"
        message_text += f"Оставляемый экземпляр: Редкость: {main_instance['rarity']}, Стоимость: {main_instance['value']} LC\n\n"
        message_text += "Дубликаты (отсортированы по стоимости):\n"
        
        # Детали по каждому дубликату (уже отсортированы)
        for i, duplicate in enumerate(duplicates_list, 1):
            message_text += f"{i}. Редкость: {duplicate['rarity']}, Стоимость: {duplicate['value']} LC\n"
        
        # Создаем клавиатуру с действиями
        keyboard = types.InlineKeyboardMarkup()
        
        # Кнопка удаления дубликатов
        if ids_to_remove:
            sell_button = types.InlineKeyboardButton(
                text=f"💰 Продать дубликаты ({duplicate_value} LC)", 
                callback_data=f"sell_fish_duplicates:{fish_index}"
            )
            keyboard.add(sell_button)
        # Кнопка возврата к списку дубликатов
        back_button = types.InlineKeyboardButton(
            text="🔙 Назад к списку дубликатов", 
            callback_data=f"duplicates_page:{user_state.get('current_page', 0)}"
        )
        keyboard.add(back_button)
        
        # Редактируем сообщение или отправляем новое
        try:
            if chat_id in self.user_messages:
                # Пытаемся редактировать существующее сообщение
                try:
                    edited_message = self.bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=self.user_messages[chat_id],
                        text=message_text,
                        reply_markup=keyboard,
                        parse_mode='HTML'
                    )
                except telebot.apihelper.ApiException:
                    # Если не удалось редактировать, отправляем новое сообщение
                    sent_message = self.bot.send_message(
                        chat_id, 
                        message_text, 
                        reply_markup=keyboard, 
                        parse_mode='HTML'
                    )
                    # Сохраняем ID нового сообщения
                    self.user_messages[chat_id] = sent_message.message_id
            else:
                # Отправляем новое сообщение и сохраняем его ID
                sent_message = self.bot.send_message(
                    chat_id, 
                    message_text, 
                    reply_markup=keyboard, 
                    parse_mode='HTML'
                )
                self.user_messages[chat_id] = sent_message.message_id
        except Exception as e:
            # Если возникла любая ошибка, отправляем обычным текстом
            sent_message = self.bot.send_message(
                chat_id, 
                message_text,
                parse_mode='HTML'
            )
            self.user_messages[chat_id] = sent_message.message_id

    def show_mini_collections(self, chat_id):
        """Отображение списка мини-коллекций"""
        # Проверяем, привязан ли пользователь
        user_data = self.get_telegram_user(chat_id)
        if not user_data or not user_data[2]:
            message_text = "Ваш аккаунт не привязан. Используйте команду /link для привязки."
            
            # Добавляем кнопку возврата в меню
            keyboard = types.InlineKeyboardMarkup()
            back_button = types.InlineKeyboardButton(
                text="🔙 Назад в меню", 
                callback_data="main_menu"
            )
            keyboard.add(back_button)
            
            try:
                sent_message = self.bot.send_message(chat_id, message_text, reply_markup=keyboard)
                self.user_messages[chat_id] = sent_message.message_id
            except:
                pass
            return
        
        twitch_username = user_data[2]
        
        if not self.mini_collections:
            message_text = "Пока нет доступных мини-коллекций."
            
            # Добавляем кнопку возврата в меню
            keyboard = types.InlineKeyboardMarkup()
            back_button = types.InlineKeyboardButton(
                text="🔙 Назад в меню", 
                callback_data="main_menu"
            )
            keyboard.add(back_button)
            
            try:
                sent_message = self.bot.send_message(chat_id, message_text, reply_markup=keyboard)
                self.user_messages[chat_id] = sent_message.message_id
            except:
                pass
            return
        
        # Получаем инвентарь пользователя
        user_inventory = self.get_user_inventory(twitch_username)
        user_fish_ids = {item[3] for item in user_inventory}  # item[3] is item_id
        
        # Формируем сообщение
        message_text = "🏅 <b>Доступные мини-коллекции</b>\n\n"
        
        keyboard = types.InlineKeyboardMarkup()
        
        for collection in self.mini_collections:
            collection_id = collection['id']
            collection_name = collection['name']
            collection_rarity = self.RARITY_NAMES_RU.get(collection['rarity'], collection['rarity'])
            
            # Проверяем, сколько рыб из коллекции у пользователя
            collected_count = sum(1 for fish_id in collection['fish_ids'] if fish_id in user_fish_ids)
            total_count = len(collection['fish_ids'])
            
            # Добавляем кнопку для каждой коллекции
            button_text = f"{collection_name} ({collected_count}/{total_count}) [{collection_rarity}]"
            button = types.InlineKeyboardButton(
                text=button_text,
                callback_data=f"view_mini_collection:{collection_id}"
            )
            keyboard.add(button)
        
        # Кнопка возврата в меню
        back_button = types.InlineKeyboardButton(
            text="🔙 Назад в меню", 
            callback_data="main_menu"
        )
        keyboard.add(back_button)
        
        try:
            sent_message = self.bot.send_message(chat_id, message_text, reply_markup=keyboard, parse_mode='HTML')
            self.user_messages[chat_id] = sent_message.message_id
        except:
            pass


    def show_mini_collection_details(self, chat_id, collection_id):
        """Отображение подробной информации о мини-коллекции"""
        # Проверяем, привязан ли пользователь
        user_data = self.get_telegram_user(chat_id)
        if not user_data or not user_data[2]:
            message_text = "Ваш аккаунт не привязан. Используйте команду /link для привязки."
            
            # Добавляем кнопку возврата в меню
            keyboard = types.InlineKeyboardMarkup()
            back_button = types.InlineKeyboardButton(
                text="🔙 Назад в меню", 
                callback_data="main_menu"
            )
            keyboard.add(back_button)
            
            try:
                sent_message = self.bot.send_message(chat_id, message_text, reply_markup=keyboard)
                self.user_messages[chat_id] = sent_message.message_id
            except:
                pass
            return
        
        twitch_username = user_data[2]
        
        # Находим коллекцию по ID
        collection = next((c for c in self.mini_collections if c['id'] == collection_id), None)
        if not collection:
            message_text = "Коллекция не найдена."
            
            # Добавляем кнопку возврата в меню
            keyboard = types.InlineKeyboardMarkup()
            back_button = types.InlineKeyboardButton(
                text="🔙 Назад в меню", 
                callback_data="main_menu"
            )
            keyboard.add(back_button)
            
            try:
                sent_message = self.bot.send_message(chat_id, message_text, reply_markup=keyboard)
                self.user_messages[chat_id] = sent_message.message_id
            except:
                pass
            return
        
        # Получаем инвентарь пользователя
        user_inventory = self.get_user_inventory(twitch_username)
        user_fish_ids = {item[3] for item in user_inventory}  # item[3] is item_id
        
        # Формируем сообщение
        collection_rarity = self.RARITY_NAMES_RU.get(collection['rarity'], collection['rarity'])
        message_text = f"🏅 <b>{collection['name']}</b>\n"
        message_text += f"<b>Редкость:</b> {collection_rarity}\n\n"
        message_text += "<b>Рыбы в коллекции:</b>\n"
        
        keyboard = types.InlineKeyboardMarkup()
        
        # Добавляем информацию о каждой рыбе в коллекции
        for fish_id in collection['fish_ids']:
            fish = self.get_fish_by_id_from_db(fish_id)
            if fish:
                fish_name = fish[1]  # fish[1] is name
                fish_rarity = self.RARITY_NAMES_RU.get(fish[4], fish[4]) if fish[4] else "Неизвестная"
                
                # Проверяем, есть ли рыба у пользователя
                has_fish = fish_id in user_fish_ids
                fish_marker = "✅" if has_fish else "❌"
                
                message_text += f"{fish_marker} {fish_name} ({fish_rarity})\n"
            else:
                message_text += f"❌ Рыба с ID {fish_id} не найдена\n"
        
        message_text += "\n"
        
        # Кнопка возврата к списку коллекций
        back_button = types.InlineKeyboardButton(
            text="🔙 Назад к коллекциям", 
            callback_data="view_mini_collections"
        )
        keyboard.add(back_button)
        
        # Кнопка возврата в меню
        menu_button = types.InlineKeyboardButton(
            text="🏠 В меню", 
            callback_data="main_menu"
        )
        keyboard.add(menu_button)
        
        try:
            sent_message = self.bot.send_message(chat_id, message_text, reply_markup=keyboard, parse_mode='HTML')
            self.user_messages[chat_id] = sent_message.message_id
        except:
            pass
class MessageStub:
    def __init__(self, chat_id):
        self.chat = type('Chat', (), {'id': chat_id})()
        self.message_id = None
        self.text = ""
            
def start_telegram_bot(token: str):
    """
    Запуск Telegram бота в отдельном потоке
    """
    bot = TelegramBot(token)
    bot.run()

