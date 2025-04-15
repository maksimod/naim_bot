import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import database as db
from config import CandidateStates
from utils.helpers import load_text_content, load_test_questions

logger = logging.getLogger(__name__)

async def send_main_menu(update, context, message=None, edit=False):
    """Send the main menu with appropriate buttons based on user's unlocked stages"""
    user_id = update.effective_user.id
    unlocked_stages = db.get_user_unlocked_stages(user_id)
    
    # Get test results for emoji display
    user_test_results = db.get_user_test_results(user_id)
    
    # Define all menu options with their locked/unlocked status and test results
    menu_options = [
        ("about_company", "🟢 Узнать о компании"),
        ("primary_file", "🟢 Первичный файл"),
        ("where_to_start", "🔴 С чего начать"),
        ("preparation_materials", "🔴 Материалы для подготовки"),
        ("take_test", "🔴 Пройти испытание"),
        ("interview_prep", "🔴 Подготовка к собеседованию"),
        ("schedule_interview", "🔴 Пройти собеседование")
    ]
    
    # Create keyboard with unlocked buttons and test status indicators
    keyboard = []
    for stage_id, stage_name in menu_options:
        # Special handling for primary_file to show test result status
        if stage_id == "primary_file" and "primary_test" in user_test_results:
            if user_test_results["primary_test"]:
                # Test passed
                stage_name = stage_name.replace("🟢", "✅")  # Replace green circle with checkmark
            else:
                # Test failed
                stage_name = stage_name.replace("🟢", "❌")  # Replace green circle with X mark
            keyboard.append([InlineKeyboardButton(stage_name, callback_data=stage_id)])
            continue  # Skip the rest of the loop for this item
            
        # Special handling for where_to_start - only unlock after primary test
        if stage_id == "where_to_start":
            # Check if there's a test result for primary_test
            if "primary_test" in user_test_results:
                # If there's a test result, this stage should be unlocked
                if stage_id not in unlocked_stages:
                    db.unlock_stage(user_id, "where_to_start")
                    unlocked_stages = db.get_user_unlocked_stages(user_id)  # Refresh unlocked stages
                
                # Check if there's a test result for this stage
                if "where_to_start_test" in user_test_results:
                    if user_test_results["where_to_start_test"]:
                        # Test passed
                        stage_name = stage_name.replace("🔴", "✅")  # Replace red circle with checkmark
                    else:
                        # Test failed
                        stage_name = stage_name.replace("🔴", "❌")  # Replace red circle with X mark
                else:
                    # No test result - show as unlocked
                    stage_name = stage_name.replace("🔴", "🟢")  # Replace red circle with green circle
                
                keyboard.append([InlineKeyboardButton(stage_name, callback_data=stage_id)])
                continue  # Skip the rest of the loop for this item
        
        # Get test status for this stage if applicable
        test_name = None
        if stage_id == "preparation_materials":
            test_name = "where_to_start_test"
        elif stage_id == "take_test":
            test_name = "preparation_test"
        
        # Check if there's a test result for this stage
        if test_name and test_name in user_test_results:
            # Test was taken - show ✅ for passed or ❌ for failed
            if user_test_results[test_name]:
                # Test passed
                if stage_id in unlocked_stages:
                    stage_name = stage_name.replace("🔴", "✅")  # Replace red circle with checkmark
                    keyboard.append([InlineKeyboardButton(stage_name, callback_data=stage_id)])
                else:
                    stage_name = stage_name.replace("🔴", "✅")  # Still show checkmark but keep locked
                    keyboard.append([InlineKeyboardButton(stage_name, callback_data="locked")])
            else:
                # Test failed
                stage_name = stage_name.replace("🔴", "❌")  # Replace red circle with X mark
                keyboard.append([InlineKeyboardButton(stage_name, callback_data="locked")])
        else:
            # No test result - show regular lock/unlock status
            if stage_id in unlocked_stages:
                stage_name = stage_name.replace("🔴", "🟢")  # Replace red circle with green circle
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

async def send_test_question(update, context, edit_message=False):
    """Send a test question to the user with smart message updates"""
    test_data = context.user_data.get("test_data", [])
    current_question = context.user_data.get("current_question", 0)
    
    # Проверяем наличие тестовых данных
    if not test_data:
        await update.effective_chat.send_message("Ошибка: тестовые данные отсутствуют. Пожалуйста, попробуйте позже.")
        return await send_main_menu(update, context)
    
    # Проверяем, не вышли ли мы за пределы доступных вопросов
    if current_question >= len(test_data):
        return await handle_test_completion(update, context)
    
    question = test_data[current_question]
    question_text = f"Вопрос {current_question + 1} из {len(test_data)}:\n\n{question['question']}"
    
    # Create answers as buttons
    keyboard = []
    for i, answer in enumerate(question['answers']):
        keyboard.append([InlineKeyboardButton(f"{i+1}. {answer}", callback_data=f"answer_{i}")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if edit_message and hasattr(update, 'callback_query') and update.callback_query:
        try:
            await update.callback_query.edit_message_text(
                text=question_text,
                reply_markup=reply_markup
            )
        except Exception as e:
            logger.error(f"Error editing message for test question: {e}")
            # If editing fails, send as a new message
            message = await update.effective_chat.send_message(
                text=question_text,
                reply_markup=reply_markup
            )
            context.user_data["test_message_id"] = message.message_id
    else:
        # Send as a new message
        message = await update.effective_chat.send_message(
            text=question_text,
            reply_markup=reply_markup
        )
        context.user_data["test_message_id"] = message.message_id

async def handle_test_completion(update, context):
    """Handle the completion of a test and determine if user passed"""
    test_name = context.user_data.get("current_test")
    correct_answers = context.user_data.get("correct_answers", 0)
    test_data = context.user_data.get("test_data", [])
    user_id = update.effective_user.id
    
    if not test_data:
        await update.effective_chat.send_message("Ошибка при обработке теста. Пожалуйста, попробуйте позже.")
        return await send_main_menu(update, context)
    
    # Calculate the passing score (50% or more)
    total_questions = len(test_data)
    passing_score = total_questions // 2
    passed = correct_answers > passing_score
    
    # Save test result
    db.update_test_result(user_id, test_name, passed)
    
    # Формируем результирующее сообщение
    if passed:
        # Determine next stage to unlock based on current test
        next_stage = None
        if test_name == "primary_test":
            next_stage = "where_to_start"
        elif test_name == "where_to_start_test":
            next_stage = "preparation_materials"
        elif test_name == "preparation_test":
            next_stage = "take_test"
        
        # Unlock the next stage if applicable
        if next_stage:
            db.unlock_stage(user_id, next_stage)
        
        # Текст для успешного прохождения теста
        result_message = (
            f"🎉 Поздравляем! Вы успешно прошли тест!\n\n"
            f"Правильных ответов: {correct_answers} из {total_questions}\n\n"
            f"Следующий этап разблокирован. Продолжайте свое путешествие по нашей программе найма!"
        )
    else:
        # Текст для неудачного прохождения теста
        result_message = (
            f"❌ К сожалению, вы не прошли тест.\n\n"
            f"Правильных ответов: {correct_answers} из {total_questions}\n\n"
            f"Пожалуйста, внимательно изучите материалы и попробуйте снова позже."
        )
    
    # Попытка редактировать существующее сообщение вместо отправки нового
    keyboard = [
        [InlineKeyboardButton("⬅️ Вернуться в главное меню", callback_data="back_to_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if hasattr(update, 'callback_query') and update.callback_query:
        try:
            await update.callback_query.edit_message_text(
                text=result_message,
                reply_markup=reply_markup
            )
        except Exception as e:
            logger.error(f"Error editing message for test result: {e}")
            await update.effective_chat.send_message(
                text=result_message,
                reply_markup=reply_markup
            )
    else:
        await update.effective_chat.send_message(
            text=result_message,
            reply_markup=reply_markup
        )
    
    # Clear test data from context
    if "current_test" in context.user_data:
        del context.user_data["current_test"]
    if "test_data" in context.user_data:
        del context.user_data["test_data"]
    if "current_question" in context.user_data:
        del context.user_data["current_question"]
    if "correct_answers" in context.user_data:
        del context.user_data["correct_answers"]
    
    # Не возвращаемся сразу в главное меню, т.к. пользователь может 
    # захотеть прочитать сообщение о результатах
    return CandidateStates.MAIN_MENU

async def handle_test_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle user's answer to a test question"""
    query = update.callback_query
    await query.answer()
    
    test_data = context.user_data.get("test_data", [])
    current_question = context.user_data.get("current_question", 0)
    
    if not test_data or current_question >= len(test_data):
        return await send_main_menu(update, context)
    
    # Parse the answer index from callback data
    try:
        answer_index = int(query.data.split('_')[1])
        question = test_data[current_question]
        is_correct = answer_index == question['correct_index']
        
        if is_correct:
            # Increment correct answers count
            context.user_data["correct_answers"] = context.user_data.get("correct_answers", 0) + 1
            feedback_text = "✅ Правильно!"
        else:
            feedback_text = f"❌ Неправильно. Правильный ответ: {question['answers'][question['correct_index']]}"
        
        # Show feedback
        await query.edit_message_text(
            text=f"{query.message.text}\n\n{feedback_text}",
            reply_markup=None
        )
        
        # Move to next question after a brief pause
        await asyncio.sleep(2)
        context.user_data["current_question"] = current_question + 1
        return await send_test_question(update, context)
    
    except (ValueError, IndexError, KeyError) as e:
        logger.error(f"Error processing test answer: {e}")
        await query.message.reply_text("Ошибка при обработке ответа. Пожалуйста, попробуйте снова.")
        return await send_main_menu(update, context)
