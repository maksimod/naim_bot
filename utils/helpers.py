import json
import logging
from pathlib import Path

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
                return questions
            elif isinstance(data, list):
                # Уже в правильном формате или близком к нему
                return data
            return data
    except Exception as e:
        logger.error(f"Error loading test questions from {filename}: {e}")
        return None
