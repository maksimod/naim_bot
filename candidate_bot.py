import logging
import os
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import database as db
from config import CandidateStates, CANDIDATE_BOT_TOKEN
from handlers.candidate_handlers import (
    send_main_menu, handle_message, handle_test_answer,
    handle_where_to_start, start_stopwords_test, handle_stopword_answer,
    next_stopword_question
)

# Загрузка переменных окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /start is issued."""
    user_id = update.effective_user.id
    
    # Проверяем, существует ли пользователь в базе данных
    if not db.user_exists(user_id):
        # Создаем нового пользователя, если его нет
        db.create_user(user_id, update.effective_user.username)
        
        # Разблокируем первые два этапа по умолчанию
        db.unlock_stage(user_id, "about_company")
        db.unlock_stage(user_id, "primary_file")
    
    # Отправляем главное меню
    return await send_main_menu(update, context)

def main():
    """Start the bot."""
    # Создание экземпляра бота
    application = ApplicationBuilder().token(CANDIDATE_BOT_TOKEN).build()
    
    # Добавление обработчиков
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("menu", send_main_menu))
    
    # Обработчики для меню
    application.add_handler(CallbackQueryHandler(send_main_menu, pattern="^back_to_menu$"))
    
    # Обработчики для раздела "С чего начать"
    application.add_handler(CallbackQueryHandler(handle_where_to_start, pattern="^where_to_start$"))
    application.add_handler(CallbackQueryHandler(start_stopwords_test, pattern="^start_stopwords_test$"))
    application.add_handler(CallbackQueryHandler(next_stopword_question, pattern="^next_stopword_question$"))
    
    # Обработчики для тестов
    application.add_handler(CallbackQueryHandler(handle_test_answer, pattern="^answer_"))
    
    # Обработчик для текстовых сообщений
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Запуск бота
    application.run_polling()

if __name__ == '__main__':
    logger.info("Бот запущен!")
    db.init_db()
    main()
