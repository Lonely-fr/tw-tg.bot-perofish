#!/usr/bin/env python3
"""
Database Manager UI for Twitch Bot
GUI application for full CRUD operations on all tables in the bot database
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import sqlite3
import os
from datetime import datetime


class DatabaseManagerUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Twitch Bot Database Manager")
        self.root.geometry("1200x800")
        
        # Database connection
        self.db_path = "bot_database.db"
        self.conn = None
        self.current_table = None
        
        # UI elements
        self.tree = None
        self.entry_frame = None
        self.entries = {}
        self.table_columns = {}
        
        # Create UI
        self.create_widgets()
        
        # Connect to database
        self.connect_database()
        
        # Load tables
        self.load_tables()
        
    def connect_database(self):
        """Connect to the SQLite database"""
        try:
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Failed to connect to database: {e}")
            
    def create_widgets(self):
        """Create UI widgets"""
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Database info frame
        db_frame = ttk.LabelFrame(main_frame, text="Database Information", padding="5")
        db_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.db_info_label = ttk.Label(db_frame, text=f"Database: {self.db_path}")
        self.db_info_label.pack(side=tk.LEFT)
        
        # Tables frame
        tables_frame = ttk.LabelFrame(main_frame, text="Tables", padding="5")
        tables_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Table listbox
        table_list_frame = ttk.Frame(tables_frame)
        table_list_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        
        ttk.Label(table_list_frame, text="Available Tables:").pack(anchor=tk.W)
        
        self.table_listbox = tk.Listbox(table_list_frame, width=30, height=8)
        self.table_listbox.pack(fill=tk.Y, expand=True)
        self.table_listbox.bind('<<ListboxSelect>>', self.on_table_select)
        
        # Table buttons
        button_frame = ttk.Frame(tables_frame)
        button_frame.pack(side=tk.LEFT, fill=tk.Y)
        
        self.refresh_btn = ttk.Button(button_frame, text="Refresh Tables", command=self.load_tables)
        self.refresh_btn.pack(fill=tk.X, pady=(0, 5))
        
        self.add_table_btn = ttk.Button(button_frame, text="Add Table", command=self.add_table)
        self.add_table_btn.pack(fill=tk.X, pady=(0, 5))
        
        self.delete_table_btn = ttk.Button(button_frame, text="Delete Table", command=self.delete_table)
        self.delete_table_btn.pack(fill=tk.X)
        
        # Data frame
        data_frame = ttk.LabelFrame(main_frame, text="Table Data", padding="5")
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
                                xscrollcommand=h_scrollbar.set)
        self.tree.pack(fill=tk.BOTH, expand=True)
        
        v_scrollbar.config(command=self.tree.yview)
        h_scrollbar.config(command=self.tree.xview)
        
        # Entry frame for data input
        self.entry_frame = ttk.LabelFrame(main_frame, text="Record Details", padding="5")
        self.entry_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Buttons frame
        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.pack(fill=tk.X)
        
        self.add_record_btn = ttk.Button(buttons_frame, text="Add Record", command=self.add_record)
        self.add_record_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        self.update_record_btn = ttk.Button(buttons_frame, text="Update Record", command=self.update_record)
        self.update_record_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        self.delete_record_btn = ttk.Button(buttons_frame, text="Delete Record", command=self.delete_record)
        self.delete_record_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        self.clear_btn = ttk.Button(buttons_frame, text="Clear Fields", command=self.clear_entries)
        self.clear_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        self.refresh_data_btn = ttk.Button(buttons_frame, text="Refresh Data", command=self.refresh_data)
        self.refresh_data_btn.pack(side=tk.RIGHT)
        
    def load_tables(self):
        """Load all tables from database"""
        if not self.conn:
            return
            
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = cursor.fetchall()
            
            # Clear listbox
            self.table_listbox.delete(0, tk.END)
            
            # Add tables to listbox
            for table in tables:
                table_name = table[0]
                # Skip internal SQLite tables
                if not table_name.startswith('sqlite_'):
                    self.table_listbox.insert(tk.END, table_name)
                    
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Failed to load tables: {e}")
            
    def on_table_select(self, event):
        """Handle table selection"""
        selection = self.table_listbox.curselection()
        if not selection:
            return
            
        table_name = self.table_listbox.get(selection[0])
        self.current_table = table_name
        self.load_table_data(table_name)
        self.create_entry_fields(table_name)
        
    def load_table_data(self, table_name):
        """Load data for selected table"""
        if not self.conn or not table_name:
            return
            
        try:
            # Clear tree
            for item in self.tree.get_children():
                self.tree.delete(item)
                
            # Clear columns
            self.tree["columns"] = ()
            
            cursor = self.conn.cursor()
            
            # Get column info
            cursor.execute(f"PRAGMA table_info({table_name});")
            columns = cursor.fetchall()
            
            # Store column info
            self.table_columns[table_name] = [col[1] for col in columns]
            
            # Configure tree columns
            column_names = [col[1] for col in columns]
            self.tree["columns"] = column_names
            
            # Format columns
            for col in column_names:
                self.tree.heading(col, text=col)
                self.tree.column(col, width=100, minwidth=50)
                
            # Load data
            cursor.execute(f"SELECT * FROM {table_name}")
            rows = cursor.fetchall()
            
            # Insert data
            for row in rows:
                values = [str(row[col]) if row[col] is not None else "NULL" for col in column_names]
                self.tree.insert("", tk.END, values=values)
                
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Failed to load table data: {e}")
            
    def create_entry_fields(self, table_name):
        """Create entry fields for table columns"""
        if not self.conn or not table_name:
            return
            
        # Clear existing entry fields
        for widget in self.entry_frame.winfo_children():
            widget.destroy()
            
        self.entries = {}
            
        try:
            cursor = self.conn.cursor()
            cursor.execute(f"PRAGMA table_info({table_name});")
            columns = cursor.fetchall()
            
            # Create entry fields in a grid
            for i, col in enumerate(columns):
                row = i // 3
                col_pos = i % 3
                
                label = ttk.Label(self.entry_frame, text=f"{col[1]} ({col[2]}):")
                label.grid(row=row*2, column=col_pos, sticky=tk.W, padx=5, pady=(5, 0))
                
                entry = ttk.Entry(self.entry_frame, width=20)
                entry.grid(row=row*2+1, column=col_pos, sticky=(tk.W, tk.E), padx=5, pady=(0, 5))
                self.entry_frame.columnconfigure(col_pos, weight=1)
                
                self.entries[col[1]] = entry
                
            # Bind tree selection to populate entries
            self.tree.bind("<<TreeviewSelect>>", self.on_tree_select)
                
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Failed to create entry fields: {e}")
            
    def on_tree_select(self, event):
        """Handle tree selection to populate entry fields"""
        selection = self.tree.selection()
        if not selection:
            return
            
        # Get selected item values
        item = self.tree.item(selection[0])
        values = item['values']
        
        # Populate entry fields
        column_names = self.table_columns.get(self.current_table, [])
        for i, col_name in enumerate(column_names):
            if i < len(values):
                entry = self.entries.get(col_name)
                if entry:
                    entry.delete(0, tk.END)
                    if values[i] != "NULL":
                        entry.insert(0, values[i])
                        
    def clear_entries(self):
        """Clear all entry fields"""
        for entry in self.entries.values():
            entry.delete(0, tk.END)
            
    def add_record(self):
        """Add a new record to the current table"""
        if not self.conn or not self.current_table:
            messagebox.showwarning("No Selection", "Please select a table first")
            return
            
        try:
            cursor = self.conn.cursor()
            
            # Get column names and values
            columns = list(self.entries.keys())
            values = []
            placeholders = []
            
            for col_name, entry in self.entries.items():
                value = entry.get()
                if value == "":
                    value = None
                    
                values.append(value)
                placeholders.append("?")
                
            # Create INSERT statement
            columns_str = ", ".join(columns)
            placeholders_str = ", ".join(placeholders)
            query = f"INSERT INTO {self.current_table} ({columns_str}) VALUES ({placeholders_str})"
            
            # Execute query
            cursor.execute(query, values)
            self.conn.commit()
            
            # Refresh data
            self.load_table_data(self.current_table)
            self.clear_entries()
            
            messagebox.showinfo("Success", "Record added successfully")
            
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Failed to add record: {e}")
            
    def update_record(self):
        """Update the selected record"""
        if not self.conn or not self.current_table:
            messagebox.showwarning("No Selection", "Please select a table first")
            return
            
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a record to update")
            return
            
        try:
            cursor = self.conn.cursor()
            
            # Get primary key columns
            cursor.execute(f"PRAGMA table_info({self.current_table});")
            columns = cursor.fetchall()
            
            pk_columns = [col[1] for col in columns if col[5] > 0]  # Primary key columns
            all_columns = [col[1] for col in columns]
            
            # If no primary key, use all columns as identifier
            if not pk_columns:
                pk_columns = all_columns
                
            # Get current values from selected row
            item = self.tree.item(selection[0])
            current_values = item['values']
            
            # Build WHERE clause using primary key columns
            where_conditions = []
            where_values = []
            
            for pk_col in pk_columns:
                if pk_col in all_columns:
                    idx = all_columns.index(pk_col)
                    if idx < len(current_values):
                        where_conditions.append(f"{pk_col} = ?")
                        where_values.append(current_values[idx] if current_values[idx] != "NULL" else None)
                        
            # Build SET clause for all columns
            set_clauses = []
            set_values = []
            
            for col_name, entry in self.entries.items():
                value = entry.get()
                if value == "":
                    value = None
                    
                set_clauses.append(f"{col_name} = ?")
                set_values.append(value)
                
            # Combine values for query
            query_values = set_values + where_values
            
            # Create UPDATE statement
            set_str = ", ".join(set_clauses)
            where_str = " AND ".join(where_conditions)
            query = f"UPDATE {self.current_table} SET {set_str} WHERE {where_str}"
            
            # Execute query
            cursor.execute(query, query_values)
            self.conn.commit()
            
            # Refresh data
            self.load_table_data(self.current_table)
            
            messagebox.showinfo("Success", "Record updated successfully")
            
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Failed to update record: {e}")
            
    def delete_record(self):
        """Delete the selected record"""
        if not self.conn or not self.current_table:
            messagebox.showwarning("No Selection", "Please select a table first")
            return
            
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a record to delete")
            return
            
        # Confirm deletion
        result = messagebox.askyesno("Confirm Deletion", "Are you sure you want to delete the selected record?")
        if not result:
            return
            
        try:
            cursor = self.conn.cursor()
            
            # Get primary key columns
            cursor.execute(f"PRAGMA table_info({self.current_table});")
            columns = cursor.fetchall()
            
            pk_columns = [col[1] for col in columns if col[5] > 0]  # Primary key columns
            all_columns = [col[1] for col in columns]
            
            # If no primary key, use all columns as identifier
            if not pk_columns:
                pk_columns = all_columns
                
            # Get current values from selected row
            item = self.tree.item(selection[0])
            current_values = item['values']
            
            # Build WHERE clause using primary key columns
            where_conditions = []
            where_values = []
            
            for pk_col in pk_columns:
                if pk_col in all_columns:
                    idx = all_columns.index(pk_col)
                    if idx < len(current_values):
                        where_conditions.append(f"{pk_col} = ?")
                        where_values.append(current_values[idx] if current_values[idx] != "NULL" else None)
                        
            # Create DELETE statement
            where_str = " AND ".join(where_conditions)
            query = f"DELETE FROM {self.current_table} WHERE {where_str}"
            
            # Execute query
            cursor.execute(query, where_values)
            self.conn.commit()
            
            # Refresh data
            self.load_table_data(self.current_table)
            self.clear_entries()
            
            messagebox.showinfo("Success", "Record deleted successfully")
            
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Failed to delete record: {e}")
            
    def refresh_data(self):
        """Refresh data for current table"""
        if self.current_table:
            self.load_table_data(self.current_table)
            self.clear_entries()
            
    def add_table(self):
        """Add a new table (placeholder)"""
        messagebox.showinfo("Not Implemented", "Adding new tables is not implemented in this version")
        
    def delete_table(self):
        """Delete a table (placeholder)"""
        messagebox.showinfo("Not Implemented", "Deleting tables is not implemented in this version")
        
    def close_connection(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()


def main():
    root = tk.Tk()
    app = DatabaseManagerUI(root)
    
    # Handle window closing
    def on_closing():
        app.close_connection()
        root.destroy()
        
    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()


if __name__ == "__main__":
    main()