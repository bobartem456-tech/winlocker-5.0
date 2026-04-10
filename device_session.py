# device_session.py
"""
Модуль для управления сессиями устройств в мульти-устройственной системе
Хранит выбранное устройство для каждого администратора
"""

import logging
import os
import tempfile
import json
from typing import Optional, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)

# Путь к файлу сессий
SESSIONS_FILE = os.path.join(tempfile.gettempdir(), "device_sessions.json")

# Глобальное хранилище сессий
_sessions: Dict[int, Dict[str, Any]] = {}


def _load_sessions():
    """Загрузка сессий из файла"""
    global _sessions
    try:
        if os.path.exists(SESSIONS_FILE):
            with open(SESSIONS_FILE, 'r', encoding='utf-8') as f:
                _sessions = json.load(f)
            # Конвертируем ключи обратно в int
            _sessions = {int(k): v for k, v in _sessions.items()}
            logger.debug(f"Загружено {len(_sessions)} сессий устройств")
    except Exception as e:
        logger.error(f"Ошибка загрузки сессий: {e}")
        _sessions = {}


def _save_sessions():
    """Сохранение сессий в файл"""
    try:
        with open(SESSIONS_FILE, 'w', encoding='utf-8') as f:
            json.dump(_sessions, f, ensure_ascii=False, indent=2)
        logger.debug(f"Сохранено {len(_sessions)} сессий устройств")
    except Exception as e:
        logger.error(f"Ошибка сохранения сессий: {e}")


def get_selected_device(admin_id: int) -> Optional[Dict[str, Any]]:
    """
    Получение выбранного устройства для администратора
    
    Args:
        admin_id: ID администратора в Telegram
        
    Returns:
        Словарь с данными устройства или None
    """
    _load_sessions()
    return _sessions.get(admin_id)


def set_selected_device(admin_id: int, device_id: int, hwid: str, device_name: str) -> bool:
    """
    Установка выбранного устройства для администратора
    
    Args:
        admin_id: ID администратора в Telegram
        device_id: ID устройства в базе данных
        hwid: Hardware ID устройства
        device_name: Имя устройства
        
    Returns:
        True если успешно
    """
    _load_sessions()
    _sessions[admin_id] = {
        'device_id': device_id,
        'hwid': hwid,
        'device_name': device_name,
        'selected_at': datetime.now().isoformat()
    }
    _save_sessions()
    logger.info(f"Администратор {admin_id} выбрал устройство: {device_name} (HWID: {hwid})")
    return True


def clear_selected_device(admin_id: int) -> bool:
    """
    Очистка выбранного устройства для администратора
    
    Args:
        admin_id: ID администратора в Telegram
        
    Returns:
        True если успешно
    """
    _load_sessions()
    if admin_id in _sessions:
        del _sessions[admin_id]
        _save_sessions()
        logger.info(f"Администратор {admin_id} очистил выбор устройства")
        return True
    return False


def get_selected_device_hwid(admin_id: int) -> Optional[str]:
    """
    Получение HWID выбранного устройства
    
    Args:
        admin_id: ID администратора в Telegram
        
    Returns:
        HWID устройства или None
    """
    device = get_selected_device(admin_id)
    if device:
        return device.get('hwid')
    return None


def get_selected_device_name(admin_id: int) -> Optional[str]:
    """
    Получение имени выбранного устройства
    
    Args:
        admin_id: ID администратора в Telegram
        
    Returns:
        Имя устройства или None
    """
    device = get_selected_device(admin_id)
    if device:
        return device.get('device_name')
    return None


def get_all_active_sessions() -> Dict[int, Dict[str, Any]]:
    """
    Получение всех активных сессий
    
    Returns:
        Словарь сессий {admin_id: device_info}
    """
    _load_sessions()
    return _sessions.copy()


def cleanup_old_sessions(max_age_hours: int = 72) -> int:
    """
    Очистка старых сессий
    
    Args:
        max_age_hours: Максимальный возраст сессии в часах
        
    Returns:
        Количество удалённых сессий
    """
    _load_sessions()
    now = datetime.now()
    removed = 0
    
    to_remove = []
    for admin_id, session in _sessions.items():
        try:
            selected_at = datetime.fromisoformat(session.get('selected_at', ''))
            age = (now - selected_at).total_seconds() / 3600
            if age > max_age_hours:
                to_remove.append(admin_id)
        except Exception:
            to_remove.append(admin_id)
    
    for admin_id in to_remove:
        del _sessions[admin_id]
        removed += 1
    
    if removed > 0:
        _save_sessions()
        logger.info(f"Очищено {removed} старых сессий устройств")
    
    return removed


# Инициализация при импорте
_load_sessions()
cleanup_old_sessions()
logger.info("Модуль device_session инициализирован")
