import os
import json
import sys
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes, ConversationHandler

# Добавляем текущую директорию в путь импорта
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import database as db
from config_fix import RecruiterStates, RECRUITER_BOT_TOKEN

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Initialize database
db.init_db()

# Helper functions
async def send_main_menu(update, context):
    """Send the main menu with options for the recruiter"""
    keyboard = [
        [InlineKeyboardButton("Проверить тестовые задания", callback_data="review_tests")],
        [InlineKeyboardButton("Запросы на собеседование", callback_data="interview_requests")],
        [InlineKeyboardButton("Просмотр метрик", callback_data="view_metrics")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.effective_message.reply_text(
        "Добро пожаловать в панель рекрутера. Выберите действие:",
        reply_markup=reply_markup
    )
    return RecruiterStates.MAIN_MENU

# Command handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /start is issued."""
    user_id = update.effective_user.id
    
    # Отправляем сообщение с ID пользователя
    await update.message.reply_text(
        f"Ваш ID для настройки уведомлений: {user_id}\n\n"
        "Пожалуйста, скопируйте этот ID и вставьте его в файл .env в переменную ADMIN_USER_ID"
    )
    
    # Показываем главное меню
    return await send_main_menu(update, context)

# Callback query handlers
async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button clicks from the inline keyboard."""
    query = update.callback_query
    await query.answer()
    
    if query.data == "review_tests":
        # Get pending test submissions
        submissions = db.get_pending_submissions()
        
        if not submissions:
            await query.message.reply_text("В настоящее время нет ожидающих проверки тестовых заданий.")
            return await send_main_menu(update, context)
        
        # Display list of submissions
        await query.message.reply_text("Тестовые задания, ожидающие проверки:")
        
        for submission in submissions:
            keyboard = [
                [InlineKeyboardButton("Просмотреть", callback_data=f"view_submission_{submission['id']}")],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.message.reply_text(
                f"ID: {submission['id']}\n"
                f"Кандидат: {submission['candidate_name']}\n"
                f"Тип теста: {submission['test_type']}\n"
                f"Файл: {submission['submission_data'].get('file_name', 'Не указан')}",
                reply_markup=reply_markup
            )
        
        return RecruiterStates.REVIEW_TEST
    
    elif query.data == "view_metrics":
        # Get metrics from database
        metrics = db.get_metrics()
        
        # Format metrics into a readable message
        message = "📊 **Метрики процесса найма:**\n\n"
        
        # Total users who started
        message += f"👤 Всего пользователей: {metrics['total_candidates']}\n\n"
        
        # Test metrics
        message += "📝 **Прогресс по тестам:**\n"
        
        if metrics['test_stats']:
            for test_type, data in metrics['test_stats'].items():
                # Make test name more readable
                test_name = test_type.replace('_', ' ').title()
                if test_type == 'primary_test':
                    test_name = "Тест по первичному файлу"
                elif test_type == 'stopwords_test':
                    test_name = "Тест С чего начать"
                elif test_type == 'logic_test':
                    test_name = "Тест на логику"
                elif test_type == 'practice_test':
                    test_name = "Испытание"
                elif test_type == 'interview_prep_test':
                    test_name = "Подготовка к собеседованию"
                    
                message += f"• {test_name}:\n"
                message += f"  - Прошли тест: {data['total_submitted']}\n"
                message += f"  - Успешно завершили: {data['passed']}\n"
        else:
            message += "Пока нет данных по тестам\n"
        
        # Interview requests
        message += f"\n👥 Запросы на собеседование: {metrics['interview_requests']}"
        
        # Add back button
        keyboard = [
            [InlineKeyboardButton("⬅️ Назад", callback_data="back_to_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.message.reply_text(message, reply_markup=reply_markup, parse_mode='Markdown')
        return RecruiterStates.MAIN_MENU
    
    elif query.data.startswith("approve_submission_") or query.data.startswith("reject_submission_"):
        submission_id = int(query.data.split("_")[2])
        status = "approved" if query.data.startswith("approve_submission_") else "rejected"
        
        # Ask for feedback
        context.user_data["current_submission_id"] = submission_id
        context.user_data["submission_status"] = status
        
        await query.message.reply_text(
            f"Пожалуйста, напишите обратную связь для кандидата {'(что понравилось в решении)' if status == 'approved' else '(что нужно улучшить)'}:"
        )
        
        return "REVIEW_FEEDBACK"
    
    elif query.data.startswith("approve_interview_") or query.data.startswith("reject_interview_"):
        request_id = int(query.data.split("_")[2])
        status = "approved" if query.data.startswith("approve_interview_") else "rejected"
        
        # Ask for response
        context.user_data["current_request_id"] = request_id
        context.user_data["request_status"] = status
        
        if status == "approved":
            await query.message.reply_text(
                "Пожалуйста, напишите детали собеседования (ссылка на звонок, дополнительная информация и т.д.):"
            )
        else:
            await query.message.reply_text(
                "Пожалуйста, укажите причину отклонения и предложите альтернативные варианты времени, если возможно:"
            )
        
        return "INTERVIEW_RESPONSE"
    
    elif query.data == "interview_requests":
        # Get pending interview requests
        requests = db.get_pending_interview_requests()
        
        if not requests:
            await query.message.reply_text("В настоящее время нет запросов на собеседование.")
            return await send_main_menu(update, context)
        
        # Display list of interview requests
        await query.message.reply_text("Запросы на собеседование:")
        
        for request in requests:
            keyboard = [
                [InlineKeyboardButton("Подтвердить", callback_data=f"approve_interview_{request['id']}")],
                [InlineKeyboardButton("Отклонить", callback_data=f"reject_interview_{request['id']}")],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.message.reply_text(
                f"ID: {request['id']}\n"
                f"Кандидат: {request['candidate_name']}\n"
                f"Предпочтительный день: {request['preferred_day']}\n"
                f"Предпочтительное время: {request['preferred_time']}",
                reply_markup=reply_markup
            )
        
        return RecruiterStates.SCHEDULE_INTERVIEW
    
    elif query.data.startswith("view_submission_"):
        submission_id = int(query.data.split("_")[2])
        
        # Store submission ID in context for future reference
        context.user_data["current_submission_id"] = submission_id
        
        # Get submission details from database
        submissions = db.get_pending_submissions()
        submission = next((s for s in submissions if s["id"] == submission_id), None)
        
        if not submission:
            await query.message.reply_text("Заявка найдена или уже обработана.")
            return await send_main_menu(update, context)
        
        # Download and forward the file
        file_id = submission["submission_data"].get("file_id")
        if file_id:
            file = await context.bot.get_file(file_id)
            await query.message.reply_document(file.file_id, caption=f"Тестовое задание от {submission['candidate_name']} (ID: {submission_id})")
        
        # Provide options to approve or reject
        keyboard = [
            [InlineKeyboardButton("Одобрить", callback_data=f"approve_submission_{submission_id}")],
            [InlineKeyboardButton("Отклонить", callback_data=f"reject_submission_{submission_id}")],
            [InlineKeyboardButton("Вернуться к списку", callback_data="review_tests")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.message.reply_text(
            f"Пожалуйста, проверьте тестовое задание и выберите действие:\n\n"
            f"Кандидат: {submission['candidate_name']}\n"
            f"ID заявки: {submission_id}",
            reply_markup=reply_markup
        )
        
        return RecruiterStates.REVIEW_TEST
    
    # Default case - return to main menu
    return await send_main_menu(update, context)

async def handle_submission_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle feedback for a test submission"""
    # Get submission details from context
    submission_id = context.user_data.get("current_submission_id")
    status = context.user_data.get("submission_status")
    feedback = update.message.text
    
    if not submission_id or not status:
        await update.message.reply_text("Произошла ошибка. Пожалуйста, начните процесс заново.")
        return await send_main_menu(update, context)
    
    # Update submission status in database
    result = db.update_test_submission(submission_id, status, feedback)
    
    if result:
        # Import the function from candidate_bot to send notification
        from candidate_bot import handle_test_feedback
        
        # Send notification to candidate
        await handle_test_feedback(result["user_id"], submission_id, status, feedback)
        
        await update.message.reply_text(
            f"Обратная связь отправлена кандидату. Статус заявки: {status}."
        )
    else:
        await update.message.reply_text("Произошла ошибка при обновлении статуса заявки.")
    
    return await send_main_menu(update, context)

async def handle_interview_response(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle response for an interview request"""
    # Get request details from context
    request_id = context.user_data.get("current_request_id")
    status = context.user_data.get("request_status")
    response = update.message.text
    
    if not request_id or not status:
        await update.message.reply_text("Произошла ошибка. Пожалуйста, начните процесс заново.")
        return await send_main_menu(update, context)
    
    # Update request status in database
    result = db.update_interview_request(request_id, status, response)
    
    if result:
        # Import the function from candidate_bot to send notification
        from candidate_bot import handle_interview_response
        
        # Send notification to candidate
        await handle_interview_response(result["user_id"], request_id, status, response)
        
        await update.message.reply_text(
            f"Ответ отправлен кандидату. Статус запроса: {status}."
        )
    else:
        await update.message.reply_text("Произошла ошибка при обновлении статуса запроса.")
    
    return await send_main_menu(update, context)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /help is issued."""
    help_text = (
        "Бот для рекрутеров - помощь\n\n"
        "/start - Начать работу с ботом\n"
        "/menu - Показать главное меню\n"
        "/help - Показать это сообщение\n\n"
        "Используйте кнопки в меню для навигации по функциям бота."
    )
    await update.message.reply_text(help_text)
    return RecruiterStates.MAIN_MENU

async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show the main menu when the command /menu is issued."""
    return await send_main_menu(update, context)

async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle unknown commands."""
    await update.message.reply_text(
        "Извините, я не понимаю эту команду. Используйте /help для получения списка доступных команд."
    )
    return RecruiterStates.MAIN_MENU

async def unknown_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle unknown messages."""
    # If we're expecting feedback or response, don't treat it as unknown
    if context.user_data.get("current_submission_id") and context.user_data.get("submission_status"):
        return await handle_submission_feedback(update, context)
    
    if context.user_data.get("current_request_id") and context.user_data.get("request_status"):
        return await handle_interview_response(update, context)
    
    await update.message.reply_text(
        "Извините, я не понимаю это сообщение. Пожалуйста, используйте кнопки в меню для навигации."
    )
    return RecruiterStates.MAIN_MENU

def main():
    """Start the bot."""
    # Create the Application
    application = Application.builder().token(RECRUITER_BOT_TOKEN).build()
    
    # Add conversation handler with states
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            RecruiterStates.MAIN_MENU: [
                CallbackQueryHandler(button_click),
                CommandHandler("menu", menu_command),
            ],
            RecruiterStates.REVIEW_TEST: [
                CallbackQueryHandler(button_click),
            ],
            "REVIEW_FEEDBACK": [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_submission_feedback),
            ],
            RecruiterStates.SCHEDULE_INTERVIEW: [
                CallbackQueryHandler(button_click),
            ],
            "INTERVIEW_RESPONSE": [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_interview_response),
            ],
        },
        fallbacks=[
            CommandHandler("help", help_command),
            CommandHandler("menu", menu_command),
            MessageHandler(filters.COMMAND, unknown_command),
            MessageHandler(filters.ALL, unknown_message),
        ],
    )
    
    application.add_handler(conv_handler)
    
    # Start the Bot
    application.run_polling()

if __name__ == '__main__':
    main()
