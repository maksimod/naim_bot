import os
import json
import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes, ConversationHandler
import database as db
from config import CandidateStates, CANDIDATE_BOT_TOKEN

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Initialize database
db.init_db()

# Helper functions
def load_text_content(filename):
    """Load text content from a file in the materials folder"""
    try:
        with open(f'materials/{filename}', 'r', encoding='utf-8') as file:
            return file.read()
    except Exception as e:
        logger.error(f"Error loading text content from {filename}: {e}")
        return f"Error loading content from {filename}. Please contact the administrator."

def load_test_questions(filename):
    """Load test questions from a JSON file in the materials folder"""
    try:
        with open(f'materials/{filename}', 'r', encoding='utf-8') as file:
            return json.load(file)
    except Exception as e:
        logger.error(f"Error loading test questions from {filename}: {e}")
        return None

async def send_main_menu(update, context, message=None, edit=False):
    """Send the main menu with appropriate buttons based on user's unlocked stages"""
    user_id = update.effective_user.id
    unlocked_stages = db.get_user_unlocked_stages(user_id)
    
    # Get test results for emoji display
    user_test_results = db.get_user_test_results(user_id)
    
    # Define all menu options with their locked/unlocked status and test results
    menu_options = [
        ("about_company", "🔓 Узнать о компании"),
        ("primary_file", "🔓 Первичный файл"),
        ("where_to_start", "🔒 С чего начать"),
        ("preparation_materials", "🔒 Материалы для подготовки"),
        ("take_test", "🔒 Пройти испытание"),
        ("interview_prep", "🔒 Подготовка к собеседованию"),
        ("schedule_interview", "🔒 Пройти собеседование")
    ]
    
    # Create keyboard with unlocked buttons and test status indicators
    keyboard = []
    for stage_id, stage_name in menu_options:
        # Get test status for this stage if applicable
        test_name = None
        if stage_id == "where_to_start":
            test_name = "primary_test"
        elif stage_id == "preparation_materials":
            test_name = "where_to_start_test"
        elif stage_id == "take_test":
            test_name = "preparation_test"
        
        # Check if there's a test result for this stage
        if test_name and test_name in user_test_results:
            # Test was taken - show ✅ for passed or ❌ for failed
            if user_test_results[test_name]:
                # Test passed
                if stage_id in unlocked_stages:
                    stage_name = stage_name.replace("🔒", "✅")  # Replace lock with checkmark
                    keyboard.append([InlineKeyboardButton(stage_name, callback_data=stage_id)])
                else:
                    stage_name = stage_name.replace("🔒", "✅")  # Still show checkmark but keep locked
                    keyboard.append([InlineKeyboardButton(stage_name, callback_data="locked")])
            else:
                # Test failed
                stage_name = stage_name.replace("🔒", "❌")  # Replace lock with X mark
                keyboard.append([InlineKeyboardButton(stage_name, callback_data="locked")])
        else:
            # No test result - show regular lock/unlock status
            if stage_id in unlocked_stages:
                stage_name = stage_name.replace("🔒", "🔓")  # Replace lock with unlock
                keyboard.append([InlineKeyboardButton(stage_name, callback_data=stage_id)])
            else:
                keyboard.append([InlineKeyboardButton(stage_name, callback_data="locked")])
    
    # Add contact developers button
    keyboard.append([InlineKeyboardButton("📞 Связаться с разработчиками", callback_data="contact_developers")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # If a custom message is provided, use it, otherwise use the default menu header
    if not message:
        message = "Главное меню:"
    
    # Always try to edit the existing message first if we have a callback query and edit=True
    if edit and hasattr(update, 'callback_query') and update.callback_query:
        try:
            # Try to edit the current message
            await update.callback_query.edit_message_text(
                text=message,
                reply_markup=reply_markup
            )
            return CandidateStates.MAIN_MENU
        except Exception as e:
            logger.error(f"Error editing message via callback query: {e}")
            # Fall through to other methods if this fails
    
    # Try to edit the last main menu message if we have its ID
    if edit and context.user_data.get("main_menu_message_id"):
        try:
            # Try to edit the existing menu message
            await context.bot.edit_message_text(
                chat_id=update.effective_chat.id,
                message_id=context.user_data["main_menu_message_id"],
                text=message,
                reply_markup=reply_markup
            )
            return CandidateStates.MAIN_MENU
        except Exception as e:
            logger.error(f"Error editing main menu message: {e}")
            # If editing fails, continue to send a new message
    
    # Send a new message if editing is not possible or not requested
    menu_message = await update.effective_message.reply_text(message, reply_markup=reply_markup)
    context.user_data["main_menu_message_id"] = menu_message.message_id
    return CandidateStates.MAIN_MENU

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

# Callback query handlers
async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button clicks from the inline keyboard."""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    unlocked_stages = db.get_user_unlocked_stages(user_id)
    
    # Try to delete the content message if it exists and we're clicking on a menu option
    # (except back_to_menu which handles this separately)
    if "content_message_id" in context.user_data and query.data != "back_to_menu":
        try:
            # Delete the content message
            await context.bot.delete_message(
                chat_id=update.effective_chat.id,
                message_id=context.user_data["content_message_id"]
            )
            # Remove the content message ID from user data
            del context.user_data["content_message_id"]
        except Exception as e:
            logger.error(f"Error deleting content message: {e}")
    
    if query.data == "locked":
        # Use edit_message_text to update the existing message instead of sending a new one
        try:
            await query.edit_message_text(
                "Этот раздел пока заблокирован. Пройдите предыдущие этапы, чтобы разблокировать его.",
                reply_markup=query.message.reply_markup
            )
        except Exception as e:
            logger.error(f"Error updating message: {e}")
            # Don't send a new message, just return to main menu
            return await send_main_menu(update, context, edit=True)
        return CandidateStates.MAIN_MENU
    
    # Define menu options
    menu_options = [
        ("about_company", "🔓 Узнать о компании"),
        ("primary_file", "🔓 Первичный файл"),
        ("where_to_start", "🔒 С чего начать"),
        ("preparation_materials", "🔒 Материалы для подготовки"),
        ("take_test", "🔒 Пройти испытание"),
        ("interview_prep", "🔒 Подготовка к собеседованию"),
        ("schedule_interview", "🔒 Пройти собеседование")
    ]
    
    # Handle different menu options
    if query.data == "about_company":
        content = load_text_content("about_company.txt")
        
        # Replace the current menu message with the content
        try:
            # Add back button at the bottom of the content
            keyboard = [
                [InlineKeyboardButton("⬅️ Вернуться в главное меню", callback_data="back_to_menu")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Edit the current message (which is the menu) to show the content with back button
            await query.edit_message_text(
                content,
                reply_markup=reply_markup
            )
            
            # Store this message ID as the content message for future reference
            context.user_data["content_message_id"] = query.message.message_id
        except Exception as e:
            logger.error(f"Error editing message: {e}")
            # If editing fails, just return to main menu
            return await send_main_menu(update, context, edit=True)
        
        return CandidateStates.MAIN_MENU
    
    elif query.data == "primary_file":
        # Send the primary file
        content = load_text_content("primary_file.txt")
        
        # Replace the current menu message with the content
        try:
            # Add test and back buttons at the bottom of the content
            keyboard = [
                [InlineKeyboardButton("✅ Пройти тест по первичному файлу", callback_data="primary_test")],
                [InlineKeyboardButton("⬅️ Вернуться в главное меню", callback_data="back_to_menu")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Edit the current message (which is the menu) to show the content with test button
            await query.edit_message_text(
                content + "\n\nТеперь, чтобы разблокировать следующий этап, вам необходимо пройти тест.",
                reply_markup=reply_markup
            )
            
            # Store this message ID as the content message for future reference
            context.user_data["content_message_id"] = query.message.message_id
        except Exception as e:
            logger.error(f"Error editing message: {e}")
            # If editing fails, just return to main menu
            return await send_main_menu(update, context, edit=True)
        
        return CandidateStates.MAIN_MENU
    
    elif query.data == "primary_test":
        # Delete the content message if it exists
        try:
            if "content_message_id" in context.user_data:
                # Delete the content message
                await context.bot.delete_message(
                    chat_id=update.effective_chat.id,
                    message_id=context.user_data["content_message_id"]
                )
                # Remove the content message ID from user data
                del context.user_data["content_message_id"]
        except Exception as e:
            logger.error(f"Error deleting content message: {e}")
        
        # Show warning before starting the test
        warning_message = (
            "⚠️ <b>ВНИМАНИЕ!</b> ⚠️\n\n" +
            "Перед началом теста, пожалуйста, внимательно ознакомьтесь с материалами. " +
            "<b>Если вы не пройдете тест, вы будете заблокированы в системе.</b>\n\n" +
            "Вы уверены, что готовы начать тест?"
        )
        
        keyboard = [
            [InlineKeyboardButton("✅ Да, я готов", callback_data="confirm_primary_test")],
            [InlineKeyboardButton("❌ Нет, вернуться к материалам", callback_data="primary_file")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Edit the current message to show the warning
        try:
            await query.edit_message_text(warning_message, reply_markup=reply_markup, parse_mode='HTML')
        except Exception as e:
            logger.error(f"Error editing message: {e}")
            # If editing fails, send as a new message
            await query.message.reply_text(warning_message, reply_markup=reply_markup, parse_mode='HTML')
        
        return CandidateStates.PRIMARY_FILE
        
    elif query.data == "confirm_primary_test":
        # Load test questions
        test_data = load_test_questions("primary_test.json")
        if not test_data:
            await query.message.reply_text("Ошибка загрузки теста. Пожалуйста, попробуйте позже.")
            return CandidateStates.MAIN_MENU
        
        # Store test data in context
        context.user_data["current_test"] = "primary_test"
        context.user_data["test_data"] = test_data
        context.user_data["current_question"] = 0
        context.user_data["correct_answers"] = 0
        
        # Send the first question by editing the current message
        try:
            await send_test_question(update, context, edit_message=True)
        except Exception as e:
            logger.error(f"Error editing message for test: {e}")
            # If editing fails, send as a new message
            await send_test_question(update, context, edit_message=False)
        
        return CandidateStates.PRIMARY_TEST
    
    elif query.data == "where_to_start" and "where_to_start" in unlocked_stages:
        content = load_text_content("where_to_start.txt")
        await query.message.reply_text(content)
        
        # Offer to take the test
        keyboard = [[InlineKeyboardButton("Пройти тест", callback_data="where_to_start_test")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text(
            "Чтобы разблокировать следующий этап, пройдите тест.",
            reply_markup=reply_markup
        )
        return CandidateStates.WHERE_TO_START
    
    elif query.data == "where_to_start_test":
        # Show warning before starting the test
        warning_message = (
            "⚠️ <b>ВНИМАНИЕ!</b> ⚠️\n\n" +
            "Перед началом теста, пожалуйста, внимательно ознакомьтесь с материалами. " +
            "<b>Если вы не пройдете тест, вы будете заблокированы в системе.</b>\n\n" +
            "Вы уверены, что готовы начать тест?"
        )
        
        keyboard = [
            [InlineKeyboardButton("✅ Да, я готов", callback_data="confirm_where_to_start_test")],
            [InlineKeyboardButton("❌ Нет, вернуться к материалам", callback_data="where_to_start")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.message.reply_text(warning_message, reply_markup=reply_markup, parse_mode='HTML')
        return CandidateStates.WHERE_TO_START
        
    elif query.data == "confirm_where_to_start_test":
        # Load test questions
        test_data = load_test_questions("where_to_start_test.json")
        if not test_data:
            await query.message.reply_text("Ошибка загрузки теста. Пожалуйста, попробуйте позже.")
            return CandidateStates.MAIN_MENU
        
        # Store test data in context
        context.user_data["current_test"] = "where_to_start_test"
        context.user_data["test_data"] = test_data
        context.user_data["current_question"] = 0
        context.user_data["correct_answers"] = 0
        
        # Send the first question
        await send_test_question(update, context)
        return CandidateStates.WHERE_TO_START_TEST
    
    elif query.data == "preparation_materials" and "preparation_materials" in unlocked_stages:
        content = load_text_content("preparation_materials.txt")
        await query.message.reply_text(content)
        
        # Offer to take the test
        keyboard = [[InlineKeyboardButton("Пройти тест", callback_data="preparation_test")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text(
            "Чтобы разблокировать следующий этап, пройдите тест.",
            reply_markup=reply_markup
        )
        return CandidateStates.PREPARATION_MATERIALS
    
    elif query.data == "preparation_test":
        # Show warning before starting the test
        warning_message = (
            "⚠️ <b>ВНИМАНИЕ!</b> ⚠️\n\n" +
            "Перед началом теста, пожалуйста, внимательно ознакомьтесь с материалами. " +
            "<b>Если вы не пройдете тест, вы будете заблокированы в системе.</b>\n\n" +
            "Вы уверены, что готовы начать тест?"
        )
        
        keyboard = [
            [InlineKeyboardButton("✅ Да, я готов", callback_data="confirm_preparation_test")],
            [InlineKeyboardButton("❌ Нет, вернуться к материалам", callback_data="preparation_materials")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.message.reply_text(warning_message, reply_markup=reply_markup, parse_mode='HTML')
        return CandidateStates.PREPARATION_MATERIALS
        
    elif query.data == "confirm_preparation_test":
        # Load test questions
        test_data = load_test_questions("preparation_test.json")
        if not test_data:
            await query.message.reply_text("Ошибка загрузки теста. Пожалуйста, попробуйте позже.")
            return CandidateStates.MAIN_MENU
        
        # Store test data in context
        context.user_data["current_test"] = "preparation_test"
        context.user_data["test_data"] = test_data
        context.user_data["current_question"] = 0
        context.user_data["correct_answers"] = 0
        
        # Send the first question
        await send_test_question(update, context)
        return CandidateStates.PREPARATION_MATERIALS
    
    elif query.data == "take_test" and "take_test" in unlocked_stages:
        content = load_text_content("test_task.txt")
        await query.message.reply_text(content)
        await query.message.reply_text(
            "Когда вы выполните задание, отправьте файл с вашим решением. "  
            "Наши специалисты проверят его и предоставят обратную связь."
        )
        return CandidateStates.TAKE_TEST
    
    elif query.data == "interview_prep" and "interview_prep" in unlocked_stages:
        content = load_text_content("interview_prep.txt")
        await query.message.reply_text(content)
        
        keyboard = [[InlineKeyboardButton("Запланировать собеседование", callback_data="schedule_interview")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text(
            "Когда вы будете готовы, вы можете запланировать собеседование.",
            reply_markup=reply_markup
        )
        return CandidateStates.INTERVIEW_PREP
    
    elif query.data == "schedule_interview" and ("schedule_interview" in unlocked_stages or "interview_prep" in unlocked_stages):
        await query.message.reply_text(
            "Пожалуйста, укажите предпочтительный день недели и время для собеседования. \n\n"
            "Например: 'Понедельник, 15:00' или 'Среда, 10:30'."
        )
        return CandidateStates.SCHEDULE_INTERVIEW
    
    # Contact developers
    elif query.data == "contact_developers":
        # Edit the message to include the return button
        keyboard = [
            [InlineKeyboardButton("📞 Перейти в группу разработчиков", url="https://t.me/+iJCNlqsPgO0wN2Yy")],
            [InlineKeyboardButton("⬅️ Вернуться в главное меню", callback_data="back_to_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        try:
            await query.edit_message_text(
                "Вы можете связаться с командой разработчиков, нажав на кнопку ниже:",
                reply_markup=reply_markup
            )
        except Exception as e:
            logger.error(f"Error updating message: {e}")
            await query.message.reply_text(
                "Вы можете связаться с командой разработчиков, нажав на кнопку ниже:",
                reply_markup=reply_markup
            )
        
        return CandidateStates.MAIN_MENU
    
    # Back to menu from any section
    elif query.data == "back_to_menu":
        # Try to delete the content message if it exists
        try:
            if "content_message_id" in context.user_data:
                # Delete the content message
                await context.bot.delete_message(
                    chat_id=update.effective_chat.id,
                    message_id=context.user_data["content_message_id"]
                )
                # Remove the content message ID from user data
                del context.user_data["content_message_id"]
        except Exception as e:
            logger.error(f"Error deleting content message: {e}")
        
        # Check if we need to edit the main menu message or create a new one
        if "main_menu_message_id" in context.user_data and context.user_data["main_menu_message_id"] == query.message.message_id:
            # We're already on the main menu message, just update it
            try:
                # Get user data for menu customization
                user_id = update.effective_user.id
                unlocked_stages = db.get_user_unlocked_stages(user_id)
                user_test_results = db.get_user_test_results(user_id)
                
                # Create keyboard with standard menu options
                keyboard = []
                for stage_id, stage_name in menu_options:
                    # Add the standard menu options with appropriate locks/unlocks
                    if stage_id in unlocked_stages:
                        stage_name = stage_name.replace("🔒", "🔓")  # Replace lock with unlock
                        keyboard.append([InlineKeyboardButton(stage_name, callback_data=stage_id)])
                    else:
                        keyboard.append([InlineKeyboardButton(stage_name, callback_data="locked")])
                
                # Add contact developers button
                keyboard.append([InlineKeyboardButton("📞 Связаться с разработчиками", callback_data="contact_developers")])
                
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                # Edit the current message to show the main menu
                await query.edit_message_text(
                    "Главное меню:",
                    reply_markup=reply_markup
                )
                
                return CandidateStates.MAIN_MENU
            except Exception as e:
                logger.error(f"Error editing message for main menu: {e}")
                # Fallback to the regular send_main_menu function
                return await send_main_menu(update, context, edit=True)
        else:
            # We're on a different message, delete current message and send a new main menu
            try:
                # Delete the current message
                await context.bot.delete_message(
                    chat_id=update.effective_chat.id,
                    message_id=query.message.message_id
                )
            except Exception as e:
                logger.error(f"Error deleting current message: {e}")
            
            # Send a new main menu message
            return await send_main_menu(update, context)
        
    # Handle test answers
    elif query.data.startswith("answer_"):
        return await handle_test_answer(update, context)
    
    # Default case - return to main menu
    return await send_main_menu(update, context)

async def send_test_question(update, context, edit_message=False):
    """Send a test question to the user with smart message updates"""
    test_data = context.user_data.get("test_data")
    current_question = context.user_data.get("current_question", 0)
    
    if not test_data or current_question >= len(test_data["questions"]):
        await update.effective_message.reply_text("Ошибка: тест не найден или вопросы закончились.")
        return await send_main_menu(update, context)
    
    question = test_data["questions"][current_question]
    question_text = f"Вопрос {current_question + 1}/{len(test_data['questions'])}:\n\n{question['question']}"
    
    # Create keyboard with answer options
    keyboard = []
    for i, option in enumerate(question["options"]):
        keyboard.append([InlineKeyboardButton(option, callback_data=f"answer_{i}")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Check if we should edit the current message or send a new one
    if (edit_message or current_question > 0) and hasattr(update, 'callback_query') and update.callback_query:
        # Edit the current message to show the question (reduces chat clutter)
        try:
            await update.callback_query.edit_message_text(question_text, reply_markup=reply_markup)
        except Exception as e:
            logger.error(f"Error editing message: {e}")
            # Fallback to sending a new message if editing fails
            await update.effective_message.reply_text(question_text, reply_markup=reply_markup)
    else:
        # Send a new message for the first question
        await update.effective_message.reply_text(question_text, reply_markup=reply_markup)

async def handle_test_answer(update, context):
    """Handle user's answer to a test question"""
    query = update.callback_query
    await query.answer()
    
    # Get the selected answer index
    selected_answer = int(query.data.split("_")[1])
    
    # Get test data from context
    test_data = context.user_data.get("test_data")
    current_question = context.user_data.get("current_question", 0)
    correct_answers = context.user_data.get("correct_answers", 0)
    current_test = context.user_data.get("current_test")
    
    if not test_data or current_question >= len(test_data["questions"]):
        await query.message.reply_text("Ошибка: тест не найден или вопросы закончились.")
        return await send_main_menu(update, context)
    
    # Check if the answer is correct
    correct_answer = test_data["questions"][current_question]["correct_answer"]
    if selected_answer == correct_answer:
        context.user_data["correct_answers"] = correct_answers + 1
        await query.message.reply_text("✅ Правильно!")
    else:
        await query.message.reply_text(f"❌ Неправильно. Правильный ответ: {test_data['questions'][current_question]['options'][correct_answer]}")
    
    # Move to the next question or finish the test
    context.user_data["current_question"] = current_question + 1
    
    if context.user_data["current_question"] < len(test_data["questions"]):
        # Send the next question
        await send_test_question(update, context)
        if current_test == "primary_test":
            return CandidateStates.PRIMARY_TEST
        elif current_test == "where_to_start_test":
            return CandidateStates.WHERE_TO_START_TEST
        else:
            return CandidateStates.PREPARATION_MATERIALS
    else:
        # Test is finished, calculate the result
        total_questions = len(test_data["questions"])
        correct_answers = context.user_data["correct_answers"]
        score_percentage = (correct_answers / total_questions) * 100
        
        # Check if the user passed the test (more than 50%)
        passed = score_percentage > 50
        
        result_message = f"Тест завершен!\n\nПравильных ответов: {correct_answers}/{total_questions} ({score_percentage:.1f}%)\n\n"
        
        user_id = update.effective_user.id
        
        # Save test result
        db.update_test_result(user_id, current_test, passed)
        
        # Get all test results to check if more than half failed
        test_results = db.get_user_test_results(user_id)
        total_tests = len(test_results)
        failed_tests = sum(1 for result in test_results.values() if not result)
        
        # Check if more than half of all tests failed
        if total_tests > 0 and failed_tests > total_tests / 2:
            # Permanently block the user
            result_message += "<b>К сожалению, вы не прошли больше половины тестов и были полностью заблокированы в системе.</b>\n\nДля повторной попытки свяжитесь с администратором."
            
            # Reset user's unlocked stages to only the first two options
            conn = sqlite3.connect(DATABASE_NAME)
            cursor = conn.cursor()
            
            unlocked_stages = json.dumps([
                'about_company',
                'primary_file'
            ])
            
            cursor.execute(
                'UPDATE users SET unlocked_stages = ? WHERE user_id = ?',
                (unlocked_stages, user_id)
            )
            
            conn.commit()
            conn.close()
        elif passed:
            result_message += "🎉 Поздравляем! Вы успешно прошли тест и разблокировали следующий этап."
            
            # Unlock the next stage based on the current test
            if current_test == "primary_test":
                db.unlock_stage(user_id, "where_to_start")
            elif current_test == "where_to_start_test":
                db.unlock_stage(user_id, "preparation_materials")
            elif current_test == "preparation_test":
                db.unlock_stage(user_id, "take_test")
            
            # Check if user has passed enough tests to unlock interview
            if total_tests > 0 and failed_tests <= total_tests / 2 and "take_test" in db.get_user_unlocked_stages(user_id):
                db.unlock_stage(user_id, "interview_prep")
        else:
            result_message += "<b>К сожалению, вы не прошли этот тест.</b> Вы можете продолжить изучение материалов, но если вы не пройдете больше половины тестов, вы будете заблокированы."
        
        # Add a button to return to the main menu
        keyboard = [[InlineKeyboardButton("⬅️ Вернуться в главное меню", callback_data="back_to_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Send the result message with the return button
        await query.message.reply_text(result_message, parse_mode='HTML')
        await query.message.reply_text("Вы можете вернуться в главное меню:", reply_markup=reply_markup)
        
        # Don't automatically show the main menu, let the user click the button
        return CandidateStates.MAIN_MENU

async def handle_file_submission(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle file submission for the test task"""
    user_id = update.effective_user.id
    unlocked_stages = db.get_user_unlocked_stages(user_id)
    
    if "take_test" not in unlocked_stages:
        await update.message.reply_text("Вы еще не разблокировали этап с тестовым заданием.")
        return CandidateStates.MAIN_MENU
    
    # Get the file
    file = update.message.document
    file_id = file.file_id
    file_name = file.file_name
    
    # Save submission to database
    submission_data = {
        "file_id": file_id,
        "file_name": file_name
    }
    submission_id = db.save_test_submission(user_id, "practical_test", submission_data)
    
    await update.message.reply_text(
        f"Спасибо за отправку решения! Ваш файл '{file_name}' получен и будет проверен нашими специалистами. \n\n"
        f"Идентификатор вашей заявки: #{submission_id}\n\n"
        "Мы сообщим вам результаты проверки."
    )
    
    return CandidateStates.MAIN_MENU

async def handle_developer_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle messages to developers"""
    user_id = update.effective_user.id
    user_name = update.effective_user.full_name
    message_text = update.message.text.strip()
    
    # Log the message
    logger.info(f"User {user_id} ({user_name}) sent a message to developers: {message_text}")
    
    # Store the message in the database for the recruiter bot to access
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    
    cursor.execute(
        'INSERT INTO developer_messages (user_id, user_name, message, timestamp) VALUES (?, ?, ?, datetime("now"))',
        (user_id, user_name, message_text)
    )
    
    conn.commit()
    conn.close()
    
    # Send confirmation to the user
    await update.message.reply_text(
        "Спасибо! Ваше сообщение было передано команде разработчиков. Мы свяжемся с вами в ближайшее время."
    )
    
    # Return to main menu
    return await send_main_menu(update, context)

async def handle_interview_scheduling(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle interview scheduling request"""
    user_id = update.effective_user.id
    unlocked_stages = db.get_user_unlocked_stages(user_id)
    
    if "interview_prep" not in unlocked_stages and "schedule_interview" not in unlocked_stages:
        await update.message.reply_text("Вы еще не разблокировали этап подготовки к собеседованию.")
        return CandidateStates.MAIN_MENU
    
    # Parse the preferred day and time
    text = update.message.text.strip()
    parts = text.split(",")
    
    if len(parts) != 2:
        await update.message.reply_text(
            "Пожалуйста, укажите день недели и время в формате: 'День недели, ЧЧ:ММ'\n"
            "Например: 'Понедельник, 15:00' или 'Среда, 10:30'."
        )
        return CandidateStates.SCHEDULE_INTERVIEW
    
    preferred_day = parts[0].strip()
    preferred_time = parts[1].strip()
    
    # Save the interview request
    request_id = db.save_interview_request(user_id, preferred_day, preferred_time)
    
    await update.message.reply_text(
        f"Спасибо! Ваш запрос на собеседование ({preferred_day}, {preferred_time}) отправлен. \n\n"
        f"Идентификатор вашего запроса: #{request_id}\n\n"
        "Мы свяжемся с вами для подтверждения времени собеседования."
    )
    
    return CandidateStates.MAIN_MENU

async def handle_test_feedback(user_id, submission_id, status, feedback):
    """Handle feedback for a test submission"""
    from telegram.error import TelegramError
    
    try:
        # Create application instance
        application = Application.builder().token(CANDIDATE_BOT_TOKEN).build()
        
        # Prepare message
        if status == "approved":
            message = f"🎉 Поздравляем! Ваше тестовое задание одобрено.\n\nОбратная связь от рекрутера:\n{feedback}\n\nТеперь вы можете перейти к этапу подготовки к собеседованию."
            # Unlock the next stage
            db.unlock_stage(user_id, "interview_prep")
        else:
            message = f"К сожалению, ваше тестовое задание требует доработки.\n\nОбратная связь от рекрутера:\n{feedback}\n\nПожалуйста, внесите необходимые изменения и отправьте решение повторно."
        
        # Send message to user
        await application.bot.send_message(chat_id=user_id, text=message)
        
    except TelegramError as e:
        logger.error(f"Error sending test feedback to user {user_id}: {e}")

async def handle_interview_response(user_id, request_id, status, response):
    """Handle response for an interview request"""
    from telegram.error import TelegramError
    
    try:
        # Create application instance
        application = Application.builder().token(CANDIDATE_BOT_TOKEN).build()
        
        # Prepare message
        if status == "approved":
            message = f"✅ Ваш запрос на собеседование подтвержден!\n\nДетали:\n{response}\n\nПожалуйста, подготовьтесь к собеседованию и будьте вовремя."
            # Unlock the final stage if not already unlocked
            db.unlock_stage(user_id, "schedule_interview")
        else:
            message = f"❌ К сожалению, предложенное время собеседования не подходит.\n\nОтвет рекрутера:\n{response}\n\nПожалуйста, предложите другое время."
        
        # Send message to user
        await application.bot.send_message(chat_id=user_id, text=message)
        
    except TelegramError as e:
        logger.error(f"Error sending interview response to user {user_id}: {e}")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /help is issued."""
    help_text = (
        "Бот для процесса найма - помощь\n\n"
        "/start - Начать процесс найма\n"
        "/menu - Показать главное меню\n"
        "/help - Показать это сообщение\n\n"
        "Используйте кнопки в меню для навигации по этапам процесса найма."
    )
    await update.message.reply_text(help_text)
    return CandidateStates.MAIN_MENU

async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show the main menu when the command /menu is issued."""
    return await send_main_menu(update, context)

async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle unknown commands."""
    await update.message.reply_text(
        "Извините, я не понимаю эту команду. Используйте /help для получения списка доступных команд."
    )
    return CandidateStates.MAIN_MENU

async def unknown_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle unknown messages."""
    # If we're expecting an interview scheduling message, don't treat it as unknown
    if context.user_data.get("awaiting_interview_schedule"):
        return await handle_interview_scheduling(update, context)
    
    await update.message.reply_text(
        "Извините, я не понимаю это сообщение. Пожалуйста, используйте кнопки в меню для навигации."
    )
    return CandidateStates.MAIN_MENU

def main():
    """Start the bot."""
    # Create the Application with increased timeout
    application = Application.builder().token(CANDIDATE_BOT_TOKEN).connect_timeout(30.0).read_timeout(30.0).build()
    
    # Add command handlers outside of conversation handler to ensure they always work
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("menu", menu_command))
    
    # Add a global callback query handler to handle button clicks
    application.add_handler(CallbackQueryHandler(button_click))
    
    # Add conversation handler with states
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        per_message=False,
        states={
            CandidateStates.MAIN_MENU: [
                CallbackQueryHandler(button_click),
                CommandHandler("menu", menu_command),
            ],
            CandidateStates.ABOUT_COMPANY: [
                CallbackQueryHandler(button_click),
            ],
            CandidateStates.PRIMARY_FILE: [
                CallbackQueryHandler(button_click),
            ],
            CandidateStates.PRIMARY_TEST: [
                CallbackQueryHandler(button_click),
            ],
            CandidateStates.WHERE_TO_START: [
                CallbackQueryHandler(button_click),
            ],
            CandidateStates.WHERE_TO_START_TEST: [
                CallbackQueryHandler(button_click),
            ],
            CandidateStates.PREPARATION_MATERIALS: [
                CallbackQueryHandler(button_click),
            ],
            CandidateStates.TAKE_TEST: [
                MessageHandler(filters.Document.ALL, handle_file_submission),
                CallbackQueryHandler(button_click),
            ],
            CandidateStates.INTERVIEW_PREP: [
                CallbackQueryHandler(button_click),
            ],
            CandidateStates.SCHEDULE_INTERVIEW: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_interview_scheduling),
                CallbackQueryHandler(button_click),
            ],
            CandidateStates.CONTACT_DEVELOPERS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_developer_contact),
                CallbackQueryHandler(button_click),
            ],
        },
        fallbacks=[
            CommandHandler("start", start),
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
