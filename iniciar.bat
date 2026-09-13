@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\activate.bat" (
    echo ============================================
    echo  Primeira execucao: instalando o sistema...
    echo  (isso pode levar um minuto)
    echo ============================================
    python -m venv .venv
    if errorlevel 1 (
        echo.
        echo ERRO: Python nao foi encontrado.
        echo Instale o Python em https://www.python.org/downloads/
        echo e marque a opcao "Add python.exe to PATH" durante a instalacao.
        echo Depois execute este arquivo novamente.
        echo.
        pause
        exit /b 1
    )

    call .venv\Scripts\activate.bat
    pip install -r requirements.txt
    python manage.py migrate

    echo.
    echo ============================================
    echo  Crie o usuario administrador do sistema
    echo  (informe um nome de usuario e uma senha)
    echo ============================================
    python manage.py createsuperuser
) else (
    call .venv\Scripts\activate.bat
    python manage.py migrate
)

echo.
echo Iniciando o servidor...
start "Servidor - Sistema da Clinica (feche esta janela para desligar)" cmd /k "call .venv\Scripts\activate.bat && python manage.py runserver"

timeout /t 3 /nobreak >nul
start "" http://127.0.0.1:8000/

echo.
echo O sistema esta rodando em outra janela chamada
echo "Servidor - Sistema da Clinica".
echo.
echo Para PARAR o sistema, feche aquela janela.
echo Esta janela aqui ja pode ser fechada.
echo.
pause
