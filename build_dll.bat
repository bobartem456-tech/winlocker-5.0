@echo off
echo ========================================
echo Компиляция system_core.dll из C++ кода
echo ========================================

REM Проверяем наличие MinGW-w64
set MINGW_PATH=.compiler\bin
if not exist "%MINGW_PATH%\g++.exe" (
    echo ❌ MinGW-w64 не найден в %MINGW_PATH%
    echo Запустите download_mingw_simple.py для установки компилятора
    pause
    exit /b 1
)

echo ✅ Найден MinGW-w64: %MINGW_PATH%\g++.exe

REM Проверяем наличие исходного файла
if not exist "system_core.cpp" (
    echo ❌ Файл system_core.cpp не найден!
    pause
    exit /b 1
)

echo Компиляция system_core.cpp в system_core.dll...

REM Компилируем DLL
"%MINGW_PATH%\g++.exe" -shared -o system_core.dll system_core.cpp ^
    -static -static-libgcc -static-libstdc++ ^
    -Wl,--subsystem,windows ^
    -lpsapi -luser32 -ladvapi32 -lkernel32

if %errorlevel% equ 0 (
    echo.
    echo ========================================
    echo ✅ Компиляция успешно завершена!
    echo ========================================
    echo Создан файл: system_core.dll
    echo.
    echo Проверка экспортируемых функций:
    "%MINGW_PATH%\nm.exe" system_core.dll | findstr "lock_workstation shutdown_system"
    
    echo.
    echo Для использования в Python:
    echo   import ctypes
    echo   dll = ctypes.CDLL("system_core.dll")
    echo   result = dll.lock_workstation()
) else (
    echo.
    echo ========================================
    echo ❌ Ошибка компиляции!
    echo ========================================
    echo Проверьте наличие всех необходимых библиотек
)

echo.
pause