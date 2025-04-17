import json
import logging
from pathlib import Path
import os
import requests
from dotenv import load_dotenv

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
        
        # Подготовка параметров запроса
        params = {
            "url": sheet_url
        }
        
        # Выполняем запрос к API для получения данных
        response = requests.get(api_url, params=params)
        
        if response.status_code != 200:
            logger.error(f"Ошибка при запросе к API Google Sheets: {response.status_code}, {response.text}")
            return []
        
        # Парсинг данных из ответа
        data = response.json()
        stopwords_data = []
        
        # Проверка наличия данных и их структуры
        if "values" not in data:
            logger.error("Неверный формат ответа API Google Sheets")
            return []
        
        # Обработка данных о стоп-словах
        # Пропускаем первую строку (заголовки)
        for row in data["values"][1:]:
            # Проверяем, что в строке достаточно столбцов
            if len(row) >= 3:  # Минимум № (индекс), слово и описание
                stopword_entry = {
                    "id": row[0] if row[0] else "",
                    "word": row[1] if len(row) > 1 and row[1] else "",
                    "description": row[2] if len(row) > 2 and row[2] else "",
                    "replacement": row[3] if len(row) > 3 and row[3] else ""
                }
                
                # Добавляем только записи с непустым словом
                if stopword_entry["word"]:
                    stopwords_data.append(stopword_entry)
        
        return stopwords_data
        
    except Exception as e:
        logger.error(f"Ошибка при получении данных о стоп-словах: {e}")
        return []

def generate_sentence_with_stopword(stopword_data):
    """Генерирует предложение с использованием стоп-слова"""
    stopword = stopword_data["word"]
    description = stopword_data["description"]
    
    # Если есть описание, используем его для создания контекста
    if description and description.strip():
        # Формируем предложение на основе описания и стоп-слова
        return f"В рабочей ситуации часто используют слово '{stopword}'. {description}"
    else:
        # Если описания нет, создаем общее предложение со стоп-словом
        return f"В деловой переписке нужно избегать использования фразы '{stopword}', так как это может привести к недопониманию."
