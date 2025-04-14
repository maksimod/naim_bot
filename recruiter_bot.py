import os
import json
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes, ConversationHandler
import database as db
from config import RecruiterStates, RECRUITER_BOT_TOKEN

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
        [InlineKeyboardButton("u041fu0440u043eu0432u0435u0440u0438u0442u044c u0442u0435u0441u0442u043eu0432u044bu0435 u0437u0430u0434u0430u043du0438u044f", callback_data="review_tests")],
        [InlineKeyboardButton("u0417u0430u043fu0440u043eu0441u044b u043du0430 u0441u043eu0431u0435u0441u0435u0434u043eu0432u0430u043du0438u0435", callback_data="interview_requests")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.effective_message.reply_text(
        "u0414u043eu0431u0440u043e u043fu043eu0436u0430u043bu043eu0432u0430u0442u044c u0432 u043fu0430u043du0435u043bu044c u0440u0435u043au0440u0443u0442u0435u0440u0430. u0412u044bu0431u0435u0440u0438u0442u0435 u0434u0435u0439u0441u0442u0432u0438u0435:",
        reply_markup=reply_markup
    )
    return RecruiterStates.MAIN_MENU

# Command handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start the conversation and show the main menu."""
    user = update.effective_user
    await update.message.reply_text(f"u0417u0434u0440u0430u0432u0441u0442u0432u0443u0439u0442u0435, {user.first_name}! u042du0442u043e u0431u043eu0442 u0434u043bu044f u0440u0435u043au0440u0443u0442u0435u0440u043eu0432.")
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
            await query.message.reply_text("u0412 u043du0430u0441u0442u043eu044fu0449u0435u0435 u0432u0440u0435u043cu044f u043du0435u0442 u043eu0436u0438u0434u0430u044eu0449u0438u0445 u043fu0440u043eu0432u0435u0440u043au0438 u0442u0435u0441u0442u043eu0432u044bu0445 u0437u0430u0434u0430u043du0438u0439.")
            return await send_main_menu(update, context)
        
        # Display list of submissions
        await query.message.reply_text("u0422u0435u0441u0442u043eu0432u044bu0435 u0437u0430u0434u0430u043du0438u044f, u043eu0436u0438u0434u0430u044eu0449u0438u0435 u043fu0440u043eu0432u0435u0440u043au0438:")
        
        for submission in submissions:
            keyboard = [
                [InlineKeyboardButton("u041fu0440u043eu0441u043cu043eu0442u0440u0435u0442u044c", callback_data=f"view_submission_{submission['id']}")],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.message.reply_text(
                f"ID: {submission['id']}\n"
                f"u041au0430u043du0434u0438u0434u0430u0442: {submission['candidate_name']}\n"
                f"u0422u0438u043f u0442u0435u0441u0442u0430: {submission['test_type']}\n"
                f"u0424u0430u0439u043b: {submission['submission_data'].get('file_name', 'u041du0435 u0443u043au0430u0437u0430u043d')}",
                reply_markup=reply_markup
            )
        
        return RecruiterStates.REVIEW_TEST
    
    elif query.data.startswith("approve_submission_") or query.data.startswith("reject_submission_"):
        submission_id = int(query.data.split("_")[2])
        status = "approved" if query.data.startswith("approve_submission_") else "rejected"
        
        # Ask for feedback
        context.user_data["current_submission_id"] = submission_id
        context.user_data["submission_status"] = status
        
        await query.message.reply_text(
            f"Пожалуйста, напишите обратную связь для кандидата {'(что понравилось в решении)' if status == 'approved' else '(что нужно улучшить)'}:"
        )
        
        return RecruiterStates.REVIEW_FEEDBACK
    
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
        
        return RecruiterStates.INTERVIEW_RESPONSE
    
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
            RecruiterStates.REVIEW_FEEDBACK: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_submission_feedback),
            ],
            RecruiterStates.SCHEDULE_INTERVIEW: [
                CallbackQueryHandler(button_click),
            ],
            RecruiterStates.INTERVIEW_RESPONSE: [
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
    
    elif query.data == "interview_requests":
        # Get pending interview requests
        requests = db.get_pending_interview_requests()
        
        if not requests:
            await query.message.reply_text("u0412 u043du0430u0441u0442u043eu044fu0449u0435u0435 u0432u0440u0435u043cu044f u043du0435u0442 u0437u0430u043fu0440u043eu0441u043eu0432 u043du0430 u0441u043eu0431u0435u0441u0435u0434u043eu0432u0430u043du0438u0435.")
            return await send_main_menu(update, context)
        
        # Display list of interview requests
        await query.message.reply_text("u0417u0430u043fu0440u043eu0441u044b u043du0430 u0441u043eu0431u0435u0441u0435u0434u043eu0432u0430u043du0438u0435:")
        
        for request in requests:
            keyboard = [
                [InlineKeyboardButton("u041fu043eu0434u0442u0432u0435u0440u0434u0438u0442u044c", callback_data=f"approve_interview_{request['id']}")],
                [InlineKeyboardButton("u041eu0442u043au043bu043eu043du0438u0442u044c", callback_data=f"reject_interview_{request['id']}")],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.message.reply_text(
                f"ID: {request['id']}\n"
                f"u041au0430u043du0434u0438u0434u0430u0442: {request['candidate_name']}\n"
                f"u041fu0440u0435u0434u043fu043eu0447u0442u0438u0442u0435u043bu044cu043du044bu0439 u0434u0435u043du044c: {request['preferred_day']}\n"
                f"u041fu0440u0435u0434u043fu043eu0447u0442u0438u0442u0435u043bu044cu043du043eu0435 u0432u0440u0435u043cu044f: {request['preferred_time']}",
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
            await query.message.reply_text("u0417u0430u044fu0432u043au0430 u043du0435 u043du0430u0439u0434u0435u043du0430 u0438u043bu0438 u0443u0436u0435 u043eu0431u0440u0430u0431u043eu0442u0430u043du0430.")
            return await send_main_menu(update, context)
        
        # Download and forward the file
        file_id = submission["submission_data"].get("file_id")
        if file_id:
            file = await context.bot.get_file(file_id)
            await query.message.reply_document(file.file_id, caption=f"u0422u0435u0441u0442u043eu0432u043eu0435 u0437u0430u0434u0430u043du0438u0435 u043eu0442 {submission['candidate_name']} (ID: {submission_id})")
        
        # Provide options to approve or reject
        keyboard = [
            [InlineKeyboardButton("u041eu0434u043eu0431u0440u0438u0442u044c", callback_data=f"approve_submission_{submission_id}")],
            [InlineKeyboardButton("u041eu0442u043au043bu043eu043du0438u0442u044c", callback_data=f"reject_submission_{submission_id}")],
            [InlineKeyboardButton("u0412u0435u0440u043du0443u0442u044cu0441u044f u043a u0441u043fu0438u0441u043au0443", callback_data="review_tests")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.message.reply_text(
            f"u041fu043eu0436u0430u043bu0443u0439u0441u0442u0430, u043fu0440u043eu0432u0435u0440u044cu0442u0435 u0442u0435u0441u0442u043eu0432u043eu0435 u0437u0430u0434u0430u043du0438u0435 u0438 u0432u044bu0431u0435u0440u0438u0442u0435 u0434u0435u0439u0441u0442u0432u0438u0435:\n\n"
            f"u041au0430u043du0434u0438u0434u0430u0442: {submission['candidate_name']}\n"
            f"ID u0437u0430u044fu0432u043au0438: {submission_id}",
            reply_markup=reply_markup
        )
        
        return RecruiterStates.REVIEW_TEST
    
    elif query.data.startswith("approve_submission_") or query.data.startswith("reject_submission_"):
        submission_id = int(query.data.split("_")[2])
        status = "approved" if query.data.startswith("approve_submission_") else "rejected"
        
        # Ask for feedback
        context.user_data["current_submission_id"] = submission_id
        context.user_data["submission_status"] = status
        
        await query.message.reply_text(
            f"Пожалуйста, напишите обратную связь для кандидата {'(что понравилось в решении)' if status == 'approved' else '(что нужно улучшить)'}:"
        )
        
        return RecruiterStates.REVIEW_FEEDBACK
    
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
        
        return RecruiterStates.INTERVIEW_RESPONSE
    
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
            RecruiterStates.REVIEW_FEEDBACK: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_submission_feedback),
            ],
            RecruiterStates.SCHEDULE_INTERVIEW: [
                CallbackQueryHandler(button_click),
            ],
            RecruiterStates.INTERVIEW_RESPONSE: [
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
