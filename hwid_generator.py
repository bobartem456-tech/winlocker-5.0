# hwid_generator.py
"""
Модуль генерации уникального Hardware ID (HWID) для идентификации устройств
HWID генерируется на основе уникальных системных идентификаторов:
- Серийный номер материнской платы
- Серийный номер процессора
- UUID системы
"""

import subprocess
import uuid
import hashlib
import platform
import os
import sys


def get_motherboard_serial():
    """Получение серийного номера материнской платы без использования wmic"""
    try:
        # Windows: используем registry для получения серийного номера
        if platform.system() == "Windows":
            try:
                import winreg
                key = winreg.OpenKey(
                    winreg.HKEY_LOCAL_MACHINE,
                    r"SYSTEM\CurrentControlSet\Control\SystemInformation"
                )
                serial, _ = winreg.QueryValueEx(key, "SystemSerialNumber")
                winreg.CloseKey(key)
                if serial:
                    return str(serial)
            except Exception:
                pass
            
            # Альтернативный метод через WMI без консольного окна
            try:
                import wmi
                c = wmi.WMI()
                for board in c.Win32_BaseBoard():
                    if board.SerialNumber:
                        return str(board.SerialNumber)
            except Exception:
                pass
                
            # Fallback: используем PowerShell без окна
            try:
                result = subprocess.run(
                    ['powershell', '-Command', 'Get-WmiObject Win32_BaseBoard | Select-Object -ExpandProperty SerialNumber'],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
                if result.returncode == 0 and result.stdout.strip():
                    return result.stdout.strip()
            except Exception:
                pass
        
        # Linux/Mac: используем dmidecode (требует sudo)
        elif platform.system() == "Linux":
            try:
                result = subprocess.run(
                    ['sudo', 'dmidecode', '-s', 'baseboard-serial-number'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0 and result.stdout.strip():
                    return result.stdout.strip()
            except Exception:
                pass
                
    except Exception as e:
        print(f"Ошибка получения серийного номера материнской платы: {e}")
    
    return None


def get_processor_serial():
    """Получение серийного номера процессора без использования wmic"""
    try:
        if platform.system() == "Windows":
            # Метод через WMI без консольного окна
            try:
                import wmi
                c = wmi.WMI()
                for processor in c.Win32_Processor():
                    if processor.ProcessorId:
                        return str(processor.ProcessorId)
            except Exception:
                pass
                
            # Метод через PowerShell без окна
            try:
                result = subprocess.run(
                    ['powershell', '-Command', 'Get-WmiObject Win32_Processor | Select-Object -ExpandProperty ProcessorId'],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
                if result.returncode == 0 and result.stdout.strip():
                    return result.stdout.strip()
            except Exception:
                pass
                
            # Метод через registry
            try:
                import winreg
                key = winreg.OpenKey(
                    winreg.HKEY_LOCAL_MACHINE,
                    r"HARDWARE\DESCRIPTION\System\CentralProcessor\0"
                )
                processor_id, _ = winreg.QueryValueEx(key, "ProcessorNameString")
                winreg.CloseKey(key)
                if processor_id:
                    # Извлекаем ID из строки
                    import re
                    match = re.search(r'ID\s*([A-F0-9]+)', processor_id, re.IGNORECASE)
                    if match:
                        return match.group(1)
            except Exception:
                pass
                
    except Exception as e:
        print(f"Ошибка получения серийного номера процессора: {e}")
    
    return None


def get_system_uuid():
    """Получение UUID системы без использования wmic"""
    try:
        if platform.system() == "Windows":
            # Метод через WMI без консольного окна
            try:
                import wmi
                c = wmi.WMI()
                for system in c.Win32_ComputerSystemProduct():
                    if system.UUID:
                        return str(system.UUID)
            except Exception:
                pass
                
            # Метод через PowerShell без окна
            try:
                result = subprocess.run(
                    ['powershell', '-Command', 'Get-WmiObject Win32_ComputerSystemProduct | Select-Object -ExpandProperty UUID'],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
                if result.returncode == 0 and result.stdout.strip():
                    return result.stdout.strip()
            except Exception:
                pass
                
            # Метод через registry
            try:
                import winreg
                key = winreg.OpenKey(
                    winreg.HKEY_LOCAL_MACHINE,
                    r"SOFTWARE\Microsoft\Cryptography"
                )
                machine_guid, _ = winreg.QueryValueEx(key, "MachineGuid")
                winreg.CloseKey(key)
                if machine_guid:
                    return str(machine_guid)
            except Exception:
                pass
        
        # Fallback: используем uuid.getnode() для всех платформ
        return str(uuid.getnode())
    except Exception as e:
        print(f"Ошибка получения UUID системы: {e}")
    
    return None


def generate_hwid() -> str:
    """
    Генерация уникального Hardware ID на основе системных идентификаторов
    HWID - это хеш от комбинации серийных номеров
    """
    components = []
    
    # Получаем серийный номер материнской платы
    motherboard_serial = get_motherboard_serial()
    if motherboard_serial:
        components.append(motherboard_serial)
    
    # Получаем серийный номер процессора
    processor_serial = get_processor_serial()
    if processor_serial:
        components.append(processor_serial)
    
    # Получаем UUID системы
    system_uuid = get_system_uuid()
    if system_uuid:
        components.append(system_uuid)
    
    # Если не удалось получить ни одного идентификатора, используем MAC-адрес
    if not components:
        try:
            import uuid
            mac = ':'.join(['{:02x}'.format((uuid.getnode() >> elements) & 0xff) 
                          for elements in range(0, 2*6, 2)][::-1])
            components.append(mac)
        except Exception:
            components.append(str(uuid.getnode()))
    
    # Создаем хеш от комбинации всех компонентов
    combined = '|'.join(components)
    hwid = hashlib.sha256(combined.encode()).hexdigest()[:16].upper()
    
    return hwid


def get_device_name() -> str:
    """Получение имени устройства"""
    try:
        import socket
        return socket.gethostname()
    except Exception:
        return "UnknownPC"


if __name__ == "__main__":
    print("=== Генерация Hardware ID ===")
    print(f"HWID: {generate_hwid()}")
    print(f"Device Name: {get_device_name()}")