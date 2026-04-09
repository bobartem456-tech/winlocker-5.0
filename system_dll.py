#!/usr/bin/env python3
"""
Модуль для работы с system_core.dll через ctypes
"""

import ctypes
import os
import sys
from ctypes import wintypes

class SystemDLL:
    """Класс для работы с системной DLL"""
    
    def __init__(self, dll_path=None):
        """Инициализация DLL"""
        if dll_path is None:
            # Ищем DLL в текущей директории
            dll_path = "system_core.dll"
        
        self.dll_path = dll_path
        
        try:
            self.dll = ctypes.CDLL(dll_path)
            self._setup_functions()
            print(f"[DLL] Загружена библиотека: {dll_path}")
        except Exception as e:
            print(f"[DLL ERROR] Не удалось загрузить {dll_path}: {e}")
            print("[DLL INFO] Создаю заглушки для функций")
            self.dll = None
            self._create_stubs()
    
    def _setup_functions(self):
        """Настройка сигнатур функций"""
        # Блокировка рабочей станции
        self.dll.lock_workstation.restype = ctypes.c_int
        self.dll.lock_workstation.argtypes = []
        
        # Выключение компьютера
        self.dll.shutdown_system.restype = ctypes.c_int
        self.dll.shutdown_system.argtypes = [ctypes.c_int]
        
        # Перезагрузка компьютера
        self.dll.reboot_system.restype = ctypes.c_int
        self.dll.reboot_system.argtypes = [ctypes.c_int]
        
        # Завершение процесса по имени
        self.dll.kill_process_by_name.restype = ctypes.c_int
        self.dll.kill_process_by_name.argtypes = [ctypes.c_char_p]
        
        # Завершение процесса по ID
        self.dll.kill_process_by_id.restype = ctypes.c_int
        self.dll.kill_process_by_id.argtypes = [ctypes.c_ulong]
        
        # Получение списка процессов
        self.dll.get_process_list.restype = ctypes.c_char_p
        self.dll.get_process_list.argtypes = []
        
        # Скрытие окна по заголовку
        self.dll.hide_window_by_title.restype = ctypes.c_int
        self.dll.hide_window_by_title.argtypes = [ctypes.c_char_p]
        
        # Показать окно по заголовку
        self.dll.show_window_by_title.restype = ctypes.c_int
        self.dll.show_window_by_title.argtypes = [ctypes.c_char_p]
        
        # Свернуть все окна
        self.dll.minimize_all_windows.restype = ctypes.c_int
        self.dll.minimize_all_windows.argtypes = []
        
        # Получение заголовка активного окна
        self.dll.get_active_window_title.restype = ctypes.c_char_p
        self.dll.get_active_window_title.argtypes = []
        
        # Получение системной информации
        self.dll.get_system_info_string.restype = ctypes.c_char_p
        self.dll.get_system_info_string.argtypes = []
        
        # Управление громкостью
        self.dll.set_system_volume.restype = ctypes.c_int
        self.dll.set_system_volume.argtypes = [ctypes.c_int]
        
        self.dll.mute_system_volume.restype = ctypes.c_int
        self.dll.mute_system_volume.argtypes = []
        
        self.dll.unmute_system_volume.restype = ctypes.c_int
        self.dll.unmute_system_volume.argtypes = []
        
        # Выполнение команды
        self.dll.execute_command.restype = ctypes.c_int
        self.dll.execute_command.argtypes = [ctypes.c_char_p]
        
        # Создание скрытого процесса
        self.dll.create_hidden_process.restype = ctypes.c_int
        self.dll.create_hidden_process.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
        
        # Освобождение памяти
        self.dll.free_string.restype = None
        self.dll.free_string.argtypes = [ctypes.c_char_p]
    
    def _create_stubs(self):
        """Создание заглушек для функций"""
        self.lock_workstation = self._stub_lock_workstation
        self.shutdown_system = self._stub_shutdown_system
        self.reboot_system = self._stub_reboot_system
        self.kill_process_by_name = self._stub_kill_process_by_name
        self.kill_process_by_id = self._stub_kill_process_by_id
        self.get_process_list = self._stub_get_process_list
        self.hide_window_by_title = self._stub_hide_window_by_title
        self.show_window_by_title = self._stub_show_window_by_title
        self.minimize_all_windows = self._stub_minimize_all_windows
        self.get_active_window_title = self._stub_get_active_window_title
        self.get_system_info_string = self._stub_get_system_info_string
        self.set_system_volume = self._stub_set_system_volume
        self.mute_system_volume = self._stub_mute_system_volume
        self.unmute_system_volume = self._stub_unmute_system_volume
        self.execute_command = self._stub_execute_command
        self.create_hidden_process = self._stub_create_hidden_process
        self.free_string = self._stub_free_string
    
    # ==================== РЕАЛЬНЫЕ ФУНКЦИИ DLL ====================
    
    def lock_workstation(self):
        """Блокировка рабочей станции"""
        return self.dll.lock_workstation()
    
    def shutdown_system(self, force=0):
        """Выключение компьютера"""
        return self.dll.shutdown_system(force)
    
    def reboot_system(self, force=0):
        """Перезагрузка компьютера"""
        return self.dll.reboot_system(force)
    
    def kill_process_by_name(self, process_name):
        """Завершение процесса по имени"""
        return self.dll.kill_process_by_name(process_name.encode('utf-8'))
    
    def kill_process_by_id(self, pid):
        """Завершение процесса по ID"""
        return self.dll.kill_process_by_id(pid)
    
    def get_process_list(self):
        """Получение списка процессов"""
        result = self.dll.get_process_list()
        if result:
            processes = result.decode('utf-8')
            self.dll.free_string(result)
            return processes
        return ""
    
    def hide_window_by_title(self, title):
        """Скрытие окна по заголовку"""
        return self.dll.hide_window_by_title(title.encode('utf-8'))
    
    def show_window_by_title(self, title):
        """Показать окно по заголовку"""
        return self.dll.show_window_by_title(title.encode('utf-8'))
    
    def minimize_all_windows(self):
        """Свернуть все окна"""
        return self.dll.minimize_all_windows()
    
    def get_active_window_title(self):
        """Получение заголовка активного окна"""
        result = self.dll.get_active_window_title()
        if result:
            title = result.decode('utf-8')
            self.dll.free_string(result)
            return title
        return ""
    
    def get_system_info_string(self):
        """Получение системной информации"""
        result = self.dll.get_system_info_string()
        if result:
            info = result.decode('utf-8')
            self.dll.free_string(result)
            return info
        return ""
    
    def set_system_volume(self, level):
        """Установка уровня громкости (0-100)"""
        if level < 0:
            level = 0
        if level > 100:
            level = 100
        return self.dll.set_system_volume(level)
    
    def mute_system_volume(self):
        """Отключение звука"""
        return self.dll.mute_system_volume()
    
    def unmute_system_volume(self):
        """Включение звука"""
        return self.dll.unmute_system_volume()
    
    def execute_command(self, command):
        """Выполнение команды CMD"""
        return self.dll.execute_command(command.encode('utf-8'))
    
    def create_hidden_process(self, exe_path, args=""):
        """Создание скрытого процесса"""
        return self.dll.create_hidden_process(
            exe_path.encode('utf-8'),
            args.encode('utf-8') if args else None
        )
    
    def free_string(self, string_ptr):
        """Освобождение памяти"""
        if self.dll and string_ptr:
            self.dll.free_string(string_ptr)
    
    # ==================== ЗАГЛУШКИ ====================
    
    def _stub_lock_workstation(self):
        print("[STUB] lock_workstation() - блокировка рабочей станции")
        import ctypes
        return ctypes.windll.user32.LockWorkStation()
    
    def _stub_shutdown_system(self, force=0):
        print(f"[STUB] shutdown_system(force={force}) - выключение компьютера")
        import subprocess
        subprocess.run(["shutdown", "/s", "/t", "0"],
                      creationflags=subprocess.CREATE_NO_WINDOW)
        return 1
    
    def _stub_reboot_system(self, force=0):
        print(f"[STUB] reboot_system(force={force}) - перезагрузка компьютера")
        import subprocess
        subprocess.run(["shutdown", "/r", "/t", "0"],
                      creationflags=subprocess.CREATE_NO_WINDOW)
        return 1
    
    def _stub_kill_process_by_name(self, process_name):
        print(f"[STUB] kill_process_by_name({process_name})")
        import subprocess
        subprocess.run(["taskkill", "/f", "/im", process_name],
                      creationflags=subprocess.CREATE_NO_WINDOW)
        return 1
    
    def _stub_kill_process_by_id(self, pid):
        print(f"[STUB] kill_process_by_id({pid})")
        import subprocess
        subprocess.run(["taskkill", "/f", "/pid", str(pid)],
                      creationflags=subprocess.CREATE_NO_WINDOW)
        return 1
    
    def _stub_get_process_list(self):
        print("[STUB] get_process_list()")
        import subprocess
        result = subprocess.run(["tasklist", "/fo", "csv"], 
                              capture_output=True, text=True)
        return result.stdout
    
    def _stub_hide_window_by_title(self, title):
        print(f"[STUB] hide_window_by_title({title})")
        return 0
    
    def _stub_show_window_by_title(self, title):
        print(f"[STUB] show_window_by_title({title})")
        return 0
    
    def _stub_minimize_all_windows(self):
        print("[STUB] minimize_all_windows()")
        import ctypes
        ctypes.windll.user32.keybd_event(0x5B, 0, 0, 0)  # Win
        ctypes.windll.user32.keybd_event(0x44, 0, 0, 0)  # D
        ctypes.windll.user32.keybd_event(0x44, 0, 2, 0)  # D release
        ctypes.windll.user32.keybd_event(0x5B, 0, 2, 0)  # Win release
        return 1
    
    def _stub_get_active_window_title(self):
        print("[STUB] get_active_window_title()")
        return "Active Window (stub)"
    
    def _stub_get_system_info_string(self):
        print("[STUB] get_system_info_string()")
        import platform
        return f"System: {platform.system()} {platform.release()}\n"
    
    def _stub_set_system_volume(self, level):
        """Установка уровня громкости (0-100) через Windows Core Audio API"""
        print(f"[STUB] set_system_volume({level}) - using Windows API")
        try:
            # Простой и надежный метод через PowerShell с Windows Audio API
            import subprocess
            # Используем PowerShell с Windows Audio Device Commandlets если доступны
            # Или используем стандартный Windows Audio API через PowerShell
            ps_script = f"""
$volume = {level}
$obj = New-Object -ComObject Shell.Application
$obj.NameSpace(0x11).Self.InvokeVerb('Properties').Document.Application.Volume = $volume
"""
            # Альтернативный метод через SendKeys (менее надежный)
            result = subprocess.run(["powershell", "-WindowStyle", "Hidden", "-Command",
                                   f"(New-Object -ComObject Shell.Application).NameSpace(0x11).Self.InvokeVerb('Properties').Document.Application.Volume = {level}"],
                                  creationflags=subprocess.CREATE_NO_WINDOW, timeout=5,
                                  capture_output=True, text=True)
            
            if result.returncode != 0:
                # Fallback к другому методу
                ps_script2 = f"""
Add-Type -TypeDefinition @'
using System.Runtime.InteropServices;
[Guid("5CDF2C82-841E-4546-9722-0CF74078229A")]
[InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
interface IAudioEndpointVolume {{
    int SetMasterVolumeLevelScalar(float fLevel, System.Guid pguidEventContext);
}}
[Guid("D666063F-1587-4E43-81F1-B948E807363F")]
[InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
interface IMMDevice {{
    int Activate(ref System.Guid iid, int dwClsCtx, IntPtr pActivationParams, out IAudioEndpointVolume ppInterface);
}}
[Guid("A95664D2-9614-4F35-A746-DE8DB63617E6")]
[InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
interface IMMDeviceEnumerator {{
    int GetDefaultAudioEndpoint(int dataFlow, int role, out IMMDevice ppEndpoint);
}}
public class Audio {{
    [DllImport("ole32.dll")]
    public static extern int CoCreateInstance(ref System.Guid clsid, IntPtr inner, uint context, ref System.Guid uuid, out object volume);
    public static void SetVolume(float level) {{
        try {{
            var enumerator = new IMMDeviceEnumerator();
            IMMDevice device = null;
            enumerator.GetDefaultAudioEndpoint(0, 1, out device);
            IAudioEndpointVolume volume = null;
            var guid = new System.Guid("5CDF2C82-841E-4546-9722-0CF74078229A");
            device.Activate(ref guid, 0, IntPtr.Zero, out volume);
            volume.SetMasterVolumeLevelScalar(level, System.Guid.Empty);
        }} catch {{}}
    }}
}}
'@
[Audio]::SetVolume({level}/100.0)
"""
                subprocess.run(["powershell", "-WindowStyle", "Hidden", "-Command", ps_script2],
                             creationflags=subprocess.CREATE_NO_WINDOW, timeout=5)
            
            return 1
        except Exception as e:
            print(f"[STUB] Volume control error: {e}")
            return 0
    
    def _stub_mute_system_volume(self):
        """Отключение звука через Windows API"""
        print("[STUB] mute_system_volume() - using Windows API")
        try:
            import subprocess
            # Метод 1: PowerShell с Audio API
            ps_script = """
$wsh = New-Object -ComObject WScript.Shell
$wsh.SendKeys([char]173)  # Volume Mute key
"""
            result = subprocess.run(["powershell", "-WindowStyle", "Hidden", "-Command", ps_script],
                                  creationflags=subprocess.CREATE_NO_WINDOW, timeout=5)
            
            # Метод 2: Установка громкости на 0
            if result.returncode != 0:
                subprocess.run(["powershell", "-WindowStyle", "Hidden", "-Command",
                              "(New-Object -ComObject Shell.Application).NameSpace(0x11).Self.InvokeVerb('Properties').Document.Application.Volume = 0"],
                             creationflags=subprocess.CREATE_NO_WINDOW, timeout=5)
            
            return 1
        except Exception as e:
            print(f"[STUB] Mute error: {e}")
            return 0
    
    def _stub_unmute_system_volume(self):
        """Включение звука через Windows API - зеркальная реализация к mute"""
        print("[STUB] unmute_system_volume() - using Windows API (mirror of mute)")
        try:
            import subprocess
            # Метод 1: PowerShell с Audio API - используем тот же Volume Mute key (173)
            # который переключает состояние mute/unmute
            ps_script = """
$wsh = New-Object -ComObject WScript.Shell
$wsh.SendKeys([char]173)  # Volume Mute key (toggle - если звук выключен, включит его)
"""
            result = subprocess.run(["powershell", "-WindowStyle", "Hidden", "-Command", ps_script],
                                  creationflags=subprocess.CREATE_NO_WINDOW, timeout=5)
            
            # Метод 2: Установка громкости на 50
            if result.returncode != 0:
                subprocess.run(["powershell", "-WindowStyle", "Hidden", "-Command",
                              "(New-Object -ComObject Shell.Application).NameSpace(0x11).Self.InvokeVerb('Properties').Document.Application.Volume = 50"],
                             creationflags=subprocess.CREATE_NO_WINDOW, timeout=5)
            
            return 1
        except Exception as e:
            print(f"[STUB] Unmute error: {e}")
            return 0
    
    def _stub_execute_command(self, command):
        print(f"[STUB] execute_command({command})")
        import subprocess
        # For shell commands, we need to use shell=True but hide window
        result = subprocess.run(command, shell=True,
                               creationflags=subprocess.CREATE_NO_WINDOW,
                               capture_output=True, text=True)
        return result.returncode
    
    def _stub_create_hidden_process(self, exe_path, args=""):
        print(f"[STUB] create_hidden_process({exe_path}, {args})")
        import subprocess
        subprocess.Popen([exe_path] + args.split(),
                        creationflags=subprocess.CREATE_NO_WINDOW)
        return 1
    
    def is_available(self):
        """Проверка доступности DLL (не заглушки)"""
        return self.dll is not None
    
    def _stub_free_string(self, string_ptr):
        print("[STUB] free_string()")
        pass

# Глобальный экземпляр для импорта
_system_dll = None

def get_system_dll():
    """Получить глобальный экземпляр SystemDLL"""
    global _system_dll
    if _system_dll is None:
        _system_dll = SystemDLL()
    return _system_dll

# Тестирование
if __name__ == "__main__":
    dll = get_system_dll()
    print("Тестирование SystemDLL:")
    print("1. Информация о системе:")
    print(dll.get_system_info_string())
    print("2. Активное окно:")
    print(dll.get_active_window_title())
    print("3. Список процессов (первые 5 строк):")
    processes = dll.get_process_list()
    lines = processes.split('\n')[:5]
    for line in lines:
        print(f"   {line}")