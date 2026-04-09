#!/usr/bin/env python3
"""
Скрипт для массового обновления всех устройств
"""

import json
import os
import sys
import subprocess
import time
import urllib.request
import tempfile

def load_config():
    try:
        with open("config.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        print("❌ Файл config.json не найден!")
        return None

def download_update(url):
    """Скачивание файла обновления"""
    try:
        print(f"⬇️ Скачиваю обновление: {url}")
        
        # Определяем имя файла
        filename = url.split('/')[-1].split('?')[0]
        if not (filename.endswith('.exe') or filename.endswith('.zip')):
            filename = "update.exe"
        
        # Скачиваем во временную папку
        temp_dir = tempfile.gettempdir()
        temp_path = os.path.join(temp_dir, f"bot_update_{int(time.time())}_{filename}")
        
        urllib.request.urlretrieve(url, temp_path)
        print(f"✅ Файл скачан: {temp_path}")
        return temp_path
    except Exception as e:
        print(f"❌ Ошибка скачивания: {e}")
        return None

def update_device(device_id, device_config, update_file):
    """Обновление конкретного устройства"""
    print(f"\n🔄 Обновление устройства: {device_id}")
    print(f"   📝 Имя: {device_config['device_name']}")
    
    try:
        # Создаем временную конфигурацию для этого устройства
        temp_config = {
            "devices": {device_id: device_config},
            "current_device": device_id
        }
        
        temp_config_file = f"temp_config_{device_id}.json"
        with open(temp_config_file, "w", encoding="utf-8") as f:
            json.dump(temp_config, f, ensure_ascii=False, indent=2)
        
        # Запускаем бота с временной конфигурацией для обновления
        cmd = [
            sys.executable, 
            "main_bot.py",
            "--config", temp_config_file,
            "--update", update_file,
            "--auto-exit"
        ]
        
        print(f"   ⚙️ Команда: {' '.join(cmd)}")
        
        # Здесь можно добавить логику отправки команды обновления через Telegram API
        # Или использовать другой механизм обновления
        
        # Для демонстрации просто показываем что нужно сделать
        print(f"   📤 Отправьте команду обновления боту {device_id}")
        print(f"   🔗 API Token: {device_config['api_token'][:10]}...")
        
        # Удаляем временный файл
        try:
            os.remove(temp_config_file)
        except:
            pass
        
        return True
        
    except Exception as e:
        print(f"   ❌ Ошибка обновления {device_id}: {e}")
        return False

def send_update_command(api_token, admin_id, update_url):
    """Отправка команды обновления через Telegram API"""
    try:
        import requests
        
        telegram_url = f"https://api.telegram.org/bot{api_token}/sendMessage"
        
        data = {
            "chat_id": admin_id,
            "text": f"/update_url {update_url}",
            "parse_mode": "HTML"
        }
        
        response = requests.post(telegram_url, data=data, timeout=10)
        
        if response.status_code == 200:
            print("   ✅ Команда обновления отправлена")
            return True
        else:
            print(f"   ❌ Ошибка отправки: {response.status_code}")
            return False
            
    except ImportError:
        print("   ⚠️ Модуль requests не установлен. Установите: pip install requests")
        return False
    except Exception as e:
        print(f"   ❌ Ошибка отправки команды: {e}")
        return False

def main():
    if len(sys.argv) < 2:
        print("Использование: python mass_updater.py <URL_обновления>")
        print("Пример: python mass_updater.py https://example.com/bot_v12.exe")
        return
    
    update_url = sys.argv[1]
    
    print("🔄 МАССОВОЕ ОБНОВЛЕНИЕ УСТРОЙСТВ")
    print("=" * 50)
    print(f"📎 URL обновления: {update_url}")
    
    # Загружаем конфигурацию
    config = load_config()
    if not config:
        return
    
    devices = config.get("devices", {})
    if not devices:
        print("❌ Устройства не найдены в конфигурации!")
        return
    
    print(f"📱 Найдено устройств: {len(devices)}")
    
    # Подтверждение
    print("\nСписок устройств для обновления:")
    for device_id, device_info in devices.items():
        print(f"  • {device_id}: {device_info['device_name']}")
    
    confirm = input("\nПродолжить обновление? (y/N): ").strip().lower()
    if confirm != 'y':
        print("❌ Обновление отменено")
        return
    
    # Скачиваем файл обновления
    update_file = download_update(update_url)
    if not update_file:
        return
    
    # Обновляем каждое устройство
    success_count = 0
    total_count = len(devices)
    
    for device_id, device_config in devices.items():
        print(f"\n--- Устройство {device_id} ---")
        
        # Отправляем команду обновления через Telegram
        if send_update_command(device_config["api_token"], device_config["admin_id"], update_url):
            success_count += 1
            print(f"   ✅ Команда отправлена успешно")
        else:
            print(f"   ❌ Ошибка отправки команды")
        
        # Небольшая пауза между устройствами
        time.sleep(2)
    
    # Удаляем скачанный файл
    try:
        os.remove(update_file)
    except:
        pass
    
    print("\n" + "=" * 50)
    print("📊 РЕЗУЛЬТАТЫ МАССОВОГО ОБНОВЛЕНИЯ")
    print(f"✅ Успешно: {success_count}/{total_count}")
    print(f"❌ Ошибок: {total_count - success_count}/{total_count}")
    
    if success_count == total_count:
        print("🎉 Все устройства обновлены успешно!")
    else:
        print("⚠️ Некоторые устройства не удалось обновить")

if __name__ == "__main__":
    main()