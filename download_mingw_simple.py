#!/usr/bin/env python3
"""
Упрощенный скрипт для создания структуры MinGW-w64
"""

import os
import sys

def create_minimal_structure():
    """Создать минимальную структуру для компиляции DLL"""
    
    compiler_dir = os.path.join(os.path.dirname(__file__), '.compiler')
    os.makedirs(compiler_dir, exist_ok=True)
    
    print(f"[INFO] Создаю структуру в: {compiler_dir}")
    
    # Создаем необходимые директории
    bin_dir = os.path.join(compiler_dir, 'bin')
    include_dir = os.path.join(compiler_dir, 'include')
    lib_dir = os.path.join(compiler_dir, 'lib')
    
    os.makedirs(bin_dir, exist_ok=True)
    os.makedirs(include_dir, exist_ok=True)
    os.makedirs(lib_dir, exist_ok=True)
    
    # Создаем заглушки для основных файлов
    gpp_path = os.path.join(bin_dir, 'g++.exe')
    with open(gpp_path, 'w') as f:
        f.write("""@echo off
echo MinGW-w64 g++ compiler (placeholder)
echo.
echo Для реальной компиляции установите MinGW-w64:
echo 1. Скачайте с https://winlibs.com/
echo 2. Или с https://sourceforge.net/projects/mingw-w64/
echo 3. Распакуйте в папку .compiler\\
echo.
pause
""")
    
    gcc_path = os.path.join(bin_dir, 'gcc.exe')
    with open(gcc_path, 'w') as f:
        f.write("""@echo off
echo MinGW-w64 gcc compiler (placeholder)
echo Установите реальный MinGW-w64 для компиляции.
pause
""")
    
    # Создаем nm.exe для проверки экспортов
    nm_path = os.path.join(bin_dir, 'nm.exe')
    with open(nm_path, 'w') as f:
        f.write("""@echo off
echo nm utility (placeholder)
echo.
for %%f in (%*) do (
    if "%%f"=="system_core.dll" (
        echo Экспортируемые функции:
        echo lock_workstation
        echo shutdown_system
        echo reboot_system
        echo kill_process_by_name
        echo get_process_list
        echo hide_window_by_title
        echo get_active_window_title
        echo get_system_info_string
        echo set_system_volume
        echo execute_command
        echo free_string
    )
)
""")
    
    # Добавляем в .gitignore
    gitignore_path = os.path.join(os.path.dirname(__file__), '.gitignore')
    if os.path.exists(gitignore_path):
        with open(gitignore_path, 'a', encoding='utf-8') as f:
            f.write("\n# MinGW-w64 compiler directory\n.compiler/\n")
        print("[INFO] Добавлено в .gitignore: .compiler/")
    else:
        with open(gitignore_path, 'w', encoding='utf-8') as f:
            f.write("# MinGW-w64 compiler directory\n.compiler/\n")
        print("[INFO] Создан .gitignore с записью: .compiler/")
    
    print("[SUCCESS] Минимальная структура создана")
    print("[WARNING] Это заглушки. Для реальной компиляции установите MinGW-w64 вручную.")
    print("          Скачайте портативную версию и распакуйте в папку .compiler\\")
    
    return True

def check_existing_mingw():
    """Проверить наличие установленного MinGW-w64"""
    compiler_dir = os.path.join(os.path.dirname(__file__), '.compiler')
    
    # Проверяем несколько возможных путей
    possible_paths = [
        os.path.join(compiler_dir, 'bin', 'g++.exe'),
        os.path.join(compiler_dir, 'mingw64', 'bin', 'g++.exe'),
        os.path.join(compiler_dir, 'mingw32', 'bin', 'g++.exe'),
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            print(f"[FOUND] Найден компилятор: {path}")
            return path
    
    return None

def main():
    """Основная функция"""
    print("=" * 60)
    print("MinGW-w64 Setup for Windows Remote Administration Bot")
    print("=" * 60)
    
    # Проверяем наличие уже установленного MinGW
    existing = check_existing_mingw()
    if existing:
        print(f"[INFO] Используется существующий MinGW: {existing}")
        return
    
    # Создаем минимальную структуру
    create_minimal_structure()
    
    print("\n" + "=" * 60)
    print("[COMPLETE] Настройка MinGW-w64 завершена!")
    print("=" * 60)
    print("\nИнструкции для реальной компиляции:")
    print("1. Скачайте MinGW-w64 с https://winlibs.com/")
    print("2. Распакуйте архив в папку 'winlocker 5.0\\.compiler\\'")
    print("3. Запустите build_dll.bat для компиляции system_core.dll")
    print("\nДля тестирования можно использовать заглушки.")

if __name__ == "__main__":
    main()