import logging
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, 
    MessageHandler, filters, ConversationHandler
)
import database as db
from config import CandidateStates, CANDIDATE_BOT_TOKEN
from handlers.command_handlers import start, help_command, menu_command, unknown_command, unknown_message
from handlers.button_handlers import button_click
from handlers.candidate_handlers import handle_test_answer

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Initialize database
db.init_db()

async def main():
    """Start the bot."""
    # Create the Application
    application = Application.builder().token(CANDIDATE_BOT_TOKEN).build()
    
    # Define conversation handler for the candidate bot
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            CandidateStates.MAIN_MENU: [
                CallbackQueryHandler(button_click),
                CommandHandler('help', help_command),
                CommandHandler('menu', menu_command),
                MessageHandler(filters.TEXT & ~filters.COMMAND, unknown_message)
            ],
            CandidateStates.PRIMARY_FILE: [
                CallbackQueryHandler(button_click),
                MessageHandler(filters.TEXT & ~filters.COMMAND, unknown_message)
            ],
            CandidateStates.PRIMARY_TEST: [
                CallbackQueryHandler(handle_test_answer),
                MessageHandler(filters.TEXT & ~filters.COMMAND, unknown_message)
            ],
            CandidateStates.WHERE_TO_START: [
                CallbackQueryHandler(button_click),
                MessageHandler(filters.TEXT & ~filters.COMMAND, unknown_message)
            ],
            CandidateStates.WHERE_TO_START_TEST: [
                CallbackQueryHandler(handle_test_answer),
                MessageHandler(filters.TEXT & ~filters.COMMAND, unknown_message)
            ],
            CandidateStates.PREPARATION_MATERIALS: [
                CallbackQueryHandler(button_click),
                MessageHandler(filters.TEXT & ~filters.COMMAND, unknown_message)
            ],
            CandidateStates.TAKE_TEST: [
                CallbackQueryHandler(button_click),
                MessageHandler(filters.TEXT & ~filters.COMMAND, unknown_message)
            ],
            CandidateStates.INTERVIEW_PREP: [
                CallbackQueryHandler(button_click),
                MessageHandler(filters.TEXT & ~filters.COMMAND, unknown_message)
            ],
            CandidateStates.SCHEDULE_INTERVIEW: [
                CallbackQueryHandler(button_click),
                MessageHandler(filters.TEXT & ~filters.COMMAND, unknown_message)
            ],
            CandidateStates.CONTACT_DEVELOPERS: [
                CallbackQueryHandler(button_click),
                MessageHandler(filters.TEXT & ~filters.COMMAND, unknown_message)
            ],
        },
        fallbacks=[
            CommandHandler('start', start),
            MessageHandler(filters.COMMAND, unknown_command)
        ]
    )
    
    # Add conversation handler to the application
    application.add_handler(conv_handler)
    
    # Add standalone command handlers
    application.add_handler(CommandHandler('help', help_command))
    application.add_handler(CommandHandler('menu', menu_command))
    
    # Add handlers for unknown commands and messages (outside of conversation)
    application.add_handler(MessageHandler(filters.COMMAND, unknown_command))
    application.add_handler(MessageHandler(filters.TEXT, unknown_message))
    
    # Start the Bot
    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    
    # Run the bot until the user presses Ctrl+C
    print('Бот запущен. Нажмите Ctrl+C для остановки.')
    try:
        # Держим бота запущенным до нажатия Ctrl+C
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print('Получен сигнал остановки, выключаем бота...')
        # Останавливаем бота при нажатии Ctrl+C
        await application.updater.stop()
        await application.stop()

if __name__ == '__main__':
    import asyncio
    asyncio.run(main())
