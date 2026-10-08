@echo off
chcp 65001 > nul
title Teste de Conexao - Telegram Bot
color 0a

echo ============================================================
echo           TESTE DE CONEXAO COM O TELEGRAM
echo ============================================================
echo.

cd /d "%~dp0"
python telegram_notifier.py

echo.
echo ============================================================
pause
