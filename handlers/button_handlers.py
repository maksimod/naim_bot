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
        await query.message.reply_text(content)
        
        # Offer to take the test
        keyboard = [[InlineKeyboardButton("Пройти тест", callback_data="where_to_start_test")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text(
            "Чтобы разблокировать следующий этап, пройдите тест.",
            reply_markup=reply_markup
        )
        return CandidateStates.WHERE_TO_START
    
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
        
        # Return to main menu
        return await send_main_menu(update, context, edit=True)
    
    # Default - return to main menu
    return await send_main_menu(update, context, edit=True)
