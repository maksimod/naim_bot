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
                    question_data = {
                        "question": q["question"],
                        "options": q.get("options", q.get("answers", []))
                    }
                    
                    # Handle different format of correct answer field
                    if "correct_answer" in q:
                        question_data["correct_answer"] = q["correct_answer"]
                    elif "correct_option" in q:
                        question_data["correct_option"] = q["correct_option"]
                    elif "correct_index" in q:
                        question_data["correct_answer"] = q["correct_index"]
                    else:
                        question_data["correct_answer"] = 0
                        
                    questions.append(question_data)
                
                # Сохраняем информацию о времени, если она есть
                result = {
                    "questions": questions,
                    "time_limit": data.get("time_limit", None)  # Время в секундах
                }
                return result
            elif isinstance(data, list):
                # For list format (like interview_prep_test.json)
                # Keep original structure but ensure consistent format
                processed_questions = []
                for q in data:
                    question_data = {
                        "question": q["question"],
                        "options": q.get("options", q.get("answers", []))
                    }
                    
                    # Handle different format of correct answer field
                    if "correct_answer" in q:
                        question_data["correct_answer"] = q["correct_answer"]
                    elif "correct_option" in q:
                        question_data["correct_option"] = q["correct_option"]
                    elif "correct_index" in q:
                        question_data["correct_answer"] = q["correct_index"]
                    else:
                        question_data["correct_answer"] = 0
                        
                    processed_questions.append(question_data)
                
                return {"questions": processed_questions, "time_limit": None}
            
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
        
        # Подготовка параметров запроса - увеличиваем диапазон, чтобы захватить больше столбцов
        payload = {
            "spreadsheet_id": spreadsheet_id,
            "range": "A1:E100"  # Диапазон ячеек для чтения
        }
        
        
        # Добавляем тайм-аут запроса (10 секунд)
        response = requests.post(api_url, json=payload, timeout=10)
        
        if response.status_code != 200:
            logger.error(f"Ошибка при запросе к API Google Sheets: {response.status_code}, {response.text}")
            # Возвращаем пустой список при ошибке, чтобы ошибка была видна
            return []
        
        # Парсинг данных из ответа
        data = response.json()
        stopwords_data = []
        
        # Проверяем формат ответа API
        if "data" in data and isinstance(data["data"], dict):
            # Получаем первый лист из таблицы
            sheet_name = next(iter(data["data"]), None)
            if sheet_name and isinstance(data["data"][sheet_name], list):
                # Обрабатываем данные из первого листа
                for row in data["data"][sheet_name]:
                    # Сохраняем все доступные данные из строки таблицы
                    stopword_entry = {
                        "id": row.get("№", ""),
                        "word": row.get("Слово/словосочетание", ""),
                        "description": row.get("Описание", ""),
                        "replacement": row.get("Заменить на", ""),
                        "date_added": row.get("Дата добавления", "")
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
        
        # Возвращаем пустой список при любой ошибке формата данных
        return []
        
    except requests.exceptions.Timeout:
        logger.error("Превышено время ожидания запроса к API Google Sheets")
        return []
    except Exception as e:
        logger.error(f"Ошибка при получении данных о стоп-словах: {e}")
        return []

def get_all_stopwords():
    """Получить полные данные о всех стоп-словах для проверки"""
    try:
        # Получаем все стоп-слова из Google Sheets
        stopwords_data = get_stopwords_data()
        
        # Если нужно получить только список слов без контекста (для обратной совместимости)
        stopwords_list = []
        for sw in stopwords_data:
            word = sw.get("word", "").lower().strip()
            if word:
                stopwords_list.append(word)
        
        # Возвращаем как полные данные, так и список слов для совместимости
        return {
            "full_data": stopwords_data,
            "words_list": list(set(stopwords_list))
        }
    except Exception as e:
        logger.error(f"Ошибка при получении данных о стоп-словах: {e}")
        return {
            "full_data": [],
            "words_list": []
        }
