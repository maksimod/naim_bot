#!/bin/bash

# Путь к директории с репозиторием
REPO_DIR="/home/user/naim_bot"
LOG_FILE="$REPO_DIR/update.log"

# Функция для очистки лог-файла (оставляет 1000 последних строк)
cleanup_log() {
    if [ -f "$LOG_FILE" ]; then
        local line_count=$(wc -l < "$LOG_FILE")
        if [ "$line_count" -gt 1000 ]; then
            tail -n 1000 "$LOG_FILE" > "$LOG_FILE.tmp"
            mv "$LOG_FILE.tmp" "$LOG_FILE"
            echo "[$(date '+%Y-%m-%d %H:%M:%S')] Лог-файл очищен, оставлено 1000 последних строк" >> "$LOG_FILE"
        fi
    fi
}

# Функция для логирования
log_message() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
}

# Очищаем лог-файл перед началом работы
cleanup_log

log_message "Начинаю проверку обновлений в репозитории"

# Определяем полный путь к pm2
PM2_PATH=$(which pm2)
if [ -z "$PM2_PATH" ]; then
    # Если which не нашел pm2, попробуем использовать наиболее вероятные пути
    if [ -f "/usr/local/bin/pm2" ]; then
        PM2_PATH="/usr/local/bin/pm2"
    elif [ -f "/usr/bin/pm2" ]; then
        PM2_PATH="/usr/bin/pm2"
    elif [ -f "$HOME/.nvm/versions/node/*/bin/pm2" ]; then
        PM2_PATH=$(find $HOME/.nvm/versions/node -name pm2 -type f | head -1)
    elif [ -f "$HOME/.npm-global/bin/pm2" ]; then
        PM2_PATH="$HOME/.npm-global/bin/pm2"
    else
        # Последняя попытка - найти через 'find'
        PM2_PATH=$(find /usr -name pm2 -type f 2>/dev/null | head -1)
    fi
fi

log_message "Использую pm2 по пути: $PM2_PATH"

# Если pm2 не найден, используем экспорт из .bashrc или .profile
if [ -z "$PM2_PATH" ]; then
    log_message "PM2 не найден. Пробуем загрузить пользовательское окружение"
    
    # Загружаем пользовательское окружение
    if [ -f "$HOME/.bashrc" ]; then
        source "$HOME/.bashrc"
    fi
    
    if [ -f "$HOME/.profile" ]; then
        source "$HOME/.profile"
    fi
    
    # Пробуем найти pm2 снова
    PM2_PATH=$(which pm2)
    log_message "После загрузки окружения pm2 найден по пути: $PM2_PATH"
fi

# Если pm2 все еще не найден, выходим с ошибкой
if [ -z "$PM2_PATH" ]; then
    log_message "ОШИБКА: Не удалось найти исполняемый файл pm2. Перезапуск невозможен."
    exit 1
fi

# Переход в директорию репозитория
cd $REPO_DIR || {
    log_message "ОШИБКА: Не удалось перейти в директорию репозитория $REPO_DIR"
    exit 1
}
log_message "Перешел в директорию репозитория: $REPO_DIR"

# Сохраняем текущий хеш коммита
CURRENT_HASH=$(git rev-parse HEAD)
log_message "Текущий хеш коммита: $CURRENT_HASH"

# Обновляем информацию о репозитории
git fetch origin main
log_message "Выполнен git fetch"

# Проверяем, есть ли изменения
UPSTREAM_HASH=$(git rev-parse origin/main)
log_message "Хеш коммита в origin/main: $UPSTREAM_HASH"

if [ "$CURRENT_HASH" != "$UPSTREAM_HASH" ]; then
    log_message "Обнаружены изменения, выполняю git pull..."
    
    # Выполняем git pull
    git pull origin main
    PULL_RESULT=$?
    
    if [ $PULL_RESULT -eq 0 ]; then
        log_message "Git pull успешно выполнен"
        
        # Добавляем задержку перед перезапуском
        log_message "Ожидаю 10 секунд перед перезапуском PM2 процессов..."
        sleep 10
        
        # Перезапускаем PM2 процессы
        log_message "Перезапускаю candidate_bot..."
        $PM2_PATH restart candidate_bot
        CANDIDATE_RESULT=$?
        
        log_message "Перезапускаю recruiter_bot..."
        $PM2_PATH restart recruiter_bot
        RECRUITER_RESULT=$?
        
        if [ $CANDIDATE_RESULT -eq 0 ] && [ $RECRUITER_RESULT -eq 0 ]; then
            log_message "Все PM2 процессы успешно перезапущены"
        else
            log_message "ОШИБКА: Не удалось перезапустить один или оба PM2 процесса"
        fi
    else
        log_message "ОШИБКА: Не удалось выполнить git pull"
    fi
else
    log_message "Изменений не обнаружено, перезапуск не требуется"
fi

log_message "Проверка обновлений завершена"

# Очищаем лог-файл после завершения работы
cleanup_log