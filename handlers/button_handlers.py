import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import database as db
from config import CandidateStates
from utils.helpers import load_text_content, load_test_questions
from handlers.candidate_handlers import send_main_menu, send_test_question

logger = logging.getLogger(__name__)

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
    elif query.data == "preparation_materials" and "preparation_materials" in unlocked_stages:
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
    
    # Back to menu from any section
    elif query.data == "back_to_menu":
        # Вместо удаления сообщения, просто редактируем его
        return await send_main_menu(update, context, edit=True)
    
    # Default - return to main menu
    return await send_main_menu(update, context, edit=True)
