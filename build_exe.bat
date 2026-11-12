@echo off
setlocal

echo =====================================
echo Construction de ProtoLab.exe
echo =====================================
echo Prerequis : Python 3.11+ et Node.js 20+ dans le PATH.

if not exist .venv\Scripts\python.exe (
    python -m venv .venv
    if errorlevel 1 goto :error
)
call .venv\Scripts\activate.bat

echo.
echo [1/3] Dependances Python...
python -m pip install --upgrade pip
pip install -r backend\requirements.txt pyinstaller
if errorlevel 1 goto :error

echo.
echo [2/3] Compilation du frontend...
pushd frontend
call npm ci
if errorlevel 1 (
    popd
    goto :error
)
call npm run build
if errorlevel 1 (
    popd
    goto :error
)
popd

echo.
echo [3/3] Creation de l executable...
pyinstaller --noconfirm ProtoLab.spec
if errorlevel 1 goto :error

echo.
echo Termine : dist\ProtoLab.exe
pause
exit /b 0

:error
echo.
echo Une erreur est survenue pendant la construction.
pause
exit /b 1
