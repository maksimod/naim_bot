import logging
import os
import sys
import asyncio
import time
import datetime
import random
import contextlib
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import ContextTypes
import database as db

# Добавляем корневую директорию проекта в путь импорта
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import CandidateStates
from utils.helpers import load_text_content, load_test_questions, get_stopwords_data
from utils.chatgpt_helpers import generate_ai_stopword_sentence, verify_stopword_rephrasing_ai, verify_poem_task, select_ai_stopword

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
        ("where_to_start", "🔴 Стоп-слова"),
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
            # Make stage green (unlocked), except for information modules which should be blue
            if stage_id in ["about_company", "preparation_materials"]:
                stage_name = stage_name.replace("🔴", "🔵")
            else:
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
        
        # Always try to edit the existing message first if we have a callback query and edit=True
        if edit and hasattr(update, 'callback_query') and update.callback_query:
            try:
                # Try to edit the current message
                await update.callback_query.edit_message_text(
                    text=message,
                    reply_markup=reply_markup
                )
                # Сохраняем ID отредактированного сообщения как main_menu_message_id
                context.user_data["main_menu_message_id"] = update.callback_query.message.message_id
                return CandidateStates.MAIN_MENU
            except Exception as e:
                logger.error(f"Error editing message via callback query: {e}")
                # Fall through to other methods if this fails
        
        # Если у нас есть content_message_id (т.е. мы в разделе вроде "Узнать о компании"), 
        # редактируем это сообщение при возврате в меню
        if edit and context.user_data.get("content_message_id"):
            try:
                # Редактируем сообщение раздела, превращая его в главное меню
                await context.bot.edit_message_text(
                    chat_id=update.effective_chat.id,
                    message_id=context.user_data["content_message_id"],
                    text=message,
                    reply_markup=reply_markup
                )
                # После успешного редактирования удаляем content_message_id,
                # так как это сообщение теперь стало главным меню
                context.user_data["main_menu_message_id"] = context.user_data["content_message_id"]
                del context.user_data["content_message_id"]
                return CandidateStates.MAIN_MENU
            except Exception as e:
                logger.error(f"Error editing content message: {e}")
                # Если не удалось, пробуем другие методы
                
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
                        # Stage unlocked - show as blue circle (for informational module)
                        stage_name = stage_name.replace("🔴", "🔵")  # Replace red circle with blue circle
            
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
    
    # Get the options/answers
    options = question.get('options', question.get('answers', []))
    
    # Формируем текст вопроса с учетом таймера и вариантами ответов
    if time_limit is not None:
        question_text = f"Времени осталось: {time_str}\nВопрос {current_question + 1} из {len(questions)}:\n\n{question['question']}\n\nВарианты ответов:"
    else:
        question_text = f"Вопрос {current_question + 1} из {len(questions)}:\n\n{question['question']}\n\nВарианты ответов:"
    
    # Add numbered answer choices to the question text
    for i, answer in enumerate(options):
        question_text += f"\n{i+1}. {answer}"
    
    # Create keyboard with just the numbers
    keyboard = []
    row = []
    for i in range(len(options)):
        # Add up to 3 buttons per row
        row.append(InlineKeyboardButton(f"{i+1}", callback_data=f"answer_{i}"))
        if len(row) == 3 or i == len(options) - 1:
            keyboard.append(row)
            row = []
    
    # Сохраняем клавиатуру в контексте для использования при обновлении таймера
    context.user_data["current_question_keyboard"] = keyboard
    
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
            except Exception as e:
                logger.error(f"Ошибка при остановке таймера: {e}")
        
        # Данные для передачи в функцию обновления таймера
        job_data = {
            "chat_id": update.effective_chat.id,
            "message_id": message_id,
            "current_question": current_question,
            "end_time": context.user_data["test_end_time"],
            "update": update,
            "context_obj": context,
            "current_message_text": question_text  # Сохраняем текст вопроса для обновления таймера
        }
        
        try:
            # Запускаем таймер, который будет обновлять сообщение каждую секунду
            job = context.job_queue.run_repeating(
                update_timer,
                interval=5.0,  # Интервал обновления - 1 секунда
                first=5.0,     # Первое обновление через 1 секунду
                data=job_data,
                name=f"timer_{update.effective_chat.id}"
            )
            context.user_data["test_timer_job"] = job
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
        return await send_main_menu(update, context, edit=True)
    
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
    else:
        # Save test result to database
        db.update_test_result(user_id, test_name, passed)
    
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
    
    # Добавляем блокировку обновления таймера на время обработки ответа
    context.user_data["processing_answer"] = True
    
    try:
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
            # Снимаем блокировку перед выходом из функции
            context.user_data.pop("processing_answer", None)
            return await send_main_menu(update, context, edit=True)
        
        try:
            # Get which answer was selected
            answer_index = int(query.data.split("_")[1])
            
            # Get current question details
            question = questions[current_question]
            
            # Handle different test formats (some use 'answer' and some use 'correct_answer')
            correct_answer = question.get('answer', question.get('correct_answer', -1))
            
            # Try to convert correct_answer to an integer if it's provided as a string (e.g., "1", "2", etc.)
            if isinstance(correct_answer, str):
                if correct_answer.isdigit():
                    # Convert 1-based index to 0-based
                    correct_answer = int(correct_answer) - 1
                else:
                    # Если correct_answer - не число, то ищем его индекс в массиве options/answers
                    options = question.get('options', question.get('answers', []))
                    if correct_answer in options:
                        correct_answer = options.index(correct_answer)
                    else:
                        logger.error(f"Invalid correct_answer format: {correct_answer}")
                        correct_answer = -1
            
            # Check if the answer is correct
            if admin_mode:
                # In admin mode, always mark answer as correct
                is_correct = True
                context.user_data["correct_answers"] = context.user_data.get("correct_answers", 0) + 1
            else:
                # Проверяем, совпадает ли выбранный ответ с правильным
                # В файле теста индексы 0-based, а в кнопках 1-based, поэтому сравниваем напрямую
                is_correct = answer_index == correct_answer
                
                if is_correct:
                    # Increment correct answers count
                    context.user_data["correct_answers"] = context.user_data.get("correct_answers", 0) + 1
                else:
                    pass
                
                # Останавливаем таймер перед обновлением UI, чтобы избежать гонки
                if "test_timer_job" in context.user_data:
                    try:
                        context.user_data["test_timer_job"].schedule_removal()
                        # Даем небольшую паузу для полной остановки таймера
                        await asyncio.sleep(0.1)
                    except Exception as e:
                        logger.error(f"Ошибка при остановке таймера для обработки ответа: {e}")
                
                # Сразу переходим к следующему вопросу без показа правильности ответа
                context.user_data["current_question"] = current_question + 1
                
                # Wait briefly to avoid UI flickering
                await asyncio.sleep(0.1)
                
                # Determine if we should go to the next question or finish
                if context.user_data["current_question"] < len(questions):
                    # Continue to next question
                    try:
                        await send_test_question(update, context, edit_message=True)
                    except Exception as e:
                        logger.error(f"Error sending next question: {e}")
                        await query.message.reply_text("Произошла ошибка при загрузке следующего вопроса.")
                        return await send_main_menu(update, context, edit=True)
                    
                    # Stay in test state
                    if "stopwords_test" in test_name:
                        return CandidateStates.STOPWORDS_TEST
                    elif test_name == "primary_test":
                        return CandidateStates.PRIMARY_TEST
                    elif test_name == "where_to_start_test":
                        return CandidateStates.WHERE_TO_START_TEST
                    elif test_name == "logic_test_result":
                        return CandidateStates.LOGIC_TEST_TESTING
                    elif test_name == "interview_prep_test":
                        return CandidateStates.INTERVIEW_PREP_TEST
                else:
                    # Test is finished, handle completion
                    return await handle_test_completion(update, context)
                    
        except ValueError as e:
            logger.error(f"Error parsing answer index: {e}")
            await query.message.reply_text("Произошла ошибка при проверке ответа. Пожалуйста, попробуйте снова.")
            return await send_main_menu(update, context, edit=True)
            
        except Exception as e:
            logger.error(f"Unexpected error in handle_test_answer: {e}")
            await query.message.reply_text("Произошла ошибка при обработке ответа. Пожалуйста, попробуйте снова.")
            return await send_main_menu(update, context, edit=True)
            
    except (ValueError, IndexError, KeyError) as e:
        logger.error(f"Error processing test answer: {e}")
        await query.message.reply_text("Ошибка при обработке ответа. Пожалуйста, попробуйте снова.")
        # Снимаем блокировку в случае ошибки
        context.user_data.pop("processing_answer", None)
        return await send_main_menu(update, context, edit=True)
    finally:
        # Снимаем блокировку после обработки ответа
        context.user_data.pop("processing_answer", None)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle text messages."""
    user_id = update.effective_user.id
    text = update.message.text
    
    # Проверяем секретную команду для сброса прогресса
    if text == "!reload2!":
        # Сбрасываем прогресс пользователя в базе данных
        db.reset_user_progress(user_id)
        
        # Очищаем данные пользователя в контексте
        context.user_data.clear()
        
        await update.message.reply_text(
            "🔄 Ваш прогресс был полностью сброшен. Все тесты, результаты, разблокированные этапы и информация об использованных нейросетях возвращены к начальному состоянию."
        )
        
        # Отправляем главное меню
        return await send_main_menu(update, context)
    
    # Проверяем команду для разблокировки всех модулей
    if text == "admin123!":
        # Список всех модулей, которые нужно разблокировать
        all_modules = [
            "about_company",
            "primary_file",
            "where_to_start",
            "logic_test",
            "preparation_materials",
            "take_test",
            "interview_prep",
            "schedule_interview"
        ]
        
        # Список тестов, которые нужно отметить как пройденные
        test_results = {
            "primary_test": True,
            "where_to_start_test": True,
            "logic_test_result": True, 
            "take_test_result": True,
            "interview_prep_test": True
        }
        
        # Разблокируем все модули
        for module in all_modules:
            db.unlock_stage(user_id, module)
        
        # Отмечаем все тесты как пройденные
        for test_name, result in test_results.items():
            db.update_test_result(user_id, test_name, result)
        
        await update.message.reply_text(
            "🔓 Администраторский режим активирован. Все модули разблокированы и все тесты отмечены как пройденные."
        )
        
        # Отправляем главное меню
        return await send_main_menu(update, context)
    
    # Проверяем команду для пропуска текущего модуля
    if text == "!skip2!":
        # Получаем список разблокированных модулей
        unlocked_stages = db.get_user_unlocked_stages(user_id)
        
        # Порядок модулей
        module_order = [
            "about_company",
            "primary_file", 
            "where_to_start",
            "logic_test",
            "preparation_materials",
            "take_test",
            "interview_prep",
            "schedule_interview"
        ]
        
        # Соответствие модулей и тестов
        module_test_mapping = {
            "primary_file": "primary_test",
            "where_to_start": "where_to_start_test",
            "logic_test": "logic_test_result",
            "take_test": "take_test_result",
            "interview_prep": "interview_prep_test"
        }
        
        # Найдем последний разблокированный модуль согласно порядку
        last_unlocked = None
        next_module_to_unlock = None
        
        # Пройдем по списку в обратном порядке для нахождения последнего разблокированного модуля
        for i in range(len(module_order) - 1, -1, -1):
            if module_order[i] in unlocked_stages:
                # Нашли последний разблокированный модуль
                last_unlocked = module_order[i]
                
                # Находим ещё не разблокированный следующий модуль
                for j in range(i + 1, len(module_order)):
                    if module_order[j] not in unlocked_stages:
                        next_module_to_unlock = module_order[j]
                        break
                break
        
        if not last_unlocked:
            await update.message.reply_text(
                "❌ Не найдены разблокированные модули. Сначала разблокируйте хотя бы один модуль."
            )
            return await send_main_menu(update, context)
        
        # Проверяем, есть ли следующий модуль для разблокировки
        if not next_module_to_unlock:
            await update.message.reply_text(
                "✅ Все модули уже разблокированы. Больше нет модулей для открытия."
            )
            return await send_main_menu(update, context)
        
        # Если для текущего модуля есть тест, отмечаем его как пройденный
        if last_unlocked in module_test_mapping:
            test_name = module_test_mapping[last_unlocked]
            db.update_test_result(user_id, test_name, True)
        
        # Разблокируем следующий модуль
        db.unlock_stage(user_id, next_module_to_unlock)
        
        await update.message.reply_text(
            f"✅ Модуль '{last_unlocked}' отмечен как успешно пройденный.\n🔓 Модуль '{next_module_to_unlock}' разблокирован."
        )
        
        # Отправляем главное меню
        return await send_main_menu(update, context)
    
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
    return await send_main_menu(update, context, edit=True)

async def process_stopword_answer(update, context, text):
    """Проверка ответа на вопрос с стоп-словами"""
    # Проверяем, что ожидается ответ на стоп-слово
    if not context.user_data.get("awaiting_stopword_answer", False):
        return

    # Устанавливаем флаг обработки ответа, чтобы избежать параллельной обработки
    context.user_data["processing_answer"] = True
    
    # Получаем информацию о текущем стоп-слове
    current_stopword = context.user_data.get("current_stopword", {})
    
    # Если не удалось получить информацию о стоп-слове, прекращаем обработку
    if not current_stopword:
        context.user_data["processing_answer"] = False
        context.user_data["awaiting_stopword_answer"] = False
        await update.effective_message.reply_text("Произошла ошибка. Пожалуйста, вернитесь в главное меню.")
        return
    
    # Получаем предложение с стоп-словом и ответ пользователя
    original_sentence = current_stopword.get("sentence", "")
    stopword_word = current_stopword.get("word", "")
    rephrased_sentence = text.strip()
    
    # Проверяем, есть ли стоп-слово в исходном предложении
    if stopword_word.lower() not in original_sentence.lower():
        logger.warning(f"Стоп-слово '{stopword_word}' отсутствует в оригинальном предложении: '{original_sentence}'")
        # Засчитываем ответ как правильный, если пользователь вернул то же предложение
        if original_sentence.lower() == rephrased_sentence.lower():
            # Увеличиваем счетчик правильных ответов
            test_data = context.user_data.get("stopwords_test", {})
            test_data["correct_answers"] = test_data.get("correct_answers", 0) + 1
            context.user_data["stopwords_test"] = test_data
            
            await update.effective_message.reply_text(
                f"✅ Отлично! Вы успешно перефразировали предложение без использования стоп-слова.\n\n"
                f"Оригинал: {original_sentence}\n"
                f"Ваш ответ: {rephrased_sentence}\n"
            )
        else:
            await update.effective_message.reply_text(
                f"❌ В исходном предложении не было стоп-слова '{stopword_word}', нужно было оставить его без изменений.\n\n"
                f"Оригинал: {original_sentence}\n"
                f"Ваш ответ: {rephrased_sentence}\n"
            )
            
        # Сбрасываем флаг обработки
        context.user_data["processing_answer"] = False
        context.user_data["awaiting_stopword_answer"] = True
            
        # Переходим к следующему вопросу
        await next_question(update, context)
        return
    
    # Если пользователь не ввел ответ, просим повторить
    if not rephrased_sentence:
        context.user_data["processing_answer"] = False
        await update.effective_message.reply_text("Пожалуйста, введите перефразированное предложение.")
        return
    
    # Проверяем, содержит ли ответ стоп-слово
    excludes_stopword = stopword_word.lower() not in rephrased_sentence.lower()
    
    # Правильный ответ - не содержит стоп-слово и не равен исходному предложению
    is_correct = excludes_stopword and rephrased_sentence.lower() != original_sentence.lower()
    
    if is_correct:
        # Увеличиваем счетчик правильных ответов
        test_data = context.user_data.get("stopwords_test", {})
        test_data["correct_answers"] = test_data.get("correct_answers", 0) + 1
        context.user_data["stopwords_test"] = test_data
        
        result_message = (
            f"✅ Отлично! Вы успешно перефразировали предложение без использования стоп-слова.\n\n"
            f"Оригинал: {original_sentence}\n"
            f"Ваш ответ: {rephrased_sentence}\n"
        )
    else:
        if not excludes_stopword:
            result_message = (
                f"❌ Ваш ответ все еще содержит стоп-слово '{stopword_word}'.\n\n"
                f"Оригинал: {original_sentence}\n"
                f"Ваш ответ: {rephrased_sentence}\n"
            )
        else:
            result_message = (
                f"❌ Ваш ответ слишком близок к оригиналу или не сохраняет смысл предложения.\n\n"
                f"Оригинал: {original_sentence}\n"
                f"Ваш ответ: {rephrased_sentence}\n"
            )
    
    # Отправляем результат проверки
    await update.effective_message.reply_text(result_message)
    
    # Сбрасываем флаг обработки, но ОСТАВЛЯЕМ флаг ожидания ответа
    context.user_data["processing_answer"] = False  
    
    # Переходим к следующему вопросу
    await next_question(update, context)

async def next_question(update, context):
    """Вспомогательная функция для перехода к следующему вопросу"""
    # Обновляем номер вопроса
    test_data = context.user_data.get("stopwords_test", {})
    current_question_idx = test_data.get("current_question", 0)
    test_data["current_question"] = current_question_idx + 1
    context.user_data["stopwords_test"] = test_data
    
    # Отправляем следующий вопрос, который установит awaiting_stopword_answer в True
    await send_stopword_question(update, context)

async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the /start command."""
    user_id = update.effective_user.id
    username = update.effective_user.username
    first_name = update.effective_user.first_name
    last_name = update.effective_user.last_name
    
    # Register user in the database if not already registered
    db.register_candidate(user_id, username, first_name, last_name)
    
    # Unlock first stages
    db.unlock_stage(user_id, "about_company")
    db.unlock_stage(user_id, "primary_file")
    
    # Welcome message
    await update.message.reply_text(
        "Добро пожаловать в бот для подготовки к собеседованию!\n\n"
        "Здесь вы сможете:\n"
        "- Узнать о компании\n"
        "- Пройти тесты для проверки знаний\n"
        "- Подготовиться к собеседованию\n"
        "- Записаться на собеседование\n\n"
        "Выберите интересующий вас раздел в главном меню."
    )
    
    return await send_main_menu(update, context, edit=True)

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
    """Показать следующий вопрос теста стоп-слов"""
    query = update.callback_query
    await query.answer()
    
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
    total_questions = test_data.get("total_questions", 10)
    
    if current_question >= total_questions:
        # Тест завершен, показываем результаты
        await handle_stopwords_test_completion(update, context)
        return CandidateStates.MAIN_MENU
    
    # Инкрементируем номер вопроса
    test_data["current_question"] = current_question + 1
    context.user_data["stopwords_test"] = test_data
    
    # Отправляем следующий вопрос - это установит awaiting_stopword_answer в True
    await send_stopword_question(update, context)
    
    return CandidateStates.STOPWORDS_TEST

async def handle_stopword_answer(update, context):
    """Обрабатывает ответ на вопрос теста стоп-слов из колбека"""
    query = update.callback_query
    await query.answer()
    
    # Раскодируем выбранный вариант
    choice = query.data.split('_')[2]
    
    # Получаем данные теста
    test_data = context.user_data.get("stopwords_test", {})
    current_question_idx = test_data.get("current_question", 0)
    all_stopwords = test_data.get("stopwords", [])
    
    # Проверяем, есть ли текущий вопрос
    if current_question_idx >= len(all_stopwords):
        await query.edit_message_text(
            "Произошла ошибка при обработке ответа. Тест будет перезапущен.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Вернуться в главное меню", callback_data="back_to_menu")]
            ])
        )
        return CandidateStates.MAIN_MENU
    
    # Получаем текущий стоп-слово и его данные
    current_stopword = current_question_idx < len(all_stopwords) and all_stopwords[current_question_idx] or {}
    
    # Получаем дополнительные данные из стоп-слова, если они есть
    word = current_stopword.get("word", "")
    description = current_stopword.get("description", "")
    replacement = current_stopword.get("replacement", "")
    
    # Все варианты ответа предлагаются ИИ, и все они без стоп-слова
    is_correct = True  # Предполагаем, что все варианты правильные, т.к. это варианты без стоп-слова
    
    # Увеличиваем счетчик правильных ответов, если ответ правильный
    if is_correct:
        test_data["correct_answers"] = test_data.get("correct_answers", 0) + 1
        context.user_data["stopwords_test"] = test_data
        
        # Отображаем сообщение об успехе с использованием полных данных о стоп-слове
        success_message = f"✅ Правильно! Вы успешно использовали альтернативу стоп-слову '{word}'."
        
        # Добавляем информацию о замене, если она есть
        if replacement:
            success_message += f"\n\nРекомендуемая замена: {replacement}"
        
        # Добавляем описание, если оно есть
        if description:
            success_message += f"\n\nПочему это стоп-слово: {description}"
        
        await query.edit_message_text(
            success_message,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("▶️ Следующий вопрос", callback_data="next_stopword")]
            ])
        )
    else:
        # Если неправильный ответ (маловероятно, так как все варианты должны быть верными)
        await query.edit_message_text(
            f"❌ К сожалению, этот вариант не подходит.\n\n"
            f"Попробуйте выбрать другой вариант или вернитесь в меню.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Вернуться в главное меню", callback_data="back_to_menu")]
            ])
        )
    
    return CandidateStates.STOPWORDS_TEST

async def handle_where_to_start(update, context):
    """Обработка раздела "Стоп-слова" с тестом на стоп-слова"""
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
    
    # Проверяем, проходил ли пользователь тест ранее
    user_id = update.effective_user.id
    if not user_id:
        logger.error("Не удалось получить user_id для теста стоп-слов")
        return CandidateStates.MAIN_MENU
    
    # Проверяем, что пользователь еще не проходил тест
    with contextlib.suppress(Exception):
        # Проверяем результат теста в БД
        if db.has_completed_test(user_id, "stopwords"):
            await query.edit_message_text(
                "Вы уже проходили этот тест. Повторное прохождение тестов не разрешено.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("⬅️ Вернуться в главное меню", callback_data="back_to_menu")]
                ])
            )
            return CandidateStates.MAIN_MENU
    
    # Инициализируем данные для теста
    num_questions = 10  # Количество вопросов в тесте
    
    # Сохраняем данные для теста
    context.user_data["stopwords_test"] = {
        "current_question": 0,
        "correct_answers": 0,
        "start_time": time.time(),
        "end_time": time.time() + 600,  # 10 минут на тест
        "total_questions": num_questions  # Общее количество вопросов
    }
    
    # Показываем первый вопрос
    await send_stopword_question(update, context)
    
    return CandidateStates.STOPWORDS_TEST

async def send_stopword_question(update, context):
    """Отправляет пользователю вопрос с тестом стоп-слов"""
    # Получаем данные теста
    test_data = context.user_data.get("stopwords_test", {})
    current_question_idx = test_data.get("current_question", 0)
    total_questions = test_data.get("total_questions", 10)
    
    # Проверяем, закончились ли вопросы
    if current_question_idx >= total_questions:
        # Если вопросы закончились, показываем результаты
        return await handle_stopwords_test_completion(update, context)
    
    # Если это первый вопрос и мы еще не выбрали предложения
    if "selected_sentences" not in test_data:
        # Список готовых предложений со стоп-словами
        predefined_sentences = [
            {"sentence": "Какая вам разница, когда я закончу этот отчет?", "word": "разница"},
            {"sentence": "Пожалуйста, передайте эти документы в бухгалтерию.", "word": "пожалуйста"},
            {"sentence": "Это был действительно хороший проект для нашей компании.", "word": "хороший"},
            {"sentence": "Ну, я думаю, мы можем завершить этот проект к пятнице.", "word": "ну"},
            {"sentence": "Ладно, я отправлю вам эти файлы позже.", "word": "ладно"},
            {"sentence": "Наверно, клиент согласится на эти условия.", "word": "наверно"},
            {"sentence": "Кажется, мы уже обсуждали этот вопрос на прошлой неделе.", "word": "кажется"},
            {"sentence": "Всё, больше вопросов по презентации у меня нет.", "word": "всё"},
            {"sentence": "Ваш подход к решению этой задачи неправильный.", "word": "неправильный"},
            {"sentence": "Хорошо, я согласен с вашим предложением.", "word": "хорошо"},
            {"sentence": "У нас хороший коллектив, поэтому проект будет успешным.", "word": "хороший"},
            {"sentence": "Этот квартальный отчет выглядит плохо, нужно его переделать.", "word": "плохо"},
            {"sentence": "Я понимаю ваши требования и выполню их в срок.", "word": "понимаю"},
            {"sentence": "Мы работаем только с проверенными поставщиками.", "word": "только"},
            {"sentence": "Это просто сделать, займет не больше часа.", "word": "просто"},
            {"sentence": "У нас сейчас слишком мало времени для разработки этого функционала.", "word": "мало"},
            {"sentence": "Предложенная цена слишком дорого для нашего бюджета.", "word": "дорого"},
            {"sentence": "Давайте чуть-чуть изменим дизайн логотипа.", "word": "чуть-чуть"},
            {"sentence": "Я виноват в том, что не проверил данные перед отправкой.", "word": "виноват"},
            {"sentence": "Извини, что не смог подготовить презентацию вовремя.", "word": "извини"},
            {"sentence": "Чем занимаешься сейчас? Могу я отвлечь тебя на минуту?", "word": "занимаешься"},
            {"sentence": "Вы сами себе противоречите в этом бизнес-плане.", "word": "противоречите"},
            {"sentence": "У меня не хватает времени для выполнения этого проекта в срок.", "word": "не хватает"},
            {"sentence": "Ты слишком хвастаешься своими достижениями перед клиентами.", "word": "хвастаешься"},
            {"sentence": "Вы не так поняли мои комментарии по поводу бюджета.", "word": "не так поняли"},
            {"sentence": "Я этого не делал, это была ошибка системы.", "word": "не делал"},
            {"sentence": "Я могу помогать вам с подготовкой ежемесячных отчетов.", "word": "помогать"},
            {"sentence": "Этот контакт может пригодиться нам в будущем.", "word": "пригодиться"},
            {"sentence": "Мне не нравится новый дизайн нашего корпоративного сайта.", "word": "не нравится"},
            {"sentence": "Мне без разницы, какой шрифт вы выберете для презентации.", "word": "без разницы"},
            {"sentence": "Я не согласен с предложенной стратегией маркетинга.", "word": "не согласен"},
            {"sentence": "Ну да, эти цифры совпадают с нашими прогнозами.", "word": "ну да"},
            {"sentence": "Странно, что клиент до сих пор не ответил на наше предложение.", "word": "странно"},
            {"sentence": "Не стоит напутать с последовательностью действий при запуске проекта.", "word": "напутать"},
            {"sentence": "Не нужно мучиться с этими расчетами, давайте используем автоматизированную систему.", "word": "мучиться"},
            {"sentence": "Если мы будем ругаться с подрядчиками, то потеряем деловую репутацию.", "word": "ругаться"},
            {"sentence": "Я стараюсь не париться по поводу мелких недочетов в документации.", "word": "париться"},
            {"sentence": "В вашем отчете полная несуразица с цифрами.", "word": "несуразица"},
            {"sentence": "Я понял вашу идею, давайте обсудим детали.", "word": "понял"},
            {"sentence": "Нам нужно докопаться до истинных причин снижения продаж.", "word": "докопаться"},
            {"sentence": "Я не готов предоставить финальную версию презентации раньше понедельника.", "word": "не готов"},
            {"sentence": "Ваше поведение на переговорах было не совсем адекватным.", "word": "адекватным"},
            {"sentence": "Я не могу больше терпеть постоянные срывы сроков.", "word": "терпеть"},
            {"sentence": "Спасибо за вашу помощь в подготовке отчета.", "word": "помощь"},
            {"sentence": "У нас возникла серьезная проблема с поставками материалов.", "word": "проблема"},
            {"sentence": "Я имел ввиду другое, когда говорил о реструктуризации отдела.", "word": "имел ввиду"},
            {"sentence": "Я задавал другой вопрос, меня интересовали сроки, а не бюджет.", "word": "задавал другой вопрос"},
            {"sentence": "По моим ощущениям, этот клиент не заинтересован в долгосрочном сотрудничестве.", "word": "ощущениям"},
            {"sentence": "Я не знаю, как решить эту техническую проблему с сервером.", "word": "не знаю"},
            {"sentence": "Нам нужно срочно согласовать этот контракт с юридическим отделом.", "word": "срочно"},
            {"sentence": "Нам нужно придумать новый подход к привлечению клиентов.", "word": "придумать"},
            {"sentence": "Я удивляюсь тому, что вы не учли эти риски в бизнес-плане.", "word": "удивляюсь"},
            {"sentence": "Вы не понимаете всей сложности этого технического решения.", "word": "не понимаете"},
            {"sentence": "Я не хочу участвовать в этом проекте из-за его низкой рентабельности.", "word": "не хочу"},
            {"sentence": "На самом деле, этот контракт не так выгоден, как кажется на первый взгляд.", "word": "на самом деле"},
            {"sentence": "Я стесняюсь выступать перед большой аудиторией на конференции.", "word": "стесняюсь"},
            {"sentence": "К сожалению, мы не уложились в установленный бюджет.", "word": "к сожалению"},
            {"sentence": "Вы не поверите, но клиент полностью одобрил наше предложение без изменений.", "word": "не поверите"},
            {"sentence": "Я не помню точных цифр из финансового отчета за прошлый квартал.", "word": "не помню"},
            {"sentence": "Я буду рад представить вам результаты нашего исследования.", "word": "рад"},
            {"sentence": "Нам важно предугадать реакцию рынка на новый продукт.", "word": "предугадать"},
            {"sentence": "Я не уверен, что мы сможем закончить проект в указанные сроки.", "word": "не уверен"},
            {"sentence": "Можно предполагать, что конкуренты выпустят аналогичный продукт в следующем квартале.", "word": "предполагать"},
            {"sentence": "Вроде бы мы обсуждали эту стратегию на прошлом совещании.", "word": "вроде"},
            {"sentence": "Давай поспорим на обед, что клиент примет наше предложение!", "word": "поспорим"},
            {"sentence": "Вы просили подготовить аналитику по рынку к среде.", "word": "просили"},
            {"sentence": "Боюсь, что мы не сможем выполнить все пункты договора в указанный срок.", "word": "боюсь"},
            {"sentence": "Расскажу вам вкратце о результатах переговоров с поставщиками.", "word": "вкратце"},
            {"sentence": "Вам будет удобно встретиться в четверг в 15:00?", "word": "удобно"},
            {"sentence": "Я советую вам пересмотреть условия этого контракта.", "word": "советую"},
            {"sentence": "У меня сегодня плохое настроение, давайте перенесем обсуждение.", "word": "плохое настроение"},
            {"sentence": "Я устал после длительных переговоров и хотел бы отложить принятие решения.", "word": "устал"},
            {"sentence": "Мы выполнили ваше поручение частично, остались некоторые детали.", "word": "частично"}
        ]
        
        # Перемешиваем предложения и выбираем 10 случайных
        import random
        random.shuffle(predefined_sentences)
        test_data["selected_sentences"] = predefined_sentences[:total_questions]
        context.user_data["stopwords_test"] = test_data
    
    # Получаем выбранные предложения
    selected_sentences = test_data.get("selected_sentences", [])
    
    # Получаем текущее предложение
    if current_question_idx < len(selected_sentences):
        current_stopword = selected_sentences[current_question_idx]
    else:
        # Если по какой-то причине нет предложения, используем запасной вариант
        current_stopword = {
            "word": "пожалуйста",
            "sentence": "Пожалуйста, рассмотрите это предложение."
        }
    
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
        f"Вопрос {current_question_idx + 1} из {total_questions}:\n\n"
        f"<b>Предложение:</b> {sentence}\n\n"
        f"Переформулируйте предложение так, чтобы избежать использования стоп-слова, но сохранить смысл. Если стоп-слова отсутсвуют, напишите предложение без изменений"
    )
    
    # Сохраняем текущее стоп-слово в контексте для последующей проверки ответа
    context.user_data["current_stopword"] = current_stopword
    
    # Устанавливаем флаг, что ожидаем ответ на стоп-слово
    context.user_data["awaiting_stopword_answer"] = True
    
    # Отправляем сообщение с клавиатурой для перехода к следующему вопросу или завершения теста
    keyboard = [
        [InlineKeyboardButton("⏭️ Пропустить вопрос", callback_data="next_stopword_question")]
    ]
    
    # Используем reply_text или edit_message_text в зависимости от типа обновления
    if update.callback_query:
        await update.callback_query.edit_message_text(
            question_message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )
    else:
        await update.effective_message.reply_text(
            question_message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )
    
    return CandidateStates.STOPWORDS_TEST

async def handle_stopwords_test_completion(update, context):
    """Обработка завершения теста стоп-слов"""
    # Получаем результаты теста
    test_data = context.user_data.get("stopwords_test", {})
    correct_answers = test_data.get("correct_answers", 0)
    selected_sentences = test_data.get("selected_sentences", [])
    total_questions = test_data.get("total_questions", 10)
    
    # Вычисляем процент правильных ответов
    answered_questions = min(len(selected_sentences), total_questions)
    percentage = (correct_answers / answered_questions * 100) if answered_questions > 0 else 0
    
    # Определяем, пройден ли тест
    passed = percentage >= 80
    
    # Сохраняем результат теста в БД
    user_id = update.effective_user.id
    if user_id:
        db.update_test_result(user_id, "where_to_start_test", passed)
        
        # Разблокируем следующий этап независимо от результата теста
        db.unlock_stage(user_id, "logic_test")
    
    # Формируем сообщение с результатами
    if passed:
        result_message = (
            f"🎉 Поздравляем! Вы успешно прошли тест на знание стоп-слов!\n\n"
            f"Ваш результат: {percentage:.1f}% ({correct_answers} из {answered_questions})\n\n"
            f"Вы можете перейти к следующему разделу программы найма."
        )
    else:
        result_message = (
            f"Вы не прошли тест на знание стоп-слов.\n\n"
            f"Ваш результат: {percentage:.1f}% ({correct_answers} из {answered_questions})\n\n"
            f"Требуется минимум 80% правильных ответов.\n\n"
            f"Несмотря на результат, вы можете перейти к следующему разделу программы найма."
        )
    
    # Очищаем данные теста из контекста
    if "stopwords_test" in context.user_data:
        del context.user_data["stopwords_test"]
    if "current_stopword" in context.user_data:
        del context.user_data["current_stopword"]
    if "awaiting_stopword_answer" in context.user_data:
        del context.user_data["awaiting_stopword_answer"]
    
    # Отправляем сообщение с результатами
    keyboard = [
        [InlineKeyboardButton("📋 Вернуться в главное меню", callback_data="back_to_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
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
    except Exception as e:
        logger.error(f"Ошибка при отправке результатов теста стоп-слов: {e}")
        # Отправляем как новое сообщение, если не удалось отредактировать
        await update.effective_chat.send_message(
            text=result_message,
            reply_markup=reply_markup
        )
    
    return CandidateStates.MAIN_MENU

def format_time(seconds):
    """Форматирует секунды в удобочитаемый формат времени"""
    minutes, seconds = divmod(int(seconds), 60)
    return f"{minutes:02d}:{seconds:02d}"

def get_test_time_limit(test_name):
    """Возвращает ограничение по времени для указанного теста в секундах"""
    # По умолчанию нет ограничения по времени
    if not test_name:
        return None
        
    # Задаем ограничения по времени для разных тестов
    time_limits = {
        "primary_test": 300,  # 5 минут
        "where_to_start_test": 600,  # 10 минут
        "logic_test_result": 1800,  # 30 минут
        "interview_prep_test": 600,  # 10 минут
        "take_test_result": 1200,  # 20 минут
    }
    
    # Возвращаем ограничение по времени или None, если ограничения нет
    return time_limits.get(test_name, None)

async def update_timer(context):
    """Обновляет таймер для тестов с ограничением времени"""
    job_data = context.job.data
    
    # Получаем данные из параметров задания
    chat_id = job_data.get("chat_id")
    message_id = job_data.get("message_id")
    current_question = job_data.get("current_question")
    end_time = job_data.get("end_time")
    
    # Получаем текущий контекст и обновление
    update_obj = job_data.get("update")
    context_obj = job_data.get("context_obj")
    
    # Проверяем блокировку - если идет обработка ответа, пропускаем обновление таймера
    if context_obj.user_data.get("processing_answer", False):
        return
    
    # Проверяем, не изменился ли номер текущего вопроса в контексте
    context_current_question = context_obj.user_data.get("current_question", 0)
    
    # Если номер вопроса изменился, останавливаем этот таймер
    if context_current_question != current_question:
        context.job.schedule_removal()
        return
    
    # Проверяем, не завершился ли уже тест
    if "test_data" not in context_obj.user_data:
        context.job.schedule_removal()
        return
    
    # Вычисляем оставшееся время
    now = time.time()
    remaining = max(0, end_time - now)
    
    # Если время истекло, завершаем тест
    if remaining <= 0:
        context.job.schedule_removal()
        
        # Заменяем сообщение на уведомление об истечении времени
        try:
            await context_obj.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text="⏰ Время тестирования истекло! Пожалуйста, вернитесь в главное меню.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("⬅️ Вернуться в главное меню", callback_data="back_to_menu")]
                ])
            )
        except Exception as e:
            logger.error(f"Ошибка при обновлении сообщения об истечении времени: {e}")
        
        # Вызываем функцию для обработки таймаута теста
        asyncio.create_task(test_timeout(update_obj, context_obj))
        return
    
    # Форматируем оставшееся время
    time_str = format_time(remaining)
    
    try:
        # Получаем текущий текст сообщения
        current_message_text = job_data.get("current_message_text", "")
        if not current_message_text:
            # Если текст сообщения недоступен, прекращаем обновление
            logger.error("Текст сообщения недоступен для обновления таймера")
            context.job.schedule_removal()
            return
        
        # Обновляем только строку с временем, остальной текст сохраняем
        lines = current_message_text.split('\n')
        if len(lines) > 0:
            # Заменяем только первую строку с таймером
            if "Времени осталось:" in lines[0]:
                lines[0] = f"Времени осталось: {time_str}"
                updated_text = '\n'.join(lines)
                
                # Сохраняем последний известный текст сообщения для следующего обновления
                job_data["current_message_text"] = updated_text

                # Используем безопасный метод обновления только текста
                try:
                    # Получаем текущие данные кнопок из context_obj
                    if "current_question_keyboard" not in context_obj.user_data:
                        # Если клавиатура не сохранена, создаем ее
                        test_data = context_obj.user_data.get("test_data", {})
                        current_question = context_obj.user_data.get("current_question", 0)
                        
                        questions = []
                        if isinstance(test_data, dict) and "questions" in test_data:
                            questions = test_data["questions"]
                        else:
                            questions = test_data
                        
                        if current_question < len(questions):
                            question = questions[current_question]
                            options = question.get('options', question.get('answers', []))
                            
                            # Создаем клавиатуру и сохраняем ее
                            keyboard = []
                            row = []
                            for i in range(len(options)):
                                row.append(InlineKeyboardButton(f"{i+1}", callback_data=f"answer_{i}"))
                                if len(row) == 3 or i == len(options) - 1:
                                    keyboard.append(row)
                                    row = []
                            
                            context_obj.user_data["current_question_keyboard"] = keyboard
                    
                    # Используем сохраненную клавиатуру
                    keyboard = context_obj.user_data.get("current_question_keyboard", [])
                    
                    # Обновляем сообщение с сохраненной клавиатурой
                    await context_obj.bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=message_id,
                        text=updated_text,
                        reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else None
                    )
                except Exception as e:
                    logger.error(f"Ошибка при обновлении таймера с сохраненной клавиатурой: {e}")
            else:
                pass
        else:
            pass
    except Exception as e:
        logger.error(f"Ошибка при обновлении таймера: {e}")
        # Не останавливаем таймер при ошибке, чтобы продолжить попытки обновления
    
    return CandidateStates.STOPWORDS_TEST

async def update_stopwords_timer(context):
    """Обновляет таймер для теста стоп-слов"""
    job_data = context.job.data
    if not job_data:
        return
    
    try:
        # Извлекаем данные из параметров задания
        chat_id = job_data.get("chat_id")
        message_id = job_data.get("message_id")
        current_question = job_data.get("current_question", 0)
        end_time = job_data.get("end_time", 0)
        total_questions = job_data.get("total_questions", 10)
        current_message_text = job_data.get("current_message_text", "")
        update_obj = job_data.get("update")
        context_obj = job_data.get("context_obj")
        
        # Проверка необходимых параметров
        if not all([chat_id, message_id, current_message_text]):
            logger.error("Не хватает данных для обновления таймера стоп-слов")
            return
        
        # Проверяем оставшееся время
        now = time.time()
        remaining = max(0, end_time - now)
        time_str = format_time(remaining)
        
        # Обновляем только часть сообщения с временем, сохраняя остальное содержимое
        current_time_line = f"⏱ Времени осталось: {time_str}"
        
        # Заменяем первую строку (с временем) на обновленную
        lines = current_message_text.split('\n')
        if lines and '⏱' in lines[0]:
            lines[0] = current_time_line
            updated_message = '\n'.join(lines)
            
            # Отправляем обновленное сообщение
            try:
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=updated_message,
                    parse_mode='HTML'
                )
            except Exception as e:
                logger.warning(f"Не удалось обновить таймер (сообщение могло быть удалено): {e}")
        
        # Если время истекло, завершаем тест
        if remaining <= 0 and update_obj and context_obj:
            # Отмечаем, что тест завершен по таймауту
            test_data = context_obj.user_data.get("stopwords_test", {})
            test_data["timeout"] = True
            
            # Останавливаем таймер
            if "stopwords_timer_job" in context_obj.user_data:
                context_obj.user_data["stopwords_timer_job"].schedule_removal()
                del context_obj.user_data["stopwords_timer_job"]
            
            # Завершаем тест и показываем результаты
            await handle_stopwords_test_completion(update_obj, context_obj)
            
    except Exception as e:
        logger.error(f"Ошибка при обновлении таймера стоп-слов: {e}")

async def test_timeout(update, context):
    user_id = update.effective_user.id
    test_name = context.user_data.get("current_test")
    
    # Check for admin mode
    admin_mode = context.user_data.get("admin_mode", False)
    
    # Mark test as failed due to timeout
    if admin_mode:
        if "admin_test_results" not in context.user_data:
            context.user_data["admin_test_results"] = {}
        context.user_data["admin_test_results"][test_name] = False
    else:
        # Save test result to database
        db.update_test_result(user_id, test_name, False)
    
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
    
    # Unlock the next stage in regular mode
    if next_stage and not admin_mode:
        db.unlock_stage(user_id, next_stage)
    
    # Show timeout message
    result_message = (
        f"⏰ Время на выполнение теста истекло!\n\n"
        f"К сожалению, вы не успели завершить тест вовремя.\n"
        f"Тест отмечен как не пройденный, но вы можете продолжить\n"
        f"с следующим этапом в программе найма."
    )
    
    # Add buttons for next steps
    keyboard = [
        [InlineKeyboardButton("📋 Вернуться в главное меню", callback_data="back_to_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Clean up test data from context
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
    
    # Stop timer if it exists
    if "test_timer_job" in context.user_data:
        try:
            context.user_data["test_timer_job"].schedule_removal()
        except Exception as e:
            logger.error(f"Error stopping timer due to timeout: {e}")
        del context.user_data["test_timer_job"]
    
    try:
        # Try to edit the last test message if possible
        if "test_message_id" in context.user_data:
            try:
                await context.bot.edit_message_text(
                    chat_id=update.effective_chat.id,
                    message_id=context.user_data["test_message_id"],
                    text=result_message,
                    reply_markup=reply_markup
                )
                return CandidateStates.MAIN_MENU
            except Exception as e:
                logger.error(f"Error editing message in test timeout: {e}")
        
        # Send as a new message if editing fails
        await update.effective_chat.send_message(
            text=result_message,
            reply_markup=reply_markup
        )
    except Exception as e:
        logger.error(f"Error sending test timeout message: {e}")
    
    return CandidateStates.MAIN_MENU

# Обработка поэтического задания
async def process_poem_task(update, context, text):
    """Обрабатывает поэтические задания от пользователя"""
    user_id = update.effective_user.id
    
    # Проверяем, что текст содержит минимум 4 строки
    lines = text.strip().split('\n')
    if len(lines) < 4:
        await update.message.reply_text(
            "Ваше стихотворение слишком короткое. Пожалуйста, напишите минимум 4 строки."
        )
        return CandidateStates.AWAITING_POEM
    
    # Отправляем сообщение о проверке
    processing_message = await update.message.reply_text("⏳ Проверяем ваше стихотворение...")
    
    # Используем ИИ для проверки стихотворения
    try:
        result = await verify_poem_task(text, user_id=user_id)
        is_valid = result["is_valid"]
        feedback = result["feedback"]
        
        # Удаляем сообщение о проверке
        await context.bot.delete_message(
            chat_id=update.effective_chat.id, 
            message_id=processing_message.message_id
        )
        
        if is_valid:
            # Обновляем результат теста в базе данных
            db.update_test_result(user_id, "interview_prep_test", True)
            
            # Разблокируем следующий этап если он был заблокирован
            db.unlock_stage(user_id, "schedule_interview")
            
            # Отправляем сообщение об успешном выполнении
            await update.message.reply_text(
                f"✅ Поздравляем! Ваше стихотворение принято!\n\n{feedback}\n\n"
                "Теперь вы можете перейти к следующему этапу - запись на собеседование."
            )
            
            # Сбрасываем состояние ожидания стихотворения
            context.user_data["awaiting_poem"] = False
            return await send_main_menu(update, context, edit=True)
        else:
            # Отправляем сообщение о неудаче с рекомендациями
            await update.message.reply_text(
                f"❌ К сожалению, ваше стихотворение не соответствует требованиям.\n\n{feedback}\n\n"
                "Пожалуйста, попробуйте еще раз, учитывая рекомендации."
            )
            return CandidateStates.AWAITING_POEM
    except Exception as e:
        logger.error(f"Error verifying poem: {e}")
        await update.message.reply_text(
            "Произошла ошибка при проверке стихотворения. Пожалуйста, попробуйте позже."
        )
        return await send_main_menu(update, context, edit=True)
