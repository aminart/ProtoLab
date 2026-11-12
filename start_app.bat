@echo off
setlocal

if not exist .venv\Scripts\python.exe (
    echo L'environnement virtuel est absent.
    echo Lancez d'abord install_windows.bat
    pause
    exit /b 1
)

call .venv\Scripts\activate.bat
if not exist frontend\dist\index.html (
    echo Le frontend n'est pas compile.
    echo Relancez install_windows.bat
    pause
    exit /b 1
)

rem Le lanceur ouvre le navigateur sur http://127.0.0.1:8030 des que le serveur repond.
python backend\launcher.py %*
pause
