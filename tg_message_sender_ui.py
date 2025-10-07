#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Telegram Message Sender UI
GUI application for sending messages to Telegram bot users
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import sqlite3
import telebot
import os
import json
from dotenv import load_dotenv
import threading
from datetime import datetime

class TelegramMessageSenderUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Отправка сообщений через Telegram бот")
        self.root.geometry("800x680")
        
        # Load environment variables
        load_dotenv(".env")
        self.token = os.getenv("TG_BOT_TOKEN")
        
        # Bot instance
        self.bot = None
        if self.token:
            self.bot = telebot.TeleBot(self.token)
        
        # Load emojis
        self.emojis = self.load_emojis()
        
        # Create notebook (tabs)
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Create tabs
        self.broadcast_tab = ttk.Frame(self.notebook)
        self.direct_message_tab = ttk.Frame(self.notebook)
        
        self.notebook.add(self.broadcast_tab, text="Массовая рассылка")
        self.notebook.add(self.direct_message_tab, text="Личное сообщение")
        
        # UI elements
        self.create_broadcast_widgets()
        self.create_direct_message_widgets()
        
        # Status variables
        self.is_sending = False
        
    def load_emojis(self):
        """Load emojis from JSON file"""
        try:
            with open('emojis.json', 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading emojis: {e}")
            return {
                "smiles": ["😀", "😃", "😄", "😁", "😊", "🙂", "😉", "😍", "😘", "😎"],
                "hearts": ["❤️", "💙", "💚", "💛", "💜"],
                "symbols": ["✨", "🔥", "💯", "💥", "⭐", "🌟"]
            }
        
    def create_broadcast_widgets(self):
        """Create UI widgets for broadcast tab"""
        # Main frame
        main_frame = ttk.Frame(self.broadcast_tab, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Configure grid weights
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(4, weight=1)
        
        # Token frame
        token_frame = ttk.LabelFrame(main_frame, text="Токен бота", padding="5")
        token_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        token_frame.columnconfigure(1, weight=1)
        
        ttk.Label(token_frame, text="Токен:").grid(row=0, column=0, sticky=tk.W, padx=(0, 5))
        self.token_var = tk.StringVar(value=self.token if self.token else "")
        self.token_entry = ttk.Entry(token_frame, textvariable=self.token_var, width=50)
        self.token_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(0, 5))
        
        self.refresh_token_btn = ttk.Button(token_frame, text="Обновить токен", command=self.refresh_token)
        self.refresh_token_btn.grid(row=0, column=2)
        
        # Mode frame
        mode_frame = ttk.LabelFrame(main_frame, text="Режим отправки", padding="5")
        mode_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        
        self.mode_var = tk.StringVar(value="all")
        ttk.Radiobutton(mode_frame, text="Отправить всем пользователям", variable=self.mode_var, value="all").grid(row=0, column=0, sticky=tk.W)
        ttk.Radiobutton(mode_frame, text="Тестовый режим (только lonely_fr)", variable=self.mode_var, value="test").grid(row=0, column=1, sticky=tk.W, padx=(20, 0))
        
        # Notification frame
        notification_frame = ttk.Frame(main_frame)
        notification_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        
        self.silent_var = tk.BooleanVar()
        self.silent_checkbox = ttk.Checkbutton(notification_frame, text="Отправить без уведомления (тихо)", variable=self.silent_var)
        self.silent_checkbox.grid(row=0, column=0, sticky=tk.W)
        
        # Media files frame for broadcast
        broadcast_media_frame = ttk.LabelFrame(main_frame, text="Медиафайлы для массовой рассылки", padding="5")
        broadcast_media_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        broadcast_media_frame.columnconfigure(1, weight=1)
        
        # Photo
        ttk.Label(broadcast_media_frame, text="Фото:").grid(row=0, column=0, sticky=tk.W)
        self.broadcast_photo_file_var = tk.StringVar()
        self.broadcast_photo_file_entry = ttk.Entry(broadcast_media_frame, textvariable=self.broadcast_photo_file_var)
        self.broadcast_photo_file_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(5, 5))
        self.browse_broadcast_photo_btn = ttk.Button(broadcast_media_frame, text="Обзор...", command=self.browse_broadcast_photo_file)
        self.browse_broadcast_photo_btn.grid(row=0, column=2)
        
        # Audio
        ttk.Label(broadcast_media_frame, text="Аудио:").grid(row=1, column=0, sticky=tk.W)
        self.broadcast_audio_file_var = tk.StringVar()
        self.broadcast_audio_file_entry = ttk.Entry(broadcast_media_frame, textvariable=self.broadcast_audio_file_var)
        self.broadcast_audio_file_entry.grid(row=1, column=1, sticky=(tk.W, tk.E), padx=(5, 5))
        self.browse_broadcast_audio_btn = ttk.Button(broadcast_media_frame, text="Обзор...", command=self.browse_broadcast_audio_file)
        self.browse_broadcast_audio_btn.grid(row=1, column=2)
        
        # Document
        ttk.Label(broadcast_media_frame, text="Документ:").grid(row=2, column=0, sticky=tk.W)
        self.broadcast_document_file_var = tk.StringVar()
        self.broadcast_document_file_entry = ttk.Entry(broadcast_media_frame, textvariable=self.broadcast_document_file_var)
        self.broadcast_document_file_entry.grid(row=2, column=1, sticky=(tk.W, tk.E), padx=(5, 5))
        self.browse_broadcast_document_btn = ttk.Button(broadcast_media_frame, text="Обзор...", command=self.browse_broadcast_document_file)
        self.browse_broadcast_document_btn.grid(row=2, column=2)
        
        # GIF
        ttk.Label(broadcast_media_frame, text="GIF:").grid(row=3, column=0, sticky=tk.W)
        self.broadcast_gif_file_var = tk.StringVar()
        self.broadcast_gif_file_entry = ttk.Entry(broadcast_media_frame, textvariable=self.broadcast_gif_file_var)
        self.broadcast_gif_file_entry.grid(row=3, column=1, sticky=(tk.W, tk.E), padx=(5, 5))
        self.browse_broadcast_gif_btn = ttk.Button(broadcast_media_frame, text="Обзор...", command=self.browse_broadcast_gif_file)
        self.browse_broadcast_gif_btn.grid(row=3, column=2)
        
        # Message frame
        message_frame = ttk.LabelFrame(main_frame, text="Сообщение", padding="5")
        message_frame.grid(row=4, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        message_frame.columnconfigure(0, weight=1)
        message_frame.rowconfigure(1, weight=1)
        
        # Message file
        file_frame = ttk.Frame(message_frame)
        file_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 5))
        file_frame.columnconfigure(1, weight=1)
        
        ttk.Label(file_frame, text="Файл сообщения:").grid(row=0, column=0, sticky=tk.W)
        self.file_var = tk.StringVar()
        self.file_entry = ttk.Entry(file_frame, textvariable=self.file_var)
        self.file_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(5, 5))
        self.browse_btn = ttk.Button(file_frame, text="Обзор...", command=self.browse_file)
        self.browse_btn.grid(row=0, column=2)
        
        # Emoji button
        self.emoji_btn = ttk.Button(file_frame, text="😊 Эмодзи", command=lambda: self.open_emoji_picker(self.message_text))
        self.emoji_btn.grid(row=0, column=3, padx=(5, 0))
        
        # Message text
        self.message_text = scrolledtext.ScrolledText(message_frame, height=10)
        self.message_text.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(5, 0))
        
        # Buttons frame
        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.grid(row=5, column=0, columnspan=2, pady=(0, 10))
        
        self.send_btn = ttk.Button(buttons_frame, text="Отправить сообщение", command=self.send_message)
        self.send_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        self.clear_btn = ttk.Button(buttons_frame, text="Очистить", command=self.clear_message)
        self.clear_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        self.load_btn = ttk.Button(buttons_frame, text="Загрузить из файла", command=self.load_message_from_file)
        self.load_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        # Save message button
        self.save_btn = ttk.Button(buttons_frame, text="Сохранить в файл", command=lambda: self.save_message_to_file(self.message_text))
        self.save_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        # Copy from logs button
        self.copy_from_logs_btn = ttk.Button(buttons_frame, text="Копировать из логов", command=lambda: self.copy_from_logs(self.message_text))
        self.copy_from_logs_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        # Status frame
        status_frame = ttk.LabelFrame(main_frame, text="Статус", padding="5")
        status_frame.grid(row=6, column=0, columnspan=2, sticky=(tk.W, tk.E))
        status_frame.columnconfigure(0, weight=1)
        
        self.status_var = tk.StringVar(value="Готов к отправке")
        self.status_label = ttk.Label(status_frame, textvariable=self.status_var)
        self.status_label.grid(row=0, column=0, sticky=tk.W)
        
        # Progress bar
        self.progress = ttk.Progressbar(status_frame, mode='indeterminate')
        self.progress.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(5, 0))
        
        # Results text
        self.results_text = scrolledtext.ScrolledText(main_frame, height=8)
        self.results_text.grid(row=7, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(10, 0))
        self.results_text.insert(tk.END, "Результаты отправки будут отображаться здесь...\n")
        
        # Enable right-click context menu for results text
        self.create_context_menu(self.results_text)
        
    def create_direct_message_widgets(self):
        """Create UI widgets for direct message tab"""
        # Main frame
        main_frame = ttk.Frame(self.direct_message_tab, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Configure grid weights
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(3, weight=1)
        
        # Token frame
        token_frame = ttk.LabelFrame(main_frame, text="Токен бота", padding="5")
        token_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        token_frame.columnconfigure(1, weight=1)
        
        ttk.Label(token_frame, text="Токен:").grid(row=0, column=0, sticky=tk.W, padx=(0, 5))
        self.dm_token_var = tk.StringVar(value=self.token if self.token else "")
        self.dm_token_entry = ttk.Entry(token_frame, textvariable=self.dm_token_var, width=50)
        self.dm_token_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(0, 5))
        
        self.dm_refresh_token_btn = ttk.Button(token_frame, text="Обновить токен", command=self.refresh_token)
        self.dm_refresh_token_btn.grid(row=0, column=2)
        
        # Chat ID frame
        chat_id_frame = ttk.LabelFrame(main_frame, text="Получатель", padding="5")
        chat_id_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        chat_id_frame.columnconfigure(1, weight=1)
        
        ttk.Label(chat_id_frame, text="Chat ID:").grid(row=0, column=0, sticky=tk.W, padx=(0, 5))
        self.chat_id_var = tk.StringVar()
        self.chat_id_entry = ttk.Entry(chat_id_frame, textvariable=self.chat_id_var, width=30)
        self.chat_id_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(0, 5))
        
        self.load_user_btn = ttk.Button(chat_id_frame, text="Выбрать из списка", command=self.select_user_from_list)
        self.load_user_btn.grid(row=0, column=2, padx=(5, 0))
        
        # Options frame
        options_frame = ttk.Frame(main_frame)
        options_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        
        self.dm_silent_var = tk.BooleanVar()
        self.dm_silent_checkbox = ttk.Checkbutton(options_frame, text="Отправить без уведомления (тихо)", variable=self.dm_silent_var)
        self.dm_silent_checkbox.grid(row=0, column=0, sticky=tk.W)
        
        # Media files frame
        media_frame = ttk.LabelFrame(options_frame, text="Медиафайлы", padding="5")
        media_frame.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(20, 0))
        media_frame.columnconfigure(1, weight=1)
        
        # Photo
        ttk.Label(media_frame, text="Фото:").grid(row=0, column=0, sticky=tk.W)
        self.photo_file_var = tk.StringVar()
        self.photo_file_entry = ttk.Entry(media_frame, textvariable=self.photo_file_var, width=30)
        self.photo_file_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(5, 5))
        self.browse_photo_btn = ttk.Button(media_frame, text="Обзор...", command=self.browse_photo_file)
        self.browse_photo_btn.grid(row=0, column=2)
        
        # Audio
        ttk.Label(media_frame, text="Аудио:").grid(row=1, column=0, sticky=tk.W)
        self.audio_file_var = tk.StringVar()
        self.audio_file_entry = ttk.Entry(media_frame, textvariable=self.audio_file_var, width=30)
        self.audio_file_entry.grid(row=1, column=1, sticky=(tk.W, tk.E), padx=(5, 5))
        self.browse_audio_btn = ttk.Button(media_frame, text="Обзор...", command=self.browse_audio_file)
        self.browse_audio_btn.grid(row=1, column=2)
        
        # Document
        ttk.Label(media_frame, text="Документ:").grid(row=2, column=0, sticky=tk.W)
        self.document_file_var = tk.StringVar()
        self.document_file_entry = ttk.Entry(media_frame, textvariable=self.document_file_var, width=30)
        self.document_file_entry.grid(row=2, column=1, sticky=(tk.W, tk.E), padx=(5, 5))
        self.browse_document_btn = ttk.Button(media_frame, text="Обзор...", command=self.browse_document_file)
        self.browse_document_btn.grid(row=2, column=2)
        
        # GIF
        ttk.Label(media_frame, text="GIF:").grid(row=3, column=0, sticky=tk.W)
        self.gif_file_var = tk.StringVar()
        self.gif_file_entry = ttk.Entry(media_frame, textvariable=self.gif_file_var, width=30)
        self.gif_file_entry.grid(row=3, column=1, sticky=(tk.W, tk.E), padx=(5, 5))
        self.browse_gif_btn = ttk.Button(media_frame, text="Обзор...", command=self.browse_gif_file)
        self.browse_gif_btn.grid(row=3, column=2)
        
        # Message frame
        message_frame = ttk.LabelFrame(main_frame, text="Сообщение", padding="5")
        message_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        message_frame.columnconfigure(0, weight=1)
        message_frame.rowconfigure(1, weight=1)
        
        # Message file
        file_frame = ttk.Frame(message_frame)
        file_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 5))
        file_frame.columnconfigure(1, weight=1)
        
        ttk.Label(file_frame, text="Файл сообщения:").grid(row=0, column=0, sticky=tk.W)
        self.dm_file_var = tk.StringVar()
        self.dm_file_entry = ttk.Entry(file_frame, textvariable=self.dm_file_var)
        self.dm_file_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(5, 5))
        self.dm_browse_btn = ttk.Button(file_frame, text="Обзор...", command=self.browse_file_dm)
        self.dm_browse_btn.grid(row=0, column=2)
        
        # Emoji button
        self.dm_emoji_btn = ttk.Button(file_frame, text="😊 Эмодзи", command=lambda: self.open_emoji_picker(self.dm_message_text))
        self.dm_emoji_btn.grid(row=0, column=3, padx=(5, 0))
        
        # Message text
        self.dm_message_text = scrolledtext.ScrolledText(message_frame, height=10)
        self.dm_message_text.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(5, 0))
        
        # Buttons frame
        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.grid(row=4, column=0, columnspan=2, pady=(0, 10))
        
        self.dm_send_btn = ttk.Button(buttons_frame, text="Отправить сообщение", command=self.send_direct_message)
        self.dm_send_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        self.dm_clear_btn = ttk.Button(buttons_frame, text="Очистить", command=self.clear_direct_message)
        self.dm_clear_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        self.dm_load_btn = ttk.Button(buttons_frame, text="Загрузить из файла", command=self.load_direct_message_from_file)
        self.dm_load_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        # Save message button
        self.dm_save_btn = ttk.Button(buttons_frame, text="Сохранить в файл", command=lambda: self.save_message_to_file(self.dm_message_text))
        self.dm_save_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        # Copy from logs button
        self.dm_copy_from_logs_btn = ttk.Button(buttons_frame, text="Копировать из логов", command=lambda: self.copy_from_logs(self.dm_message_text))
        self.dm_copy_from_logs_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        # Status frame
        status_frame = ttk.LabelFrame(main_frame, text="Статус", padding="5")
        status_frame.grid(row=5, column=0, columnspan=2, sticky=(tk.W, tk.E))
        status_frame.columnconfigure(0, weight=1)
        
        self.dm_status_var = tk.StringVar(value="Готов к отправке")
        self.dm_status_label = ttk.Label(status_frame, textvariable=self.dm_status_var)
        self.dm_status_label.grid(row=0, column=0, sticky=tk.W)
        
        # Progress bar
        self.dm_progress = ttk.Progressbar(status_frame, mode='indeterminate')
        self.dm_progress.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(5, 0))
        
        # Results text
        self.dm_results_text = scrolledtext.ScrolledText(main_frame, height=8)
        self.dm_results_text.grid(row=6, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(10, 0))
        self.dm_results_text.insert(tk.END, "Результаты отправки будут отображаться здесь...\n")
        
        # Enable right-click context menu for results text
        self.create_context_menu(self.dm_results_text)
        
    def refresh_token(self):
        """Refresh token from .env file"""
        load_dotenv(".env", override=True)
        self.token = os.getenv("TG_BOT_TOKEN")
        self.token_var.set(self.token if self.token else "")
        self.dm_token_var.set(self.token if self.token else "")
        if self.token:
            self.bot = telebot.TeleBot(self.token)
            self.status_var.set("Токен обновлён")
            self.dm_status_var.set("Токен обновлён")
        else:
            self.bot = None
            self.status_var.set("Токен не найден в .env файле")
            self.dm_status_var.set("Токен не найден в .env файле")
            
    def browse_file(self):
        """Browse for message file"""
        filename = filedialog.askopenfilename(
            title="Выберите файл с сообщением",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        if filename:
            self.file_var.set(filename)
            
    def browse_file_dm(self):
        """Browse for message file (direct message tab)"""
        filename = filedialog.askopenfilename(
            title="Выберите файл с сообщением",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        if filename:
            self.dm_file_var.set(filename)
            
    def browse_photo_file(self):
        """Browse for photo file"""
        filename = filedialog.askopenfilename(
            title="Выберите фото для отправки",
            filetypes=[("Image files", "*.jpg *.jpeg *.png *.gif *.bmp *.webp"), ("All files", "*.*")]
        )
        if filename:
            self.photo_file_var.set(filename)
            
    def browse_broadcast_photo_file(self):
        """Browse for broadcast photo file"""
        filename = filedialog.askopenfilename(
            title="Выберите фото для массовой рассылки",
            filetypes=[("Image files", "*.jpg *.jpeg *.png *.gif *.bmp *.webp"), ("All files", "*.*")]
        )
        if filename:
            self.broadcast_photo_file_var.set(filename)
            
    def browse_audio_file(self):
        """Browse for audio file"""
        filename = filedialog.askopenfilename(
            title="Выберите аудио для отправки",
            filetypes=[("Audio files", "*.mp3 *.wav *.ogg *.flac *.m4a"), ("All files", "*.*")]
        )
        if filename:
            self.audio_file_var.set(filename)
            
    def browse_broadcast_audio_file(self):
        """Browse for broadcast audio file"""
        filename = filedialog.askopenfilename(
            title="Выберите аудио для массовой рассылки",
            filetypes=[("Audio files", "*.mp3 *.wav *.ogg *.flac *.m4a"), ("All files", "*.*")]
        )
        if filename:
            self.broadcast_audio_file_var.set(filename)
            
    def browse_document_file(self):
        """Browse for document file"""
        filename = filedialog.askopenfilename(
            title="Выберите документ для отправки",
            filetypes=[("Document files", "*.pdf *.doc *.docx *.txt *.xls *.xlsx *.ppt *.pptx"), ("All files", "*.*")]
        )
        if filename:
            self.document_file_var.set(filename)
            
    def browse_broadcast_document_file(self):
        """Browse for broadcast document file"""
        filename = filedialog.askopenfilename(
            title="Выберите документ для массовой рассылки",
            filetypes=[("Document files", "*.pdf *.doc *.docx *.txt *.xls *.xlsx *.ppt *.pptx"), ("All files", "*.*")]
        )
        if filename:
            self.broadcast_document_file_var.set(filename)
            
    def browse_gif_file(self):
        """Browse for GIF file"""
        filename = filedialog.askopenfilename(
            title="Выберите GIF для отправки",
            filetypes=[("GIF files", "*.gif"), ("All files", "*.*")]
        )
        if filename:
            self.gif_file_var.set(filename)
            
    def browse_broadcast_gif_file(self):
        """Browse for broadcast GIF file"""
        filename = filedialog.askopenfilename(
            title="Выберите GIF для массовой рассылки",
            filetypes=[("GIF files", "*.gif"), ("All files", "*.*")]
        )
        if filename:
            self.broadcast_gif_file_var.set(filename)
            
    def save_message_to_file(self, text_widget):
        """Save message from text widget to file"""
        message_text = text_widget.get(1.0, tk.END).strip()
        if not message_text:
            messagebox.showwarning("Предупреждение", "Нет текста для сохранения")
            return
            
        filename = filedialog.asksaveasfilename(
            title="Сохранить сообщение в файл",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        if filename:
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(message_text)
                messagebox.showinfo("Успех", f"Сообщение сохранено в файл: {filename}")
            except Exception as e:
                messagebox.showerror("Ошибка", f"Не удалось сохранить файл:\n{str(e)}")
                
    def copy_from_logs(self, text_widget):
        """Copy selected text from logs to message text widget"""
        # We'll implement this functionality in the context menu
        pass
                
    def load_message_from_file(self):
        """Load message from file"""
        filename = self.file_var.get()
        if not filename:
            messagebox.showwarning("Предупреждение", "Сначала выберите файл")
            return
            
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                content = f.read()
            self.message_text.delete(1.0, tk.END)
            self.message_text.insert(tk.END, content)
            self.status_var.set(f"Сообщение загружено из {filename}")
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось загрузить файл:\n{str(e)}")
            
    def load_direct_message_from_file(self):
        """Load direct message from file"""
        filename = self.dm_file_var.get()
        if not filename:
            messagebox.showwarning("Предупреждение", "Сначала выберите файл")
            return
            
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                content = f.read()
            self.dm_message_text.delete(1.0, tk.END)
            self.dm_message_text.insert(tk.END, content)
            self.dm_status_var.set(f"Сообщение загружено из {filename}")
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось загрузить файл:\n{str(e)}")
            
    def clear_message(self):
        """Clear message text"""
        self.message_text.delete(1.0, tk.END)
        self.results_text.delete(1.0, tk.END)
        self.results_text.insert(tk.END, "Результаты отправки будут отображаться здесь...\n")
        self.status_var.set("Сообщение очищено")
        
    def clear_direct_message(self):
        """Clear direct message text"""
        self.dm_message_text.delete(1.0, tk.END)
        self.dm_results_text.delete(1.0, tk.END)
        self.dm_results_text.insert(tk.END, "Результаты отправки будут отображаться здесь...\n")
        self.dm_status_var.set("Сообщение очищено")
        
    def get_all_users(self):
        """Get all Telegram users from the database"""
        try:
            conn = sqlite3.connect('bot_database.db')
            cursor = conn.cursor()
            
            if self.mode_var.get() == "test":
                # In test mode, only get the test user
                cursor.execute('''
                    SELECT chat_id, twitch_username 
                    FROM telegram_users 
                    WHERE twitch_username = ?
                ''', ("lonely_fr",))
            else:
                # In production mode, get all users
                cursor.execute('''
                    SELECT chat_id, twitch_username 
                    FROM telegram_users 
                    WHERE twitch_username IS NOT NULL
                ''')
            
            users = cursor.fetchall()
            conn.close()
            
            return [{'chat_id': user[0], 'twitch_username': user[1]} for user in users]
        except Exception as e:
            self.append_result(f"Ошибка получения пользователей из базы данных: {e}\n")
            return []
            
    def select_user_from_list(self):
        """Open a dialog to select user from list"""
        # Create a new window
        user_select_window = tk.Toplevel(self.root)
        user_select_window.title("Выбор пользователя")
        user_select_window.geometry("500x400")
        
        # Create listbox with scrollbar
        list_frame = ttk.Frame(user_select_window)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        user_listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set)
        user_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=user_listbox.yview)
        
        # Load users from database
        try:
            conn = sqlite3.connect('bot_database.db')
            cursor = conn.cursor()
            cursor.execute('''
                SELECT chat_id, twitch_username 
                FROM telegram_users 
                WHERE twitch_username IS NOT NULL
            ''')
            users = cursor.fetchall()
            conn.close()
            
            # Add users to listbox
            for user in users:
                display_text = f"{user[1]} (ID: {user[0]})" if user[1] else f"ID: {user[0]}"
                user_listbox.insert(tk.END, display_text)
                # Store the chat_id as a hidden value
                user_listbox.itemconfig(tk.END, {'fg': 'black'})
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось загрузить список пользователей:\n{str(e)}")
            user_select_window.destroy()
            return
            
        def on_select():
            selection = user_listbox.curselection()
            if selection:
                index = selection[0]
                chat_id = users[index][0]  # Get chat_id from the users list
                self.chat_id_var.set(str(chat_id))
                user_select_window.destroy()
            else:
                messagebox.showwarning("Предупреждение", "Выберите пользователя из списка")
                
        def on_cancel():
            user_select_window.destroy()
            
        # Buttons
        button_frame = ttk.Frame(user_select_window)
        button_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        select_btn = ttk.Button(button_frame, text="Выбрать", command=on_select)
        select_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        cancel_btn = ttk.Button(button_frame, text="Отмена", command=on_cancel)
        cancel_btn.pack(side=tk.LEFT)
        
        # Make the window modal
        user_select_window.transient(self.root)
        user_select_window.grab_set()
        self.root.wait_window(user_select_window)
        
    def open_emoji_picker(self, text_widget):
        """Open emoji picker window"""
        emoji_window = tk.Toplevel(self.root)
        emoji_window.title("Выбор эмодзи")
        emoji_window.geometry("400x300")
        emoji_window.resizable(False, False)
        
        # Make window modal
        emoji_window.transient(self.root)
        emoji_window.grab_set()
        
        # Create notebook for emoji categories
        emoji_notebook = ttk.Notebook(emoji_window)
        emoji_notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Create frames for each emoji category
        for category_name, emojis in self.emojis.items():
            frame = ttk.Frame(emoji_notebook)
            emoji_notebook.add(frame, text=category_name.capitalize())
            
            # Create canvas and scrollbar for emojis
            canvas = tk.Canvas(frame)
            scrollbar = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview)
            scrollable_frame = ttk.Frame(canvas)
            
            scrollable_frame.bind(
                "<Configure>",
                lambda e: canvas.configure(
                    scrollregion=canvas.bbox("all")
                )
            )
            
            canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)
            
            # Add emojis to the frame
            row, col = 0, 0
            for emoji in emojis:
                btn = tk.Button(
                    scrollable_frame, 
                    text=emoji, 
                    font=("Arial", 14),
                    command=lambda e=emoji: self.insert_emoji(text_widget, e),
                    width=3,
                    height=1
                )
                btn.grid(row=row, column=col, padx=2, pady=2)
                col += 1
                if col > 9:  # 10 emojis per row
                    col = 0
                    row += 1
            
            canvas.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")
            
    def insert_emoji(self, text_widget, emoji):
        """Insert selected emoji into text widget"""
        text_widget.insert(tk.INSERT, emoji)
        text_widget.focus()
        
    def create_context_menu(self, text_widget):
        """Create context menu for text widget"""
        context_menu = tk.Menu(text_widget, tearoff=0)
        context_menu.add_command(label="Копировать", command=lambda: self.copy_text(text_widget))
        context_menu.add_command(label="Вставить", command=lambda: self.paste_text(text_widget))
        context_menu.add_command(label="Вырезать", command=lambda: self.cut_text(text_widget))
        context_menu.add_separator()
        context_menu.add_command(label="Выделить всё", command=lambda: self.select_all_text(text_widget))
        
        def show_context_menu(event):
            context_menu.tk_popup(event.x_root, event.y_root)
            
        text_widget.bind("<Button-3>", show_context_menu)
        
    def copy_text(self, text_widget):
        """Copy selected text to clipboard"""
        try:
            selected_text = text_widget.selection_get()
            text_widget.clipboard_clear()
            text_widget.clipboard_append(selected_text)
        except tk.TclError:
            # No text selected
            pass
            
    def paste_text(self, text_widget):
        """Paste text from clipboard"""
        try:
            clipboard_text = text_widget.clipboard_get()
            text_widget.insert(tk.INSERT, clipboard_text)
        except tk.TclError:
            # No text in clipboard
            pass
            
    def cut_text(self, text_widget):
        """Cut selected text"""
        try:
            selected_text = text_widget.selection_get()
            text_widget.clipboard_clear()
            text_widget.clipboard_append(selected_text)
            text_widget.delete("sel.first", "sel.last")
        except tk.TclError:
            # No text selected
            pass
            
    def select_all_text(self, text_widget):
        """Select all text in widget"""
        text_widget.tag_add("sel", "1.0", "end")
        
    def append_result(self, text):
        """Append text to results"""
        self.results_text.insert(tk.END, text)
        self.results_text.see(tk.END)
        self.root.update_idletasks()
        
    def append_dm_result(self, text):
        """Append text to direct message results"""
        self.dm_results_text.insert(tk.END, text)
        self.dm_results_text.see(tk.END)
        self.root.update_idletasks()
        
    def send_message_thread(self):
        """Send message in a separate thread"""
        try:
            # Get message text
            message_text = self.message_text.get(1.0, tk.END).strip()
            
            # Get media files for broadcast
            broadcast_photo_file = self.broadcast_photo_file_var.get().strip()
            broadcast_audio_file = self.broadcast_audio_file_var.get().strip()
            broadcast_document_file = self.broadcast_document_file_var.get().strip()
            broadcast_gif_file = self.broadcast_gif_file_var.get().strip()
            
            # Validate inputs
            if not message_text and not broadcast_photo_file and not broadcast_audio_file and not broadcast_document_file and not broadcast_gif_file:
                self.status_var.set("Ошибка: Нет текста сообщения и медиафайлов")
                self.progress.stop()
                self.send_btn.config(state='normal')
                self.is_sending = False
                return
                
            # Get users
            users = self.get_all_users()
            if not users:
                self.status_var.set("Нет пользователей для отправки")
                self.progress.stop()
                self.send_btn.config(state='normal')
                self.is_sending = False
                return
                
            # Send messages
            successful_sends = 0
            failed_sends = 0
            
            self.append_result(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Начало отправки сообщения {len(users)} пользователям...\n")
            self.append_result(f"Режим: {'Тестовый (только lonely_fr)' if self.mode_var.get() == 'test' else 'Всем пользователям'}\n")
            self.append_result(f"Уведомление: {'Выключено' if self.silent_var.get() else 'Включено'}\n")
            
            if broadcast_photo_file:
                self.append_result(f"Файл фото: {broadcast_photo_file}\n")
            if broadcast_audio_file:
                self.append_result(f"Файл аудио: {broadcast_audio_file}\n")
            if broadcast_document_file:
                self.append_result(f"Файл документа: {broadcast_document_file}\n")
            if broadcast_gif_file:
                self.append_result(f"Файл GIF: {broadcast_gif_file}\n")
                
            self.append_result("-" * 50 + "\n")
            
            for user in users:
                if not self.is_sending:  # Check if sending was cancelled
                    break
                    
                try:
                    # Send photo if specified
                    if broadcast_photo_file and os.path.exists(broadcast_photo_file):
                        with open(broadcast_photo_file, 'rb') as photo:
                            self.bot.send_photo(
                                user['chat_id'], 
                                photo, 
                                caption=message_text if message_text else "",
                                disable_notification=self.silent_var.get()
                            )
                        successful_sends += 1
                        self.append_result(f"✓ Фото с сообщением отправлено {user['twitch_username']} (chat_id: {user['chat_id']})\n")
                        continue  # Skip to next user after sending photo
                    
                    # Send audio if specified
                    if broadcast_audio_file and os.path.exists(broadcast_audio_file):
                        with open(broadcast_audio_file, 'rb') as audio:
                            self.bot.send_audio(
                                user['chat_id'], 
                                audio, 
                                caption=message_text if message_text else "",
                                disable_notification=self.silent_var.get()
                            )
                        successful_sends += 1
                        self.append_result(f"✓ Аудио с сообщением отправлено {user['twitch_username']} (chat_id: {user['chat_id']})\n")
                        continue  # Skip to next user after sending audio
                    
                    # Send document if specified
                    if broadcast_document_file and os.path.exists(broadcast_document_file):
                        with open(broadcast_document_file, 'rb') as document:
                            self.bot.send_document(
                                user['chat_id'], 
                                document, 
                                caption=message_text if message_text else "",
                                disable_notification=self.silent_var.get()
                            )
                        successful_sends += 1
                        self.append_result(f"✓ Документ с сообщением отправлен {user['twitch_username']} (chat_id: {user['chat_id']})\n")
                        continue  # Skip to next user after sending document
                    
                    # Send GIF if specified
                    if broadcast_gif_file and os.path.exists(broadcast_gif_file):
                        with open(broadcast_gif_file, 'rb') as gif:
                            self.bot.send_animation(
                                user['chat_id'], 
                                gif, 
                                caption=message_text if message_text else "",
                                disable_notification=self.silent_var.get()
                            )
                        successful_sends += 1
                        self.append_result(f"✓ GIF с сообщением отправлен {user['twitch_username']} (chat_id: {user['chat_id']})\n")
                        continue  # Skip to next user after sending GIF
                    
                    # Send text message only if no media files were sent
                    if message_text:
                        self.bot.send_message(
                            user['chat_id'], 
                            message_text, 
                            disable_notification=self.silent_var.get()
                        )
                        successful_sends += 1
                        self.append_result(f"✓ Сообщение отправлено {user['twitch_username']} (chat_id: {user['chat_id']})\n")
                    else:
                        self.append_result(f"✗ Нет контента для отправки {user['twitch_username']} (chat_id: {user['chat_id']})\n")
                        failed_sends += 1
                        
                except telebot.apihelper.ApiException as e:
                    failed_sends += 1
                    self.append_result(f"✗ Ошибка отправки {user['twitch_username']} (chat_id: {user['chat_id']}): {str(e)}\n")
                except Exception as e:
                    failed_sends += 1
                    self.append_result(f"✗ Неожиданная ошибка {user['twitch_username']} (chat_id: {user['chat_id']}): {str(e)}\n")
                    
            # Summary
            self.append_result("-" * 50 + "\n")
            self.append_result("ИТОГИ ОТПРАВКИ:\n")
            self.append_result(f"Всего пользователей: {len(users)}\n")
            self.append_result(f"Успешно отправлено: {successful_sends}\n")
            self.append_result(f"Ошибок: {failed_sends}\n")
            self.append_result("=" * 50 + "\n")
            
            self.status_var.set(f"Отправка завершена: {successful_sends} успешно, {failed_sends} ошибок")
            
        except Exception as e:
            self.status_var.set(f"Ошибка: {str(e)}")
            self.append_result(f"Общая ошибка: {str(e)}\n")
        finally:
            self.progress.stop()
            self.send_btn.config(state='normal')
            self.is_sending = False
            
    def send_direct_message_thread(self):
        """Send direct message in a separate thread"""
        try:
            # Get message text
            message_text = self.dm_message_text.get(1.0, tk.END).strip()
            
            # Get chat_id
            chat_id = self.chat_id_var.get().strip()
            if not chat_id:
                self.dm_status_var.set("Ошибка: Не указан Chat ID")
                self.dm_progress.stop()
                self.dm_send_btn.config(state='normal')
                self.is_sending = False
                return
                
            try:
                chat_id = int(chat_id)
            except ValueError:
                self.dm_status_var.set("Ошибка: Неверный формат Chat ID")
                self.dm_progress.stop()
                self.dm_send_btn.config(state='normal')
                self.is_sending = False
                return
                
            # Get media files
            photo_file = self.photo_file_var.get().strip()
            audio_file = self.audio_file_var.get().strip()
            document_file = self.document_file_var.get().strip()
            gif_file = self.gif_file_var.get().strip()
            
            # Validate inputs
            if not message_text and not photo_file and not audio_file and not document_file and not gif_file:
                self.dm_status_var.set("Ошибка: Нет текста сообщения и медиафайлов")
                self.dm_progress.stop()
                self.dm_send_btn.config(state='normal')
                self.is_sending = False
                return
                
            # Send message
            self.append_dm_result(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Отправка сообщения пользователю с chat_id: {chat_id}...\n")
            
            successful_sends = 0
            failed_sends = 0
            
            try:
                # Send photo if specified
                if photo_file and os.path.exists(photo_file):
                    with open(photo_file, 'rb') as photo:
                        self.bot.send_photo(
                            chat_id, 
                            photo, 
                            caption=message_text if message_text else "",
                            disable_notification=self.dm_silent_var.get()
                        )
                    self.append_dm_result(f"✓ Фото успешно отправлено пользователю с chat_id: {chat_id}\n")
                    successful_sends += 1
                
                # Send audio if specified
                elif audio_file and os.path.exists(audio_file):
                    with open(audio_file, 'rb') as audio:
                        self.bot.send_audio(
                            chat_id, 
                            audio, 
                            caption=message_text if message_text else "",
                            disable_notification=self.dm_silent_var.get()
                        )
                    self.append_dm_result(f"✓ Аудио успешно отправлено пользователю с chat_id: {chat_id}\n")
                    successful_sends += 1
                
                # Send document if specified
                elif document_file and os.path.exists(document_file):
                    with open(document_file, 'rb') as document:
                        self.bot.send_document(
                            chat_id, 
                            document, 
                            caption=message_text if message_text else "",
                            disable_notification=self.dm_silent_var.get()
                        )
                    self.append_dm_result(f"✓ Документ успешно отправлен пользователю с chat_id: {chat_id}\n")
                    successful_sends += 1
                
                # Send GIF if specified
                elif gif_file and os.path.exists(gif_file):
                    with open(gif_file, 'rb') as gif:
                        self.bot.send_animation(
                            chat_id, 
                            gif, 
                            caption=message_text if message_text else "",
                            disable_notification=self.dm_silent_var.get()
                        )
                    self.append_dm_result(f"✓ GIF успешно отправлен пользователю с chat_id: {chat_id}\n")
                    successful_sends += 1
                
                # Send text message if there's text and no media was sent
                elif message_text and successful_sends == 0:
                    self.bot.send_message(
                        chat_id, 
                        message_text,
                        disable_notification=self.dm_silent_var.get()
                    )
                    self.append_dm_result(f"✓ Сообщение успешно отправлено пользователю с chat_id: {chat_id}\n")
                    successful_sends += 1
                    
                if successful_sends > 0:
                    self.dm_status_var.set("Сообщение успешно отправлено")
                else:
                    self.dm_status_var.set("Ошибка отправки сообщения")
                    
            except telebot.apihelper.ApiException as e:
                self.append_dm_result(f"✗ Ошибка отправки пользователю с chat_id: {chat_id}: {str(e)}\n")
                self.dm_status_var.set("Ошибка отправки сообщения")
                failed_sends += 1
            except Exception as e:
                self.append_dm_result(f"✗ Неожиданная ошибка при отправке пользователю с chat_id: {chat_id}: {str(e)}\n")
                self.dm_status_var.set("Ошибка отправки сообщения")
                failed_sends += 1
                
        except Exception as e:
            self.dm_status_var.set(f"Ошибка: {str(e)}")
            self.append_dm_result(f"Общая ошибка: {str(e)}\n")
        finally:
            self.dm_progress.stop()
            self.dm_send_btn.config(state='normal')
            self.is_sending = False
            
    def send_message(self):
        """Send message to users"""
        # Validate token
        token = self.token_var.get()
        if not token:
            messagebox.showwarning("Предупреждение", "Введите токен бота")
            return
            
        # Update bot if token changed
        if not self.bot or self.token != token:
            try:
                self.bot = telebot.TeleBot(token)
                self.token = token
            except Exception as e:
                messagebox.showerror("Ошибка", f"Неверный токен бота:\n{str(e)}")
                return
                
        # Check if already sending
        if self.is_sending:
            # Cancel sending
            self.is_sending = False
            self.status_var.set("Отправка отменена")
            self.progress.stop()
            self.send_btn.config(state='normal')
            return
            
        # Start sending in a separate thread
        self.is_sending = True
        self.send_btn.config(text="Отменить отправку", state='normal')
        self.status_var.set("Отправка сообщения...")
        self.progress.start()
        
        # Start thread
        thread = threading.Thread(target=self.send_message_thread)
        thread.daemon = True
        thread.start()
        
    def send_direct_message(self):
        """Send direct message to a specific user"""
        # Validate token
        token = self.dm_token_var.get()
        if not token:
            messagebox.showwarning("Предупреждение", "Введите токен бота")
            return
            
        # Update bot if token changed
        if not self.bot or self.token != token:
            try:
                self.bot = telebot.TeleBot(token)
                self.token = token
            except Exception as e:
                messagebox.showerror("Ошибка", f"Неверный токен бота:\n{str(e)}")
                return
                
        # Check if already sending
        if self.is_sending:
            # Cancel sending
            self.is_sending = False
            self.dm_status_var.set("Отправка отменена")
            self.dm_progress.stop()
            self.dm_send_btn.config(state='normal')
            return
            
        # Start sending in a separate thread
        self.is_sending = True
        self.dm_send_btn.config(text="Отменить отправку", state='normal')
        self.dm_status_var.set("Отправка сообщения...")
        self.dm_progress.start()
        
        # Start thread
        thread = threading.Thread(target=self.send_direct_message_thread)
        thread.daemon = True
        thread.start()

def main():
    root = tk.Tk()
    app = TelegramMessageSenderUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()