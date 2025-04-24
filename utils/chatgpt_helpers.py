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
DEFAULT_MODEL = "gpt-4.1-nano"
DEFAULT_TEMPERATURE = 0.7
DEFAULT_MAX_TOKENS = 5000

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
            return True
        else:
            _api_key = api_key
            return True
    
    logger.warning("API key/URL not found. Some features will be unavailable.")
    return False

async def call_openai_api(messages, 
                          model=DEFAULT_MODEL,
                          temperature=DEFAULT_TEMPERATURE,
                          max_tokens=DEFAULT_MAX_TOKENS,
                          language="ru",
                          user_id=None):

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
    if not isinstance(text, str):
        return text

    if '\\u' not in text:
        return text
    
    try:
        decoded = json.loads(f'"{text}"')
        return decoded
    except json.JSONDecodeError:
        try:
            pattern = '\\\\u([0-9a-fA-F]{4})'
            result = re.sub(pattern, lambda m: chr(int(m.group(1), 16)), text)
            return result
        except Exception as e:
            logger.warning(f"Failed to decode Unicode: {e}")
            return text

async def select_ai_stopword(user_id=None, used_stopwords=None):
    """
    Позволяет ИИ выбрать стоп-слово из полного списка и построить с ним предложение.
    
    Args:
        user_id: ID пользователя для логирования API вызовов
        used_stopwords: Список уже использованных стоп-слов, чтобы избежать повторений
    
    Returns:
        dict: Словарь с выбранным стоп-словом и построенным предложением
    """
    # Добавляем логирование
    logger.info(f"Начало select_ai_stopword. Used stopwords: {used_stopwords}")
    
    # Получаем полный список всех стоп-слов для выбора
    all_stopwords_data = get_stopwords_data()
    logger.info(f"Получено {len(all_stopwords_data)} стоп-слов из базы")
    
    if not all_stopwords_data:
        logger.error("Не удалось получить список стоп-слов")
        return {
            "word": "пожалуйста",
            "description": "Вежливое слово, используемое для смягчения просьбы",
            "replacement": "Уберите это слово или перестройте предложение",
            "sentence": "Пожалуйста, подготовьте отчет к завтрашнему дню."
        }
    
    # Инициализируем список уже использованных стоп-слов, если он не передан
    if used_stopwords is None:
        used_stopwords = []
    
    logger.info(f"Фильтрация стоп-слов. Уже использовано: {len(used_stopwords)}")
    
    # Определим список приоритетных стоп-слов, которые хорошо видны в предложениях
    priority_stopwords = [
        "пожалуйста", "наверное", "возможно", "ну", "проблема", "давайте подумаем", 
        "ладно", "помогать", "хороший", "не хочу", "не могу", "не знаю"
    ]
    
    # Формируем отфильтрованный список доступных стоп-слов
    available_stopwords = []
    
    for sw in all_stopwords_data:
        word = sw.get("word", "").lower().strip()
        # Проверяем, что стоп-слово еще не использовалось
        if word and word not in [w.lower() for w in used_stopwords]:
            available_stopwords.append(sw)
    
    # Если осталось меньше 5 стоп-слов, сбрасываем список использованных
    if len(available_stopwords) < 5:
        logger.warning(f"Мало доступных стоп-слов ({len(available_stopwords)}), сбрасываем список использованных")
        available_stopwords = all_stopwords_data
    
    logger.info(f"Доступно стоп-слов после фильтрации: {len(available_stopwords)}")
    
    # Сортируем стоп-слова, чтобы приоритетные были в начале списка
    def get_priority(stopword):
        word = stopword.get("word", "").lower().strip()
        # Если слово в приоритетном списке, возвращаем его индекс
        for i, priority_word in enumerate(priority_stopwords):
            if priority_word in word or word in priority_word:
                return i
        # Если не в приоритетном списке, возвращаем высокое значение
        return 1000
    
    # Сортируем по приоритету
    available_stopwords.sort(key=get_priority)
    
    # Выбираем первые 15 стоп-слов для отправки в API
    selected_stopwords = available_stopwords[:15]
    
    # Формируем контекст для запроса
    stopwords_context = []
    for sw in selected_stopwords:
        word = sw.get("word", "").strip()
        description = sw.get("description", "").strip()
        replacement = sw.get("replacement", "").strip()
        
        if word:
            stopwords_context.append(f"Стоп-слово: {word}\nОписание: {description}\nРекомендуемая замена: {replacement}")
    
    logger.info(f"Отправляем в API {len(stopwords_context)} стоп-слов")
    
    # Составляем запрос для ИИ с доступными стоп-словами
    messages = [
        {
            "role": "system",
            "content": "Вы - эксперт по деловой коммуникации. Ваша задача - выбрать одно стоп-слово из предложенного списка и составить с ним реалистичное деловое предложение. КРАЙНЕ ВАЖНО, чтобы стоп-слово было явно и чётко видно в предложении."
        },
        {
            "role": "user",
            "content": f"""Выберите ОДНО стоп-слово из списка ниже и создайте с ним реалистичное деловое предложение:

{chr(10).join(stopwords_context)}

ОБЯЗАТЕЛЬНЫЕ ТРЕБОВАНИЯ:
1. Выберите ТОЛЬКО ОДНО стоп-слово из списка
2. Включите это стоп-слово в предложение ОЧЕНЬ ЯВНО, сделав его хорошо заметным
3. Создайте РЕАЛИСТИЧНОЕ деловое предложение длиной 7-15 слов
4. НЕ добавляйте к выбранному стоп-слову другие стоп-слова из списка
5. Не выбирайте стоп-слова, которые уже использовались: {', '.join(used_stopwords) if used_stopwords else 'таких пока нет'}

ПРИМЕР ХОРОШЕГО РЕЗУЛЬТАТА:
Стоп-слово: пожалуйста
Предложение: "Отправьте мне отчет до завтра, пожалуйста."

ПРИМЕР ПЛОХОГО РЕЗУЛЬТАТА:
Стоп-слово: пожалуйста
Предложение: "Мы обсудили некоторые темы на совещании" (стоп-слово отсутствует!)

Ответьте в формате JSON:
{{
  "word": "выбранное стоп-слово",
  "description": "описание из таблицы",
  "replacement": "рекомендуемая замена из таблицы",
  "sentence": "составленное предложение со стоп-словом"
}}"""
        }
    ]
    
    # Добавляем логирование запроса
    logger.info(f"Отправляем запрос в ChatGPT для выбора стоп-слова")
    
    # Вызываем API с указанием языка
    response = await call_openai_api(messages, user_id=user_id, language="ru")
    if not response:
        logger.error("Не получен ответ от API при выборе стоп-слова")
        # В случае ошибки возвращаем стандартное стоп-слово
        return {
            "word": "пожалуйста",
            "description": "Вежливое слово, используемое для смягчения просьбы",
            "replacement": "Уберите это слово или перестройте предложение",
            "sentence": "Пожалуйста, подготовьте отчет к завтрашнему дню."
        }
    
    logger.info(f"Получен ответ от API: {response[:100]}...")
    
    # Извлекаем JSON из ответа
    try:
        # Ищем JSON в ответе
        json_match = re.search(r'\{.*\}', response, re.DOTALL)
        if json_match:
            json_str = json_match.group(0)
            result = json.loads(json_str)
            
            # Проверяем, что все нужные поля присутствуют
            if "word" in result and "sentence" in result:
                # Проверяем, что стоп-слово действительно присутствует в предложении
                if result["word"].lower() in result["sentence"].lower():
                    logger.info(f"Успешно выбрано стоп-слово: {result['word']}")
                    # Убеждаемся, что описание и замена заполнены
                    if not result.get("description"):
                        result["description"] = "Это стоп-слово затрудняет деловую коммуникацию"
                    if not result.get("replacement"):
                        result["replacement"] = "Уберите это слово или перефразируйте предложение"
                    return result
                else:
                    logger.error(f"Стоп-слово '{result['word']}' отсутствует в предложении '{result['sentence']}'")
    except Exception as e:
        logger.error(f"Ошибка при извлечении выбранного стоп-слова: {e}")
    
    # Если не удалось создать предложение через API, выбираем приоритетное стоп-слово
    fallback_options = [
        {
            "word": "пожалуйста",
            "description": "Вежливое слово, используемое для смягчения просьбы. ПРИМЕНЯТЬ ТОЛЬКО: 1. ПОСЛЕ ТОГО, КАК ТЫ ПОВТОРЯЕШЬ ПРОСЬБУ ЧЕРЕЗ НЕКОТОРОЕ ВРЕМЯ! 2. В ОТВЕТ НА СПАСИБО!",
            "replacement": "Уберите это слово или перестройте предложение",
            "sentence": "Подготовьте отчет к завтрашнему дню, пожалуйста."
        },
        {
            "word": "наверное",
            "description": "Выражает неуверенность и сомнение, что неприемлемо в деловой коммуникации",
            "replacement": "Уберите это слово или используйте конкретные сроки/факты",
            "sentence": "Я наверное закончу проект к пятнице."
        },
        {
            "word": "проблема",
            "description": "Негативно окрашенное слово, создающее психологический барьер",
            "replacement": "задача, вопрос, ситуация",
            "sentence": "У нас возникла проблема с поставкой материалов."
        }
    ]
    
    # Выбираем первое стоп-слово, которое еще не использовалось
    for option in fallback_options:
        if option["word"].lower() not in [w.lower() for w in used_stopwords]:
            logger.info(f"Использую резервное стоп-слово: {option['word']}")
            return option
    
    # Если все резервные варианты использованы, возвращаем первый
    logger.info("Все резервные стоп-слова использованы, возвращаю первое")
    return fallback_options[0]

async def generate_ai_stopword_sentence(stopword_data, user_id=None):
    api_url = os.getenv("CHATGPT_API_KEY")
    
    # Если передан словарь с готовым предложением от select_ai_stopword
    if "sentence" in stopword_data:
        return stopword_data.get("sentence")
    
    # Иначе работаем в обычном режиме
    stopword = stopword_data["word"]
    
    # Используем полные данные из таблицы стоп-слов
    description = stopword_data.get("description", "")
    replacement = stopword_data.get("replacement", "")
    
    # Получаем полный список всех стоп-слов для проверки
    all_stopwords = []
    all_stopwords_data = get_stopwords_data()
    all_stopwords = [sw.get("word", "").lower() for sw in all_stopwords_data if "word" in sw]
    
    # Убираем текущее стоп-слово из списка всех стоп-слов
    other_stopwords = [w for w in all_stopwords if w.lower() != stopword.lower()]
    
    # Составляем контекст для ИИ с полной информацией из таблицы
    context = f"Стоп-слово для включения в предложение: {stopword}\n"
    if description:
        context += f"Описание: {description}\n"
    if replacement:
        context += f"Рекомендуемая замена: {replacement}\n"
    
    # Добавляем информацию о других стоп-словах
    if other_stopwords:
        context += f"\nВАЖНО: Предложение должно содержать указанное стоп-слово '{stopword}'. НЕ ВКЛЮЧАЙТЕ другие стоп-слова: {', '.join(other_stopwords)}\n"
    
    messages = [
        {
            "role": "system",
            "content": "Вы - специалист по деловой коммуникации. Ваша задача - создать одно короткое деловое предложение, которое содержит ОДНО указанное стоп-слово и НЕ содержит других стоп-слов из запрещенного списка. Предложение должно быть естественным, лаконичным и реалистичным."
        },
        {
            "role": "user",
            "content": f"Создайте одно короткое, реалистичное деловое предложение, включающее указанное стоп-слово '{stopword}' и НЕ включающее никаких других стоп-слов из запрещенного списка.\n\n{context}\n\nПредложение должно:\n1) Содержать указанное стоп-слово '{stopword}'\n2) НЕ содержать никаких других стоп-слов\n3) Быть коротким (5-15 слов) и звучать естественно\n4) Подходить для делового общения\n\nОтветьте ТОЛЬКО одним предложением, без кавычек и пояснений."
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
    stopword = stopword_data["word"]
    examples = stopword_data.get("examples", [])
    
    # Если есть примеры, берем случайный
    if examples:
        return random.choice(examples)
    
    # Если нет примеров, создаем стандартное предложение
    return f"Пример предложения, содержащего слово '{stopword}'."

async def verify_stopword_rephrasing_ai(original_sentence, rephrased_sentence, stopword, user_id=None):
    """
    Проверяет, правильно ли перефразировано предложение без стоп-слова.
    
    Args:
        original_sentence: Исходное предложение со стоп-словом
        rephrased_sentence: Перефразированное предложение
        stopword: Стоп-слово или словарь с данными о стоп-слове
        user_id: ID пользователя для логирования API вызовов
    
    Returns:
        dict: Результат проверки {preserves_meaning, excludes_stopword, used_synonym, detected_stopword}
    """
    logger.info(f"Начало проверки перефразирования. Стоп-слово: {stopword if isinstance(stopword, str) else stopword.get('word', '')}")
    logger.info(f"Оригинал: {original_sentence}")
    logger.info(f"Перефраз: {rephrased_sentence}")
    
    # Если stopword - это словарь с полной информацией, извлекаем из него данные
    stopword_word = stopword
    description = ""
    replacement = ""
    
    if isinstance(stopword, dict):
        stopword_word = stopword.get("word", "")
        description = stopword.get("description", "")
        replacement = stopword.get("replacement", "")
    
    # Получаем полный список всех стоп-слов для проверки
    all_stopwords = []
    all_stopwords_data = get_stopwords_data()
    all_stopwords = [sw.get("word", "").lower() for sw in all_stopwords_data if "word" in sw]
    
    # Составляем контекст для ИИ с полной информацией
    context = ""
    if stopword_word:
        context += f"Целевое стоп-слово: {stopword_word}\n"
    if description:
        context += f"Описание стоп-слова: {description}\n"
    if replacement:
        context += f"Рекомендуемая замена: {replacement}\n"
    
    # Добавляем информацию о всех стоп-словах (передаем список из 20 наиболее распространенных)
    common_stopwords = ["пожалуйста", "наверное", "возможно", "проблема", "ну", "ладно", 
                      "надо", "ясно", "как бы", "хорошо", "плохо", "нормально"]
    
    context += f"\nСписок распространенных стоп-слов для проверки: {', '.join(common_stopwords)}\n"
        
    # Создаем примеры правильных и неправильных решений для обучения AI
    examples = f"""
ПРИМЕРЫ ПРОВЕРКИ ПЕРЕФРАЗИРОВАНИЙ:

ПРИМЕР 1:
Оригинал: "Не уверен, но предложу вам этот вариант."
Стоп-слово: "не уверен"
Перефраз: "Я конечно совневаюсь, но наверное предложу вам этот вариант"
❌ НЕПРАВИЛЬНО - "Совневаюсь" - прямой синоним "не уверен", а "наверное" указывает на неуверенность

ПРИМЕР 2:
Оригинал: "Не хочу принимать это предложение без дополнительных условий."
Стоп-слово: "не хочу"
Перефраз: "Я собираюсь принять это красивое и прекрасное предложения с дополнительными условиями"
❌ НЕПРАВИЛЬНО - Добавлены субъективные оценочные прилагательные "красивое" и "прекрасное"

ПРИМЕР 3:
Оригинал: "Хорошо, приступим к реализации этого проекта."
Стоп-слово: "Хорошо"
Перефраз: "Приступим к реализации этого проекта"
✅ ПРАВИЛЬНО - Пользователь удалил стоп-слово "Хорошо" и сохранил основную инструкцию.

ПРИМЕР 4:
Оригинал: "Вы не так поняли!"
Стоп-слово: "понять"
Перефраз: "Вам нужно сосредоточиться и правильно меня услышать"
✅ ПРАВИЛЬНО - Пользователь полностью изменил конструкцию без использования концепта "понимания".

ПРИМЕР 5:
Оригинал: "Товары предлагаются по разным ценам: дёшево или дорого."
Стоп-слово: "дёшево или дорого"
Перефраз: "Товары предлагаются по цене 20 и 40 рублей"
✅ ПРАВИЛЬНО - Пользователь заменил оценочные суждения на конкретные цены.

ПРИМЕР 6:
Оригинал: "Я буду рад, если вы примете участие."
Стоп-слово: "рад"
Перефраз: "Примите участие"
✅ ПРАВИЛЬНО - Пользователь удалил эмоциональную составляющую и оставил ключевое действие.

ПРИМЕР 7:
Оригинал: "Не знаю, какое решение принять в этой ситуации."
Стоп-слово: "не знаю"
Перефраз: "Я в раздумьях насчет решения в этой ситуации"
❌ НЕПРАВИЛЬНО - "В раздумьях" в данном контексте - синоним "не знаю"
"""

    # Делаем базовую проверку
    if not rephrased_sentence or rephrased_sentence.strip() == "":
        logger.warning("Пустой ответ на перефразирование")
        return {
            "preserves_meaning": False,
            "excludes_stopword": False,
            "used_synonym": False,
            "detected_stopword": stopword_word
        }
    
    # Быстрая проверка на наличие стоп-слова в ответе
    if stopword_word.lower() in rephrased_sentence.lower():
        logger.info(f"Быстрая проверка обнаружила стоп-слово '{stopword_word}' в ответе")
        return {
            "preserves_meaning": True,
            "excludes_stopword": False,
            "used_synonym": False,
            "detected_stopword": stopword_word
        }
    
    # Проверяем, не совпадает ли оригинал с ответом (если стоп-слова в оригинале нет)
    if original_sentence.lower() == rephrased_sentence.lower() and stopword_word.lower() not in original_sentence.lower():
        logger.info("Ответ совпадает с оригиналом, и стоп-слова нет в оригинале")
        return {
            "preserves_meaning": True,
            "excludes_stopword": True,
            "used_synonym": False,
            "detected_stopword": ""
        }
        
    messages = [
        {
            "role": "system",
            "content": "Вы - эксперт по лингвистическому анализу, специализирующийся на оценке перефразированных предложений. Ваша задача - определить, правильно ли пользователь удалил стоп-слова из предложения. При оценке СТРОГО ПРИДЕРЖИВАЙТЕСЬ следующих принципов:\n\n1. ПРИНИМАЙТЕ удаление вводных фраз и любых частей предложения, содержащих стоп-слово, если смысл предложения сохранен.\n\n2. ПРИНИМАЙТЕ полностью перестроенные предложения, где концепт, связанный со стоп-словом, передан другими способами.\n\n3. СЧИТАЙТЕ НЕПРАВИЛЬНЫМ ответы с ЛЮБЫМИ субъективными оценками - прилагательными 'красивый', 'прекрасный', 'хороший', 'плохой', 'странный' и другими качественными прилагательными.\n\n4. СЧИТАЙТЕ НЕПРАВИЛЬНЫМ ответы с ЛЮБЫМИ синонимами стоп-слов: 'не знаю'→'совневаюсь/в раздумьях', 'не уверен'→'не понимаю', 'возможно'→'может быть/вероятно', и т.д.\n\n5. СЧИТАЙТЕ НЕПРАВИЛЬНЫМИ ЛЮБЫЕ ОТВЕТЫ, СОДЕРЖАЩИЕ ХОТЯ БЫ ОДНО СТОП СЛОВО ИЛИ ЕГО СИНОНИМ ИЗ СПИСКА ЗАПРЕЩЕННЫХ СЛОВ!"
        },
        {
            "role": "user",
            "content": f"""Проанализируйте, правильно ли перефразировано предложение:

ОРИГИНАЛ: \"{original_sentence}\"
СТОП-СЛОВО: \"{stopword_word}\"
ПЕРЕФРАЗ: \"{rephrased_sentence}\"

ТАБЛИЦА СТОП-СЛОВ С ОБЬЯСНЕНИЯМИ:
{context}

ИНСТРУКЦИЯ ПО ОЦЕНКЕ:

1. СЧИТАЙТЕ ПРАВИЛЬНЫМ ОТВЕТОМ ТОЛЬКО:
   - Полное удаление частей предложения, содержащих стоп-слово
   - Существенное сокращение предложения, если удалено стоп-слово
   - Полное изменение конструкции, чтобы избежать стоп-слова и его синонимов
   - Замену субъективных оценок на объективные факты (конкретные цифры и т.д.)

2. СЧИТАЙТЕ НЕПРАВИЛЬНЫМ ОТВЕТОМ:
   - Использование того же стоп-слова в любой форме
   - Использование синонимов (например: 'не уверен'→'совневаюсь', 'возможно'→'может быть')
   - Добавление субъективных оценочных прилагательных ('красивый', 'прекрасный', 'хороший')
   - Сохранение той же самой модальности или эмоциональной окраски

3. ВНИМАТЕЛЬНО АНАЛИЗИРУЙТЕ СИНОНИМИЧЕСКИЕ ПЕРЕФРАЗИРОВКИ:
   - 'совневаюсь' = синоним 'не уверен'
   - 'может быть/вероятно' = синоним 'возможно'
   - 'в раздумьях' = синоним 'не знаю'

{examples}

Верните ваше решение в JSON формате:

```json
{{
  "preserves_meaning": true/false, // сохраняет ли перефразированное предложение основной смысл
  "excludes_stopword": true/false, // отсутствуют ли стоп-слова и их синонимы
  "used_synonym": true/false, // использовал ли автор синоним стоп-слова
  "detected_stopword": "конкретное найденное стоп-слово или его синоним" // пустая строка, если стоп-слова нет
}}
```"""
        }
    ]
    
    logger.info("Отправляю запрос в ChatGPT для проверки перефразирования")

    try:
        # Вызываем AI API с указанием русского языка
        response = await call_openai_api(messages, user_id=user_id, language="ru")
        if not response:
            logger.error("Не получен ответ от API при проверке перефразирования")
            # Если нет ответа, делаем простую проверку на наличие стоп-слова
            return {
                "preserves_meaning": True, 
                "excludes_stopword": stopword_word.lower() not in rephrased_sentence.lower(), 
                "used_synonym": False,
                "detected_stopword": stopword_word.lower() if stopword_word.lower() in rephrased_sentence.lower() else ""
            }
        
        logger.info(f"Получен ответ от API: {response[:100]}...")
        
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
                    
                    # Если поле detected_stopword не передано, добавляем пустую строку
                    if "detected_stopword" not in result:
                        result["detected_stopword"] = ""
                    
                    logger.info(f"Результат проверки: сохраняет смысл={result['preserves_meaning']}, исключает стоп-слово={result['excludes_stopword']}")
                    if not result['excludes_stopword'] and result.get('detected_stopword'):
                        logger.info(f"Обнаружено стоп-слово: {result['detected_stopword']}")
                        
                    return result
            except json.JSONDecodeError:
                logger.warning(f"Не удалось распарсить JSON из ответа API: {json_str}")
        
        # Анализируем текстовый ответ, если JSON не найден
        preserves_meaning = "не сохран" not in response.lower() and "не передает" not in response.lower()
        excludes_stopword = "содержит стоп-слово" not in response.lower() and "включает стоп-слово" not in response.lower()
        used_synonym = "синоним" in response.lower() and "не считайте синонимами" not in response.lower()
        detected_stopword = ""
        
        # Ищем указание на конкретное стоп-слово в ответе
        stopword_match = re.search(r'стоп-слово.*?[«"\']([^«"\']+)[»"\']', response, re.IGNORECASE)
        if stopword_match:
            detected_stopword = stopword_match.group(1)
        
        # Если использован синоним, считаем, что стоп-слово не исключено
        if used_synonym:
            excludes_stopword = False
            
        logger.info(f"Результат текстового анализа: сохраняет смысл={preserves_meaning}, исключает стоп-слово={excludes_stopword}")
        if not excludes_stopword and detected_stopword:
            logger.info(f"Обнаружено стоп-слово: {detected_stopword}")
            
        return {
            "preserves_meaning": preserves_meaning,
            "excludes_stopword": excludes_stopword,
            "used_synonym": used_synonym,
            "detected_stopword": detected_stopword
        }
    except Exception as e:
        logger.error(f"Ошибка при проверке перефразирования: {e}")
        # При ошибке выполняем базовую проверку
        return {
            "preserves_meaning": True, 
            "excludes_stopword": stopword_word.lower() not in rephrased_sentence.lower(),
            "used_synonym": False,
            "detected_stopword": stopword_word.lower() if stopword_word.lower() in rephrased_sentence.lower() else ""
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
            model="gpt-4.1-nano",
            temperature=0.3,
            max_tokens=5000,
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
