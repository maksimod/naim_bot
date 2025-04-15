import os
import logging
import aiohttp
import json
import re
from dotenv import load_dotenv

load_dotenv()

# Default settings
DEFAULT_MODEL = "gpt-3.5-turbo-0125"
DEFAULT_TEMPERATURE = 0.7
DEFAULT_MAX_TOKENS = 1000

# Global variables
_api_key = None
_api_url = None

# Logger
logger = logging.getLogger(__name__)

def load_api_key():
    """Load API key or URL for the local API."""
    global _api_key, _api_url
    
    # Check environment variables
    api_key = os.getenv("CHATGPT_API_KEY")
    if api_key:
        if api_key.startswith("http://") or api_key.startswith("https://"):
            _api_url = api_key
            logger.info(f"Local API URL loaded from environment: {_api_url}")
            return True
        else:
            _api_key = api_key
            logger.info("OpenAI API key loaded from environment")
            return True
    
    logger.warning("API key/URL not found. Some features will be unavailable.")
    return False

async def call_openai_api(messages, 
                          model=DEFAULT_MODEL,
                          temperature=DEFAULT_TEMPERATURE,
                          max_tokens=DEFAULT_MAX_TOKENS,
                          language="ru"):
    """
    Call OpenAI API or local API to get a response from the model.
    
    Args:
        messages: List of message dicts for context
        model: OpenAI model name
        temperature: Generation temperature
        max_tokens: Maximum tokens
        language: Response language
    
    Returns:
        Response text or None on error
    """
    if not _api_key and not _api_url:
        if not load_api_key():
            logger.error("API key/URL not found. Cannot perform request.")
            return None
    
    # If using local API
    if _api_url:
        try:
            # Get last user message (or empty string)
            user_message = next((msg["content"] for msg in reversed(messages) if msg["role"] == "user"), "")
            
            # Get system message (instruction)
            system_message = next((msg["content"] for msg in messages if msg["role"] == "system"), "")
            
            # Configure request to local API
            data = {
                "text": user_message,
                "language": language,
                "prompt": system_message
            }
            
            headers = {
                "Content-Type": "application/json"
            }
            
            # Make sure endpoint ends with /chatgpt_translate
            endpoint = _api_url
            if not endpoint.endswith("/chatgpt_translate"):
                endpoint = f"{endpoint}/chatgpt_translate"
            
            async with aiohttp.ClientSession() as session:
                async with session.post(endpoint, 
                                       headers=headers, 
                                       json=data) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"Local API error ({response.status}): {error_text}")
                        return None
                    
                    # Get response
                    response_text = await response.text()
                    
                    try:
                        # Try to parse JSON
                        result = json.loads(response_text)
                        
                        # If response is a dictionary
                        if isinstance(result, dict):
                            # Check different field variants
                            if "output" in result:
                                return decode_unicode_string(result["output"])
                            elif "response" in result:
                                return decode_unicode_string(result["response"])
                            elif "text" in result:
                                return decode_unicode_string(result["text"])
                            elif "content" in result:
                                return decode_unicode_string(result["content"])
                            elif "translated_text" in result:
                                return decode_unicode_string(result["translated_text"])
                            elif "translation" in result:
                                return decode_unicode_string(result["translation"])
                            elif "success" in result and "output" in result:
                                return decode_unicode_string(result["output"])
                            else:
                                # If no known fields, return whole JSON as string
                                # Try to find any text field
                                for key, value in result.items():
                                    if isinstance(value, str) and len(value) > 5:
                                        return decode_unicode_string(value)
                                return decode_unicode_string(str(result))
                        elif isinstance(result, str):
                            return decode_unicode_string(result)
                        else:
                            return decode_unicode_string(str(result))
                    except json.JSONDecodeError:
                        # If JSON parsing failed, return text as is
                        return decode_unicode_string(response_text)
                        
        except Exception as e:
            logger.error(f"Error calling local API: {e}")
            return None
    
    # If using official OpenAI API
    else:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {_api_key}"
        }
        
        data = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post("https://api.openai.com/v1/chat/completions", 
                                       headers=headers, 
                                       json=data) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"OpenAI API error ({response.status}): {error_text}")
                        return None
                    
                    result = await response.json()
                    return result["choices"][0]["message"]["content"]
        except Exception as e:
            logger.error(f"Error calling OpenAI API: {e}")
            return None

def decode_unicode_string(text):
    """
    Decode a string containing Unicode sequences like \\uXXXX.
    
    Args:
        text: String to decode
    
    Returns:
        Decoded string
    """
    if not isinstance(text, str):
        return text
    
    # If string doesn't contain Unicode sequences, return as is
    if '\\u' not in text:
        return text
    
    try:
        # Try to decode through JSON
        decoded = json.loads(f'"{text}"')
        return decoded
    except json.JSONDecodeError:
        # If failed, use regex
        try:
            pattern = '\\\\u([0-9a-fA-F]{4})'
            result = re.sub(pattern, lambda m: chr(int(m.group(1), 16)), text)
            return result
        except Exception as e:
            logger.warning(f"Failed to decode Unicode: {e}")
            return text

async def verify_test_completion(user_solution):
    """
    Verify if the user has correctly completed the test using ChatGPT.
    
    Args:
        user_solution: The solution provided by the user
    
    Returns:
        Tuple (passed, feedback) where passed is a boolean and feedback is a string
    """
    # Prepare system message
    system_message = {
        "role": "system",
        "content": """
        Ты - проверяющая система для оценки решений. Твоя задача - оценить, правильно ли выполнено задание и дать подробную обратную связь.
        
        Исходное задание:
        «Сгенерируйте короткий стихотворный текст (4-6 строк) на русском языке, который:
        1. Содержит аллитерацию на звук "С" в каждой строке.
        2. Включает упоминание двух противоположных стихий (например, огонь и вода).
        3. Имеет скрытый акростих из первых букв строк, образующих слово "ИСКРА".»
        
        Твоя задача:
        1. Проверить, содержит ли решение пользователя диалог с нейросетью (ChatGPT, Claude, и т.д.)
        2. Проверить, был ли сгенерирован стихотворный текст из 4-6 строк
        3. Проверить, есть ли аллитерация на "С" в каждой строке
        4. Проверить, упоминаются ли две противоположные стихии
        5. Проверить, образуют ли первые буквы каждой строки слово "ИСКРА"
        
        Ответь в формате:
        1. Сначала четко укажи: "ПРОВЕРКА: ТЕСТ [ПРОЙДЕН/НЕ ПРОЙДЕН]"
        2. Затем перечисли все выполненные и невыполненные условия с пояснениями
        3. Закончи общей обратной связью и рекомендациями
        
        Критерии оценки:
        - Тест считается пройденным, если выполнены все 5 условий
        - Если хотя бы одно условие не выполнено, тест считается не пройденным
        """
    }
    
    # User message with the solution
    user_message = {
        "role": "user",
        "content": f"Вот мое решение задания:\n\n{user_solution}"
    }
    
    # Call OpenAI API
    messages = [system_message, user_message]
    response = await call_openai_api(messages)
    
    if not response:
        return False, "Не удалось проверить решение. Пожалуйста, попробуйте позже."
    
    # Determine if the test is passed based on the response
    passed = "ТЕСТ ПРОЙДЕН" in response.upper()
    
    return passed, response

# Load API key on module import
load_api_key()
