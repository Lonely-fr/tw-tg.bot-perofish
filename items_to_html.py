import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import sqlite3
import webbrowser
import os
from datetime import datetime

class ItemsToHtmlApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Items to HTML Converter")
        self.root.geometry("600x500")
        self.root.resizable(True, True)
        
        # Variables
        self.db_path = tk.StringVar(value="bot_database.db")
        self.output_path = tk.StringVar(value="items_table.html")
        self.include_fish_only = tk.BooleanVar(value=False)
        
        self.create_widgets()
        
    def create_widgets(self):
        # Main frame
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        title_label = ttk.Label(main_frame, text="Items Database to HTML Converter", 
                               font=("Arial", 16, "bold"))
        title_label.pack(pady=(0, 20))
        
        # Database frame
        db_frame = ttk.LabelFrame(main_frame, text="Database Settings", padding="10")
        db_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Database path
        ttk.Label(db_frame, text="Database Path:").grid(row=0, column=0, sticky=tk.W, pady=(0, 5))
        db_path_frame = ttk.Frame(db_frame)
        db_path_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        db_path_frame.columnconfigure(0, weight=1)
        
        ttk.Entry(db_path_frame, textvariable=self.db_path).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(db_path_frame, text="Browse", command=self.browse_db).pack(side=tk.LEFT, padx=(5, 0))
        
        # Fish only checkbox
        ttk.Checkbutton(db_frame, text="Include only fish items", 
                       variable=self.include_fish_only).grid(row=2, column=0, sticky=tk.W)
        
        # Output frame
        output_frame = ttk.LabelFrame(main_frame, text="Output Settings", padding="10")
        output_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(output_frame, text="Output File:").grid(row=0, column=0, sticky=tk.W, pady=(0, 5))
        output_path_frame = ttk.Frame(output_frame)
        output_path_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E))
        output_path_frame.columnconfigure(0, weight=1)
        
        ttk.Entry(output_path_frame, textvariable=self.output_path).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(output_path_frame, text="Browse", command=self.browse_output).pack(side=tk.LEFT, padx=(5, 0))
        
        # Buttons frame
        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.pack(fill=tk.X, pady=(20, 0))
        
        ttk.Button(buttons_frame, text="Extract & Generate HTML", 
                  command=self.extract_and_generate).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        ttk.Button(buttons_frame, text="View HTML", 
                  command=self.view_html).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 0))
        
        # Status frame
        self.status_var = tk.StringVar(value="Ready")
        status_frame = ttk.Frame(main_frame)
        status_frame.pack(fill=tk.X, pady=(20, 0))
        
        self.status_label = ttk.Label(status_frame, textvariable=self.status_var, 
                                     relief=tk.SUNKEN, anchor=tk.CENTER)
        self.status_label.pack(fill=tk.X)
        
    def browse_db(self):
        filename = filedialog.askopenfilename(
            title="Select Database File",
            filetypes=[("SQLite Database", "*.db"), ("All Files", "*.*")]
        )
        if filename:
            self.db_path.set(filename)
            
    def browse_output(self):
        filename = filedialog.asksaveasfilename(
            title="Save HTML File",
            defaultextension=".html",
            filetypes=[("HTML Files", "*.html"), ("All Files", "*.*")]
        )
        if filename:
            self.output_path.set(filename)
            
    def extract_and_generate(self):
        try:
            self.status_var.set("Extracting data...")
            self.root.update()
            
            # Connect to database
            conn = sqlite3.connect(self.db_path.get())
            cursor = conn.cursor()
            
            # Query based on fish only option
            if self.include_fish_only.get():
                cursor.execute("SELECT * FROM items WHERE type = 'fish'")
            else:
                cursor.execute("SELECT * FROM items")
                
            data = cursor.fetchall()
            columns = [description[0] for description in cursor.description]
            
            # Close connection
            conn.close()
            
            if not data:
                messagebox.showwarning("Warning", "No data found in the items table.")
                self.status_var.set("No data found")
                return
                
            self.status_var.set(f"Generating HTML for {len(data)} items...")
            self.root.update()
            
            # Generate HTML
            html_content = self.generate_html_content(columns, data)
            
            # Save HTML
            with open(self.output_path.get(), "w", encoding="utf-8") as f:
                f.write(html_content)
                
            self.status_var.set(f"Success! Generated HTML for {len(data)} items")
            messagebox.showinfo("Success", f"Generated HTML file with {len(data)} items")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to process: {str(e)}")
            self.status_var.set("Error occurred")
            
    def generate_html_content(self, columns, data):
        # Create HTML table
        headers_html = "".join(f"<th>{col}</th>" for col in columns)
        
        rows_html = ""
        for i, row in enumerate(data):
            row_class = "even" if i % 2 == 0 else "odd"
            cells_html = "".join(f"<td>{cell if cell is not None else ''}</td>" for cell in row)
            rows_html += f"<tr class='{row_class}'>{cells_html}</tr>"
        
        # Create full HTML document
        html_content = f"""
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Items Database Table</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background-color: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #333;
            text-align: center;
        }}
        .info {{
            background-color: #e7f3ff;
            padding: 15px;
            border-left: 6px solid #2196F3;
            margin: 20px 0;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }}
        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }}
        th {{
            background-color: #4CAF50;
            color: white;
            font-weight: bold;
        }}
        tr.even {{
            background-color: #f2f2f2;
        }}
        tr.odd {{
            background-color: white;
        }}
        tr:hover {{
            background-color: #f5f5f5;
        }}
        .button {{
            display: inline-block;
            padding: 10px 20px;
            background-color: #4CAF50;
            color: white;
            text-decoration: none;
            border-radius: 4px;
            margin: 5px;
            cursor: pointer;
            border: none;
        }}
        .button:hover {{
            background-color: #45a049;
        }}
        .controls {{
            text-align: center;
            margin: 20px 0;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Items Database Table</h1>
        
        <div class="info">
            <p><strong>Total Items:</strong> {len(data)}</p>
            <p><strong>Generated:</strong> {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
            <p><strong>Filter:</strong> {"Fish Only" if self.include_fish_only.get() else "All Items"}</p>
        </div>
        
        <div class="controls">
            <button class="button" onclick="window.print()">Print Table</button>
        </div>
        
        <table>
            <thead>
                <tr>
                    {headers_html}
                </tr>
            </thead>
            <tbody>
                {rows_html}
            </tbody>
        </table>
    </div>
</body>
</html>
        """
        
        return html_content
        
    def view_html(self):
        output_file = self.output_path.get()
        if not os.path.exists(output_file):
            messagebox.showwarning("Warning", "HTML file not found. Please generate it first.")
            return
            
        try:
            webbrowser.open(f"file://{os.path.abspath(output_file)}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open HTML: {str(e)}")

def main():
    root = tk.Tk()
    app = ItemsToHtmlApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()