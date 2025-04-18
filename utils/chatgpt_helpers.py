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
    try:
        # Получаем API URL из env
        api_url = os.getenv("CHATGPT_API_KEY")
        
        if not api_url:
            logger.error("CHATGPT_API_KEY не найден, невозможно использовать AI")
            raise Exception("API ключ не найден")
        
        # Составляем список стоп-слов для промпта
        all_stopwords = get_stopwords_data()
        stopwords_list = "\n".join([f"- {sw.get('word', '')}: {sw.get('description', '')}" for sw in all_stopwords])
        
        # Подготовка промпта для AI
        prompt = f"""
        Ты - злой подрывник компании, тебя поставили в конкурирующую компанию, чтобы ты разрушил дух рабочих.
        Вот стоп-слова этой компании:
        {stopwords_list}
        
        Твоя задача - сгенерировать реалистичное предложение, в котором используется стоп-слово: "{stopword_data.get('word', '')}".
        
        Важные требования:
        1. Предложение должно быть реалистичным, которое может сказать сотрудник в разговоре
        2. Предложение ОБЯЗАТЕЛЬНО должно содержать стоп-слово "{stopword_data.get('word', '')}" в точно такой же форме
        3. Предложение должно быть прямой речью, как в живом диалоге
        4. НЕ используй сложные конструкции с вложенными цитатами
        5. НЕ начинай предложение с фраз типа "Мне нужно..." или "Коллега сказал..."
        
        Примеры хороших предложений:
        - "Какая тебе разница, когда я закончу этот отчет?"
        - "Ты можешь мне помочь с этой задачей?"
        - "Наверное, мы не успеем закончить проект в срок."
        
        Выдай ТОЛЬКО САМО ПРЕДЛОЖЕНИЕ без кавычек, объяснений или дополнительного контекста.
        """
        
        # Отправляем запрос к API
        response = requests.post(api_url, json={
            "text": stopword_data.get('word', ''),
            "prompt": prompt,
            "format": "text"
        }, timeout=15)
        
        # Обрабатываем ответ
        if response.status_code != 200:
            logger.error(f"Ошибка при генерации предложения со стоп-словом: {response.status_code}, {response.text}")
            # Повторяем запрос с упрощенным промптом
            retry_prompt = f"""
            Сгенерируй одно короткое предложение, которое обязательно содержит фразу "{stopword_data.get('word', '')}".
            Например: "Какая тебе разница, во сколько я приду на работу?" для стоп-слова "Какая тебе разница".
            Выдай только предложение, без кавычек и пояснений.
            """
            retry_response = requests.post(api_url, json={
                "text": "Создай предложение",
                "prompt": retry_prompt,
                "format": "text"
            }, timeout=15)
            
            if retry_response.status_code != 200:
                raise Exception(f"Повторная ошибка API: {retry_response.status_code}")
            
            return extract_sentence_from_response(retry_response.text)
        
        # Получаем сгенерированное предложение
        ai_sentence = extract_sentence_from_response(response.text)
        
        # Проверяем, что предложение содержит стоп-слово
        if stopword_data.get('word', '').lower() not in ai_sentence.lower():
            logger.warning(f"AI не включил стоп-слово '{stopword_data.get('word', '')}' в предложение, повторная попытка")
            
            # Более строгий промпт для повторной попытки
            prompt_retry = f"""
            Создай ОДНО КОРОТКОЕ предложение, которое ОБЯЗАТЕЛЬНО включает стоп-слово "{stopword_data.get('word', '')}" в точности как указано.
            
            Примеры:
            - Стоп-слово "Какая разница": "Какая разница, кто выполнит эту работу?"
            - Стоп-слово "Помоги": "Помоги мне с этим отчетом, пожалуйста."
            
            Важно: предложение должно быть реалистичным, как в обычном разговоре между коллегами.
            Важно: предложение ДОЛЖНО содержать фразу "{stopword_data.get('word', '')}" в точности.
            
            Выдай только само предложение без кавычек и объяснений.
            """
            
            # Повторная попытка с более строгим промптом
            retry_response = requests.post(api_url, json={
                "text": "Создай предложение со стоп-словом",
                "prompt": prompt_retry,
                "format": "text"
            }, timeout=15)
            
            if retry_response.status_code == 200:
                return extract_sentence_from_response(retry_response.text)
            else:
                # Если и повторный запрос не удался, делаем еще одну попытку с простейшим промптом
                final_prompt = f'Напиши одно предложение со словом "{stopword_data.get("word", "")}".'
                final_response = requests.post(api_url, json={
                    "text": "Последняя попытка",
                    "prompt": final_prompt,
                    "format": "text"
                }, timeout=10)
                
                return extract_sentence_from_response(final_response.text)
        
        # Возвращаем предложение без дополнительного форматирования
        return ai_sentence
        
    except Exception as e:
        logger.error(f"Ошибка при генерации предложения через AI: {e}")
        # Последняя попытка с самым простым запросом
        try:
            simple_prompt = f'Напиши предложение с фразой "{stopword_data.get("word", "")}".'
            last_response = requests.post(api_url, json={
                "text": "SOS запрос",
                "prompt": simple_prompt,
                "format": "text"
            }, timeout=10)
            
            return extract_sentence_from_response(last_response.text)
        except:
            # В случае полного отказа, просто возвращаем стоп-слово
            return stopword_data.get('word', '')

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
    try:
        api_url = os.getenv("CHATGPT_API_KEY")
        if not api_url:
            logger.error("CHATGPT_API_KEY не найден")
            raise Exception("API ключ не найден")
        
        # Получаем все стоп-слова для контекста
        all_stopwords = get_stopwords_data()
        stopwords_list = "\n".join([f"- {sw.get('word', '')}: {sw.get('description', '')}" for sw in all_stopwords])
        
        # Создаем промпт для AI
        prompt = f"""
        Ты - руководитель компании. Твоя задача - внимательно ознакомиться с ответом пользователя. 
        Он пытался исправить предложение со стоп словом.
        
        Исходное предложение: "{original_sentence}"
        Исходное стоп-слово: "{stopword.get('word', '')}"
        Перефразированный ответ пользователя: "{rephrased_sentence}"
        
        Вот стоп-слова компании, которые необходимо избегать:
        {stopwords_list}
        
        Оцени ответ пользователя строго по следующим критериям:
        1. В ответе НЕТ стоп-слова "{stopword.get('word', '')}"
        2. Ответ сохраняет смысл исходного предложения
        3. Ответ не содержит других стоп-слов из списка
        4. Ответ соответствует деловому стилю общения (нет ругательств, оскорблений)
        
        Ответь строго в формате JSON:
        {{
          "passed": true/false,
          "feedback": "конкретная обратная связь с объяснением результата"
        }}
        """
        
        # Отправляем запрос к API
        response = requests.post(api_url, json={
            "text": rephrased_sentence,
            "prompt": prompt,
            "format": "json"
        }, timeout=10)
        
        # Обрабатываем ответ
        if response.status_code != 200:
            logger.error(f"Ошибка при проверке ответа: {response.status_code}, {response.text}")
            raise Exception(f"Ошибка API: {response.status_code}")
        
        try:
            # Пытаемся распарсить JSON ответ
            result = response.json()
            passed = result.get("passed", False)
            feedback = result.get("feedback", "")
            
            return passed, feedback
        except json.JSONDecodeError:
            logger.error(f"Не удалось распарсить ответ API: {response.text}")
            raise Exception("Некорректный формат ответа от API")
            
    except Exception as e:
        logger.error(f"Ошибка при проверке перефразирования через AI: {e}")
        # Даже в случае ошибки, предоставляем простой ответ без использования шаблонов
        if stopword.get('word', '').lower() in rephrased_sentence.lower():
            return False, f"Ваш ответ все еще содержит стоп-слово '{stopword.get('word', '')}'. Попробуйте перефразировать предложение, полностью избегая этого слова."
        else:
            return True, "Ваш ответ принят. Вы успешно избежали использования стоп-слова."

# Load API key on module import
load_api_key()
