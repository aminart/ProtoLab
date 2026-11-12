@echo off
setlocal

echo =====================================
echo Installation de ProtoLab (backend Python + frontend React)
echo =====================================

where py >nul 2>nul
if %errorlevel%==0 (
    set PYTHON_CMD=py
) else (
    where python >nul 2>nul
    if %errorlevel%==0 (
        set PYTHON_CMD=python
    ) else (
        echo Python n'est pas installe ou non disponible dans le PATH.
        echo Installez Python 3.11+ depuis https://www.python.org/downloads/windows/
        pause
        exit /b 1
    )
)

echo.
echo [1/5] Creation de l'environnement virtuel...
%PYTHON_CMD% -m venv .venv
if errorlevel 1 goto :error

echo.
echo [2/5] Mise a jour de pip...
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
if errorlevel 1 goto :error

echo.
echo [3/5] Installation des dependances...
pip install -r backend\requirements.txt
if errorlevel 1 goto :error

echo.
echo [4/5] Installation des dependances du frontend...
where npm >nul 2>nul
if errorlevel 1 (
    echo Node.js n'est pas installe ou non disponible dans le PATH.
    echo Installez Node.js 20+ depuis https://nodejs.org/
    goto :error
)
pushd frontend
call npm install
if errorlevel 1 (
    popd
    goto :error
)

echo.
echo [5/5] Compilation du frontend...
call npm run build
if errorlevel 1 (
    popd
    goto :error
)
popd

echo.
echo Installation terminee.
echo Lancez start_app.bat : au premier lancement, l'application demande l'URL du service,
echo la cle API et le certificat (.crt).
pause
exit /b 0

:error
echo.
echo Une erreur est survenue pendant l'installation.
pause
exit /b 1
