#!/usr/bin/env python3
"""
Скрипт для быстрого развертывания бота на новом устройстве
Использование: python deploy_device.py
"""

import json
import os
import sys
import shutil
import socket

def create_device_config():
    print("=== НАСТРОЙКА НОВОГО УСТРОЙСТВА ===\n")
    
    # Получаем данные от пользователя
    device_id = input("ID устройства (например, child1, child2): ").strip()
    if not device_id:
        device_id = f"device_{socket.gethostname().lower()}"
        print(f"Использую автоматический ID: {device_id}")
    
    api_token = input("API Token Telegram бота: ").strip()
    if not api_token:
        print("❌ API Token обязателен!")
        return False
    
    admin_id = input("Admin ID (Telegram ID родителя): ").strip()
    if not admin_id:
        print("❌ Admin ID обязателен!")
        return False
    
    try:
        admin_id = int(admin_id)
    except:
        print("❌ Admin ID должен быть числом!")
        return False
    
    device_name = input(f"Имя устройства (по умолчанию: {socket.gethostname()}): ").strip()
    if not device_name:
        device_name = socket.gethostname()
    
    description = input("Описание устройства (необязательно): ").strip()
    
    # Создаем конфигурацию
    config = {
        "devices": {
            device_id: {
                "api_token": api_token,
                "admin_id": admin_id,
                "device_name": device_name,
                "description": description
            }
        },
        "current_device": device_id
    }
    
    # Сохраняем конфигурацию
    try:
        with open("config.json", "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        
        print(f"\n✅ Конфигурация создана!")
        print(f"📱 Устройство: {device_name}")
        print(f"🆔 ID: {device_id}")
        print(f"🔑 Token: {api_token[:10]}...")
        print(f"👤 Admin: {admin_id}")
        
        return True
    except Exception as e:
        print(f"❌ Ошибка сохранения: {e}")
        return False

def copy_bot_files():
    """Копирование файлов бота"""
    required_files = ["main_bot.py", "watchdog.py"]
    
    print("\n=== КОПИРОВАНИЕ ФАЙЛОВ ===")
    
    for file in required_files:
        if os.path.exists(file):
            print(f"✅ {file} найден")
        else:
            print(f"❌ {file} не найден!")
            return False
    
    print("✅ Все файлы на месте")
    return True

def create_startup_script():
    """Создание скрипта автозапуска"""
    script_content = f"""@echo off
cd /d "{os.getcwd()}"
python watchdog.py
pause
"""
    
    try:
        with open("start_bot.bat", "w", encoding="cp1251") as f:
            f.write(script_content)
        print("✅ Скрипт запуска создан: start_bot.bat")
        return True
    except Exception as e:
        print(f"❌ Ошибка создания скрипта: {e}")
        return False

def main():
    print("🤖 Развертывание системы родительского контроля v14.0")
    print("=" * 50)
    
    # Проверяем наличие основных файлов бота
    if not os.path.exists("main_bot.py") or not os.path.exists("watchdog.py"):
        print("❌ Файлы main_bot.py и watchdog.py не найдены!")
        print("Убедитесь, что вы запускаете скрипт в правильной папке.")
        return
    
    # Создаем конфигурацию
    if not create_device_config():
        return
    
    # Копируем файлы
    if not copy_bot_files():
        return
    
    # Создаем скрипт запуска
    create_startup_script()
    
    print("\n" + "=" * 50)
    print("🎉 РАЗВЕРТЫВАНИЕ ЗАВЕРШЕНО!")
    print("\nДля запуска бота:")
    print("1. Запустите start_bot.bat")
    print("2. Или выполните: python watchdog.py")
    print("\nДля добавления в автозагрузку используйте команду /start в боте")

if __name__ == "__main__":
    main()