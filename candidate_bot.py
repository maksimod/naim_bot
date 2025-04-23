import logging
import os
import sys
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# Добавляем текущую директорию в путь импорта
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

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
    
    # Сохраняем информацию о пользователе
    db.register_user(
        user_id, 
        update.effective_user.username,
        update.effective_user.first_name,
        update.effective_user.last_name
    )
    
    # Проверяем, существует ли пользователь в базе данных
    if not db.user_exists(user_id):
        # Создаем нового пользователя, если его нет
        db.create_user(user_id, update.effective_user.username)
        
        # Разблокируем первые два этапа по умолчанию
        db.unlock_stage(user_id, "about_company")
        db.unlock_stage(user_id, "primary_file")
    
    # Читаем и отправляем приветственное сообщение
    from utils.helpers import load_text_content
    welcome_message = load_text_content("welcome_message.txt")
    await update.message.reply_text(welcome_message)
    
    # Отправляем главное меню
    return await send_main_menu(update, context)

async def handle_interview_request(user_id, preferred_day, preferred_time):
    """Handle a new interview request and notify the recruiter"""
    # Save the interview request
    request_id = db.save_interview_request(user_id, preferred_day, preferred_time)
    
    # Get user info for notification
    user_info = db.get_user_info_with_interview_details(user_id, preferred_day, preferred_time)
    
    if user_info and request_id:
        # Create recruiter bot instance to send notification
        try:
            from telegram import Bot
            recruiter_bot = Bot(token=RECRUITER_BOT_TOKEN)
            
            # Get display info
            display_name = user_info.get('display_name', f"Пользователь {user_id}")
            username_display = f" (@{user_info['username']})" if user_info.get('username') else ""
            
            # Получаем статистику тестов пользователя
            user_test_results = db.get_user_test_results(user_id)
            
            # Получаем информацию о нейросетях, которыми пользовался кандидат
            ai_usage = db.get_user_ai_usage(user_id) if hasattr(db, 'get_user_ai_usage') else None
            
            # Формируем информацию о тестах
            tests_info = ""
            if user_test_results:
                tests_info += "\n\n📊 *Статистика тестов:*\n"
                for test_name, result in user_test_results.items():
                    test_display_name = test_name.replace('_', ' ').title()
                    
                    # Делаем имена тестов более читаемыми
                    if test_name == 'primary_test':
                        test_display_name = "Тест по первичному файлу"
                    elif test_name == 'where_to_start_test':
                        test_display_name = "Тест 'С чего начать'"
                    elif test_name == 'logic_test_result':
                        test_display_name = "Тест на логику"
                    elif test_name == 'take_test_result':
                        test_display_name = "Испытание"
                    elif test_name == 'interview_prep_test':
                        test_display_name = "Подготовка к собеседованию"
                    
                    status = "✅ Успешно" if result else "❌ Не пройден"
                    tests_info += f"  • {test_display_name}: {status}\n"
            else:
                tests_info += "\n\n📊 *Статистика тестов:* нет данных"
            
            # Формируем информацию о нейросетях
            ai_info = ""
            if ai_usage and ai_usage.get('models'):
                ai_info += "\n\n🤖 *Использование нейросетей:*\n"
                for model_name, usage_count in ai_usage['models'].items():
                    ai_info += f"  • {model_name}\n"
            else:
                ai_info += "\n\n🤖 *Использование нейросетей:* нет данных"
            
            # Format notification message with test and AI info
            notification = (
                f"📣 *Новый запрос на собеседование!*\n\n"
                f"👤 Кандидат: {display_name}{username_display}\n"
                f"📅 Предпочтительный день: {user_info['preferred_day']}\n"
                f"⏰ Предпочтительное время: {user_info['preferred_time']}"
                f"{tests_info}"
                f"{ai_info}\n\n"
            )
            
            # Get all recruiters and send notification to each
            recruiters = db.get_all_recruiters()
            
            if recruiters:
                for recruiter in recruiters:
                    try:
                        await recruiter_bot.send_message(
                            chat_id=recruiter['user_id'],
                            text=notification,
                            parse_mode='Markdown'
                        )
                        logger.info(f"Interview request notification sent to recruiter {recruiter['user_id']} for user {user_id}")
                    except Exception as e:
                        logger.error(f"Error sending notification to recruiter {recruiter['user_id']}: {e}")
            else:
                logger.warning("No recruiters found, could not send notification")
                
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
    application.add_handler(CallbackQueryHandler(
        lambda update, context: send_main_menu(update, context, edit=True), 
        pattern="^back_to_menu$"
    ))
    
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
