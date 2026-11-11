Set WshShell = CreateObject("WScript.Shell")

' Aguarda 25 segundos para o Windows carregar a rede e o Wi-Fi
WScript.Sleep 25000

Dim folderPath
folderPath = "C:\Users\TRANSRAP05\Desktop\iptv-monitor-bot"
WshShell.CurrentDirectory = folderPath

' 1. Inicia o robo de atendimento do Telegram em segundo plano continuo (invisivel)
WshShell.Run "pythonw.exe bot_telegram.py", 0, False

' 2. Executa a sincronizacao matinal do painel
WshShell.Run "pythonw.exe monitor_iptv.py", 0, False
