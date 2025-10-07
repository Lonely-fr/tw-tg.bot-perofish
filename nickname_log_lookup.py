import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import re
from datetime import datetime

class NicknameLogLookup:
    def __init__(self, root):
        self.root = root
        self.root.title("Поиск информации по никнейму в логах")
        self.root.geometry("1000x700")
        
        # Variables
        self.log_path = tk.StringVar(value="tg_bot.log")
        self.nickname = tk.StringVar()
        
        self.create_widgets()
        
    def create_widgets(self):
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure grid weights for resizing
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(2, weight=1)
        
        # Log file selection
        log_frame = ttk.LabelFrame(main_frame, text="Файл логов", padding="10")
        log_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        log_frame.columnconfigure(1, weight=1)
        
        ttk.Label(log_frame, text="Путь к файлу логов:").grid(row=0, column=0, sticky=tk.W)
        ttk.Entry(log_frame, textvariable=self.log_path, width=50).grid(row=0, column=1, padx=(10, 10), sticky=(tk.W, tk.E))
        ttk.Button(log_frame, text="Обзор", command=self.browse_log).grid(row=0, column=2)
        
        # Search frame
        search_frame = ttk.LabelFrame(main_frame, text="Поиск", padding="10")
        search_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        search_frame.columnconfigure(1, weight=1)
        
        ttk.Label(search_frame, text="Никнейм:").grid(row=0, column=0, sticky=tk.W)
        ttk.Entry(search_frame, textvariable=self.nickname, width=30).grid(row=0, column=1, padx=(10, 10), sticky=(tk.W, tk.E))
        ttk.Button(search_frame, text="Поиск", command=self.search_logs).grid(row=0, column=2)
        
        # Notebook for tabs
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Chat messages tab
        self.messages_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.messages_frame, text="Сообщения в чате")
        self.messages_text = self.create_text_widget(self.messages_frame)
        
        # Mentions tab
        self.mentions_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.mentions_frame, text="Упоминания")
        self.mentions_text = self.create_text_widget(self.mentions_frame)
        
        # Actions tab
        self.actions_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.actions_frame, text="Действия")
        self.actions_text = self.create_text_widget(self.actions_frame)
        
        # Button frame
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=3, column=0, columnspan=2, pady=(10, 0))
        button_frame.columnconfigure(0, weight=1)
        button_frame.columnconfigure(1, weight=1)
        
        # Export buttons
        ttk.Button(button_frame, text="Экспорт всех результатов", command=self.export_all_results).grid(row=0, column=0, sticky=tk.W)
        ttk.Button(button_frame, text="Очистить", command=self.clear_results).grid(row=0, column=1, sticky=tk.E)
        
    def browse_log(self):
        """Browse for log file"""
        filename = filedialog.askopenfilename(
            title="Выберите файл логов",
            filetypes=[("Log files", "*.log"), ("All files", "*.*")]
        )
        if filename:
            self.log_path.set(filename)
            
    def create_text_widget(self, parent):
        """Create a scrolled text widget"""
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)
        
        text_frame = ttk.Frame(parent)
        text_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        text_frame.columnconfigure(0, weight=1)
        text_frame.rowconfigure(0, weight=1)
        
        text_widget = tk.Text(text_frame, wrap=tk.WORD, width=70, height=20)
        scrollbar = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=text_widget.yview)
        text_widget.configure(yscrollcommand=scrollbar.set)
        
        text_widget.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        return text_widget
        
    def browse_log(self):
        """Browse for log file"""
        filename = filedialog.askopenfilename(
            title="Выберите файл логов",
            filetypes=[("Log files", "*.log"), ("All files", "*.*")]
        )
        if filename:
            self.log_path.set(filename)
            
    def search_logs(self):
        """Search logs for nickname"""
        nickname = self.nickname.get().strip().lower()
        log_path = self.log_path.get().strip()
        
        if not nickname:
            messagebox.showwarning("Предупреждение", "Пожалуйста, введите никнейм для поиска")
            return
            
        if not log_path or not os.path.exists(log_path):
            messagebox.showerror("Ошибка", "Файл логов не найден")
            return
            
        try:
            # Clear previous results
            self.messages_text.delete(1.0, tk.END)
            self.mentions_text.delete(1.0, tk.END)
            self.actions_text.delete(1.0, tk.END)
            
            # Read log file
            with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
            
            # Search for nickname in log lines
            chat_messages = []
            chat_mentions = []
            actions = []
            
            # Patterns for identifying different types of entries
            message_pattern = re.compile(rf'.*{re.escape(nickname)}.*?:\s+.*')
            
            for line in lines:
                # Check if line contains the nickname
                if nickname in line:
                    # Determine the type of entry
                    if ':' in line and nickname in line.split(':', 1)[0].lower():
                        # Chat message (nickname before colon)
                        chat_messages.append(line.strip())
                    elif any(action_keyword in line.lower() for action_keyword in 
                            ['joined', 'left', ' kicked ', ' banned ', 'action', 'command']):
                        # Action entry
                        actions.append(line.strip())
                    else:
                        # Mention
                        chat_mentions.append(line.strip())
            
            # Display results
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # Display chat messages
            header = f"Сообщения в чате для '{nickname}' (поиск выполнен {timestamp})\n"
            header += "=" * 80 + "\n\n"
            self.messages_text.insert(tk.END, header)
            
            if chat_messages:
                for msg in chat_messages:
                    self.messages_text.insert(tk.END, f"{msg}\n")
            else:
                self.messages_text.insert(tk.END, "Сообщений не найдено\n")
            
            # Display mentions
            header = f"Упоминания '{nickname}' (поиск выполнен {timestamp})\n"
            header += "=" * 80 + "\n\n"
            self.mentions_text.insert(tk.END, header)
            
            if chat_mentions:
                for mention in chat_mentions:
                    self.mentions_text.insert(tk.END, f"{mention}\n")
            else:
                self.mentions_text.insert(tk.END, "Упоминаний не найдено\n")
            
            # Display actions
            header = f"Действия с участием '{nickname}' (поиск выполнен {timestamp})\n"
            header += "=" * 80 + "\n\n"
            self.actions_text.insert(tk.END, header)
            
            if actions:
                for action in actions:
                    self.actions_text.insert(tk.END, f"{action}\n")
            else:
                self.actions_text.insert(tk.END, "Действий не найдено\n")
            
            # Show message with count of results
            total_results = len(chat_messages) + len(chat_mentions) + len(actions)
            messagebox.showinfo("Поиск завершен", 
                              f"Найдено записей:\n"
                              f"Сообщений: {len(chat_messages)}\n"
                              f"Упоминаний: {len(chat_mentions)}\n"
                              f"Действий: {len(actions)}\n"
                              f"Всего: {total_results}")
            
        except Exception as e:
            messagebox.showerror("Ошибка", f"Ошибка при поиске: {str(e)}")
            
    def export_all_results(self):
        """Export all results to separate text files"""
        nickname = self.nickname.get().strip()
        if not nickname:
            messagebox.showwarning("Предупреждение", "Пожалуйста, сначала выполните поиск")
            return
        
        # Get directory for saving files
        directory = filedialog.askdirectory(title="Выберите папку для сохранения результатов")
        if not directory:
            return
            
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            # Export messages
            messages_content = self.messages_text.get(1.0, tk.END)
            if messages_content.strip():
                messages_filename = os.path.join(directory, f"{nickname}_messages_{timestamp}.txt")
                with open(messages_filename, 'w', encoding='utf-8') as f:
                    f.write(messages_content)
            
            # Export mentions
            mentions_content = self.mentions_text.get(1.0, tk.END)
            if mentions_content.strip():
                mentions_filename = os.path.join(directory, f"{nickname}_mentions_{timestamp}.txt")
                with open(mentions_filename, 'w', encoding='utf-8') as f:
                    f.write(mentions_content)
            
            # Export actions
            actions_content = self.actions_text.get(1.0, tk.END)
            if actions_content.strip():
                actions_filename = os.path.join(directory, f"{nickname}_actions_{timestamp}.txt")
                with open(actions_filename, 'w', encoding='utf-8') as f:
                    f.write(actions_content)
            
            messagebox.showinfo("Успех", f"Результаты успешно сохранены в папке:\n{directory}")
            
        except Exception as e:
            messagebox.showerror("Ошибка", f"Ошибка при сохранении файлов: {str(e)}")
                
    def clear_results(self):
        """Clear search results"""
        self.messages_text.delete(1.0, tk.END)
        self.mentions_text.delete(1.0, tk.END)
        self.actions_text.delete(1.0, tk.END)
        self.nickname.set("")

def main():
    root = tk.Tk()
    app = NicknameLogLookup(root)
    root.mainloop()

if __name__ == "__main__":
    main()