import json
import logging
from pathlib import Path
import os
import requests
from dotenv import load_dotenv
import re
import random

load_dotenv()

logger = logging.getLogger(__name__)

def load_text_content(filename):
    """Load text content from a file in the materials folder"""
    try:
        with open(Path('materials') / filename, 'r', encoding='utf-8') as file:
            return file.read()
    except Exception as e:
        logger.error(f"Error loading text content from {filename}: {e}")
        return f"Error loading content from {filename}. Please contact the administrator."

def load_test_questions(filename):
    """Load test questions from a JSON file in the materials folder"""
    try:
        with open(Path('materials') / filename, 'r', encoding='utf-8') as file:
            data = json.load(file)
            # Convert from JSON format to expected format in code
            if isinstance(data, dict) and "questions" in data:
                questions = []
                for q in data["questions"]:
                    questions.append({
                        "question": q["question"],
                        "options": q.get("options", q.get("answers", [])),
                        "correct_option": q.get("correct_option", q.get("correct_index", q.get("correct_answer", 0)))
                    })
                # Сохраняем информацию о времени, если она есть
                result = {
                    "questions": questions,
                    "time_limit": data.get("time_limit", None)  # Время в секундах
                }
                return result
            elif isinstance(data, list):
                # Уже в правильном формате или близком к нему
                return {"questions": data, "time_limit": None}
            return data
    except Exception as e:
        logger.error(f"Error loading test questions from {filename}: {e}")
        return None

def get_stopwords_data():
    """Получить данные о стоп-словах из Google Sheets"""
    try:
        api_url = os.getenv("API_KEY")
        sheet_url = os.getenv("STOPWORDS_SHEET_URL")
        
        if not api_url or not sheet_url:
            logger.error("API_KEY или STOPWORDS_SHEET_URL не настроены в .env")
            return []
        
        # Извлекаем ID таблицы из URL
        # URL формата: https://docs.google.com/spreadsheets/d/SPREADSHEET_ID/edit?gid=0#gid=0
        spreadsheet_id_match = re.search(r'/d/([^/]+)', sheet_url)
        if not spreadsheet_id_match:
            logger.error(f"Не удалось извлечь ID таблицы из URL: {sheet_url}")
            return []
            
        spreadsheet_id = spreadsheet_id_match.group(1)
        
        # Подготовка параметров запроса
        payload = {
            "spreadsheet_id": spreadsheet_id,
            "range": "A1:E100"  # Диапазон ячеек для чтения
        }
        
        logger.info(f"Отправка запроса к API с параметрами: {payload}")
        
        # Добавляем тайм-аут запроса (10 секунд)
        response = requests.post(api_url, json=payload, timeout=10)
        
        if response.status_code != 200:
            logger.error(f"Ошибка при запросе к API Google Sheets: {response.status_code}, {response.text}")
            # Возвращаем тестовые данные вместо пустого списка при ошибке
            return get_fallback_stopwords()
        
        # Парсинг данных из ответа
        data = response.json()
        logger.info(f"Получен ответ от API: {data.keys() if isinstance(data, dict) else 'не словарь'}")
        stopwords_data = []
        
        # Проверяем формат ответа API
        if "data" in data and isinstance(data["data"], dict):
            # Получаем первый лист из таблицы
            sheet_name = next(iter(data["data"]), None)
            if sheet_name and isinstance(data["data"][sheet_name], list):
                # Обрабатываем данные из первого листа
                for row in data["data"][sheet_name]:
                    stopword_entry = {
                        "id": row.get("№", ""),
                        "word": row.get("Слово/словосочетание", ""),
                        "description": row.get("Описание", ""),
                        "replacement": row.get("Заменить на", "")
                    }
                    
                    # Добавляем только записи с непустым словом
                    if stopword_entry["word"]:
                        stopwords_data.append(stopword_entry)
                
                logger.info(f"Успешно загружено {len(stopwords_data)} стоп-слов")
                return stopwords_data
            else:
                logger.error(f"Неверный формат данных листа: {data}")
        else:
            logger.error(f"Неверный формат ответа API Google Sheets: {data}")
        
        # Возвращаем тестовые данные вместо пустого списка
        return get_fallback_stopwords()
        
    except requests.exceptions.Timeout:
        logger.error("Превышено время ожидания запроса к API Google Sheets")
        return get_fallback_stopwords()
    except Exception as e:
        logger.error(f"Ошибка при получении данных о стоп-словах: {e}")
        return get_fallback_stopwords()

def get_fallback_stopwords():
    """Возвращает тестовый набор стоп-слов для использования при недоступности API"""
    logger.info("Возвращаем тестовый набор стоп-слов")
    return [
        {
            "id": "1",
            "word": "Странно",
            "description": "может обозначать что угодно",
            "replacement": "Необычно"
        },
        {
            "id": "2",
            "word": "Виноват",
            "description": "Нельзя обвинять ни себя, ни другого! Обвинение кого-то это непризнание своих ошибок! А обвинять себя - значит проиграть обстоятельствам, которые сам себе придумал!",
            "replacement": "Я допустил ошибку"
        },
        {
            "id": "3",
            "word": "Пригодиться",
            "description": "Может только какой-то товар, но не люди! Так можно обидеть человека!",
            "replacement": "Будет полезен"
        },
        {
            "id": "4",
            "word": "Частично",
            "description": "Размытое понятие, лучше указывать конкретную степень или процент выполнения",
            "replacement": "На 30%, в небольшой степени"
        },
        {
            "id": "5",
            "word": "Просто",
            "description": "Ничего не бывает просто, это умаляет усилия других людей",
            "replacement": "Для выполнения задачи необходимо..."
        },
        {
            "id": "6",
            "word": "Попробую",
            "description": "Не дает гарантий выполнения задачи",
            "replacement": "Сделаю"
        },
        {
            "id": "7",
            "word": "Наверное",
            "description": "Создает неуверенность и размытость",
            "replacement": "Определенно"
        },
        {
            "id": "8",
            "word": "Как бы",
            "description": "Размывает смысл сказанного",
            "replacement": "Точно, определенно"
        },
        {
            "id": "9",
            "word": "Думаю",
            "description": "Создает впечатление неуверенности",
            "replacement": "Уверен"
        },
        {
            "id": "10",
            "word": "Какая разница",
            "description": "Неуважительно и показывает безразличие",
            "replacement": "Давайте уточним, почему это важно"
        }
    ]

def generate_sentence_with_stopword(stopword_data):
    """Генерирует предложение с использованием стоп-слова"""
    # Получаем слово и его описание
    stopword = stopword_data.get("word", "")
    description = stopword_data.get("description", "")
    
    # Готовые шаблоны реальных предложений с различными стоп-словами
    realistic_templates = [
        "В разговоре с коллегой вы услышали: «{}». Как лучше выразить эту мысль?",
        "Клиент написал в чате: «{}». Как бы вы перефразировали это в деловом общении?",
        "На совещании прозвучала фраза: «{}». Предложите более корректный вариант.",
        "В email от сотрудника было сказано: «{}». Как улучшить эту формулировку?",
        "Руководитель отдела сказал на встрече: «{}». Как выразить ту же мысль без стоп-слова?"
    ]
    
    # Примеры реальных фраз с разными стоп-словами
    examples = {
        "Ты хвастаешься": [
            "Ты опять хвастаешься своими достижениями!",
            "Не надо мне хвастаться тем, что ты сделал.",
            "Я хотел бы похвастаться нашими результатами за квартал.",
            "Когда ты хвастаешься, это выглядит непрофессионально."
        ],
        "Странно": [
            "Мне кажется странно, что отчет до сих пор не готов.",
            "Странно, что никто не заметил эту ошибку раньше.",
            "Ваше поведение на встрече выглядело странно.",
            "Странно, что клиент не ответил на наше предложение."
        ],
        "Виноват": [
            "В этой ситуации виноват только менеджер проекта.",
            "Я не виноват, что сроки были нереалистичными.",
            "Кто виноват в срыве дедлайна?",
            "Если я в чем-то виноват, готов исправить ситуацию."
        ],
        "Пригодиться": [
            "Этот сотрудник может пригодиться в нашем проекте.",
            "Ваш опыт точно пригодится нашей команде.",
            "Думаю, эти навыки пригодятся тебе в новой должности.",
            "Когда-нибудь это пригодится, поверь мне."
        ],
        "Частично": [
            "Задача выполнена частично, нужно доработать.",
            "Я частично согласен с вашим предложением.",
            "Проект реализован частично из-за нехватки ресурсов.",
            "Мы частично решили эту проблему."
        ],
        "Просто": [
            "Это просто невозможно сделать в такие сроки!",
            "Давайте просто закроем этот вопрос и двинемся дальше.",
            "Я просто хотел узнать ваше мнение.",
            "Это просто отличная идея!"
        ],
        "Попробую": [
            "Я попробую закончить отчет к завтрашнему дню.",
            "Попробую связаться с клиентом сегодня.",
            "Давайте попробуем другой подход к решению проблемы.",
            "Я попробую убедить руководство в необходимости этих изменений."
        ],
        "Наверное": [
            "Наверное, мы не успеем завершить проект в срок.",
            "Этот подход, наверное, не сработает в нашем случае.",
            "Наверное, клиент будет недоволен таким решением.",
            "Я, наверное, не смогу присутствовать на совещании."
        ],
        "Как бы": [
            "Это, как бы, не совсем то, что мы планировали.",
            "Я, как бы, не совсем согласен с вашим подходом.",
            "Результаты, как бы, оказались ниже ожидаемых.",
            "Этот метод, как бы, устарел для современных задач."
        ],
        "Думаю": [
            "Думаю, нам стоит пересмотреть стратегию.",
            "Я думаю, что этот план не сработает.",
            "Думаю, клиент будет доволен нашим предложением.",
            "Как вы думаете, стоит ли нам менять поставщика?"
        ],
        "Какая разница": [
            "Какая разница, кто это сделал, главное результат.",
            "Какая разница, когда начинать, если дедлайн всё равно сорван?",
            "Какая разница между этими двумя подходами?",
            "Какая разница в цене между базовой и расширенной версией?"
        ]
    }
    
    # Если есть готовые примеры для данного стоп-слова, используем их
    if stopword in examples:
        example_sentences = examples[stopword]
        example = random.choice(example_sentences)
    else:
        # Если нет готовых примеров, создаем обобщенное предложение
        basic_templates = [
            "Я {} результатами проекта.",
            "Вы {} этим решением.",
            "Они {} своими достижениями.",
            "Команда {} новыми разработками.",
            "Руководитель {} показателями отдела."
        ]
        
        verbs = {
            "Ты хвастаешься": ["хвастается", "гордится", "похвастался"],
            "Странно": ["находит странным", "считает странным", "удивляется"],
            "Виноват": ["виноват в", "ответственен за", "несет ответственность за"],
            "Пригодиться": ["может пригодиться для", "будет полезен в", "пригодится при"],
            "Частично": ["частично доволен", "отчасти согласен с", "частично выполнил"],
            "Просто": ["просто недоволен", "просто не согласен с", "просто игнорирует"],
            "Попробую": ["попробует", "попытается", "попробовал бы"],
            "Наверное": ["наверное недоволен", "наверное согласится с", "наверное примет"],
            "Как бы": ["как бы согласен", "как бы понимает", "как бы принимает"],
            "Думаю": ["думает о", "размышляет над", "задумывается о"],
            "Какая разница": ["не видит разницы в", "безразличен к", "игнорирует различия в"]
        }
        
        # Если у нас есть глаголы для данного стоп-слова
        if stopword in verbs:
            verb_options = verbs[stopword]
            verb = random.choice(verb_options)
            template = random.choice(basic_templates)
            example = template.format(verb)
        else:
            # Создаем общее предложение со стоп-словом
            example = f"В рабочем разговоре было сказано: '{stopword}'."
    
    # Выбираем шаблон для итогового предложения
    template = random.choice(realistic_templates)
    return template.format(example)

def get_all_stopwords():
    """Получить список всех стоп-слов для проверки"""
    try:
        # Получаем все стоп-слова из базы данных или из Google Sheets
        stopwords_data = get_stopwords_data()
        
        # Создаем список только слов
        stopwords_list = []
        for sw in stopwords_data:
            word = sw.get("word", "").lower().strip()
            if word:
                stopwords_list.append(word)
        
        # Добавляем базовые разговорные слова и выражения, которые часто используются, но не желательны
        common_stopwords = [
            "какая разница", "какая тебе разница", "ну и что", "типа", "короче", "как бы",
            "ну", "блин", "это самое", "ладно", "так сказать", "чисто", "прикинь", "на самом деле",
            "в принципе", "жесть", "вообще", "просто", "значит", "как-то так", "щас", "прямо", "такое"
        ]
        
        # Объединяем списки, удаляя дубликаты
        all_stopwords = list(set(stopwords_list + common_stopwords))
        
        return all_stopwords
    except Exception as e:
        logger.error(f"Ошибка при получении списка всех стоп-слов: {e}")
        return []
