@echo off
chcp 65001 >nul
echo ============================================================
echo Компиляция WinLocker 5.0 в EXE (Оптимизированная)
echo ============================================================
echo.

echo [1/3] Компиляция MainBot.exe (без очистки для скорости)...
REM Используем --noconfirm для пропуска вопросов и убираем --clean для скорости
pyinstaller main_bot.spec --noconfirm
if errorlevel 1 (
    echo ❌ Ошибка компиляции MainBot!
    goto :error
)
echo.

echo [2/3] Компиляция Watchdog.exe...
pyinstaller watchdog.spec --noconfirm
if errorlevel 1 (
    echo ❌ Ошибка компиляции Watchdog!
    goto :error
)
echo.

echo [3/3] Копирование необходимых файлов...
copy /Y config.py dist\ >nul
copy /Y secure_config.py dist\ >nul
copy /Y .env dist\ >nul
copy /Y icon.ico dist\ >nul 2>nul

echo.
echo ============================================================
echo ✅ Компиляция завершена успешно!
echo ============================================================
echo.
echo Файлы находятся в папке: dist\
echo   - MainBot.exe
echo   - Watchdog.exe
echo   - config.py
echo   - secure_config.py
echo   - .env
echo.
echo ⚡ Для быстрой компиляции в следующий раз:
echo    - Флаг --clean убирается (кэширование PyInstaller)
echo    - Используйте --noconfirm для пропуска вопросов
echo.
echo Для запуска бота используйте:
echo   1. Watchdog.exe (запускает и мониторит MainBot.exe)
echo   ИЛИ
echo   2. MainBot.exe (отдельный запуск)
echo.
pause

:error
echo.
echo ============================================================
echo ❌ Ошибка компиляции!
echo ============================================================
echo Проверьте логи выше для диагностики
pause
exit /b 1
