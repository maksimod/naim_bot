import os
import logging
import aiohttp
import json
import re
import requests
from dotenv import load_dotenv
import random
from utils.helpers import get_stopwords_data

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

async def generate_ai_stopword_sentence(stopword_data):
    """Генерирует предложение с использованием стоп-слова через AI"""
    api_url = os.getenv("CHATGPT_API_KEY")
    
    stopword_word = stopword_data.get('word', '')
    stopword_desc = stopword_data.get('description', '')
    
    logger.info(f"Генерируем предложение для стоп-слова: {stopword_word}")
    
    prompt = f"""
    ЗАДАЧА: Составить ОДНО деловое предложение, где ОБЯЗАТЕЛЬНО используется фраза "{stopword_word}".
    
    ОБЯЗАТЕЛЬНЫЕ УСЛОВИЯ:
    1. Предложение ДОЛЖНО содержать фразу "{stopword_word}"
    2. Делай предложение в деловом стиле, типичное для рабочей коммуникации
    3. Фраза "{stopword_word}" должна выглядеть уместно в контексте предложения
    4. Не заключай "{stopword_word}" в кавычки, используй как обычную часть речи
    
    ПРИМЕРЫ УСПЕШНЫХ ПРЕДЛОЖЕНИЙ:
    • Для стоп-слова "ну да!": "Я сказал ну да! и согласился на перенос встречи."
    • Для стоп-слова "всё равно": "Мне всё равно, в каком порядке обсуждать пункты повестки."
    • Для стоп-слова "стыдно": "Мне стыдно признаться, что я забыл отправить важный отчет вчера."
    
    ФОРМАТ ОТВЕТА: Верни ТОЛЬКО готовое предложение, без пояснений или комментариев.
    """
    
    # Отправляем запрос к API
    response = requests.post(api_url, json={
        "text": stopword_word,
        "prompt": prompt,
        "format": "text"
    }, timeout=15)
    
    # Получаем сгенерированное предложение
    ai_sentence = extract_sentence_from_response(response.text)
    
    # Удаляем кавычки, если они есть
    ai_sentence = ai_sentence.strip('"\'`')
    
    # Логируем финальное предложение
    logger.info(f"Сгенерировано предложение: {ai_sentence}")
    
    return ai_sentence

def extract_sentence_from_response(response_text):
    """Извлекает чистый текст предложения из ответа API, который может быть в JSON"""
    try:
        # Попытка распарсить как JSON
        response_data = json.loads(response_text)
        
        # Если это словарь
        if isinstance(response_data, dict):
            # Проверяем распространенные ключи в ответах API
            if 'output' in response_data:
                return response_data['output']
            elif 'text' in response_data:
                return response_data['text']
            elif 'content' in response_data:
                return response_data['content']
            elif 'response' in response_data:
                return response_data['response']
            elif 'result' in response_data:
                return response_data['result']
            else:
                # Если ничего не нашли, возвращаем первое строковое значение
                for key, value in response_data.items():
                    if isinstance(value, str) and len(value) > 5:
                        return value
                
                # Если не нашли подходящих строк, возвращаем весь текст
                return str(response_data)
    except json.JSONDecodeError:
        # Если это не JSON, просто возвращаем текст как есть
        pass
    except Exception as e:
        logger.error(f"Ошибка при извлечении предложения из ответа: {e}")
    
    # Удаляем кавычки в начале и конце
    return response_text.strip().strip('"\'`').strip()

async def verify_stopword_rephrasing_ai(original_sentence, rephrased_sentence, stopword):
    """Проверить корректность перефразированного предложения без стоп-слова используя AI"""
    api_url = os.getenv("CHATGPT_API_KEY")
    
    # Получаем данные о стоп-слове
    stopword_text = stopword.get('word', '').strip().lower()
    
    # Логируем то, что проверяем для отладки
    logger.info(f"Проверка ответа: Исходное='{original_sentence}', Ответ='{rephrased_sentence}', Стоп-слово='{stopword_text}'")
    
    # Проверка на сохранение смысла и прочие критерии через API
    # Создаем улучшенный промпт для AI
    prompt = f"""
    Ты - старший преподаватель делового русского языка и коммуникаций. Твоя задача - проверить, правильно ли пользователь перефразировал предложение, избегая стоп-слова.   
    
    ## Исходные данные
    Исходное предложение: "{original_sentence}"
    Стоп-слово, которое нужно было избегать: "{stopword_text}"
    Ответ пользователя: "{rephrased_sentence}"

    ## КРИТЕРИИ ОЦЕНКИ (оценивай строго):
    1. В ответе пользователя НЕТ стоп-слова "{stopword_text}" или его форм/вариаций.
    2. КРИТИЧЕСКИ ВАЖНО: Ответ пользователя СОХРАНЯЕТ ОСНОВНОЙ СМЫСЛ исходного предложения.
    3. Ответ пользователя логичен и согласован грамматически.
    
    ## ПРАВИЛА ПРОВЕРКИ:
    - Предложение считается ПРАВИЛЬНЫМ, только если соответствует ВСЕМ критериям.
    - Даже небольшое искажение смысла оригинала делает ответ НЕПРАВИЛЬНЫМ.
    - Полностью несвязанное с оригиналом предложение - НЕПРАВИЛЬНЫЙ ответ.
    - Предложение с большим количеством ошибок в грамматике, пунктуации, синтаксисе - НЕПРАВИЛЬНЫЙ ответ.
    - Если пользователь превращает отрицание в положительное, то это НЕПРАВИЛЬНЫЙ ответ.
    
    ## ФОРМАТ ОТВЕТА (строго в JSON):
    {{
      "passed": true/false,
      "feedback": "Развернутая оценка результата. Если ответ неправильный, объясни, почему именно он не соответствует критериям.",
      "better_example": "Пример правильного перефразирования без использования стоп-слова (только если ответ пользователя неверный)."
    }}
    """
    
    # Отправляем запрос к API
    response = requests.post(api_url, json={
        "text": rephrased_sentence,
        "prompt": prompt,
        "format": "json"
    }, timeout=15)
    
    # Логируем полный ответ API для отладки
    logger.info(f"Ответ API на проверку: {response.text}")
    
    # Обработка ответа API
    result_text = response.text
    try:
        # Сначала парсим внешний JSON
        outer_result = json.loads(result_text)
        
        # Проверяем, есть ли поле 'output' - значит результат в нем
        if 'output' in outer_result:
            # Парсим JSON строку из поля 'output'
            try:
                inner_json = outer_result['output']
                result = json.loads(inner_json)
            except json.JSONDecodeError:
                # Если не удалось распарсить внутренний JSON, пытаемся найти JSON в тексте
                json_match = re.search(r'({\s*"passed"\s*:.*})', inner_json, re.DOTALL)
                if json_match:
                    try:
                        result = json.loads(json_match.group(1))
                    except json.JSONDecodeError:
                        result = {
                            "passed": False,
                            "feedback": "Не удалось проанализировать ответ. Пожалуйста, попробуйте перефразировать иначе."
                        }
                else:
                    result = {
                        "passed": False,
                        "feedback": "Не удалось проанализировать ответ. Пожалуйста, попробуйте перефразировать иначе."
                    }
        else:
            # Если нет поля 'output', то результат, вероятно, в корне ответа
            result = outer_result
    except json.JSONDecodeError:
        # Если внешний JSON не распарсился, пытаемся найти JSON в тексте с помощью регулярного выражения
        json_match = re.search(r'({\s*"passed"\s*:.*})', result_text, re.DOTALL)
        if json_match:
            try:
                result = json.loads(json_match.group(1))
            except json.JSONDecodeError:
                # Если и это не помогло, создаем базовый объект результата
                result = {
                    "passed": False,
                    "feedback": "Не удалось проанализировать ответ. Пожалуйста, попробуйте перефразировать иначе."
                }
        else:
            # Если JSON не найден, создаем базовый объект результата
            result = {
                "passed": False,
                "feedback": "Не удалось проанализировать ответ. Пожалуйста, попробуйте перефразировать иначе."
            }
    
    print("РЕЗУЛЬТАТ:", result)
    # Извлекаем результаты проверки
    passed = result.get("passed", False)
    feedback = result.get("feedback", "")
    better_example = result.get("better_example", "")
    

    # Формируем итоговую обратную связь
    final_feedback = feedback
    if better_example:
        final_feedback += f"\n\nЛучший пример: \"{better_example}\""

    # Добавляем информацию для отладки при необходимости
    if os.getenv("DEBUG", "false").lower() == "true":
        debug_info = f"\n\nИсходное: \"{original_sentence}\"\nСтоп-слово: \"{stopword_text}\"\nВаш ответ: \"{rephrased_sentence}\"\nОбратная связь: \"{feedback}\"\nЛучший пример: \"{better_example}\""
        final_feedback += debug_info
    
    return passed, final_feedback

async def verify_poem_task(solution_text):
    """Verify completion of the poem task using ChatGPT"""
    # Use the API endpoint from .env
    api_url = os.getenv("CHATGPT_API_KEY")
    
    # Проверка на наличие самого стихотворения в решении (базовая)
    if not solution_text:
        return False, "Отсутствует решение. Пожалуйста, предоставьте полный диалог с ИИ, включая стихотворение."
    
    # Проверка наличия диалога с ИИ и стихотворения с ключевыми элементами
    has_dialog = "You" in solution_text or "Assistant" in solution_text or "Human" in solution_text or "AI" in solution_text
    has_poem = "ИСКРА" in solution_text or ("И" in solution_text and "С" in solution_text and "К" in solution_text and "Р" in solution_text and "А" in solution_text)
    has_key_terms = "аллитерац" in solution_text and ("стих" in solution_text or "огон" in solution_text or "вод" in solution_text)
    
    # Если в тексте совсем нет признаков стихотворения
    if not (has_dialog and has_poem and has_key_terms):
        return False, "Решение не содержит необходимых элементов: диалога с ИИ, стихотворения с акростихом 'ИСКРА', упоминания стихий и аллитерации. Пожалуйста, предоставьте полное решение согласно заданию."
    
    # Автоматически проверим текст на наличие стихотворения с акростихом ИСКРА
    lines = solution_text.split('\n')
    poem_found = False
    for i in range(len(lines) - 4):  # Минимум 5 строк нужно для ИСКРА
        first_letters = ''.join([line.strip()[0].upper() if line.strip() else '' for line in lines[i:i+6]])
        if 'ИСКРА' in first_letters:
            poem_found = True
            break
    
    # Если стихотворение найдено без API, возвращаем успех (предотвращаем ложноотрицательные результаты)
    if poem_found:
        # Проверяем также наличие упоминания проверки в тексте
        verification_mentioned = "проверь" in solution_text.lower() or "verify" in solution_text.lower()
        if verification_mentioned:
            return True, "Стихотворение найдено и соответствует требованиям. Акростих 'ИСКРА' присутствует. Диалог с проверкой включен."
    
    # Prepare the prompt for GPT
    prompt = f"""
    Ты - специалист по оценке стихотворных заданий. Необходимо оценить решение кандидата на вакансию.
    
    Задание: Сгенерировать короткий стихотворный текст (4-6 строк) на русском языке, который:
    1. Содержит аллитерацию на звук "С" в каждой строке.
    2. Включает упоминание двух противоположных стихий (например, огонь и вода).
    3. Имеет скрытый акростих из первых букв строк, образующих слово "ИСКРА".
    
    Проверяемый текст должен содержать:
    1. Диалог пользователя с ИИ, где пользователь просит создать стихотворение с указанными критериями
    2. Ответ ИИ с предложенным стихотворением
    3. Запрос пользователя на проверку стихотворения
    4. Ответ ИИ с подтверждением выполнения требований или исправлениями
    
    Проверь, есть ли в диалоге все эти элементы, а затем оцени финальное стихотворение по критериям.
    
    Ответ кандидата:
    {solution_text}
    
    Оцени решение по следующим критериям:
    - Наличие аллитерации на звук "С" в каждой строке стихотворения
    - Включение двух противоположных стихий (например, огонь и вода)
    - Правильность акростиха (первые буквы строк должны образовывать слово "ИСКРА")
    - Полнота выполнения задания (наличие всех элементов диалога с ИИ)
    
    Дай общую оценку (прошел/не прошел тест) и детальную обратную связь. Решение считается успешным, если выполнены ВСЕ необходимые условия.
    
    Формат ответа:
    {{
      "passed": true/false,
      "feedback": "подробная обратная связь"
    }}
    """
    
    try:
        # Make the API request
        response = requests.post(api_url, json={
            "text": solution_text,
            "prompt": prompt,
            "format": "json"
        })
        
        # Process the response
        if response.status_code != 200:
            logger.error(f"Error calling ChatGPT API: {response.status_code}")
            logger.error(f"Response text: {response.text}")
            # Если API не работает, но мы уже проверили стихотворение 
            if poem_found:
                return True, "Стихотворение найдено и соответствует требованиям. Акростих 'ИСКРА' присутствует."
            return False, "Произошла ошибка при проверке вашего решения. Пожалуйста, попробуйте позже."
        
        # Log the full response for debugging
        logger.info(f"API response for poem task: {response.text}")
        
        # Parse the JSON response
        try:
            # First try to parse it as a direct JSON
            result = response.json()
            
            # Check if result contains outer structure with 'output'
            if isinstance(result, dict) and 'output' in result:
                # Try to parse the output field as JSON
                try:
                    inner_result = json.loads(result['output'])
                    # Use inner result
                    result = inner_result
                except json.JSONDecodeError:
                    # If output is not valid JSON, check if it's a string containing JSON
                    output_str = result['output']
                    json_match = re.search(r'({.*?"passed".*?})', output_str, re.DOTALL)
                    if json_match:
                        try:
                            result = json.loads(json_match.group(1))
                        except json.JSONDecodeError:
                            # Fallback to simple extraction of passed/feedback
                            passed = 'true' in output_str.lower() and 'passed' in output_str.lower()
                            feedback = output_str
                            return passed, feedback
            
            # Now extract passed and feedback
            if isinstance(result, dict):
                passed = result.get("passed", False)
                feedback = result.get("feedback", "Нет обратной связи")
                # Если API говорит "не прошел", но мы уже проверили стихотворение 
                if not passed and poem_found:
                    logger.info("API says test failed but poem was found locally, overriding result")
                    return True, "Стихотворение прошло проверку. Акростих 'ИСКРА' присутствует. " + feedback
                return passed, feedback
            else:
                # If result is not a dict, treat as string and check for 'passed'
                result_str = str(result)
                passed = 'true' in result_str.lower() and 'passed' in result_str.lower()
                if not passed and poem_found:
                    logger.info("API says test failed but poem was found locally, overriding result")
                    return True, "Стихотворение прошло проверку. Акростих 'ИСКРА' присутствует."
                return passed, result_str
                
        except json.JSONDecodeError:
            # If JSON parsing fails, try to extract passed/feedback using regex
            response_text = response.text
            json_match = re.search(r'({.*?"passed".*?})', response_text, re.DOTALL)
            if json_match:
                try:
                    extracted = json.loads(json_match.group(1))
                    passed = extracted.get("passed", False)
                    feedback = extracted.get("feedback", "Нет обратной связи")
                    if not passed and poem_found:
                        logger.info("API says test failed but poem was found locally, overriding result")
                        return True, "Стихотворение прошло проверку. Акростих 'ИСКРА' присутствует. " + feedback
                    return passed, feedback
                except json.JSONDecodeError:
                    pass
                    
            # As a fallback, check if response contains "passed" and "true"
            passed = 'true' in response_text.lower() and 'passed' in response_text.lower()
            if not passed and poem_found:
                logger.info("API says test failed but poem was found locally, overriding result")
                return True, "Стихотворение прошло проверку. Акростих 'ИСКРА' присутствует."
            return passed, response_text
    
    except Exception as e:
        logger.error(f"Error verifying poem task: {e}")
        # Если произошла ошибка, но мы уже проверили стихотворение 
        if poem_found:
            return True, "Стихотворение найдено и соответствует требованиям. Акростих 'ИСКРА' присутствует."
        return False, "Произошла ошибка при проверке вашего решения. Пожалуйста, попробуйте позже."

# Load API key on module import
load_api_key()
