@echo off
echo ========================================
echo Компиляция Watchdog...
echo ========================================

REM Проверка наличия PyInstaller
where pyinstaller >nul 2>nul
if %errorlevel% neq 0 (
    echo Ошибка: PyInstaller не найден!
    echo Установите PyInstaller: pip install pyinstaller
    pause
    exit /b 1
)

REM Проверка наличия файла watchdog.py
if not exist "watchdog.py" (
    echo Ошибка: Файл watchdog.py не найден!
    pause
    exit /b 1
)

echo Очистка предыдущих сборок...
if exist "build" rmdir /s /q build
if exist "dist" rmdir /s /q dist

echo Компиляция с параметрами --onefile --noconsole...
pyinstaller --onefile --noconsole --name "watchdog" watchdog.py

if %errorlevel% equ 0 (
    echo.
    echo ========================================
    echo ✅ Компиляция успешно завершена!
    echo ========================================
    echo Исполняемый файл: dist\watchdog.exe
    echo Размер: 
    for %%F in (dist\watchdog.exe) do echo   %%~zF байт
    echo.
    echo Для запуска: dist\watchdog.exe
    echo.
    echo ⚠️  Важно: watchdog.exe должен находиться в одной директории с mainbot.exe
) else (
    echo.
    echo ========================================
    echo ❌ Ошибка компиляции!
    echo ========================================
)

pause