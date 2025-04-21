#!/usr/bin/env python3
import os
import sys
import re

def switch_mode(new_mode):
    """
    Переключает режим работы приложения между develop и production
    """
    if new_mode not in ['develop', 'production']:
        print(f"Ошибка: режим должен быть 'develop' или 'production', получено: '{new_mode}'")
        return False
        
    # Чтение файла .env
    try:
        with open('.env', 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"Ошибка при чтении файла .env: {e}")
        return False
        
    # Проверка наличия переменной MODE
    mode_pattern = re.compile(r'MODE\s*=\s*(\w+)')
    mode_match = mode_pattern.search(content)
    
    if mode_match:
        # Если переменная найдена, заменяем ее значение
        current_mode = mode_match.group(1)
        if current_mode == new_mode:
            print(f"Режим уже установлен в '{new_mode}'")
            return True
            
        content = mode_pattern.sub(f'MODE={new_mode}', content)
    else:
        # Если переменная не найдена, добавляем ее в конец файла
        content += f"\n# Режим работы приложения (develop или production)\nMODE={new_mode}\n"
    
    # Запись обновленного содержимого обратно в файл
    try:
        with open('.env', 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Режим успешно изменен на '{new_mode}'")
        return True
    except Exception as e:
        print(f"Ошибка при записи файла .env: {e}")
        return False

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Использование: python switch_mode.py [develop|production]")
        sys.exit(1)
    
    mode = sys.argv[1].lower()
    result = switch_mode(mode)
    
    if result:
        print(f"Для применения изменений перезапустите приложение")
        
        # Выводим сообщение о том, как перезапустить боты
        print("\nЧтобы перезапустить боты, выполните следующие команды:")
        print("pm2 restart candidate_bot")
        print("pm2 restart recruiter_bot")
    else:
        sys.exit(1) 