
import os
import logging
import subprocess
import psutil
import random
import json
import time
import asyncio
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass
import threading
from twitchio.ext import commands
from difflib import SequenceMatcher
from dotenv import load_dotenv
from tg_bot import start_telegram_bot
from twitch_link_handler import setup_twitch_link_handler
from pastes_manager import PastesManager
from tgw_past_def import handle_twitch_paste_command as pasta_comm
from upgrade_system import UpgradeSystem

upgrade=UpgradeSystem()
load_dotenv(".env")

# Initialize pastes manager
pastes_manager = PastesManager()

ECONOMY_ENABLED = True
TWITCH_TOKEN = os.getenv("TWITCH_TOKEN_TESTER")
TWITCH_MOD_TOKEN = os.getenv("TWITCH_TOKEN_LONELY")
TWITCH_CLIENT_ID = os.getenv("TWITCH_CLIENT_ID")
CHANNEL = "perolya"
SLOT_SYMBOLS = ["perolyGhoul", "perolyWok", "perolyAe"]
WHITENOTMODER = ["lonely_fr"]
PREDICTIONS_FILE = 'zodiac_predictions.json'
PREDICTIONS_LIST_FILE = 'predictions.json'
USED_PREDICTIONS_FILE = 'used_predictions.json'
ZODIAC_SIGNS = [
    "Овен", "Телец", "Близнецы", "Рак", 
    "Лев", "Дева", "Весы", "Скорпион", 
    "Стрелец", "Козерог", "Водолей", "Рыбы"
]

# File paths
SHOP_FILE = "shop_items.json"
STORIES_FILE = "stories.json"
MAGIC_FILE = "magic.json"
HELP_FILE = "help.json"

F_MODE = "limited"
F_ACTIVE = False
N_TASK = None
F_CD = {}
ITEMS_PER_PAGE = 4
COMMANDS_ENABLED = True  
load_dotenv(".env")

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

log_format = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
file_handler = logging.FileHandler("logger.log", encoding="utf-8")
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(log_format)

file_handler2 = logging.FileHandler("logchat.log", encoding="utf-8")
file_handler2.setLevel(logging.DEBUG)
file_handler2.setFormatter(log_format)

file_handler3 = logging.FileHandler("logcommand.log", encoding="utf-8")
file_handler3.setLevel(logging.ERROR)
file_handler3.setFormatter(log_format)

logger.addHandler(file_handler)
logger.addHandler(file_handler2)
logger.addHandler(file_handler3)

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s - %(message)s - %(asctime)s",
)

# Utility functions
def commands_enabled(func):
    """Decorator to check if commands are enabled before executing a command"""
    async def wrapper(ctx, *args, **kwargs):
        # Commands that should always work (even when disabled)
        always_enabled_commands = ['вкл', 'выкл', 'gt']
        
        # Check if command is in the always enabled list
        command_name = ctx.message.content.split()[0][1:]  # Get command name without '!'
        
        # If commands are disabled and this isn't an always-enabled command, block execution
        if not COMMANDS_ENABLED and command_name not in always_enabled_commands:
            return
            
        # If commands are enabled, or this is an always-enabled command, proceed
        return await func(ctx, *args, **kwargs)
    return wrapper

def load_data(file_path, default_value=None, convert_fn=None, logger=None):
    """
    Universal function to load data from JSON file
    :param file_path: path to file
    :param default_value: default value if file not found or parsing error
    :param convert_fn: function to convert data after loading
    :param logger: logger for recording errors (if needed)
    :return: loaded data or default_value
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return convert_fn(data) if convert_fn else data
    except (FileNotFoundError, json.JSONDecodeError) as e:
        if logger:
            logger.error(f"Error loading {file_path}: {e}")
        return default_value() if callable(default_value) else default_value

# Database class for optimized operations
class Database:
    def __init__(self, db_path: str = 'bot_database.db'):
        """Initialize the database connection"""
        self.db_path = db_path
        self.conn = None
        self._init_tables()
    
    def connect(self, db_path: str = None):
        """Connect database"""
        if db_path:
            self.db_path = db_path
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
    
    def close(self):
        """Close the database connection"""
        if self.conn:
            self.conn.close()
            
    def _init_tables(self):
        """Create tables if they don't exist"""
        self.connect()
        cursor = self.conn.cursor()
        
        # Players table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS players (
            username TEXT PRIMARY KEY,
            balance INTEGER DEFAULT 0,
            last_daily_reward INTEGER,
            is_banned INTEGER DEFAULT 0,
            is_ignored INTEGER DEFAULT 0,
            queue_position INTEGER,
            queue_number TEXT,
            queue_timestamp DATETIME,
            queue_passes INTEGER DEFAULT 0,
            fishing_pass_expiry INTEGER,
            last_fishing_time INTEGER,
            temp_ban_expiry INTEGER,
            last_played DATETIME,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # Inventory table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            item_type TEXT CHECK(item_type IN ('fish', 'item')),
            item_id INTEGER,
            item_name TEXT,
            rarity TEXT,
            value INTEGER,
            obtained_at DATETIME,
            metadata TEXT,
            FOREIGN KEY(username) REFERENCES players(username) ON DELETE CASCADE
        )
        ''')
        # TG table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS telegram_users (
        chat_id INTEGER PRIMARY KEY,
        link_code TEXT,
        twitch_username TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(twitch_username) REFERENCES players(username) ON DELETE SET NULL
        )
        ''')
        # Items table (fish, shop items)
        cursor.execute('''  
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY,
            name TEXT,
            type TEXT CHECK(type IN ('fish', 'item')),
            base_price INTEGER,
            rarity TEXT,
            is_unique INTEGER DEFAULT 0,
            is_caught INTEGER DEFAULT 0,
            description TEXT
        )
        ''')
        # Queue table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            number TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(username) REFERENCES players(username) ON DELETE CASCADE
        )
        ''')
        # Queue passes table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS queue_passes (
            username TEXT PRIMARY KEY,
            passes INTEGER DEFAULT 0,
            FOREIGN KEY(username) REFERENCES players(username) ON DELETE CASCADE
        )
        ''')
        
        # Pass cooldowns table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS pass_cooldowns (
            username TEXT PRIMARY KEY,
            last_used INTEGER,
            FOREIGN KEY(username) REFERENCES players(username) ON DELETE CASCADE
        )
        ''')
        # Bans table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS bans (
            username TEXT PRIMARY KEY,
            FOREIGN KEY(username) REFERENCES players(username) ON DELETE CASCADE
        )
        ''')
        # Ignored users table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS ignored_users (
            username TEXT PRIMARY KEY,
            FOREIGN KEY(username) REFERENCES players(username) ON DELETE CASCADE
        )
        ''')
        # Temporary bans table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS temp_bans (
            username TEXT PRIMARY KEY,
            expiry INTEGER,
            FOREIGN KEY(username) REFERENCES players(username) ON DELETE CASCADE
        )
        ''')
        # Cooldowns table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS cooldowns (
            username TEXT PRIMARY KEY,
            last_used INTEGER,
            FOREIGN KEY(username) REFERENCES players(username) ON DELETE CASCADE
        )
        ''')
        # Daily fish catches table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS daily_fish_catches (
            username TEXT,
            catch_date DATE,
            catch_count INTEGER,
            PRIMARY KEY (username, catch_date),
            FOREIGN KEY(username) REFERENCES players(username) ON DELETE CASCADE
        )
        ''')
        # Fishing bans table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS fishing_bans (
            username TEXT PRIMARY KEY,
            banned_by TEXT,
            ban_reason TEXT,
            ban_date DATETIME,
            FOREIGN KEY(username) REFERENCES players(username) ON DELETE CASCADE
        )
        ''')
        
        # Pass usage cooldowns table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS pass_cooldowns (
            username TEXT PRIMARY KEY,
            last_used INTEGER,
            FOREIGN KEY(username) REFERENCES players(username) ON DELETE CASCADE
        )
        ''')
        
        self.conn.commit()
        self.close()
    
    # Player methods
    def player_exists(self, username: str) -> bool:
        self.connect()
        cursor = self.conn.cursor()
        cursor.execute('SELECT 1 FROM players WHERE username = ?', (username.lower(),))
        answer = cursor.fetchone() is not None
        self.close()
        return answer
    
    def create_player(self, username: str) -> bool:
        self.connect()
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT OR IGNORE INTO players (username) 
                VALUES (?)
            ''', (username.lower(),))
            self.conn.commit()
            return cursor.rowcount > 0
        except sqlite3.Error:
            return False
        finally:
            self.close()
    
    def get_player(self, username: str) -> Optional[Dict]:
        self.connect()
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM players WHERE username = ?', (username.lower(),))
        row = cursor.fetchone()
        self.close()
        return dict(row) if row else None
    
    def update_player(self, username: str, **fields) -> bool:
        if not fields:
            return False
        self.connect()
        try:
            cursor = self.conn.cursor()
            set_clause = ', '.join(f"{k} = ?" for k in fields.keys())
            values = list(fields.values()) + [username.lower()]
            
            cursor.execute(f'''
                UPDATE players 
                SET {set_clause}
                WHERE username = ?
            ''', values)
            
            self.conn.commit()
            return cursor.rowcount > 0
        except sqlite3.Error:
            return False
        finally:
            self.close()
    
    # Economy methods
    def get_balance(self, username: str) -> int:
        self.connect()
        cursor = self.conn.cursor()
        cursor.execute('SELECT balance FROM players WHERE username = ?', (username.lower(),))
        row = cursor.fetchone()
        answer = row['balance'] if row else 0
        self.close()
        return answer
    
    def add_coins(self, username: str, amount: int) -> int:
        self.create_player(username)
        self.connect()
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE players 
            SET balance = balance + ? 
            WHERE username = ?
        ''', (amount, username.lower()))
        self.conn.commit()
        answer = self.get_balance(username)
        self.close()
        return answer
    
    def transfer_coins(self, from_user: str, to_user: str, amount: int) -> bool:
        if amount <= 0:
            return False
            
        self.create_player(from_user)
        self.create_player(to_user)
        self.connect()
        try:
            cursor = self.conn.cursor()
            cursor.execute('SELECT balance FROM players WHERE username = ?', (from_user.lower(),))
            from_balance = cursor.fetchone()['balance']
            
            if from_balance < amount:
                return False
            
            cursor.execute('''
                UPDATE players 
                SET balance = balance - ? 
                WHERE username = ?
            ''', (amount, from_user.lower()))
            
            cursor.execute('''
                UPDATE players 
                SET balance = balance + ? 
                WHERE username = ?
            ''', (amount, to_user.lower()))
            
            self.conn.commit()
            return True
        except sqlite3.Error:
            return False
        finally:
            self.close()
    
    # Inventory methods
    def add_to_inventory(self, username: str, item_data: Dict) -> bool:
        self.connect()
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT INTO inventory (
                    username, item_type, item_id, item_name, 
                    rarity, value, obtained_at, metadata
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                username.lower(),
                item_data.get('type', 'fish'),
                item_data.get('id'),
                item_data.get('name'),
                item_data.get('rarity', 'common'),
                item_data.get('price', 0),
                item_data.get('obtained_at', datetime.now().isoformat()),
                str(item_data.get('metadata', {}))
            ))
            self.conn.commit()
            return cursor.lastrowid is not None
        except sqlite3.Error:
            return False
        finally:
            self.close()
    
    def get_inventory(self, username: str, item_type: str = None) -> List[Dict]:
        self.connect()
        cursor = self.conn.cursor()
        
        if item_type:
            cursor.execute('''
                SELECT * FROM inventory 
                WHERE username = ? AND item_type = ?
                ORDER BY obtained_at DESC
            ''', (username.lower(), item_type))
        else:
            cursor.execute('''
                SELECT * FROM inventory 
                WHERE username = ? 
                ORDER BY obtained_at DESC
            ''', (username.lower(),))
        answer = [dict(row) for row in cursor.fetchall()]
        self.close()
        return answer
    
    def remove_from_inventory(self, username: str, item_id: int) -> Optional[Dict]:
        self.connect()
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT * FROM inventory 
            WHERE id = ? AND username = ?
        ''', (item_id, username.lower()))
        
        item = cursor.fetchone()
        if not item:
            return None
            
        cursor.execute('''
            DELETE FROM inventory 
            WHERE id = ? AND username = ?
        ''', (item_id, username.lower()))
        
        self.conn.commit()
        answer=dict(item)
        self.close()
        return answer
   
    
    def get_fish_catalog(self) -> List[Dict]:
        self.connect()
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM items WHERE type = "fish"')
        answer  = [dict(row) for row in cursor.fetchall()]
        self.close()
        return answer
    
    # Queue methods
    def add_to_queue(self, username: str, number: str) -> bool:
        self.connect()
        try:
            cursor = self.conn.cursor()
            # Remove if already in queue
            cursor.execute('DELETE FROM queue WHERE username = ?', (username.lower(),))
            # Add to queue with current timestamp
            cursor.execute('''
                INSERT INTO queue (username, number, timestamp)
                VALUES (?, ?, CURRENT_TIMESTAMP)
            ''', (username.lower(), number))
            self.conn.commit()
            
            return True
        except sqlite3.Error:
            return False
        finally:
            self.close()
    
    def remove_from_queue(self, username: str) -> bool:
        """Remove user from queue"""
        self.connect()
        try:
            cursor = self.conn.cursor()
            cursor.execute('DELETE FROM queue WHERE username = ?', (username.lower(),))
            self.conn.commit()
            return cursor.rowcount > 0
        except sqlite3.Error:
            return False
        finally:
            self.close()
    
    def _clean_expired_queue_entries(self):
        """Remove users who have been in queue for more than 8 hours"""
        self.connect()
        try:
            cursor = self.conn.cursor()
            # Remove expired entries (older than 8 hours)
            cursor.execute('''
                DELETE FROM queue 
                WHERE timestamp < datetime('now', '-8 hours')
            ''')
            
            if cursor.rowcount > 0:
                self.conn.commit()
                logging.info(f"Removed {cursor.rowcount} expired queue entries")
        except sqlite3.Error as e:
            logging.error(f"Error cleaning expired queue entries: {e}")
        finally:
            self.close()
    
    def get_queue(self) -> List[Dict]:
        # First, remove users who have been in queue for more than 8 hours
        self._clean_expired_queue_entries()
        self.connect()
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT username, number, timestamp 
            FROM queue 
            ORDER BY timestamp ASC
        ''')
        answer = [dict(row) for row in cursor.fetchall()]
        self.close()
        return answer
    
    def get_queue_position(self, username: str) -> Optional[int]:
        # Clean expired entries first
        self._clean_expired_queue_entries()
        
        queue = self.get_queue()
        for i, entry in enumerate(queue, 1):
            if entry['username'].lower() == username.lower():
                return i
        return None
    
    # Queue passes methods
    def add_queue_pass(self, username: str, passes: int = 1) -> bool:
        self.connect()
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO queue_passes (username, passes)
                VALUES (?, COALESCE((SELECT passes FROM queue_passes WHERE username = ?), 0) + ?)
            ''', (username.lower(), username.lower(), passes))
            self.conn.commit()
            return True
        except sqlite3.Error:
            return False
        finally:
            self.close()
    
    def get_queue_passes(self, username: str) -> int:
        self.connect()
        cursor = self.conn.cursor()
        cursor.execute('SELECT passes FROM queue_passes WHERE username = ?', (username.lower(),))
        row = cursor.fetchone()
        self.close()
        if row is not None:
            # Handle case where row might be a tuple or dict
            if isinstance(row, dict):
                return row.get('passes', 0)
            else:
                # If it's a tuple, get the first element
                return row[0] if len(row) > 0 else 0
        return 0
    
    # Economy methods
    def get_balance(self, username: str) -> int:
        self.connect()
        cursor = self.conn.cursor()
        cursor.execute('SELECT balance FROM players WHERE username = ?', (username.lower(),))
        row = cursor.fetchone()
        self.close()
        if row is not None:
            # Handle case where row might be a tuple or dict
            if isinstance(row, dict):
                return row.get('balance', 0)
            else:
                # If it's a tuple, get the first element
                return row[0] if len(row) > 0 else 0
        return 0
    
    # Administration methods
    def ban_player(self, username: str) -> bool:
        self.connect()
        try:
            cursor = self.conn.cursor()
            cursor.execute('INSERT OR IGNORE INTO bans VALUES (?)', (username.lower(),))
            self.conn.commit()
            return cursor.rowcount > 0
        except sqlite3.Error:
            return False
        finally:
            self.close()
    
    def unban_player(self, username: str) -> bool:
        self.connect()
        try:
            cursor = self.conn.cursor()
            cursor.execute('DELETE FROM bans WHERE username = ?', (username.lower(),))
            self.conn.commit()
            return cursor.rowcount > 0
        except sqlite3.Error:
            return False
        finally:
            self.close()
    
    def is_banned(self, username: str) -> bool:
        self.connect()
        cursor = self.conn.cursor()
        cursor.execute('SELECT 1 FROM bans WHERE username = ?', (username.lower(),))
        answer = cursor.fetchone() is not None
        self.close()
        return answer
    
    def ignore_player(self, username: str) -> bool:
        self.connect()
        try:
            cursor = self.conn.cursor()
            cursor.execute('INSERT OR IGNORE INTO ignored_users VALUES (?)', (username.lower(),))
            self.conn.commit()
            return cursor.rowcount > 0
        except sqlite3.Error:
            return False
        finally:
            self.close()
    
    def unignore_player(self, username: str) -> bool:
        self.connect()
        try:
            cursor = self.conn.cursor()
            cursor.execute('DELETE FROM ignored_users WHERE username = ?', (username.lower(),))
            self.conn.commit()
            return cursor.rowcount > 0
        except sqlite3.Error:
            return False
        finally:
            self.close()
    
    def is_ignored(self, username: str) -> bool:
        self.connect()
        cursor = self.conn.cursor()
        cursor.execute('SELECT 1 FROM ignored_users WHERE username = ?', (username.lower(),))
        answer = cursor.fetchone() is not None
        self.close()
        return answer
    
    # Temporary bans methods
    def add_temp_ban(self, username: str, duration: int) -> bool:
        expiry = int(time.time()) + duration
        self.connect()
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO temp_bans (username, expiry)
                VALUES (?, ?)
            ''', (username.lower(), expiry))
            self.conn.commit()
            return True
        except sqlite3.Error:
            return False
        finally:
            self.close()
    
    def remove_temp_ban(self, username: str) -> bool:
        self.connect()
        try:
            cursor = self.conn.cursor()
            cursor.execute('DELETE FROM temp_bans WHERE username = ?', (username.lower(),))
            self.conn.commit()
            return cursor.rowcount > 0
        except sqlite3.Error:
            return False
        finally:
            self.close()
    
    def get_cooldown_time(self, username: str) -> Optional[int]:
        self.connect()
        cursor = self.conn.cursor()
        cursor.execute('SELECT last_used FROM cooldowns WHERE username = ?', (username.lower(),))
        row = cursor.fetchone()
        if not row:
            self.close()
            return None
        # Handle case where row might be a tuple or dict
        if isinstance(row, dict):
            last_used = row.get('last_used')
        else:
            # If it's a tuple, get the first element
            last_used = row[0] if len(row) > 0 else None
        remaining = last_used - time.time() if last_used is not None else None
        self.close()
        return int(remaining) if remaining is not None and remaining > 0 else None
    
    def is_on_cooldown(self, username: str) -> bool:
        self.connect()
        cursor = self.conn.cursor()
        cursor.execute('SELECT last_used FROM cooldowns WHERE username = ?', (username.lower(),))
        row = cursor.fetchone()
        if not row:
            self.close()
            return False
        # Handle case where row might be a tuple or dict
        if isinstance(row, dict):
            last_used = row.get('last_used')
        else:
            # If it's a tuple, get the first element
            last_used = row[0] if len(row) > 0 else None
        answer = last_used > time.time() if last_used is not None else False
        self.close()
        return answer
    
    def is_temp_banned(self, username: str) -> bool:
        self.connect()
        cursor = self.conn.cursor()
        cursor.execute('SELECT expiry FROM temp_bans WHERE username = ?', (username.lower(),))
        row = cursor.fetchone()
        if not row:
            self.close()
            return False
        # Handle case where row might be a tuple or dict
        if isinstance(row, dict):
            expiry = row.get('expiry')
        else:
            # If it's a tuple, get the first element
            expiry = row[0] if len(row) > 0 else None
        answer = expiry > time.time() if expiry is not None else False
        self.close()
        return answer
    
    def get_temp_ban_time(self, username: str) -> Optional[int]:
        self.connect()
        cursor = self.conn.cursor()
        cursor.execute('SELECT expiry FROM temp_bans WHERE username = ?', (username.lower(),))
        row = cursor.fetchone()
        if not row:
            self.close()
            return None
        # Handle case where row might be a tuple or dict
        if isinstance(row, dict):
            expiry = row.get('expiry')
        else:
            # If it's a tuple, get the first element
            expiry = row[0] if len(row) > 0 else None
        remaining = expiry - time.time() if expiry is not None else None
        self.close()
        return int(remaining) if remaining is not None and remaining > 0 else None

        return max(0, int(remaining))
    
    # Cooldowns methods
    def set_cooldown(self, username: str, duration: int) -> bool:
        expiry = int(time.time()) + duration
        self.connect()
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO cooldowns (username, last_used)
                VALUES (?, ?)
            ''', (username.lower(), expiry))
            self.conn.commit()
            return True
        except sqlite3.Error:
            return False
        finally:
            self.close()
    
    def is_on_cooldown(self, username: str) -> bool:
        self.connect()
        cursor = self.conn.cursor()
        cursor.execute('SELECT last_used FROM cooldowns WHERE username = ?', (username.lower(),))
        row = cursor.fetchone()
        if not row:
            self.close()
            return False
        answer = row['last_used'] > time.time()
        self.close()
        return answer
    
    def get_cooldown_time(self, username: str) -> Optional[int]:
        self.connect()
        cursor = self.conn.cursor()
        cursor.execute('SELECT last_used FROM cooldowns WHERE username = ?', (username.lower(),))
        row = cursor.fetchone()
        if not row:
            self.close()
            return None
        remaining = row['last_used'] - time.time()
        self.close()
        return max(0, int(remaining))
    
    # Daily fish catches methods
    def record_fish_catch(self, username: str, catch_date: str = None, catch_count: int = 1) -> bool:
        if catch_date is None:
            catch_date = datetime.now().strftime('%Y-%m-%d')
        self.connect()
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO daily_fish_catches (username, catch_date, catch_count)
                VALUES (?, ?, COALESCE((SELECT catch_count FROM daily_fish_catches WHERE username = ? AND catch_date = ?), 0) + ?)
            ''', (username.lower(), catch_date, username.lower(), catch_date, catch_count))
            self.conn.commit()
            return True
        except sqlite3.Error:
            return False
        finally:
            self.close()
    
    # Queue pass methods
    def get_queue_passes(self, username: str) -> int:
        self.connect()
        cursor = self.conn.cursor()
        cursor.execute('SELECT passes FROM queue_passes WHERE username = ?', (username.lower(),))
        row = cursor.fetchone()
        answer = row['passes'] if row else 0
        self.close()
        return row['passes'] if row else 0
    
    # Pass cooldown methods
    def get_pass_cooldown(self, username: str) -> Optional[int]:
        """Get pass cooldown for a specific user"""
        self.connect()
        try:
            cursor = self.conn.cursor()
            cursor.execute('SELECT last_used FROM pass_cooldowns WHERE username = ?', (username.lower(),))
            row = cursor.fetchone()
            return row[0] if row else None
        except sqlite3.Error as e:
            logger.error(f"Error fetching pass cooldown: {e}")
            return None
        finally:
            self.close()
            
    def update_pass_cooldown(self, username: str, last_used: int) -> bool:
        """Update a pass cooldown for a user"""
        self.connect()
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO pass_cooldowns (username, last_used)
                VALUES (?, ?)
            ''', (username.lower(), last_used))
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            logger.error(f"Error updating pass cooldown: {e}")
            return False
        finally:
            self.close()
            
    def can_use_pass(self, username: str) -> bool:
        """Check if user can use a pass (8 hour cooldown)"""
        last_used = self.get_pass_cooldown(username)
        if not last_used:
            return True  # No cooldown record, can use pass
            
        # Check if 8 hours (28800 seconds) have passed
        current_time = int(time.time())
        return (current_time - last_used) >= 28800  # 8 hours in seconds
    
    # Administration methods
    def ban_user(self, username: str, duration: Optional[int] = None) -> bool:
        expiry = int(time.time()) + duration if duration else None
        self.connect()
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO bans (username, expiry)
                VALUES (?, ?)
            ''', (username.lower(), expiry))
            self.conn.commit()
            return True
        except sqlite3.Error:
            return False
        finally:
            self.close()
    
    def unban_user(self, username: str) -> bool:
        self.connect()
        try:
            cursor = self.conn.cursor()
            cursor.execute('DELETE FROM bans WHERE username = ?', (username.lower(),))
            self.conn.commit()
            return True
        except sqlite3.Error:
            return False
        finally:
            self.close()
    
    def is_banned(self, username: str) -> bool:
        self.connect()
        cursor = self.conn.cursor()
        cursor.execute('SELECT 1 FROM bans WHERE username = ?', (username.lower(),))
        answer = cursor.fetchone() is not None
        self.close()
        return answer
    
    # Fishing bans methods
    def add_fishing_ban(self, username: str, banned_by: str, ban_reason: str = "", ban_date: str = None) -> bool:
        if ban_date is None:
            ban_date = datetime.now().isoformat()
        self.connect()
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO fishing_bans (username, banned_by, ban_reason, ban_date)
                VALUES (?, ?, ?, ?)
            ''', (username.lower(), banned_by, ban_reason, ban_date))
            self.conn.commit()
            return True
        except sqlite3.Error:
            return False
        finally:
            self.close()
    
    def remove_fishing_ban(self, username: str) -> bool:
        self.connect()
        try:
            cursor = self.conn.cursor()
            cursor.execute('DELETE FROM fishing_bans WHERE username = ?', (username.lower(),))
            self.conn.commit()
            return cursor.rowcount > 0
        except sqlite3.Error:
            return False
        finally:
            self.close()
    
    def is_fishing_banned(self, username: str) -> bool:
        self.connect()
        cursor = self.conn.cursor()
        cursor.execute('SELECT 1 FROM fishing_bans WHERE username = ?', (username.lower(),))
        answer = cursor.fetchone() is not None
        self.close()
        return answer
    
    def get_fishing_ban(self, username: str) -> Optional[Dict]:
        self.connect()
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM fishing_bans WHERE username = ?', (username.lower(),))
        row = cursor.fetchone()
        answer = dict(row) if row else None
        self.close()
        return answer
    
    # Utility methods
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

# Bot configuration
DAILY_REWARD = 50

# Utility functions
def load_data(file_path, default_value=None, convert_fn=None, logger=None):
    """
    Universal function to load data from JSON file
    :param file_path: path to file
    :param default_value: default value if file not found or parsing error
    :param convert_fn: function to convert data after loading
    :param logger: logger for recording errors (if needed)
    :return: loaded data or default_value
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return convert_fn(data) if convert_fn else data
    except (FileNotFoundError, json.JSONDecodeError) as e:
        if logger:
            logger.error(f"Error loading {file_path}: {e}")
        return default_value() if callable(default_value) else default_value
    
def get_zodiac_prediction(zodiac_sign):
    # Загружаем данные
    predictions = load_predictions()
    used_predictions = load_used_predictions()
    today = datetime.now().strftime('%Y-%m-%d')
    
    # Если предсказание уже есть - возвращаем его
    if zodiac_sign in predictions and predictions[zodiac_sign]['date'] == today:
        return predictions[zodiac_sign]['prediction']
    
    # Загружаем все возможные предсказания
    with open(PREDICTIONS_LIST_FILE, 'r', encoding='utf-8') as f:
        all_predictions = json.load(f)
    
    # Проверяем, нужно ли обновить список использованных предсказаний
    if used_predictions.get('date') != today:
        used_predictions = {'date': today, 'used': []}
    
    # Доступные предсказания (исключаем уже использованные)
    available_predictions = [
        p for p in all_predictions 
        if p not in used_predictions['used']
    ]
    
    # Если все предсказания использованы - очищаем список
    if not available_predictions:
        available_predictions = all_predictions.copy()
        used_predictions['used'] = []
    
    # Выбираем случайное предсказание
    random.seed(f"{today}_{zodiac_sign}")
    prediction = random.choice(available_predictions)
    
    # Сохраняем данные
    full_prediction = f"{zodiac_sign}. {prediction}"
    predictions[zodiac_sign] = {
        'date': today,
        'prediction': full_prediction
    }
    used_predictions['used'].append(prediction)
    
    save_predictions(predictions)
    save_used_predictions(used_predictions)
    
    return full_prediction

def load_predictions():
    if os.path.exists(PREDICTIONS_FILE):
        with open(PREDICTIONS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def load_used_predictions():
    if os.path.exists(USED_PREDICTIONS_FILE):
        with open(USED_PREDICTIONS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {'date': '', 'used': []}

def save_predictions(predictions):
    with open(PREDICTIONS_FILE, 'w', encoding='utf-8') as f:
        json.dump(predictions, f, ensure_ascii=False, indent=2)

def save_used_predictions(used_predictions):
    with open(USED_PREDICTIONS_FILE, 'w', encoding='utf-8') as f:
        json.dump(used_predictions, f, ensure_ascii=False, indent=2)

# Initialize database
db = Database()

# Bot instances
botMOD = commands.Bot(
    token=TWITCH_MOD_TOKEN,
    prefix="!",
    initial_channels=[CHANNEL],
    heartbeat=20.0  # 设置心跳间隔
)
DUEL_OUTCOMES = load_data('duel_outcomes.json', {})

def load_data(file_path, default_value=None, convert_fn=None, logger=None):
    """
    Universal function to load data from JSON file
    :param file_path: path to file
    :param default_value: default value if file not found or parsing error
    :param convert_fn: function to convert data after loading
    :param logger: logger for recording errors (if needed)
    :return: loaded data or default_value
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return convert_fn(data) if convert_fn else data
    except (FileNotFoundError, json.JSONDecodeError) as e:
        if logger:
            logger.error(f"Error loading {file_path}: {e}")
        return default_value() if callable(default_value) else default_value

# New functions to enable/disable commands
async def enable_commands(ctx):
    """Enable most bot commands"""
    global COMMANDS_ENABLED
    
    if moder(ctx):
        COMMANDS_ENABLED = True
        await ctx.send(f"🟢 {ctx.author.name} включает команды бота")
        logger.info(f"Commands enabled by {ctx.author.name}")
    else:
        logger.info(f"Permission denied: {ctx.author.name} tried to enable commands")
        await ctx.send("❌ У вас нет прав для включения команд!")

async def disable_commands(ctx):
    """Disable most bot commands (queue and fishing)"""
    global COMMANDS_ENABLED
    
    if moder(ctx):
        COMMANDS_ENABLED = False
        await ctx.send(f"🔴 {ctx.author.name} выключает команды бота")
        logger.info(f"Commands disabled by {ctx.author.name}")
    else:
        logger.info(f"Permission denied: {ctx.author.name} tried to disable commands")
        await ctx.send("❌ У вас нет прав для выключения команд!")

async def just_ask(ctx):
    logger.error("Вызвано !мне только спросить")
    try:
        if ctx.message.content.split()[1] != "только" or ctx.message.content.split()[2] != "спросить":
            await ctx.send(f"❌ {ctx.author.name}, используйте: !мне только спросить")
            return
    except IndexError:
        await ctx.send(f"❌ {ctx.author.name}, используйте: !мне только спросить")
        return
    user = ctx.author.name.lower()
    current_time = time.time()
    
    # Check cooldown using database
    if db.is_on_cooldown(user):
        remaining = db.get_cooldown_time(user)
        if remaining and remaining > 0:
            minutes = remaining // 60
            seconds = remaining % 60
            await ctx.send(f"⏳ {ctx.author.name}, команда доступна через {minutes}м {seconds}с")
            return
    
    # Check temp ban using database
    if db.is_temp_banned(user):
        remaining = db.get_temp_ban_time(user)
        if remaining and remaining > 0:
            minutes = remaining // 60
            seconds = remaining % 60
            await ctx.send(f"🚫 {ctx.author.name}, бан очереди (осталось {minutes}м {seconds}с)")
            return
    
    queue = db.get_queue()
    queue_entry = next((p for p in queue if p['username'].lower() == user), None)
    if not queue_entry:
        await ctx.send(f"❌ Вас нет в очереди")
        return
    if random.random() < 0.01:
        # Move user to front of queue
        queue.remove(queue_entry)
        queue.insert(0, queue_entry)
        # Update queue in database
        for entry in queue:
            db.add_to_queue(entry['username'], entry['number'])
        # Set cooldown
        db.set_cooldown(user, 7200)  # 2 hours
        await ctx.send(f"🎉 {ctx.author.name}, вы стали ПЕРВЫМ в очереди!")
    else:
        # Add temp ban for 30 minutes
        db.add_temp_ban(user, 1800)
        # Remove from queue
        db.remove_from_queue(user)
        fails = load_data("queue_fail.json", {})
        fail = fails.get("fail", [])
        event_data = random.choice(fail)
        message = f"{event_data['emoji']} {ctx.author.name} {event_data['text']} Бан очереди на 30 минут!"
        await ctx.send(message)

async def check_ban(ctx):
    user = ctx.author.name.lower()
    current_time = time.time()
    
    # Check temp ban
    if db.is_temp_banned(user):
        remaining = db.get_temp_ban_time(user)
        if remaining and remaining > 0:
            minutes = remaining // 60
            seconds = remaining % 60
            await ctx.send(f"⏳ {ctx.author.name}, бан очереди (осталось {minutes}м {seconds}с)")
            return
    
    # Check permanent ban
    if db.is_banned(user):
        await ctx.send(f"🚫 {ctx.author.name}, вы заблокированы и не можете записаться в очередь!")
        return
    
    await ctx.send(f"ℹ️ {ctx.author.name}, у вас нет активного бана очереди")

async def check_cooldown_cmd(ctx):
    user = ctx.author.name.lower()
    
    # Check cooldown
    if db.is_on_cooldown(user):
        remaining = db.get_cooldown_time(user)
        if remaining and remaining > 0:
            minutes = remaining // 60
            seconds = remaining % 60
            await ctx.send(f"⏳ {ctx.author.name}, кулдаун команды (осталось {minutes}м {seconds}с)")
            return
    
    await ctx.send(f"✅ {ctx.author.name}, команда доступна")

async def add_fish_cmd(ctx):
    if not_moder(ctx):
        await ctx.send("❌ Эта команда доступна только модераторам!")
        return
    db.connect()
    try:
        parts = ctx.message.content.split()
        if len(parts) < 3:
            await ctx.send("❌ Формат: !добавить <редкость> <название рыбы>")
            return
        rarity = parts[1].lower()
        name = ' '.join(parts[2:])
        valid_rarities = ["common", "uncommon", "rare", "epic", "legendary", "immortal", "mythical", "arcane", "ultimate"]
        if rarity not in valid_rarities:
            await ctx.send(f"❌ Недопустимая редкость. Используйте: {', '.join(valid_rarities)}")
            return
        
        # Check if fish already exists in database
        cursor = db.conn.cursor()
        cursor.execute('SELECT 1 FROM items WHERE name = ? AND type = "fish"', (name,))
        if cursor.fetchone():
            await ctx.send(f"❌ Рыба с названием '{name}' уже существует!")
            return
            
        # Get max id and create new id
        cursor.execute('SELECT MAX(id) FROM items')
        max_id = cursor.fetchone()[0] or 0
        fish_id = max_id + 1
        
        price_ranges = {
            "common": (1, 3),
            "uncommon": (4, 10),
            "rare": (11, 25),
            "epic": (26, 50),
            "legendary": (51, 100),
            "immortal": (101, 500),
            "mythical": (501, 750),
            "arcane": (751, 999),
            "ultimate": (1000, 5000)
        }
        min_p, max_p = price_ranges[rarity]
        price = random.randint(min_p, max_p)
        
        # Insert fish into database
        cursor.execute('''
            INSERT INTO items (id, name, type, base_price, rarity)
            VALUES (?, ?, "fish", ?, ?)
        ''', (fish_id, name, price, rarity))
        db.conn.commit()
        
        await ctx.send(
            f"🎣 Добавлена новая рыба:"
            f"┌ Название: {name}"
            f"├ ID: {fish_id}"
            f"├ Редкость: {rarity}"
            f"└ Цена: {price} LC"
        )
        logger.info(f"Модератор {ctx.author.name} добавил рыбу: {{'id': {fish_id}, 'name': '{name}', 'base_price': {price}, 'rarity': '{rarity}'}}")
    except Exception as e:
        logger.error(f"Ошибка при добавлении рыбы: {str(e)}")
        await ctx.send("❌ Произошла ошибка. Проверьте формат команды.")
    finally:
        db.close()

async def transfer_passes(ctx, *args, **kwargs):
    """Передает пропуски другому игроку"""
    global ECONOMY_ENABLED
    if not ECONOMY_ENABLED:
        return
    try:
        args = ctx.message.content.split()
        if len(args) < 2 or args[1] in ["пропуск", "пустиего"] or args[0] in ["pass", "passes"]:
            await ctx.send("❌ Использование: !пропуск/!пустиего @ник (количество(автоматом 1))")
            return
        recipient = args[1].strip('@').lower()
        sender = ctx.author.name.lower()
        if sender == recipient:
            await ctx.send("❌ Нельзя передать пропуски самому себе")
            return
        passes_to_transfer=0
        try:
            if len(args) > 2:
                passes_to_transfer = int(args[2])
            else:
                passes_to_transfer = 1
        except ValueError:
            await ctx.send("❌ Количество пропусков должно быть числом")
            return
        if passes_to_transfer <= 0:
            await ctx.send("❌ Количество пропусков должно быть больше 0")
            return

        # Получаем количество пропусков у отправителя
        sender_passes = db.get_queue_passes(sender)
        
        if sender_passes < passes_to_transfer:
            await ctx.send(f"❌ У вас недостаточно пропусков. Доступно: {sender_passes}")
            return
        # Передаем пропуски
        db.add_queue_pass(sender, -passes_to_transfer)  # Уменьшаем у отправителя
        db.add_queue_pass(recipient, passes_to_transfer)  # Увеличиваем у получателя

        # Получаем обновленное количество пропусков
        new_sender_passes = db.get_queue_passes(sender)
        new_recipient_passes = db.get_queue_passes(recipient)

        await ctx.send(
            f"⏩ {ctx.author.name} передал {passes_to_transfer} пропуск(ов) "
            f"игроку {recipient}! У вас осталось: {new_sender_passes}"
        )
        
        logger.info(f"{sender} передал {passes_to_transfer} пропусков игроку {recipient}")

    except Exception as e:
        logger.error(f"Ошибка при передаче пропусков: {str(e)}")
        await ctx.send("❌ Произошла ошибка при передаче пропусков")

async def transfer_fish(ctx):
    """Передает рыбу другому игроку"""
    global ECONOMY_ENABLED
    if not ECONOMY_ENABLED:
        return

    try:
        args = ctx.message.content.split()
        if len(args) < 3:
            await ctx.send("❌ Использование: !лови @ник номер_рыбы")
            return

        recipient = args[1].strip('@').lower()
        sender = ctx.author.name.lower()

        if sender == recipient:
            await ctx.send("❌ Нельзя передать рыбу самому себе")
            return

        try:
            fish_index = int(args[2]) - 1  # Переводим в 0-based индекс
        except ValueError:
            await ctx.send("❌ Номер рыбы должен быть числом")
            return

        # Получаем инвентари обоих игроков
        sender_inventory = get_user_inventory(sender)
        recipient_inventory = get_user_inventory(recipient)

        # Проверяем существование рыбы
        if fish_index < 0 or fish_index >= len(sender_inventory):
            await ctx.send(f"❌ Нет рыбы с номером {fish_index + 1} в вашем инвентаре")
            return
        fish_to_transfer = sender_inventory[fish_index]
        removed_fish = remove_fish_from_inventory(sender, fish_index)
        if not removed_fish:
            await ctx.send("❌ Ошибка при передаче рыбы")
            return
        add_fish_to_inventory(recipient, fish_to_transfer)
        await ctx.send(
            f"🎣 {ctx.author.name} передал рыбу '{fish_to_transfer['name']}' "
            f"игроку {recipient}!"
        )
        logger.info(f"{sender} передал рыбу {fish_to_transfer['name']} (ID:{fish_to_transfer['id']}) игроку {recipient}")

    except Exception as e:
        logger.error(f"Ошибка при передаче рыбы: {str(e)}")
        await ctx.send("❌ Произошла ошибка при передаче рыбы")

async def show_other_inventory(ctx, username: str, page: int = 1):
    if not moder(ctx):
        await ctx.send("❌ Эта команда доступна только модераторам!")
        return
    global ECONOMY_ENABLED
    if not ECONOMY_ENABLED:
        return

    inventory = get_user_inventory(username.replace("@", "").strip())
    if not inventory:
        await ctx.send(f"❌ У пользователя {username} нет рыбы!")
        return
    PER_PAGE = 5
    total_pages = (len(inventory) + PER_PAGE - 1) // PER_PAGE
    page = max(1, min(page, total_pages))

    # Создаем сообщение
    header = f"🐟 Инвентарь {username} (стр. {page}/{total_pages}):"
    fish_list = []
    start_idx = (page - 1) * PER_PAGE
    end_idx = min(start_idx + PER_PAGE, len(inventory))

    for idx in range(start_idx, end_idx):
        fish = inventory[idx]
        fish_list.append(f" {idx+1}. {fish['name']} ({fish['rarity']}) - {fish['price']} LC||")

    message = [header] + fish_list

    if total_pages > 1 and page < total_pages:
        message.append(f"Используйте `!глядь {username} {page+1}` для следующей страницы")
    await ctx.send("\n".join(message))

# Словарь для хранения времени последнего использования команды
user_cooldowns = {}

async def horoscope(ctx, zodiac_sign=None):
    logger.error(f"Вызвано !гороскоп для {zodiac_sign} пользователем {ctx.author.name}")
    
    # Проверка прав пользователя (модератор или владелец)
    is_privileged = ctx.author.is_mod or ctx.author.is_broadcaster
    
    # Проверка кулдауна для обычных пользователей
    if not is_privileged:
        last_used = user_cooldowns.get(ctx.author.name)
        if last_used and (datetime.now() - last_used).total_seconds() < 7200:  # 2 часа = 7200 секунд
            logger.info(f"Horoscope command on cooldown for {ctx.author.name}")
            return  # Просто выходим без сообщения
    
    if not zodiac_sign:
        message = "❌ Укажите ваш знак зодиака, например: !гороскоп Овен"
        logger.info(f"Horoscope command triggered but failed: {message}")
        await ctx.send(message)
        return
    
    zodiac_sign = zodiac_sign.capitalize()
    
    if zodiac_sign not in ZODIAC_SIGNS:
        message = f"❌ '{zodiac_sign}' не является знаком зодиака!"
        logger.info(f"Horoscope command triggered but failed: {message}")
        await ctx.send(message)
        return
    
    try:
        prediction = get_zodiac_prediction(zodiac_sign)
        message = f"🔮 Гороскоп:\n{prediction}"
        logger.info(f"Horoscope command success: {message}")
        
        # Обновляем время последнего использования для обычных пользователей
        if not is_privileged:
            user_cooldowns[ctx.author.name] = datetime.now()
        
        await ctx.send(message)
    except Exception as e:
        message = f"❌ Произошла ошибка при получении гороскопа: {str(e)}"
        logger.error(f"Horoscope command error: {message}")
        await ctx.send(message)

# Словарь для хранения времени последнего использования команды дуэли
user_cooldowns_duel = {}

async def duel(ctx, target=None):
    logger.error(f"Вызвана дуэль: {ctx.author.name} vs {target}")
    
    chatters = ctx.channel.chatters
    available_targets = [chatter.name for chatter in chatters if chatter.name != ctx.author.name]
    
    if not target:
        if not available_targets:
            await ctx.send("❌ Нет доступных противников")
            return
        target = random.choice(available_targets)
    else:
        target = target.lstrip('@')
        
    is_privileged = ctx.author.is_mod or ctx.author.is_broadcaster
    
    # Проверка кулдауна для обычных пользователей
    if not is_privileged:
        last_used = user_cooldowns_duel.get(ctx.author.name)
        if last_used and (datetime.now() - last_used).total_seconds() < 600:  # 5 мин = 300
            return  # Просто выходим без сообщения
    outcome_type = random.choices(
        ['initiator_failed', 'target_failed', 'initiator_won', 'target_won', 'both_lost'],
        weights=[0.2, 0.2, 0.2, 0.2, 0.2]
    )[0]
    
    outcome = random.choice(DUEL_OUTCOMES[outcome_type]).format(
        initiator=ctx.author.name,
        target=target
    )
    
    await ctx.send(f"⚔️ Дуэль {ctx.author.name} vs {target}: {outcome}")
    logger.info(f"Duel: {ctx.author.name} vs {target} - {outcome_type}")

# Define DUEL_OUTCOMES after load_data is defined
DUEL_OUTCOMES = load_data('duel_outcomes.json', {})


def similarity_ratio(text1, text2):
    return SequenceMatcher(None, text1, text2).ratio() * 100  # Percentage match

def get_time_remaining(username):
    player = db.get_player(username.lower())
    if not player or not player.get('last_played'):
        return None
    
    last_played_str = player['last_played']
    try:
        last_played = datetime.fromisoformat(last_played_str)
    except ValueError:
        return None
        
    time_passed = datetime.now() - last_played
    time_remaining = timedelta(hours=6) - time_passed
    if time_remaining.total_seconds() <= 0:
        return None
    hours, remainder = divmod(time_remaining.seconds, 3600)
    minutes = remainder // 60
    return f"{hours}ч {minutes}м"

def not_moder(ctx):
    if not (ctx.author.is_mod or ctx.author.name == ctx.channel.name or ctx.author.name.lower() in WHITENOTMODER):
        return True
    else:
        return False

def moder(ctx):
    if (ctx.author.is_mod or ctx.author.name == ctx.channel.name or ctx.author.name.lower() in WHITENOTMODER):
        return True
    else:
        return False

# Bot command handlers
async def transfer_coins(ctx):
    if not ECONOMY_ENABLED:
        return
    try:
        args = ctx.message.content.split()
        if len(args) > 2:
            recipient = args[1].strip('@').lower()
            amount = int(args[2])
            sender = ctx.author.name.lower()
            sender_balance = db.get_balance(sender)
            if sender == recipient:
                await ctx.send("❌ Нельзя перевести самому себе")
                return
            if sender_balance >= amount and amount > 0:
                success = db.transfer_coins(sender, recipient, amount)
                if success:
                    new_balance = db.get_balance(recipient)
                    await ctx.send(
                        f"💸 {ctx.author.name} перевел {amount} LC пользователю {recipient}. "
                        f"Новый баланс получателя: {new_balance} LC"
                    )
                    logger.info(f"{sender} перевел {amount} LC на {recipient}")
                else:
                    await ctx.send("❌ Ошибка перевода")
            else:
                await ctx.send("❌ Недостаточно средств или неверная сумма")
        else:
            await ctx.send("❌ Использование: !перевод @ник сумма")
    except ValueError:
        await ctx.send("❌ Укажите корректную сумму")

async def give_coins(ctx):
    if moder(ctx):
        try:
            args = ctx.message.content.split()
            if len(args) > 2:
                username = args[1].strip('@').lower()
                amount = int(args[2])
                new_balance = db.add_coins(username, amount)
                await ctx.send(f"🪙 {username} получил {amount} LC. Новый баланс: {new_balance} LC")
            else:
                await ctx.send("❌ Использование: !выдать @ник сумма")
        except ValueError:
            await ctx.send("❌ Укажите корректную сумму")

async def take_coins(ctx):
    if moder(ctx):
        try:
            args = ctx.message.content.split()
            if len(args) > 2:
                username = args[1].strip('@').lower()
                amount = int(args[2])
                balance = db.get_balance(username)
                if balance < amount:
                    amount = balance
                new_balance = db.add_coins(username, -amount)
                await ctx.send(f"🪙 С {username} снято {amount} LC. Новый баланс: {new_balance} LC")
            else:
                await ctx.send("❌ Использование: !снять @ник сумма")
        except ValueError:
            await ctx.send("❌ Укажите корректную сумму")

async def bring_item(ctx):
    if moder(ctx):
        items = [
            "Но она сказала, что вернётся через 5 минут... Прошло 3 часа.",
            "Но что-то опять сломалось и не получилось. У её лапки.",
            "Вот оно! ... Подожди, а где?",
            "Она ушла за мечтой, но вернулась с печенькой.",
        ]
        text = ctx.message.content.split(" ")
        if len(text) > 1:
            text.pop(0)
            text = " ".join(text)
        else:
            text = ", но забыл уточнить что нужно принести.",
        item = random.choice(items)
        await ctx.channel.send(f"🔹 {ctx.author.name} приказал @perolya принести {text}... {item}")
        logger.info(f"Command '!принеси' executed by {ctx.author.name}, item: {item}")
    else:
        logger.info(f"Command '!принеси' denied for {ctx.author.name} (not mod)")

async def random_choice(ctx):
    logger.error("Вызвано !кто")
    chatters = list(ctx.channel.chatters)
    if len(chatters) < 2:
        await ctx.send("❌ Недостаточно людей в чате!")
        return
    question = " ".join(ctx.message.content.split()[1:])
    chosen = random.choice([c.name for c in chatters if c.name != ctx.author.name])
    chat = " ".join([c.name for c in chatters])
    logger.debug(f"Список чата {chat}")
    if question:
        await ctx.send(f"Кто {question} ?? Это {chosen}!")
        logger.info(f"Random choice command triggered: {chosen} asked about {question}")
    else:
        await ctx.send(f"🎲 Случайный выбор: {chosen}")

async def lick_user(ctx):
    logger.error("Вызвано !лизнуть")
    chatters = ctx.channel.chatters
    if len(chatters) > 1:
        random_user = random.choice([chatter.name for chatter in chatters if chatter.name != ctx.author.name])
        message = f"🤪 {ctx.author.name} лизнул {random_user}!"
        logger.info(f"Lick command triggered: {message}")
        await ctx.send(message)
    else:
        message = "❌ Недостаточно людей в чате для лизания!"
        logger.info(f"Lick command triggered but failed: {message}")
        await ctx.send(message)

async def travel_story(ctx):
    logger.error("Вызвано !путешествие")
    stories = load_data(STORIES_FILE, {})
    story = f"{ctx.author.name} " + random.choice(stories.get("travel_stories", []))
    await ctx.channel.send(story)

async def magic_event(ctx):
    try:
        magics = load_data(MAGIC_FILE, {})
        magic_events = magics.get("magic_events", [])

        if not magic_events:
            await ctx.send("⚠️ Магия временно не работает... Попробуйте позже!")
            return

        event_data = random.choice(magic_events)
        message = f"{event_data['emoji']} {ctx.author.name} {event_data['text']}"

        await ctx.send(message)
        logger.info(f"Magic event: {message}")

    except Exception as e:
        logger.error(f"Magic command error: {str(e)}")
        await ctx.send("🔮 Произошла магическая ошибка! Волшебство временно недоступно.")

# Fishing system
async def fishing(ctx):
    global F_MODE, F_ACTIVE
    if not ECONOMY_ENABLED:
        return
    username = ctx.author.name.lower()
    current_time = time.time()
    now = datetime.now()
    if F_MODE == "limited":
        if not F_ACTIVE:
            now = datetime.now()
            next_window = (now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1))
            wait_time = (next_window - now).total_seconds()
            minutes = int(wait_time // 60)
            seconds = int(wait_time % 60)
            await ctx.send(
                f"⏳ Рыбалка закрыта! Следующее окно через {minutes}м {seconds}с"
            )
            return
    if username in F_CD:
        time_passed = time.time() - F_CD[username]
        if time_passed < 300:
            remaining = 300 - time_passed
            await ctx.send(f"⏳ Следующая попытка через {int(remaining//60)}м {int(remaining%60)}с")
            return
    fish_catalog = db.get_fish_catalog()
    fish_data = {"рыбы": fish_catalog}
    if F_MODE == "limited" and F_ACTIVE:
        rarity_weights = {
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
        reward_multipliers = {
            "common": 6.0,
            "uncommon": 5.5,
            "rare": 4.5,
            "epic": 3.0,
            "legendary": 2.0,
            "immortal": 1.7,
            "mythical": 1.5,
            "arcane": 1.4,
            "ultimate": 1.0
        }
    else:
        rarity_weights = {
            "common": 6000,
            "uncommon": 3000,
            "rare": 1500,
            "epic": 400,
            "legendary": 50,
            "immortal": 5,
            "mythical": 3,
            "arcane": 2,
            "ultimate": 1
        }
        reward_multipliers = {
            "common": 1.0,
            "uncommon": 1.0,
            "rare": 1.0,
            "epic": 1.0,
            "legendary": 1.0,
            "immortal": 1.0,
            "mythical": 1.0,
            "arcane": 1.0,
            "ultimate": 1.0
        }

    # Редкость рыбы и их веса для выбора
    FISH_RARITY_WEIGHTS = rarity_weights
    
    # Перевод названий редкости на русский язык
    RARITY_NAMES_RU = {
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
    # Валюта бота
    CURRENCY_NAME = "LC"  # Lonely Coins
    
    def get_fish_drop_chances():
        """Получить шансы выпадения рыбы по редкости"""
        rarity_info = FISH_RARITY_WEIGHTS
        total_weight = sum(rarity_info.values())
        chances = {}
        
        for rarity, weight in rarity_info.items():
            chance = (weight / total_weight) * 100
            chances[rarity] = {
                'weight': weight,
                'chance': chance
            }
        
        return chances
    # Use the exposed variables
    available_fish = [
        fish for fish in fish_data["рыбы"]
        if not (fish["rarity"] == "ultimate" and fish.get("is_caught", False))
    ]
    if not available_fish:
        await ctx.send("❌ В озере не осталось рыбы!")
        return
    
    # Get drop chances for better fish selection
    drop_chances = get_fish_drop_chances()
    
    # Create weighted pool using the exposed FISH_RARITY_WEIGHTS
    weighted_pool = []
    for fish in available_fish:
        weight = FISH_RARITY_WEIGHTS.get(fish["rarity"], 0)
        if weight > 0:
            weighted_pool.extend([fish] * weight)
    
    if not weighted_pool:
        await ctx.send("❌ Не удалось определить доступную рыбу")
        return
    
    caught_fish = random.choice(weighted_pool)
    
    # Use the exposed CURRENCY_NAME
    if caught_fish["rarity"] != "ultimate":
        caught_fish["base_price"] = int(caught_fish["base_price"] * reward_multipliers[caught_fish["rarity"]])
    if caught_fish["rarity"] == "ultimate":
        # Update fish as caught in database
        db.connect()
        cursor = db.conn.cursor()
        cursor.execute('UPDATE items SET is_caught = 1 WHERE id = ?', (caught_fish['id'],))
        db.conn.commit()
        db.close()
        
    caught_copy = caught_fish.copy()
    caught_copy["caught_at"] = int(current_time)
    caught_copy["mode"] = F_MODE  # Save the mode in which the fish was caught
    # Use base_price instead of price for database consistency
    caught_copy["price"] = caught_copy.get("base_price", 0)
    
    # Add to inventory
    item_data = {
        'type': caught_copy.get('type', 'fish'),
        'id': caught_copy.get('id'),
        'name': caught_copy.get('name'),
        'rarity': caught_copy.get('rarity', 'common'),
        'price': caught_copy.get('price', 0),
        'obtained_at': datetime.fromtimestamp(caught_copy.get('caught_at', time.time())).isoformat(),
        'metadata': str(caught_copy.get('metadata', {}))
    }
    db.add_to_inventory(username, item_data)
    
    # Record the catch
    db.record_fish_catch(username)
    
    F_CD[username] = current_time
    # Get Russian name for rarity
    rarity_ru = RARITY_NAMES_RU.get(caught_fish["rarity"], caught_fish["rarity"])
    
    await ctx.send(
        f"🎣 {ctx.author.name} поймал "
        f"{caught_fish['name']} ({rarity_ru})! +{caught_fish.get('base_price', 0)} {CURRENCY_NAME}"
    )

# Queue system
async def join_queue(ctx):
    logger.error("Вызвано !хочу")
    player_name = ctx.author.name
    player_name_lower = player_name.lower()
    args = ctx.message.content.split()
    db._clean_expired_queue_entries()
    
    # Check if player is temporarily banned
    if db.is_temp_banned(player_name_lower):
        time_remaining = db.get_temp_ban_time(player_name_lower)
        if time_remaining:
            minutes = time_remaining // 60
            seconds = time_remaining % 60
            await ctx.channel.send(f"🚫 {player_name}, вы забанены и не можете записаться в очередь! Осталось: {minutes}м {seconds}с")
            logger.info("banned player tried to join the queue")
            return
    
    # Check if player is permanently banned
    if db.is_banned(player_name_lower):
        await ctx.channel.send(f"❌ {player_name}, вы заблокированы и не можете записаться в очередь!")
        logger.info("banned player tried to join the queue")
        return
    
    if len(args) < 2 or not args[1].isdigit():
        message = random.choice([
            "Хоти дальше", "План хороший, но не работает",
            "Мечтать не вредно", "А я пиццы хочу и вертолёт",
            "Любые хотелки за ваши деньги", "А я котиков люблю ",
            "Вы уверены, что хотите поставиться в очередь? Подумайте"
        ])
        await ctx.channel.send(f"❌ {message}, {player_name}")
        return
    number = args[1]
    use_pass = len(args) > 2 and args[2].lower() == "пропуск"
    
    time_remaining = get_time_remaining(player_name)
    if time_remaining and not use_pass:
        await ctx.channel.send(
            f"⏳ {player_name}, вы уже играли сегодня! "
            f"Следующая попытка через {time_remaining} "
            f"Используйте `!хочу {number} пропуск` чтобы использовать пропуск"
        )
        logger.info(f"{player_name} tried to join queue during cooldown")
        return
    
    if use_pass:
        passes = db.get_queue_passes(player_name_lower)
        if passes <= 0:
            await ctx.channel.send(
                f"❌ {player_name}, у вас нет пропусков!"
                f"Доступно через: {time_remaining}"
            )
            logger.info(f"{player_name} tried to use pass but has none")
            return
        
        # Use one pass
        db.add_queue_pass(player_name_lower, -1)
        
        # Clear cooldown for player
        db.update_player(player_name_lower, last_played=None)
        
        # Add to front of queue
        db.add_to_queue(player_name, number)
        
        await ctx.channel.send(
            f"⏩ {player_name} использовал пропуск и теперь первый в очереди! "
            f"🎫 Осталось пропусков: {passes - 1}"
        )
        logger.info(f"{player_name} used pass to bypass cooldown")
        return
    
    # Check if player is already in queue
    queue_position = db.get_queue_position(player_name_lower)
    if queue_position is not None:
        # Remove from queue
        db.remove_from_queue(player_name_lower)
        await ctx.channel.send(f"❌ {player_name} удален из очереди!")
        logger.info(f"{player_name} removed from queue!")
    else:
        # Add to queue
        db.add_to_queue(player_name, number)
        # Get the actual position of the user in the queue
        position = db.get_queue_position(player_name_lower)
        await ctx.channel.send(f"✅ {player_name} добавлен в очередь, вы {position} в очереди!")
        logger.info(f"{player_name} added to queue with number {number}!")

# Inventory system
def get_user_inventory(username):
    # Using database instead of file
    inventory_items = db.get_inventory(username)
    # Convert database format to the old format for compatibility
    return [{
        'id': item['item_id'],
        'name': item['item_name'],
        'rarity': item['rarity'],
        'price': item['value'],
        'caught_at': int(datetime.fromisoformat(item['obtained_at']).timestamp()) if item['obtained_at'] else None,
        'type': item['item_type']
    } for item in inventory_items]

def add_fish_to_inventory(username, fish):
    # Using database instead of file
    item_data = {
        'type': fish.get('type', 'fish'),
        'id': fish.get('id'),
        'name': fish.get('name'),
        'rarity': fish.get('rarity', 'common'),
        'price': fish.get('price', 0),
        'caught_at': datetime.fromtimestamp(fish.get('caught_at', time.time())).isoformat() if fish.get('caught_at') else datetime.now().isoformat(),
        'metadata': str(fish.get('metadata', {}))
    }
    return db.add_to_inventory(username, item_data)

def remove_fish_from_inventory(username, fish_index):
    # Using database instead of file
    inventory_items = db.get_inventory(username)
    if 0 <= fish_index < len(inventory_items):
        item = db.remove_from_inventory(username, inventory_items[fish_index]['id'])
        if item:
            # Convert database format to the old format for compatibility
            return {
                'id': item['item_id'],
                'name': item['item_name'],
                'rarity': item['rarity'],
                'price': item['value'],
                'caught_at': int(datetime.fromisoformat(item['obtained_at']).timestamp()) if item['obtained_at'] else None,
                'type': item['item_type']
            }
    return None

async def show_inventory(ctx, *args):
    global ECONOMY_ENABLED
    if not ECONOMY_ENABLED:
        return
    # Rarity emojis dictionary
    rarity_emojis = {
        "common": "🪙",
        "uncommon": "💰",
        "rare": "💎",
        "epic": "💠",
        "legendary": "✨",
        "immortal": "☯",
        "mythical": "🌌",
        "arcane": "🔮",
        "ultimate": "🌠"
    }
    
    # Parse arguments
    rarity_filter = None
    page = 1
    
    if len(args) >= 1:
        # First argument could be either rarity or page number
        if args[0].lower() in rarity_emojis:
            rarity_filter = args[0].lower()
        elif args[0].isdigit():
            page = int(args[0])
    
    if len(args) >= 2:
        # Second argument is page number if first was rarity
        if rarity_filter and args[1].isdigit():
            page = int(args[1])
    
    # Get inventory
    inventory = get_user_inventory(ctx.author.name)
    if not inventory:
        await ctx.send(f"❌ {ctx.author.name}, у вас нет рыбы! Используйте !рыбалка")
        return
    
    # Filter by rarity if needed
    if rarity_filter:
        filtered_inventory = [fish for fish in inventory if fish['rarity'].lower() == rarity_filter]
        if not filtered_inventory:
            await ctx.send(f"❌ {ctx.author.name}, у вас нет рыбы с редкостью '{rarity_filter}'!")
            return
        inventory = filtered_inventory
    
    PER_PAGE = 5
    total_pages = (len(inventory) + PER_PAGE - 1) // PER_PAGE
    page = max(1, min(page, total_pages))
    
    # Form header with filter and emoji
    header = f"🐟 Инвентарь {ctx.author.name}"
    if rarity_filter:
        emoji = rarity_emojis.get(rarity_filter, "")
        header += f" (фильтр: {emoji}{rarity_filter.capitalize()})"
    header += f" (стр. {page}/{total_pages}):"
    
    fish_list = []
    start_idx = (page - 1) * PER_PAGE
    end_idx = min(start_idx + PER_PAGE, len(inventory))
    for idx in range(start_idx, end_idx):
        fish = inventory[idx]
        emoji = rarity_emojis.get(fish['rarity'].lower(), "")
        fish_list.append(f" {idx+1}. {emoji}{fish['name']} ({fish['rarity']}) - {fish['price']} LC||")
    
    message = [header] + fish_list
    if total_pages > 1:
        next_page_command = f"!рыба {rarity_filter} {page+1}" if rarity_filter else f"!рыба {page+1}"
        prev_page_command = f"!рыба {rarity_filter} {page-1}" if rarity_filter else f"!рыба {page-1}"
        
        page_nav = []
        if page > 1:
            page_nav.append(f"Пред: `{prev_page_command}`")
        if page < total_pages:
            page_nav.append(f"След: `{next_page_command}`")
        
        if page_nav:
            message.append(" | ".join(page_nav))

    await ctx.send("\n".join(message))

async def sell_fish(ctx, fish_index: str = None):
    if not ECONOMY_ENABLED:
        return
    if fish_index is None:
        await ctx.send("❌ Укажите номер рыбы: `!продать <номер>` или `!продать всё`")
        return
    if fish_index.lower() in ['всё', 'все']:
        inventory = get_user_inventory(ctx.author.name)
        if not inventory:
            await ctx.send(f"❌ {ctx.author.name}, у вас нет рыбы для продажи!")
            return
        total_income = 0
        sold_count = 0
        kept_ultimate = 0
        kept_non_sale = 0
        # Separate fish to keep vs sell
        fish_to_remove = []
        for i, fish in enumerate(inventory):
            if fish['rarity'] == 'ultimate':
                kept_ultimate += 1
                continue
            if fish['price']==0:
                kept_non_sale += 1
                continue
            total_income += fish['price']
            sold_count += 1
            fish_to_remove.append(i)
        # Remove sold fish from inventory (in reverse order to maintain indices)
        for i in reversed(fish_to_remove):
            remove_fish_from_inventory(ctx.author.name, i)
        try:
                fish_modi=upgrade.get_user_upgrades(ctx.author.name.lower())
                total_income += int(total_income *fish_modi.get("sale_price_increase")*0.001)
        except :
                pass
        if sold_count > 0:
            db.add_coins(ctx.author.name, total_income)
            new_balance = db.get_balance(ctx.author.name)
            message = (f"💰 {ctx.author.name} продал {sold_count} рыб(y/ы) и получил {total_income} LC! 💳 Новый баланс: {new_balance} LC")
            if kept_ultimate > 0:
                message += f"🔒 Сохранено {kept_ultimate} ultimate рыб(y/ы)"
            if kept_non_sale > 0:
                message += f"🔒 Сохранено {kept_non_sale} рыб(у/ы) без цены"
        else:
            message = f"ℹ️ {ctx.author.name}, у вас нет рыбы для массовой продажи (только ultimate)"
        await ctx.send(message)
        logger.info(f"{ctx.author.name} продал {sold_count} рыб(ы) за {total_income} LC")
        return
    try:
        fish_index = int(fish_index) - 1
        inventory = get_user_inventory(ctx.author.name)
        if fish_index < 0 or fish_index >= len(inventory):
            await ctx.send(f"❌ Нет рыбы с номером {fish_index + 1} в инвентаре!")
            return
        fish_to_sell = inventory[fish_index]
        price = fish_to_sell['price']
        
        if fish_to_sell['rarity'] == 'ultimate':
            # Mark fish as uncaught in database
            db.connect()
            cursor = db.conn.cursor()
            cursor.execute('UPDATE items SET is_caught = 0 WHERE id = ?', (fish_to_sell.get('item_id', fish_to_sell.get('id')),))
            db.conn.commit()
            db.close()
            
        removed_fish = remove_fish_from_inventory(ctx.author.name, fish_index)
        if not removed_fish:
            await ctx.send("❌ Ошибка при продаже рыбы!")
            return
        try:
                fish_modi=upgrade.get_user_upgrades(ctx.author.name.lower())
                price += int(price *fish_modi.get("sale_price_increase")*0.001)
                print(price)
        except :
                pass
        db.add_coins(ctx.author.name, price)
        new_balance = db.get_balance(ctx.author.name)
        price_emojis = {
            "common": "🪙",
            "uncommon": "💰",
            "rare": "💎",
            "epic": "💠",
            "legendary": "✨",
            "immortal": "☯",
            "mythical": "🌌",
            "arcane": "🔮",
            "ultimate": "🌠"
        }
        emoji = price_emojis.get(fish_to_sell['rarity'], "🪙")
        await ctx.send(
            f"💰 {ctx.author.name} продал {fish_to_sell['name']} "
            f"за {emoji} {price} LC {emoji} "
            f"💳 Новый баланс: {new_balance} LC"
        )
        if fish_to_sell['rarity'] in ['ultimate', 'arcane', 'mythical']:
            logger.info(f"Продана {fish_to_sell['rarity']} рыба: {fish_to_sell['name']} (ID: {fish_to_sell.get('item_id', fish_to_sell.get('id'))})")
    except ValueError:
        await ctx.send("❌ Номер рыбы должен быть целым числом или 'всё'!")
    except Exception as e:
        logger.error(f"Ошибка при продаже: {str(e)}")
        await ctx.send("❌ Произошла ошибка при продаже рыбы!")

# Shop system
def load_shop_items():
    return load_data(SHOP_FILE, default_value=list)

async def buy_item(ctx, item_id: str = None):
    global ECONOMY_ENABLED
    if not ECONOMY_ENABLED:
        return
    
    # Check if item ID is specified
    if item_id is None:
        await ctx.send("❌ Укажите ID товара: !купить <ID>")
        return
    try:
        item_id = int(item_id)
        shop_items = load_shop_items()
        item = next((x for x in shop_items if x["id"] == item_id), None)
        
        if item is None:
            await ctx.send(f"❌ Товар с ID {item_id} не найден")
            return
            
        print(item["name"])
        if item["name"] == "Случайная уникальная рыба":
            print("test")
            # Special case: buying random unique fish
            user_balance = db.get_balance(ctx.author.name)
            fish_price = item["price"]  # Fixed price for unique fish
            
            # Check if user has enough funds
            if user_balance < fish_price:
                await ctx.send(f"❌ Недостаточно LC. Нужно {fish_price} LC, у вас {user_balance} LC")
                return
            
            # Get list of all unique (ultimate) fish that haven't been caught yet
            db.connect()
            cursor = db.conn.cursor()
            cursor.execute('SELECT * FROM items WHERE type = "fish" AND rarity = "ultimate" AND is_caught = 0')
            available_fish = cursor.fetchall()
            
            if not available_fish:
                await ctx.send("❌ К сожалению, все уникальные рыбы уже куплены или пойманы!")
                return
                
            # Select random fish from available ones
            fish_item = dict(random.choice(available_fish))
            
            # Mark fish as caught
            cursor.execute('UPDATE items SET is_caught = 1 WHERE id = ?', (fish_item['id'],))
            db.conn.commit()
            db.close()
            # Add fish to user's inventory
            fish_to_add = fish_item.copy()
            fish_to_add["caught_at"] = int(time.time())
            fish_to_add["mode"] = "purchased"
            fish_to_add["price"] = fish_to_add["base_price"]
            add_fish_to_inventory(ctx.author.name, fish_to_add)
            # Deduct money
            db.add_coins(ctx.author.name, -fish_price)
            
            await ctx.send(
                f"🎉 {ctx.author.name} купил уникальную рыбу: {fish_item['name']}! "
                f"Теперь она в вашем инвентаре."
            )
            logger.info(f"{ctx.author.name} купил уникальную рыбу: {fish_item['name']} (ID:{fish_item['id']})")
            return
        
        user_balance = db.get_balance(ctx.author.name)
        if user_balance < item["price"]:
            await ctx.send(f"❌ Недостаточно LC. Нужно {item['price']} LC, у вас {user_balance} LC")
            return
        bonus_msg = ""
        if item["name"] == "Пропуск в очередь":
            db.add_queue_pass(ctx.author.name.lower(), 1)
            bonus_msg = "🎫 +1 пропуск в очередь"
        db.add_coins(ctx.author.name, -item["price"])
        await ctx.send(f"✅ Успешная покупка! ✅{bonus_msg}")
        logger.info(f"{ctx.author.name} купил {item['name']} (ID:{item_id}) за {item['price']} LC")
    
    except ValueError:
        await ctx.send("❌ ID товара должен быть числом")
    except Exception as e:
        logger.error(f"Ошибка покупки: {str(e)}")
        await ctx.send("❌ Ошибка при покупке товара")

async def show_shop(ctx, page: int = 1):
    global ECONOMY_ENABLED
    if not ECONOMY_ENABLED:
        return
    shop_items = load_shop_items()
    total_pages = max(1, (len(shop_items) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE)
    page = max(1, min(page, total_pages))
    start_idx = (page - 1) * ITEMS_PER_PAGE
    end_idx = min(start_idx + ITEMS_PER_PAGE, len(shop_items))
    message = [f"🛒 Магазин LC (Стр. {page}/{total_pages}) Ваш баланс: {db.get_balance(ctx.author.name)} LC"]
    for idx in range(start_idx, end_idx):
        item = shop_items[idx]
        message.append(
            f"|{idx+1}. {item['name']} - {item['price']} LC"
            f"(!купить {item['id']})"
        )
    if total_pages > 1:
        message.append(f"Следующая страница: !магазин {page+1}")
    await ctx.send("".join(message))

# Slots game
SLOT_CD = {}

async def slot_machine(ctx):
    global ECONOMY_ENABLED
    if not ECONOMY_ENABLED:
        return
    logger.error("Вызвано !слоты")
    username = ctx.author.name.lower()
    current_time = datetime.now()
    if username in SLOT_CD:
        last_used = SLOT_CD[username]
        if current_time - last_used < timedelta(minutes=2):
            remaining = (last_used + timedelta(minutes=2) - current_time)
            await ctx.send(f"⏳ {ctx.author.name}, следующая попытка через {remaining.seconds//60}м {remaining.seconds%60}с")
            return
    cost = 10
    args = ctx.message.content.split()
    try:
        if len(args) > 1:
            cost = int(args[1])
            if cost < 1:
                await ctx.send("❌ Ставка должна быть больше 1 LC")
                return
    except ValueError:
        await ctx.send("❌ Укажите корректную сумму (число)")
        return
    balance = db.get_balance(username)
    if balance < cost:
        await ctx.send(f"❌ Недостаточно LC. Игра стоит {cost} LC (у вас {balance} LC)")
        return
    slots = [random.choice(SLOT_SYMBOLS) for _ in range(5)]
    result = " | ".join(slots)
    if all(s == slots[0] for s in slots):
        win = cost * 5
        prize = f"JACKPOT! +{win} LC!"
    elif (slots[0] == slots[1] == slots[2] or
          slots[1] == slots[2] == slots[3] or
          slots[2] == slots[3] == slots[4]):
        win = cost
        prize = f"Выигрыш! +{win} LC!"
    else:
        win = -cost
        prize = f"Проигрыш {cost} LC"
    new_balance = db.add_coins(username, win)
    SLOT_CD[username] = current_time
    await ctx.send(
        f"🎰 {ctx.author.name} крутит слоты: {result} || {prize} "
        f"(Баланс: {new_balance} LC)"
    )

# Daily reward
async def daily_reward(ctx):
    username = ctx.author.name.lower()
    player = db.get_player(username)
    current_time = time.time()
    last_claim = player.get('last_daily_reward', 0) if player else 0
    
    # Ensure last_claim is numeric
    if isinstance(last_claim, str):
        try:
            last_claim = float(last_claim)
        except ValueError:
            last_claim = 0
    
    if current_time - last_claim >= 86400:  # 24 hours
        coins = db.add_coins(username, DAILY_REWARD)
        db.update_player(username, last_daily_reward=int(current_time))
        await ctx.send(
            f"🎁 {ctx.author.name}, вы получили {DAILY_REWARD} LC! "
            f"Теперь у вас {coins} LC"
        )
        logger.info(f"{username} получил ежедневную награду")
    else:
        remaining = 86400 - (current_time - last_claim)
        hours = int(remaining // 3600)
        minutes = int((remaining % 3600) // 60)
        await ctx.send(
            f"⏳ {ctx.author.name}, следующая ежедневка через {hours}ч {minutes}м"
        )
        logger.info(f"{username} ожидает ежедневную награду")

# Top richest players
async def top_rich(ctx):
    logger.error("Вызвано !топ")
    global ECONOMY_ENABLED
    if not ECONOMY_ENABLED:
        return
    # Get top users from database
    db.connect()
    cursor = db.conn.cursor()
    cursor.execute('SELECT username, balance FROM players WHERE balance > 0 ORDER BY balance DESC LIMIT 5')
    top_users = cursor.fetchall()
    
    if not top_users:
        await ctx.send("ℹ️ Нет данных о балансах")
        return
    
    message = "🏆:" + "".join(
        f"{i+1}. {user['username']}: {user['balance']} LC"
        for i, user in enumerate(top_users)
    )
    db.close()
    await ctx.send(message)

# Queue management
async def show_queue(ctx, page: str = None):
    # Clean expired entries when showing queue
    db._clean_expired_queue_entries()
    
    queue = db.get_queue()
    logger.error(f"Вызвано !очередь, страница {page if page else '1'}")
    if not queue:
        await ctx.channel.send("Очередь пуста FeelsBadMan")
        return
    try:
        page=int(page)
    except:
        page = 1
    for entry in queue:
        if str(entry['username']) == str(ctx.author.name.lower()):
            queue_position = db.get_queue_position(ctx.author.name.lower())
            await ctx.channel.send(
                f"@{ctx.author.name} вы в очереди. "
                f"Позиция {queue_position}/{len(queue)}"
            )
            if page> 0:
                return
    if page is None:
        page = 1
    per_page = 5
    total_pages = (len(queue) + per_page - 1) // per_page
    if page < 1:
        await ctx.channel.send(f"Некорректная страница. Доступно: 1-{total_pages}")
        return
    elif page > total_pages+1000:
        await join_queue(ctx)
        return
    start = (page-1)*per_page
    end = start + per_page
    queue_part = [
        f"{i+1}. {entry['username']} {entry['number']}"
        for i, entry in enumerate(queue[start:end], start)
    ]
    msg = (
        f"Очередь [{page}/{total_pages}]: " +
        " | ".join(queue_part)
    )
    await ctx.channel.send(msg)

# Ban management
async def toggle_ban(ctx):
    if moder(ctx):
        num = ctx.message.content.split(" ")
        if len(num) > 1:
            player_name = num[1].replace("@", "").strip().lower()
            # Check if player is already banned
            if db.is_banned(player_name):
                db.unban_player(player_name)
                await ctx.channel.send(f"✅ {player_name} теперь может снова записываться в очередь!")
                logger.info(f"{player_name} removed from banlist!")
            else:
                db.ban_player(player_name)
                await ctx.channel.send(f"🚫 {player_name} забанен и больше не может записываться в очередь!")
                logger.info(f"{player_name} added to banlist!")
        else:
            await ctx.channel.send("❌ Ошибка! Используйте `!бан @имя`")
            logger.info("Invalid ban command usage")

# Help system
async def help_command(ctx):
    args = ctx.message.content.lower().split()
    help_type = args[1] if len(args) > 1 else "0"
    help_sections = load_data(HELP_FILE, {})
    section = None
    if help_type in help_sections:
        section = help_sections[help_type]
    else:
        for key, data in help_sections.items():
            if help_type in data["aliases"]:
                section = data
                break
        else:
            section = help_sections["1"]
    if section.get("mod_only") and not_moder(ctx):
        await ctx.send("❌ Этот раздел доступен только модераторам")
        return
    message = (
        f"{section['title']}:"
        f"{section['content']}"
        "ℹ️ Другие разделы: `!помогите 1-5` "
        "или `!помогите [фан|очередь|игры|админ|рыба]`"
    )
    await ctx.send(message)
    logger.info(f"Help requested by {ctx.author.name} - section {help_type}")

# Event handlers
async def my_message_handler(ctx):
    try:
        if ctx.author.name.lower() not in {"dotabod", "streamelements", "test_testy_tester", "lonely_fr"}:
            logger.debug(f"💬 Сообщение от {ctx.author.name}: {ctx.content}")
    except:
        logger.debug(f"💬 Сообщение: {ctx.content}")
        return
    if moder(ctx):
        if "test me now" in ctx.content:
            if ctx.author.name.lower() not in {"perolya","lizamoloko"}:
                await ctx.channel.send("Работаю, хозяин!")
            else:
                await ctx.channel.send("Работаю, хозяйка!")
                

async def event_ready():
    global N_TASK
    logger.info(f"Bot {botMOD.nick} подключен к {CHANNEL}!")
    print("Запущен TW")

    N_TASK = asyncio.create_task(fishing_notifier())

async def event_disconnected(ws, error):
    """Handler for when the bot is disconnected from Twitch"""
    logger.warning(f"Бот отключен от Twitch: {error}")
    # Schedule a restart attempt
    asyncio.create_task(restart_bot_with_delay())

# Fishing notifier
async def fishing_notifier():
    global F_ACTIVE, F_MODE
    while True:
        try:
            now = datetime.now()
            if F_MODE == "limited":
                
                    if now.minute >= 7 and F_ACTIVE:
                        F_ACTIVE = False
                        channel = botMOD.get_channel(CHANNEL)
                        if channel:
                            try:
                                await channel.send("⏳ ⏳ ⏳ ОКНО РЫБАЛКИ ЗАКРЫТО ⏳ ⏳ ⏳ Больше рыбы и активностей --> https://t.me/PeroFish_bot")
                            except Exception as e:
                                logger.warning(f"Не удалось отправить сообщение о закрытии окна рыбалки: {e}")
                                await reboot()
                    if now.minute < 7 and not F_ACTIVE:
                        F_ACTIVE = True
                        channel = botMOD.get_channel(CHANNEL)
                        if channel:
                            try:
                                await channel.send("🎣 🎣 🎣 ОКНО РЫБАЛКИ ОТКРЫТО! 🎣 🎣 🎣 У вас есть 7 минут для рыбалки!")
                            except Exception as e:
                                logger.warning(f"Не удалось отправить сообщение об открытии окна рыбалки: {e}")
                                await reboot()
        except Exception as e:
            logger.exception("Ошибка в fishing_notifier")
        finally:
            await asyncio.sleep(1)

# Bot commands
@botMOD.command(name='баланс')
async def check_balance(ctx, *args, **kwargs):
    global ECONOMY_ENABLED
    if not ECONOMY_ENABLED:
        return
    username = ctx.author.name
    balance = db.get_balance(username)
    await ctx.send(f"💰 {username}, ваш баланс: {balance} LC")

@botMOD.command(name='ежедневка')
async def daily_reward_cmd(ctx):
    await daily_reward(ctx)

@botMOD.command(name='перевод')
async def transfer_coins_cmd(ctx):
    await transfer_coins(ctx)

@botMOD.command(name='выдать')
async def give_coins_cmd(ctx):
    await give_coins(ctx)

@botMOD.command(name='топ')
async def top_rich_cmd(ctx):
    await top_rich(ctx)

@botMOD.command(name='слоты')
@commands_enabled
async def slot_machine_cmd(ctx, *args, **kwargs):
    await slot_machine(ctx)

@botMOD.command(name='рыбалка')
@commands_enabled
async def fishing_cmd(ctx, *args, **kwargs):
    await fishing(ctx)

@botMOD.command(name='рыба')
@commands_enabled
async def show_inventory_cmd(ctx, *args, **kwargs):
    args = ctx.message.content.split()[1:] if len(ctx.message.content.split()) > 1 else []
    await show_inventory(ctx, *args)

@botMOD.command(name='продать')
@commands_enabled
async def sell_fish_cmd(ctx, *args, **kwargs):
    args = ctx.message.content.split()[1:] if len(ctx.message.content.split()) > 1 else []
    if len(args) == 0:
        await sell_fish(ctx)
    else:
        await sell_fish(ctx, args[0])

@botMOD.command(name='магазин')
@commands_enabled
async def shop_cmd(ctx, *args, **kwargs):
    args = ctx.message.content.split()[1:] if len(ctx.message.content.split()) > 1 else []
    if len(args) == 0:
        await show_shop(ctx)
    else:
        try:
            await show_shop(ctx, int(args[0]))
        except ValueError:
            await ctx.send("❌ Номер страницы должен быть числом")

@botMOD.command(name='купить')
@commands_enabled
async def buy_item_cmd(ctx, *args, **kwargs):
    args = ctx.message.content.split()[1:] if len(ctx.message.content.split()) > 1 else []
    if len(args) == 0:
        await buy_item(ctx)
    else:
        await buy_item(ctx, args[0])

@botMOD.command(name='очередь')
@commands_enabled
async def show_queue_cmd(ctx, *args, **kwargs):
    args = ctx.message.content.split()[1:] if len(ctx.message.content.split()) > 1 else []
    if len(args) == 0:
        await show_queue(ctx)
    elif len(args)<=100:
        await show_queue(ctx, args[0])
    else:
        await join_queue(ctx)
        

@botMOD.command(name='хочу')
@commands_enabled
async def join_queue_cmd(ctx, *args, **kwargs):
    await join_queue(ctx)

@botMOD.command(name='пати')
@commands_enabled
async def join_queue_cmd2(ctx, *args, **kwargs):
    await join_queue(ctx)

# Add more command handlers
@botMOD.command(name='мне')
@commands_enabled
async def just_ask_cmd(ctx, *args, **kwargs):
    await just_ask(ctx)

@botMOD.command(name='вкл')
async def enable_commands_cmd(ctx):
    await enable_commands(ctx)

@botMOD.command(name='выкл')
async def disable_commands_cmd(ctx):
    await disable_commands(ctx)

    
@botMOD.command(name='забанен')
async def check_ban_cmd(ctx):
    await check_ban(ctx)

@botMOD.command(name='проверитькулдаун')
@commands_enabled
async def check_cooldown_cmd_handler(ctx, *args, **kwargs):
    await check_cooldown_cmd(ctx)

@botMOD.command(name='добавить')
async def add_fish_cmd_handler(ctx, *args, **kwargs):
    await add_fish_cmd(ctx)

@botMOD.command(name='лови')
@commands_enabled
async def transfer_fish_cmd(ctx, *args, **kwargs):
    await transfer_fish(ctx)

@botMOD.command(name='глядь')
@commands_enabled
async def show_other_inventory_cmd(ctx, *args, **kwargs):
    args = ctx.message.content.split()
    if len(args) > 1:
        username = args[1]
        page = int(args[2]) if len(args) > 2 and args[2].isdigit() else 1
        await show_other_inventory(ctx, username, page)
    else:
        await ctx.send("❌ Использование: !глядь @ник [страница]")

@botMOD.command(name='гороскоп')
async def horoscope_cmd(ctx, *args, **kwargs):
    args = ctx.message.content.split()
    zodiac_sign = args[1] if len(args) > 1 else None
    await horoscope(ctx, zodiac_sign)

@botMOD.command(name='дуэль')
async def duel_cmd(ctx, *args, **kwargs):
    args = ctx.message.content.split()
    target = args[1] if len(args) > 1 else None
    await duel(ctx, target)


@botMOD.command(name='h')
async def help_cmd2(ctx, *args, **kwargs):
    await help_command(ctx)

# Add missing command handlers
@botMOD.command(name='снять')
async def take_coins_cmd(ctx, *args, **kwargs):
    await take_coins(ctx)

@botMOD.command(name='принеси')
async def bring_item_cmd(ctx, *args, **kwargs):
    await bring_item(ctx)

@botMOD.command(name='кто')
async def random_choice_cmd(ctx, *args, **kwargs):
    await random_choice(ctx)

@botMOD.command(name='лизнуть')
async def lick_user_cmd(ctx):
    await lick_user(ctx)

@botMOD.command(name='путешествие')
async def travel_story_cmd(ctx):
    await travel_story(ctx)

@botMOD.command(name='магия')
async def magic_event_cmd(ctx):
    await magic_event(ctx)

# Add more missing command functions
async def use_skip(ctx):
    logger.error("вызвано !пусти")
    player_name = ctx.author.name.replace("@", "").strip()
    
    # Check if player has queue passes
    passes = db.get_queue_passes(player_name)
    if passes <= 0:
        await ctx.channel.send(f"❌ {player_name}, у вас нет пропусков!")
        logger.info(f"{player_name} пытался использовать пропуск, но у него их 0.")
        return
    
    # Check pass cooldown (8 hours)
    if not db.can_use_pass(player_name):
        # Calculate remaining cooldown time
        last_used = db.get_pass_cooldown(player_name)
        current_time = int(time.time())
        elapsed_time = current_time - last_used
        remaining_time = max(0, 28800 - elapsed_time)  # 8 hours in seconds
        
        hours = remaining_time // 3600
        minutes = (remaining_time % 3600) // 60
        
        await ctx.channel.send(
            f"⏳ {player_name}, вы уже использовали пропуск недавно! "
            f"Следующее использование возможно через {hours}ч {minutes}м"
        )
        logger.info(f"{player_name} пытался использовать пропуск, но он на кулдауне.")
        return
    
    # Check if player is in queue
    queue_position = db.get_queue_position(player_name)
    if queue_position is None:
        await ctx.channel.send(f"❌ {player_name}, ты не в очереди!")
        logger.info(f"{player_name} попытался использовать пропуск, но его нет в очереди.")
        return
    
    # Move player to front of queue
    queue = db.get_queue()
    player_entry = None
    for i, entry in enumerate(queue):
        if entry['username'].lower() == player_name.lower():
            player_entry = queue.pop(i)
            break
    
    if player_entry:
        queue.insert(0, player_entry)
        # Update queue in database - this would require a full rewrite of the queue table
        # For now we'll just use the existing method
        for entry in queue:
            db.add_to_queue(entry['username'], entry['number'])
    
    # Decrement passes
    db.add_queue_pass(player_name, -1)
    
    # Update pass cooldown
    db.update_pass_cooldown(player_name, int(time.time()))
    
    await ctx.channel.send(f"⏩ {player_name} использовал пропуск и теперь стоит первым в очереди!")
    logger.info(f"{player_name} использовал пропуск и переместился в начало очереди.")

async def give_skip(ctx, *args, **kwargs):
    if not_moder(ctx):
        await transfer_passes(ctx, *args, **kwargs)
        return
    args = ctx.message.content.split()
    if len(args) < 2:
        await ctx.send("❌ Формат: !пропуск @ник [количество=1]")
        return
    player_name = args[1].replace("@", "").strip().lower()
    amount = int(args[2]) if len(args) > 2 and args[2].isdigit() else 1
    
    # Add passes to player
    db.add_queue_pass(player_name, amount)
    
    passes = db.get_queue_passes(player_name)
    await ctx.send(
        f"⏩ {ctx.author.name} выдал {player_name} "
        f"{amount} пропуск(ов)! Теперь у него {passes}"
    )
    logger.info(f"Модератор {ctx.author.name} выдал {amount} пропусков игроку {player_name}")

async def remove_skip(ctx):
    if moder(ctx):
        args = ctx.message.content.split()
        if len(args) > 1:
            player_name = args[1].replace("@", "").strip().lower()
            # Remove one pass
            passes_before = db.get_queue_passes(player_name)
            if passes_before > 0:
                db.add_queue_pass(player_name, -1)
                passes_after = db.get_queue_passes(player_name)
                await ctx.channel.send(f"⏳ {ctx.author.name} убрал у {player_name} 1 пропуск! Осталось {passes_after}.")
                logger.info(f"{ctx.author.name} убрал пропуск у {player_name}. Осталось {passes_after}")
            else:
                await ctx.channel.send(f"❌ {player_name} не имеет пропусков!")
                logger.info(f"{ctx.author.name} пытался убрать пропуск у {player_name}, но у него их нет")
        else:
            await ctx.channel.send("❌ Использование: !антипропуск <ник>")
            logger.info(f"{ctx.author.name} ввел команду !антипропуск без ника")

async def check_passes(ctx):
    logger.error("Вызвано !пропуски")
    args = ctx.message.content.split()
    if len(args) > 1 and moder(ctx):
        player_name = args[1].replace("@", "").strip().lower()
    else:
        player_name = ctx.author.name.replace("@", "").strip().lower()
    
    passes = db.get_queue_passes(player_name)
    if passes == 1:
        word = "пропуск"
    elif 2 <= passes <= 4:
        word = "пропуска"
    else:
        word = "пропусков"
    
    if passes > 0:
        await ctx.channel.send(f"🔖 У {player_name} - {passes} {word}.")
        logger.info(f"{ctx.author.name} проверил пропуски {player_name}: {passes}.")
    else:
        await ctx.channel.send(f"❌ У {player_name} - нет пропусков.")
        logger.info(f"{ctx.author.name} проверил пропуски {player_name}, но их нет.")

async def pick_users(ctx, count: int = 1):
    if moder(ctx):
        logger.error(f"Вызвано !pick {count}")
        if count < 1:
            await ctx.channel.send("❌ Количество игроков должно быть положительным числом!")
            return
        
        queue = db.get_queue()
        count = min(count, len(queue)) if queue else 0
        if count == 0:
            await ctx.channel.send("❌ Очередь пуста!")
            return
        
        # Get the first 'count' users from queue
        picked_users = queue[:count]
        
        # Remove picked users from queue
        for user in picked_users:
            db.remove_from_queue(user['username'])
        
        # Update last played for picked users
        for user in picked_users:
            db.update_player(user['username'].lower(), last_played=datetime.now().isoformat())
        
        selected_names = " || ".join([f"{entry['username']} {entry['number']}" for entry in picked_users])
        await ctx.channel.send(f"🎲 Выбраны ({count}): {selected_names}")
        logger.info(f"Selected {count} users: {selected_names}")

async def pick_random_users(ctx, count: int = 1):
    if moder(ctx):
        logger.error(f"Вызвано !pick_random {count}")
        if count < 1:
            await ctx.channel.send("❌ Количество игроков должно быть положительным числом!")
            return
        
        queue = db.get_queue()
        count = min(count, len(queue)) if queue else 0
        if count == 0:
            await ctx.channel.send("❌ Очередь пуста!")
            return
        
        # Randomly select users
        picked_users = random.sample(queue, count)
        
        # Remove picked users from queue
        for user in picked_users:
            db.remove_from_queue(user['username'])
        
        # Update last played for picked users
        for user in picked_users:
            db.update_player(user['username'].lower(), last_played=datetime.now().isoformat())
        
        selected_names = " || ".join([f"{entry['username']} {entry['number']}" for entry in picked_users])
        await ctx.channel.send(f"🎲 Случайно выбраны ({count}): {selected_names}")
        logger.info(f"Randomly selected {count} users: {selected_names}")

async def remove_from_queue_cmd(ctx):
    if moder(ctx):
        logger.error("Вызвано !удалить")
        args = ctx.message.content.split()
        if len(args) > 1 and args[1].isdigit():
            position = int(args[1]) - 1
            queue = db.get_queue()
            if 0 <= position < len(queue):
                removed_player = queue[position]
                db.remove_from_queue(removed_player['username'])
                queue = db.get_queue()  # Refresh queue after removal
                await ctx.channel.send(f"🗑 {ctx.author.name} удалил {removed_player['username']} из очереди!")
                logger.info(f"{ctx.author.name} удалил {removed_player['username']} из очереди (позиция {position+1})")
            else:
                await ctx.channel.send(f"❌ Неверный номер! В очереди всего {len(queue)} игроков.")
                logger.info(f"{ctx.author.name} попытался удалить игрока с неверной позицией ({position+1})")
        else:
            await ctx.channel.send("❌ Использование: !удалить <номер в списке>")
            logger.info(f"{ctx.author.name} ввел команду !удалить без номера")
    else:
        logger.info(f"{ctx.author.name} попытался удалить игрока без прав")

async def clear_cooldowns(ctx, username: str = None):
    if moder(ctx):
        db.connect()
        cursor = db.conn.cursor()
        if username:
            # Remove @ symbol if present
            clean_username = username.lstrip('@').lower()
            # Clear last played data for specific user
            cursor.execute('UPDATE players SET last_played = NULL WHERE username = ?', (clean_username,))
            db.conn.commit()
            if cursor.rowcount > 0:
                await ctx.channel.send(f"🗑 Кулдаун для очереди снят для пользователя {clean_username}")
                logger.info(f"LastPlayed cleared for {clean_username} by moderator {ctx.author.name}")
            else:
                await ctx.channel.send(f"❌ Пользователь {clean_username} не найден")
                logger.info(f"Attempt to clear cooldown for non-existent user {clean_username} by {ctx.author.name}")
        else:
            # Clear last played data for all players
            cursor.execute('UPDATE players SET last_played = NULL')
            db.conn.commit()
            await ctx.channel.send("🗑 Все кулдауны для очереди сняты")
            logger.info("LastPlayed cleared by moderator!")
        db.close()

async def clear_queue_cmd(ctx):
    if moder(ctx):
        logger.info("ОЧЕРЕДЬ ПЕРЕД ОЧИСТКОЙ", db.get_queue())
        # Clear queue table
        db.connect()
        cursor = db.conn.cursor()
        cursor.execute('DELETE FROM queue')
        db.conn.commit()
        await ctx.channel.send("🗑 Очередь очищена!")
        logger.info("Queue cleared by moderator!")
        db.close()

async def show_banlist(ctx):
    if moder(ctx):
        db.connect()
        cursor = db.conn.cursor()
        cursor.execute('SELECT username FROM bans')
        rows = cursor.fetchall()
        # Handle case where row might be a tuple or dict
        banned_users = []
        for row in rows:
            if isinstance(row, dict):
                banned_users.append(row.get('username'))
            else:
                # If it's a tuple, get the first element
                banned_users.append(row[0] if len(row) > 0 else None)
        banned_users = [user for user in banned_users if user is not None]
        
        if banned_users:
            ban_list = " || ".join(banned_users)
            await ctx.channel.send(f"🚫 Заблокированные игроки: {ban_list}")
            logger.info("Banlist invoked")
        else:
            await ctx.channel.send("✅ В банлисте никого нет!")
            logger.info("Banlist empty")
        db.close()

# Add more command handlers
@botMOD.command(name='пусти')
@commands_enabled
async def use_skip_cmd(ctx):
    await use_skip(ctx)

@botMOD.command(name='пустиего')
@commands_enabled
async def transfer_passes_cmd(ctx, *args, **kwargs):
    await transfer_passes(ctx, *args, **kwargs)

@botMOD.command(name='пропуск')
@commands_enabled
async def give_skip_cmd(ctx, *args, **kwargs):
    await give_skip(ctx, *args, **kwargs)

@botMOD.command(name='антипропуск')
@commands_enabled
async def remove_skip_cmd(ctx, *args, **kwargs):
    await remove_skip(ctx)

@botMOD.command(name='пропуски')
@commands_enabled
async def check_passes_cmd(ctx, *args, **kwargs):
    await check_passes(ctx)

@botMOD.command(name='рыбачим')
@commands_enabled
async def fish_mod_change(ctx, *args, **kwargs):
    if moder(ctx):
        global F_MODE
        if F_MODE == "limited":
            F_MODE = "normal"
            await ctx.send("✅ Режим рыбачим изменен на постоянную")
        else:
            F_MODE = "limited"
            await ctx.send("✅ Режим рыбачим изменен на ограниченную")
        

@botMOD.command(name='сборка')
@commands_enabled
async def generate_build_cmd(ctx, *args, **kwargs):
    """Генерирует случайную сборку"""
    # Check for cooldown
    username = ctx.author.name.lower()
    current_time = datetime.now()
    
    if username in BUILD_CD:
        last_used = BUILD_CD[username]
        if current_time - last_used < timedelta(minutes=7):
            remaining = (last_used + timedelta(minutes=7) - current_time)
            minutes = remaining.seconds // 60
            seconds = remaining.seconds % 60
            await ctx.send(f"⏳ {ctx.author.name}, следующая сборка через {minutes}м {seconds}с")
            return
    
    try:
        # Load heroes data
        with open("heroes.json", "r", encoding="utf-8") as f:
            heroes_data = json.load(f)
        
        # Load items data
        with open("items.json", "r", encoding="utf-8") as f:
            items_data = json.load(f)
        
        # Select random hero
        random_hero_key = random.choice(list(heroes_data.keys()))
        hero = heroes_data[random_hero_key]
        hero_name = hero.get("localized_name", "Неизвестный герой")
        
        # Flatten all items from different categories in the new structure
        all_items = []
        for category, items in items_data["items"].items():
            for item_key, item_data in items.items():
                if "dname" in item_data:
                    all_items.append(item_data)
        
        # Select 6 random items
        if len(all_items) >= 6:
            random_items = random.sample(all_items, 6)
        else:
            # If we have less than 6 items, take what we have
            random_items = all_items
        
        # Extract item names
        item_names = [item["dname"] for item in random_items]
        
        # Create message for chat
        items_list = ", ".join(item_names) if item_names else "Нет доступных предметов"
        message = f"🎲 Сборка для {hero_name}: {items_list}"
        
        await ctx.send(message)
        logger.info(f"Generated build: {hero_name} with items {item_names}")
        
        # Set cooldown
        BUILD_CD[username] = current_time
        
    except FileNotFoundError as e:
        await ctx.send("❌ Ошибка: не удалось найти файлы с героями или предметами")
        logger.error(f"File not found when generating build: {e}")
    except Exception as e:
        await ctx.send("❌ Ошибка при генерации сборки")
        logger.error(f"Error generating build: {e}")
BUILD_CD={}

@botMOD.command(name='pick')
@commands_enabled
async def pick_users_cmd(ctx, *args, **kwargs):
    args = ctx.message.content.split()
    count = int(args[1]) if len(args) > 1 and args[1].isdigit() else 1
    await pick_users(ctx, count)

@botMOD.command(name='pick_random')
@commands_enabled
async def pick_random_users_cmd(ctx, *args, **kwargs):
    args = ctx.message.content.split()
    count = int(args[1]) if len(args) > 1 and args[1].isdigit() else 1
    await pick_random_users(ctx, count)

@botMOD.command(name='удалить')
@commands_enabled
async def remove_from_queue_cmd_handler(ctx, *args, **kwargs):
    await remove_from_queue_cmd(ctx)

@botMOD.command(name='свобода')
@commands_enabled
async def clear_cooldowns_cmd(ctx):
    args = ctx.message.content.split()
    username = args[1] if len(args) > 1 else None
    await clear_cooldowns(ctx, username)

@botMOD.command(name='очистить')
@commands_enabled
async def clear_queue_cmd_handler(ctx):
    await clear_queue_cmd(ctx)

@botMOD.command(name='банлист')
async def show_banlist_cmd(ctx):
    await show_banlist(ctx)
    
@botMOD.command(name='reboot')
async def show_banlist_cmd(ctx):
    if moder(ctx):
        await reboot()
@dataclass
class PasteCommandCooldown:
    last_used: float = 0
    cooldown_period: float = 300  # 5 minutes in seconds

class PasteCommandManager:
    def __init__(self):
        self.cooldown = PasteCommandCooldown()
    
    def is_paste_command_available(self) -> tuple[bool, int]:
        """Check if paste command is available and return remaining cooldown time"""
        time_since_last = time.time() - self.cooldown.last_used
        if time_since_last >= self.cooldown.cooldown_period:
            return True, 0
        else:
            remaining = int(self.cooldown.cooldown_period - time_since_last)
            return False, remaining
    
    def update_paste_command_timestamp(self):
        """Update the timestamp when paste command was used"""
        self.cooldown.last_used = time.time()

# Create instance of paste command manager
paste_command_manager = PasteCommandManager()

@botMOD.command(name='паста')
async def paste_command(ctx):
        """Handle the !паста command"""
        # Get the argument if provided
        argument = ctx.message.content[len("!паста "):].strip() if len(ctx.message.content) > len("!паста") else None
        
        # Check if user is channel owner or moderator
        is_privileged = moder(ctx)
        
        # Only apply cooldown when sending a specific paste, not when listing
        # Also skip cooldown for channel owners and moderators
        if argument and not is_privileged and not argument.startswith("страница "):
            # Check cooldown
            is_available, seconds_remaining = pastes_manager.is_paste_command_available()
            if not is_available:
                minutes = seconds_remaining // 60
                seconds = seconds_remaining % 60
                if minutes > 0:
                    await ctx.send(f"Команда на перезарядке. Осталось {minutes} мин {seconds} сек.")
                else:
                    await ctx.send(f"Команда на перезарядке. Осталось {seconds} сек.")
                return
            
            # Update timestamp since we're processing the command
            pastes_manager.update_paste_command_timestamp()
        
        # Process the command using the pastes manager
        response = pasta_comm(argument)
        # Send the response to chat
        await ctx.send(response)
    
# Add event handlers
botMOD.add_event(my_message_handler, "event_message")
botMOD.add_event(event_ready)
botMOD.add_event(event_disconnected, "event_disconnected")

async def restart_bot_with_delay():
    """Restart the bot after a delay"""
    logger.info("Планируется перезапуск бота через 5 секунд...")
    await asyncio.sleep(5)
    logger.info("Перезапуск бота...")
    await reboot()


async def reboot():
    subprocess.Popen(["reboot.exe"])
def find_process(process_name):
    """
    Поиск и завершение процесса по имени
    """
    try:
        # Поиск всех процессов с указанным именем
        processes = []
        for proc in psutil.process_iter(['pid', 'name']):
            if proc.info['name'].lower() == process_name.lower():
                processes.append(proc)
    except:
        return None
    if not processes:
        return None
    if len(processes) >2:
        for proc in processes:
            try:
                print(f"Завершение процесса {process_name} (PID: {proc.info['pid']})")
                proc.terminate()  # Попытка корректного завершения
                proc.wait(timeout=3)  # Ожидание завершения
                print(f"Процесс {process_name} успешно завершен.")
            except psutil.TimeoutExpired:
                print(f"Принудительное завершение процесса {process_name}...")
                proc.kill()  # Принудительное завершение
                proc.wait()
                print(f"Процесс {process_name} принудительно завершен.")
            except psutil.NoSuchProcess:
                print(f"Процесс {process_name} уже завершен.")
            except Exception as e:
                print(f"Ошибка при завершении процесса: {e}")
        
        return True
async def run_tw_bot():
    try:
        print ("запуск tw")
        await botMOD.start()
    except Exception as e:
        time.sleep(5)
        print("Упал" + f"Ошибка при запуске бота: {e}")
        await run_tw_bot()

if __name__ == "__main__":
    logger.info("🚀 Запуск бота...")
    # Start health check task
    find_process("tw.exe")
    TELEGRAM_BOT_TOKEN = os.getenv("TG_BOT_TOKEN")  
    if TELEGRAM_BOT_TOKEN:
        tg_thread = threading.Thread(
            target=start_telegram_bot, 
            args=(TELEGRAM_BOT_TOKEN,), 
            daemon=True
        )
        tg_thread.start()
        
        setup_twitch_link_handler(botMOD)
        
        print("Telegram bot starting!")

    asyncio.get_event_loop().run_until_complete(run_tw_bot())
