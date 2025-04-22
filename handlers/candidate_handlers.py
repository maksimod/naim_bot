import logging
import os
import sys
import asyncio
import time
import datetime
import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import ContextTypes
import database as db

# Добавляем корневую директорию проекта в путь импорта
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import CandidateStates
from utils.helpers import load_text_content, load_test_questions, get_stopwords_data
from utils.chatgpt_helpers import generate_ai_stopword_sentence, verify_stopword_rephrasing_ai, verify_poem_task

logger = logging.getLogger(__name__)

async def send_main_menu(update, context, message=None, edit=False):
    """Send the main menu with appropriate buttons based on user's unlocked stages"""
    user_id = update.effective_user.id
    unlocked_stages = db.get_user_unlocked_stages(user_id)
    
    # Check for admin mode
    admin_mode = context.user_data.get("admin_mode", False)
    
    # Get test results for emoji display
    user_test_results = db.get_user_test_results(user_id)
    
    # In admin mode, get test results from context instead of DB
    if admin_mode:
        admin_test_results = context.user_data.get("admin_test_results", {})
        # Combine with regular results, but admin results take precedence
        display_test_results = {**user_test_results, **admin_test_results}
    else:
        display_test_results = user_test_results
    
    # Define all menu options with their locked/unlocked status and test results
    menu_options = [
        ("about_company", "🔵 Узнать о компании"),
        ("primary_file", "🟢 Первичный файл"),
        ("where_to_start", "🔴 С чего начать"),
        ("logic_test", "🔴 Тест на логику"),
        ("preparation_materials", "🔴 Материалы для подготовки"),
        ("take_test", "🔴 Пройти испытание"),
        ("interview_prep", "🔴 Подготовка к собеседованию"),
        ("schedule_interview", "🔴 Пройти собеседование")
    ]
    
    # Create keyboard with unlocked buttons and test status indicators
    keyboard = []
    
    # In admin mode, all items are unlocked and use admin_test_results
    if admin_mode:
        # Get admin test results
        admin_test_results = context.user_data.get("admin_test_results", {})
        
        for stage_id, stage_name in menu_options:
            # Make stage green (unlocked)
            stage_name = stage_name.replace("🔴", "🟢")
            
            # Check specific test results and show pass/fail
            if stage_id == "primary_file" and "primary_test" in admin_test_results:
                # Show ✅ or ❌ based on test result
                if admin_test_results["primary_test"]:
                    stage_name = stage_name.replace("🟢", "✅")
                else:
                    stage_name = stage_name.replace("🟢", "❌")
            
            elif stage_id == "where_to_start" and "where_to_start_test" in admin_test_results:
                # Show ✅ or ❌ based on test result
                if admin_test_results["where_to_start_test"]:
                    stage_name = stage_name.replace("🟢", "✅")
                else:
                    stage_name = stage_name.replace("🟢", "❌")
            
            elif stage_id == "take_test" and "take_test_result" in admin_test_results:
                # Show ✅ or ❌ based on test result
                if admin_test_results["take_test_result"]:
                    stage_name = stage_name.replace("🟢", "✅")
                else:
                    stage_name = stage_name.replace("🟢", "❌")
            
            elif stage_id == "logic_test" and "logic_test_result" in admin_test_results:
                # Show ✅ or ❌ based on test result
                if admin_test_results["logic_test_result"]:
                    stage_name = stage_name.replace("🟢", "✅")
                else:
                    stage_name = stage_name.replace("🟢", "❌")
            
            elif stage_id == "interview_prep" and "interview_prep_test" in admin_test_results:
                # Show ✅ or ❌ based on test result
                if admin_test_results["interview_prep_test"]:
                    stage_name = stage_name.replace("🟢", "✅")
                else:
                    stage_name = stage_name.replace("🟢", "❌")
            
            keyboard.append([InlineKeyboardButton(stage_name, callback_data=stage_id)])
        
        # Add contact developers button
        keyboard.append([InlineKeyboardButton("📞 Связаться с разработчиками", callback_data="contact_developers")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # If a custom message is provided, use it, otherwise use the default menu header
        if not message:
            message = "Главное меню (Режим администратора):"
        
        # Try to edit the existing message if needed
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
        
        # Send a new message if editing is not possible or not requested
        menu_message = await update.effective_message.reply_text(message, reply_markup=reply_markup)
        context.user_data["main_menu_message_id"] = menu_message.message_id
        return CandidateStates.MAIN_MENU
    
    else:
        for stage_id, stage_name in menu_options:
            # Special handling for primary_file to show test result status
            if stage_id == "primary_file" and "primary_test" in display_test_results:
                if display_test_results["primary_test"]:
                    # Test passed
                    stage_name = stage_name.replace("🟢", "✅")  # Replace green circle with checkmark
                else:
                    # Test failed
                    stage_name = stage_name.replace("🟢", "❌")  # Replace green circle with X mark
                keyboard.append([InlineKeyboardButton(stage_name, callback_data=stage_id)])
                continue  # Skip the rest of the loop for this item
                
            # Special handling for where_to_start - unlock after primary test regardless of result
            if stage_id == "where_to_start":
                # Check if there's a test result for primary_test
                if "primary_test" in display_test_results:
                    # If there's a test result, this stage should be unlocked regardless of pass/fail
                    if stage_id not in unlocked_stages:
                        db.unlock_stage(user_id, "where_to_start")
                        unlocked_stages = db.get_user_unlocked_stages(user_id)  # Refresh unlocked stages
                    
                    # Check if there's a test result for this stage
                    if "where_to_start_test" in display_test_results:
                        if display_test_results["where_to_start_test"]:
                            # Test passed
                            stage_name = stage_name.replace("🔴", "✅")  # Replace red circle with checkmark
                        else:
                            # Test failed
                            stage_name = stage_name.replace("🔴", "❌")  # Replace red circle with X mark
                    elif stage_id in unlocked_stages:
                        # No test result - show as unlocked
                        stage_name = stage_name.replace("🔴", "🟢")  # Replace red circle with green circle
                    
                    keyboard.append([InlineKeyboardButton(stage_name, callback_data=stage_id)])
                    continue  # Skip the rest of the loop for this item
            
            # Special handling for logic_test - unlock after where_to_start test regardless of result
            if stage_id == "logic_test":
                # Check if there's a test result for where_to_start_test
                if "where_to_start_test" in display_test_results:
                    # If there's a test result, this stage should be unlocked regardless of pass/fail
                    if stage_id not in unlocked_stages:
                        db.unlock_stage(user_id, "logic_test")
                        unlocked_stages = db.get_user_unlocked_stages(user_id)  # Refresh unlocked stages
                    
                    # Check if there's a test result for this stage
                    if "logic_test_result" in display_test_results:
                        if display_test_results["logic_test_result"]:
                            # Test passed
                            stage_name = stage_name.replace("🔴", "✅")  # Replace red circle with checkmark
                        else:
                            # Test failed
                            stage_name = stage_name.replace("🔴", "❌")  # Replace red circle with X mark
                    elif stage_id in unlocked_stages:
                        # No test result - show as unlocked
                        stage_name = stage_name.replace("🔴", "🟢")  # Replace red circle with green circle
            
            # Special handling for preparation_materials - unlock after logic_test result regardless of result
            if stage_id == "preparation_materials":
                # Check if there's a test result for logic_test_result
                if "logic_test_result" in display_test_results:
                    # If there's a test result, this stage should be unlocked regardless of pass/fail
                    if stage_id not in unlocked_stages:
                        db.unlock_stage(user_id, "preparation_materials")
                        unlocked_stages = db.get_user_unlocked_stages(user_id)  # Refresh unlocked stages
                    
                    if stage_id in unlocked_stages:
                        # Stage unlocked - show as green circle (not checkmark)
                        stage_name = stage_name.replace("🔴", "🟢")  # Replace red circle with green circle
            
            # Check if there's a test result for this stage
            test_name = None
            if stage_id == "take_test":
                test_name = "take_test_result"
            
            # Check if there's a test result for this stage
            if test_name and test_name in display_test_results:
                # Test was taken - show ✅ for passed or ❌ for failed
                if display_test_results[test_name]:
                    # Test passed
                    stage_name = stage_name.replace("🔴", "✅")  # Replace red circle with checkmark
                else:
                    # Test failed
                    stage_name = stage_name.replace("🔴", "❌")  # Replace red circle with X mark
                    stage_name = stage_name.replace("🟢", "❌")  # Also replace green circle with X mark if needed
                keyboard.append([InlineKeyboardButton(stage_name, callback_data=stage_id)])
            else:
                # No test result - show regular lock/unlock status
                if stage_id in unlocked_stages:
                    stage_name = stage_name.replace("🔴", "🟢")  # Replace red circle with green circle
                keyboard.append([InlineKeyboardButton(stage_name, callback_data=stage_id)])
    
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
    """Send a test question to the user"""
    test_data = context.user_data.get("test_data", {})
    current_question = context.user_data.get("current_question", 0)
    
    # Получаем вопросы из test_data
    questions = []
    if isinstance(test_data, dict) and "questions" in test_data:
        questions = test_data["questions"]
    else:
        questions = test_data
    
    if current_question >= len(questions):
        return await handle_test_completion(update, context)
    
    # Проверяем, есть ли ограничение по времени для текущего теста
    test_name = context.user_data.get("current_test")
    time_limit = None
    
    # Определяем лимит времени для теста
    if isinstance(test_data, dict) and "time_limit" in test_data:
        time_limit = test_data["time_limit"]
    
    # Если время не указано в данных теста, используем значение по умолчанию
    if time_limit is None:
        time_limit = get_test_time_limit(test_name)
    
    # Если установлен лимит времени и это первый вопрос, сохраняем время начала
    if time_limit is not None and current_question == 0 and "test_start_time" not in context.user_data:
        context.user_data["test_start_time"] = time.time()
        context.user_data["test_end_time"] = time.time() + time_limit
    
    # Получаем оставшееся время (если ограничение по времени установлено)
    time_str = ""
    if time_limit is not None:
        end_time = context.user_data.get("test_end_time")
        now = time.time()
        remaining = end_time - now
        
        if remaining <= 0:
            # Время истекло
            return await test_timeout(update, context)
        
        time_str = format_time(remaining)
    
    question = questions[current_question]
    
    # Формируем текст вопроса с учетом таймера
    if time_limit is not None:
        question_text = f"Времени осталось: {time_str}\nВопрос {current_question + 1} из {len(questions)}:\n\n{question['question']}"
    else:
        question_text = f"Вопрос {current_question + 1} из {len(questions)}:\n\n{question['question']}"
    
    # Create answers as buttons, поддерживаем оба формата: answers и options
    keyboard = []
    options = question.get('options', question.get('answers', []))
    for i, answer in enumerate(options):
        keyboard.append([InlineKeyboardButton(f"{i+1}. {answer}", callback_data=f"answer_{i}")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if edit_message and hasattr(update, 'callback_query') and update.callback_query:
        try:
            await update.callback_query.edit_message_text(
                text=question_text,
                reply_markup=reply_markup
            )
            # Сохраняем ID сообщения
            message_id = update.callback_query.message.message_id
            context.user_data["test_message_id"] = message_id
        except Exception as e:
            logger.error(f"Error editing message for test question: {e}")
            # If editing fails, send as a new message
            message = await update.effective_chat.send_message(
                text=question_text,
                reply_markup=reply_markup
            )
            context.user_data["test_message_id"] = message.message_id
            message_id = message.message_id
    else:
        # Send as a new message
        message = await update.effective_chat.send_message(
            text=question_text,
            reply_markup=reply_markup
        )
        context.user_data["test_message_id"] = message.message_id
        message_id = message.message_id
    
    # Запускаем или обновляем таймер, если есть ограничение по времени
    if time_limit is not None:
        # Останавливаем существующий таймер, если есть
        if "test_timer_job" in context.user_data:
            try:
                context.user_data["test_timer_job"].schedule_removal()
                logger.info("Таймер остановлен при завершении теста")
            except Exception as e:
                logger.error(f"Ошибка при остановке таймера: {e}")
        
        # Данные для передачи в функцию обновления таймера
        job_data = {
            "chat_id": update.effective_chat.id,
            "message_id": message_id,
            "questions": questions,
            "current_question": current_question,
            "end_time": context.user_data["test_end_time"],
            "update": update,
            "context_obj": context
        }
        
        try:
            # Запускаем таймер, который будет обновлять сообщение каждую секунду
            job = context.job_queue.run_repeating(
                update_timer,
                interval=1.0,  # Интервал обновления - 1 секунда
                first=1.0,     # Первое обновление через 1 секунду
                data=job_data,
                name=f"timer_{update.effective_chat.id}"
            )
            context.user_data["test_timer_job"] = job
            logger.info(f"Запущен таймер для теста, оставшееся время: {time_str}")
        except Exception as e:
            logger.error(f"Ошибка при запуске таймера: {e}")
            logger.error(f"Параметры задания: {job_data}")
        
        # Сохраняем данные для таймера в контексте, чтобы иметь к ним доступ при необходимости
        context.user_data["timer_data"] = {
            "message_id": message_id,
            "chat_id": update.effective_chat.id
        }

async def handle_test_completion(update, context):
    """Handle the completion of a test and determine if user passed"""
    test_name = context.user_data.get("current_test")
    correct_answers = context.user_data.get("correct_answers", 0)
    test_data = context.user_data.get("test_data", [])
    user_id = update.effective_user.id
    
    # Check for admin mode
    admin_mode = context.user_data.get("admin_mode", False)
    
    if not test_data:
        return await send_main_menu(update, context)
    
    # Get the questions array from test_data depending on format
    questions = []
    if isinstance(test_data, dict) and "questions" in test_data:
        questions = test_data["questions"]
    else:
        questions = test_data
    
    # Calculate score as a percentage
    total_questions = len(questions)
    score = (correct_answers / total_questions) * 100 if total_questions > 0 else 0
    
    # Determine if user passed (need 70% or higher)
    passed = score >= 70
    
    # Для теста на логику особое условие - минимум 22 из 30 правильных ответов
    if test_name == "logic_test_result":
        passed = correct_answers >= 22
    
    # In regular mode, save result to database
    # In admin mode, save to context.user_data instead
    if admin_mode:
        if "admin_test_results" not in context.user_data:
            context.user_data["admin_test_results"] = {}
        context.user_data["admin_test_results"][test_name] = passed
        logger.info(f"Admin mode: Test {test_name} completed with score {score:.1f}%, result: {'PASS' if passed else 'FAIL'}")
    else:
        # Save test result to database
        db.update_test_result(user_id, test_name, passed)
        logger.info(f"User {user_id} completed test {test_name} with score {score:.1f}%, result: {'PASS' if passed else 'FAIL'}")
    
    # Determine which stages should be unlocked based on the test
    # Unlock the next stage regardless of test result
    next_stage = None
    if test_name == "primary_test":
        next_stage = "where_to_start"
    elif test_name == "where_to_start_test":
        next_stage = "logic_test"
    elif test_name == "logic_test_result":
        next_stage = "preparation_materials"
    elif test_name == "take_test_result":
        next_stage = "interview_prep"
    
    # Unlock the next stage in the regular mode only
    if next_stage and not admin_mode:
        db.unlock_stage(user_id, next_stage)
    
    # Show results to the user
    if passed:
        # Текст для успешного прохождения теста
        result_message = (
            f"🎉 Поздравляем! Вы успешно прошли тест!\n\n"
            f"Правильных ответов: {correct_answers} из {total_questions}\n\n"
            f"Следующий этап разблокирован. Продолжайте свое путешествие по нашей программе найма!"
        )
    else:
        # Текст для неудачного прохождения теста
        result_message = (
            f"❌ Результат теста: не пройден.\n\n"
            f"Правильных ответов: {correct_answers} из {total_questions}\n\n"
            f"Однако, следующий этап все равно разблокирован. Вы можете продолжить, но рекомендуем еще раз просмотреть материалы."
        )
    
    # Отправляем новое сообщение с результатами теста вместо редактирования
    keyboard = [
        [InlineKeyboardButton("⬅️ Вернуться в главное меню", callback_data="back_to_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Вместо отправки нового сообщения, редактируем последнее сообщение с вопросом
    if hasattr(update, 'callback_query') and update.callback_query:
        try:
            # Редактируем последнее сообщение с вопросом
            await update.callback_query.edit_message_text(
                text=result_message,
                reply_markup=reply_markup
            )
        except Exception as e:
            logger.error(f"Error editing message for test results: {e}")
            # Если редактирование не удалось, отправляем новое сообщение
            await update.effective_chat.send_message(
                text=result_message,
                reply_markup=reply_markup
            )
    elif "test_message_id" in context.user_data:
        # Есть ID сообщения с тестом, редактируем его
        try:
            await context.bot.edit_message_text(
                chat_id=update.effective_chat.id,
                message_id=context.user_data["test_message_id"],
                text=result_message,
                reply_markup=reply_markup
            )
        except Exception as e:
            logger.error(f"Error editing stored test message: {e}")
            # Если редактирование не удалось, отправляем новое сообщение
            await update.effective_chat.send_message(
                text=result_message,
                reply_markup=reply_markup
            )
    else:
        # Нет возможности редактировать, отправляем новое сообщение
        await update.effective_chat.send_message(
            text=result_message,
            reply_markup=reply_markup
        )
    
    # Очищаем данные теста из контекста
    if "current_test" in context.user_data:
        del context.user_data["current_test"]
    if "test_data" in context.user_data:
        del context.user_data["test_data"]
    if "current_question" in context.user_data:
        del context.user_data["current_question"]
    if "correct_answers" in context.user_data:
        del context.user_data["correct_answers"]
    if "test_start_time" in context.user_data:
        del context.user_data["test_start_time"]
    if "test_end_time" in context.user_data:
        del context.user_data["test_end_time"]
    if "timer_data" in context.user_data:
        del context.user_data["timer_data"]
    
    # Останавливаем таймер, если он существует
    if "test_timer_job" in context.user_data:
        try:
            context.user_data["test_timer_job"].schedule_removal()
            logger.info("Таймер остановлен при завершении теста")
        except Exception as e:
            logger.error(f"Ошибка при остановке таймера: {e}")
        del context.user_data["test_timer_job"]
    
    # Не возвращаемся сразу в главное меню, т.к. пользователь может 
    # захотеть прочитать сообщение о результатах
    return CandidateStates.MAIN_MENU

async def handle_test_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle user's answer to a test question"""
    query = update.callback_query
    await query.answer()
    
    # Check for admin mode
    admin_mode = context.user_data.get("admin_mode", False)
    
    # Get test data from context
    test_data = context.user_data.get("test_data", {})
    current_question = context.user_data.get("current_question", 0)
    test_name = context.user_data.get("current_test")
    user_id = update.effective_user.id
    
    # Получаем вопросы из test_data
    questions = []
    if isinstance(test_data, dict) and "questions" in test_data:
        questions = test_data["questions"]
    else:
        questions = test_data
    
    if not questions or current_question >= len(questions):
        return await send_main_menu(update, context)
    
    try:
        # Parse the answer index from callback data
        if query.data.startswith("answer_"):
            # Проверяем, не истекло ли время теста
            if "test_end_time" in context.user_data:
                now = time.time()
                end_time = context.user_data["test_end_time"]
                if now >= end_time:
                    # Время истекло, завершаем тест
                    logger.info(f"Time expired for test when processing answer")
                    return await test_timeout(update, context)
            
            answer_index = int(query.data.split('_')[1])
            question = questions[current_question]
            
            # Support both correct_answer and correct_option formats
            # The field may contain either numeric index or string value
            correct_answer = None
            if 'correct_answer' in question:
                correct_answer = question['correct_answer']
            elif 'correct_option' in question:
                correct_answer = question['correct_option']
            else:
                # Default to first option if no correct answer is specified
                correct_answer = 0
                
            # Convert to int if it's a string number
            if isinstance(correct_answer, str) and correct_answer.isdigit():
                correct_answer = int(correct_answer)
                
            # Отладочный вывод для диагностики
            logger.info(f"Answer debug - Question: {question['question']}")
            logger.info(f"Answer debug - Available fields: {list(question.keys())}")
            logger.info(f"Answer debug - correct_answer value: {correct_answer}")
            logger.info(f"Answer debug - user selected: {answer_index}")
            logger.info(f"Answer debug - options: {question.get('options', question.get('answers', []))}")
            
            # Проверяем, совпадает ли выбранный ответ с правильным
            # В файле теста индексы 0-based, а в кнопках 1-based, поэтому сравниваем напрямую
            is_correct = answer_index == correct_answer
            
            if is_correct:
                # Increment correct answers count
                context.user_data["correct_answers"] = context.user_data.get("correct_answers", 0) + 1
                logger.info(f"Answer debug - Correct! Total correct answers: {context.user_data['correct_answers']}")
                logger.info(f"Answer debug - User selected option {answer_index} which matches correct answer {correct_answer}")
                # Отправляем сообщение пользователю о правильном ответе
                # await query.message.reply_text("✅ Правильный ответ!")
            else:
                logger.info(f"Answer debug - Incorrect! Expected {correct_answer}, got {answer_index}")
                logger.info(f"Answer debug - User selected option {answer_index} but correct answer was {correct_answer}")
                # Отправляем сообщение пользователю о неправильном ответе
                # await query.message.reply_text("❌ Неправильный ответ!")
            
            # Сразу переходим к следующему вопросу без показа правильности ответа
            context.user_data["current_question"] = current_question + 1
            
            # Обновляем информацию о текущем вопросе для таймера
            if "timer_data" in context.user_data:
                context.user_data["timer_data"]["current_question"] = context.user_data["current_question"]
            
            # If this is the last question, complete the test
            if context.user_data["current_question"] >= len(questions):
                return await handle_test_completion(update, context)
            
            # Otherwise, send next question
            return await send_test_question(update, context, edit_message=True)
        
        return CandidateStates.PRIMARY_TEST
        
    except (ValueError, IndexError, KeyError) as e:
        logger.error(f"Error processing test answer: {e}")
        await query.message.reply_text("Ошибка при обработке ответа. Пожалуйста, попробуйте снова.")
        return await send_main_menu(update, context)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle text messages."""
    user_id = update.effective_user.id
    text = update.message.text
    
    # Проверяем, ожидается ли ответ в тесте на стоп-слова
    if context.user_data.get("awaiting_stopword_answer", False):
        return await process_stopword_answer(update, context, text)
    
    # Если текущее состояние - ввод примеров использования стоп-слов
    if context.user_data.get("awaiting_examples", False):
        return await process_stopword_examples(update, context, text)
    
    # Если текущее состояние - тестовое задание
    if context.user_data.get("awaiting_test_solution", False):
        return await process_test_solution(update, context, text)
    
    # Если текущее состояние - поэтическое задание
    if context.user_data.get("awaiting_poem", False):
        return await process_poem_task(update, context, text)
    
    # Если текущее состояние - резюме
    if context.user_data.get("awaiting_resume", False):
        return await process_resume(update, context)
        
    # Если текущее состояние - выбор дня для собеседования
    if context.user_data.get("awaiting_interview_day", False):
        return await process_interview_day(update, context, text)
    
    # Если текущее состояние - выбор времени для собеседования
    if context.user_data.get("awaiting_interview_time", False):
        return await process_interview_time(update, context, text)
    
    # Если пользователь в состоянии разблокировки админа
    admin_unlock_state = context.user_data.get("admin_unlock_state", None)
    if admin_unlock_state:
        return await process_admin_unlock(update, context, text)
    
    # В противном случае отправляем главное меню
    await update.message.reply_text(
        "Пожалуйста, используйте меню для взаимодействия с ботом.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📋 Главное меню", callback_data="back_to_menu")]
        ])
    )
    return await send_main_menu(update, context)

async def process_stopword_answer(update, context, text):
    """Обрабатывает ответ пользователя на вопрос теста стоп-слов"""
    user_id = update.effective_user.id
    
    # Останавливаем таймер, если он существует
    if "stopwords_timer_job" in context.user_data:
        try:
            context.user_data["stopwords_timer_job"].schedule_removal()
            logger.info("Таймер остановлен при обработке ответа на вопрос")
        except Exception as e:
            logger.error(f"Ошибка при остановке таймера: {e}")
    
    # Получаем текущий вопрос
    current_stopword = context.user_data.get("current_stopword", {})
    if not current_stopword:
        await update.message.reply_text(
            "Произошла ошибка при обработке ответа. Пожалуйста, вернитесь в главное меню и начните тест заново.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📋 Главное меню", callback_data="back_to_menu")]
            ])
        )
        return CandidateStates.MAIN_MENU
    
    # Получаем данные теста
    test_data = context.user_data.get("stopwords_test", {})
    
    # Получаем исходное предложение и стоп-слово
    original_sentence = current_stopword.get("sentence", "")
    stopword = current_stopword.get("word", "")
    
    # Очищаем флаг ожидания ответа
    context.user_data["awaiting_stopword_answer"] = False
    
    # Проверяем ответ пользователя с помощью ИИ
    try:
        # Используем AI для проверки ответа пользователя
        passed, feedback = await verify_stopword_rephrasing_ai(original_sentence, text, current_stopword)
        
        # Определяем результат
        result_emoji = "✅" if passed else "❌"
        result_message = (
            f"{result_emoji} {feedback}\n\n"
            f"Исходное предложение: <b>{original_sentence}</b>\n"
            f"Стоп-слово: <b>{stopword}</b>\n"
            f"Ваш ответ: <b>{text}</b>"
        )
        
        # Обновляем счетчик правильных ответов
        if passed:
            test_data["correct_answers"] = test_data.get("correct_answers", 0) + 1
        
        # Переходим к следующему вопросу
        test_data["current_question"] = test_data.get("current_question", 0) + 1
        context.user_data["stopwords_test"] = test_data
        
        # Отправляем сообщение с результатом
        keyboard = [
            [InlineKeyboardButton("➡️ Следующий вопрос", callback_data="next_stopword_question")],
            [InlineKeyboardButton("⬅️ Вернуться в главное меню", callback_data="back_to_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            result_message,
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
        
        return CandidateStates.STOPWORDS_TEST
    
    except Exception as e:
        logger.error(f"Ошибка при обработке ответа на тест стоп-слов: {e}")
        
        # Если произошла ошибка, даем пользователю возможность продолжить тест
        await update.message.reply_text(
            "Произошла ошибка при проверке вашего ответа. Пожалуйста, продолжите тест.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("➡️ Следующий вопрос", callback_data="next_stopword_question")],
                [InlineKeyboardButton("⬅️ Вернуться в главное меню", callback_data="back_to_menu")]
            ])
        )
        
        # Переходим к следующему вопросу
        test_data["current_question"] = test_data.get("current_question", 0) + 1
        context.user_data["stopwords_test"] = test_data
        
        return CandidateStates.STOPWORDS_TEST

async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the /start command."""
    user = update.effective_user
    user_id = user.id
    
    # Сохраняем информацию о пользователе в базу данных
    db.save_user_info(
        user_id=user_id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name
    )
    
    # Отправляем приветственное сообщение
    welcome_message = load_text_content("welcome_message.txt")
    await update.message.reply_text(welcome_message)
    
    # Отправляем главное меню
    return await send_main_menu(update, context)

async def handle_schedule_interview(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle interview scheduling."""
    query = update.callback_query
    await query.answer()
    
    # Получаем информацию о пользователе из базы данных
    user_id = update.effective_user.id
    user_info = db.get_user_info(user_id)
    
    # Формируем текст с username пользователя
    username = user_info.get('username', '')
    if username:
        user_link = f"@{username}"
    else:
        # Если username не указан, используем имя и фамилию
        first_name = user_info.get('first_name', '')
        last_name = user_info.get('last_name', '')
        user_link = f"{first_name} {last_name}".strip() or "Пользователь"
    
    # Формируем сообщение с заявкой на собеседование
    message = (
        f"📝 Заявка на собеседование:\n\n"
        f"ID: {user_id}\n"
        f"Кандидат: {user_link}\n"
        f"Предпочтительный день: {context.user_data.get('preferred_day', 'Не указан')}\n"
        f"Предпочтительное время: {context.user_data.get('preferred_time', 'Не указано')}\n\n"
        f"Для подтверждения нажмите кнопку ниже."
    )
    
    keyboard = [
        [InlineKeyboardButton("✅ Подтвердить", callback_data="confirm_interview")],
        [InlineKeyboardButton("⬅️ Вернуться в главное меню", callback_data="back_to_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        text=message,
        reply_markup=reply_markup
    )
    
    return CandidateStates.SCHEDULE_INTERVIEW

async def next_stopword_question(update, context):
    """Переход к следующему вопросу в тесте стоп-слов"""
    query = update.callback_query
    await query.answer()
    
    # Останавливаем таймер, если он существует
    if "stopwords_timer_job" in context.user_data:
        try:
            context.user_data["stopwords_timer_job"].schedule_removal()
            logger.info("Таймер остановлен при переходе к следующему вопросу")
        except Exception as e:
            logger.error(f"Ошибка при остановке таймера: {e}")
    
    # Проверяем существование данных теста
    if "stopwords_test" not in context.user_data:
        # Если данные отсутствуют, возможно, тест был перезапущен или произошла ошибка
        logger.error("Данные теста отсутствуют в next_stopword_question")
        await query.edit_message_text(
            "Произошла ошибка при переходе к следующему вопросу. Пожалуйста, начните тест заново.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Вернуться в главное меню", callback_data="back_to_menu")],
                [InlineKeyboardButton("🔄 Начать тест заново", callback_data="start_stopwords_test")]
            ])
        )
        return CandidateStates.MAIN_MENU
    
    # Проверяем, не закончился ли тест
    test_data = context.user_data.get("stopwords_test", {})
    current_question = test_data.get("current_question", 0)
    questions = test_data.get("stopwords", [])
    
    if current_question >= len(questions):
        # Тест завершен, показываем результаты
        await handle_stopwords_test_completion(update, context)
        return CandidateStates.MAIN_MENU
    
    # Отправляем следующий вопрос
    await send_stopword_question(update, context)
    
    return CandidateStates.STOPWORDS_TEST

async def handle_stopword_answer(update, context):
    """Обрабатывает ответ на вопрос теста стоп-слов из колбека"""
    query = update.callback_query
    await query.answer()
    
    # Останавливаем таймер, если он существует
    if "stopwords_timer_job" in context.user_data:
        try:
            context.user_data["stopwords_timer_job"].schedule_removal()
            logger.info("Таймер остановлен при обработке ответа на вопрос")
        except Exception as e:
            logger.error(f"Ошибка при остановке таймера: {e}")
    
    # Получаем выбранный вариант ответа
    answer_idx = int(query.data.split("_")[-1])
    
    # Получаем данные теста
    test_data = context.user_data.get("stopwords_test", {})
    current_question = test_data.get("current_question", 0)
    stopwords = test_data.get("stopwords", [])
    
    if current_question >= len(stopwords):
        # Если вопросы закончились, показываем результаты
        return await handle_stopwords_test_completion(update, context)
    
    # Получаем текущий стоп-слово и его данные
    current_stopword = stopwords[current_question]
    selected_answer = current_stopword.get("answers", [])[answer_idx] if answer_idx < len(current_stopword.get("answers", [])) else ""
    
    # Проверяем, является ли ответ правильным (упрощенная проверка)
    # В реальном тесте используется AI для проверки пользовательского ответа
    is_correct = True  # Предполагаем, что все варианты правильные, т.к. это варианты без стоп-слова
    
    # Инкрементируем счетчик правильных ответов
    if is_correct:
        test_data["correct_answers"] = test_data.get("correct_answers", 0) + 1
    
    # Показываем результат ответа
    stopword = current_stopword.get("word", "")
    original_sentence = current_stopword.get("sentence", "")
    
    result_emoji = "✅" if is_correct else "❌"
    result_message = (
        f"{result_emoji} {'Правильно!' if is_correct else 'Неправильно!'}\n\n"
        f"Исходное предложение: <b>{original_sentence}</b>\n"
        f"Стоп-слово: <b>{stopword}</b>\n"
        f"Ваш ответ: <b>{selected_answer}</b>"
    )
    
    # Отправляем сообщение с результатом
    keyboard = [
        [InlineKeyboardButton("➡️ Следующий вопрос", callback_data="next_stopword_question")],
        [InlineKeyboardButton("⬅️ Вернуться в главное меню", callback_data="back_to_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        result_message,
        reply_markup=reply_markup,
        parse_mode='HTML'
    )
    
    # Переходим к следующему вопросу
    test_data["current_question"] = current_question + 1
    context.user_data["stopwords_test"] = test_data
    
    return CandidateStates.STOPWORDS_TEST

async def handle_where_to_start(update, context):
    """Обработка раздела "С чего начать" с тестом на стоп-слова"""
    query = update.callback_query
    
    # Показываем информацию о стоп-словах и ссылку на таблицу
    message = (
        "📝 *Стоп-слова в деловой коммуникации*\n\n"
        "Стоп-слова - это слова и выражения, которые могут негативно влиять на бизнес-коммуникацию "
        "и создавать недопонимание между собеседниками.\n\n"
        "Использование стоп-слов может:\n"
        "• Искажать смысл сообщения\n"
        "• Вызывать негативные эмоции\n"
        "• Создавать двусмысленность\n"
        "• Снижать эффективность делового общения\n\n"
        "Ознакомьтесь с таблицей стоп-слов по ссылке:\n"
        "[Таблица стоп-слов](https://docs.google.com/spreadsheets/d/1MI3pHW2NsjcR_8n2sw2dMm9BxLy3oGg-ZdiPLClCR9c/edit?gid=0#gid=0)\n\n"
        "Готовы пройти тест на знание стоп-слов?"
    )
    
    keyboard = [
        [InlineKeyboardButton("✅ Начать тест", callback_data="start_stopwords_test")],
        [InlineKeyboardButton("⬅️ Вернуться в главное меню", callback_data="back_to_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        text=message,
        reply_markup=reply_markup,
        parse_mode="Markdown",
        disable_web_page_preview=False  # Включаем предпросмотр веб-страницы для ссылки
    )
    
    return CandidateStates.WHERE_TO_START

async def start_stopwords_test(update, context):
    """Начать тест на знание стоп-слов"""
    query = update.callback_query
    await query.answer()
    
    # Проверяем, проходил ли пользователь уже этот тест
    user_id = update.effective_user.id
    user_test_results = db.get_user_test_results(user_id)
    
    # Если тест уже был пройден (успешно или неуспешно), не позволяем пересдавать
    if "where_to_start_test" in user_test_results:
        await query.edit_message_text(
            "Вы уже проходили этот тест. Повторное прохождение тестов не разрешено.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Вернуться в главное меню", callback_data="back_to_menu")]
            ])
        )
        return CandidateStates.MAIN_MENU
        
    # Получаем данные о стоп-словах из Google Sheets
    stopwords_data = get_stopwords_data()
    
    if not stopwords_data:
        await query.edit_message_text(
            "К сожалению, не удалось загрузить данные о стоп-словах. Пожалуйста, попробуйте позже.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Вернуться в главное меню", callback_data="back_to_menu")]
            ])
        )
        return CandidateStates.MAIN_MENU
    
    # Отправляем инструкцию перед началом теста
    instructions = (
        "📝 <b>Тест на знание стоп-слов</b>\n\n"
        "В этом тесте вам будут показаны предложения, содержащие стоп-слова.\n"
        "Ваша задача - перефразировать предложение так, чтобы в нём НЕ использовалось указанное стоп-слово, "
        "но при этом сохранялся смысл.\n\n"
        "Например:\n"
        "Предложение: \"Я решу эту задачу наверное к 23 апреля\"\n"
        "Стоп-слово: <b>Наверное</b>\n\n"
        "Хороший ответ: \"Я решу эту задачу точно к 24 апреля\" или \"Я гарантирую выполнение задачи до конца месяца\"\n\n"
        "У вас будет 10 минут на прохождение всего теста.\n"
        "Нажмите кнопку ниже, чтобы начать."
    )
    
    keyboard = [
        [InlineKeyboardButton("▶️ Начать тест", callback_data="begin_stopwords_test")],
        [InlineKeyboardButton("⬅️ Вернуться в главное меню", callback_data="back_to_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        instructions,
        reply_markup=reply_markup,
        parse_mode="HTML"
    )
    
    return CandidateStates.STOPWORDS_TEST

async def begin_stopwords_test(update, context):
    """Начать тест стоп-слов после просмотра инструкции"""
    query = update.callback_query
    await query.answer()
    
    # Проверяем, проходил ли пользователь уже этот тест
    user_id = update.effective_user.id
    user_test_results = db.get_user_test_results(user_id)
    
    # Если тест уже был пройден (успешно или неуспешно), не позволяем пересдавать
    if "where_to_start_test" in user_test_results:
        await query.edit_message_text(
            "Вы уже проходили этот тест. Повторное прохождение тестов не разрешено.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Вернуться в главное меню", callback_data="back_to_menu")]
            ])
        )
        return CandidateStates.MAIN_MENU
    
    # Получаем данные о стоп-словах из Google Sheets
    stopwords_data = get_stopwords_data()
    
    if not stopwords_data:
        await query.edit_message_text(
            "К сожалению, не удалось загрузить данные о стоп-словах. Пожалуйста, попробуйте позже.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Вернуться в главное меню", callback_data="back_to_menu")]
            ])
        )
        return CandidateStates.MAIN_MENU
    
    # Выбираем случайные стоп-слова для теста (без генерации предложений)
    random.shuffle(stopwords_data)
    selected_stopwords = stopwords_data[:10] if len(stopwords_data) >= 10 else stopwords_data
    
    # Сохраняем данные для теста
    context.user_data["stopwords_test"] = {
        "stopwords": selected_stopwords,
        "current_question": 0,
        "correct_answers": 0,
        "start_time": time.time(),
        "end_time": time.time() + 600  # 10 минут на тест
    }
    
    # Показываем первый вопрос
    await send_stopword_question(update, context)
    
    return CandidateStates.STOPWORDS_TEST

async def send_stopword_question(update, context):
    """Отправляет пользователю вопрос с тестом стоп-слов"""
    # Получаем данные теста
    test_data = context.user_data.get("stopwords_test", {})
    current_question_idx = test_data.get("current_question", 0)
    all_stopwords = test_data.get("stopwords", [])
    
    # Проверяем, закончились ли вопросы
    if current_question_idx >= len(all_stopwords):
        # Если вопросы закончились, показываем результаты
        return await handle_stopwords_test_completion(update, context)
    
    # Если это первый вопрос и мы еще не генерировали предложения
    if "generated_sentences" not in test_data:
        test_data["generated_sentences"] = []
        context.user_data["stopwords_test"] = test_data
    
    # Получаем информацию о текущем стоп-слове
    current_stopword = all_stopwords[current_question_idx]
    
    # Проверяем, есть ли уже сгенерированное предложение для текущего вопроса
    generated_sentences = test_data.get("generated_sentences", [])
    if current_question_idx < len(generated_sentences) and generated_sentences[current_question_idx]:
        # Предложение уже сгенерировано, используем его
        current_stopword = generated_sentences[current_question_idx]
    else:
        # Нужно сгенерировать предложение
        if hasattr(update, 'callback_query') and update.callback_query:
            # Отправляем сообщение о генерации
            await update.callback_query.edit_message_text(
                f"⏳ Генерирую предложение для стоп-слова '{current_stopword.get('word', '')}'..."
            )
        elif update.effective_message:
            # Отправляем как новое сообщение
            await update.effective_message.reply_text(
                f"⏳ Генерирую предложение для стоп-слова '{current_stopword.get('word', '')}'..."
            )
        
        try:
            # Генерируем предложение с использованием стоп-слова через ИИ
            word = current_stopword.get("word", "")
            sentence = await generate_ai_stopword_sentence(current_stopword)
            
            # Обновляем объект с предложением
            current_stopword["sentence"] = sentence
            
            # Сохраняем сгенерированное предложение для повторного использования
            while len(generated_sentences) <= current_question_idx:
                generated_sentences.append(None)
            generated_sentences[current_question_idx] = current_stopword
            test_data["generated_sentences"] = generated_sentences
            context.user_data["stopwords_test"] = test_data
            
        except Exception as e:
            # Если возникла ошибка при генерации, создаем простой пример
            logger.error(f"Ошибка при генерации предложения для стоп-слова '{current_stopword.get('word', '')}': {e}")
            word = current_stopword.get("word", "")
            current_stopword["sentence"] = f"В этом предложении используется стоп-слово {word}."
            
            # Сохраняем даже простое предложение для повторного использования
            while len(generated_sentences) <= current_question_idx:
                generated_sentences.append(None)
            generated_sentences[current_question_idx] = current_stopword
            test_data["generated_sentences"] = generated_sentences
            context.user_data["stopwords_test"] = test_data
    
    # Проверяем оставшееся время
    end_time = test_data.get("end_time", 0)
    now = time.time()
    remaining = max(0, end_time - now)
    time_str = format_time(remaining)
    
    # Отправляем вопрос
    word = current_stopword.get("word", "")
    sentence = current_stopword.get("sentence", "")
    
    question_message = (
        f"⏱ Времени осталось: {time_str}\n\n"
        f"Вопрос {current_question_idx + 1} из {len(all_stopwords)}:\n\n"
        f"<b>Предложение:</b> {sentence}\n\n"
        f"<b>Стоп-слово:</b> {word}\n\n"
        f"Переформулируйте предложение так, чтобы избежать использования стоп-слова, но сохранить смысл."
    )
    
    # Сохраняем текущее стоп-слово в контексте для последующей проверки ответа
    context.user_data["current_stopword"] = current_stopword
    # Устанавливаем флаг ожидания ответа на стоп-слово
    context.user_data["awaiting_stopword_answer"] = True
    
    # Отправляем вопрос
    message = None
    if hasattr(update, 'callback_query') and update.callback_query:
        # Редактируем текущее сообщение
        message = await update.callback_query.edit_message_text(
            text=question_message,
            parse_mode='HTML'
        )
    else:
        # Отправляем как новое сообщение
        message = await update.effective_message.reply_text(
            text=question_message,
            parse_mode='HTML'
        )
    
    # Запускаем или обновляем таймер
    message_id = message.message_id if message else (
        update.callback_query.message.message_id if hasattr(update, 'callback_query') and update.callback_query else None
    )
    
    if message_id:
        # Останавливаем существующий таймер, если есть
        if "stopwords_timer_job" in context.user_data:
            try:
                context.user_data["stopwords_timer_job"].schedule_removal()
                logger.info("Таймер остановлен при переходе к новому вопросу")
            except Exception as e:
                logger.error(f"Ошибка при остановке таймера: {e}")
        
        # Данные для передачи в функцию обновления таймера
        job_data = {
            "chat_id": update.effective_chat.id,
            "message_id": message_id,
            "stopwords": all_stopwords,
            "current_question": current_question_idx,
            "end_time": end_time,
            "update": update,
            "context_obj": context,
            "current_message_text": question_message  # Сохраняем полный текст сообщения
        }
        
        try:
            # Запускаем таймер, который будет обновлять сообщение каждую секунду
            job = context.job_queue.run_repeating(
                update_stopwords_timer,
                interval=1.0,  # Интервал обновления - 1 секунда
                first=1.0,     # Первое обновление через 1 секунду
                data=job_data,
                name=f"stopwords_timer_{update.effective_chat.id}"
            )
            context.user_data["stopwords_timer_job"] = job
            logger.info(f"Запущен таймер для теста стоп-слов, оставшееся время: {time_str}")
        except Exception as e:
            logger.error(f"Ошибка при запуске таймера: {e}")
    
    return CandidateStates.STOPWORDS_TEST

async def handle_stopwords_test_completion(update, context):
    """Обработка завершения теста стоп-слов"""
    # Останавливаем таймер, если он существует
    if "stopwords_timer_job" in context.user_data:
        try:
            context.user_data["stopwords_timer_job"].schedule_removal()
            logger.info("Таймер остановлен при завершении теста")
        except Exception as e:
            logger.error(f"Ошибка при остановке таймера: {e}")
        del context.user_data["stopwords_timer_job"]
    
    # Получаем результаты теста
    test_data = context.user_data.get("stopwords_test", {})
    correct_answers = test_data.get("correct_answers", 0)
    total_questions = len(test_data.get("stopwords", []))
    
    # Считаем процент правильных ответов
    score = (correct_answers / total_questions) * 100 if total_questions > 0 else 0
    
    # Определяем, пройден ли тест (минимум 70%)
    passed = score >= 70
    
    # Сохраняем результат теста в базе данных
    user_id = update.effective_user.id
    db.update_test_result(user_id, "where_to_start_test", passed)
    
    # Разблокируем следующий этап
    db.unlock_stage(user_id, "logic_test")
    
    # Формируем сообщение с результатами
    if passed:
        result_message = (
            f"🎉 Поздравляем! Вы успешно прошли тест на знание стоп-слов!\n\n"
            f"Правильных ответов: {correct_answers} из {total_questions} ({score:.1f}%)\n\n"
            f"Следующий этап разблокирован. Продолжайте свое путешествие по нашей программе найма!"
        )
    else:
        result_message = (
            f"❌ Результат теста: не пройден.\n\n"
            f"Правильных ответов: {correct_answers} из {total_questions} ({score:.1f}%)\n\n"
            f"Однако, следующий этап все равно разблокирован. Вы можете продолжить, но рекомендуем "
            f"внимательнее изучить стоп-слова в таблице."
        )
    
    # Отправляем сообщение с результатами
    keyboard = [
        [InlineKeyboardButton("⬅️ Вернуться в главное меню", callback_data="back_to_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if hasattr(update, 'callback_query') and update.callback_query:
        await update.callback_query.edit_message_text(
            text=result_message,
            reply_markup=reply_markup
        )
    else:
        await update.effective_message.reply_text(
            text=result_message,
            reply_markup=reply_markup
        )
    
    # Очищаем данные теста из контекста
    if "stopwords_test" in context.user_data:
        del context.user_data["stopwords_test"]
    if "current_stopword" in context.user_data:
        del context.user_data["current_stopword"]
    if "awaiting_stopword_answer" in context.user_data:
        del context.user_data["awaiting_stopword_answer"]
    
    return CandidateStates.MAIN_MENU

def format_time(seconds):
    """Форматирует секунды в удобочитаемый формат времени"""
    minutes, seconds = divmod(int(seconds), 60)
    return f"{minutes:02d}:{seconds:02d}"

async def update_stopwords_timer(context):
    """Обновляет таймер для теста стоп-слов"""
    job_data = context.job.data
    
    # Получаем данные из параметров задания
    chat_id = job_data.get("chat_id")
    message_id = job_data.get("message_id")
    current_question = job_data.get("current_question")
    end_time = job_data.get("end_time")
    stopwords = job_data.get("stopwords", [])
    
    # Получаем текущий контекст и обновление
    update_obj = job_data.get("update")
    context_obj = job_data.get("context_obj")
    
    # Проверяем, не изменился ли номер текущего вопроса в контексте
    test_data = context_obj.user_data.get("stopwords_test", {})
    current_question_in_context = test_data.get("current_question", 0)
    
    # Если номер вопроса изменился, останавливаем этот таймер
    if current_question_in_context != current_question:
        logger.info(f"Номер вопроса изменился: {current_question} -> {current_question_in_context}. Останавливаем таймер.")
        context.job.schedule_removal()
        return
    
    # Проверяем, не завершился ли уже тест
    if "stopwords_test" not in context_obj.user_data:
        logger.info("Тест завершен. Останавливаем таймер.")
        context.job.schedule_removal()
        return
    
    # Вычисляем оставшееся время
    now = time.time()
    remaining = max(0, end_time - now)
    
    # Если время истекло, завершаем тест
    if remaining <= 0:
        logger.info("Время теста истекло. Завершаем тест.")
        context.job.schedule_removal()
        
        # Отправляем сообщение о завершении времени
        await context_obj.bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text="⏰ Время тестирования истекло! Пожалуйста, вернитесь в главное меню.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Вернуться в главное меню", callback_data="back_to_menu")]
            ])
        )
        
        # Очищаем данные теста из контекста
        if "stopwords_test" in context_obj.user_data:
            del context_obj.user_data["stopwords_test"]
        if "current_stopword" in context_obj.user_data:
            del context_obj.user_data["current_stopword"]
        if "awaiting_stopword_answer" in context_obj.user_data:
            del context_obj.user_data["awaiting_stopword_answer"]
        
        return
    
    # Форматируем оставшееся время
    time_str = format_time(remaining)
    
    try:
        # Получаем текущий текст из контекста, если он сохранен
        current_message_text = job_data.get("current_message_text", "")
        
        # Если текст не сохранен, создаем базовый шаблон
        if not current_message_text:
            # Используем текущее сообщение о вопросе как шаблон
            current_stopword = context_obj.user_data.get("current_stopword", {})
            word = current_stopword.get("word", "")
            sentence = current_stopword.get("sentence", "")
            
            current_message_text = (
                f"⏱ Времени осталось: {time_str}\n\n"
                f"Вопрос {current_question + 1} из {len(stopwords)}:\n\n"
                f"<b>Предложение:</b> {sentence}\n\n"
                f"<b>Стоп-слово:</b> {word}\n\n"
                f"Переформулируйте предложение так, чтобы избежать использования стоп-слова, но сохранить смысл."
            )
            # Сохраняем шаблон в данных задачи для последующих обновлений
            job_data["current_message_text"] = current_message_text
        
        # Обновляем только строку со временем
        if "⏱ Времени осталось:" in current_message_text:
            updated_text = current_message_text.replace(
                current_message_text.splitlines()[0], 
                f"⏱ Времени осталось: {time_str}"
            )
            
            # Сохраняем обновленный текст для следующего обновления
            job_data["current_message_text"] = updated_text
            
            # Обновляем сообщение
            await context_obj.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=updated_text,
                parse_mode='HTML'
            )
        else:
            # Если формат сообщения изменился, просто добавляем время вверху
            prefix_time = f"⏱ Времени осталось: {time_str}\n\n"
            if not current_message_text.startswith("⏱ Времени осталось:"):
                updated_text = prefix_time + current_message_text
            else:
                updated_text = current_message_text
            
            # Обновляем сообщение
            await context_obj.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=updated_text,
                parse_mode='HTML'
            )
            
            # Сохраняем обновленный текст для следующего обновления
            job_data["current_message_text"] = updated_text
    except Exception as e:
        logger.error(f"Ошибка при обновлении таймера: {e}")
        context.job.schedule_removal()
