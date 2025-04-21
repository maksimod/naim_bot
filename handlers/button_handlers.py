import logging
import os
import sys
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import ContextTypes
import database as db
from config import CandidateStates
from utils.helpers import load_text_content, load_test_questions
from handlers.candidate_handlers import send_main_menu, send_test_question
import asyncio

# Добавляем корневую директорию проекта в путь импорта
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger(__name__)

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button clicks from the inline keyboard."""
    query = update.callback_query
    await query.answer()  # Acknowledge the button click
    
    # Get user ID and current state
    user_id = update.effective_user.id
    unlocked_stages = db.get_user_unlocked_stages(user_id)
    
    # Check for admin mode
    admin_mode = context.user_data.get("admin_mode", False)
    
    # If the button click is for a locked stage and admin mode is not active, show a message
    if (query.data in ['where_to_start', 'preparation_materials', 'take_test', 
                      'interview_prep', 'schedule_interview'] and 
                      query.data not in unlocked_stages and 
                      not admin_mode):
        await query.edit_message_text(
            "🔒 Этот пункт пока недоступен. Продолжайте выполнять предыдущие задания, чтобы разблокировать его.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Назад", callback_data="back_to_menu")]
            ])
        )
        return CandidateStates.MAIN_MENU
    
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
    
    # Menu options with emoji status controlled by send_main_menu
    menu_options = [
        ("about_company", "🟢 Узнать о компании"),
        ("primary_file", "🟢 Первичный файл"),
        ("where_to_start", "🔴 С чего начать"),
        ("preparation_materials", "🔴 Материалы для подготовки"),
        ("take_test", "🔴 Пройти испытание"),
        ("interview_prep", "🔴 Подготовка к собеседованию"),
        ("schedule_interview", "🔴 Пройти собеседование")
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
        # Вместо удаления сообщения редактируем его
        # Show warning before starting the test
        warning_message = (
            "⚠️ <b>ВНИМАНИЕ!</b> ⚠️\n\n" +
            "Перед началом теста, пожалуйста, внимательно ознакомьтесь с материалами. " +
            "<b>Если вы не пройдете успешно хотя бы половину всех тестов, вы будете заблокированы в системе.</b>\n\n" +
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
        # Проверяем, проходил ли пользователь уже этот тест
        user_id = update.effective_user.id
        user_test_results = db.get_user_test_results(user_id)
        
        # Если тест уже был пройден (успешно или неуспешно), не позволяем пересдавать
        if "primary_test" in user_test_results:
            await query.edit_message_text(
                "Вы уже проходили этот тест. Повторное прохождение тестов не разрешено.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("⬅️ Вернуться в главное меню", callback_data="back_to_menu")]
                ])
            )
            return CandidateStates.MAIN_MENU
            
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
    
    elif (query.data == "where_to_start" and "where_to_start" in unlocked_stages) or admin_mode and query.data == "where_to_start":
        content = load_text_content("where_to_start.txt")
        
        # Вместо создания нового сообщения, редактируем текущее
        keyboard = [
            [InlineKeyboardButton("Пройти тест", callback_data="where_to_start_test")],
            [InlineKeyboardButton("⬅️ Вернуться в главное меню", callback_data="back_to_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        try:
            await query.edit_message_text(
                content + "\n\nЧтобы разблокировать следующий этап, пройдите тест.",
                reply_markup=reply_markup
            )
            # Сохраняем ID сообщения для возможного последующего редактирования
            context.user_data["content_message_id"] = query.message.message_id
        except Exception as e:
            logger.error(f"Error editing message: {e}")
            # Если редактирование не удалось, возвращаемся в главное меню
            return await send_main_menu(update, context, edit=True)
            
        return CandidateStates.WHERE_TO_START
    
    elif query.data == "where_to_start_test":
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
        
        # Show warning before starting the test
        warning_message = (
            "⚠️ <b>ВНИМАНИЕ!</b> ⚠️\n\n" +
            "Перед началом теста, пожалуйста, внимательно ознакомьтесь с материалами. " +
            "<b>Если вы не пройдете успешно хотя бы половину всех тестов, вы будете заблокированы в системе.</b>\n\n" +
            "Вы уверены, что готовы начать тест?"
        )
        
        keyboard = [
            [InlineKeyboardButton("✅ Да, я готов", callback_data="confirm_where_to_start_test")],
            [InlineKeyboardButton("❌ Нет, вернуться к материалам", callback_data="where_to_start")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Редактировать текущее сообщение вместо создания нового
        try:
            await query.edit_message_text(warning_message, reply_markup=reply_markup, parse_mode='HTML')
        except Exception as e:
            logger.error(f"Error editing message: {e}")
            # Только в случае ошибки отправляем новое сообщение
            await query.message.reply_text(warning_message, reply_markup=reply_markup, parse_mode='HTML')
            
        return CandidateStates.WHERE_TO_START
    
    elif query.data == "confirm_where_to_start_test":
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
        
        # Load test questions
        test_data = load_test_questions("where_to_start_test.json")
        if not test_data:
            try:
                await query.edit_message_text(
                    "Ошибка загрузки теста. Пожалуйста, попробуйте позже.",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("⬅️ Вернуться в главное меню", callback_data="back_to_menu")]
                    ])
                )
            except Exception as e:
                logger.error(f"Error editing message: {e}")
                await query.message.reply_text("Ошибка загрузки теста. Пожалуйста, попробуйте позже.")
            return CandidateStates.MAIN_MENU
        
        # Store test data in context
        context.user_data["current_test"] = "where_to_start_test"
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
        
        return CandidateStates.WHERE_TO_START_TEST
    
    # Handler for logic_test menu option
    elif (query.data == "logic_test" and "logic_test" in unlocked_stages) or admin_mode and query.data == "logic_test":
        try:
            # Сначала отправляем документ
            docx_path = "materials/logic_test_prepare.docx"
            with open(docx_path, 'rb') as doc:
                await context.bot.send_document(
                    chat_id=update.effective_chat.id,
                    document=doc,
                    filename="logic_test_prepare.docx",
                    caption="Материалы для подготовки к тесту на логику"
                )
                
            # Добавляем паузу в 5 секунд, чтобы файл успел загрузиться
            await asyncio.sleep(5)
                
            # Затем отправляем краткое описание КАК НОВОЕ СООБЩЕНИЕ
            brief_content = (
                "*Подготовка к тесту на логическое мышление*\n\n"
                "Этот тест проверяет ваши навыки логического мышления. Он не требует специальных знаний и "
                "опирается на логические принципы при работе с описанными ситуациями.\n\n"
                "Основы логики, которые нужно знать, содержатся в файле выше.\n\n"
                "В тесте вы встретите вымышленные термины и понятия - это сделано специально, чтобы проверить "
                "чистые логические навыки без влияния предварительных знаний.\n\n"
                "*Стратегия прохождения теста*:\n\n"
                "1. Внимательно читайте условие задания\n"
                "2. Переформулируйте условие в более простую логическую структуру\n"
                "3. Проверяйте каждый ответ на соответствие условию\n"
                "4. Помните, что некоторые ответы могут быть технически верными, но не следовать напрямую из посылок\n\n"
                "Удачи с прохождением теста! Для успешного завершения вам нужно правильно ответить как минимум на 22 вопроса из 30.\n\n"
                "Чтобы разблокировать следующий этап, пройдите тест на логику."
            )
            
            # Создаем кнопки
            keyboard = [
                [InlineKeyboardButton("Пройти тест", callback_data="logic_test_start")],
                [InlineKeyboardButton("⬅️ Вернуться в главное меню", callback_data="back_to_menu")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Отправляем новое сообщение вместо редактирования старого
            message = await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=brief_content,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            
            # Сохраняем ID нового сообщения
            context.user_data["content_message_id"] = message.message_id
            
            # Удаляем старое сообщение с меню
            try:
                await query.delete_message()
            except Exception as e:
                logger.error(f"Error deleting old message: {e}")
            
        except FileNotFoundError:
            logger.error(f"File not found: {docx_path}")
            await query.edit_message_text(
                "Ошибка: Материалы для подготовки к тесту не найдены. Пожалуйста, сообщите администратору.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("⬅️ Вернуться в главное меню", callback_data="back_to_menu")]
                ])
            )
            return CandidateStates.MAIN_MENU
        except Exception as e:
            logger.error(f"Error sending logic test materials: {e}")
            return await send_main_menu(update, context, edit=True)
            
        return CandidateStates.LOGIC_TEST
    
    # Handler for starting the logic test
    elif query.data == "logic_test_start":
        # Show warning before starting the test
        warning_message = (
            "⚠️ <b>ВНИМАНИЕ!</b> ⚠️\n\n" +
            "Перед началом теста на логику, пожалуйста, внимательно ознакомьтесь с материалами. " +
            "<b>Для успешного прохождения необходимо правильно ответить как минимум на 22 вопроса из 30.</b>\n\n" +
            "Вы уверены, что готовы начать тест?"
        )
        
        keyboard = [
            [InlineKeyboardButton("✅ Да, я готов", callback_data="confirm_logic_test")],
            [InlineKeyboardButton("❌ Нет, вернуться к материалам", callback_data="logic_test")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        try:
            await query.edit_message_text(warning_message, reply_markup=reply_markup, parse_mode='HTML')
        except Exception as e:
            logger.error(f"Error editing message: {e}")
            await query.message.reply_text(warning_message, reply_markup=reply_markup, parse_mode='HTML')
            
        return CandidateStates.LOGIC_TEST_PREPARE
        
    # Handler for confirming the logic test
    elif query.data == "confirm_logic_test":
        # Проверяем, проходил ли пользователь уже этот тест
        user_id = update.effective_user.id
        user_test_results = db.get_user_test_results(user_id)
        
        # Если тест уже был пройден (успешно или неуспешно), не позволяем пересдавать
        if "logic_test_result" in user_test_results:
            await query.edit_message_text(
                "Вы уже проходили этот тест. Повторное прохождение тестов не разрешено.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("⬅️ Вернуться в главное меню", callback_data="back_to_menu")]
                ])
            )
            return CandidateStates.MAIN_MENU
            
        # Load test questions
        test_data = load_test_questions("logic_test.json")
        if not test_data:
            try:
                await query.edit_message_text(
                    "Ошибка загрузки теста. Пожалуйста, попробуйте позже.",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("⬅️ Вернуться в главное меню", callback_data="back_to_menu")]
                    ])
                )
            except Exception as e:
                logger.error(f"Error editing message: {e}")
                await query.message.reply_text("Ошибка загрузки теста. Пожалуйста, попробуйте позже.")
            return CandidateStates.MAIN_MENU
        
        # Store test data in context
        context.user_data["current_test"] = "logic_test_result"
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
        
        return CandidateStates.LOGIC_TEST_TESTING
    
    # Contact developers - FIX: emoji display issue
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
    
    # Handler for preparation_materials
    elif (query.data == "preparation_materials" and "preparation_materials" in unlocked_stages) or admin_mode and query.data == "preparation_materials":
        # First, send the video file
        try:
            # Send a message that video is loading
            await query.edit_message_text(
                "Загрузка видеоматериалов, пожалуйста подождите...",
                reply_markup=None
            )
            
            # Send the video as a separate message
            video_path = "materials/materials_for_prepare.mp4"
            with open(video_path, 'rb') as video:
                video_message = await context.bot.send_video(
                    chat_id=update.effective_chat.id,
                    video=video,
                    caption="Материалы для подготовки"
                )
            
            # Now, send the survey question
            survey_data = load_test_questions("materials_for_prepare_survey.json")
            if not survey_data or not isinstance(survey_data, dict):
                await update.effective_chat.send_message(
                    "Ошибка: не удалось загрузить опрос. Пожалуйста, свяжитесь с администратором."
                )
                return await send_main_menu(update, context)
            
            # Create keyboard with survey options
            keyboard = []
            context.user_data["survey_selected_options"] = []
            
            for i, option in enumerate(survey_data["options"]):
                # For multiple choice, we'll use a different callback format
                keyboard.append([InlineKeyboardButton(
                    f"☐ {option}", 
                    callback_data=f"survey_option_{i}"
                )])
            
            # Add submit button at the bottom
            keyboard.append([InlineKeyboardButton("Отправить ответы", callback_data="submit_survey")])
            keyboard.append([InlineKeyboardButton("⬅️ Вернуться в главное меню", callback_data="back_to_menu")])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Store the survey options for reference
            context.user_data["survey_options"] = survey_data["options"]
            context.user_data["survey_multiple_choice"] = survey_data.get("multiple_choice", False)
            
            # Send as a new message
            survey_message = await update.effective_chat.send_message(
                text=f"{survey_data['question']}\n\nВыберите один или несколько вариантов:",
                reply_markup=reply_markup
            )
            
            # Store the survey message ID
            context.user_data["survey_message_id"] = survey_message.message_id
            
        except FileNotFoundError:
            logger.error(f"Video file not found: {video_path}")
            await update.effective_chat.send_message(
                "Извините, видеоматериалы временно недоступны. Пожалуйста, свяжитесь с администратором."
            )
            return await send_main_menu(update, context)
        except Exception as e:
            logger.error(f"Error sending preparation materials: {e}")
            await update.effective_chat.send_message(
                "Произошла ошибка при загрузке материалов. Пожалуйста, попробуйте позже."
            )
            return await send_main_menu(update, context)
        
        return CandidateStates.PREPARATION_MATERIALS
    
    # Handle survey option selection (multiple choice)
    elif query.data.startswith("survey_option_"):
        try:
            option_index = int(query.data.split("_")[-1])
            survey_options = context.user_data.get("survey_options", [])
            selected_options = context.user_data.get("survey_selected_options", [])
            
            if option_index in selected_options:
                # Deselect this option
                selected_options.remove(option_index)
            else:
                # Select this option
                selected_options.append(option_index)
            
            # Update user data
            context.user_data["survey_selected_options"] = selected_options
            
            # Rebuild keyboard with updated selection status
            keyboard = []
            for i, option in enumerate(survey_options):
                # Show checkmark for selected options, empty box for unselected
                prefix = "☑" if i in selected_options else "☐"
                keyboard.append([InlineKeyboardButton(
                    f"{prefix} {option}", 
                    callback_data=f"survey_option_{i}"
                )])
            
            # Add submit button at the bottom
            keyboard.append([InlineKeyboardButton("Отправить ответы", callback_data="submit_survey")])
            keyboard.append([InlineKeyboardButton("⬅️ Вернуться в главное меню", callback_data="back_to_menu")])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Update the message with the new keyboard
            await query.edit_message_reply_markup(reply_markup)
            
        except Exception as e:
            logger.error(f"Error handling survey option selection: {e}")
        
        return CandidateStates.PREPARATION_MATERIALS
    
    # Handle survey submission
    elif query.data == "submit_survey":
        selected_options = context.user_data.get("survey_selected_options", [])
        survey_options = context.user_data.get("survey_options", [])
        
        # Construct a string with the selected options
        if selected_options:
            selected_text = "\n".join([f"- {survey_options[i]}" for i in selected_options])
            response_text = f"Спасибо за ваши ответы!\n\nВыбранные варианты:\n{selected_text}"
        else:
            response_text = "Вы не выбрали ни одного варианта. Ответы не сохранены."
        
        # Save survey results to database if needed
        # Here we would typically save the results to DB
        user_id = update.effective_user.id
        
        # Unlock the next stage (take_test)
        db.unlock_stage(user_id, "take_test")
        
        # Update the message with confirmation and return button
        keyboard = [
            [InlineKeyboardButton("⬅️ Вернуться в главное меню", callback_data="back_to_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        try:
            await query.edit_message_text(
                response_text + "\n\nСледующий этап разблокирован.",
                reply_markup=reply_markup
            )
        except Exception as e:
            logger.error(f"Error updating survey message: {e}")
            await update.effective_chat.send_message(
                response_text + "\n\nСледующий этап разблокирован.",
                reply_markup=reply_markup
            )
        
        return CandidateStates.MAIN_MENU
    
    # Handler for take_test button
    elif (query.data == "take_test" and "take_test" in unlocked_stages) or admin_mode and query.data == "take_test":
        try:
            # Проверяем, проходил ли пользователь уже этот тест
            user_id = update.effective_user.id
            user_test_results = db.get_user_test_results(user_id)
            
            # Если тест уже был пройден (успешно или неуспешно), не позволяем пересдавать
            if "take_test_result" in user_test_results:
                await query.edit_message_text(
                    "Вы уже проходили этот тест. Повторное прохождение тестов не разрешено.",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("⬅️ Вернуться в главное меню", callback_data="back_to_menu")]
                    ])
                )
                return CandidateStates.MAIN_MENU
                
            # Load the task description
            task_content = load_text_content("past_the_test.txt")
            
            # Show the task to the user
            keyboard = [
                [InlineKeyboardButton("Отправить решение", callback_data="submit_solution")],
                [InlineKeyboardButton("⬅️ Вернуться в главное меню", callback_data="back_to_menu")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            try:
                await query.edit_message_text(
                    task_content,
                    reply_markup=reply_markup
                )
                context.user_data["content_message_id"] = query.message.message_id
            except Exception as e:
                logger.error(f"Error editing message: {e}")
                # If editing fails, send as a new message
                message = await update.effective_chat.send_message(
                    text=task_content,
                    reply_markup=reply_markup
                )
                context.user_data["content_message_id"] = message.message_id
                
            # Set up the context for solution submission
            context.user_data["awaiting_solution"] = True
            
        except Exception as e:
            logger.error(f"Error handling take_test button: {e}")
            await update.effective_chat.send_message(
                "Произошла ошибка при загрузке задания. Пожалуйста, попробуйте позже."
            )
            return await send_main_menu(update, context)
            
        return CandidateStates.TAKE_TEST
    
    # Handler for submission of the solution
    elif query.data == "submit_solution":
        if "awaiting_solution" not in context.user_data or not context.user_data["awaiting_solution"]:
            # If we're not awaiting a solution, return to main menu
            return await send_main_menu(update, context)
            
        # Проверяем, проходил ли пользователь уже этот тест
        user_id = update.effective_user.id
        user_test_results = db.get_user_test_results(user_id)
        
        # Если тест уже был пройден (успешно или неуспешно), не позволяем пересдавать
        if "take_test_result" in user_test_results:
            await query.edit_message_text(
                "Вы уже проходили этот тест. Повторное прохождение тестов не разрешено.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("⬅️ Вернуться в главное меню", callback_data="back_to_menu")]
                ])
            )
            return CandidateStates.MAIN_MENU
            
        # Text to send
        message_text = ("Пожалуйста, отправьте ваше решение задачи в следующем сообщении.\n\n"
                       "Вставьте полный текст вашего диалога с ИИ, включая задание и решение.")
        reply_markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ Отмена и возврат в меню", callback_data="back_to_menu")]
        ])
        
        try:
            # Try to edit the current message
            await query.edit_message_text(
                message_text,
                reply_markup=reply_markup
            )
        except Exception as e:
            # If editing fails, send a new message
            logger.error(f"Error editing message: {e}")
            await query.message.reply_text(
                message_text,
                reply_markup=reply_markup
            )
        
        # Set the state to indicate we're waiting for a solution message
        context.user_data["awaiting_solution_message"] = True
        # Проверка, что состояние WAITING_FOR_SOLUTION существует
        if hasattr(CandidateStates, 'WAITING_FOR_SOLUTION'):
            return CandidateStates.WAITING_FOR_SOLUTION
        else:
            # Если состояние не существует, используем TAKE_TEST как запасной вариант
            logger.warning("CandidateStates.WAITING_FOR_SOLUTION not found, using TAKE_TEST instead")
            return CandidateStates.TAKE_TEST
    
    # Handler for interview_prep
    elif (query.data == "interview_prep" and "interview_prep" in unlocked_stages) or admin_mode and query.data == "interview_prep":
        content = load_text_content("interview_prep.txt")
        
        # Разбиваем длинный текст на части
        max_length = 3000  # Безопасная длина для сообщений Telegram
        
        # Сначала отправляем первую часть текста с кнопками
        first_part = content[:max_length] if len(content) > max_length else content
        
        keyboard = [
            [InlineKeyboardButton("Пройти тест", callback_data="interview_prep_test")],
            [InlineKeyboardButton("⬅️ Вернуться в главное меню", callback_data="back_to_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        try:
            # Отправляем первую часть с кнопками
            await query.edit_message_text(
                first_part,
                reply_markup=reply_markup
            )
            context.user_data["content_message_id"] = query.message.message_id
            
            # Если текст был разбит, отправляем оставшиеся части
            if len(content) > max_length:
                remaining_content = content[max_length:]
                await update.effective_chat.send_message(remaining_content)
        except Exception as e:
            logger.error(f"Error editing message: {e}")
            # If editing fails, send as a new message
            message = await update.effective_chat.send_message(
                text=first_part,
                reply_markup=reply_markup
            )
            context.user_data["content_message_id"] = message.message_id
            
            # Если текст был разбит, отправляем оставшиеся части
            if len(content) > max_length:
                remaining_content = content[max_length:]
                await update.effective_chat.send_message(remaining_content)
            
        return CandidateStates.INTERVIEW_PREP
    
    # Handler for interview_prep_test
    elif query.data == "interview_prep_test":
        # Show warning before starting the test
        warning_message = (
            "⚠️ <b>ВНИМАНИЕ!</b> ⚠️\n\n" +
            "Перед началом теста, пожалуйста, внимательно ознакомьтесь с материалами. " +
            "<b>Если вы не пройдете успешно хотя бы половину всех тестов, вы будете заблокированы в системе.</b>\n\n" +
            "Вы уверены, что готовы начать тест?"
        )
        
        keyboard = [
            [InlineKeyboardButton("✅ Да, я готов", callback_data="confirm_interview_prep_test")],
            [InlineKeyboardButton("❌ Нет, вернуться к материалам", callback_data="interview_prep")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        try:
            await query.edit_message_text(warning_message, reply_markup=reply_markup, parse_mode='HTML')
        except Exception as e:
            logger.error(f"Error editing message: {e}")
            # If editing fails, send as a new message
            await query.message.reply_text(warning_message, reply_markup=reply_markup, parse_mode='HTML')
            
        return CandidateStates.INTERVIEW_PREP
    
    # Handler for confirm_interview_prep_test
    elif query.data == "confirm_interview_prep_test":
        # Проверяем, проходил ли пользователь уже этот тест
        user_id = update.effective_user.id
        user_test_results = db.get_user_test_results(user_id)
        
        # Если тест уже был пройден (успешно или неуспешно), не позволяем пересдавать
        if "interview_prep_test" in user_test_results:
            await query.edit_message_text(
                "Вы уже проходили этот тест. Повторное прохождение тестов не разрешено.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("⬅️ Вернуться в главное меню", callback_data="back_to_menu")]
                ])
            )
            return CandidateStates.MAIN_MENU
            
        # Load test questions
        test_data = load_test_questions("interview_prep_test.json")
        if not test_data:
            await query.message.reply_text("Ошибка загрузки теста. Пожалуйста, попробуйте позже.")
            return CandidateStates.MAIN_MENU
        
        # Store test data in context
        context.user_data["current_test"] = "interview_prep_test"
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
        
        return CandidateStates.INTERVIEW_PREP_TEST
    
    # Handler for scheduled_interview button
    elif (query.data == "schedule_interview" and "schedule_interview" in unlocked_stages) or admin_mode and query.data == "schedule_interview":
        # Get the test results for the user
        user_test_results = db.get_user_test_results(user_id)
        
        # В режиме администратора используем результаты из context.user_data
        if admin_mode:
            admin_test_results = context.user_data.get("admin_test_results", {})
            # Объединяем с результатами из БД, но admin_test_results имеют приоритет
            display_test_results = {**user_test_results, **admin_test_results}
        else:
            display_test_results = user_test_results
        
        # Определяем список всех тестов
        test_names = {
            "primary_test": "Первичный файл",
            "where_to_start_test": "С чего начать",
            "logic_test_result": "Тест на логику",
            "take_test_result": "Пройти испытание", 
            "interview_prep_test": "Подготовка к собеседованию"
        }
        
        # Всего тестов и количество пройденных
        total_tests = len(test_names)  # Всегда 5 тестов
        passed_tests = 0
        
        test_status = []
        for test_id, display_name in test_names.items():
            if test_id in display_test_results and display_test_results[test_id]:
                passed_tests += 1
                status = "✅ Пройден"
            else:
                status = "❌ Не пройден"
            test_status.append(f"{display_name}: {status}")
        
        # Create a message with test results
        test_results_message = "Результаты всех тестов:\n\n"
        test_results_message += "\n".join(test_status)
        test_results_message += f"\n\nВсего пройдено {passed_tests} из {total_tests} тестов."
        
        # Check if the user has passed at least 3 out of 5 tests
        if passed_tests >= 3:  # More than 50% requirement
            # Get interview status to check if user already has a pending request
            interview_status = db.get_interview_status(user_id)
            
            if interview_status and interview_status['status'] == 'pending':
                # User already has a pending request
                message = (
                    f"{test_results_message}\n\n"
                    "🕒 У вас уже есть ожидающий ответа запрос на собеседование.\n\n"
                    f"Предпочтительный день: {interview_status['preferred_day']}\n"
                    f"Предпочтительное время: {interview_status['preferred_time']}\n\n"
                    "Пожалуйста, дождитесь ответа рекрутера."
                )
                keyboard = [
                    [InlineKeyboardButton("⬅️ Вернуться в главное меню", callback_data="back_to_menu")]
                ]
            elif interview_status and interview_status['status'] == 'approved':
                # Interview already approved
                message = (
                    f"{test_results_message}\n\n"
                    "✅ Ваш запрос на собеседование был подтвержден!\n\n"
                    f"Ответ рекрутера: {interview_status['recruiter_response']}\n\n"
                    "Хорошей подготовки к собеседованию!"
                )
                keyboard = [
                    [InlineKeyboardButton("⬅️ Вернуться в главное меню", callback_data="back_to_menu")]
                ]
            elif interview_status and interview_status['status'] == 'rejected':
                # Interview was rejected, allow to make new request
                message = (
                    f"{test_results_message}\n\n"
                    "🎉 Поздравляем! Вы успешно прошли все необходимые этапы и готовы к собеседованию!\n\n"
                    "Ваш предыдущий запрос был отклонен:\n"
                    f"{interview_status['recruiter_response']}\n\n"
                    "Выберите удобные день и время:"
                )
                keyboard = [
                    [InlineKeyboardButton("Понедельник", callback_data="interview_day_Понедельник")],
                    [InlineKeyboardButton("Вторник", callback_data="interview_day_Вторник")],
                    [InlineKeyboardButton("Среда", callback_data="interview_day_Среда")],
                    [InlineKeyboardButton("Четверг", callback_data="interview_day_Четверг")],
                    [InlineKeyboardButton("Пятница", callback_data="interview_day_Пятница")],
                    [InlineKeyboardButton("⬅️ Вернуться в главное меню", callback_data="back_to_menu")]
                ]
                # Store that we're in interview scheduling mode
                context.user_data["scheduling_interview"] = True
            else:
                # No existing request, show schedule form
                message = (
                    f"{test_results_message}\n\n"
                    "🎉 Поздравляем! Вы успешно прошли все необходимые этапы и готовы к собеседованию!\n\n"
                    "Выберите удобный для вас день недели:"
                )
                keyboard = [
                    [InlineKeyboardButton("Понедельник", callback_data="interview_day_Понедельник")],
                    [InlineKeyboardButton("Вторник", callback_data="interview_day_Вторник")],
                    [InlineKeyboardButton("Среда", callback_data="interview_day_Среда")],
                    [InlineKeyboardButton("Четверг", callback_data="interview_day_Четверг")],
                    [InlineKeyboardButton("Пятница", callback_data="interview_day_Пятница")],
                    [InlineKeyboardButton("⬅️ Вернуться в главное меню", callback_data="back_to_menu")]
                ]
                # Store that we're in interview scheduling mode
                context.user_data["scheduling_interview"] = True
        else:
            message = (
                test_results_message + "\n\n"
                "К сожалению, вы не прошли необходимое количество тестов для перехода к собеседованию.\n"
                "Пожалуйста, пройдите оставшиеся тесты и попробуйте снова."
            )
            keyboard = [
                [InlineKeyboardButton("⬅️ Вернуться в главное меню", callback_data="back_to_menu")]
            ]
        
        # Send the message to the user
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        try:
            await query.edit_message_text(
                message,
                reply_markup=reply_markup
            )
        except Exception as e:
            logger.error(f"Error editing message: {e}")
            await update.effective_chat.send_message(
                message,
                reply_markup=reply_markup
            )
        
        return CandidateStates.SCHEDULE_INTERVIEW
    
    # Handle interview day selection
    elif query.data.startswith("interview_day_"):
        selected_day = query.data.replace("interview_day_", "")
        context.user_data["interview_day"] = selected_day
        
        # Show time selection buttons
        message = f"Вы выбрали день: {selected_day}\n\nТеперь выберите предпочтительное время:"
        keyboard = [
            [InlineKeyboardButton("10:00 - 12:00", callback_data="interview_time_10:00 - 12:00")],
            [InlineKeyboardButton("12:00 - 14:00", callback_data="interview_time_12:00 - 14:00")],
            [InlineKeyboardButton("14:00 - 16:00", callback_data="interview_time_14:00 - 16:00")],
            [InlineKeyboardButton("16:00 - 18:00", callback_data="interview_time_16:00 - 18:00")],
            [InlineKeyboardButton("⬅️ Назад к выбору дня", callback_data="schedule_interview")],
            [InlineKeyboardButton("⬅️ Вернуться в главное меню", callback_data="back_to_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        try:
            await query.edit_message_text(
                message,
                reply_markup=reply_markup
            )
        except Exception as e:
            logger.error(f"Error editing message: {e}")
            await update.effective_chat.send_message(
                message,
                reply_markup=reply_markup
            )
        
        return CandidateStates.SCHEDULE_INTERVIEW
    
    # Handle interview time selection
    elif query.data.startswith("interview_time_"):
        selected_time = query.data.replace("interview_time_", "")
        selected_day = context.user_data.get("interview_day", "Не указан")
        
        # Save to context temporarily
        context.user_data["interview_time"] = selected_time
        
        # Show confirmation
        message = (
            f"Вы выбрали:\n\n"
            f"День: {selected_day}\n"
            f"Время: {selected_time}\n\n"
            f"Подтвердите запрос на собеседование:"
        )
        keyboard = [
            [InlineKeyboardButton("✅ Подтвердить", callback_data="confirm_interview_request")],
            [InlineKeyboardButton("⬅️ Изменить время", callback_data="interview_day_" + selected_day)],
            [InlineKeyboardButton("⬅️ Изменить день", callback_data="schedule_interview")],
            [InlineKeyboardButton("⬅️ Вернуться в главное меню", callback_data="back_to_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        try:
            await query.edit_message_text(
                message,
                reply_markup=reply_markup
            )
        except Exception as e:
            logger.error(f"Error editing message: {e}")
            await update.effective_chat.send_message(
                message,
                reply_markup=reply_markup
            )
        
        return CandidateStates.SCHEDULE_INTERVIEW
    
    # Handle interview request confirmation
    elif query.data == "confirm_interview_request":
        user_id = update.effective_user.id
        selected_day = context.user_data.get("interview_day", "Не указан")
        selected_time = context.user_data.get("interview_time", "Не указано")
        
        # Import handle_interview_request function from candidate_bot
        from candidate_bot import handle_interview_request
        
        # Submit interview request and send notification to recruiter
        await handle_interview_request(user_id, selected_day, selected_time)
        
        # Show confirmation message
        message = (
            "✅ Запрос на собеседование успешно отправлен!\n\n"
            f"День: {selected_day}\n"
            f"Время: {selected_time}\n\n"
            "Рекрутер рассмотрит ваш запрос и свяжется с вами. "
            "Вы получите уведомление, когда запрос будет обработан."
        )
        keyboard = [
            [InlineKeyboardButton("⬅️ Вернуться в главное меню", callback_data="back_to_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        try:
            await query.edit_message_text(
                message,
                reply_markup=reply_markup
            )
        except Exception as e:
            logger.error(f"Error editing message: {e}")
            await update.effective_chat.send_message(
                message,
                reply_markup=reply_markup
            )
        
        # Clear interview scheduling data
        if "interview_day" in context.user_data:
            del context.user_data["interview_day"]
        if "interview_time" in context.user_data:
            del context.user_data["interview_time"]
        if "scheduling_interview" in context.user_data:
            del context.user_data["scheduling_interview"]
        
        return CandidateStates.MAIN_MENU
    
    # Back to menu from any section
    elif query.data == "back_to_menu":
        # Вместо удаления сообщения, просто редактируем его
        return await send_main_menu(update, context, edit=True)
    
    # Default - return to main menu
    return await send_main_menu(update, context, edit=True)
