# database.py
"""
Модуль управления базой данных для системы мульти-администраторов
Использует SQLite для хранения профилей администраторов и устройств
"""

import sqlite3
import os
import tempfile
import logging
from datetime import datetime
from typing import Optional, List, Tuple, Dict, Any

logger = logging.getLogger(__name__)

# Путь к базе данных
DB_FILE = os.path.join(tempfile.gettempdir(), "bot_database.db")

# Константы ролей
ROLE_SUPER_ADMIN = "super_admin"
ROLE_ADMIN = "admin"


class Database:
    """Класс для управления базой данных"""
    
    def __init__(self, db_path: str = None):
        """Инициализация базы данных"""
        self.db_path = db_path or DB_FILE
        self._init_database()
    
    def _get_connection(self) -> sqlite3.Connection:
        """Получение соединения с базой данных"""
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn
    
    def _init_database(self):
        """Инициализация таблиц базы данных"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Таблица администраторов
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS admins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE NOT NULL,
                username TEXT,
                role TEXT DEFAULT 'admin',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                is_active INTEGER DEFAULT 1
            )
        ''')
        
        # Таблица устройств
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS devices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                hwid TEXT UNIQUE NOT NULL,
                device_name TEXT NOT NULL,
                last_online DATETIME,
                watchdog_status TEXT DEFAULT 'active',
                ip_address TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                is_active INTEGER DEFAULT 1
            )
        ''')
        
        # Таблица сессий (для отслеживания активных сессий администраторов)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                admin_id INTEGER NOT NULL,
                device_id INTEGER,
                session_start DATETIME DEFAULT CURRENT_TIMESTAMP,
                session_end DATETIME,
                FOREIGN KEY (admin_id) REFERENCES admins(id),
                FOREIGN KEY (device_id) REFERENCES devices(id)
            )
        ''')
        
        # Таблица логов действий (обновленная структура - без device_id)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS action_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                admin_id INTEGER,
                action_type TEXT NOT NULL,
                action_details TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (admin_id) REFERENCES admins(id)
            )
        ''')
        
        conn.commit()
        conn.close()
        logger.info("База данных инициализирована")
    
    # --- Методы для управления администраторами ---
    
    def add_admin(self, telegram_id: int, username: str = None, role: str = "admin") -> bool:
        """Добавление нового администратора"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR IGNORE INTO admins (telegram_id, username, role)
                VALUES (?, ?, ?)
            ''', (telegram_id, username, role))
            
            conn.commit()
            conn.close()
            logger.info(f"Добавлен администратор: {telegram_id} (роль: {role})")
            return True
        except Exception as e:
            logger.error(f"Ошибка добавления администратора: {e}")
            return False
    
    def remove_admin(self, telegram_id: int) -> bool:
        """Удаление администратора"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute('DELETE FROM admins WHERE telegram_id = ?', (telegram_id,))
            
            conn.commit()
            conn.close()
            logger.info(f"Удален администратор: {telegram_id}")
            return True
        except Exception as e:
            logger.error(f"Ошибка удаления администратора: {e}")
            return False
    
    def get_admin(self, telegram_id: int) -> Optional[Dict[str, Any]]:
        """Получение информации об администраторе"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute('SELECT * FROM admins WHERE telegram_id = ?', (telegram_id,))
            row = cursor.fetchone()
            
            conn.close()
            if row:
                return dict(row)
            return None
        except Exception as e:
            logger.error(f"Ошибка получения администратора: {e}")
            return None
    
    def get_all_admins(self) -> List[Dict[str, Any]]:
        """Получение списка всех администраторов"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute('SELECT * FROM admins WHERE is_active = 1 ORDER BY role DESC, created_at')
            rows = cursor.fetchall()
            
            conn.close()
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Ошибка получения списка администраторов: {e}")
            return []
    
    def is_super_admin(self, telegram_id: int) -> bool:
        """Проверка, является ли пользователь супер-администратором"""
        admin = self.get_admin(telegram_id)
        return admin and admin.get('role') == ROLE_SUPER_ADMIN
    
    def update_admin_role(self, telegram_id: int, role: str) -> bool:
        """Обновление роли администратора"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute('UPDATE admins SET role = ? WHERE telegram_id = ?', (role, telegram_id))
            
            conn.commit()
            conn.close()
            logger.info(f"Обновлена роль администратора {telegram_id}: {role}")
            return True
        except Exception as e:
            logger.error(f"Ошибка обновления роли администратора: {e}")
            return False
    
    # --- Методы для управления устройствами ---
    
    def add_device(self, hwid: str, device_name: str, ip_address: str = None) -> bool:
        """Добавление нового устройства"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Сначала удаляем старые записи с тем же IP-адресом, если они существуют
            if ip_address:
                cursor.execute('''
                    DELETE FROM devices WHERE ip_address = ? AND hwid != ?
                ''', (ip_address, hwid))
            
            # Затем добавляем новое устройство или обновляем существующее
            cursor.execute('''
                INSERT OR REPLACE INTO devices (hwid, device_name, last_online, ip_address)
                VALUES (?, ?, ?, ?)
            ''', (hwid, device_name, datetime.now(), ip_address))
            
            conn.commit()
            conn.close()
            logger.info(f"Добавлено устройство: {device_name} (HWID: {hwid})")
            return True
        except Exception as e:
            logger.error(f"Ошибка добавления устройства: {e}")
            return False
    
    def remove_device(self, hwid: str) -> bool:
        """Удаление устройства"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute('DELETE FROM devices WHERE hwid = ?', (hwid,))
            
            conn.commit()
            conn.close()
            logger.info(f"Удалено устройство: {hwid}")
            return True
        except Exception as e:
            logger.error(f"Ошибка удаления устройства: {e}")
            return False
    
    def get_device(self, hwid: str) -> Optional[Dict[str, Any]]:
        """Получение информации об устройстве"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute('SELECT * FROM devices WHERE hwid = ?', (hwid,))
            row = cursor.fetchone()
            
            conn.close()
            if row:
                return dict(row)
            return None
        except Exception as e:
            logger.error(f"Ошибка получения устройства: {e}")
            return None
    
    def get_all_devices(self) -> List[Dict[str, Any]]:
        """Получение списка всех устройств"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute('SELECT * FROM devices WHERE is_active = 1 ORDER BY device_name')
            rows = cursor.fetchall()
            
            conn.close()
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Ошибка получения списка устройств: {e}")
            return []
    
    def update_device_last_online(self, hwid: str) -> bool:
        """Обновление времени последней активности устройства"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE devices SET last_online = ? WHERE hwid = ?
            ''', (datetime.now(), hwid))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Ошибка обновления времени последней активности: {e}")
            return False
    
    def update_watchdog_status(self, hwid: str, status: str) -> bool:
        """Обновление статуса watchdog"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE devices SET watchdog_status = ? WHERE hwid = ?
            ''', (status, hwid))
            
            conn.commit()
            conn.close()
            logger.info(f"Обновлен статус watchdog для {hwid}: {status}")
            return True
        except Exception as e:
            logger.error(f"Ошибка обновления статуса watchdog: {e}")
            return False
    
    # --- Методы для управления сессиями ---
    
    def create_session(self, admin_id: int, device_id: int = None) -> int:
        """Создание новой сессии"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO sessions (admin_id, device_id, session_start)
                VALUES (?, ?, ?)
            ''', (admin_id, device_id, datetime.now()))
            
            session_id = cursor.lastrowid
            conn.commit()
            conn.close()
            return session_id
        except Exception as e:
            logger.error(f"Ошибка создания сессии: {e}")
            return 0
    
    def end_session(self, session_id: int) -> bool:
        """Завершение сессии"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE sessions SET session_end = ? WHERE id = ?
            ''', (datetime.now(), session_id))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Ошибка завершения сессии: {e}")
            return False
    
    def get_active_session(self, admin_id: int) -> Optional[Dict[str, Any]]:
        """Получение активной сессии администратора"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT * FROM sessions 
                WHERE admin_id = ? AND session_end IS NULL
                ORDER BY session_start DESC LIMIT 1
            ''', (admin_id,))
            
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return dict(row)
            return None
        except Exception as e:
            logger.error(f"Ошибка получения активной сессии: {e}")
            return None
    
    # --- Методы для логирования ---
    
    def log_action(self, user_id, action=None, details=None):
        """
        Логирование действия
        
        Новая сигнатура (согласно ТЗ):
        - user_id: ID пользователя
        - action: тип действия (строка)
        - details: детали действия (опционально)
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO action_logs (admin_id, action_type, action_details)
                VALUES (?, ?, ?)
            ''', (user_id, action, details))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Ошибка логирования действия: {e}")
            return False
    
    # --- Методы для очистки дубликатов ---
    
    def cleanup_duplicate_devices(self) -> Dict[str, int]:
        """
        Очистка дубликатов устройств в базе данных.
        Удаляет устройства с одинаковыми HWID, device_name или IP-адресом,
        оставляя только самую свежую запись.
        
        Возвращает словарь с количеством удаленных дубликатов по каждому типу.
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            stats = {
                'hwid_duplicates': 0,
                'name_duplicates': 0,
                'ip_duplicates': 0,
                'total_removed': 0
            }
            
            # 1. Очистка дубликатов по HWID (оставляем самую свежую запись)
            cursor.execute('''
                DELETE FROM devices
                WHERE id NOT IN (
                    SELECT MIN(id)
                    FROM devices
                    WHERE hwid IS NOT NULL AND hwid != ''
                    GROUP BY hwid
                )
                AND hwid IS NOT NULL AND hwid != ''
            ''')
            hwid_deleted = cursor.rowcount
            stats['hwid_duplicates'] = hwid_deleted
            
            # 2. Очистка дубликатов по device_name (оставляем самую свежую запись)
            cursor.execute('''
                DELETE FROM devices
                WHERE id NOT IN (
                    SELECT MIN(id)
                    FROM devices
                    WHERE device_name IS NOT NULL AND device_name != ''
                    GROUP BY device_name
                )
                AND device_name IS NOT NULL AND device_name != ''
                AND id NOT IN (
                    SELECT id FROM devices WHERE hwid IS NOT NULL AND hwid != ''
                )
            ''')
            name_deleted = cursor.rowcount
            stats['name_duplicates'] = name_deleted
            
            # 3. Очистка дубликатов по IP-адресу (оставляем самую свежую запись)
            cursor.execute('''
                DELETE FROM devices
                WHERE id NOT IN (
                    SELECT MIN(id)
                    FROM devices
                    WHERE ip_address IS NOT NULL AND ip_address != ''
                    GROUP BY ip_address
                )
                AND ip_address IS NOT NULL AND ip_address != ''
                AND id NOT IN (
                    SELECT id FROM devices WHERE hwid IS NOT NULL AND hwid != ''
                )
            ''')
            ip_deleted = cursor.rowcount
            stats['ip_duplicates'] = ip_deleted
            
            # 4. Очистка неактивных устройств (старше 30 дней)
            cursor.execute('''
                DELETE FROM devices
                WHERE last_online IS NOT NULL
                AND julianday('now') - julianday(last_online) > 30
                AND is_active = 0
            ''')
            inactive_deleted = cursor.rowcount
            
            conn.commit()
            conn.close()
            
            stats['total_removed'] = hwid_deleted + name_deleted + ip_deleted + inactive_deleted
            
            if stats['total_removed'] > 0:
                logger.info(f"Очистка дубликатов завершена. Удалено: {stats}")
            else:
                logger.info("Дубликаты не найдены.")
            
            return stats
            
        except Exception as e:
            logger.error(f"Ошибка очистки дубликатов: {e}")
            return {'hwid_duplicates': 0, 'name_duplicates': 0, 'ip_duplicates': 0, 'total_removed': 0}
    
    def cleanup_duplicate_admins(self) -> Dict[str, int]:
        """
        Очистка дубликатов администраторов в базе данных.
        Удаляет администраторов с одинаковым telegram_id.
        
        Возвращает словарь с количеством удаленных дубликатов.
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Удаляем дубликаты администраторов по telegram_id
            cursor.execute('''
                DELETE FROM admins
                WHERE id NOT IN (
                    SELECT MIN(id)
                    FROM admins
                    WHERE telegram_id IS NOT NULL
                    GROUP BY telegram_id
                )
            ''')
            deleted_count = cursor.rowcount
            
            conn.commit()
            conn.close()
            
            if deleted_count > 0:
                logger.info(f"Очистка дубликатов администраторов завершена. Удалено: {deleted_count}")
            
            return {'admins_removed': deleted_count}
            
        except Exception as e:
            logger.error(f"Ошибка очистки дубликатов администраторов: {e}")
            return {'admins_removed': 0}
    
    def run_complete_cleanup(self) -> Dict[str, Any]:
        """
        Выполнение полной очистки базы данных:
        1. Очистка дубликатов устройств
        2. Очистка дубликатов администраторов
        3. Очистка старых логов (старше 90 дней)
        
        Возвращает сводную статистику.
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Собираем статистику
            device_stats = self.cleanup_duplicate_devices()
            admin_stats = self.cleanup_duplicate_admins()
            
            # Очистка старых логов (старше 90 дней)
            cursor.execute('''
                DELETE FROM action_logs
                WHERE timestamp IS NOT NULL
                AND julianday('now') - julianday(timestamp) > 90
            ''')
            old_logs_deleted = cursor.rowcount
            
            conn.commit()
            conn.close()
            
            total_stats = {
                'device_duplicates_removed': device_stats['total_removed'],
                'admin_duplicates_removed': admin_stats['admins_removed'],
                'old_logs_removed': old_logs_deleted,
                'total_cleaned': device_stats['total_removed'] + admin_stats['admins_removed'] + old_logs_deleted
            }
            
            logger.info(f"Полная очистка БД завершена. Статистика: {total_stats}")
            return total_stats
            
        except Exception as e:
            logger.error(f"Ошибка полной очистки БД: {e}")
            return {'device_duplicates_removed': 0, 'admin_duplicates_removed': 0, 'old_logs_removed': 0, 'total_cleaned': 0}

    # --- Вспомогательные методы ---
    
    def get_device_by_id(self, device_id: int) -> Optional[Dict[str, Any]]:
        """Получение устройства по ID"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute('SELECT * FROM devices WHERE id = ?', (device_id,))
            row = cursor.fetchone()
            
            conn.close()
            if row:
                return dict(row)
            return None
        except Exception as e:
            logger.error(f"Ошибка получения устройства по ID: {e}")
            return None


# Глобальный экземпляр базы данных
db = Database()


def init_database():
    """Инициализация базы данных при запуске"""
    return db._init_database()


def get_db():
    """Получение экземпляра базы данных"""
    return db