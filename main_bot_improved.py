            shell=True,
            capture_output=True,
            text=True,
            encoding='cp866',
            timeout=30
        )
        return result.stdout if result.returncode == 0 else f"Ошибка: {result.stderr}"
    except subprocess.TimeoutExpired:
        logger.error(f"Таймаут выполнения команды: {cmd}")
        return "Ошибка: команда превысила лимит времени (30 сек)"
    except Exception as e:
        logger.error(f"Ошибка выполнения команды {cmd}: {e}")
        raise

# --- OTA СИСТЕМА ОБНОВЛЕНИЙ ---

@async_task
def download_update(url):
    """Скачивание обновления по URL"""
    try:
        # Обработка Dropbox ссылок
        if "dropbox.com" in url and "dl=0" in url:
            url = url.replace("dl=0", "dl=1")
        
        temp_dir = tempfile.mkdtemp(prefix="bot_update_")
        zip_path = os.path.join(temp_dir, "update.zip")
        
        logger.info(f"Скачивание обновления из {url} в {zip_path}")
        
        # Скачивание файла
        urllib.request.urlretrieve(url, zip_path)
        
        return zip_path, temp_dir
    except Exception as e:
        logger.error(f"Ошибка скачивания обновления: {e}")
        raise

@async_task
def apply_update(zip_path, temp_dir):
    """Применение обновления из ZIP-архива"""
    try:
        # Распаковка архива
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)
        
        # Создание батника для обновления
        bat_content = f"""@echo off
timeout /t 3 /nobreak >nul
taskkill /F /IM python.exe 2>nul
taskkill /F /IM bot.exe 2>nul
xcopy /Y /E "{temp_dir}\\*" "{os.path.dirname(os.path.abspath(__file__))}"
start "" "{sys.executable}" main_bot.py
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

# --- ОСНОВНЫЕ КОМАНДЫ ---

@bot.message_handler(commands=['start'])
@command_handler
def start_command(message):
    """Команда /start - приветствие и регистрация устройства"""
    user_id = message.from_user.id
    
    # Регистрация устройства
    register_device()
    
    # Добавление SuperAdmin при первом запуске
    if not db.get_admin(SUPER_ADMIN_ID):
        db.add_admin(SUPER_ADMIN_ID, "SuperAdmin", ROLE_SUPER_ADMIN)
        logger.info(f"SuperAdmin добавлен: {SUPER_ADMIN_ID}")
    
    # Добавление текущего пользователя как администратора, если его нет
    if not db.get_admin(user_id):
        username = message.from_user.username or f"user_{user_id}"
        db.add_admin(user_id, username, ROLE_ADMIN)
        logger.info(f"Новый администратор добавлен: {user_id}")
    
    welcome_text = f"""
🎮 <b>Удаленный администратор v16.0</b>

✅ Устройство зарегистрировано: <b>{CURRENT_DEVICE_NAME}</b>
🆔 HWID: <code>{CURRENT_HWID}</code>

📋 <b>Основные команды:</b>
/panel - Панель управления
/pc_list - Список устройств
/info - Информация об устройстве
/screen - Скриншот экрана
/procs - Список процессов

👨‍💼 <b>Администрирование:</b>
/admin_list - Список администраторов
/add_admin - Добавить администратора (SuperAdmin)
/del_admin - Удалить администратора (SuperAdmin)

⚙️ <b>Система:</b>
/update_url - OTA обновление
/wd_on - Включить Watchdog
/wd_off - Выключить Watchdog

Ваша роль: <b>{get_admin_role(user_id) or 'admin'}</b>
"""
    
    bot.reply_to(message, welcome_text, parse_mode='HTML')
    db.log_action(user_id, None, "start_command")

@bot.message_handler(commands=['panel'])
@command_handler
def panel_command(message):
    """Команда /panel - главная панель управления с выбором устройства"""
    user_id = message.from_user.id
    
    # Получаем список устройств
    devices = db.get_all_devices()
    
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
    
    # Кнопки действий
    markup.row(
        types.InlineKeyboardButton("🔄 Обновить список", callback_data="refresh_devices"),
        types.InlineKeyboardButton("➕ Добавить устройство", callback_data="add_device")
    )
    markup.row(
        types.InlineKeyboardButton("📸 Скриншот", callback_data="action_screen"),
        types.InlineKeyboardButton("🖥 Процессы", callback_data="action_procs")
    )
    markup.row(
        types.InlineKeyboardButton("🔒 Блокировка", callback_data="action_lock_confirm"),
        types.InlineKeyboardButton("⏻ Выключение", callback_data="action_shutdown_confirm")
    )
    markup.row(
        types.InlineKeyboardButton("💻 CMD", callback_data="action_cmd_menu"),
        types.InlineKeyboardButton("ℹ️ Инфо", callback_data="action_info")
    )
    
    # Текущее выбранное устройство
    session = get_admin_session(user_id)
    current_device = "Текущее" if not session or not session.get('device_hwid') else db.get_device(session.get('device_hwid')).get('device_name', 'Unknown')
    
    text = f"""
🎛 <b>Главная панель управления</b>

📱 <b>Доступные устройства:</b> {len(devices)}
🎯 <b>Текущее устройство:</b> <code>{current_device}</code>

Выберите устройство или действие:
"""
    
    bot.reply_to(message, text, reply_markup=markup, parse_mode='HTML')
    db.log_action(user_id, None, "panel_command")

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
        
        # Статус Watchdog
        status_icon = "🟢" if watchdog_status == 'active' else "🔴" if watchdog_status == 'stopped' else "🟡"
        
        text += f"{i}. <b>{device_name}</b>\n"
        text += f"   🆔 HWID: <code>{device_hwid[:8]}...</code>\n"
        text += f"   📍 IP: {ip_address}\n"
        text += f"   ⏰ Последняя активность: {last_str}\n"
        text += f"   🐕 Watchdog: {status_icon} {watchdog_status}\n\n"
    
    bot.reply_to(message, text, parse_mode='HTML')
    db.log_action(user_id, None, "pc_list_command")

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
    ip_address = device.get('ip_address', 'N/A')
    
    # Системная информация
    try:
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        memory_percent = memory.percent
        memory_total = memory.total / (1024**3)  # GB
        memory_used = memory.used / (1024**3)    # GB
        
        disk = psutil.disk_usage('/')
        disk_percent = disk.percent
        disk_total = disk.total / (1024**3)      # GB
        disk_used = disk.used / (1024**3)        # GB
        
        boot_time = datetime.fromtimestamp(psutil.boot_time())
        uptime = datetime.now() - boot_time
        uptime_hours = int(uptime.total_seconds() / 3600)
        uptime_minutes = int((uptime.total_seconds() % 3600) / 60)
        
        system_info = f"""
💻 <b>Системная информация:</b>
🖥 CPU: {cpu_percent}%
🧠 ОЗУ: {memory_percent}% ({memory_used:.1f}/{memory_total:.1f} GB)
💾 Диск: {disk_percent}% ({disk_used:.1f}/{disk_total:.1f} GB)
⏱ Аптайм: {uptime_hours}ч {uptime_minutes}мин
"""
    except Exception as e:
        logger.error(f"Ошибка получения системной информации: {e}")
        system_info = "\n⚠️ Не удалось получить системную информацию"
    
    text = f"""
📊 <b>Информация об устройстве</b>

<b>Имя:</b> {device_name}
<b>HWID:</b> <code>{target_hwid}</code>
<b>IP:</b> {ip_address}
<b>Последняя активность:</b> {last_online}
{system_info}
"""
    
    bot.reply_to(message, text, parse_mode='HTML')
    db.log_action(user_id, target_hwid, "info_command")

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
        
        with open(screenshot_path, 'rb') as photo:
            bot.send_photo(message.chat.id, photo, caption="📸 Скриншот экрана")
        
        # Удаляем временный файл
        os.remove(screenshot_path)
        
        db.log_action(user_id, target_hwid, "screen_command")
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка создания скриншота: {e}")

@bot.message_handler(commands=['procs'])
@command_handler
def procs_command(message):
    """Команда /procs - список процессов"""
    user_id = message.from_user.id
    target_hwid = get_target_device_hwid(user_id)
    
    if target_hwid != CURRENT_HWID:
        bot.reply_to(message, "⚠️ Команда доступна только для текущего устройства.")
        return
    
    try:
        processes = get_process_list()
        
        text = "🖥 <b>Топ-20 процессов по использованию CPU:</b>\n\n"
        
        # Сортируем по использованию CPU
        sorted_procs = sorted(processes, key=lambda x: x.get('cpu_percent', 0), reverse=True)[:20]
        
        for i, proc in enumerate(sorted_procs, 1):
            name = escape_html(proc.get('name', 'Unknown'))
            pid = proc.get('pid', 'N/A')
            cpu = proc.get('cpu_percent', 0)
            memory = proc.get('memory_percent', 0)
            
            text += f"{i}. <b>{name}</b> (PID: {pid})\n"
            text += f"   CPU: {cpu:.1f}% | ОЗУ: {memory:.1f}%\n"
        
        bot.reply_to(message, text, parse_mode='HTML')
        db.log_action(user_id, target_hwid, "procs_command")
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка получения списка процессов: {e}")

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
    """Команда /lock - блокировка компьютера"""
    user_id = message.from_user.id
    target_hwid = get_target_device_hwid(user_id)
    
    if target_hwid != CURRENT_HWID:
        bot.reply_to(message, "⚠️ Команда доступна только для текущего устройства.")
        return
    
    # Подтверждение через inline-кнопки
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("✅ Да, заблокировать", callback_data="lock_confirm"),
        types.In
