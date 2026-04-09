PER_ADMIN else "👤" if role == ROLE_ADMIN else "👥"
        
        text += f"{i}. {role_icon} <b>{username}</b> (ID: {admin_id})\n"
        text += f"   Роль: <b>{role}</b>\n"
        text += f"   Добавлен: {created_at[:10] if len(created_at) > 10 else created_at}\n\n"
    
    bot.reply_to(message, text, parse_mode='HTML')
    db.log_action(user_id, None, "admin_list_command")

@bot.message_handler(commands=['add_admin'])
@command_handler
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
@command_handler
def del_admin_cmd(message):
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
            db.log_action(user_id, None, "del_admin", f"Deleted admin {admin_id_to_delete}")
        else:
            bot.reply_to(message, "❌ Ошибка удаления администратора.")
    except ValueError:
        bot.reply_to(message, "❌ Неверный формат ID. ID должен быть числом.")
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")

@bot.message_handler(commands=['update_url'])
@command_handler
def update_url_command(message):
    """Команда /update_url - OTA обновление по ссылке"""
    user_id = message.from_user.id
    
    if not check_permission(user_id, ROLE_SUPER_ADMIN):
        bot.reply_to(message, "❌ Недостаточно прав. Только SuperAdmin может обновлять систему.")
        return
    
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, "⚠️ Использование: /update_url <ссылка_на_zip_архив>")
        return
    
    url = args[1]
    
    try:
        bot.reply_to(message, "🔄 Начинаю загрузку обновления...")
        
        # Скачиваем обновление
        zip_path, temp_dir = download_update(url)
        
        # Применяем обновление
        if apply_update(zip_path, temp_dir):
            bot.reply_to(message, "✅ Обновление успешно установлено. Система перезагружается...")
            
            # Завершаем работу бота для перезагрузки
            time.sleep(2)
            sys.exit(0)
        else:
            bot.reply_to(message, "❌ Ошибка применения обновления.")
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка обновления: {e}")

@bot.message_handler(commands=['wd_on', 'wd_off'])
@command_handler
def watchdog_control_command(message):
    """Команды управления Watchdog: /wd_on и /wd_off"""
    user_id = message.from_user.id
    target_hwid = get_target_device_hwid(user_id)
    
    if target_hwid != CURRENT_HWID:
        bot.reply_to(message, "⚠️ Команда доступна только для текущего устройства.")
        return
    
    command = message.text.split()[0]
    
    if command == '/wd_on':
        new_status = 'active'
        status_text = "включен"
    else:
        new_status = 'stopped'
        status_text = "выключен"
    
    if db.update_watchdog_status(CURRENT_HWID, new_status):
        bot.reply_to(message, f"✅ Watchdog {status_text} для текущего устройства.")
        db.log_action(user_id, CURRENT_HWID, f"watchdog_{new_status}")
    else:
        bot.reply_to(message, f"❌ Ошибка изменения статуса Watchdog.")

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
                    
                    # Обновляем сообщение
                    text = f"🎯 <b>Устройство выбрано:</b> {device_name}\n\nТеперь все команды будут отправляться на это устройство."
                    bot.edit_message_text(text, chat_id, message_id, parse_mode='HTML')
                else:
                    bot.answer_callback_query(call.id, "❌ Ошибка выбора устройства.")
            else:
                bot.answer_callback_query(call.id, "❌ Устройство не найдено.")
        
        # Обновление списка устройств
        elif data == 'refresh_devices':
            bot.answer_callback_query(call.id, "🔄 Обновляю список устройств...")
            # Здесь можно добавить логику обновления списка
            time.sleep(1)
            bot.answer_callback_query(call.id, "✅ Список обновлен.")
        
        # Скриншот
        elif data == 'action_screen':
            bot.answer_callback_query(call.id, "📸 Делаю скриншот...")
            
            try:
                screenshot_path = take_screenshot()
                
                with open(screenshot_path, 'rb') as photo:
                    bot.send_photo(chat_id, photo, caption="📸 Скриншот экрана")
                
                os.remove(screenshot_path)
                db.log_action(user_id, get_target_device_hwid(user_id), "screen_from_panel")
            except Exception as e:
                bot.answer_callback_query(call.id, f"❌ Ошибка: {str(e)[:50]}")
        
        # Список процессов
        elif data == 'action_procs':
            bot.answer_callback_query(call.id, "🖥 Получаю список процессов...")
            
            try:
                processes = get_process_list()
                
                text = "🖥 <b>Топ-10 процессов по использованию CPU:</b>\n\n"
                
                sorted_procs = sorted(processes, key=lambda x: x.get('cpu_percent', 0), reverse=True)[:10]
                
                for i, proc in enumerate(sorted_procs, 1):
                    name = escape_html(proc.get('name', 'Unknown'))
                    pid = proc.get('pid', 'N/A')
                    cpu = proc.get('cpu_percent', 0)
                    memory = proc.get('memory_percent', 0)
                    
                    text += f"{i}. <b>{name}</b> (PID: {pid})\n"
                    text += f"   CPU: {cpu:.1f}% | ОЗУ: {memory:.1f}%\n"
                
                bot.send_message(chat_id, text, parse_mode='HTML')
                db.log_action(user_id, get_target_device_hwid(user_id), "procs_from_panel")
            except Exception as e:
                bot.answer_callback_query(call.id, f"❌ Ошибка: {str(e)[:50]}")
        
        # Подтверждение блокировки
        elif data == 'lock_confirm':
            bot.answer_callback_query(call.id, "🔒 Блокирую компьютер...")
            
            try:
                if lock_computer():
                    bot.send_message(chat_id, "✅ Компьютер заблокирован.")
                    db.log_action(user_id, get_target_device_hwid(user_id), "lock_computer")
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
                if shutdown_computer(delay=10):
                    bot.send_message(chat_id, "✅ Компьютер будет выключен через 10 секунд.")
                    db.log_action(user_id, get_target_device_hwid(user_id), "shutdown_computer")
                else:
                    bot.send_message(chat_id, "❌ Ошибка выключения компьютера.")
            except Exception as e:
                bot.send_message(chat_id, f"❌ Ошибка: {e}")
        
        # Отмена выключения
        elif data == 'poweroff_cancel':
            bot.answer_callback_query(call.id, "❌ Выключение отменено.")
            bot.send_message(chat_id, "❌ Выключение компьютера отменено.")
        
        # Информация об устройстве
        elif data == 'action_info':
            bot.answer_callback_query(call.id, "ℹ️ Получаю информацию...")
            
            target_hwid = get_target_device_hwid(user_id)
            device = db.get_device(target_hwid)
            
            if device:
                device_name = device.get('device_name', 'Unknown')
                text = f"📊 <b>Информация об устройстве:</b>\n\n"
                text += f"<b>Имя:</b> {device_name}\n"
                text += f"<b>HWID:</b> <code>{target_hwid}</code>\n"
                text += f"<b>Последняя активность:</b> {device.get('last_online', 'Never')}\n"
                text += f"<b>Статус Watchdog:</b> {device.get('watchdog_status', 'unknown')}"
                
                bot.send_message(chat_id, text, parse_mode='HTML')
            else:
                bot.send_message(chat_id, "❌ Устройство не найдено.")
        
        else:
            bot.answer_callback_query(call.id, "⚠️ Неизвестная команда.")
    
    except Exception as e:
        logger.error(f"Ошибка обработки callback: {e}\n{traceback.format_exc()}")
        bot.answer_callback_query(call.id, "❌ Ошибка обработки команды.")

# --- ЗАПУСК БОТА ---

def main():
    """Основная функция запуска бота"""
    logger.info("=== Запуск основного бота системы мульти-администраторов ===")
    logger.info(f"Версия: 16.0")
    logger.info(f"Текущее устройство: {CURRENT_DEVICE_NAME}")
    logger.info(f"HWID: {CURRENT_HWID}")
    
    # Регистрация устройства
    register_device()
    
    # Добавление SuperAdmin при первом запуске
    if not db.get_admin(SUPER_ADMIN_ID):
        db.add_admin(SUPER_ADMIN_ID, "SuperAdmin", ROLE_SUPER_ADMIN)
        logger.info(f"SuperAdmin добавлен: {SUPER_ADMIN_ID}")
    
    logger.info("Бот запущен и готов к работе")
    
    # Бесконечный цикл опроса с обработкой ошибок
    while True:
        try:
            bot.polling(none_stop=True, interval=1, timeout=30)
        except Exception as e:
            logger.error(f"Ошибка в основном цикле бота: {e}")
            logger.info(f"Повторная попытка через 10 секунд...")
            time.sleep(10)

if __name__ == "__main__":
    main()