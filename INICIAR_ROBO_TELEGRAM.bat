@echo off
chcp 65001 > nul
title Bot IPTV Telegram - Servico Ativo
color 0a

echo ============================================================
echo         BOT DO TELEGRAM - MONITOR DE CLIENTES IPTV
echo ============================================================
echo.
echo O bot esta ativo e escutando seus comandos no Telegram!
echo Deixe esta janela aberta ou minimizada.
echo.
echo Para fechar o servico, basta fechar esta janela.
echo ============================================================
echo.

cd /d "%~dp0"
python bot_telegram.py

pause
