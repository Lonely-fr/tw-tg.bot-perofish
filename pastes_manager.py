import sqlite3
import re
from typing import List, Dict, Optional, Tuple
from difflib import SequenceMatcher
from datetime import datetime, timedelta


class PastesManager:
    def __init__(self, db_path: str = 'bot_database.db'):
        self.db_path = db_path
        self.PASTE_COOLDOWN = 15 * 60  # 15 minutes in seconds
        self.create_pastes_table()
        self.create_pastes_votes_table()
        self.create_pastes_suggestions_table()
        self.create_pastes_cooldown_table()

    def get_db_connection(self):
        """Create and return a database connection"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def create_pastes_table(self):
        """Create the main pastes table"""
        conn = self.get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pastes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                text TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                approved INTEGER DEFAULT 1
            )
        ''')
        
        conn.commit()
        conn.close()

    def create_pastes_votes_table(self):
        """Create the table for tracking user votes"""
        conn = self.get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pastes_votes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                paste_id INTEGER NOT NULL,
                voted_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (paste_id) REFERENCES pastes (id),
                UNIQUE(username)
            )
        ''')
        
        conn.commit()
        conn.close()

    def create_pastes_suggestions_table(self):
        """Create the table for suggested pastes that need approval"""
        conn = self.get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pastes_suggestions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                name TEXT NOT NULL,
                text TEXT NOT NULL,
                suggested_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()

    def create_pastes_cooldown_table(self):
        """Create the table for tracking paste command cooldowns"""
        conn = self.get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pastes_cooldowns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                last_used INTEGER NOT NULL
            )
        ''')
        
        # Insert initial row if not exists
        cursor.execute('''
            INSERT OR IGNORE INTO pastes_cooldowns (id, last_used) VALUES (1, 0)
        ''')
        
        conn.commit()
        conn.close()

    def add_paste(self, name: str, text: str, approved: bool = True) -> bool:
        """
        Add a new paste to the database
        Returns True if successful, False if paste with this name already exists
        """
        if len(name) > 35:
            raise ValueError("Paste name cannot exceed 35 characters")
        
        if len(text) > 250:
            raise ValueError("Paste text cannot exceed 250 characters")
        
        conn = self.get_db_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute(
                "INSERT INTO pastes (name, text, approved) VALUES (?, ?, ?)",
                (name, text, int(approved))
            )
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            # Paste with this name already exists
            return False
        finally:
            conn.close()

    def suggest_paste(self, username: str, name: str, text: str) -> bool:
        """
        Suggest a new paste for approval
        Returns True if successful, False if paste with this name already exists
        """
        if len(name) > 35:
            raise ValueError("Paste name cannot exceed 35 characters")
        
        if len(text) > 250:
            raise ValueError("Paste text cannot exceed 250 characters")
        
        conn = self.get_db_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute(
                "INSERT INTO pastes_suggestions (username, name, text) VALUES (?, ?, ?)",
                (username, name, text)
            )
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            # Paste with this name already exists
            return False
        finally:
            conn.close()

    def get_all_approved_pastes(self) -> List[Dict]:
        """Get all approved pastes ordered by ID"""
        conn = self.get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT id, name, text FROM pastes WHERE approved = 1 ORDER BY id ASC"
        )
        
        pastes = cursor.fetchall()
        conn.close()
        
        return [dict(paste) for paste in pastes]

    def get_paste_by_id(self, paste_id: int) -> Optional[Dict]:
        """Get a specific paste by its ID"""
        conn = self.get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT id, name, text FROM pastes WHERE id = ? AND approved = 1",
            (paste_id,)
        )
        
        paste = cursor.fetchone()
        conn.close()
        
        return dict(paste) if paste else None

    def search_pastes_by_name(self, name: str) -> List[Dict]:
        """Search for pastes by name with fuzzy matching"""
        all_pastes = self.get_all_approved_pastes()
        matched_pastes = []
        
        for paste in all_pastes:
            similarity = SequenceMatcher(None, name.lower(), paste['name'].lower()).ratio()
            if similarity >= 0.85:  # 85% similarity threshold
                matched_pastes.append({
                    'id': paste['id'],
                    'name': paste['name'],
                    'text': paste['text'],
                    'similarity': similarity
                })
        
        # Sort by similarity (highest first)
        matched_pastes.sort(key=lambda x: x['similarity'], reverse=True)
        return matched_pastes

    def vote_for_paste(self, username: str, paste_id: int) -> bool:
        """
        Vote for a paste. If user has already voted, remove previous vote.
        Returns True if vote was successful
        """
        conn = self.get_db_connection()
        cursor = conn.cursor()
        
        # Check if paste exists and is approved
        cursor.execute(
            "SELECT id FROM pastes WHERE id = ? AND approved = 1",
            (paste_id,)
        )
        
        if not cursor.fetchone():
            conn.close()
            return False
        
        try:
            # Remove any existing vote for this user
            cursor.execute("DELETE FROM pastes_votes WHERE username = ?", (username,))
            
            # Add new vote
            cursor.execute(
                "INSERT INTO pastes_votes (username, paste_id) VALUES (?, ?)",
                (username, paste_id)
            )
            
            conn.commit()
            return True
        except sqlite3.Error:
            return False
        finally:
            conn.close()

    def get_user_vote(self, username: str) -> Optional[Dict]:
        """Get the paste that a user has voted for"""
        conn = self.get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT p.id, p.name, p.text 
            FROM pastes_votes pv
            JOIN pastes p ON pv.paste_id = p.id
            WHERE pv.username = ? AND p.approved = 1
        ''', (username,))
        
        paste = cursor.fetchone()
        conn.close()
        
        return dict(paste) if paste else None

    def get_paste_votes_count(self, paste_id: int) -> int:
        """Get the number of votes for a specific paste"""
        conn = self.get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT COUNT(*) as vote_count FROM pastes_votes WHERE paste_id = ?",
            (paste_id,)
        )
        
        count = cursor.fetchone()[0]
        conn.close()
        
        return count

    def get_all_suggestions(self) -> List[Dict]:
        """Get all paste suggestions that need approval"""
        conn = self.get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT id, username, name, text, suggested_at FROM pastes_suggestions ORDER BY suggested_at ASC"
        )
        
        suggestions = cursor.fetchall()
        conn.close()
        
        return [dict(suggestion) for suggestion in suggestions]

    def approve_suggestion(self, suggestion_id: int) -> bool:
        """
        Approve a paste suggestion and add it to the main pastes table
        Returns True if successful
        """
        conn = self.get_db_connection()
        cursor = conn.cursor()
        
        # Get the suggestion
        cursor.execute(
            "SELECT username, name, text FROM pastes_suggestions WHERE id = ?",
            (suggestion_id,)
        )
        
        suggestion = cursor.fetchone()
        if not suggestion:
            conn.close()
            return False
        
        try:
            # Add to main pastes table
            cursor.execute(
                "INSERT INTO pastes (name, text, approved) VALUES (?, ?, ?)",
                (suggestion['name'], suggestion['text'], 1)
            )
            
            # Remove from suggestions
            cursor.execute(
                "DELETE FROM pastes_suggestions WHERE id = ?",
                (suggestion_id,)
            )
            
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            # Paste with this name already exists
            return False
        finally:
            conn.close()

    def reject_suggestion(self, suggestion_id: int) -> bool:
        """Reject and remove a paste suggestion"""
        conn = self.get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM pastes_suggestions WHERE id = ?", (suggestion_id,))
        
        result = cursor.rowcount > 0
        conn.commit()
        conn.close()
        
        return result

    def delete_paste(self, paste_id: int) -> bool:
        """Delete a paste and renumber the remaining pastes"""
        conn = self.get_db_connection()
        cursor = conn.cursor()
        
        # Check if paste exists
        cursor.execute("SELECT id FROM pastes WHERE id = ?", (paste_id,))
        if not cursor.fetchone():
            conn.close()
            return False
        
        # Delete the paste
        cursor.execute("DELETE FROM pastes WHERE id = ?", (paste_id,))
        
        # Delete associated votes
        cursor.execute("DELETE FROM pastes_votes WHERE paste_id = ?", (paste_id,))
        
        conn.commit()
        conn.close()
        
        return True

    def format_paste_list(self, page=1, items_per_page=7) -> str:
        """Format a list of all pastes for display with pagination"""
        pastes = self.get_all_approved_pastes()
        
        if not pastes:
            return "Пока нет ни одной пасты."
        
        # Calculate pagination
        total_pastes = len(pastes)
        total_pages = (total_pastes + items_per_page - 1) // items_per_page
        page = max(1, min(page, total_pages))
        start_index = (page - 1) * items_per_page
        end_index = min(start_index + items_per_page, total_pastes)
        page_pastes = pastes[start_index:end_index]
        
        # Format the list
        result = "Список доступных паст:\n\n"
        for paste in page_pastes:
            result += f"{paste['id']}. {paste['name']}\n"
        
        # Add pagination info
        result += f"\nСтраница {page} из {total_pages}"
        if total_pages > 1:
            if page > 1:
                result += f"  !паста страница {page-1} для предыдущей"
            if page < total_pages:
                result += f"  !паста страница {page+1} для следующей"
        
        return result.strip()

    def is_paste_command_available(self) -> Tuple[bool, int]:
        """
        Check if the paste command is available (not on cooldown)
        Returns (is_available, seconds_remaining)
        """
        conn = self.get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT last_used FROM pastes_cooldowns WHERE id = 1")
        result = cursor.fetchone()
        conn.close()
        
        if not result:
            return True, 0
            
        last_used = result[0]
        current_time = int(datetime.now().timestamp())
        elapsed_time = current_time - last_used
        seconds_remaining = max(0, self.PASTE_COOLDOWN - elapsed_time)
        
        return elapsed_time >= self.PASTE_COOLDOWN, seconds_remaining

    def update_paste_command_timestamp(self):
        """Update the timestamp for the last paste command usage"""
        conn = self.get_db_connection()
        cursor = conn.cursor()
        
        current_time = int(datetime.now().timestamp())
        cursor.execute(
            "UPDATE pastes_cooldowns SET last_used = ? WHERE id = 1",
            (current_time,)
        )
        
        conn.commit()
        conn.close()

    def handle_twitch_paste_command(self, argument: str = None) -> str:
        """
        Handle the !паста command from Twitch
        Returns the formatted response string
        """
        if not argument:
            # No argument - show first page of paste list
            return self.format_paste_list()
        
        # Check if argument is a page request
        if argument.startswith("страница "):
            try:
                page = int(argument.split(" ")[1])
                return self.format_paste_list(page=page, items_per_page=7)
            except (ValueError, IndexError):
                return "Неверный формат. Используйте: !паста страница [номер]"
        
        # Check if argument is a number (specific paste)
        if argument.isdigit():
            paste_id = int(argument)
            paste = self.get_paste_by_id(paste_id)
            
            if paste:
                return f"{paste['name']}:\n{paste['text']}"
            else:
                return f"Паста с номером {paste_id} не найдена."
        
        # Argument is a name - search by name
        matched_pastes = self.search_pastes_by_name(argument)
        
        if not matched_pastes:
            return f"Пасты с названием, похожим на '{argument}', не найдены."
        elif len(matched_pastes) == 1:
            paste = matched_pastes[0]
            return f"{paste['name']}:\n{paste['text']}"
        else:
            # Multiple matches - ask to clarify
            result = "Найдено несколько паст с похожим названием. Уточните запрос или используйте номер:\n"
            for paste in matched_pastes:
                result += f"{paste['id']} - {paste['name']} (совпадение {paste['similarity']:.1%})\n"
            return result.strip()
