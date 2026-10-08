import os
import json
import time
import sys
import re
import unicodedata
import threading
from datetime import datetime
import requests

# Garante suporte a UTF-8 no console do Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from monitor_iptv import (
    executar_monitor,
    formatar_relatorio_proximos,
    formatar_relatorio_todos,
    formatar_detalhe_cliente,
    CLIENTES_JSON
)

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")

def carregar_config():
    if not os.path.exists(CONFIG_PATH):
        return {}
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def carregar_clientes_salvos() -> list:
    if os.path.exists(CLIENTES_JSON):
        try:
            with open(CLIENTES_JSON, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return []

def normalizar_texto(texto: str) -> str:
    """Remove acentos e padroniza para minúsculas."""
    if not texto:
        return ""
    return unicodedata.normalize("NFKD", texto).encode("ASCII", "ignore").decode("utf-8").strip().lower()

def buscar_clientes_por_termo(termo: str, clientes: list) -> list:
    """Busca inteligente de clientes com normalização e limpeza de prefixos."""
    termo_norm = normalizar_texto(termo)
    # Remove prefixos como 'login', 'senha', 'ver', 'dados'
    termo_norm = re.sub(r"^(login|senha|ver|dados|acesso|usuario)\s+", "", termo_norm).strip()
    
    if not termo_norm:
        return []

    encontrados = []
    for c in clientes:
        nome_norm = normalizar_texto(c.get("nome", ""))
        user_norm = normalizar_texto(c.get("usuario", ""))
        id_norm = normalizar_texto(c.get("id", ""))
        tel_norm = normalizar_texto(c.get("whatsapp", ""))

        if (termo_norm in nome_norm or 
            termo_norm == user_norm or 
            termo_norm == id_norm or 
            (len(termo_norm) >= 4 and termo_norm in tel_norm)):
            encontrados.append(c)
    return encontrados

def enviar_mensagem_com_teclado(chat_id, texto: str, token: str):
    """Envia mensagem para o Telegram com botões fixos no teclado."""
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    
    teclado = {
        "keyboard": [
            [{"text": "⏳ Próximos (5 dias)"}],
            [{"text": "📋 Todos os Clientes"}, {"text": "🔑 Ver Login/Senha"}],
            [{"text": "🔄 Atualizar Painel"}]
        ],
        "resize_keyboard": True,
        "is_persistent": True
    }

    payload = {
        "chat_id": chat_id,
        "text": texto,
        "parse_mode": "HTML",
        "reply_markup": teclado,
        "disable_web_page_preview": True
    }

    try:
        requests.post(url, json=payload, timeout=15)
    except Exception as e:
        print(f"[ERRO TELEGRAM] {e}")

def rotina_agendamento_diario(token: str, chat_id: str, hora_alvo: str = "10:00", dias_alerta: int = 5):
    """Dispara o alerta diário às 10:00 AM."""
    ultima_data_executada = ""

    while True:
        try:
            agora = datetime.now()
            hora_atual = agora.strftime("%H:%M")
            data_atual = agora.strftime("%Y-%m-%d")

            if hora_atual == hora_alvo and ultima_data_executada != data_atual:
                ultima_data_executada = data_atual
                print(f"[AGENDADOR] Enviando resumo das {hora_alvo}...")

                # Executa atualização em segundo plano
                try:
                    clientes = executar_monitor(silencioso=True)
                except Exception:
                    clientes = carregar_clientes_salvos()

                relatorio = formatar_relatorio_proximos(clientes, dias_alerta)
                msg_final = f"☀️ <b>BOM DIA! RESUMO MATINAL DAS {hora_alvo}</b>\n\n" + relatorio
                enviar_mensagem_com_teclado(chat_id, msg_final, token)
        except Exception as e:
            print(f"[ERRO AGENDADOR] {e}")

        time.sleep(30)

def loop_polling_bot():
    """Loop principal de escuta de mensagens do Telegram."""
    config = carregar_config()
    cfg_telegram = config.get("telegram", {})
    token = cfg_telegram.get("bot_token", "").strip()
    chat_id = str(cfg_telegram.get("chat_id", "")).strip()
    dias_alerta = config.get("configuracoes", {}).get("dias_alerta_proximos", 5)
    hora_alerta = config.get("configuracoes", {}).get("hora_alerta_diario", "10:00")

    if not token or not chat_id:
        print("[ERRO] Token ou Chat ID ausente no config.json.")
        return

    # Inicia a thread do agendador diário
    t_agendador = threading.Thread(
        target=rotina_agendamento_diario,
        args=(token, chat_id, hora_alerta, dias_alerta),
        daemon=True
    )
    t_agendador.start()

    msg_inicio = (
        "👋 <b>Olá, Gabriel! Bot IPTV Monitor Conectado!</b>\n\n"
        "Toque em um dos botões abaixo a qualquer momento:\n\n"
        "⏳ <b>Próximos (5 dias)</b>: Vencimentos próximos\n"
        "📋 <b>Todos os Clientes</b>: Lista com nome, login e valor\n"
        "🔑 <b>Ver Login/Senha</b>: Consulta a senha de qualquer cliente\n"
        "🔄 <b>Atualizar Painel</b>: Sincroniza dados com o site"
    )

    print("[STATUS] Bot iniciado e aguardando comandos...\n")

    ultimo_update_id = 0
    url_updates = f"https://api.telegram.org/bot{token}/getUpdates"

    # Consome mensagens anteriores
    try:
        resp = requests.get(url_updates, params={"offset": -1}, timeout=10).json()
        if resp.get("ok") and resp.get("result"):
            ultimo_update_id = resp["result"][-1]["update_id"]
    except Exception:
        pass

    while True:
        try:
            params = {"offset": ultimo_update_id + 1, "timeout": 20}
            resp = requests.get(url_updates, params=params, timeout=25).json()

            if resp.get("ok") and resp.get("result"):
                for upd in resp["result"]:
                    ultimo_update_id = upd["update_id"]
                    msg = upd.get("message", {})
                    texto_user = msg.get("text", "").strip()
                    sender_id = str(msg.get("chat", {}).get("id", ""))

                    if sender_id != chat_id:
                        continue

                    print(f"[COMANDO RECEBIDO] {texto_user}")
                    txt_lower = texto_user.lower()
                    clientes = carregar_clientes_salvos()

                    # 1. PRÓXIMOS (5 DIAS)
                    if "próximos" in txt_lower or "proximos" in txt_lower or txt_lower == "/proximos":
                        relatorio = formatar_relatorio_proximos(clientes, dias_alerta)
                        enviar_mensagem_com_teclado(chat_id, relatorio, token)

                    # 2. TODOS OS CLIENTES
                    elif "todos" in txt_lower or txt_lower == "/todos":
                        relatorio = formatar_relatorio_todos(clientes)
                        enviar_mensagem_com_teclado(chat_id, relatorio, token)

                    # 3. VER LOGIN/SENHA (BOTÃO OU COMANDO)
                    elif txt_lower in ["🔑 ver login/senha", "ver login/senha", "ver login", "/login", "login", "senha"]:
                        linhas_menu = ["🔑 <b>CONSULTA DE LOGIN E SENHA</b>\n", "Digite o <b>nome</b> do cliente ou o <b>número</b>:\n"]
                        for i, c in enumerate(clientes, start=1):
                            linhas_menu.append(f"{i} - <b>{c.get('nome')}</b>")
                        linhas_menu.append("\n<i>Exemplo: digite 'Tadeu', 'Fernando' ou o número '7'</i>")
                        enviar_mensagem_com_teclado(chat_id, "\n".join(linhas_menu), token)

                    # 4. ATUALIZAR PAINEL
                    elif "atualizar" in txt_lower or "verificar" in txt_lower or txt_lower == "/atualizar":
                        enviar_mensagem_com_teclado(chat_id, "🔄 <i>Acessando o painel para atualizar os dados... Aguarde cerca de 15 segundos.</i>", token)
                        try:
                            clientes = executar_monitor(silencioso=True)
                            msg_sucesso = f"✅ <b>Painel sincronizado com sucesso!</b>\nForam atualizados <b>{len(clientes)} clientes</b> com logins e senhas.\n\n"
                            msg_sucesso += formatar_relatorio_proximos(clientes, dias_alerta)
                            enviar_mensagem_com_teclado(chat_id, msg_sucesso, token)
                        except Exception as err:
                            enviar_mensagem_com_teclado(chat_id, f"⚠️ Erro ao atualizar painel: {err}\nUsando dados locais salvos.", token)

                    # 5. DIGITOU UM NÚMERO (1 a 11)
                    elif texto_user.isdigit() and 1 <= int(texto_user) <= len(clientes):
                        cliente_escolhido = clientes[int(texto_user) - 1]
                        enviar_mensagem_com_teclado(chat_id, formatar_detalhe_cliente(cliente_escolhido), token)

                    # 6. DIGITOU NOME (ex: 'Tadeu', 'login Tadeu', 'Fernando', 'Sandra', 'Izabel')
                    else:
                        encontrados = buscar_clientes_por_termo(texto_user, clientes)
                        if len(encontrados) == 1:
                            enviar_mensagem_com_teclado(chat_id, formatar_detalhe_cliente(encontrados[0]), token)
                        elif len(encontrados) > 1:
                            msg_multi = [f"🔍 <b>Encontrei {len(encontrados)} clientes:</b>\n"]
                            for idx, enc in enumerate(encontrados, start=1):
                                msg_multi.append(f"{idx} - <b>{enc.get('nome')}</b> (Login: <code>{enc.get('usuario')}</code>)")
                            msg_multi.append("\n<i>Digite o nome completo desejado para ver os dados.</i>")
                            enviar_mensagem_com_teclado(chat_id, "\n".join(msg_multi), token)
                        elif txt_lower.startswith("/start") or "menu" in txt_lower:
                            enviar_mensagem_com_teclado(chat_id, msg_inicio, token)
                        else:
                            enviar_mensagem_com_teclado(chat_id, f"❓ Cliente '<b>{texto_user}</b>' não encontrado.\n\nDigite o nome de um cliente (ex: <i>Tadeu</i>, <i>Fernando</i>) ou toque no botão abaixo.", token)

        except Exception as e:
            time.sleep(5)

        time.sleep(1)

def iniciar_bot():
    print("=" * 60)
    print("🤖 SERVIÇO DO BOT DO TELEGRAM - IPTV MONITOR")
    print("=" * 60)
    loop_polling_bot()

def iniciar_bot_em_background():
    """Inicia o bot em uma thread em background (para Render / Flask)."""
    t = threading.Thread(target=loop_polling_bot, daemon=True)
    t.start()

if __name__ == "__main__":
    iniciar_bot()
