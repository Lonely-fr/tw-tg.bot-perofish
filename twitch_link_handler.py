import sqlite3
from twitchio.ext import commands

def setup_twitch_link_handler(bot, db_path: str = 'bot_database.db'):
    """
    Setup the Twitch bot command for handling Telegram linking codes
    """
    
    @bot.command(name='linktg')
    async def link_telegram_command(ctx):
        """
        Command to handle linking with Telegram. 
        Users send their Telegram linking code with this command.
        Usage: !linktg <code>
        """
        # Get the message content and split to get the code
        parts = ctx.message.content.split()
        if len(parts) < 2:
            await ctx.send("Использование: !linktg <код> Получить код - https://t.me/PeroFish_bot")
            return
            
        link_code = parts[1].strip().upper()
        
        # Connect to database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Find Telegram user with this code
        cursor.execute('''
            SELECT chat_id, twitch_username FROM telegram_users 
            WHERE link_code = ?
        ''', (link_code,))
        
        result = cursor.fetchone()
        
        if not result:
            await ctx.send("Неверный код привязки. Проверьте код и попробуйте снова.")
            conn.close()
            return
            
        chat_id, existing_twitch_user = result
        
        # Check if code is already used by the same user
        if existing_twitch_user and existing_twitch_user == ctx.author.name.lower():
            await ctx.send("Этот код уже использован для привязки вашего аккаунта.")
            conn.close()
            return
            
        # Check if user exists in players table
        cursor.execute('SELECT username FROM players WHERE username = ?', (ctx.author.name.lower(),))
        player_exists = cursor.fetchone()
        
        if not player_exists:
            # Create player if not exists
            cursor.execute('INSERT OR IGNORE INTO players (username) VALUES (?)', (ctx.author.name.lower(),))
            conn.commit()
        
        # Link the accounts
        cursor.execute('''
            UPDATE telegram_users 
            SET twitch_username = ?, link_code = NULL
            WHERE link_code = ?
        ''', (ctx.author.name.lower(), link_code))
        
        conn.commit()
        conn.close()
        
        # Send confirmation to Twitch chat
        await ctx.send(f"@{ctx.author.name}, ваш аккаунт успешно привязан к Telegram!")
        
        # Note: In a complete implementation, you would also send a message to the Telegram user
        # But that would require access to the Telegram bot instance

# Usage:
# In your main Twitch bot file, you would call:
# setup_twitch_link_handler(bot)  # Pass your bot instance