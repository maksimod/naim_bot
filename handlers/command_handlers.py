import logging
import os
import sys
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import database as db
from config import CandidateStates
from utils.helpers import load_text_content
from handlers.candidate_handlers import send_main_menu

# Добавляем корневую директорию проекта в путь импорта
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger(__name__)

# Command handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start the conversation and show the main menu."""
    user = update.effective_user
    db.register_user(
        user.id,
        user.username,
        user.first_name,
        user.last_name
    )
    
    # Send welcome message first, separate from the main menu
    welcome_message = load_text_content("welcome_message.txt")
    welcome_msg = await update.message.reply_text(f"Здравствуйте, {user.first_name}!\n\n{welcome_message}")
    
    # Store the welcome message ID for reference
    context.user_data["welcome_message_id"] = welcome_msg.message_id
    
    # Immediately show the main menu without requiring a button click
    return await send_main_menu(update, context)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /help is issued."""
    help_text = (
        "Доступные команды:\n"
        "/start - Начать или перезапустить бота\n"
        "/menu - Открыть главное меню\n"
        "/help - Показать эту справку"
    )
    await update.message.reply_text(help_text)
    return CandidateStates.MAIN_MENU

async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show the main menu when the command /menu is issued."""
    return await send_main_menu(update, context)

async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle unknown commands."""
    await update.message.reply_text(
        "Извините, я не распознал эту команду. Используйте /help для списка доступных команд."
    )
    return CandidateStates.MAIN_MENU

async def unknown_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle unknown messages."""
    # Check if we're expecting a specific type of input
    state = context.user_data.get('state', CandidateStates.MAIN_MENU)
    
    # Secret admin mode activation check - проверяем различные варианты секретного кода
    message_text = update.message.text
    secret_codes = ["admin123!", "admin123"]
    if message_text in secret_codes or message_text.strip() in secret_codes:
        context.user_data["admin_mode"] = True
        await update.message.reply_text(
            "🔓 Режим администратора активирован. Все пункты меню теперь доступны.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Вернуться в главное меню", callback_data="back_to_menu")]
            ])
        )
        return CandidateStates.MAIN_MENU
    
    if state == CandidateStates.MAIN_MENU:
        await update.message.reply_text(
            "Пожалуйста, используйте кнопки меню или /help для списка доступных команд."
        )
    
    return state
