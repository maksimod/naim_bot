import os
import logging
import aiohttp
import json
import re
import requests
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

async def verify_test_completion(solution_text):
    """Verify completion of the test using ChatGPT"""
    try:
        # Use the API endpoint from .env
        api_url = os.getenv("CHATGPT_API_KEY")
        
        # Prepare the prompt for GPT
        prompt = f"""
        Ты - специалист по оценке тестовых заданий. Необходимо оценить решение кандидата на вакансию.
        
        Задание: Разработать план действий для стартапа, планирующего запуск нового продукта на рынок.
        
        Ответ кандидата:
        {solution_text}
        
        Оцени решение по шкале от 1 до 10 по следующим критериям:
        - Полнота охвата всех аспектов запуска продукта (маркетинг, продажи, поддержка)
        - Реалистичность и практическая применимость плана
        - Учет возможных рисков и препятствий
        - Креативность и нестандартный подход
        - Четкость формулировок и структурированность
        
        Дай общую оценку (прошел/не прошел тест) и детальную обратную связь. Решение считается успешным, если получено не менее 7 баллов по каждому критерию.
        
        Формат ответа:
        {{
          "passed": true/false,
          "feedback": "подробная обратная связь"
        }}
        """
        
        # Make the API request
        response = requests.post(api_url, json={"prompt": prompt, "format": "json"})
        
        # Process the response
        if response.status_code != 200:
            logger.error(f"Error calling ChatGPT API: {response.status_code}")
            logger.error(f"Response text: {response.text}")
            # Default response if API call fails
            return False, "Не удалось проверить ваше решение. Пожалуйста, попробуйте позже."
        
        # Parse the JSON response
        try:
            result = response.json()
            passed = result.get("passed", False)
            feedback = result.get("feedback", "Нет обратной связи")
            return passed, feedback
        except json.JSONDecodeError:
            logger.error(f"Failed to parse API response as JSON: {response.text}")
            # Extract information from text response as fallback
            text = response.text
            passed = "прошел" in text.lower() or "успешн" in text.lower()
            return passed, text
        
    except Exception as e:
        logger.error(f"Error verifying test completion: {e}")
        return False, "Произошла ошибка при проверке вашего решения."

async def verify_stopword_rephrasing(original_sentence, rephrased_sentence, stopword):
    """Проверяет, правильно ли перефразировано предложение без использования стоп-слова"""
    try:
        # Используем API из .env
        api_url = os.getenv("CHATGPT_API_KEY")
        
        # Подготовка запроса для GPT
        prompt = f"""
        Ты - специалист по деловой коммуникации. Оцени, правильно ли перефразировано предложение.
        
        Исходное предложение: "{original_sentence}"
        
        Перефразированное предложение: "{rephrased_sentence}"
        
        Стоп-слово, которое нужно было исключить: "{stopword['word']}"
        
        Требования к успешному перефразированию:
        1. Стоп-слово полностью отсутствует в новом предложении
        2. Смысл сохранен
        3. Предложение грамматически корректно
        
        Формат ответа:
        {{
          "passed": true/false,
          "feedback": "краткая обратная связь"
        }}
        """
        
        # Делаем запрос к API
        response = requests.post(api_url, json={"prompt": prompt, "format": "json"})
        
        # Обрабатываем ответ
        if response.status_code != 200:
            logger.error(f"Ошибка при вызове ChatGPT API: {response.status_code}")
            logger.error(f"Текст ответа: {response.text}")
            # Ответ по умолчанию, если вызов API не удался
            return False, "Не удалось проверить ваш ответ. Пожалуйста, попробуйте еще раз."
        
        # Парсим JSON ответ
        try:
            result = response.json()
            passed = result.get("passed", False)
            feedback = result.get("feedback", "Нет обратной связи")
            return passed, feedback
        except json.JSONDecodeError:
            logger.error(f"Не удалось распарсить ответ API как JSON: {response.text}")
            # Извлекаем информацию из текстового ответа как запасной вариант
            text = response.text
            passed = "прошел" in text.lower() or "правильно" in text.lower() or "успешно" in text.lower()
            return passed, text
        
    except Exception as e:
        logger.error(f"Ошибка при проверке перефразирования: {e}")
        return False, "Произошла ошибка при проверке вашего ответа."

# Load API key on module import
load_api_key()
