#!/usr/bin/env python3
"""
Fish Inventory Manager for Twitch Bot
GUI application for adding fish to user inventories with price modification
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import sqlite3
import os
from datetime import datetime


class FishInventoryManager:
    def __init__(self, root):
        self.root = root
        self.root.title("Fish Inventory Manager")
        self.root.geometry("800x600")
        
        # Database connection
        self.db_path = "bot_database.db"
        
        # UI variables
        self.username_var = tk.StringVar()
        self.fish_var = tk.StringVar()
        self.custom_price_var = tk.StringVar()
        self.selected_fish_id = None
        self.selected_fish_base_price = 0
        
        # Create UI
        self.create_widgets()
        
        # Load data
        self.load_players()
        self.load_fish()
        
    def create_widgets(self):
        """Create UI widgets with tabs"""
        # Main notebook for tabs
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Create tabs
        self.add_fish_tab = ttk.Frame(self.notebook)
        self.remove_fish_tab = ttk.Frame(self.notebook)
        
        self.notebook.add(self.add_fish_tab, text="Add Fish")
        self.notebook.add(self.remove_fish_tab, text="Remove Fish")
        
        # Create widgets for each tab
        self.create_add_fish_widgets()
        self.create_remove_fish_widgets()
        
    def create_add_fish_widgets(self):
        """Create widgets for the add fish tab"""
        # Main frame
        main_frame = ttk.Frame(self.add_fish_tab, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        title_label = ttk.Label(main_frame, text="Add Fish to User Inventory", font=("Arial", 16, "bold"))
        title_label.pack(pady=(0, 20))
        
        # User selection frame
        user_frame = ttk.LabelFrame(main_frame, text="User Selection", padding="10")
        user_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(user_frame, text="Username:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        self.username_combo = ttk.Combobox(user_frame, textvariable=self.username_var, width=30)
        self.username_combo.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(0, 10))
        ttk.Button(user_frame, text="Refresh Users", command=self.load_players).grid(row=0, column=2)
        user_frame.columnconfigure(1, weight=1)
        
        # Fish selection frame
        fish_frame = ttk.LabelFrame(main_frame, text="Fish Selection", padding="10")
        fish_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(fish_frame, text="Select Fish:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        self.fish_combo = ttk.Combobox(fish_frame, textvariable=self.fish_var, width=30, state="readonly")
        self.fish_combo.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(0, 10))
        self.fish_combo.bind("<<ComboboxSelected>>", self.on_fish_selected)
        ttk.Button(fish_frame, text="Refresh Fish", command=self.load_fish).grid(row=0, column=2)
        fish_frame.columnconfigure(1, weight=1)
        
        # Price modification frame
        price_frame = ttk.LabelFrame(main_frame, text="Price Modification", padding="10")
        price_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(price_frame, text="Base Price:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        self.base_price_label = ttk.Label(price_frame, text="N/A")
        self.base_price_label.grid(row=0, column=1, sticky=tk.W, padx=(0, 20))
        
        ttk.Label(price_frame, text="Custom Price:").grid(row=0, column=2, sticky=tk.W, padx=(20, 10))
        self.custom_price_entry = ttk.Entry(price_frame, textvariable=self.custom_price_var, width=15)
        self.custom_price_entry.grid(row=0, column=3, sticky=tk.W, padx=(0, 10))
        ttk.Button(price_frame, text="Use Base Price", command=self.use_base_price).grid(row=0, column=4)
        
        # Action buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(20, 10))
        
        self.add_btn = ttk.Button(button_frame, text="Add Fish to Inventory", command=self.add_fish_to_inventory)
        self.add_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Button(button_frame, text="Clear", command=self.clear_form).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(button_frame, text="Exit", command=self.root.destroy).pack(side=tk.RIGHT)
        
        # Result log
        log_frame = ttk.LabelFrame(main_frame, text="Result Log", padding="10")
        log_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))
        
        log_scrollbar = ttk.Scrollbar(log_frame)
        log_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.log_text = tk.Text(log_frame, height=10, yscrollcommand=log_scrollbar.set)
        self.log_text.pack(fill=tk.BOTH, expand=True)
        log_scrollbar.config(command=self.log_text.yview)
        
        # Configure tags for text coloring
        self.log_text.tag_configure("success", foreground="green")
        self.log_text.tag_configure("error", foreground="red")
        self.log_text.tag_configure("info", foreground="blue")
        
    def create_remove_fish_widgets(self):
        """Create widgets for the remove fish tab"""
        # Main frame
        main_frame = ttk.Frame(self.remove_fish_tab, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        title_label = ttk.Label(main_frame, text="Remove Fish from User Inventory", font=("Arial", 16, "bold"))
        title_label.pack(pady=(0, 20))
        
        # User selection frame
        user_frame = ttk.LabelFrame(main_frame, text="User Selection", padding="10")
        user_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(user_frame, text="Username:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        self.remove_username_combo = ttk.Combobox(user_frame, width=30)
        self.remove_username_combo.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(0, 10))
        self.remove_username_combo.bind("<<ComboboxSelected>>", self.load_user_fish)
        ttk.Button(user_frame, text="Refresh Users", command=self.load_players).grid(row=0, column=2)
        user_frame.columnconfigure(1, weight=1)
        
        # Fish list frame
        fish_list_frame = ttk.LabelFrame(main_frame, text="User's Fish", padding="10")
        fish_list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Fish treeview
        fish_tree_frame = ttk.Frame(fish_list_frame)
        fish_tree_frame.pack(fill=tk.BOTH, expand=True)
        
        # Scrollbars for fish
        fish_v_scrollbar = ttk.Scrollbar(fish_tree_frame, orient=tk.VERTICAL)
        fish_v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        fish_h_scrollbar = ttk.Scrollbar(fish_tree_frame, orient=tk.HORIZONTAL)
        fish_h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Fish treeview
        self.fish_tree = ttk.Treeview(fish_tree_frame,
                                     columns=("id", "item_name", "rarity", "value", "obtained_at"),
                                     show="headings",
                                     yscrollcommand=fish_v_scrollbar.set,
                                     xscrollcommand=fish_h_scrollbar.set)
        self.fish_tree.pack(fill=tk.BOTH, expand=True)
        
        fish_v_scrollbar.config(command=self.fish_tree.yview)
        fish_h_scrollbar.config(command=self.fish_tree.xview)
        
        # Define headings
        self.fish_tree.heading("id", text="ID")
        self.fish_tree.heading("item_name", text="Fish Name")
        self.fish_tree.heading("rarity", text="Rarity")
        self.fish_tree.heading("value", text="Value")
        self.fish_tree.heading("obtained_at", text="Obtained At")
        
        # Define column widths
        self.fish_tree.column("id", width=50, minwidth=50)
        self.fish_tree.column("item_name", width=200, minwidth=150)
        self.fish_tree.column("rarity", width=100, minwidth=80)
        self.fish_tree.column("value", width=80, minwidth=80)
        self.fish_tree.column("obtained_at", width=150, minwidth=120)
        
        # Buttons frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))
        
        self.remove_fish_btn = ttk.Button(button_frame, text="Remove Selected Fish", command=self.remove_selected_fish)
        self.remove_fish_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Button(button_frame, text="Load User Fish", command=self.load_user_fish).pack(side=tk.LEFT, padx=(0, 10))
        
    def connect_db(self):
        """Create a new database connection"""
        return sqlite3.connect(self.db_path)
        
    def load_players(self):
        """Load all players from database"""
        try:
            conn = self.connect_db()
            cursor = conn.cursor()
            cursor.execute("SELECT username FROM players ORDER BY username")
            players = cursor.fetchall()
            conn.close()
            
            player_list = [player[0] for player in players]
            self.username_combo['values'] = player_list
            self.remove_username_combo['values'] = player_list
            
            self.log_message("Players list loaded successfully", "info")
        except sqlite3.Error as e:
            self.log_message(f"Failed to load players: {e}", "error")
            
    def load_fish(self):
        """Load fish items from database sorted by ID in descending order"""
        try:
            conn = self.connect_db()
            cursor = conn.cursor()
            # Sort fish by ID in descending order
            cursor.execute("SELECT id, name, base_price FROM items WHERE type = 'fish' ORDER BY id DESC")
            fish_items = cursor.fetchall()
            conn.close()
            
            # Store fish data
            self.fish_data = {f"{name} (ID: {id})": (id, base_price) for id, name, base_price in fish_items}
            fish_list = list(self.fish_data.keys())
            self.fish_combo['values'] = fish_list
            
            self.log_message("Fish list loaded successfully (sorted by ID DESC)", "info")
        except sqlite3.Error as e:
            self.log_message(f"Failed to load fish: {e}", "error")
            
    def load_user_fish(self, event=None):
        """Load fish for selected user"""
        username = self.remove_username_combo.get()
        if not username:
            self.log_message("Please select a username", "error")
            return
            
        try:
            # Clear existing fish
            for item in self.fish_tree.get_children():
                self.fish_tree.delete(item)
                
            conn = self.connect_db()
            cursor = conn.cursor()
            cursor.execute("""SELECT id, item_name, rarity, value, obtained_at 
                             FROM inventory 
                             WHERE username = ? AND item_type = 'fish'
                             ORDER BY id DESC""", (username,))
            fish_items = cursor.fetchall()
            conn.close()
            
            # Add fish to treeview
            for fish in fish_items:
                self.fish_tree.insert("", tk.END, values=fish)
                
            self.log_message(f"Loaded {len(fish_items)} fish for user {username}", "info")
        except sqlite3.Error as e:
            self.log_message(f"Failed to load user fish: {e}", "error")
            
    def on_fish_selected(self, event=None):
        """Handle fish selection"""
        selected = self.fish_var.get()
        if selected in self.fish_data:
            self.selected_fish_id, self.selected_fish_base_price = self.fish_data[selected]
            self.base_price_label.config(text=str(self.selected_fish_base_price))
            self.custom_price_var.set("")  # Clear custom price when new fish is selected
            
    def use_base_price(self):
        """Set custom price to base price"""
        self.custom_price_var.set(str(self.selected_fish_base_price))
        
    def add_fish_to_inventory(self):
        """Add selected fish to user's inventory"""
        # Validate inputs
        username = self.username_var.get().strip()
        if not username:
            self.log_message("Please select or enter a username", "error")
            messagebox.showwarning("Validation Error", "Please select or enter a username")
            return
            
        if not self.selected_fish_id:
            self.log_message("Please select a fish", "error")
            messagebox.showwarning("Validation Error", "Please select a fish")
            return
            
        # Get price
        custom_price_str = self.custom_price_var.get().strip()
        try:
            if custom_price_str:
                fish_price = int(custom_price_str)
            else:
                fish_price = self.selected_fish_base_price
        except ValueError:
            self.log_message("Custom price must be a valid number", "error")
            messagebox.showwarning("Validation Error", "Custom price must be a valid number")
            return
            
        # Get fish details
        selected_fish_text = self.fish_var.get()
        fish_name = selected_fish_text.split(" (ID:")[0]  # Extract name from "Name (ID: X)"
        
        try:
            # Add fish to inventory
            conn = self.connect_db()
            cursor = conn.cursor()
            
            # Check if user exists
            cursor.execute("SELECT username FROM players WHERE username = ?", (username,))
            if not cursor.fetchone():
                conn.close()
                self.log_message(f"User '{username}' does not exist", "error")
                messagebox.showwarning("User Not Found", f"User '{username}' does not exist")
                return
                
            # Get fish rarity from database
            cursor.execute("SELECT rarity FROM items WHERE id = ?", (self.selected_fish_id,))
            result = cursor.fetchone()
            if not result:
                conn.close()
                self.log_message(f"Fish with ID {self.selected_fish_id} does not exist", "error")
                messagebox.showwarning("Fish Not Found", f"Fish with ID {self.selected_fish_id} does not exist")
                return
                
            fish_rarity = result[0]
            obtained_at = datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f")
            
            # Insert fish into inventory
            cursor.execute("""INSERT INTO inventory 
                             (username, item_type, item_id, item_name, rarity, value, obtained_at, metadata) 
                             VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                          (username, "fish", self.selected_fish_id, fish_name, fish_rarity, fish_price, obtained_at, "{}"))
            
            conn.commit()
            conn.close()
            
            success_msg = f"Added '{fish_name}' to {username}'s inventory with price {fish_price}"
            self.log_message(success_msg, "success")
            messagebox.showinfo("Success", success_msg)
            
            # Reload user fish if the same user is selected in the remove tab
            if self.remove_username_combo.get() == username:
                self.load_user_fish()
                
        except sqlite3.Error as e:
            self.log_message(f"Failed to add fish to inventory: {e}", "error")
            messagebox.showerror("Database Error", f"Failed to add fish to inventory: {e}")
            
    def remove_selected_fish(self):
        """Remove selected fish from user's inventory"""
        # Get selected fish
        selection = self.fish_tree.selection()
        if not selection:
            self.log_message("Please select a fish to remove", "error")
            messagebox.showwarning("No Selection", "Please select a fish to remove")
            return
            
        # Confirm deletion
        result = messagebox.askyesno("Confirm Deletion", "Are you sure you want to remove the selected fish?")
        if not result:
            return
            
        # Get selected item details
        item = self.fish_tree.item(selection[0])
        values = item['values']
        fish_id = values[0]
        fish_name = values[1]
        username = self.remove_username_combo.get()
        
        try:
            conn = self.connect_db()
            cursor = conn.cursor()
            
            # Delete the specific fish
            cursor.execute("DELETE FROM inventory WHERE username = ? AND id = ? AND item_type = 'fish'", 
                          (username, fish_id))
            
            conn.commit()
            conn.close()
            
            success_msg = f"Removed '{fish_name}' (ID: {fish_id}) from {username}'s inventory"
            self.log_message(success_msg, "success")
            messagebox.showinfo("Success", success_msg)
            
            # Refresh the fish list
            self.load_user_fish()
            
        except sqlite3.Error as e:
            self.log_message(f"Failed to remove fish: {e}", "error")
            messagebox.showerror("Database Error", f"Failed to remove fish: {e}")
            
    def clear_form(self):
        """Clear the form"""
        self.username_var.set("")
        self.fish_var.set("")
        self.custom_price_var.set("")
        self.base_price_label.config(text="N/A")
        self.selected_fish_id = None
        self.selected_fish_base_price = 0
        
    def log_message(self, message, tag=None):
        """Add message to log"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        formatted_message = f"[{timestamp}] {message}\n"
        self.log_text.insert(tk.END, formatted_message, tag)
        self.log_text.see(tk.END)


def main():
    root = tk.Tk()
    app = FishInventoryManager(root)
    root.mainloop()


if __name__ == "__main__":
    main()