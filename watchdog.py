# watchdog.py
"""
Система "Сторожевой пес" - защищает основной бот от остановки
При запуске создает мьютекс для предотвращения множественных запусков
Если основной бот падает, watchdog автоматически его перезапускает
Двухкомпонентная архитектура: watchdog + main_bot
"""

import win32event
import win32api
import subprocess
import sys
import time
import os
import psutil
import logging

# Импорт конфигурации
from config import *

# Настройка логирования с кодировкой UTF-8
import codecs
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(WATCHDOG_LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class DoubleWatchdog:
    """Двойной страж - мониторинг и восстановление основного бота"""
    
    def __init__(self):
        self.main_process = None
        self.restart_attempts = 0
        self.mutex = None
        self.is_running = True
        self.crash_loop_detected = False
        self.last_crash_time = 0

    def create_mutex(self):
        """
        Создание мьютекса для предотвращения множественных запусков
        Возвращает False если мьютекс уже существует (другой процесс запущен)
        """
        try:
            self.mutex = win32event.CreateMutex(None, False, MUTEX_NAME)
            if win32api.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
                logger.warning("Мьютекс уже существует. Другой процесс watchdog уже запущен.")
                return False
            logger.info("Мьютекс создан успешно")
            return True
        except Exception as e:
            logger.error(f"Ошибка создания мьютекса: {e}")
            return False

    def is_main_bot_running(self):
        """Проверка наличия процесса main_bot.py или mainbot.exe"""
        try:
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    proc_name = proc.info['name'].lower()
                    
                    # Проверяем скомпилированный mainbot.exe
                    if proc_name == 'mainbot.exe':
                        return True
                    
                    # Проверяем скрипт python с main_bot.py
                    if proc_name == 'python.exe' and proc.info['cmdline']:
                        cmdline = ' '.join(proc.info['cmdline']).lower()
                        if 'main_bot.py' in cmdline and 'watchdog.py' not in cmdline:
                            return True
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception as e:
            logger.error(f"Ошибка проверки процессов: {e}")
        
        return False

    def start_main_bot(self):
        """
        Запуск основного бота в скрытом режиме
        Возвращает True при успешном запуске
        """
        try:
            # Проверяем, запущен ли watchdog в скомпилированном режиме
            if getattr(sys, 'frozen', False):
                # Скомпилированный режим: запускаем mainbot.exe
                base_dir = os.path.dirname(sys.executable)
                exe_path = os.path.join(base_dir, 'mainbot.exe')
                
                if not os.path.exists(exe_path):
                    logger.error(f"Файл mainbot.exe не найден: {exe_path}")
                    return False
                
                self.main_process = subprocess.Popen(
                    [exe_path],
                    creationflags=subprocess.CREATE_NO_WINDOW,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
            else:
                # Режим скрипта: запускаем main_bot.py
                python_exec = sys.executable
                script_path = os.path.abspath("main_bot.py")
                
                if not os.path.exists(script_path):
                    logger.error(f"Файл main_bot.py не найден: {script_path}")
                    return False
                
                self.main_process = subprocess.Popen(
                    [python_exec, script_path],
                    creationflags=subprocess.CREATE_NO_WINDOW,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
            
            self.restart_attempts = 0
            logger.info("Основной бот запущен успешно")
            return True
        except Exception as e:
            logger.error(f"Ошибка запуска main_bot: {e}")
            return False

    def stop_main_bot(self):
        """Остановка основного бота"""
        if self.main_process and self.main_process.poll() is None:
            try:
                logger.info("Останавливаю основной бот...")
                self.main_process.terminate()
                self.main_process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                logger.warning("Принудительное завершение основного бота...")
                self.main_process.kill()
            except Exception as e:
                logger.error(f"Ошибка остановки основного бота: {e}")
            finally:
                self.main_process = None

    def check_crash_loop(self):
        """Проверка на циклические краши (crash loop)"""
        current_time = time.time()
        
        if self.restart_attempts >= MAX_RESTART_ATTEMPTS:
            # Если было много перезапусков за короткое время
            if current_time - self.last_crash_time < CRASH_LOOP_DELAY * 2:
                self.crash_loop_detected = True
                logger.warning(f"Обнаружен crash loop! Задержка {CRASH_LOOP_DELAY} секунд")
                return True
        
        self.last_crash_time = current_time
        return False

    def run(self):
        """Основной цикл watchdog"""
        logger.info("=== Запуск Watchdog системы ===")
        logger.info(f"Mutex: {MUTEX_NAME}")
        logger.info(f"Интервал проверки: {WATCHDOG_POLL_INTERVAL} сек")
        logger.info(f"Макс. попыток перезапуска: {MAX_RESTART_ATTEMPTS}")
        
        if not self.create_mutex():
            # Если мьютекс уже существует, значит main_bot уже запущен
            logger.info("Другой экземпляр watchdog уже запущен. Завершаюсь.")
            sys.exit(0)

        # Запускаем main_bot при старте watchdog
        if not self.start_main_bot():
            logger.error("Не удалось запустить основной бот при старте")
            sys.exit(1)

        logger.info("Watchdog запущен и мониторит основной бот")
        
        while self.is_running:
            try:
                if not self.is_main_bot_running():
                    logger.warning("Основной бот не запущен!")
                    
                    # Проверяем на crash loop
                    if self.check_crash_loop():
                        logger.warning(f"Crash loop обнаружен. Задержка {CRASH_LOOP_DELAY} секунд...")
                        time.sleep(CRASH_LOOP_DELAY)
                        self.restart_attempts = 0
                        self.crash_loop_detected = False
                        continue
                    
                    # Если main_bot не запущен, пытаемся его перезапустить
                    if self.restart_attempts < MAX_RESTART_ATTEMPTS:
                        self.restart_attempts += 1
                        logger.info(f"Попытка перезапуска {self.restart_attempts}/{MAX_RESTART_ATTEMPTS}")
                        time.sleep(1)  # Небольшая задержка перед перезапуском
                        
                        if not self.start_main_bot():
                            logger.error(f"Не удалось перезапустить основной бот (попытка {self.restart_attempts})")
                    else:
                        # Превышено количество попыток перезапуска
                        logger.error(f"Превышено максимальное количество попыток перезапуска ({MAX_RESTART_ATTEMPTS})")
                        logger.warning(f"Ожидание {WATCHDOG_POLL_INTERVAL} секунд перед следующей проверкой...")
                        time.sleep(WATCHDOG_POLL_INTERVAL)
                else:
                    # Основной бот работает нормально
                    if self.restart_attempts > 0:
                        logger.info("Основной бот восстановлен. Сброс счетчика попыток.")
                        self.restart_attempts = 0
                        self.crash_loop_detected = False
                
                time.sleep(WATCHDOG_POLL_INTERVAL)
                
            except KeyboardInterrupt:
                logger.info("Получен сигнал KeyboardInterrupt. Завершаю работу...")
                self.is_running = False
            except Exception as e:
                logger.error(f"Неожиданная ошибка в цикле watchdog: {e}")
                time.sleep(WATCHDOG_POLL_INTERVAL)

        # Очистка при выходе
        logger.info("Завершение работы watchdog...")
        self.stop_main_bot()
        
        if self.mutex:
            try:
                win32api.CloseHandle(self.mutex)
                logger.info("Мьютекс освобожден")
            except Exception as e:
                logger.error(f"Ошибка освобождения мьютекса: {e}")
        
        logger.info("Watchdog завершил работу")


if __name__ == "__main__":
    watchdog = DoubleWatchdog()
    watchdog.run()