import logging
import os
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import database as db
from config import CandidateStates, CANDIDATE_BOT_TOKEN, RECRUITER_BOT_TOKEN
from handlers.candidate_handlers import (
    send_main_menu, handle_message, handle_test_answer,
    handle_where_to_start, start_stopwords_test, handle_stopword_answer,
    next_stopword_question, begin_stopwords_test
)
from handlers.button_handlers import button_click

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

async def handle_interview_request(user_id, preferred_day, preferred_time):
    """Handle a new interview request and notify the recruiter"""
    # Save the interview request
    request_id = db.save_interview_request(user_id, preferred_day, preferred_time)
    
    # Get user info for notification
    user_info = db.send_interview_notification_to_recruiter(user_id, preferred_day, preferred_time)
    
    if user_info and request_id:
        # Create recruiter bot instance to send notification
        try:
            from telegram import Bot
            recruiter_bot = Bot(token=RECRUITER_BOT_TOKEN)
            
            # Format notification message
            notification = (
                f"📣 *Новый запрос на собеседование!*\n\n"
                f"👤 Кандидат: @{user_info['username']}\n"
                f"📅 Предпочтительный день: {user_info['preferred_day']}\n"
                f"⏰ Предпочтительное время: {user_info['preferred_time']}\n\n"
                f"Используйте меню 'Запросы на собеседование' для управления."
            )
            
            # Send to recruiter channel/chat (replace with actual admin user ID or channel ID)
            # This would typically be a specific admin user or chat where recruiters monitor
            admin_user_id = os.getenv("ADMIN_USER_ID", "")  # Get from environment variables
            
            if admin_user_id and admin_user_id.isdigit():
                await recruiter_bot.send_message(
                    chat_id=int(admin_user_id),
                    text=notification,
                    parse_mode='Markdown'
                )
                logger.info(f"Interview request notification sent to admin for user {user_id}")
            else:
                logger.warning("Admin user ID not configured, could not send notification")
                
        except Exception as e:
            logger.error(f"Error sending interview notification: {e}")
    
    return request_id

async def handle_test_feedback(user_id, submission_id, status, feedback):
    """Handle test feedback from recruiter and notify the candidate"""
    # This function is imported and called from recruiter_bot.py
    # after a test submission is reviewed
    
    from telegram import Bot
    
    try:
        # Create a bot instance
        bot = Bot(token=CANDIDATE_BOT_TOKEN)
        
        # Decide on message based on status
        if status == "approved":
            message = (
                "🎉 *Ваше тестовое задание одобрено!*\n\n"
                f"Отзыв рекрутера: {feedback}\n\n"
                "Продолжайте работу с ботом для дальнейших шагов."
            )
        else:
            message = (
                "❗ *Ваше тестовое задание нуждается в доработке*\n\n"
                f"Отзыв рекрутера: {feedback}\n\n"
                "Ознакомьтесь с комментариями и повторите попытку."
            )
        
        # Send the message to the candidate
        await bot.send_message(
            chat_id=user_id,
            text=message,
            parse_mode='Markdown'
        )
        
        return True
    except Exception as e:
        logger.error(f"Error sending test feedback to user {user_id}: {e}")
        return False

async def handle_interview_response(user_id, request_id, status, response):
    """Handle interview response from recruiter and notify the candidate"""
    # This function is imported and called from recruiter_bot.py
    # after an interview request is processed
    
    from telegram import Bot
    
    try:
        # Create a bot instance
        bot = Bot(token=CANDIDATE_BOT_TOKEN)
        
        # Decide on message based on status
        if status == "approved":
            message = (
                "✅ *Ваш запрос на собеседование подтвержден!*\n\n"
                f"Детали: {response}\n\n"
                "Хорошей подготовки к собеседованию!"
            )
        else:
            message = (
                "❌ *Ваш запрос на собеседование требует корректировки*\n\n"
                f"Ответ рекрутера: {response}\n\n"
                "Пожалуйста, следуйте инструкциям выше."
            )
        
        # Send the message to the candidate
        await bot.send_message(
            chat_id=user_id,
            text=message,
            parse_mode='Markdown'
        )
        
        return True
    except Exception as e:
        logger.error(f"Error sending interview response to user {user_id}: {e}")
        return False

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
    application.add_handler(CallbackQueryHandler(begin_stopwords_test, pattern="^begin_stopwords_test$"))
    application.add_handler(CallbackQueryHandler(next_stopword_question, pattern="^next_stopword_question$"))
    
    # Обработчики для тестов
    application.add_handler(CallbackQueryHandler(handle_test_answer, pattern="^answer_"))
    
    # Обработчики для собеседования
    application.add_handler(CallbackQueryHandler(button_click, pattern="^interview_day_"))
    application.add_handler(CallbackQueryHandler(button_click, pattern="^interview_time_"))
    application.add_handler(CallbackQueryHandler(button_click, pattern="^confirm_interview_request$"))
    
    # Общий обработчик для всех кнопок меню
    application.add_handler(CallbackQueryHandler(button_click))
    
    # Обработчик для текстовых сообщений
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Запуск бота
    application.run_polling()

if __name__ == '__main__':
    logger.info("Бот запущен!")
    db.init_db()
    main()
