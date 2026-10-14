@echo off
chcp 65001 >nul
title Gerando EmuHub.exe
cd /d "%~dp0"

echo Instalando/atualizando PyInstaller e Pillow...
python -m pip install --upgrade pyinstaller pillow
if errorlevel 1 (
    echo.
    echo [ERRO] Nao consegui usar o Python. Instale em python.org e marque "Add to PATH".
    pause
    exit /b 1
)

echo.
echo Gerando o executavel...
python -m PyInstaller --onefile --windowed --name EmuHub emu_hub.py
if errorlevel 1 (
    echo.
    echo [ERRO] Falha ao gerar o .exe.
    pause
    exit /b 1
)

echo.
echo ============================================
echo  Pronto! Seu programa esta em:
echo  %~dp0dist\EmuHub.exe
echo ============================================
echo Pode copiar o EmuHub.exe para onde quiser.
echo A config (hub_config.json) sera criada ao lado dele.
pause
