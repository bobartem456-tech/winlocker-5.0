# secure_config.py
"""
Безопасная система конфигурации с загрузкой из .env файла
Никогда не храните чувствительные данные в коде!
"""

import os
from pathlib import Path
from typing import Optional, Union


def load_env_file(env_path: str = ".env") -> dict:
    """
    Загрузка переменных окружения из .env файла
    
    Args:
        env_path: Путь к .env файлу
        
    Returns:
        dict: Словарь с переменными окружения
    """
    env_vars = {}
    env_file = Path(env_path)
    
    if env_file.exists():
        with open(env_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                # Пропускаем комментарии и пустые строки
                if not line or line.startswith('#') or '=' not in line:
                    continue
                
                # Разделяем ключ и значение
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip()
                
                # Убираем кавычки если есть
                if value and value[0] in '"\'':
                    value = value[1:-1]
                
                env_vars[key] = value
    
    return env_vars


class SecureConfig:
    """
    Безопасный класс конфигурации с приоритетами:
    1. Переменные окружения ОС
    2. .env файл
    3. Значения по умолчанию
    """
    
    def __init__(self, env_file: str = ".env"):
        """Инициализация конфигурации"""
        self._env_vars = load_env_file(env_file)
        self._validate_config()
    
    def _validate_config(self):
        """Проверка критических переменных"""
        required_vars = ['BOT_TOKEN', 'SUPER_ADMIN_ID']
        missing = []
        
        for var in required_vars:
            if not self.get(var):
                missing.append(var)
        
        if missing:
            print(f"⚠️ ВНИМАНИЕ: Отсутствуют критические переменные: {', '.join(missing)}")
            print("   Создайте .env файл или установите переменные окружения")
            print("   Пример .env файла смотрите в .env.example")
    
    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """
        Получение значения конфигурации
        
        Приоритеты:
        1. Переменная окружения ОС
        2. .env файл
        3. Значение по умолчанию
        
        Args:
            key: Ключ переменной
            default: Значение по умолчанию
            
        Returns:
            Значение переменной или default
        """
        # Сначала проверяем переменные окружения ОС
        os_value = os.environ.get(key)
        if os_value:
            return os_value
        
        # Затем .env файл
        env_value = self._env_vars.get(key)
        if env_value:
            return env_value
        
        # Возвращаем default
        return default
    
    def get_int(self, key: str, default: int = 0) -> int:
        """Получение целочисленного значения"""
        value = self.get(key, str(default))
        try:
            return int(value)
        except (ValueError, TypeError):
            return default
    
    def get_bool(self, key: str, default: bool = False) -> bool:
        """Получение булевого значения"""
        value = self.get(key, str(default)).lower()
        return value in ('true', '1', 'yes', 'on')
    
    def get_path(self, key: str, default: str = "") -> str:
        """Получение пути с нормализацией"""
        value = self.get(key, default)
        return os.path.normpath(value) if value else value
    
    def is_configured(self) -> bool:
        """Проверка, настроена ли конфигурация"""
        return bool(self.get('BOT_TOKEN')) and bool(self.get('SUPER_ADMIN_ID'))
    
    def get_all(self) -> dict:
        """Получение всех переменных (для отладки)"""
        return {
            **self._env_vars,
            **{k: v for k, v in os.environ.items() if k in self._env_vars}
        }


# Глобальный экземпляр конфигурации
_secure_config = None


def get_secure_config() -> SecureConfig:
    """Получение глобального экземпляра конфигурации"""
    global _secure_config
    if _secure_config is None:
        _secure_config = SecureConfig()
    return _secure_config


# Функции для совместимости со старым кодом
def get_bot_token() -> str:
    """Получение токена бота"""
    config = get_secure_config()
    token = config.get('BOT_TOKEN')
    if not token:
        raise ValueError("BOT_TOKEN не настроен! Проверьте .env файл или переменные окружения")
    return token


def get_super_admin_id() -> int:
    """Получение ID супер-администратора"""
    config = get_secure_config()
    admin_id = config.get('SUPER_ADMIN_ID')
    if not admin_id:
        raise ValueError("SUPER_ADMIN_ID не настроен! Проверьте .env файл или переменные окружения")
    try:
        return int(admin_id)
    except ValueError:
        raise ValueError("SUPER_ADMIN_ID должен быть числом!")


# Для обратной совместимости создадим модульные переменные
if __name__ != "__main__":
    try:
        config = get_secure_config()
        BOT_TOKEN = config.get('BOT_TOKEN', '')
        SUPER_ADMIN_ID = config.get_int('SUPER_ADMIN_ID', 0)
    except:
        BOT_TOKEN = ''
        SUPER_ADMIN_ID = 0
