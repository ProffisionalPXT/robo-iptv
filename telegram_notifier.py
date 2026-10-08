import json
import os
import sys
import requests

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")

def carregar_config():
    if not os.path.exists(CONFIG_PATH):
        return {}
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def enviar_mensagem_telegram(mensagem: str, parse_mode: str = "HTML") -> bool:
    """Envia uma mensagem para o chat do Telegram configurado."""
    config = carregar_config()
    telegram_cfg = config.get("telegram", {})
    
    token = telegram_cfg.get("bot_token", "").strip()
    chat_id = str(telegram_cfg.get("chat_id", "")).strip()

    if not token or token == "SEU_BOT_TOKEN_AQUI":
        print("[Telegram] Token do bot nao configurado no config.json.")
        return False

    if not chat_id or chat_id == "SEU_CHAT_ID_AQUI":
        print("[Telegram] Chat ID nao configurado no config.json.")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": mensagem,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True
    }

    try:
        response = requests.post(url, json=payload, timeout=15)
        res_json = response.json()
        if response.status_code == 200 and res_json.get("ok"):
            print("[Telegram] Mensagem enviada com sucesso!")
            return True
        else:
            print(f"[Telegram] Falha ao enviar: {res_json.get('description', response.text)}")
            return False
    except Exception as e:
        print(f"[Telegram] Erro de conexao ao enviar: {e}")
        return False

def testar_conexao():
    """Testa a conexao com o bot do Telegram."""
    print("=" * 50)
    print("TESTE DE CONEXAO COM TELEGRAM")
    print("=" * 50)
    
    config = carregar_config()
    telegram_cfg = config.get("telegram", {})
    token = telegram_cfg.get("bot_token", "").strip()
    chat_id = str(telegram_cfg.get("chat_id", "")).strip()

    if not token or token == "SEU_BOT_TOKEN_AQUI":
        print("[ERRO] Por favor, preencha o campo 'bot_token' no arquivo config.json.")
        return

    if not chat_id or chat_id == "SEU_CHAT_ID_AQUI":
        print("[ERRO] Por favor, preencha o campo 'chat_id' no arquivo config.json.")
        return

    try:
        url_me = f"https://api.telegram.org/bot{token}/getMe"
        resp_me = requests.get(url_me, timeout=10).json()
        if not resp_me.get("ok"):
            print(f"[ERRO] Token invalido: {resp_me.get('description')}")
            return
        bot_user = resp_me["result"].get("username", "Bot")
        print(f"[SUCESSO] Bot identificado: @{bot_user}")
    except Exception as e:
        print(f"[ERRO] Falha ao validar token: {e}")
        return

    msg_teste = (
        "🚀 <b>Monitor IPTV - Conexão Bem-Sucedida!</b>\n\n"
        "Este canal está configurado para receber os relatórios e alertas de vencimento dos clientes."
    )
    sucesso = enviar_mensagem_telegram(msg_teste)
    if sucesso:
        print("[SUCESSO] Teste concluido! Mensagem enviada para o seu Telegram.")
    else:
        print("[AVISO] Verifique se voce iniciou a conversa com o bot (/start) antes do teste.")

if __name__ == "__main__":
    testar_conexao()
