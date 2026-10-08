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

# Importa funções auxiliares de formatação
try:
    from monitor_iptv import (
        formatar_relatorio_proximos,
        formatar_relatorio_todos,
        formatar_detalhe_cliente,
        executar_monitor,
        CLIENTES_JSON
    )
    TEM_PLAYWRIGHT = True
except Exception:
    TEM_PLAYWRIGHT = False
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    CLIENTES_JSON = os.path.join(BASE_DIR, "clientes_extraidos.json")

    def formatar_relatorio_proximos(clientes: list, dias_alerta: int = 5) -> str:
        hoje = datetime.now()
        vencem_hoje = []
        vencem_breve = []
        vencidos = []
        
        for c in clientes:
            venc_str = c.get("vencimento", "")
            data_match = re.search(r"(\d{2})/(\d{2})/(\d{4})", venc_str)
            if data_match:
                dia, mes, ano = map(int, data_match.groups())
                try:
                    dt_venc = datetime(ano, mes, dia)
                    dias_restantes = (dt_venc.date() - hoje.date()).days
                    c["dias_restantes"] = dias_restantes
                    
                    if dias_restantes < 0 or c.get("status", "").lower() == "vencido":
                        vencidos.append(c)
                    elif dias_restantes == 0:
                        vencem_hoje.append(c)
                    elif 0 < dias_restantes <= dias_alerta:
                        vencem_breve.append(c)
                except Exception:
                    pass

        vencem_breve.sort(key=lambda x: x.get("dias_restantes", 999))
        linhas = [
            "⏳ <b>CLIENTES PRÓXIMOS AO VENCIMENTO (CASSIO)</b>",
            f"📅 <i>Consulta: {hoje.strftime('%d/%m/%Y às %H:%M')}</i>\n"
        ]

        if vencem_hoje:
            linhas.append("🚨 <b>VENCEM HOJE:</b>")
            for c in vencem_hoje:
                linhas.append(f"• <b>{c.get('nome')}</b> (Login: <code>{c.get('usuario')}</code>) — 💰 {c.get('plano')}")
            linhas.append("")

        if vencem_breve:
            linhas.append(f"⚠️ <b>VENCEM NOS PRÓXIMOS {dias_alerta} DIAS:</b>")
            for c in vencem_breve:
                dias = c.get("dias_restantes")
                venc = c.get("vencimento", "").split(",")[0]
                txt_dia = "amanhã" if dias == 1 else f"em {dias} dias"
                tel = c.get("whatsapp", "")
                txt_tel = f" | 📱 {tel}" if tel else ""
                linhas.append(f"• <b>{c.get('nome')}</b> (Login: <code>{c.get('usuario')}</code>){txt_tel}\n  📅 {venc} ({txt_dia}) | 💰 {c.get('plano')}")
            linhas.append("")

        if not vencem_hoje and not vencem_breve:
            linhas.append(f"✅ <i>Nenhum cliente vencendo nos próximos {dias_alerta} dias!</i>\n")

        if vencidos:
            linhas.append(f"❌ <b>Já Vencidos ({len(vencidos)}):</b>")
            for c in vencidos:
                linhas.append(f"• {c.get('nome')} (Venceu em {c.get('vencimento','').split(',')[0]})")
            linhas.append("")

        linhas.append(f"📊 Total de clientes monitorados: <b>{len(clientes)}</b>")
        return "\n".join(linhas)

    def formatar_relatorio_todos(clientes: list) -> str:
        hoje = datetime.now()
        linhas = [
            "📋 <b>LISTA DE TODOS OS CLIENTES (CASSIO)</b>",
            f"👥 Total: <b>{len(clientes)} clientes</b>\n"
        ]
        for i, c in enumerate(clientes, start=1):
            tel = c.get("whatsapp", "")
            txt_tel = f" | 📱 {tel}" if tel else ""
            linhas.append(f"{i}. <b>{c.get('nome')}</b>")
            linhas.append(f"   👤 Login: <code>{c.get('usuario')}</code> | 📅 Venc: {c.get('vencimento','').split(',')[0]} | 💰 {c.get('plano')}{txt_tel}\n")
        linhas.append(f"<i>Atualizado em {hoje.strftime('%d/%m/%Y às %H:%M')}</i>")
        return "\n".join(linhas)

    def formatar_detalhe_cliente(c: dict) -> str:
        linhas = [
            f"🔐 <b>DADOS DE ACESSO - {c.get('nome')}</b>\n",
            f"👤 <b>Usuário:</b> <code>{c.get('usuario')}</code>",
            f"🔑 <b>Senha:</b> <code>{c.get('senha')}</code>",
            f"📅 <b>Vencimento:</b> {c.get('vencimento')}",
            f"💰 <b>Plano:</b> {c.get('plano')}"
        ]
        if c.get("whatsapp"):
            linhas.append(f"📱 <b>WhatsApp:</b> {c.get('whatsapp')}")
        linhas.append("\n<i>Toque no Usuário ou na Senha para copiar rapidamente!</i>")
        return "\n".join(linhas)

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
    if not texto:
        return ""
    return unicodedata.normalize("NFKD", texto).encode("ASCII", "ignore").decode("utf-8").strip().lower()

def buscar_clientes_por_termo(termo: str, clientes: list) -> list:
    termo_norm = normalizar_texto(termo)
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
    ultima_data_executada = ""
    while True:
        try:
            agora = datetime.now()
            hora_atual = agora.strftime("%H:%M")
            data_atual = agora.strftime("%Y-%m-%d")

            if hora_atual == hora_alvo and ultima_data_executada != data_atual:
                ultima_data_executada = data_atual
                clientes = carregar_clientes_salvos()
                relatorio = formatar_relatorio_proximos(clientes, dias_alerta)
                msg_final = f"☀️ <b>BOM DIA! RESUMO MATINAL DAS {hora_alvo}</b>\n\n" + relatorio
                enviar_mensagem_com_teclado(chat_id, msg_final, token)
        except Exception as e:
            print(f"[ERRO AGENDADOR] {e}")
        time.sleep(30)

def loop_polling_bot():
    config = carregar_config()
    cfg_telegram = config.get("telegram", {})
    token = cfg_telegram.get("bot_token", "").strip()
    chat_id = str(cfg_telegram.get("chat_id", "")).strip()
    dias_alerta = config.get("configuracoes", {}).get("dias_alerta_proximos", 5)
    hora_alerta = config.get("configuracoes", {}).get("hora_alerta_diario", "10:00")

    if not token or not chat_id:
        print("[ERRO] Token ou Chat ID ausente no config.json.")
        return

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

                    # 3. VER LOGIN/SENHA (MENU OU BUSCA)
                    elif txt_lower in ["🔑 ver login/senha", "ver login/senha", "ver login", "/login", "login", "senha"]:
                        linhas_menu = ["🔑 <b>CONSULTA DE LOGIN E SENHA</b>\n", "Digite o <b>nome</b> do cliente ou o <b>número</b>:\n"]
                        for i, c in enumerate(clientes, start=1):
                            linhas_menu.append(f"{i} - <b>{c.get('nome')}</b>")
                        linhas_menu.append("\n<i>Exemplo: digite 'Tadeu', 'Fernando' ou o número '7'</i>")
                        enviar_mensagem_com_teclado(chat_id, "\n".join(linhas_menu), token)

                    # 4. ATUALIZAR PAINEL
                    elif "atualizar" in txt_lower or "verificar" in txt_lower or txt_lower == "/atualizar":
                        if TEM_PLAYWRIGHT:
                            enviar_mensagem_com_teclado(chat_id, "🔄 <i>Acessando o painel para atualizar os dados... Aguarde cerca de 15 segundos.</i>", token)
                            try:
                                clientes = executar_monitor(silencioso=True)
                                msg_sucesso = f"✅ <b>Painel sincronizado com sucesso!</b>\nForam atualizados <b>{len(clientes)} clientes</b> com logins e senhas.\n\n"
                                msg_sucesso += formatar_relatorio_proximos(clientes, dias_alerta)
                                enviar_mensagem_com_teclado(chat_id, msg_sucesso, token)
                            except Exception as err:
                                enviar_mensagem_com_teclado(chat_id, f"⚠️ Erro ao atualizar painel: {err}\nUsando dados locais salvos.", token)
                        else:
                            enviar_mensagem_com_teclado(chat_id, "ℹ️ <i>Você está no servidor da nuvem (Render). A sincronização com o site oficial deve ser feita pelo computador onde o Google Chrome oficial está instalado para evitar o bloqueio anti-bot. A base de dados atualizada já está ativa com todos os seus 11 clientes!</i>", token)

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
    t = threading.Thread(target=loop_polling_bot, daemon=True)
    t.start()

if __name__ == "__main__":
    iniciar_bot()
