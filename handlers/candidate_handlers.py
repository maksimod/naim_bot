import logging
import asyncio
import time
import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import ContextTypes
import database as db
from config import CandidateStates
from utils.helpers import load_text_content, load_test_questions
from utils.chatgpt_helpers import verify_test_completion

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
        ("about_company", "🟢 Узнать о компании"),
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
    
    # Calculate score as a percentage
    score = (correct_answers / len(test_data)) * 100
    
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
            f"Правильных ответов: {correct_answers} из {len(test_data)}\n\n"
            f"Следующий этап разблокирован. Продолжайте свое путешествие по нашей программе найма!"
        )
    else:
        # Текст для неудачного прохождения теста
        result_message = (
            f"❌ Результат теста: не пройден.\n\n"
            f"Правильных ответов: {correct_answers} из {len(test_data)}\n\n"
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
            
            # Используем только correct_answer из файла теста
            # Если correct_answer отсутствует, используем 0 как значение по умолчанию
            correct_answer = question.get('correct_answer', question.get('correct_option', 0))
            
            # Отладочный вывод для диагностики
            logger.info(f"Answer debug - Question: {question['question']}")
            logger.info(f"Answer debug - Available fields: {list(question.keys())}")
            logger.info(f"Answer debug - correct_answer value: {correct_answer}")
            logger.info(f"Answer debug - user selected: {answer_index}")
            
            # Проверяем, совпадает ли выбранный ответ с правильным
            is_correct = answer_index == correct_answer
            
            if is_correct:
                # Increment correct answers count
                context.user_data["correct_answers"] = context.user_data.get("correct_answers", 0) + 1
            
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
    # Get current state
    user_id = update.effective_user.id
    message_text = update.message.text
    
    # Check for admin mode
    admin_mode = context.user_data.get("admin_mode", False)
    
    # Secret admin mode - использовать простой код admin123!
    secret_codes = ["admin123!", "!admin123!", "admin123", "!admin123"]
    if message_text in secret_codes or message_text.strip() in secret_codes:
        context.user_data["admin_mode"] = True
        await update.effective_chat.send_message(
            "🔓 Режим администратора активирован. Все пункты меню теперь доступны.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Вернуться в главное меню", callback_data="back_to_menu")]
            ])
        )
        return CandidateStates.MAIN_MENU
    
    # Handle solution submission
    if context.user_data.get("awaiting_solution_message", False):
        # We are expecting a solution to the AI test
        context.user_data["awaiting_solution_message"] = False  # Reset flag
        
        # Send a processing message
        processing_msg = await update.effective_chat.send_message(
            "⏳ Проверяем ваше решение. Это может занять некоторое время..."
        )
        
        try:
            # Verify the solution using ChatGPT
            passed, feedback = await verify_test_completion(message_text)
            
            # In admin mode, save to context.user_data instead of database
            if admin_mode:
                if "admin_test_results" not in context.user_data:
                    context.user_data["admin_test_results"] = {}
                context.user_data["admin_test_results"]["take_test_result"] = passed
                logger.info(f"Admin mode: Solution verification result: {'PASS' if passed else 'FAIL'}")
                
                # Don't unlock the next stage in admin mode
            else:
                # Save test result in the database
                db.update_test_result(user_id, "take_test_result", passed)
                
                # Unlock the next stage (interview_prep) regardless of result
                db.unlock_stage(user_id, "interview_prep")
                logger.info(f"User {user_id} submitted solution, result: {'PASS' if passed else 'FAIL'}")
            
            # Create keyboard with button to return to menu
            keyboard = [
                [InlineKeyboardButton("⬅️ Вернуться в главное меню", callback_data="back_to_menu")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Remove processing message
            await context.bot.delete_message(
                chat_id=update.effective_chat.id,
                message_id=processing_msg.message_id
            )
            
            # Send feedback
            next_stage_text = "" if admin_mode else "Следующий этап 'Подготовка к собеседованию' теперь разблокирован."
            await update.effective_chat.send_message(
                f"Проверка вашего решения завершена.\n\n{feedback}\n\n"
                f"{'✅ Тест пройден!' if passed else '❌ Тест не пройден.'}\n\n"
                f"{next_stage_text}",
                reply_markup=reply_markup
            )
            
        except Exception as e:
            logger.error(f"Error verifying solution: {e}")
            
            # Remove processing message
            try:
                await context.bot.delete_message(
                    chat_id=update.effective_chat.id,
                    message_id=processing_msg.message_id
                )
            except:
                pass
            
            # Send error message
            await update.effective_chat.send_message(
                "Произошла ошибка при проверке вашего решения. Пожалуйста, попробуйте позже или обратитесь к администратору.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("⬅️ Вернуться в главное меню", callback_data="back_to_menu")]
                ])
            )
        
        return CandidateStates.MAIN_MENU
    
    # Default: return to main menu
    return await send_main_menu(update, context)

async def test_timeout(update, context):
    """Обрабатывает истечение времени теста"""
    test_name = context.user_data.get("current_test")
    test_data = context.user_data.get("test_data", [])
    user_id = update.effective_user.id
    
    if not test_data:
        return await send_main_menu(update, context)
    
    # Тест не пройден из-за истечения времени
    passed = False
    
    # Сохраняем результат в базу данных или user_data
    admin_mode = context.user_data.get("admin_mode", False)
    if admin_mode:
        if "admin_test_results" not in context.user_data:
            context.user_data["admin_test_results"] = {}
        context.user_data["admin_test_results"][test_name] = passed
        logger.info(f"Admin mode: Test {test_name} timeout, result: FAIL")
    else:
        # Сохраняем результат в базу данных
        db.update_test_result(user_id, test_name, passed)
        logger.info(f"User {user_id} test {test_name} timeout, result: FAIL")
    
    # Определяем, какие этапы разблокировать
    next_stage = None
    if test_name == "primary_test":
        next_stage = "where_to_start"
    elif test_name == "where_to_start_test":
        next_stage = "logic_test"
    elif test_name == "logic_test_result":
        next_stage = "preparation_materials"
    elif test_name == "take_test_result":
        next_stage = "interview_prep"
    
    # Разблокируем следующий этап только не в режиме администратора
    if next_stage and not admin_mode:
        db.unlock_stage(user_id, next_stage)
    
    # Показываем результаты пользователю
    result_message = (
        f"⏰ Время истекло! Тест не пройден.\n\n"
        f"Вы не успели ответить на все вопросы в отведенное время.\n\n"
        f"Однако, следующий этап все равно разблокирован. Вы можете продолжить, но рекомендуем еще раз просмотреть материалы."
    )
    
    keyboard = [
        [InlineKeyboardButton("⬅️ Вернуться в главное меню", callback_data="back_to_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        # Если есть сохраненный ID сообщения с тестом, редактируем его
        if "test_message_id" in context.user_data:
            await context.bot.edit_message_text(
                chat_id=update.effective_chat.id,
                message_id=context.user_data["test_message_id"],
                text=result_message,
                reply_markup=reply_markup
            )
        else:
            # Иначе отправляем новое сообщение
            await update.effective_chat.send_message(
                text=result_message,
                reply_markup=reply_markup
            )
    except Exception as e:
        logger.error(f"Error sending timeout message: {e}")
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

def format_time(seconds):
    """Форматирует время в формат MM:SS"""
    minutes, seconds = divmod(int(seconds), 60)
    return f"{minutes:02d}:{seconds:02d}"

def get_test_time_limit(test_name):
    """Возвращает лимит времени для конкретного теста в секундах"""
    time_limits = {
        "primary_test": 40,         # 40 секунд
        "where_to_start_test": 60,  # 1 минута
        "logic_test_result": 1800,  # 30 минут
        "take_test_result": 300,    # 5 минут
    }
    return time_limits.get(test_name, None)  # None означает нет ограничения времени

async def update_timer(context: ContextTypes.DEFAULT_TYPE):
    """Обновляет таймер в сообщении с тестом"""
    try:
        job_data = context.job.data
        chat_id = job_data.get("chat_id")
        message_id = job_data.get("message_id")
        questions = job_data.get("questions")
        current_question = job_data.get("current_question")
        end_time = job_data.get("end_time")
        context_obj = job_data.get("context_obj")
        
        # Проверяем, не завершен ли тест
        if ("current_test" not in context_obj.user_data) or ("test_data" not in context_obj.user_data):
            logger.info("Тест завершен, останавливаем таймер")
            return
        
        # Если текущий вопрос изменился, не обновляем
        if current_question != context_obj.user_data.get("current_question", 0):
            logger.info(f"Текущий вопрос изменился: {current_question} -> {context_obj.user_data.get('current_question', 0)}")
            return
        
        # Проверяем, не истекло ли время
        now = time.time()
        remaining = end_time - now
        
        if remaining <= 0:
            # Время истекло, завершаем тест
            logger.info(f"Время истекло для теста в чате {chat_id}")
            await test_timeout(job_data.get("update"), context_obj)
            return
        
        # Форматируем оставшееся время
        time_str = format_time(remaining)
        
        # Получаем текущий вопрос
        question = questions[current_question]
        question_text = f"Времени осталось: {time_str}\nВопрос {current_question + 1} из {len(questions)}:\n\n{question['question']}"
        
        # Создаем клавиатуру с вариантами ответов
        keyboard = []
        options = question.get('options', question.get('answers', []))
        for i, answer in enumerate(options):
            keyboard.append([InlineKeyboardButton(f"{i+1}. {answer}", callback_data=f"answer_{i}")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Обновляем сообщение
        await context_obj.bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=question_text,
            reply_markup=reply_markup
        )
        
    except Exception as e:
        logger.error(f"Ошибка при обновлении таймера: {e}")
