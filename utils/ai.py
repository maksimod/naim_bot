import re
import json
from log import logger
from settings import settings

async def verify_stopword_rephrasing_ai(original_sentence, rephrased_sentence, stopword_data, user_id=None):
    """Использует ИИ для проверки, правильно ли пользователь перефразировал предложение с стоп-словами"""
    # Логируем входные данные для отладки
    logger.info(f"Проверка перефразирования: Оригинал: '{original_sentence}', Ответ: '{rephrased_sentence}'")
    logger.info(f"Данные стоп-слова: {stopword_data}")
    
    try:
        # Извлекаем данные о стоп-слове
        stopword = stopword_data.get("word", "").lower()
        description = stopword_data.get("description", "")
        synonyms = stopword_data.get("synonyms", [])
        
        # Проверяем, что стоп-слово действительно есть в исходном предложении
        if stopword not in original_sentence.lower():
            logger.warning(f"Стоп-слово '{stopword}' отсутствует в оригинальном предложении: '{original_sentence}'")
            # Если исходное предложение не содержит стоп-слова, правильным будет идентичный ответ
            if original_sentence.lower() == rephrased_sentence.lower():
                return {
                    "preserves_meaning": True,
                    "excludes_stopword": True,
                    "used_synonym": False,
                    "detected_stopword": ""
                }
            else:
                return {
                    "preserves_meaning": False,
                    "excludes_stopword": True,
                    "used_synonym": False,
                    "detected_stopword": ""
                }
        
        # Простая проверка наличия стоп-слова и его синонимов
        detected_stopword = ""
        contains_stopword = False
        
        # Проверяем на наличие стоп-слова (с учетом словоформ)
        if stopword in rephrased_sentence.lower():
            # Проверяем, что это не часть другого слова
            words = re.findall(r'\b\w+\b', rephrased_sentence.lower())
            if stopword in words or f"{stopword}," in rephrased_sentence.lower() or f"{stopword}." in rephrased_sentence.lower():
                contains_stopword = True
                detected_stopword = stopword
        
        # Если стоп-слово не найдено напрямую, проверяем на синонимы
        if not contains_stopword and synonyms:
            for synonym in synonyms:
                synonym = synonym.lower()
                if synonym in rephrased_sentence.lower():
                    # Проверяем, что это не часть другого слова
                    words = re.findall(r'\b\w+\b', rephrased_sentence.lower())
                    if synonym in words or f"{synonym}," in rephrased_sentence.lower() or f"{synonym}." in rephrased_sentence.lower():
                        contains_stopword = True
                        detected_stopword = synonym
                        break
        
        # Если не удалось найти стоп-слово с помощью простой проверки, используем ИИ
        if not contains_stopword:
            # Подготавливаем запрос к API LLM
            prompt = f"""
            Задача: Определите, содержит ли перефразированное предложение стоп-слово или его синонимы, и сохраняет ли оно смысл оригинала.

            Оригинальное предложение: "{original_sentence}"
            Стоп-слово: "{stopword}"
            Описание стоп-слова: "{description}"
            Синонимы стоп-слова: {synonyms}
            
            Перефразированное предложение: "{rephrased_sentence}"
            
            Проверьте:
            1. Сохраняет ли перефразированное предложение смысл оригинального предложения.
            2. Исключает ли перефразированное предложение стоп-слово и его синонимы.
            3. Если стоп-слово или его синоним все еще присутствует, укажите какое именно слово обнаружено.
            
            Ответьте строго в формате JSON:
            {{
              "preserves_meaning": true/false,
              "excludes_stopword": true/false,
              "detected_stopword": ""  // Заполните, если найдено стоп-слово или синоним
            }}
            """
            
            # Отправляем запрос к ИИ и ожидаем ответ в формате JSON
            response = await get_openai_completion(
                prompt,
                llm_model=settings.DEFAULT_LLM_MODEL
            )
            
            try:
                # Обрабатываем ответ ИИ, извлекая JSON
                json_match = re.search(r'({.*})', response, re.DOTALL)
                if json_match:
                    json_str = json_match.group(1)
                    result = json.loads(json_str)
                    
                    # Логируем результат для отладки
                    logger.info(f"Результат ИИ: {result}")
                    
                    # Устанавливаем флаг использования синонима
                    used_synonym = False
                    if not result.get("excludes_stopword", True) and result.get("detected_stopword", ""):
                        detected_word = result.get("detected_stopword", "").lower()
                        if detected_word != stopword:
                            used_synonym = True
                    
                    # Обогащаем результат дополнительной информацией
                    result["used_synonym"] = used_synonym
                    
                    return result
                else:
                    logger.warning(f"Не удалось извлечь JSON из ответа ИИ: {response}")
            except json.JSONDecodeError as e:
                logger.error(f"Ошибка декодирования JSON: {e}. Ответ ИИ: {response}")
            except Exception as e:
                logger.error(f"Ошибка при обработке ответа ИИ: {e}")
        
        # Если ИИ не дал результата, возвращаем результат простой проверки
        return {
            "preserves_meaning": True,  # Предполагаем, что смысл сохранен
            "excludes_stopword": not contains_stopword,
            "used_synonym": detected_stopword in synonyms if detected_stopword else False,
            "detected_stopword": detected_stopword
        }
        
    except Exception as e:
        logger.error(f"Ошибка при проверке перефразирования: {e}")
        # В случае ошибки возвращаем максимально нейтральный результат
        return {
            "preserves_meaning": False,
            "excludes_stopword": False,
            "used_synonym": False,
            "detected_stopword": ""
        } 

async def generate_stopword_sentence_ai(stopword_data, language="ru", user_id=None, previous_sentences=None):
    """Генерирует предложение с использованием стоп-слова для тренировки"""
    try:
        word = stopword_data.get("word", "")
        description = stopword_data.get("description", "")
        examples = stopword_data.get("examples", [])
        
        # Логируем входящие данные
        logger.info(f"Генерация предложения со стоп-словом: {word}, описание: {description}")
        
        # Подготовка списка предыдущих предложений для избежания повторов
        previous_examples = []
        if previous_sentences and isinstance(previous_sentences, list):
            previous_examples = [s for s in previous_sentences if s][:5]  # ограничиваем 5 последними
        
        # Настраиваем промпт в зависимости от языка
        if language == "ru":
            prompt = f"""
            Создайте одно короткое и естественное предложение (7-15 слов) на русском языке, 
            которое включает слово "{word}" ровно один раз. 
            
            Описание слова: {description}
            
            Требования:
            1. Предложение должно быть простым и понятным
            2. Использовать стоп-слово "{word}" только ОДИН раз
            3. Предложение должно быть реалистичным и применимым в повседневной речи
            4. НЕ используйте другие стоп-слова и их синонимы в предложении
            5. Предложение должно отличаться от примеров, которые уже были использованы
            
            Примеры предложений с этим словом: {examples}
            
            Предыдущие сгенерированные предложения (ИЗБЕГАЙТЕ ПОВТОРЕНИЙ):
            {previous_examples}
            
            Предложение:
            """
        else:  # английский по умолчанию
            prompt = f"""
            Create one short and natural sentence (7-15 words) in English 
            that includes the word "{word}" exactly once.
            
            Word description: {description}
            
            Requirements:
            1. The sentence should be simple and clear
            2. Use the stopword "{word}" only ONCE
            3. The sentence should be realistic and applicable in everyday speech
            4. DO NOT use other stopwords or their synonyms in the sentence
            5. The sentence should be different from examples that have already been used
            
            Example sentences with this word: {examples}
            
            Previously generated sentences (AVOID REPETITION):
            {previous_examples}
            
            Sentence:
            """
        
        # Получение ответа от LLM
        response = await get_openai_completion(
            prompt,
            llm_model=settings.DEFAULT_LLM_MODEL
        )
        
        # Очистка ответа
        sentence = response.strip().strip('"\'')
        
        # Дополнительная проверка качества
        word_count = len(sentence.split())
        contains_stopword = word.lower() in sentence.lower().split()
        
        # Логирование результата
        logger.info(f"Сгенерировано предложение: '{sentence}' (слов: {word_count}, содержит стоп-слово: {contains_stopword})")
        
        # Проверка на соответствие требованиям
        if 4 <= word_count <= 20 and contains_stopword:
            return sentence
        else:
            # Повторная попытка, если предложение не соответствует требованиям
            logger.warning(f"Сгенерированное предложение не соответствует требованиям. Повторная попытка...")
            return await generate_stopword_sentence_ai(stopword_data, language, user_id, previous_sentences)
    
    except Exception as e:
        logger.error(f"Ошибка при генерации предложения: {e}")
        # Fallback к простому предложению в случае ошибки
        if language == "ru":
            return f"В этом предложении используется стоп-слово {word}."
        else:
            return f"This sentence uses the stopword {word}." 