import sqlite3
import logging
from telebot import types
from datetime import datetime

logger = logging.getLogger(__name__)

class TradeSystem:
    def __init__(self, db_path: str = 'bot_database.db'):
        self.db_path = db_path
        self.create_trades_table()
    
    def create_trades_table(self):
        """Создание таблицы для обмена"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                creator_username TEXT NOT NULL,
                offered_fish_id INTEGER,  -- ID из таблицы inventory
                offered_coins INTEGER DEFAULT 0,
                requested_fish_id INTEGER,  -- ID из таблицы items
                requested_coins INTEGER DEFAULT 0,
                status TEXT DEFAULT 'active', -- active, completed, cancelled
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP NULL,
                responder_username TEXT NULL
            )
        ''')
        
        conn.commit()
        conn.close()
        logger.info("Trades table created or verified successfully")
    
    def add_trade_methods(self, bot_class):
        """Добавление методов обмена в класс бота"""
        
        def trade_command(self, message):
            """Handle the /trade command - main entry point for trading system"""
            chat_id = message.chat.id
            
            # Check if user is linked
            user_data = self.get_telegram_user(chat_id)
            if not user_data or not user_data[2]:
                message_text = "Ваш аккаунт не привязан. Используйте команду /link для привязки."
                keyboard = types.InlineKeyboardMarkup()
                back_button = types.InlineKeyboardButton(text="🔙 Назад в меню", callback_data="main_menu")
                keyboard.add(back_button)
                
                try:
                    sent_message = self.bot.send_message(chat_id, message_text, reply_markup=keyboard)
                    self.user_messages[chat_id] = sent_message.message_id
                except:
                    pass
                return
            
            # Show trade main menu
            self.show_trade_menu(chat_id)
        
        def show_trade_menu(self, chat_id):
            """Show the main trade menu"""
            message_text = "💱 <b>Система обмена</b>\n\n"
            message_text += "Выберите действие:\n"
            message_text += "• Создать предложение обмена\n"
            message_text += "• Посмотреть активные предложения\n"
            message_text += "• Мои предложения\n"
            
            keyboard = types.InlineKeyboardMarkup()
            
            # Create trade button
            create_button = types.InlineKeyboardButton(
                text="📝 Создать обмен", 
                callback_data="trade_create"
            )
            keyboard.add(create_button)
            
            # View active trades button
            view_button = types.InlineKeyboardButton(
                text="🔍 Посмотреть обмены", 
                callback_data="trade_view_active"
            )
            keyboard.add(view_button)
            
            # My trades button
            my_trades_button = types.InlineKeyboardButton(
                text="📦 Мои обмены", 
                callback_data="trade_view_my"
            )
            keyboard.add(my_trades_button)
            
            # Back button
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
                        reply_markup=keyboard,
                        parse_mode='HTML'
                    )
                else:
                    sent_message = self.bot.send_message(
                        chat_id, 
                        message_text, 
                        reply_markup=keyboard,
                        parse_mode='HTML'
                    )
                    self.user_messages[chat_id] = sent_message.message_id
            except:
                sent_message = self.bot.send_message(
                    chat_id, 
                    message_text,
                    reply_markup=keyboard,
                    parse_mode='HTML'
                )
                self.user_messages[chat_id] = sent_message.message_id
        
        def create_trade_offer(self, chat_id):
            """Start creating a trade offer"""
            user_data = self.get_telegram_user(chat_id)
            twitch_username = user_data[2]
            
            # Save state - user is creating a trade
            self.user_states[chat_id] = {
                'state': 'creating_trade',
                'offered_fish': None,
                'offered_coins': 0,
                'requested_fish': None,
                'requested_coins': 0
            }
            
            # Show what user can offer
            self.show_user_offer_options(chat_id, twitch_username)
        
        def show_user_offer_options(self, chat_id, twitch_username, page=0):
            """Show what user can offer in a trade"""
            message_text = "📤 <b>Что вы хотите предложить?</b>\n\n"
            message_text += "Выберите рыбу из своего инвентаря или укажите количество LC:\n"
            
            keyboard = types.InlineKeyboardMarkup()
            
            # Get user inventory
            inventory = self.get_user_inventory(twitch_username)
            fish_items = [item for item in inventory if item[2] == 'fish']  # Only fish items
            
            # Pagination variables
            items_per_page = 10
            total_items = len(fish_items)
            total_pages = (total_items + items_per_page - 1) // items_per_page if total_items > 0 else 1
            page = max(0, min(page, total_pages - 1))
            start_index = page * items_per_page
            end_index = min(start_index + items_per_page, total_items)
            page_fish_items = fish_items[start_index:end_index]
            
            # Add fish options
            for item in page_fish_items:
                fish_id = item[0]  # inventory id (это ID записи в таблице inventory)
                fish_name = item[4]  # fish name (item_name)
                fish_button = types.InlineKeyboardButton(
                    text=f"🐟 {fish_name}",
                    callback_data=f"trade_offer_fish:{fish_id}"
                )
                keyboard.add(fish_button)
            
            # Add pagination buttons
            if total_pages > 1:
                pagination_buttons = []
                if page > 0:
                    pagination_buttons.append(types.InlineKeyboardButton(
                        text="⬅️ Назад",
                        callback_data=f"trade_offer_page:{page-1}"
                    ))
                if page < total_pages - 1:
                    pagination_buttons.append(types.InlineKeyboardButton(
                        text="Вперёд ➡️",
                        callback_data=f"trade_offer_page:{page+1}"
                    ))
                if pagination_buttons:
                    keyboard.add(*pagination_buttons)
            
            # Add coins option
            coins_button = types.InlineKeyboardButton(
                text="💰 Предложить LC",
                callback_data="trade_offer_coins"
            )
            keyboard.add(coins_button)
            
            # Skip offering option
            skip_button = types.InlineKeyboardButton(
                text="⏭ Пропустить",
                callback_data="trade_offer_skip"
            )
            keyboard.add(skip_button)
            
            # Cancel button
            cancel_button = types.InlineKeyboardButton(
                text="❌ Отмена",
                callback_data="trade_menu"
            )
            keyboard.add(cancel_button)
            
            # Add page info if there are multiple pages
            if total_pages > 1:
                message_text += f"\nСтраница {page+1} из {total_pages}\n"
            
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
                    sent_message = self.bot.send_message(
                        chat_id, 
                        message_text, 
                        reply_markup=keyboard,
                        parse_mode='HTML'
                    )
                    self.user_messages[chat_id] = sent_message.message_id
            except:
                sent_message = self.bot.send_message(
                    chat_id, 
                    message_text,
                    reply_markup=keyboard,
                    parse_mode='HTML'
                )
                self.user_messages[chat_id] = sent_message.message_id
        
        def handle_trade_callback(self, chat_id, data):
            """Handle trade-related callback queries"""
            if data == "trade_menu":
                self.show_trade_menu(chat_id)
                
            elif data == "trade_create":
                self.create_trade_offer(chat_id)
                
            elif data == "trade_view_active":
                self.view_active_trades(chat_id, 0)  # Первая страница
                
            elif data.startswith("trade_view_active_page:"):
                page = int(data.split(":")[1])
                self.view_active_trades(chat_id, page)
                
            elif data == "trade_view_my":
                self.view_my_trades(chat_id, 0)  # Первая страница
                
            elif data.startswith("trade_view_my_page:"):
                page = int(data.split(":")[1])
                self.view_my_trades(chat_id, page)
                
            elif data.startswith("trade_offer_page:"):
                page = int(data.split(":")[1])
                twitch_username = self.get_twitch_username(chat_id)
                if twitch_username:
                    self.show_user_offer_options(chat_id, twitch_username, page)
                
            elif data.startswith("trade_offer_fish:"):
                fish_inventory_id = int(data.split(":")[1])
                # Store the offered fish (это ID записи в таблице inventory)
                user_state = self.user_states.get(chat_id, {})
                user_state['offered_fish'] = fish_inventory_id
                self.user_states[chat_id] = user_state
                
                # Now ask what they want in return
                self.show_user_request_options(chat_id)
                
            elif data == "trade_offer_coins":
                # Ask for coin amount to offer
                self.ask_for_coin_amount(chat_id, "offer")
                
            elif data == "trade_offer_skip":
                # Skip offering, go to request
                self.show_user_request_options(chat_id)
                
            elif data.startswith("trade_request_page:"):
                page = int(data.split(":")[1])
                self.show_user_request_options(chat_id, page)
                
            elif data.startswith("trade_request_fish:"):
                fish_item_id = int(data.split(":")[1])
                # Store the requested fish (это ID записи в таблице items)
                user_state = self.user_states.get(chat_id, {})
                user_state['requested_fish'] = fish_item_id
                self.user_states[chat_id] = user_state
                
                # Confirm trade
                self.confirm_trade_creation(chat_id)
                
            elif data == "trade_request_coins":
                # Ask for coin amount to request
                self.ask_for_coin_amount(chat_id, "request")
                
            elif data == "trade_request_skip":
                # Skip requesting, go to confirm
                self.confirm_trade_creation(chat_id)
                
            elif data.startswith("trade_respond:"):
                trade_id = int(data.split(":")[1])
                self.show_respond_to_trade(chat_id, trade_id)
                
            elif data.startswith("trade_accept:"):
                trade_id = int(data.split(":")[1])
                self.accept_trade(chat_id, trade_id)
                
            elif data.startswith("trade_cancel:"):
                trade_id = int(data.split(":")[1])
                self.cancel_trade(chat_id, trade_id)
                
            elif data.startswith("trade_details:"):
                trade_id = int(data.split(":")[1])
                self.show_trade_details(chat_id, trade_id)
        
        def show_user_request_options(self, chat_id, page=0):
            """Show what user can request in a trade"""
            message_text = "📥 <b>Что вы хотите получить?</b>\n\n"
            message_text += "Выберите рыбу или укажите количество LC:\n"
            
            keyboard = types.InlineKeyboardMarkup()
            
            # Add option to request fish from the general items table
            # We'll show a selection of available fish
            
            # For now, let's get some fish from the items table
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('SELECT id, name FROM items WHERE type = "fish"')
            fish_items = cursor.fetchall()
            conn.close()
            
            # Pagination variables
            items_per_page = 10
            total_items = len(fish_items)
            total_pages = (total_items + items_per_page - 1) // items_per_page if total_items > 0 else 1
            page = max(0, min(page, total_pages - 1))
            start_index = page * items_per_page
            end_index = min(start_index + items_per_page, total_items)
            page_fish_items = fish_items[start_index:end_index]
            
            # Add fish options
            for fish in page_fish_items:
                fish_id = fish[0]  # item id (это ID записи в таблице items)
                fish_name = fish[1]
                fish_button = types.InlineKeyboardButton(
                    text=f"🐟 {fish_name}",
                    callback_data=f"trade_request_fish:{fish_id}"
                )
                keyboard.add(fish_button)
            
            # Add pagination buttons
            if total_pages > 1:
                pagination_buttons = []
                if page > 0:
                    pagination_buttons.append(types.InlineKeyboardButton(
                        text="⬅️ Назад",
                        callback_data=f"trade_request_page:{page-1}"
                    ))
                if page < total_pages - 1:
                    pagination_buttons.append(types.InlineKeyboardButton(
                        text="Вперёд ➡️",
                        callback_data=f"trade_request_page:{page+1}"
                    ))
                if pagination_buttons:
                    keyboard.add(*pagination_buttons)
            
            # Add coins option
            coins_button = types.InlineKeyboardButton(
                text="💰 Запросить LC",
                callback_data="trade_request_coins"
            )
            keyboard.add(coins_button)
            
            # Skip requesting option
            skip_button = types.InlineKeyboardButton(
                text="⏭ Пропустить",
                callback_data="trade_request_skip"
            )
            keyboard.add(skip_button)
            
            # Back button
            back_button = types.InlineKeyboardButton(
                text="🔙 Назад",
                callback_data="trade_create"
            )
            keyboard.add(back_button)
            
            # Add page info if there are multiple pages
            if total_pages > 1:
                message_text += f"\nСтраница {page+1} из {total_pages}\n"
            
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
                    sent_message = self.bot.send_message(
                        chat_id, 
                        message_text, 
                        reply_markup=keyboard,
                        parse_mode='HTML'
                    )
                    self.user_messages[chat_id] = sent_message.message_id
            except:
                sent_message = self.bot.send_message(
                    chat_id, 
                    message_text,
                    reply_markup=keyboard,
                    parse_mode='HTML'
                )
                self.user_messages[chat_id] = sent_message.message_id
        
        def ask_for_coin_amount(self, chat_id, coin_type):
            """Ask user for coin amount (either to offer or request)"""
            user_state = self.user_states.get(chat_id, {})
            user_state['awaiting_coin_input'] = coin_type  # "offer" or "request"
            self.user_states[chat_id] = user_state
            
            action = "предложить" if coin_type == "offer" else "запросить"
            message_text = f"💰 Введите количество LC, которое вы хотите {action}:"
            
            keyboard = types.InlineKeyboardMarkup()
            cancel_button = types.InlineKeyboardButton(
                text="❌ Отмена",
                callback_data="trade_create"
            )
            keyboard.add(cancel_button)
            
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
                    sent_message = self.bot.send_message(
                        chat_id, 
                        message_text, 
                        reply_markup=keyboard,
                        parse_mode='HTML'
                    )
                    self.user_messages[chat_id] = sent_message.message_id
            except:
                sent_message = self.bot.send_message(
                    chat_id, 
                    message_text,
                    reply_markup=keyboard,
                    parse_mode='HTML'
                )
                self.user_messages[chat_id] = sent_message.message_id
        
        def handle_trade_message(self, message):
            """Handle regular text messages for trade system"""
            chat_id = message.chat.id
            
            # Check if we're waiting for coin input
            user_state = self.user_states.get(chat_id, {})
            if user_state.get('awaiting_coin_input'):
                coin_type = user_state['awaiting_coin_input']
                try:
                    amount = int(message.text)
                    if amount < 0:
                        raise ValueError("Amount cannot be negative")
                    
                    # Store the amount
                    if coin_type == "offer":
                        user_state['offered_coins'] = amount
                    else:  # request
                        user_state['requested_coins'] = amount
                    
                    # Remove the awaiting flag
                    del user_state['awaiting_coin_input']
                    self.user_states[chat_id] = user_state
                    
                    # Continue with trade creation
                    if coin_type == "offer":
                        self.show_user_request_options(chat_id)
                    else:  # request
                        self.confirm_trade_creation(chat_id)
                        
                except ValueError:
                    # Invalid input, ask again
                    action = "предложить" if coin_type == "offer" else "запросить"
                    message_text = f"❌ Пожалуйста, введите корректное количество LC для {action}:"
                    try:
                        sent_message = self.bot.send_message(chat_id, message_text)
                        self.user_messages[chat_id] = sent_message.message_id
                    except:
                        pass
                return
        
        def confirm_trade_creation(self, chat_id):
            """Confirm and save the trade offer"""
            user_data = self.get_telegram_user(chat_id)
            twitch_username = user_data[2] if user_data else None
            
            if not twitch_username:
                return
            
            user_state = self.user_states.get(chat_id, {})
            
            # Get trade details
            offered_fish = user_state.get('offered_fish')  # ID из таблицы inventory
            offered_coins = user_state.get('offered_coins', 0)
            requested_fish = user_state.get('requested_fish')  # ID из таблицы items
            requested_coins = user_state.get('requested_coins', 0)
            
            # Validate that at least something is offered and requested
            if not (offered_fish or offered_coins) or not (requested_fish or requested_coins):
                message_text = "❌ Вы должны предложить и запросить что-то для создания обмена!"
                keyboard = types.InlineKeyboardMarkup()
                back_button = types.InlineKeyboardButton(
                    text="🔙 Назад в меню обмена",
                    callback_data="trade_menu"
                )
                keyboard.add(back_button)
                
                try:
                    sent_message = self.bot.send_message(chat_id, message_text, reply_markup=keyboard)
                    self.user_messages[chat_id] = sent_message.message_id
                except:
                    pass
                return
            
            # Save trade to database
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            try:
                cursor.execute('''
                    INSERT INTO trades 
                    (creator_username, offered_fish_id, offered_coins, requested_fish_id, requested_coins)
                    VALUES (?, ?, ?, ?, ?)
                ''', (twitch_username, offered_fish, offered_coins, requested_fish, requested_coins))
                
                conn.commit()
                trade_id = cursor.lastrowid
                
                # Success message
                message_text = "✅ Предложение обмена успешно создано!\n\n"
                message_text += f"ID обмена: {trade_id}\n"
                
                # Add details of what's being offered
                if offered_fish:
                    # Get fish details from inventory
                    cursor.execute('''
                        SELECT i.item_name FROM inventory i 
                        WHERE i.id = ?
                    ''', (offered_fish,))
                    fish_result = cursor.fetchone()
                    if fish_result:
                        message_text += f"Предложено: 🐟 {fish_result[0]}\n"
                
                if offered_coins > 0:
                    message_text += f"Предложено: 💰 {offered_coins} LC\n"
                
                # Add details of what's being requested
                if requested_fish:
                    # Get fish details from items
                    cursor.execute('''
                        SELECT i.name FROM items i 
                        WHERE i.id = ?
                    ''', (requested_fish,))
                    fish_result = cursor.fetchone()
                    if fish_result:
                        message_text += f"Запрошено: 🐟 {fish_result[0]}\n"
                
                if requested_coins > 0:
                    message_text += f"Запрошено: 💰 {requested_coins} LC\n"
                    
            except sqlite3.Error as e:
                message_text = f"❌ Ошибка при создании обмена: {str(e)}"
                logger.error(f"Database error creating trade: {e}")
            finally:
                conn.close()
            
            # Show success message with back button
            keyboard = types.InlineKeyboardMarkup()
            view_trades_button = types.InlineKeyboardButton(
                text="🔍 Посмотреть обмены",
                callback_data="trade_view_active"
            )
            keyboard.add(view_trades_button)
            
            back_button = types.InlineKeyboardButton(
                text="🔙 Назад в меню",
                callback_data="trade_menu"
            )
            keyboard.add(back_button)
            
            try:
                sent_message = self.bot.send_message(
                    chat_id, 
                    message_text, 
                    reply_markup=keyboard,
                    parse_mode='HTML'
                )
                self.user_messages[chat_id] = sent_message.message_id
            except:
                pass
            
            # Clear user state
            if chat_id in self.user_states:
                del self.user_states[chat_id]
        
        def view_active_trades(self, chat_id, page=0):
            """Show active trades to the user with pagination"""
            ITEMS_PER_PAGE = 10
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get user's username
            user_data = self.get_telegram_user(chat_id)
            twitch_username = user_data[2] if user_data else None
            
            # Get total count of active trades (excluding user's own)
            if twitch_username:
                cursor.execute('''
                    SELECT COUNT(*) FROM trades t
                    WHERE t.status = 'active' AND t.creator_username != ?
                ''', (twitch_username,))
            else:
                cursor.execute('''
                    SELECT COUNT(*) FROM trades t
                    WHERE t.status = 'active'
                ''')
                
            total_trades = cursor.fetchone()[0]
            total_pages = (total_trades + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
            
            if page < 0:
                page = 0
            elif page >= total_pages and total_pages > 0:
                page = total_pages - 1
            
            offset = page * ITEMS_PER_PAGE
            
            # Get active trades (limit to 10 per page, excluding user's own)
            if twitch_username:
                cursor.execute('''
                    SELECT t.id, t.creator_username, t.offered_fish_id, t.offered_coins, 
                           t.requested_fish_id, t.requested_coins, t.created_at
                    FROM trades t
                    WHERE t.status = 'active' AND t.creator_username != ?
                    ORDER BY t.created_at DESC
                    LIMIT ? OFFSET ?
                ''', (twitch_username, ITEMS_PER_PAGE, offset))
            else:
                cursor.execute('''
                    SELECT t.id, t.creator_username, t.offered_fish_id, t.offered_coins, 
                           t.requested_fish_id, t.requested_coins, t.created_at
                    FROM trades t
                    WHERE t.status = 'active'
                    ORDER BY t.created_at DESC
                    LIMIT ? OFFSET ?
                ''', (ITEMS_PER_PAGE, offset))
                
            trades = cursor.fetchall()
            conn.close()
            
            if not trades:
                message_text = "📭 Нет активных предложений обмена."
                keyboard = types.InlineKeyboardMarkup()
                create_button = types.InlineKeyboardButton(
                    text="📝 Создать обмен",
                    callback_data="trade_create"
                )
                keyboard.add(create_button)
                
                back_button = types.InlineKeyboardButton(
                    text="🔙 Назад в меню",
                    callback_data="trade_menu"
                )
                keyboard.add(back_button)
            else:
                message_text = f"💱 <b>Активные предложения обмена:</b> (Страница {page+1}/{total_pages})\n\n"
                
                keyboard = types.InlineKeyboardMarkup()
                
                for trade in trades:
                    trade_id = trade[0]
                    creator = trade[1]
                    offered_fish_id = trade[2]  # ID из таблицы inventory
                    offered_coins = trade[3]
                    requested_fish_id = trade[4]  # ID из таблицы items
                    requested_coins = trade[5]
                    
                    # Format trade details
                    trade_text = f"<b>Обмен #{trade_id}</b> от {creator}\n"
                    
                    # Offered items
                    trade_text += "Отдает: "
                    if offered_fish_id:
                        # Get fish name from inventory
                        conn = sqlite3.connect(self.db_path)
                        cursor = conn.cursor()
                        cursor.execute('''
                            SELECT i.item_name FROM inventory i 
                            WHERE i.id = ?
                        ''', (offered_fish_id,))
                        fish_result = cursor.fetchone()
                        conn.close()
                        if fish_result:
                            trade_text += f"🐟 {fish_result[0]} "
                    
                    if offered_coins > 0:
                        trade_text += f"💰 {offered_coins} LC "
                    
                    trade_text += "\n"
                    
                    # Requested items
                    trade_text += "Просит: "
                    if requested_fish_id:
                        # Get fish name from items
                        conn = sqlite3.connect(self.db_path)
                        cursor = conn.cursor()
                        cursor.execute('''
                            SELECT i.name FROM items i 
                            WHERE i.id = ?
                        ''', (requested_fish_id,))
                        fish_result = cursor.fetchone()
                        conn.close()
                        if fish_result:
                            trade_text += f"🐟 {fish_result[0]} "
                    
                    if requested_coins > 0:
                        trade_text += f"💰 {requested_coins} LC "
                    
                    trade_text += "\n________\n"
                    message_text += trade_text
                    
                    # Add button to respond to this trade
                    respond_button = types.InlineKeyboardButton(
                        text=f"Ответить на обмен #{trade_id}",
                        callback_data=f"trade_respond:{trade_id}"
                    )
                    keyboard.add(respond_button)
                
                # Add pagination buttons
                nav_buttons = []
                if page > 0:
                    nav_buttons.append(types.InlineKeyboardButton(
                        text="⬅️ Назад", 
                        callback_data=f"trade_view_active_page:{page-1}"
                    ))
                
                if page < total_pages - 1:
                    nav_buttons.append(types.InlineKeyboardButton(
                        text="Вперёд ➡️", 
                        callback_data=f"trade_view_active_page:{page+1}"
                    ))
                
                if nav_buttons:
                    keyboard.add(*nav_buttons)
                
                back_button = types.InlineKeyboardButton(
                    text="🔙 Назад в меню",
                    callback_data="trade_menu"
                )
                keyboard.add(back_button)
            
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
                    sent_message = self.bot.send_message(
                        chat_id, 
                        message_text, 
                        reply_markup=keyboard,
                        parse_mode='HTML'
                    )
                    self.user_messages[chat_id] = sent_message.message_id
            except:
                sent_message = self.bot.send_message(
                    chat_id, 
                    message_text,
                    reply_markup=keyboard,
                    parse_mode='HTML'
                )
                self.user_messages[chat_id] = sent_message.message_id
        
        def view_my_trades(self, chat_id, page=0):
            """Show user's own trades with pagination"""
            user_data = self.get_telegram_user(chat_id)
            twitch_username = user_data[2] if user_data else None
            
            if not twitch_username:
                return
            
            ITEMS_PER_PAGE = 10
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get total count of user's trades
            cursor.execute('''
                SELECT COUNT(*) FROM trades t
                WHERE t.creator_username = ?
            ''', (twitch_username,))
                
            total_trades = cursor.fetchone()[0]
            total_pages = (total_trades + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
            
            if page < 0:
                page = 0
            elif page >= total_pages and total_pages > 0:
                page = total_pages - 1
            
            offset = page * ITEMS_PER_PAGE
            
            # Get user's trades (limit to 10 per page)
            cursor.execute('''
                SELECT t.id, t.offered_fish_id, t.offered_coins, 
                       t.requested_fish_id, t.requested_coins, t.status, t.created_at
                FROM trades t
                WHERE t.creator_username = ?
                ORDER BY t.created_at DESC
                LIMIT ? OFFSET ?
            ''', (twitch_username, ITEMS_PER_PAGE, offset))
            
            trades = cursor.fetchall()
            conn.close()
            
            if not trades:
                message_text = "📭 У вас нет активных предложений обмена."
                keyboard = types.InlineKeyboardMarkup()
                create_button = types.InlineKeyboardButton(
                    text="📝 Создать обмен",
                    callback_data="trade_create"
                )
                keyboard.add(create_button)
                
                back_button = types.InlineKeyboardButton(
                    text="🔙 Назад в меню",
                    callback_data="trade_menu"
                )
                keyboard.add(back_button)
            else:
                message_text = f"📦 <b>Ваши предложения обмена:</b> (Страница {page+1}/{total_pages})\n\n"
                
                keyboard = types.InlineKeyboardMarkup()
                
                for trade in trades:
                    trade_id = trade[0]
                    offered_fish_id = trade[1]  # ID из таблицы inventory
                    offered_coins = trade[2]
                    requested_fish_id = trade[3]  # ID из таблицы items
                    requested_coins = trade[4]
                    status = trade[5]
                    
                    # Format trade details
                    status_text = {
                        'active': 'Активен',
                        'completed': 'Завершен',
                        'cancelled': 'Отменен'
                    }.get(status, status)
                    
                    trade_text = f"<b>Обмен #{trade_id}</b> ({status_text})\n"
                    
                    # Offered items
                    trade_text += "Вы отдаете: "
                    if offered_fish_id:
                        # Get fish name from inventory
                        conn = sqlite3.connect(self.db_path)
                        cursor = conn.cursor()
                        cursor.execute('''
                            SELECT i.item_name FROM inventory i 
                            WHERE i.id = ?
                        ''', (offered_fish_id,))
                        fish_result = cursor.fetchone()
                        conn.close()
                        if fish_result:
                            trade_text += f"🐟 {fish_result[0]} "
                    
                    if offered_coins > 0:
                        trade_text += f"💰 {offered_coins} LC "
                    
                    trade_text += "\n"
                    
                    # Requested items
                    trade_text += "Вы просите: "
                    if requested_fish_id:
                        # Get fish name from items
                        conn = sqlite3.connect(self.db_path)
                        cursor = conn.cursor()
                        cursor.execute('''
                            SELECT i.name FROM items i 
                            WHERE i.id = ?
                        ''', (requested_fish_id,))
                        fish_result = cursor.fetchone()
                        conn.close()
                        if fish_result:
                            trade_text += f"🐟 {fish_result[0]} "
                    
                    if requested_coins > 0:
                        trade_text += f"💰 {requested_coins} LC "
                    
                    trade_text += "\n________\n"
                    message_text += trade_text
                    
                    # Add details button for all trades
                    details_button = types.InlineKeyboardButton(
                        text=f"Детали обмена #{trade_id}",
                        callback_data=f"trade_details:{trade_id}"
                    )
                    keyboard.add(details_button)
                    
                    # Add cancel button only for active trades
                    if status == 'active':
                        cancel_button = types.InlineKeyboardButton(
                            text=f"Отменить обмен #{trade_id}",
                            callback_data=f"trade_cancel:{trade_id}"
                        )
                        keyboard.add(cancel_button)
                
                # Add pagination buttons
                nav_buttons = []
                if page > 0:
                    nav_buttons.append(types.InlineKeyboardButton(
                        text="⬅️ Назад", 
                        callback_data=f"trade_view_my_page:{page-1}"
                    ))
                
                if page < total_pages - 1:
                    nav_buttons.append(types.InlineKeyboardButton(
                        text="Вперёд ➡️", 
                        callback_data=f"trade_view_my_page:{page+1}"
                    ))
                
                if nav_buttons:
                    keyboard.add(*nav_buttons)
                
                back_button = types.InlineKeyboardButton(
                    text="🔙 Назад в меню",
                    callback_data="trade_menu"
                )
                keyboard.add(back_button)
            
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
                    sent_message = self.bot.send_message(
                        chat_id, 
                        message_text, 
                        reply_markup=keyboard,
                        parse_mode='HTML'
                    )
                    self.user_messages[chat_id] = sent_message.message_id
            except:
                sent_message = self.bot.send_message(
                    chat_id, 
                    message_text,
                    reply_markup=keyboard,
                    parse_mode='HTML'
                )
                self.user_messages[chat_id] = sent_message.message_id
        
        def show_respond_to_trade(self, chat_id, trade_id):
            """Show details for responding to a trade"""
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get trade details
            cursor.execute('''
                SELECT t.id, t.creator_username, t.offered_fish_id, t.offered_coins, 
                       t.requested_fish_id, t.requested_coins, t.created_at
                FROM trades t
                WHERE t.id = ? AND t.status = 'active'
            ''', (trade_id,))
            trade = cursor.fetchone()
            conn.close()
            
            if not trade:
                message_text = "❌ Обмен не найден или уже завершен."
                keyboard = types.InlineKeyboardMarkup()
                back_button = types.InlineKeyboardButton(
                    text="🔙 Назад к обменам",
                    callback_data="trade_view_active"
                )
                keyboard.add(back_button)
                
                try:
                    sent_message = self.bot.send_message(chat_id, message_text, reply_markup=keyboard)
                    self.user_messages[chat_id] = sent_message.message_id
                except:
                    pass
                return
            
            trade_id = trade[0]
            creator = trade[1]
            offered_fish_id = trade[2]  # ID из таблицы inventory
            offered_coins = trade[3]
            requested_fish_id = trade[4]  # ID из таблицы items
            requested_coins = trade[5]
            
            # Format trade details
            message_text = f"💱 <b>Обмен #{trade_id}</b>\n"
            message_text += f"Создатель: {creator}\n\n"
            
            # Offered items (what you can get)
            message_text += "Вы можете получить:\n"
            if offered_fish_id:
                # Get fish name from inventory
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT i.item_name FROM inventory i 
                    WHERE i.id = ?
                ''', (offered_fish_id,))
                fish_result = cursor.fetchone()
                conn.close()
                if fish_result:
                    message_text += f"🐟 {fish_result[0]}\n"
            
            if offered_coins > 0:
                message_text += f"💰 {offered_coins} LC\n"
            
            message_text += "\nВ обмен вы должны предоставить:\n"
            if requested_fish_id:
                # Get fish name from items
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT i.name FROM items i 
                    WHERE i.id = ?
                ''', (requested_fish_id,))
                fish_result = cursor.fetchone()
                conn.close()
                if fish_result:
                    message_text += f"🐟 {fish_result[0]}\n"
            
            if requested_coins > 0:
                message_text += f"💰 {requested_coins} LC\n"
            
            keyboard = types.InlineKeyboardMarkup()
            
            # Accept trade button
            accept_button = types.InlineKeyboardButton(
                text="✅ Принять обмен",
                callback_data=f"trade_accept:{trade_id}"
            )
            keyboard.add(accept_button)
            
            # Back button
            back_button = types.InlineKeyboardButton(
                text="🔙 Назад к обменам",
                callback_data="trade_view_active"
            )
            keyboard.add(back_button)
            
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
                    sent_message = self.bot.send_message(
                        chat_id, 
                        message_text, 
                        reply_markup=keyboard,
                        parse_mode='HTML'
                    )
                    self.user_messages[chat_id] = sent_message.message_id
            except:
                sent_message = self.bot.send_message(
                    chat_id, 
                    message_text,
                    reply_markup=keyboard,
                    parse_mode='HTML'
                )
                self.user_messages[chat_id] = sent_message.message_id
        
        def accept_trade(self, chat_id, trade_id):
            """Accept a trade offer"""
            user_data = self.get_telegram_user(chat_id)
            responder_username = user_data[2] if user_data else None
            
            if not responder_username:
                return
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            try:
                # Get trade details
                cursor.execute('''
                    SELECT creator_username, offered_fish_id, offered_coins, 
                           requested_fish_id, requested_coins
                    FROM trades 
                    WHERE id = ? AND status = 'active'
                ''', (trade_id,))
                trade = cursor.fetchone()
                
                if not trade:
                    message_text = "❌ Обмен не найден или уже завершен."
                    keyboard = types.InlineKeyboardMarkup()
                    back_button = types.InlineKeyboardButton(
                        text="🔙 Назад к обменам",
                        callback_data="trade_view_active"
                    )
                    keyboard.add(back_button)
                    
                    try:
                        sent_message = self.bot.send_message(chat_id, message_text, reply_markup=keyboard)
                        self.user_messages[chat_id] = sent_message.message_id
                    except:
                        pass
                    conn.close()
                    return
                
                creator_username = trade[0]
                offered_fish_id = trade[1]  # ID из таблицы inventory
                offered_coins = trade[2]
                requested_fish_id = trade[3]  # ID из таблицы items
                requested_coins = trade[4]
                
                # Check if responder has what's requested (рыба из таблицы items)
                if requested_fish_id:
                    # Для проверки нужно найти такую же рыбу в инвентаре пользователя
                    cursor.execute('''
                        SELECT i.id FROM inventory i
                        JOIN items it ON i.item_id = it.id
                        WHERE i.username = ? AND it.id = ?
                        LIMIT 1
                    ''', (responder_username, requested_fish_id))
                    if not cursor.fetchone():
                        message_text = "❌ У вас нет рыбы, которую запрашивает создатель обмена."
                        keyboard = types.InlineKeyboardMarkup()
                        back_button = types.InlineKeyboardButton(
                            text="🔙 Назад к обменам",
                            callback_data="trade_view_active"
                        )
                        keyboard.add(back_button)
                        
                        try:
                            sent_message = self.bot.send_message(chat_id, message_text, reply_markup=keyboard)
                            self.user_messages[chat_id] = sent_message.message_id
                        except:
                            pass
                        conn.close()
                        return
                
                if requested_coins > 0:
                    cursor.execute('''
                        SELECT balance FROM players WHERE username = ?
                    ''', (responder_username,))
                    balance_result = cursor.fetchone()
                    if not balance_result or balance_result[0] < requested_coins:
                        message_text = f"❌ У вас недостаточно LC. Требуется {requested_coins} LC."
                        keyboard = types.InlineKeyboardMarkup()
                        back_button = types.InlineKeyboardButton(
                            text="🔙 Назад к обменам",
                            callback_data="trade_view_active"
                        )
                        keyboard.add(back_button)
                        
                        try:
                            sent_message = self.bot.send_message(chat_id, message_text, reply_markup=keyboard)
                            self.user_messages[chat_id] = sent_message.message_id
                        except:
                            pass
                        conn.close()
                        return
                
                # Check if creator still has what they're offering (рыба из таблицы inventory)
                if offered_fish_id:
                    cursor.execute('''
                        SELECT COUNT(*) FROM inventory 
                        WHERE id = ? AND username = ?
                    ''', (offered_fish_id, creator_username))
                    if cursor.fetchone()[0] == 0:
                        message_text = "❌ У создателя обмена больше нет рыбы, которую он предлагает."
                        keyboard = types.InlineKeyboardMarkup()
                        back_button = types.InlineKeyboardButton(
                            text="🔙 Назад к обменам",
                            callback_data="trade_view_active"
                        )
                        keyboard.add(back_button)
                        
                        try:
                            sent_message = self.bot.send_message(chat_id, message_text, reply_markup=keyboard)
                            self.user_messages[chat_id] = sent_message.message_id
                        except:
                            pass
                        conn.close()
                        return
                
                if offered_coins > 0:
                    cursor.execute('''
                        SELECT balance FROM players WHERE username = ?
                    ''', (creator_username,))
                    balance_result = cursor.fetchone()
                    if not balance_result or balance_result[0] < offered_coins:
                        message_text = "❌ У создателя обмена недостаточно LC."
                        keyboard = types.InlineKeyboardMarkup()
                        back_button = types.InlineKeyboardButton(
                            text="🔙 Назад к обменам",
                            callback_data="trade_view_active"
                        )
                        keyboard.add(back_button)
                        
                        try:
                            sent_message = self.bot.send_message(chat_id, message_text, reply_markup=keyboard)
                            self.user_messages[chat_id] = sent_message.message_id
                        except:
                            pass
                        conn.close()
                        return
                
                # Perform the trade
                # 1. Transfer offered fish to responder (из inventory creator'а в inventory responder'а)
                if offered_fish_id:
                    cursor.execute('''
                        UPDATE inventory 
                        SET username = ? 
                        WHERE id = ?
                    ''', (responder_username, offered_fish_id))
                
                # 2. Transfer requested fish to creator (из inventory responder'а в inventory creator'а)
                if requested_fish_id:
                    # Нужно найти конкретную рыбу в инвентаре пользователя
                    cursor.execute('''
                        SELECT i.id FROM inventory i
                        JOIN items it ON i.item_id = it.id
                        WHERE i.username = ? AND it.id = ?
                        LIMIT 1
                    ''', (responder_username, requested_fish_id))
                    requested_fish_inventory_id = cursor.fetchone()
                    if requested_fish_inventory_id:
                        cursor.execute('''
                            UPDATE inventory 
                            SET username = ? 
                            WHERE id = ?
                        ''', (creator_username, requested_fish_inventory_id[0]))
                
                # 3. Transfer coins
                if offered_coins > 0:
                    cursor.execute('''
                        UPDATE players 
                        SET balance = balance - ? 
                        WHERE username = ?
                    ''', (offered_coins, creator_username))
                    
                    cursor.execute('''
                        UPDATE players 
                        SET balance = balance + ? 
                        WHERE username = ?
                    ''', (offered_coins, responder_username))
                
                if requested_coins > 0:
                    cursor.execute('''
                        UPDATE players 
                        SET balance = balance - ? 
                        WHERE username = ?
                    ''', (requested_coins, responder_username))
                    
                    cursor.execute('''
                        UPDATE players 
                        SET balance = balance + ? 
                        WHERE username = ?
                    ''', (requested_coins, creator_username))
                
                # 4. Mark trade as completed
                cursor.execute('''
                    UPDATE trades 
                    SET status = 'completed', responder_username = ?, completed_at = ?
                    WHERE id = ?
                ''', (responder_username, datetime.now(), trade_id))
                
                conn.commit()
                
                # Send success messages
                message_text = "✅ Обмен успешно завершен!\n\n"
                message_text += f"Обмен #{trade_id} между {creator_username} и {responder_username} завершен."
                
                keyboard = types.InlineKeyboardMarkup()
                back_button = types.InlineKeyboardButton(
                    text="🔙 Назад к обменам",
                    callback_data="trade_view_active"
                )
                keyboard.add(back_button)
                
                try:
                    sent_message = self.bot.send_message(chat_id, message_text, reply_markup=keyboard)
                    self.user_messages[chat_id] = sent_message.message_id
                except:
                    pass
                
                # Try to notify the creator
                try:
                    creator_chat_id = None
                    cursor.execute('''
                        SELECT chat_id FROM telegram_users WHERE twitch_username = ?
                    ''', (creator_username,))
                    creator_result = cursor.fetchone()
                    if creator_result:
                        creator_chat_id = creator_result[0]
                        if creator_chat_id in self.user_messages:
                            self.bot.edit_message_text(
                                chat_id=creator_chat_id,
                                message_id=self.user_messages[creator_chat_id],
                                text=f"✅ Ваш обмен #{trade_id} был принят пользователем {responder_username}!"
                            )
                        else:
                            self.bot.send_message(
                                creator_chat_id,
                                f"✅ Ваш обмен #{trade_id} был принят пользователем {responder_username}!"
                            )
                except Exception as e:
                    logger.error(f"Failed to notify trade creator: {e}")
                    
            except sqlite3.Error as e:
                message_text = f"❌ Ошибка при выполнении обмена: {str(e)}"
                logger.error(f"Database error accepting trade: {e}")
                
                keyboard = types.InlineKeyboardMarkup()
                back_button = types.InlineKeyboardButton(
                    text="🔙 Назад к обменам",
                    callback_data="trade_view_active"
                )
                keyboard.add(back_button)
                
                try:
                    sent_message = self.bot.send_message(chat_id, message_text, reply_markup=keyboard)
                    self.user_messages[chat_id] = sent_message.message_id
                except:
                    pass
            finally:
                conn.close()
        
        def cancel_trade(self, chat_id, trade_id):
            """Cancel a trade offer"""
            user_data = self.get_telegram_user(chat_id)
            username = user_data[2] if user_data else None
            
            if not username:
                return
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            try:
                # Check if trade exists and belongs to user
                cursor.execute('''
                    SELECT COUNT(*) FROM trades 
                    WHERE id = ? AND creator_username = ? AND status = 'active'
                ''', (trade_id, username))
                
                if cursor.fetchone()[0] == 0:
                    message_text = "❌ Обмен не найден или не принадлежит вам."
                else:
                    # Cancel the trade
                    cursor.execute('''
                        UPDATE trades 
                        SET status = 'cancelled', completed_at = ?
                        WHERE id = ?
                    ''', (datetime.now(), trade_id))
                    
                    conn.commit()
                    message_text = f"✅ Обмен #{trade_id} успешно отменен."
                    
            except sqlite3.Error as e:
                message_text = f"❌ Ошибка при отмене обмена: {str(e)}"
                logger.error(f"Database error cancelling trade: {e}")
            finally:
                conn.close()
            
            keyboard = types.InlineKeyboardMarkup()
            back_button = types.InlineKeyboardButton(
                text="🔙 Назад к обменам",
                callback_data="trade_view_my"
            )
            keyboard.add(back_button)
            
            try:
                sent_message = self.bot.send_message(chat_id, message_text, reply_markup=keyboard)
                self.user_messages[chat_id] = sent_message.message_id
            except:
                pass
        
        def show_trade_details(self, chat_id, trade_id):
            """Show detailed information about a trade"""
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get trade details
            cursor.execute('''
                SELECT t.id, t.creator_username, t.offered_fish_id, t.offered_coins, 
                       t.requested_fish_id, t.requested_coins, t.status, t.created_at, 
                       t.completed_at, t.responder_username
                FROM trades t
                WHERE t.id = ?
            ''', (trade_id,))
            trade = cursor.fetchone()
            conn.close()
            
            if not trade:
                message_text = "❌ Обмен не найден."
                keyboard = types.InlineKeyboardMarkup()
                back_button = types.InlineKeyboardButton(
                    text="🔙 Назад в меню",
                    callback_data="trade_menu"
                )
                keyboard.add(back_button)
                
                try:
                    sent_message = self.bot.send_message(chat_id, message_text, reply_markup=keyboard)
                    self.user_messages[chat_id] = sent_message.message_id
                except:
                    pass
                return
            
            trade_id = trade[0]
            creator = trade[1]
            offered_fish_id = trade[2]  # ID из таблицы inventory
            offered_coins = trade[3]
            requested_fish_id = trade[4]  # ID из таблицы items
            requested_coins = trade[5]
            status = trade[6]
            created_at = trade[7]
            completed_at = trade[8]
            responder = trade[9]
            
            # Format trade details
            status_text = {
                'active': 'Активен',
                'completed': 'Завершен',
                'cancelled': 'Отменен'
            }.get(status, status)
            
            message_text = f"💱 <b>Детали обмена #{trade_id}</b>\n"
            message_text += f"Статус: {status_text}\n"
            message_text += f"Создатель: {creator}\n"
            if responder:
                message_text += f"Участник: {responder}\n"
            message_text += f"Создан: {created_at}\n"
            if completed_at:
                message_text += f"Завершен: {completed_at}\n"
            message_text += "\n"
            
            # Offered items
            message_text += "Предлагается:\n"
            if offered_fish_id:
                # Get fish name from inventory
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT i.item_name FROM inventory i 
                    WHERE i.id = ?
                ''', (offered_fish_id,))
                fish_result = cursor.fetchone()
                conn.close()
                if fish_result:
                    message_text += f"🐟 {fish_result[0]}\n"
            
            if offered_coins > 0:
                message_text += f"💰 {offered_coins} LC\n"
            
            message_text += "\nЗапрашивается:\n"
            if requested_fish_id:
                # Get fish name from items
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT i.name FROM items i 
                    WHERE i.id = ?
                ''', (requested_fish_id,))
                fish_result = cursor.fetchone()
                conn.close()
                if fish_result:
                    message_text += f"🐟 {fish_result[0]}\n"
            
            if requested_coins > 0:
                message_text += f"💰 {requested_coins} LC\n"
            
            keyboard = types.InlineKeyboardMarkup()
            back_button = types.InlineKeyboardButton(
                text="🔙 Назад в меню",
                callback_data="trade_menu"
            )
            keyboard.add(back_button)
            
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
                    sent_message = self.bot.send_message(
                        chat_id, 
                        message_text, 
                        reply_markup=keyboard,
                        parse_mode='HTML'
                    )
                    self.user_messages[chat_id] = sent_message.message_id
            except:
                sent_message = self.bot.send_message(
                    chat_id, 
                    message_text,
                    reply_markup=keyboard,
                    parse_mode='HTML'
                )
                self.user_messages[chat_id] = sent_message.message_id
        
        # Добавляем методы в класс бота
        bot_class.trade_command = trade_command
        bot_class.show_trade_menu = show_trade_menu
        bot_class.create_trade_offer = create_trade_offer
        bot_class.show_user_offer_options = show_user_offer_options
        bot_class.handle_trade_callback = handle_trade_callback
        bot_class.show_user_request_options = show_user_request_options
        bot_class.ask_for_coin_amount = ask_for_coin_amount
        bot_class.handle_trade_message = handle_trade_message
        bot_class.confirm_trade_creation = confirm_trade_creation
        bot_class.view_active_trades = view_active_trades
        bot_class.view_my_trades = view_my_trades
        bot_class.show_respond_to_trade = show_respond_to_trade
        bot_class.accept_trade = accept_trade
        bot_class.cancel_trade = cancel_trade
        bot_class.show_trade_details = show_trade_details

# Инициализация системы обмена
trade_system = TradeSystem()