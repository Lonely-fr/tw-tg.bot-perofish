import sqlite3
import os
import logging
from typing import Optional, Dict, Tuple

logger = logging.getLogger(__name__)

class UpgradeSystem:
    def __init__(self, db_path: str = "upgrades.db", main_db_path: str = "bot_database.db"):
        self.db_path = db_path
        self.main_db_path = main_db_path
        self.create_upgrades_table()
        
        # Upgrade costs configuration
        # Formula: base_cost * (level + 1) ^ growth_factor
        self.upgrade_config = {
            'double_catch_chance': {
                'name': 'Шанс двойной поимки',
                'base_cost': 10,
                'growth_factor': 1.8,
                'max_level': 3000,
                'description': 'Увеличивает шанс поймать пару рыб сразу 1 лвл = 0.1%, максимум 300% (+3 доп рыбы за 1 рыбалку)'
            },
            'rare_fish_chance': {
                'name': 'Шанс редкой рыбы',
                'base_cost': 10,
                'growth_factor': 2,
                'max_level': 500,
                'description': 'Увеличивает шанс(вес) выпадения рыб (чем выше редкость, тем выше увеличение шанса)'
            },
            'fishing_cooldown_reduction': {
                'name': 'Уменьшение кулдауна рыбалки',
                'base_cost': 12,
                'growth_factor': 1.6,
                'max_level': 700,
                'description': 'Уменьшает время между рыбалками в процентах 1 лвл = 0.1%'
            },
            'shop_discount': {
                'name': 'Скидки в магазине',
                'base_cost': 15,
                'growth_factor': 1.7,
                'max_level': 3000,
                'description': 'Скидка на покупки в магазине 1 лвл = 0.017%, максимум 51%'
            },
            'sale_price_increase': {
                'name': 'Увеличение стоимости продажи',
                'base_cost': 10,
                'growth_factor': 2,
                'max_level': 1000,
                'description': 'Увеличивает стоимость продажи рыб 1 лвл = 0.1%, максимум 100%'
            }
        }
    
    def create_upgrades_table(self):
        """Create the upgrades table if it doesn't exist"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS upgrades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                twitch_username TEXT UNIQUE NOT NULL,
                double_catch_chance INTEGER DEFAULT 0,
                rare_fish_chance INTEGER DEFAULT 0,
                fishing_cooldown_reduction INTEGER DEFAULT 0,
                shop_discount INTEGER DEFAULT 0,
                sale_price_increase INTEGER DEFAULT 0,
                points_balance INTEGER DEFAULT 0
            )
        ''')
        
        conn.commit()
        conn.close()
        logger.info("Upgrades table initialized")
    
    def get_upgrade_cost(self, upgrade_type: str, current_level: int) -> int:
        """
        Calculate the cost of upgrading a specific upgrade based on current level
        Formula: base_cost * (level + 1) ^ growth_factor
        """
        if upgrade_type not in self.upgrade_config:
            raise ValueError(f"Unknown upgrade type: {upgrade_type}")
            
        config = self.upgrade_config[upgrade_type]
        if current_level >= config['max_level']:
            return -1  # Max level reached
            
        base_cost = config['base_cost']
        growth_factor = config['growth_factor']
        
        cost = int(base_cost * ((current_level + 1) ** growth_factor))
        return cost
    
    def get_user_upgrades(self, twitch_username: str) -> Optional[Dict]:
        """Get all upgrades for a specific user"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT double_catch_chance, rare_fish_chance, fishing_cooldown_reduction,
                   shop_discount, sale_price_increase, points_balance
            FROM upgrades WHERE twitch_username = ?
        ''', (twitch_username,))
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return {
                'double_catch_chance': result[0],
                'rare_fish_chance': result[1],
                'fishing_cooldown_reduction': result[2],
                'shop_discount': result[3],
                'sale_price_increase': result[4],
                'points_balance': result[5]
            }
        return None
    
    def initialize_user_upgrades(self, twitch_username: str):
        """Initialize upgrades for a new user"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT OR IGNORE INTO upgrades 
                (twitch_username, double_catch_chance, rare_fish_chance, 
                 fishing_cooldown_reduction, shop_discount, sale_price_increase, points_balance)
                VALUES (?, 0, 0, 0, 0, 0, 0)
            ''', (twitch_username,))
            
            conn.commit()
        except sqlite3.Error as e:
            logger.error(f"Error initializing user upgrades for {twitch_username}: {e}")
        finally:
            conn.close()
    
    def purchase_upgrade_points(self, twitch_username: str, points_amount: int, lc_cost: int) -> Tuple[bool, str]:
        """
        Purchase upgrade points with LC from main database
        Returns (success, message)
        """
        # First, check if user has enough LC in main database
        try:
            main_conn = sqlite3.connect(self.main_db_path)
            main_cursor = main_conn.cursor()
            
            main_cursor.execute('SELECT balance FROM players WHERE username = ?', (twitch_username,))
            result = main_cursor.fetchone()
            
            if not result or result[0] < lc_cost:
                main_conn.close()
                return False, "Недостаточно LC для покупки очков прокачки"
            
            # Deduct LC from main database
            main_cursor.execute('UPDATE players SET balance = balance - ? WHERE username = ?', 
                              (lc_cost, twitch_username))
            main_conn.commit()
            main_conn.close()
        except sqlite3.Error as e:
            logger.error(f"Error deducting LC for {twitch_username}: {e}")
            return False, "Ошибка при списании LC"
        
        # Add points to upgrades database
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Initialize user if not exists
            self.initialize_user_upgrades(twitch_username)
            
            cursor.execute('UPDATE upgrades SET points_balance = points_balance + ? WHERE twitch_username = ?',
                          (points_amount, twitch_username))
            
            conn.commit()
            conn.close()
            
            logger.info(f"User {twitch_username} purchased {points_amount} upgrade points for {lc_cost} LC")
            return True, f"Успешно куплено {points_amount} очков прокачки за {lc_cost} LC"
        except sqlite3.Error as e:
            logger.error(f"Error adding upgrade points for {twitch_username}: {e}")
            return False, "Ошибка при добавлении очков прокачки"
    
    def upgrade_skill(self, twitch_username: str, upgrade_type: str) -> Tuple[bool, str]:
        """
        Upgrade a specific skill for a user
        Returns (success, message)
        """
        if upgrade_type not in self.upgrade_config:
            return False, "Неверный тип прокачки"
        
        # Get user's current upgrades
        user_upgrades = self.get_user_upgrades(twitch_username)
        if not user_upgrades:
            self.initialize_user_upgrades(twitch_username)
            user_upgrades = self.get_user_upgrades(twitch_username)
        
        current_level = user_upgrades[upgrade_type]
        config = self.upgrade_config[upgrade_type]
        
        # Check if max level reached
        if current_level >= config['max_level']:
            return False, f"Достигнут максимальный уровень для {config['name']}"
        
        # Calculate upgrade cost
        cost = self.get_upgrade_cost(upgrade_type, current_level)
        
        # Check if user has enough points
        if user_upgrades['points_balance'] < cost:
            return False, f"Недостаточно очков прокачки. Нужно {cost} очков, у вас {user_upgrades['points_balance']}"
        
        # Perform upgrade
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Deduct points
            cursor.execute('UPDATE upgrades SET points_balance = points_balance - ? WHERE twitch_username = ?',
                          (cost, twitch_username))
            
            # Increase upgrade level
            cursor.execute(f'UPDATE upgrades SET {upgrade_type} = {upgrade_type} + 1 WHERE twitch_username = ?',
                          (twitch_username,))
            
            conn.commit()
            conn.close()
            
            new_level = current_level + 1
            logger.info(f"User {twitch_username} upgraded {upgrade_type} to level {new_level}")
            return True, f"Успешно улучшено: {config['name']}. Новый уровень: {new_level}"
        except sqlite3.Error as e:
            logger.error(f"Error upgrading skill for {twitch_username}: {e}")
            return False, "Ошибка при улучшении навыка"
    
    def get_upgrade_info(self, upgrade_type: str) -> Optional[Dict]:
        """Get information about a specific upgrade type"""
        return self.upgrade_config.get(upgrade_type)
    
    def get_all_upgrade_info(self) -> Dict:
        """Get information about all upgrades"""
        return self.upgrade_config

# Example usage and testing
if __name__ == "__main__":
    # Create upgrade system instance
    upgrade_system = UpgradeSystem()
    
    # Example: Purchase upgrade points
    # success, message = upgrade_system.purchase_upgrade_points("test_user", 10, 1000)
    # print(message)
    
    # Example: Upgrade a skill
    # success, message = upgrade_system.upgrade_skill("test_user", "double_catch_chance")
    # print(message)
    print("Upgrade system module loaded successfully")

