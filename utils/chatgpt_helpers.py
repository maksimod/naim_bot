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
                          language="ru",
                          user_id=None):
    """
    Call OpenAI API or local API to get a response from the model.
    
    Args:
        messages: List of message dicts for context
        model: OpenAI model name
        temperature: Generation temperature
        max_tokens: Maximum tokens
        language: Response language
        user_id: ID пользователя для записи использования AI (опционально)
    
    Returns:
        Response text or None on error
    """
    if not _api_key and not _api_url:
        if not load_api_key():
            logger.error("API key/URL not found. Cannot perform request.")
            return None
    
    # Запись использования AI, если передан user_id
    if user_id is not None:
        try:
            import database as db
            # Записываем использование с реальным названием модели
            model_name = model
            # Если используется локальный API, записываем это
            if _api_url:
                model_name = f"local_api_{model}"
            db.record_ai_usage(user_id, model_name)
        except Exception as e:
            logger.error(f"Error recording AI usage: {e}")
    
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

async def generate_ai_stopword_sentence(stopword_data, user_id=None):
    """
    Generate a sentence containing the stopword using AI.
    
    Args:
        stopword_data: Dictionary with stopword data
        user_id: ID пользователя для записи использования AI (опционально)
    
    Returns:
        Generated sentence
    """
    api_url = os.getenv("CHATGPT_API_KEY")
    
    stopword = stopword_data["word"]
    
    # Используем полные данные из таблицы стоп-слов
    description = stopword_data.get("description", "")
    replacement = stopword_data.get("replacement", "")
    
    # Составляем контекст для ИИ с полной информацией из таблицы
    context = f"Стоп-слово: {stopword}\n"
    if description:
        context += f"Описание: {description}\n"
    if replacement:
        context += f"Рекомендуемая замена: {replacement}\n"
    
    messages = [
        {
            "role": "system",
            "content": "Вы - помощник для генерации примеров предложений на русском языке. Создайте естественно звучащее предложение на русском языке, содержащее указанное слово. Используйте контекст, чтобы точно понять назначение и смысл стоп-слова. ВАЖНО: используйте ТОЛЬКО русский язык, не смешивайте русский с английским или другими языками."
        },
        {
            "role": "user",
            "content": f"Создайте одно предложение на русском языке, включающее слово '{stopword}'.\n\n{context}\n\nВажно: ответьте ТОЛЬКО предложением на русском языке, без дополнительных пояснений и без использования других языков."
        }
    ]
    
    # Вызываем API с указанием языка
    response = await call_openai_api(messages, user_id=user_id, language="ru")
    if not response:
        return f"В этом предложении используется стоп-слово {stopword}."
    
    # Извлекаем предложение из ответа
    sentence = extract_sentence_from_response(response)
    if not sentence:
        return f"В этом предложении используется стоп-слово {stopword}."
    
    return sentence

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

def get_hardcoded_example(stopword_data):
    """
    Возвращает заготовленный пример предложения для стоп-слова,
    если по какой-то причине не удалось сгенерировать через AI.
    
    Args:
        stopword_data: Данные о стоп-слове
    
    Returns:
        Пример предложения
    """
    stopword = stopword_data["word"]
    examples = stopword_data.get("examples", [])
    
    # Если есть примеры, берем случайный
    if examples:
        return random.choice(examples)
    
    # Если нет примеров, создаем стандартное предложение
    return f"Пример предложения, содержащего слово '{stopword}'."

async def verify_stopword_rephrasing_ai(original_sentence, rephrased_sentence, stopword, user_id=None):
    """
    Checks if the rephrased sentence:
    1. Preserves the semantic meaning of the original
    2. Не содержит стоп-слова
    
    Args:
        original_sentence: Исходное предложение со стоп-словом
        rephrased_sentence: Перефразированное предложение для проверки 
        stopword: Стоп-слово, которое должно быть исключено
        user_id: ID пользователя для записи использования AI (опционально)
    
    Returns:
        Dict с результатами проверки
    """
    # Если stopword - это словарь с полной информацией, извлекаем из него данные
    stopword_word = stopword
    description = ""
    replacement = ""
    
    if isinstance(stopword, dict):
        stopword_word = stopword.get("word", "")
        description = stopword.get("description", "")
        replacement = stopword.get("replacement", "")
    
    # Составляем контекст для ИИ с полной информацией
    context = ""
    if description:
        context += f"Описание стоп-слова: {description}\n"
    if replacement:
        context += f"Рекомендуемая замена: {replacement}\n"
        
    # Создаем примеры неправильных замен с синонимами
    examples = ""
    if isinstance(stopword_word, str) and len(stopword_word) > 0:
        examples = f"""
Примеры НЕПРАВИЛЬНЫХ замен (с использованием синонимов):

Стоп-слово: "спутать"
Оригинал: "Не пытайся спутать карты, я знаю, что ты планируешь."
❌ Неправильно: "Не пытайся спрятать карты, я знаю, что ты планируешь." (заменили на синоним)
✅ Правильно: "Я знаю твои планы, не пытайся меня обмануть."

Стоп-слово: "наверное"
Оригинал: "Он наверное придет завтра."
❌ Неправильно: "Он вероятно придет завтра." (заменили на синоним)
✅ Правильно: "Он точно придет завтра." или "Он обещал прийти завтра."

Стоп-слово: "{stopword_word}"
Необходимо не просто заменить на синоним, а перестроить предложение, чтобы избежать проблемной концепции.
"""
        
    messages = [
        {
            "role": "system",
            "content": "Вы - система строгой проверки перефразирования предложений со стоп-словами. Ваша основная задача - выявлять замены стоп-слов их синонимами, которые НЕ решают проблему стоп-слова. Стоп-слова запрещены не из-за конкретного слова, а из-за концепции или проблемного смысла, который они несут. Простая замена на синоним НЕ является правильным решением! Будьте очень строги в оценке."
        },
        {
            "role": "user",
            "content": f"Оцените, правильно ли перефразировано предложение:\n\n"
                       f"Оригинальное предложение: \"{original_sentence}\"\n"
                       f"Перефразированное предложение: \"{rephrased_sentence}\"\n"
                       f"Стоп-слово: \"{stopword_word}\"\n\n"
                       f"{context}\n\n"
                       f"⚠️ КРИТИЧЕСКИ ВАЖНО! ⚠️\n"
                       f"Замена стоп-слова его синонимом или близким по значению выражением НЕ ЯВЛЯЕТСЯ правильным ответом!\n"
                       f"Проблема не в конкретном слове, а в концепции. Предложение должно быть полностью перестроено.\n\n"
                       f"{examples}\n"
                       f"Верните результат в JSON формате:\n"
                       f"```json\n"
                       f"{{\n"
                       f"  \"preserves_meaning\": true/false - сохраняет ли перефразированное предложение смысл оригинала,\n"
                       f"  \"excludes_stopword\": true/false - отсутствует ли стоп-слово И его синонимы в перефразированном предложении,\n"
                       f"  \"used_synonym\": true/false - использовал ли автор синоним вместо стоп-слова\n"
                       f"}}\n"
                       f"```"
        }
    ]
    
    try:
        # Вызываем AI API с указанием русского языка
        response = await call_openai_api(messages, user_id=user_id, language="ru")
        if not response:
            # Если нет ответа, делаем простую проверку на наличие стоп-слова
            return {"preserves_meaning": True, "excludes_stopword": stopword_word.lower() not in rephrased_sentence.lower(), "used_synonym": False}
        
        # Ищем JSON в ответе
        json_match = re.search(r'\{.*\}', response, re.DOTALL)
        if json_match:
            json_str = json_match.group(0)
            try:
                result = json.loads(json_str)
                # Проверяем, есть ли все необходимые поля
                if "preserves_meaning" in result and "excludes_stopword" in result:
                    # Если обнаружено использование синонима, сразу отклоняем ответ
                    if "used_synonym" in result and result["used_synonym"]:
                        result["excludes_stopword"] = False
                    return result
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse JSON from AI response: {json_str}")
        
        # Анализируем текстовый ответ, если JSON не найден
        preserves_meaning = "не сохран" not in response.lower() and "не передает" not in response.lower()
        excludes_stopword = "содержит стоп-слово" not in response.lower() and "включает стоп-слово" not in response.lower() and "синоним" not in response.lower()
        used_synonym = "синоним" in response.lower() or "заменил на похожее" in response.lower()
        
        # Если использован синоним, считаем, что стоп-слово не исключено
        if used_synonym:
            excludes_stopword = False
            
        return {
            "preserves_meaning": preserves_meaning,
            "excludes_stopword": excludes_stopword,
            "used_synonym": used_synonym
        }
    except Exception as e:
        logger.error(f"Error verifying rephrasing: {e}")
        # При ошибке выполняем базовую проверку
        return {
            "preserves_meaning": True, 
            "excludes_stopword": stopword_word.lower() not in rephrased_sentence.lower(),
            "used_synonym": False
        }

async def verify_poem_task(solution_text, user_id=None):
    """Verify completion of the poem task using ChatGPT"""
    api_url = os.getenv("CHATGPT_API_KEY")
    
    messages = [
        {
            "role": "system",
            "content": "You are a poetry expert evaluating a poem written by a job candidate. Provide a detailed assessment."
        },
        {
            "role": "user",
            "content": f"""Please evaluate this poem written by a job candidate:

{solution_text}

Evaluate on these criteria:
1. It must be at least 4 lines
2. It should have some rhythm or rhyme
3. It should be creative and demonstrate effort
4. It should be about technology, AI, or the workplace

Respond with a JSON object like this:
{{
  "is_valid": true/false,
  "feedback": "Your assessment"
}}

Only include the JSON object in your response."""
        }
    ]
    
    try:
        response = await call_openai_api(
            messages=messages,
            model="gpt-3.5-turbo-0125",
            temperature=0.3,
            max_tokens=500,
            user_id=user_id
        )
        
        if not response:
            # Fallback if API call fails
            return {
                "is_valid": True,  # Give benefit of the doubt
                "feedback": "Automatic verification unavailable. We've accepted your poem. Well done!"
            }
        
        # Try to extract JSON from response
        try:
            # Look for a JSON object in the response
            json_match = re.search(r'(\{.*\})', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
                result = json.loads(json_str)
                return result
            else:
                # If no JSON found, try to parse the whole response
                result = json.loads(response)
                return result
        except json.JSONDecodeError:
            logger.error(f"Error calling ChatGPT API: {response.status_code}")
            # Fallback JSON
            return {
                "is_valid": True,  # Give benefit of the doubt
                "feedback": "We had trouble analyzing your poem, but we've accepted it. Thank you for your submission!"
            }
    except Exception as e:
        logger.error(f"Error verifying poem: {e}")
        # Fallback result
        return {
            "is_valid": True,  # Give benefit of the doubt
            "feedback": "We're experiencing technical issues with our evaluation system, but we've decided to accept your poem. Thank you for your effort!"
        }

# Load API key on module import
load_api_key()
