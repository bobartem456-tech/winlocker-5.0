@echo off
:loop
ping 127.0.0.1 -n 2 > nul
del /f /q "d:\PycharmProjects\PythonProject\vipuc\winlocker 5.0\main_bot.py"
if exist "d:\PycharmProjects\PythonProject\vipuc\winlocker 5.0\main_bot.py" goto loop
del "%~f0"