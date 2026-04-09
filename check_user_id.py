#!/usr/bin/env python3
"""
Скрипт для проверки ID пользователя в Telegram
"""

import telebot
import logging

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Токен бота из config.py
try:
    from config import BOT_TOKEN
    logger.info(f"Токен загружен из config.py")
except ImportError:
    logger.error("Не удалось импортировать BOT_TOKEN из config.py")
    # Используем токен напрямую (временно для теста)
    BOT_TOKEN = "8655788950:AAFct5_PtK-7b3CWUFmylCwFyRHb2QVsXY8"
    logger.warning(f"Используется хардкодный токен")

# Создаем экземпляр бота
bot = telebot.TeleBot(BOT_TOKEN)

@bot.message_handler(commands=['myid', 'id', 'start'])
def get_user_id(message):
    """Получить ID пользователя"""
    user_id = message.from_user.id
    username = message.from_user.username or "без имени"
    first_name = message.from_user.first_name or ""
    last_name = message.from_user.last_name or ""
    
    response = (
        f"👤 *Ваши данные в Telegram:*\n\n"
        f"🆔 *ID:* `{user_id}`\n"
        f"📛 *Username:* @{username}\n"
        f"👨 *Имя:* {first_name}\n"
        f"👨 *Фамилия:* {last_name}\n\n"
        f"📋 *SUPER_ADMIN_ID из config.py:* 6219146434\n\n"
        f"🔍 *Сравнение:* {'✅ Совпадает' if user_id == 6219146434 else '❌ НЕ совпадает'}"
    )
    
    logger.info(f"Пользователь: user_id={user_id}, username=@{username}")
    bot.reply_to(message, response, parse_mode='Markdown')

@bot.message_handler(func=lambda message: True)
def echo_all(message):
    """Эхо всех сообщений"""
    user_id = message.from_user.id
    text = message.text
    
    logger.info(f"Сообщение от user_id={user_id}: {text[:50]}...")
    
    response = f"Ваш ID: `{user_id}`\nОтправьте /myid для подробной информации"
    bot.reply_to(message, response, parse_mode='Markdown')

def main():
    """Главная функция"""
    print("=" * 60)
    print("ПРОВЕРКА ID ПОЛЬЗОВАТЕЛЯ")
    print("=" * 60)
    print("1. Отправьте любое сообщение этому боту в Telegram")
    print("2. Бот покажет ваш ID")
    print("3. Сравните с SUPER_ADMIN_ID в config.py (6219146434)")
    print("=" * 60)
    
    try:
        # Проверка соединения
        logger.info("Проверка соединения...")
        bot_info = bot.get_me()
        logger.info(f"Бот: @{bot_info.username} (ID: {bot_info.id})")
        
        # Очистка webhook
        bot.delete_webhook()
        
        # Запуск
        print("\n[OK] Бот запущен. Отправьте /myid в Telegram")
        print("[INFO] Для остановки: Ctrl+C")
        
        bot.infinity_polling(timeout=60, long_polling_timeout=60)
        
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return 1
    except KeyboardInterrupt:
        print("\n[STOP] Бот остановлен")
        return 0

if __name__ == "__main__":
    import sys
    sys.exit(main())