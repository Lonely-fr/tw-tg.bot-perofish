#!/usr/bin/env python3
"""
Inventory Manager UI for Twitch Bot
GUI application for managing user inventories - duplicating fish or adding fish by ID
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import sqlite3
import os
from datetime import datetime


class InventoryManagerUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Twitch Bot Inventory Manager")
        self.root.geometry("1000x700")
        
        # Database connection
        self.db_path = "bot_database.db"
        self.conn = None
        
        # UI elements
        self.username_var = tk.StringVar()
        self.item_id_var = tk.StringVar()
        self.quantity_var = tk.StringVar(value="1")
        self.search_var = tk.StringVar()
        
        self.inventory_tree = None
        self.items_tree = None
        
        # Create UI
        self.create_widgets()
        
        # Connect to database
        self.connect_database()
        
        # Load data
        self.load_players()
        self.load_items()
        
    def connect_database(self):
        """Connect to the SQLite database"""
        try:
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Failed to connect to database: {e}")
            
    def create_widgets(self):
        """Create UI widgets"""
        # Main notebook for tabs
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Create tabs
        self.manage_tab = ttk.Frame(self.notebook)
        self.inventory_tab = ttk.Frame(self.notebook)
        self.items_tab = ttk.Frame(self.notebook)
        self.fish_tab = ttk.Frame(self.notebook)  # New fish management tab
        
        self.notebook.add(self.manage_tab, text="Manage Inventory")
        self.notebook.add(self.inventory_tab, text="User Inventory")
        self.notebook.add(self.items_tab, text="Available Items")
        self.notebook.add(self.fish_tab, text="Add Fish")  # Add the new tab
        
        # Create widgets for each tab
        self.create_manage_widgets()
        self.create_inventory_widgets()
        self.create_items_widgets()
        self.create_fish_widgets()  # Create widgets for fish tab
        
    def create_manage_widgets(self):
        """Create widgets for the inventory management tab"""
        # Main frame
        main_frame = ttk.Frame(self.manage_tab, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # User selection frame
        user_frame = ttk.LabelFrame(main_frame, text="User Selection", padding="5")
        user_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(user_frame, text="Username:").grid(row=0, column=0, sticky=tk.W, padx=(0, 5))
        self.username_combo = ttk.Combobox(user_frame, textvariable=self.username_var, width=30)
        self.username_combo.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(0, 5))
        user_frame.columnconfigure(1, weight=1)
        
        # Item selection frame
        item_frame = ttk.LabelFrame(main_frame, text="Item Selection", padding="5")
        item_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(item_frame, text="Item ID:").grid(row=0, column=0, sticky=tk.W, padx=(0, 5))
        self.item_id_entry = ttk.Entry(item_frame, textvariable=self.item_id_var, width=10)
        self.item_id_entry.grid(row=0, column=1, sticky=tk.W, padx=(0, 5))
        
        ttk.Label(item_frame, text="Quantity:").grid(row=0, column=2, sticky=tk.W, padx=(10, 5))
        self.quantity_entry = ttk.Entry(item_frame, textvariable=self.quantity_var, width=10)
        self.quantity_entry.grid(row=0, column=3, sticky=tk.W, padx=(0, 5))
        
        # Buttons frame
        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.add_item_btn = ttk.Button(buttons_frame, text="Add Item to Inventory", command=self.add_item_to_inventory)
        self.add_item_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        self.duplicate_item_btn = ttk.Button(buttons_frame, text="Duplicate Selected Item", command=self.duplicate_item)
        self.duplicate_item_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        self.refresh_btn = ttk.Button(buttons_frame, text="Refresh Data", command=self.refresh_data)
        self.refresh_btn.pack(side=tk.RIGHT)
        
        # Preview frame
        preview_frame = ttk.LabelFrame(main_frame, text="Item Preview", padding="5")
        preview_frame.pack(fill=tk.BOTH, expand=True)
        
        # Items treeview
        items_tree_frame = ttk.Frame(preview_frame)
        items_tree_frame.pack(fill=tk.BOTH, expand=True)
        
        # Scrollbars for items
        items_v_scrollbar = ttk.Scrollbar(items_tree_frame, orient=tk.VERTICAL)
        items_v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        items_h_scrollbar = ttk.Scrollbar(items_tree_frame, orient=tk.HORIZONTAL)
        items_h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Items treeview
        self.items_tree = ttk.Treeview(items_tree_frame, 
                                      columns=("id", "name", "type", "rarity", "base_price"),
                                      show="headings",
                                      yscrollcommand=items_v_scrollbar.set,
                                      xscrollcommand=items_h_scrollbar.set)
        self.items_tree.pack(fill=tk.BOTH, expand=True)
        
        items_v_scrollbar.config(command=self.items_tree.yview)
        items_h_scrollbar.config(command=self.items_tree.xview)
        
        # Define headings
        self.items_tree.heading("id", text="ID")
        self.items_tree.heading("name", text="Name")
        self.items_tree.heading("type", text="Type")
        self.items_tree.heading("rarity", text="Rarity")
        self.items_tree.heading("base_price", text="Base Price")
        
        # Define column widths
        self.items_tree.column("id", width=50, minwidth=50)
        self.items_tree.column("name", width=200, minwidth=100)
        self.items_tree.column("type", width=100, minwidth=80)
        self.items_tree.column("rarity", width=100, minwidth=80)
        self.items_tree.column("base_price", width=100, minwidth=80)
        
        # Bind selection event
        self.items_tree.bind("<<TreeviewSelect>>", self.on_item_select)
        
        # Search frame
        search_frame = ttk.Frame(preview_frame)
        search_frame.pack(fill=tk.X, pady=(5, 0))
        
        ttk.Label(search_frame, text="Search:").pack(side=tk.LEFT)
        self.search_entry = ttk.Entry(search_frame, textvariable=self.search_var)
        self.search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 0))
        self.search_var.trace("w", self.on_search_change)
        
    def create_inventory_widgets(self):
        """Create widgets for the user inventory tab"""
        # Main frame
        main_frame = ttk.Frame(self.inventory_tab, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # User selection frame
        user_frame = ttk.LabelFrame(main_frame, text="Select User", padding="5")
        user_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(user_frame, text="Username:").grid(row=0, column=0, sticky=tk.W, padx=(0, 5))
        self.inventory_username_combo = ttk.Combobox(user_frame, width=30)
        self.inventory_username_combo.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(0, 5))
        self.inventory_username_combo.bind("<<ComboboxSelected>>", self.load_user_inventory)
        user_frame.columnconfigure(1, weight=1)
        
        # Inventory treeview
        inventory_tree_frame = ttk.Frame(main_frame)
        inventory_tree_frame.pack(fill=tk.BOTH, expand=True)
        
        # Scrollbars for inventory
        inventory_v_scrollbar = ttk.Scrollbar(inventory_tree_frame, orient=tk.VERTICAL)
        inventory_v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        inventory_h_scrollbar = ttk.Scrollbar(inventory_tree_frame, orient=tk.HORIZONTAL)
        inventory_h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Inventory treeview
        self.inventory_tree = ttk.Treeview(inventory_tree_frame,
                                          columns=("id", "item_name", "item_type", "rarity", "value", "obtained_at"),
                                          show="headings",
                                          yscrollcommand=inventory_v_scrollbar.set,
                                          xscrollcommand=inventory_h_scrollbar.set)
        self.inventory_tree.pack(fill=tk.BOTH, expand=True)
        
        inventory_v_scrollbar.config(command=self.inventory_tree.yview)
        inventory_h_scrollbar.config(command=self.inventory_tree.xview)
        
        # Define headings
        self.inventory_tree.heading("id", text="ID")
        self.inventory_tree.heading("item_name", text="Item Name")
        self.inventory_tree.heading("item_type", text="Type")
        self.inventory_tree.heading("rarity", text="Rarity")
        self.inventory_tree.heading("value", text="Value")
        self.inventory_tree.heading("obtained_at", text="Obtained At")
        
        # Define column widths
        self.inventory_tree.column("id", width=50, minwidth=50)
        self.inventory_tree.column("item_name", width=200, minwidth=150)
        self.inventory_tree.column("item_type", width=100, minwidth=80)
        self.inventory_tree.column("rarity", width=100, minwidth=80)
        self.inventory_tree.column("value", width=80, minwidth=80)
        self.inventory_tree.column("obtained_at", width=150, minwidth=120)
        
        # Buttons frame
        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.pack(fill=tk.X, pady=(5, 0))
        
        self.remove_item_btn = ttk.Button(buttons_frame, text="Remove Selected Item", command=self.remove_selected_item)
        self.remove_item_btn.pack(side=tk.LEFT)
        
        self.load_inventory_btn = ttk.Button(buttons_frame, text="Load Inventory", command=self.load_user_inventory)
        self.load_inventory_btn.pack(side=tk.RIGHT)
        
    def create_items_widgets(self):
        """Create widgets for the items tab"""
        # Main frame
        main_frame = ttk.Frame(self.items_tab, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Items treeview
        items_tree_frame = ttk.Frame(main_frame)
        items_tree_frame.pack(fill=tk.BOTH, expand=True)
        
        # Scrollbars for items
        items_v_scrollbar = ttk.Scrollbar(items_tree_frame, orient=tk.VERTICAL)
        items_v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        items_h_scrollbar = ttk.Scrollbar(items_tree_frame, orient=tk.HORIZONTAL)
        items_h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Items treeview
        self.all_items_tree = ttk.Treeview(items_tree_frame,
                                          columns=("id", "name", "type", "rarity", "base_price", "is_unique", "is_caught"),
                                          show="headings",
                                          yscrollcommand=items_v_scrollbar.set,
                                          xscrollcommand=items_h_scrollbar.set)
        self.all_items_tree.pack(fill=tk.BOTH, expand=True)
        
        items_v_scrollbar.config(command=self.all_items_tree.yview)
        items_h_scrollbar.config(command=self.all_items_tree.xview)
        
        # Define headings
        self.all_items_tree.heading("id", text="ID")
        self.all_items_tree.heading("name", text="Name")
        self.all_items_tree.heading("type", text="Type")
        self.all_items_tree.heading("rarity", text="Rarity")
        self.all_items_tree.heading("base_price", text="Base Price")
        self.all_items_tree.heading("is_unique", text="Unique")
        self.all_items_tree.heading("is_caught", text="Caught")
        
        # Define column widths
        self.all_items_tree.column("id", width=50, minwidth=50)
        self.all_items_tree.column("name", width=200, minwidth=150)
        self.all_items_tree.column("type", width=100, minwidth=80)
        self.all_items_tree.column("rarity", width=100, minwidth=80)
        self.all_items_tree.column("base_price", width=100, minwidth=80)
        self.all_items_tree.column("is_unique", width=80, minwidth=80)
        self.all_items_tree.column("is_caught", width=80, minwidth=80)
        
        # Buttons frame
        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.pack(fill=tk.X, pady=(5, 0))
        
        self.refresh_items_btn = ttk.Button(buttons_frame, text="Refresh Items", command=self.load_items)
        self.refresh_items_btn.pack(side=tk.RIGHT)
        
    def create_fish_widgets(self):
        """Create widgets for the fish management tab"""
        # Main frame
        main_frame = ttk.Frame(self.fish_tab, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        title_label = ttk.Label(main_frame, text="Add Fish to User Inventory", font=("Arial", 14, "bold"))
        title_label.pack(pady=(0, 15))
        
        # User selection frame
        user_frame = ttk.LabelFrame(main_frame, text="User Selection", padding="10")
        user_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(user_frame, text="Username:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        self.fish_username_combo = ttk.Combobox(user_frame, width=30)
        self.fish_username_combo.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(0, 10))
        ttk.Button(user_frame, text="Refresh Users", command=self.load_players).grid(row=0, column=2)
        user_frame.columnconfigure(1, weight=1)
        
        # Fish selection frame
        fish_selection_frame = ttk.LabelFrame(main_frame, text="Fish Selection", padding="10")
        fish_selection_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(fish_selection_frame, text="Fish:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        self.fish_selection_combo = ttk.Combobox(fish_selection_frame, width=30, state="readonly")
        self.fish_selection_combo.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(0, 10))
        self.fish_selection_combo.bind("<<ComboboxSelected>>", self.on_fish_selected)
        ttk.Button(fish_selection_frame, text="Refresh Fish", command=self.load_fish_items).grid(row=0, column=2)
        fish_selection_frame.columnconfigure(1, weight=1)
        
        # Fish details frame
        fish_details_frame = ttk.LabelFrame(main_frame, text="Fish Details", padding="10")
        fish_details_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(fish_details_frame, text="Base Price:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        self.fish_base_price_label = ttk.Label(fish_details_frame, text="N/A")
        self.fish_base_price_label.grid(row=0, column=1, sticky=tk.W, padx=(0, 20))
        
        ttk.Label(fish_details_frame, text="Custom Price:").grid(row=0, column=2, sticky=tk.W, padx=(20, 10))
        self.fish_custom_price_var = tk.StringVar()
        self.fish_custom_price_entry = ttk.Entry(fish_details_frame, textvariable=self.fish_custom_price_var, width=15)
        self.fish_custom_price_entry.grid(row=0, column=3, sticky=tk.W, padx=(0, 10))
        ttk.Button(fish_details_frame, text="Use Base Price", command=self.use_fish_base_price).grid(row=0, column=4)
        
        # Action buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))
        
        self.add_fish_button = ttk.Button(button_frame, text="Add Fish to Inventory", command=self.add_fish_to_user)
        self.add_fish_button.pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Button(button_frame, text="Clear Form", command=self.clear_fish_form).pack(side=tk.LEFT, padx=(0, 10))
        
        # Initialize fish data storage
        self.fish_data = {}
        self.selected_fish_id = None
        self.selected_fish_base_price = 0
        
        # Load initial data
        self.load_players()
        self.load_fish_items()
        
    def load_fish_items(self):
        """Load fish items from database"""
        if not self.conn:
            return
            
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT id, name, base_price FROM items WHERE type = 'fish' ORDER BY name")
            fish_items = cursor.fetchall()
            
            # Store fish data
            self.fish_data = {f"{name} (ID: {id})": (id, base_price) for id, name, base_price in fish_items}
            fish_list = list(self.fish_data.keys())
            self.fish_selection_combo['values'] = fish_list
            
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Failed to load fish items: {e}")
            
    def on_fish_selected(self, event=None):
        """Handle fish selection"""
        selected = self.fish_selection_combo.get()
        if selected in self.fish_data:
            self.selected_fish_id, self.selected_fish_base_price = self.fish_data[selected]
            self.fish_base_price_label.config(text=str(self.selected_fish_base_price))
            self.fish_custom_price_var.set("")  # Clear custom price when new fish is selected
            
    def use_fish_base_price(self):
        """Set custom price to base price"""
        self.fish_custom_price_var.set(str(self.selected_fish_base_price))
        
    def add_fish_to_user(self):
        """Add selected fish to user's inventory"""
        if not self.conn:
            messagebox.showerror("Database Error", "Not connected to database")
            return
            
        # Validate inputs
        username = self.fish_username_combo.get().strip()
        if not username:
            messagebox.showwarning("Validation Error", "Please select or enter a username")
            return
            
        if not self.selected_fish_id:
            messagebox.showwarning("Validation Error", "Please select a fish")
            return
            
        # Get price
        custom_price_str = self.fish_custom_price_var.get().strip()
        try:
            if custom_price_str:
                fish_price = int(custom_price_str)
            else:
                fish_price = self.selected_fish_base_price
        except ValueError:
            messagebox.showwarning("Validation Error", "Custom price must be a valid number")
            return
            
        # Get fish details
        selected_fish_text = self.fish_selection_combo.get()
        fish_name = selected_fish_text.split(" (ID:")[0]  # Extract name from "Name (ID: X)"
        
        try:
            cursor = self.conn.cursor()
            
            # Check if user exists
            cursor.execute("SELECT username FROM players WHERE username = ?", (username,))
            if not cursor.fetchone():
                messagebox.showwarning("User Not Found", f"User '{username}' does not exist")
                return
                
            # Get fish rarity from database
            cursor.execute("SELECT rarity FROM items WHERE id = ?", (self.selected_fish_id,))
            result = cursor.fetchone()
            if not result:
                messagebox.showwarning("Fish Not Found", f"Fish with ID {self.selected_fish_id} does not exist")
                return
                
            fish_rarity = result[0]
            obtained_at = datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f")
            
            # Insert fish into inventory
            cursor.execute("""INSERT INTO inventory 
                             (username, item_type, item_id, item_name, rarity, value, obtained_at, metadata) 
                             VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                          (username, "fish", self.selected_fish_id, fish_name, fish_rarity, fish_price, obtained_at, "{}"))
            
            self.conn.commit()
            
            messagebox.showinfo("Success", f"Added '{fish_name}' to {username}'s inventory with price {fish_price}")
            
            # Clear the form
            self.clear_fish_form()
            
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Failed to add fish to inventory: {e}")
            
    def clear_fish_form(self):
        """Clear the fish form"""
        self.fish_username_combo.set("")
        self.fish_selection_combo.set("")
        self.fish_custom_price_var.set("")
        self.fish_base_price_label.config(text="N/A")
        self.selected_fish_id = None
        self.selected_fish_base_price = 0
        
    def load_players(self):
        """Load all players from database"""
        if not self.conn:
            return
            
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT username FROM players ORDER BY username")
            players = cursor.fetchall()
            
            player_list = [player[0] for player in players]
            self.username_combo['values'] = player_list
            self.inventory_username_combo['values'] = player_list
            
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Failed to load players: {e}")
            
    def load_items(self):
        """Load items from database"""
        if not self.conn:
            return
            
        try:
            # Clear existing items
            for item in self.items_tree.get_children():
                self.items_tree.delete(item)
                
            for item in self.all_items_tree.get_children():
                self.all_items_tree.delete(item)
                
            cursor = self.conn.cursor()
            
            # Load items for the manage tab (preview)
            cursor.execute("SELECT id, name, type, rarity, base_price FROM items ORDER BY id")
            items = cursor.fetchall()
            
            for item in items:
                self.items_tree.insert("", tk.END, values=item)
                
            # Load items for the items tab (full details)
            cursor.execute("SELECT id, name, type, rarity, base_price, is_unique, is_caught FROM items ORDER BY id")
            all_items = cursor.fetchall()
            
            for item in all_items:
                is_unique = "Yes" if item[5] else "No"
                is_caught = "Yes" if item[6] else "No"
                values = (item[0], item[1], item[2], item[3], item[4], is_unique, is_caught)
                self.all_items_tree.insert("", tk.END, values=values)
                
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Failed to load items: {e}")
            
    def load_user_inventory(self, event=None):
        """Load inventory for selected user"""
        if not self.conn:
            return
            
        username = self.inventory_username_combo.get()
        if not username:
            messagebox.showwarning("No Selection", "Please select a username")
            return
            
        try:
            # Clear existing inventory
            for item in self.inventory_tree.get_children():
                self.inventory_tree.delete(item)
                
            cursor = self.conn.cursor()
            cursor.execute("""SELECT id, item_name, item_type, rarity, value, obtained_at 
                             FROM inventory 
                             WHERE username = ? 
                             ORDER BY obtained_at DESC""", (username,))
            items = cursor.fetchall()
            
            for item in items:
                self.inventory_tree.insert("", tk.END, values=item)
                
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Failed to load inventory: {e}")
            
    def on_item_select(self, event):
        """Handle item selection in the items tree"""
        selection = self.items_tree.selection()
        if not selection:
            return
            
        item = self.items_tree.item(selection[0])
        item_id = item['values'][0]  # First column is ID
        self.item_id_var.set(str(item_id))
        
    def on_search_change(self, *args):
        """Handle search text change"""
        search_term = self.search_var.get().lower()
        
        # Clear the tree
        for item in self.items_tree.get_children():
            self.items_tree.delete(item)
            
        if not self.conn:
            return
            
        try:
            cursor = self.conn.cursor()
            if search_term:
                cursor.execute("""SELECT id, name, type, rarity, base_price 
                                 FROM items 
                                 WHERE name LIKE ? OR rarity LIKE ?
                                 ORDER BY id""", (f"%{search_term}%", f"%{search_term}%"))
            else:
                cursor.execute("SELECT id, name, type, rarity, base_price FROM items ORDER BY id")
                
            items = cursor.fetchall()
            
            for item in items:
                self.items_tree.insert("", tk.END, values=item)
                
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Failed to search items: {e}")
            
    def add_item_to_inventory(self):
        """Add item to user's inventory"""
        if not self.conn:
            messagebox.showerror("Database Error", "Not connected to database")
            return
            
        username = self.username_var.get().strip()
        item_id_str = self.item_id_var.get().strip()
        quantity_str = self.quantity_var.get().strip()
        
        # Validate inputs
        if not username:
            messagebox.showwarning("Validation Error", "Please select or enter a username")
            return
            
        if not item_id_str:
            messagebox.showwarning("Validation Error", "Please select or enter an item ID")
            return
            
        try:
            item_id = int(item_id_str)
        except ValueError:
            messagebox.showwarning("Validation Error", "Item ID must be a number")
            return
            
        try:
            quantity = int(quantity_str)
            if quantity <= 0:
                messagebox.showwarning("Validation Error", "Quantity must be greater than 0")
                return
        except ValueError:
            messagebox.showwarning("Validation Error", "Quantity must be a number")
            return
            
        try:
            cursor = self.conn.cursor()
            
            # Check if user exists
            cursor.execute("SELECT username FROM players WHERE username = ?", (username,))
            if not cursor.fetchone():
                messagebox.showwarning("User Not Found", f"User '{username}' does not exist")
                return
                
            # Check if item exists
            cursor.execute("SELECT id, name, type, rarity, base_price FROM items WHERE id = ?", (item_id,))
            item = cursor.fetchone()
            if not item:
                messagebox.showwarning("Item Not Found", f"Item with ID {item_id} does not exist")
                return
                
            # Add item(s) to inventory
            item_name, item_type, rarity, base_price = item[1], item[2], item[3], item[4]
            
            # Use current timestamp for obtained_at
            obtained_at = datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f")
            
            # Insert the item quantity times
            for _ in range(quantity):
                cursor.execute("""INSERT INTO inventory 
                                 (username, item_type, item_id, item_name, rarity, value, obtained_at, metadata) 
                                 VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                              (username, item_type, item_id, item_name, rarity, base_price, obtained_at, "{}"))
            
            self.conn.commit()
            
            messagebox.showinfo("Success", f"Added {quantity}x '{item_name}' to {username}'s inventory")
            
            # Clear the item ID and reset quantity
            self.item_id_var.set("")
            self.quantity_var.set("1")
            
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Failed to add item to inventory: {e}")
            
    def duplicate_item(self):
        """Duplicate selected item in user's inventory"""
        if not self.conn:
            messagebox.showerror("Database Error", "Not connected to database")
            return
            
        # Get selected inventory item
        if not self.inventory_tree:
            messagebox.showwarning("Error", "Inventory tab not initialized")
            return
            
        selection = self.inventory_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select an item to duplicate")
            return
            
        username = self.inventory_username_combo.get()
        if not username:
            messagebox.showwarning("No User", "Please select a user")
            return
            
        try:
            item = self.inventory_tree.item(selection[0])
            values = item['values']
            
            # Extract item details
            item_id = values[0]
            item_name = values[1]
            item_type = values[2]
            rarity = values[3]
            value = values[4]
            
            cursor = self.conn.cursor()
            
            # Use current timestamp for obtained_at
            obtained_at = datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f")
            
            # Insert duplicated item
            cursor.execute("""INSERT INTO inventory 
                             (username, item_type, item_id, item_name, rarity, value, obtained_at, metadata) 
                             VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                          (username, item_type, item_id, item_name, rarity, value, obtained_at, "{}"))
            
            self.conn.commit()
            
            messagebox.showinfo("Success", f"Duplicated '{item_name}' in {username}'s inventory")
            
            # Refresh inventory
            self.load_user_inventory()
            
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Failed to duplicate item: {e}")
            
    def remove_selected_item(self):
        """Remove selected item from user's inventory"""
        if not self.conn:
            messagebox.showerror("Database Error", "Not connected to database")
            return
            
        # Get selected inventory item
        if not self.inventory_tree:
            messagebox.showwarning("Error", "Inventory tab not initialized")
            return
            
        selection = self.inventory_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select an item to remove")
            return
            
        # Confirm deletion
        result = messagebox.askyesno("Confirm Deletion", "Are you sure you want to remove the selected item?")
        if not result:
            return
            
        username = self.inventory_username_combo.get()
        if not username:
            messagebox.showwarning("No User", "Please select a user")
            return
            
        try:
            item = self.inventory_tree.item(selection[0])
            values = item['values']
            item_id = values[0]
            item_name = values[1]
            
            cursor = self.conn.cursor()
            
            # Delete the specific item
            cursor.execute("DELETE FROM inventory WHERE username = ? AND id = ?", (username, item_id))
            
            self.conn.commit()
            
            messagebox.showinfo("Success", f"Removed '{item_name}' from {username}'s inventory")
            
            # Refresh inventory
            self.load_user_inventory()
            
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Failed to remove item: {e}")
            
    def refresh_data(self):
        """Refresh all data"""
        self.load_players()
        self.load_items()
        self.item_id_var.set("")
        self.quantity_var.set("1")
        messagebox.showinfo("Refresh", "Data refreshed successfully")
        
    def close_connection(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()


def main():
    root = tk.Tk()
    app = InventoryManagerUI(root)
    
    # Handle window closing
    def on_closing():
        app.close_connection()
        root.destroy()
        
    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()


if __name__ == "__main__":
    main()