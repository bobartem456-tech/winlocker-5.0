@echo off
echo ========================================
echo Компиляция Mainbot...
echo ========================================

REM Проверка наличия PyInstaller
where pyinstaller >nul 2>nul
if %errorlevel% neq 0 (
    echo Ошибка: PyInstaller не найден!
    echo Установите PyInstaller: pip install pyinstaller
    pause
    exit /b 1
)

REM Проверка наличия файла main_bot.py
if not exist "main_bot.py" (
    echo Ошибка: Файл main_bot.py не найден!
    pause
    exit /b 1
)

echo Очистка предыдущих сборок...
if exist "build" rmdir /s /q build
if exist "dist" rmdir /s /q dist

echo Компиляция с параметрами --onefile --noconsole...
pyinstaller --onefile --noconsole --name "mainbot" --icon "icon.ico" main_bot.py

if %errorlevel% equ 0 (
    echo.
    echo ========================================
    echo ✅ Компиляция успешно завершена!
    echo ========================================
    echo Исполняемый файл: dist\mainbot.exe
    echo Размер: 
    for %%F in (dist\mainbot.exe) do echo   %%~zF байт
    echo.
    echo Для запуска: dist\mainbot.exe
) else (
    echo.
    echo ========================================
    echo ❌ Ошибка компиляции!
    echo ========================================
)

pause