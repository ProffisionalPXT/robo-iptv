@echo off
chcp 65001 > nul
title Monitor IPTV - Painel de Clientes
color 0b

echo ============================================================
echo           ROBO MONITOR DE CLIENTES IPTV
echo ============================================================
echo.

cd /d "%~dp0"
python monitor_iptv.py

echo.
echo ============================================================
echo Execucao finalizada. Pressione qualquer tecla para fechar.
pause > nul
