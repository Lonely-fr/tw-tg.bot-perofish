#!/usr/bin/env python3
"""
Telegram Account Linker UI
GUI application for manually linking Telegram accounts with Twitch usernames in the telegram_users table
"""

import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3
import os


class TelegramAccountLinkerUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Telegram Account Linker")
        self.root.geometry("800x600")
        
        # Database connection
        self.db_path = "bot_database.db"
        self.conn = None
        
        # UI elements
        self.tree = None
        self.telegram_chat_id_entry = None
        self.twitch_username_entry = None
        self.link_code_entry = None
        
        # Create UI
        self.create_widgets()
        
        # Connect to database
        self.connect_database()
        
        # Load data
        self.load_telegram_users()
        
    def connect_database(self):
        """Connect to the SQLite database"""
        try:
            if not os.path.exists(self.db_path):
                messagebox.showerror("Database Error", f"Database file not found: {self.db_path}")
                return
                
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Failed to connect to database: {e}")
            
    def create_widgets(self):
        """Create UI widgets"""
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        title_label = ttk.Label(main_frame, text="Telegram Account Linker", font=("Arial", 16, "bold"))
        title_label.pack(pady=(0, 20))
        
        # Description
        desc_label = ttk.Label(main_frame, 
                              text="Manually link Telegram accounts with Twitch usernames in the telegram_users table",
                              wraplength=700)
        desc_label.pack(pady=(0, 20))
        
        # Data frame
        data_frame = ttk.LabelFrame(main_frame, text="Telegram Users", padding="5")
        data_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        data_frame.columnconfigure(0, weight=1)
        data_frame.rowconfigure(0, weight=1)
        
        # Treeview for data
        tree_frame = ttk.Frame(data_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True)
        tree_frame.columnconfigure(0, weight=1)
        tree_frame.rowconfigure(0, weight=1)
        
        # Scrollbars
        v_scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)
        v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        h_scrollbar = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL)
        h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Treeview
        self.tree = ttk.Treeview(tree_frame, 
                                yscrollcommand=v_scrollbar.set,
                                xscrollcommand=h_scrollbar.set,
                                columns=('Chat ID', 'Link Code', 'Twitch Username', 'Created At'), 
                                show='headings')
        
        # Define headings
        self.tree.heading('Chat ID', text='Chat ID')
        self.tree.heading('Link Code', text='Link Code')
        self.tree.heading('Twitch Username', text='Twitch Username')
        self.tree.heading('Created At', text='Created At')
        
        # Define columns
        self.tree.column('Chat ID', width=100)
        self.tree.column('Link Code', width=100)
        self.tree.column('Twitch Username', width=150)
        self.tree.column('Created At', width=150)
        
        self.tree.pack(fill=tk.BOTH, expand=True)
        
        v_scrollbar.config(command=self.tree.yview)
        h_scrollbar.config(command=self.tree.xview)
        
        # Bind tree selection to populate entries
        self.tree.bind("<<TreeviewSelect>>", self.on_tree_select)
        
        # Entry frame for data input
        self.entry_frame = ttk.LabelFrame(main_frame, text="Link Account", padding="10")
        self.entry_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Create entry fields
        self.create_entry_fields()
        
        # Buttons frame
        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.pack(fill=tk.X)
        
        self.link_btn = ttk.Button(buttons_frame, text="Link Account", command=self.link_account)
        self.link_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        self.unlink_btn = ttk.Button(buttons_frame, text="Unlink Account", command=self.unlink_account)
        self.unlink_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        self.refresh_btn = ttk.Button(buttons_frame, text="Refresh", command=self.load_telegram_users)
        self.refresh_btn.pack(side=tk.RIGHT)
        
    def create_entry_fields(self):
        """Create entry fields for linking accounts"""
        # Clear existing entry fields
        for widget in self.entry_frame.winfo_children():
            widget.destroy()
            
        # Create entry fields in a grid
        # Chat ID
        ttk.Label(self.entry_frame, text="Telegram Chat ID:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.telegram_chat_id_entry = ttk.Entry(self.entry_frame, width=30)
        self.telegram_chat_id_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=5, pady=5)
        
        # Link Code
        ttk.Label(self.entry_frame, text="Link Code:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.link_code_entry = ttk.Entry(self.entry_frame, width=30)
        self.link_code_entry.grid(row=1, column=1, sticky=(tk.W, tk.E), padx=5, pady=5)
        
        # Twitch Username
        ttk.Label(self.entry_frame, text="Twitch Username:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        self.twitch_username_entry = ttk.Entry(self.entry_frame, width=30)
        self.twitch_username_entry.grid(row=2, column=1, sticky=(tk.W, tk.E), padx=5, pady=5)
        
        # Configure column weights
        self.entry_frame.columnconfigure(1, weight=1)
        
    def on_tree_select(self, event):
        """Handle tree selection to populate entry fields"""
        selection = self.tree.selection()
        if not selection:
            return
            
        # Get selected item values
        item = self.tree.item(selection[0])
        values = item['values']
        
        # Populate entry fields
        # values order: Chat ID, Link Code, Twitch Username, Created At
        if len(values) >= 3:
            self.telegram_chat_id_entry.delete(0, tk.END)
            self.telegram_chat_id_entry.insert(0, values[0])
            
            self.link_code_entry.delete(0, tk.END)
            self.link_code_entry.insert(0, values[1] if values[1] != "NULL" else "")
            
            self.twitch_username_entry.delete(0, tk.END)
            self.twitch_username_entry.insert(0, values[2] if values[2] != "NULL" else "")
            
    def load_telegram_users(self):
        """Load telegram users data"""
        if not self.conn:
            return
            
        try:
            # Clear tree
            for item in self.tree.get_children():
                self.tree.delete(item)
                
            cursor = self.conn.cursor()
            
            # Load data
            cursor.execute("SELECT chat_id, link_code, twitch_username, created_at FROM telegram_users")
            rows = cursor.fetchall()
            
            # Insert data
            for row in rows:
                values = []
                for i in range(len(row)):
                    if row[i] is not None:
                        values.append(str(row[i]))
                    else:
                        values.append("NULL")
                self.tree.insert("", tk.END, values=values)
                
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Failed to load telegram users: {e}")
            
    def link_account(self):
        """Link a Telegram account with a Twitch username"""
        if not self.conn:
            messagebox.showerror("Database Error", "Not connected to database")
            return
            
        # Get values from entries
        chat_id = self.telegram_chat_id_entry.get().strip()
        link_code = self.link_code_entry.get().strip()
        twitch_username = self.twitch_username_entry.get().strip()
        
        # Validate input
        if not chat_id:
            messagebox.showwarning("Input Error", "Telegram Chat ID is required")
            return
            
        try:
            chat_id = int(chat_id)
        except ValueError:
            messagebox.showerror("Input Error", "Telegram Chat ID must be a number")
            return
            
        # If link_code is empty, set it to None
        if not link_code:
            link_code = None
            
        # If twitch_username is empty, set it to None
        if not twitch_username:
            twitch_username = None
            
        try:
            cursor = self.conn.cursor()
            
            # Check if the chat_id already exists
            cursor.execute("SELECT chat_id FROM telegram_users WHERE chat_id = ?", (chat_id,))
            existing_user = cursor.fetchone()
            
            if existing_user:
                # Update existing user
                cursor.execute("""
                    UPDATE telegram_users 
                    SET link_code = ?, twitch_username = ? 
                    WHERE chat_id = ?
                """, (link_code, twitch_username, chat_id))
                action = "updated"
            else:
                # Insert new user
                cursor.execute("""
                    INSERT INTO telegram_users (chat_id, link_code, twitch_username) 
                    VALUES (?, ?, ?)
                """, (chat_id, link_code, twitch_username))
                action = "added"
                
            self.conn.commit()
            
            # Refresh data
            self.load_telegram_users()
            
            # Clear entries
            self.clear_entries()
            
            messagebox.showinfo("Success", f"Telegram account {action} successfully")
            
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Failed to link account: {e}")
            
    def unlink_account(self):
        """Unlink a Telegram account from a Twitch username"""
        if not self.conn:
            messagebox.showerror("Database Error", "Not connected to database")
            return
            
        # Get chat_id from entry
        chat_id = self.telegram_chat_id_entry.get().strip()
        
        # Validate input
        if not chat_id:
            messagebox.showwarning("Input Error", "Telegram Chat ID is required")
            return
            
        try:
            chat_id = int(chat_id)
        except ValueError:
            messagebox.showerror("Input Error", "Telegram Chat ID must be a number")
            return
            
        try:
            cursor = self.conn.cursor()
            
            # Check if the chat_id exists
            cursor.execute("SELECT chat_id FROM telegram_users WHERE chat_id = ?", (chat_id,))
            existing_user = cursor.fetchone()
            
            if not existing_user:
                messagebox.showwarning("Not Found", "Telegram account not found")
                return
                
            # Update to remove twitch_username and link_code
            cursor.execute("""
                UPDATE telegram_users 
                SET link_code = NULL, twitch_username = NULL 
                WHERE chat_id = ?
            """, (chat_id,))
                
            self.conn.commit()
            
            # Refresh data
            self.load_telegram_users()
            
            # Clear entries
            self.clear_entries()
            
            messagebox.showinfo("Success", "Telegram account unlinked successfully")
            
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Failed to unlink account: {e}")
            
    def clear_entries(self):
        """Clear all entry fields"""
        self.telegram_chat_id_entry.delete(0, tk.END)
        self.link_code_entry.delete(0, tk.END)
        self.twitch_username_entry.delete(0, tk.END)
        
    def close_connection(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()


def main():
    root = tk.Tk()
    app = TelegramAccountLinkerUI(root)
    
    # Handle window closing
    def on_closing():
        app.close_connection()
        root.destroy()
        
    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()


if __name__ == "__main__":
    main()