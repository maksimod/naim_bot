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
        response = requests.post(api_url, json={
            "text": solution_text,
            "prompt": prompt,
            "format": "json"
        })
        
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
            # If JSON parsing fails, return a default message
            logger.error(f"Failed to parse API response as JSON: {response.text}")
            return False, "Не удалось проверить ваше решение. Пожалуйста, попробуйте позже."
    
    except Exception as e:
        logger.error(f"Error verifying solution: {e}")
        return False, "Произошла ошибка при проверке вашего решения. Пожалуйста, попробуйте позже."

async def verify_stopword_rephrasing(original_sentence, rephrased_sentence, stopword):
    """Проверить корректность перефразированного предложения без стоп-слова"""
    try:
        # Получаем слово из словаря стоп-слова
        stopword_text = stopword.get("word", "").lower().strip()
        stopword_desc = stopword.get("description", "").strip()
        stopword_repl = stopword.get("replacement", "").strip()
        
        logger.info(f"Проверка ответа: оригинал = '{original_sentence}', ответ = '{rephrased_sentence}', стоп-слово = '{stopword_text}'")
        
        # Если ответ пустой
        if not rephrased_sentence or not rephrased_sentence.strip():
            return False, "Ответ не может быть пустым. Пожалуйста, перефразируйте предложение без использования стоп-слова."
        
        # Первичная проверка на наличие стоп-слова
        if stopword_text and stopword_text.lower() in rephrased_sentence.lower():
            return False, f"Ваш ответ содержит стоп-слово '{stopword_text}'. Попробуйте перефразировать предложение без использования этого слова."
        
        # Проверка на оскорбления и ненормативную лексику
        profanity_words = ["блять", "нахуй", "хуй", "ебать", "сука", "пизда", "долбоеб", "хуйня", "пиздец"]
        for word in profanity_words:
            if word in rephrased_sentence.lower():
                return False, "Ваш ответ содержит ненормативную лексику. Пожалуйста, используйте деловой стиль общения."
        
        # Используем API для более сложной проверки
        try:
            api_url = os.getenv("CHATGPT_API_KEY")
            if api_url:
                # Подготовка данных для запроса
                prompt = f"""
                Ты - специалист по деловой коммуникации, проверяющий умение перефразировать предложения, избегая стоп-слов.
                
                Исходное предложение: "{original_sentence}"
                В этом предложении стоп-слово: "{stopword_text}"
                
                Перефразированный вариант: "{rephrased_sentence}"
                
                Оцени, качественно ли перефразировано предложение:
                1. Не содержит ли перефразированное предложение указанное стоп-слово
                2. Сохранен ли смысл исходного предложения
                3. Соответствует ли ответ деловому стилю общения
                
                Ответ дай в формате JSON:
                {{
                  "passed": true/false,
                  "feedback": "конкретная обратная связь что хорошо/плохо и как можно улучшить",
                  "better_example": "пример лучшего перефразирования, если ответ неправильный"
                }}
                """
                
                # Отправляем запрос к API
                response = requests.post(api_url, json={
                    "text": rephrased_sentence,
                    "prompt": prompt,
                    "format": "json"
                }, timeout=10)
                
                # Обрабатываем ответ
                if response.status_code == 200:
                    try:
                        result = response.json()
                        passed = result.get("passed", False)
                        feedback = result.get("feedback", "")
                        better_example = result.get("better_example", "")
                        
                        # Формируем полную обратную связь
                        if better_example and not passed:
                            feedback = f"{feedback}\n\nПример лучшего варианта: \"{better_example}\""
                        
                        return passed, feedback
                    except:
                        # Если не удалось распарсить JSON, просто проверяем основное правило
                        pass
        except:
            # При ошибке API продолжаем с базовой проверкой
            pass
        
        # Если AI проверка не сработала, используем базовые правила
        # Проверка на наличие стоп-слова - это главное правило
        if stopword_text and stopword_text.lower() in rephrased_sentence.lower():
            return False, f"Ваш ответ содержит стоп-слово '{stopword_text}'. Попробуйте перефразировать предложение без использования этого слова."
        
        # По умолчанию, если прошли все проверки, считаем ответ правильным
        feedback = f"Отлично! Вы успешно перефразировали предложение, избежав использования стоп-слова '{stopword_text}'."
        
        # Добавляем рекомендованную замену, если она есть
        if stopword_repl:
            feedback += f" Рекомендуемый вариант замены: '{stopword_repl}'."
            
        return True, feedback
    
    except Exception as e:
        logger.error(f"Ошибка при проверке перефразирования: {e}")
        # При любой ошибке позволяем продолжить тест
        return True, "Ответ принят. Продолжайте тест."

async def generate_ai_stopword_sentence(stopword_data):
    """Генерирует предложение с использованием стоп-слова через AI"""
    # Получаем API URL из env
    api_url = os.getenv("CHATGPT_API_KEY")
    
    # Составляем список стоп-слов для промпта
    all_stopwords = get_stopwords_data()
    
    # Стоп-слово, для которого генерируем предложение
    stopword_word = stopword_data.get('word', '')
    stopword_desc = stopword_data.get('description', '')
    
    logger.info(f"Генерируем предложение для стоп-слова: {stopword_word}")
    
    # Подготовка промпта для AI - максимально упрощенный
    prompt = f"""
    Твоя задача - сгенерировать естественное предложение, в котором обязательно используется стоп-слово "{stopword_word}".
    
    ПРАВИЛА:
    1. Предложение должно быть реалистичным, как в обычном разговоре между сотрудниками компании
    2. Предложение ДОЛЖНО содержать ТОЧНО стоп-слово "{stopword_word}" в ИСХОДНОЙ форме 
    3. НЕ используй кавычки в начале и конце предложения
    4. НЕ начинай предложение с фраз "например", "коллега сказал", "мне нужно" и т.п.
    5. Предложение должно звучать естественно, как прямая речь
    
    Примеры хороших предложений:
    - "Какая разница, во сколько начинается собрание?" (для стоп-слова "Какая разница")
    - "Я не хочу помогать новому сотруднику с отчетом." (для стоп-слова "Не хочу")
    - "Мне надоело постоянно исправлять твои ошибки." (для стоп-слова "Надоело")
    
    ВАЖНО: Верни ТОЛЬКО текст предложения без каких-либо пояснений, кавычек или JSON.
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

# Load API key on module import
load_api_key()
