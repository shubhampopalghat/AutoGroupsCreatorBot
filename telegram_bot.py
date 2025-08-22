# Save this file as telegram_bot.py
import logging
import json
import os
import asyncio
import threading
import queue
import time
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler, ConversationHandler,
    ContextTypes, filters
)
from telegram.constants import ParseMode

from BigBotFinal import run_group_creation_process, API_ID, API_HASH
from telethon.sync import TelegramClient
from telethon.errors import SessionPasswordNeededError

# --- Configuration ---
CONFIG_FILE = 'bot_config.json'
SESSIONS_DIR = 'sessions'

# --- FIXED SETTINGS ---
FIXED_DELAY = 2
FIXED_MESSAGES_PER_GROUP = 10
FIXED_MESSAGES = [
    "💻 Code crafted: @OldGcHub", "🖥️ Innovation lives here: @OldGcHub",
    "⚡ Built for speed: @OldGcHub", "🔧 Tools of the trade: @OldGcHub",
    "🛠️ Engineered with precision: @OldGcHub", "📡 Connected globally: @OldGcHub",
    "🤖 Future-ready: @OldGcHub", "💾 Data secured: @OldGcHub",
    "🌐 Bridging tech & ideas: @OldGcHub", "🚀 Launching progress: @OldGcHub"
]

# States for conversation
(GET_PHONE, GET_LOGIN_CODE, GET_2FA_PASS, GET_GROUP_COUNT) = range(4)
ACTIVE_PROCESSES = {}

# --- Helper Functions ---
def load_config():
    if not os.path.exists(SESSIONS_DIR): os.makedirs(SESSIONS_DIR)
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'w') as f:
            json.dump({"BOT_TOKEN": "YOUR_BOT_TOKEN_HERE", "OWNER_ID": 0, "ADMIN_IDS": []}, f, indent=4)
        print("CONFIG CREATED: Please edit 'bot_config.json' with your bot token and owner ID.")
        exit()
    with open(CONFIG_FILE, 'r') as f: return json.load(f)

def save_config(config_data):
    with open(CONFIG_FILE, 'w') as f: json.dump(config_data, f, indent=4)

config = load_config()
OWNER_ID, ADMIN_IDS = config['OWNER_ID'], config['ADMIN_IDS']

def authorized(func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = update.effective_user.id
        if user_id == OWNER_ID or user_id in ADMIN_IDS:
            return await func(update, context, *args, **kwargs)
        else: await update.message.reply_text("⛔ You are not authorized to use this bot.")
    return wrapper

async def send_login_success_details(update: Update, context: ContextTypes.DEFAULT_TYPE, session_path: str, phone: str):
    """Connects to a session, sends details, and then disconnects."""
    client = TelegramClient(session_path, API_ID, API_HASH)
    await client.connect()
    me = await client.get_me()
    details_text = (
        f"✅ **Account Ready!**\n\n"
        f"👤 **Name:** {me.first_name} {me.last_name or ''}\n"
        f"🔖 **Username:** @{me.username or 'N/A'}\n"
        f"🆔 **ID:** `{me.id}`"
    )
    await update.message.reply_text(details_text, parse_mode=ParseMode.MARKDOWN)
    await context.bot.send_document(
        chat_id=update.effective_chat.id,
        document=open(f"{session_path}.session", 'rb'),
        caption="Here is the session file for this account."
    )
    await client.disconnect()
    context.user_data['account_info'] = {'session_path': session_path, 'phone': phone}
    await update.message.reply_text("Now, how many groups should this account create?")
    return GET_GROUP_COUNT

# --- Bot Command Handlers ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = "Hello! You are not authorized."
    if user_id == OWNER_ID or user_id in ADMIN_IDS:
        text = ("Hello! I'm ready to work.\n\n"
                "🔹 /run - Start the group creation process.\n"
                "🔹 /logged_accounts - View your saved accounts.\n"
                "🔹 /cancel - Stop the current setup process.\n")
        if user_id == OWNER_ID:
            text += ("\n**Owner Commands:**\n"
                     "🔸 /add_admin <user_id>\n🔸 /remove_admin <user_id>\n🔸 /list_admins")
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

@authorized
async def admin_commands(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("⛔ Only the owner can manage admins.")
        return
    command = update.message.text.split()[0]
    try:
        if command == '/add_admin':
            user_id = int(context.args[0])
            if user_id not in ADMIN_IDS:
                ADMIN_IDS.append(user_id)
                config['ADMIN_IDS'] = ADMIN_IDS
                save_config(config)
                await update.message.reply_text(f"✅ User {user_id} added as an admin.")
            else: await update.message.reply_text("User is already an admin.")
        elif command == '/remove_admin':
            user_id = int(context.args[0])
            if user_id in ADMIN_IDS:
                ADMIN_IDS.remove(user_id)
                config['ADMIN_IDS'] = ADMIN_IDS
                save_config(config)
                await update.message.reply_text(f"✅ User {user_id} removed from admins.")
            else: await update.message.reply_text("User is not an admin.")
    except (IndexError, ValueError):
        await update.message.reply_text(f"Usage: {command} <user_id>")

@authorized
async def list_admins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = "Configured Admins:\n" + "\n".join(f"🔹 `{admin_id}`" for admin_id in ADMIN_IDS) if ADMIN_IDS else "No admins configured."
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

@authorized
async def logged_accounts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_session_dir = os.path.join(SESSIONS_DIR, str(user_id))
    if not os.path.exists(user_session_dir) or not os.listdir(user_session_dir):
        await update.message.reply_text("You have no accounts logged in yet.")
        return
    sessions = [s.replace('.session', '') for s in os.listdir(user_session_dir) if s.endswith('.session')]
    text = "Your saved accounts (sessions):\n" + "\n".join([f"🔹 `{s}`" for s in sessions])
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

@authorized
async def run_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if ACTIVE_PROCESSES.get(user_id):
        await update.message.reply_text("⚠️ You already have a process running.")
        return ConversationHandler.END
    context.user_data.clear()
    await update.message.reply_text("Please send the phone number of the account you want to use (e.g., +15551234567).")
    return GET_PHONE

async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id, phone = update.effective_user.id, update.message.text.strip()
    session_name = phone.replace('+', '')
    user_session_dir = os.path.join(SESSIONS_DIR, str(user_id))
    session_path = os.path.join(user_session_dir, session_name)
    os.makedirs(user_session_dir, exist_ok=True)
    
    if os.path.exists(f"{session_path}.session"):
        return await send_login_success_details(update, context, session_path, phone)
    else:
        client = TelegramClient(session_path, API_ID, API_HASH)
        await client.connect()
        try:
            sent_code = await client.send_code_request(phone)
            context.user_data.update({'login_client': client, 'login_phone': phone, 'login_hash': sent_code.phone_code_hash})
            await update.message.reply_text("I've sent a code to that number. Please send me the code.")
            return GET_LOGIN_CODE
        except Exception as e:
            await update.message.reply_text(f"❌ **Login Failed!** Could not send code. Please check the phone number and /run again.\n\n`Error: {e}`", parse_mode=ParseMode.MARKDOWN)
            await client.disconnect()
            return ConversationHandler.END

async def get_login_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    code, client, phone, code_hash = update.message.text.strip(), context.user_data['login_client'], context.user_data['login_phone'], context.user_data['login_hash']
    try:
        await client.sign_in(phone, code, phone_code_hash=code_hash)
        # Login success, now get details and proceed
        return await send_login_success_details(update, context, client.session.filename.replace('.session',''), phone)
    except SessionPasswordNeededError:
        await update.message.reply_text("This account has 2FA enabled. Please send me the password.")
        return GET_2FA_PASS
    except Exception as e:
        await update.message.reply_text(f"❌ **Login Failed!** The code was incorrect. Please /run and try again.", parse_mode=ParseMode.MARKDOWN)
        await client.disconnect()
        return ConversationHandler.END

async def get_2fa_pass(update: Update, context: ContextTypes.DEFAULT_TYPE):
    password, client, phone = update.message.text.strip(), context.user_data['login_client'], context.user_data['login_phone']
    try:
        await client.sign_in(password=password)
        # Login success, now get details and proceed
        return await send_login_success_details(update, context, client.session.filename.replace('.session',''), phone)
    except Exception as e:
        await update.message.reply_text(f"❌ **Login Failed!** The password was incorrect. Please /run and try again.", parse_mode=ParseMode.MARKDOWN)
        await client.disconnect()
        return ConversationHandler.END

async def get_group_count_and_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        count = int(update.message.text)
        if count > 50:
            await update.message.reply_text("⚠️ **Warning:** Creating more than 50 groups can lead to account limits. Proceeding with caution.")
        
        account_info = context.user_data['account_info']
        await update.message.reply_text(f"✅ Setup complete! Starting process for account `{account_info['phone']}`...\nThis may take some time.", parse_mode=ParseMode.MARKDOWN)
        
        user_id = update.effective_user.id
        ACTIVE_PROCESSES[user_id] = True
        progress_queue, start_time = queue.Queue(), time.time()
        
        worker_args = (
            account_info, count,
            FIXED_MESSAGES_PER_GROUP, FIXED_DELAY, FIXED_MESSAGES, progress_queue
        )
        
        threading.Thread(target=lambda: asyncio.run(run_group_creation_process(*worker_args)), daemon=True).start()
        asyncio.create_task(progress_updater(update, context, progress_queue, start_time, count))
        return ConversationHandler.END
    except (ValueError, KeyError):
        await update.message.reply_text("Please enter a valid number, or /run to start over if there was an error.")
        return GET_GROUP_COUNT

async def progress_updater(update: Update, context: ContextTypes.DEFAULT_TYPE, progress_queue: queue.Queue, start_time: float, total_groups: int):
    user_id = update.effective_user.id
    status_message = await context.bot.send_message(chat_id=user_id, text="Starting process...")
    created_count = 0
    
    while True:
        try:
            item = progress_queue.get_nowait()
            if isinstance(item, str) and item.startswith("DONE"):
                results = json.loads(item.split(':', 1)[1])
                time_taken = time.strftime("%H:%M:%S", time.gmtime(time.time() - start_time))
                final_report = f"✅ **Process Complete!**\n\n**Time Taken:** {time_taken}\n\n---\n\n"
                output_files = [res['output_file'] for res in results if res.get('output_file')]
                for res in results:
                    final_report += f"{res['account_details']}\n📈 **Groups Created:** {res['created_count']}\n---"
                await context.bot.edit_message_text(chat_id=user_id, message_id=status_message.message_id, text=final_report, parse_mode=ParseMode.MARKDOWN)
                for file_path in output_files:
                    await context.bot.send_document(chat_id=user_id, document=open(file_path, 'rb'))
                    os.remove(file_path)
                break
            
            created_count += item
            percentage = (created_count / total_groups) * 100 if total_groups > 0 else 0
            await context.bot.edit_message_text(
                chat_id=user_id, message_id=status_message.message_id,
                text=f"⚙️ **In Progress...**\n\nCreated: {created_count}/{total_groups}\nProgress: {percentage:.1f}%"
            )
        except queue.Empty: await asyncio.sleep(2)
    ACTIVE_PROCESSES[user_id] = False

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Setup cancelled.")
    return ConversationHandler.END

def main():
    application = Application.builder().token(config['BOT_TOKEN']).build()
    
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('run', run_command)],
        states={
            GET_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_phone)],
            GET_LOGIN_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_login_code)],
            GET_2FA_PASS: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_2fa_pass)],
            GET_GROUP_COUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_group_count_and_start)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler(["add_admin", "remove_admin"], admin_commands))
    application.add_handler(CommandHandler("list_admins", list_admins))
    application.add_handler(CommandHandler("logged_accounts", logged_accounts))
    application.add_handler(conv_handler)
    
    application.run_polling()

if __name__ == '__main__':
    main()