import logging
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, 
    MessageHandler, filters, ConversationHandler
)
import database as db
from config_fix import CandidateStates, CANDIDATE_BOT_TOKEN
from handlers import command_handlers, button_handlers, candidate_handlers

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
        entry_points=[CommandHandler('start', command_handlers.start)],
        states={
            CandidateStates.MAIN_MENU: [
                CallbackQueryHandler(button_handlers.button_click),
                CommandHandler('help', command_handlers.help_command),
                CommandHandler('menu', command_handlers.menu_command),
                MessageHandler(filters.TEXT & ~filters.COMMAND, command_handlers.unknown_message)
            ],
            CandidateStates.PRIMARY_FILE: [
                CallbackQueryHandler(button_handlers.button_click),
                MessageHandler(filters.TEXT & ~filters.COMMAND, command_handlers.unknown_message)
            ],
            CandidateStates.PRIMARY_TEST: [
                CallbackQueryHandler(candidate_handlers.handle_test_answer),
                MessageHandler(filters.TEXT & ~filters.COMMAND, command_handlers.unknown_message)
            ],
            CandidateStates.WHERE_TO_START: [
                CallbackQueryHandler(button_handlers.button_click),
                MessageHandler(filters.TEXT & ~filters.COMMAND, command_handlers.unknown_message)
            ],
            CandidateStates.WHERE_TO_START_TEST: [
                CallbackQueryHandler(candidate_handlers.handle_test_answer),
                MessageHandler(filters.TEXT & ~filters.COMMAND, command_handlers.unknown_message)
            ],
            CandidateStates.PREPARATION_MATERIALS: [
                CallbackQueryHandler(button_handlers.button_click),
                MessageHandler(filters.TEXT & ~filters.COMMAND, command_handlers.unknown_message)
            ],
            CandidateStates.TAKE_TEST: [
                CallbackQueryHandler(button_handlers.button_click),
                MessageHandler(filters.TEXT & ~filters.COMMAND, command_handlers.unknown_message)
            ],
            CandidateStates.WAITING_FOR_SOLUTION: [
                CallbackQueryHandler(button_handlers.button_click),
                MessageHandler(filters.TEXT & ~filters.COMMAND, candidate_handlers.handle_message)
            ],
            CandidateStates.INTERVIEW_PREP: [
                CallbackQueryHandler(button_handlers.button_click),
                MessageHandler(filters.TEXT & ~filters.COMMAND, command_handlers.unknown_message)
            ],
            CandidateStates.SCHEDULE_INTERVIEW: [
                CallbackQueryHandler(button_handlers.button_click),
                MessageHandler(filters.TEXT & ~filters.COMMAND, command_handlers.unknown_message)
            ],
            CandidateStates.CONTACT_DEVELOPERS: [
                CallbackQueryHandler(button_handlers.button_click),
                MessageHandler(filters.TEXT & ~filters.COMMAND, command_handlers.unknown_message)
            ],
        },
        fallbacks=[
            CommandHandler('start', command_handlers.start),
            MessageHandler(filters.COMMAND, command_handlers.unknown_command)
        ]
    )
    
    # Add conversation handler to the application
    application.add_handler(conv_handler)
    
    # Add standalone command handlers
    application.add_handler(CommandHandler('help', command_handlers.help_command))
    application.add_handler(CommandHandler('menu', command_handlers.menu_command))
    
    # Add handlers for unknown commands and messages (outside of conversation)
    application.add_handler(MessageHandler(filters.COMMAND, command_handlers.unknown_command))
    application.add_handler(MessageHandler(filters.TEXT, command_handlers.unknown_message))
    
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
