import sqlite3
import re
from typing import List, Dict, Optional, Tuple
from difflib import SequenceMatcher
from datetime import datetime, timedelta

def get_db_connection():
    """Create and return a database connection"""
    conn = sqlite3.connect('bot_database.db')
    conn.row_factory = sqlite3.Row
    return conn

def migrate_pastes_table():
    """Migrate the pastes table to ensure paste_num column exists and is populated"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Check if paste_num column exists
    cursor.execute("PRAGMA table_info(pastes)")
    columns = [column[1] for column in cursor.fetchall()]
    
    if 'paste_num' not in columns:
        # Add the paste_num column
        cursor.execute("ALTER TABLE pastes ADD COLUMN paste_num INTEGER")
        
        # Populate paste_num with sequential numbers based on id
        cursor.execute("SELECT id FROM pastes ORDER BY id ASC")
        paste_ids = cursor.fetchall()
        
        for index, (paste_id,) in enumerate(paste_ids, 1):
            cursor.execute(
                "UPDATE pastes SET paste_num = ? WHERE id = ?",
                (index, paste_id)
            )
    
    conn.commit()
    conn.close()

def create_pastes_table():
    """Create the main pastes table"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pastes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            text TEXT NOT NULL,
            paste_num INTEGER NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            approved INTEGER DEFAULT 1
        )
    ''')
    
    conn.commit()
    conn.close()


def create_pastes_suggestions_table():
    """Create the table for suggested pastes that need approval"""
    conn = get_db_connection()
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

def _get_next_paste_num(conn):
    """Get the next available paste number"""
    cursor = conn.cursor()
    cursor.execute("SELECT COALESCE(MAX(paste_num), 0) + 1 FROM pastes")
    return cursor.fetchone()[0]

def _renumber_pastes(conn):
    """Renumber all pastes to ensure sequential numbering"""
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM pastes ORDER BY paste_num ASC")
    paste_ids = cursor.fetchall()
    
    for index, (paste_id,) in enumerate(paste_ids, 1):
        cursor.execute(
            "UPDATE pastes SET paste_num = ? WHERE id = ?",
            (index, paste_id)
        )

def add_paste(name: str, text: str, approved: bool = True) -> bool:
    """
    Add a new paste to the database
    Returns True if successful, False if paste with this name already exists
    """
    if len(name) > 35:
        raise ValueError(f"Paste name cannot exceed {len(name)}/35 characters")
    
    if len(text) > 450:
        raise ValueError(f"Paste text cannot exceed {len(text)}/450 characters")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Get the next paste number
        next_paste_num = _get_next_paste_num(conn)
        
        cursor.execute(
            "INSERT INTO pastes (name, text, paste_num, approved) VALUES (?, ?, ?, ?)",
            (name, text, next_paste_num, int(approved))
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        # Paste with this name already exists
        return False
    finally:
        conn.close()

def add_approved_paste(name: str, text: str) -> bool:
    """
    Add a new paste directly in approved state
    Returns True if successful, False if paste with this name already exists
    """
    return add_paste(name, text, approved=True)

def suggest_paste(username: str, name: str, text: str) -> bool:
    """
    Suggest a new paste for approval
    Returns True if successful, False if paste with this name already exists
    """
    if len(name) > 35:
        raise ValueError(f"Paste name cannot exceed {len(name)}/35 characters")
    
    if len(text) > 450:
        raise ValueError(f"Paste text cannot exceed {len(text)}/450 characters")
    
    conn = get_db_connection()
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

def get_all_approved_pastes() -> List[Dict]:
    """Get all approved pastes ordered by paste number"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute(
        "SELECT id, name, text, paste_num FROM pastes WHERE approved = 1 ORDER BY paste_num ASC"
    )
    
    pastes = cursor.fetchall()
    conn.close()
    
    return [dict(paste) for paste in pastes]

def get_paste_by_id(paste_id: int) -> Optional[Dict]:
    """Get a specific paste by its ID"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute(
        "SELECT id, name, text, paste_num FROM pastes WHERE id = ? AND approved = 1",
        (paste_id,)
    )
    
    paste = cursor.fetchone()
    conn.close()
    
    return dict(paste) if paste else None

def get_paste_by_num(paste_num: int) -> Optional[Dict]:
    """Get a specific paste by its number"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute(
        "SELECT id, name, text, paste_num FROM pastes WHERE paste_num = ? AND approved = 1",
        (paste_num,)
    )
    
    paste = cursor.fetchone()
    conn.close()
    
    return dict(paste) if paste else None

def search_pastes_by_name(name: str) -> List[Dict]:
    """Search for pastes by name with fuzzy matching"""
    all_pastes = get_all_approved_pastes()
    matched_pastes = []
    
    for paste in all_pastes:
        similarity = SequenceMatcher(None, name.lower(), paste['name'].lower()).ratio()
        if similarity >= 0.85:  # 85% similarity threshold
            matched_pastes.append({
                'id': paste['id'],
                'name': paste['name'],
                'text': paste['text'],
                'paste_num': paste['paste_num'],
                'similarity': similarity
            })
    
    # Sort by similarity (highest first)
    matched_pastes.sort(key=lambda x: x['similarity'], reverse=True)
    return matched_pastes



def get_all_suggestions() -> List[Dict]:
    """Get all paste suggestions that need approval"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute(
        "SELECT id, username, name, text, suggested_at FROM pastes_suggestions ORDER BY suggested_at ASC"
    )
    
    suggestions = cursor.fetchall()
    conn.close()
    
    return [dict(suggestion) for suggestion in suggestions]

def approve_suggestion(suggestion_id: int) -> bool:
    """
    Approve a paste suggestion and add it to the main pastes table
    Returns True if successful
    """
    conn = get_db_connection()
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
        # Get the next paste number
        next_paste_num = _get_next_paste_num(conn)
        
        # Add to main pastes table
        cursor.execute(
            "INSERT INTO pastes (name, text, paste_num, approved) VALUES (?, ?, ?, ?)",
            (suggestion['name'], suggestion['text'], next_paste_num, 1)
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

def reject_suggestion(suggestion_id: int) -> bool:
    """Reject and remove a paste suggestion"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("DELETE FROM pastes_suggestions WHERE id = ?", (suggestion_id,))
    
    result = cursor.rowcount > 0
    conn.commit()
    conn.close()
    
    return result

def delete_paste(paste_num: int) -> bool:
    """Delete a paste and renumber the remaining pastes"""
    conn = get_db_connection()
    cursor = conn.cursor()
    print("OK")

    # Check if paste exists
    cursor.execute("SELECT paste_num FROM pastes WHERE paste_num = ?", (paste_num,))
    if not cursor.fetchone():
        conn.close()
        return False
    
    # Delete the paste
    cursor.execute("DELETE FROM pastes WHERE paste_num = ?", (paste_num,))
    
    # Renumber all pastes to maintain sequential numbering
    _renumber_pastes(conn)
    
    conn.commit()
    conn.close()
    print("OK")
    return True

def format_paste_list(page=1, items_per_page=7) -> str:
    """Format a list of all pastes for display with pagination"""
    pastes = get_all_approved_pastes()
    
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
    result = "Список доступных паст:"
    for paste in page_pastes:
        result += f" {paste['paste_num']}. {paste['name']} "
    
    # Add pagination info
    result += f" Страница {page} из {total_pages}  "
    if page < total_pages:
        result += f"  !паста страница {page+1} для следующей  "
    result += f"Хочешь добавить пасту? --> https://t.me/PeroFish_bot"
    return result.strip()

def update_paste_command_timestamp():
    """Update the timestamp for the last paste command usage"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    current_time = int(datetime.now().timestamp())
    cursor.execute(
        "UPDATE pastes_cooldowns SET last_used = ? WHERE id = 1",
        (current_time,)
    )
    
    conn.commit()
    conn.close()

def handle_twitch_paste_command(argument: str = None) -> str:
    """
    Handle the !паста command from Twitch
    Returns the formatted response string
    """
    if not argument:
        # No argument - show first page of paste list
        return format_paste_list()
    
    # Check if argument is a page request
    if argument.startswith("страница"):
        try:
            page = int(argument.split(" ")[1])
            return format_paste_list(page=page, items_per_page=7)
        except (ValueError, IndexError):
            return "Неверный формат. Используйте: !паста страница [номер]"
    num= None
    try:
        num = argument.split(" ")[0]
        num = int(num)
    except:
        pass
    # Check if argument is a number (specific paste)
    if type(num) == int:
        # Try to get paste by number first, then by ID if not found
        paste = get_paste_by_num(num)
        
        if paste:
            return f"{paste['text']} "
        else:
            return f"Паста с номером {num} не найдена."
    
    # Argument is a name - search by name
    matched_pastes = search_pastes_by_name(argument)
    
    if not matched_pastes:
        return f"Пасты с названием, похожим на '{argument}', не найдены."
    elif len(matched_pastes) == 1:
        paste = matched_pastes[0]
        return f"{paste['name']}:\n{paste['text']}"
    else:
        # Multiple matches - ask to clarify
        result = "Найдено несколько паст с похожим названием. Уточните запрос или используйте номер:\n"
        for paste in matched_pastes:
            result += f"{paste['paste_num']} - {paste['name']} (совпадение {paste['similarity']:.1%})\n"
        return result.strip()

