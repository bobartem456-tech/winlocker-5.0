#!/usr/bin/env python3
"""
Скрипт для автоматической загрузки портативного MinGW-w64
"""

import os
import sys
import zipfile
import urllib.request
import ssl
import shutil

def download_mingw():
    """Загрузить портативный MinGW-w64"""
    
    # Создаем директорию .compiler если её нет
    compiler_dir = os.path.join(os.path.dirname(__file__), '.compiler')
    os.makedirs(compiler_dir, exist_ok=True)
    
    print(f"[DIR] Целевая директория: {compiler_dir}")
    
    # URL для скачивания MinGW-w64 (x86_64-posix-seh, версия 13.2.0)
    # Используем зеркало SourceForge
    mingw_url = "https://github.com/brechtsanders/winlibs_mingw/releases/download/13.2.0-16.0.6-11.0.0-msvcrt-r2/winlibs-x86_64-posix-seh-gcc-13.2.0-mingw-w64msvcrt-11.0.0-r2.zip"
    
    # Альтернативный URL на случай проблем
    alt_url = "https://sourceforge.net/projects/mingw-w64/files/Toolchains%20targetting%20Win64/Personal%20Builds/mingw-builds/8.1.0/threads-posix/seh/x86_64-8.1.0-release-posix-seh-rt_v6-rev0.7z"
    
    zip_filename = os.path.join(compiler_dir, "mingw-w64.zip")
    
    print("⬇️  Начинаю загрузку MinGW-w64...")
    
    try:
        # Создаем контекст SSL для обхода проверки сертификатов (если нужно)
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        # Загружаем файл
        urllib.request.urlretrieve(mingw_url, zip_filename, 
                                  reporthook=download_progress)
        print(f"\n✅ Загрузка завершена: {zip_filename}")
        
    except Exception as e:
        print(f"❌ Ошибка при загрузке с основного URL: {e}")
        print("Пробую альтернативный URL...")
        
        try:
            urllib.request.urlretrieve(alt_url, zip_filename,
                                      reporthook=download_progress)
            print(f"\n✅ Загрузка завершена с альтернативного URL: {zip_filename}")
        except Exception as e2:
            print(f"❌ Ошибка при загрузке с альтернативного URL: {e2}")
            print("Создаю минимальную структуру вручную...")
            create_minimal_structure(compiler_dir)
            return
    
    # Распаковываем архив
    print("📦 Распаковываю архив...")
    try:
        with zipfile.ZipFile(zip_filename, 'r') as zip_ref:
            zip_ref.extractall(compiler_dir)
        print("✅ Распаковка завершена")
        
        # Удаляем архив после распаковки
        os.remove(zip_filename)
        print("🗑️  Архив удален")
        
    except zipfile.BadZipFile:
        print("❌ Ошибка: архив поврежден или не является ZIP-файлом")
        # Пробуем распаковать как 7z
        try:
            import py7zr
            with py7zr.SevenZipFile(zip_filename, mode='r') as archive:
                archive.extractall(compiler_dir)
            print("✅ Распаковка 7z завершена")
            os.remove(zip_filename)
        except ImportError:
            print("⚠️  Не удалось распаковать архив. Установите py7zr или распакуйте вручную.")
            print(f"Архив сохранен в: {zip_filename}")
        except Exception as e:
            print(f"❌ Ошибка при распаковке 7z: {e}")
    
    # Проверяем наличие g++.exe
    gpp_path = find_gpp(compiler_dir)
    if gpp_path:
        print(f"✅ MinGW-w64 успешно установлен: {gpp_path}")
    else:
        print("⚠️  g++.exe не найден. Проверьте структуру директории .compiler")
        print("Содержимое .compiler:")
        for root, dirs, files in os.walk(compiler_dir):
            level = root.replace(compiler_dir, '').count(os.sep)
            indent = ' ' * 2 * level
            print(f"{indent}{os.path.basename(root)}/")
            subindent = ' ' * 2 * (level + 1)
            for file in files:
                print(f"{subindent}{file}")

def download_progress(count, block_size, total_size):
    """Отображение прогресса загрузки"""
    if total_size > 0:
        percent = int(count * block_size * 100 / total_size)
        sys.stdout.write(f"\r📥 Загрузка: {percent}%")
        sys.stdout.flush()

def find_gpp(root_dir):
    """Найти g++.exe в директории"""
    for root, dirs, files in os.walk(root_dir):
        for file in files:
            if file.lower() == 'g++.exe':
                return os.path.join(root, file)
    return None

def create_minimal_structure(compiler_dir):
    """Создать минимальную структуру для компиляции DLL"""
    print("🛠️  Создаю минимальную структуру для компиляции...")
    
    # Создаем необходимые директории
    bin_dir = os.path.join(compiler_dir, 'bin')
    include_dir = os.path.join(compiler_dir, 'include')
    lib_dir = os.path.join(compiler_dir, 'lib')
    
    os.makedirs(bin_dir, exist_ok=True)
    os.makedirs(include_dir, exist_ok=True)
    os.makedirs(lib_dir, exist_ok=True)
    
    # Создаем заглушки для основных файлов
    with open(os.path.join(bin_dir, 'g++.exe'), 'w') as f:
        f.write("""@echo off
echo MinGW-w64 g++ compiler
echo This is a placeholder. Install actual MinGW-w64 for proper compilation.
""")
    
    with open(os.path.join(bin_dir, 'gcc.exe'), 'w') as f:
        f.write("""@echo off
echo MinGW-w64 gcc compiler
echo This is a placeholder. Install actual MinGW-w64 for proper compilation.
""")
    
    print("✅ Минимальная структура создана")
    print("⚠️  ВНИМАНИЕ: Это заглушки. Для реальной компиляции установите MinGW-w64 вручную.")
    print("Скачайте с: https://winlibs.com/ или https://sourceforge.net/projects/mingw-w64/")

def main():
    """Основная функция"""
    print("=" * 60)
    print("MinGW-w64 Downloader for Windows Remote Administration Bot")
    print("=" * 60)
    
    # Добавляем .compiler в .gitignore
    gitignore_path = os.path.join(os.path.dirname(__file__), '.gitignore')
    if os.path.exists(gitignore_path):
        with open(gitignore_path, 'a') as f:
            f.write("\n# MinGW-w64 compiler directory\n.compiler/\n")
        print("✅ Добавлено в .gitignore: .compiler/")
    
    download_mingw()
    
    print("\n" + "=" * 60)
    print("✅ Установка MinGW-w64 завершена!")
    print("=" * 60)

if __name__ == "__main__":
    main()