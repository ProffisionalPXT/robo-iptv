Set WshShell = CreateObject("WScript.Shell")

' Aguarda 25 segundos para o Windows carregar a rede e o Wi-Fi
WScript.Sleep 25000

' Caminho da pasta e script
Dim scriptPath
scriptPath = "C:\Users\TRANSRAP05\Desktop\iptv-monitor-bot\monitor_iptv.py"

' Executa 100% invisivel (o parametro 0 oculta qualquer janela)
WshShell.Run "pythonw.exe """ & scriptPath & """", 0, False
