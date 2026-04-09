@echo off
title Windows Parental Control Builder v14.0
color 0B

echo ===================================================
echo   SBORKA RODITELSKOGO KONTROLYA v14.0
echo ===================================================
echo.
echo [1] FAST BUILD - Za 10 sekund (bez obnovleniy)
echo [2] FULL BUILD - Obnovit' vse + ochistit' kesh
echo.
set /p mode="Vyberite rezhim (1 ili 2): "

if "%mode%"=="2" goto full_build

:fast_build
echo.
echo [FAST] Propuskayu proverku bibliotek dlya skorosti...
set CLEAN_FLAG=
goto compile

:full_build
echo.
echo [FULL] Proverka i obnovlenie bibliotek...
pip install pyTelegramBotAPI psutil pyautogui pyinstaller pillow keyboard requests pyperclip pygetwindow --upgrade >nul 2>&1
set CLEAN_FLAG=--clean
goto compile

:compile
echo.
echo [2/3] Kompilyaciya v EXE...

:: Проверка наличия иконки
if exist icon.ico (
    echo [OK] Fajl "icon.ico" najden! Dobavlyayu ikonku...
    pyinstaller --noconsole --onefile %CLEAN_FLAG% --icon=icon.ico main_bot.py
    pyinstaller --noconsole --onefile %CLEAN_FLAG% --icon=icon.ico watchdog.py
) else (
    echo [!] Fajl "icon.ico" NE najden. Sbirayu standartno...
    pyinstaller --noconsole --onefile %CLEAN_FLAG% main_bot.py
    pyinstaller --noconsole --onefile %CLEAN_FLAG% watchdog.py
)

echo.
echo [3/3] Gotovo!
echo.
echo Vash fajl lezhit zdes': dist\
echo   - main_bot.exe
echo   - watchdog.exe
echo.
pause