import os
import json
import time
import re
import sys
from datetime import datetime
import requests

# Garante suporte a UTF-8 no console do Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from playwright.sync_api import sync_playwright
from telegram_notifier import carregar_config, enviar_mensagem_telegram

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SESSAO_DIR = os.path.join(BASE_DIR, "sessao_chrome")
CLIENTES_JSON = os.path.join(BASE_DIR, "clientes_extraidos.json")

def formatar_relatorio_proximos(clientes: list, dias_alerta: int = 5) -> str:
    """Gera relatório para o Telegram focando em clientes próximos ao vencimento."""
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

    linhas = []
    linhas.append("⏳ <b>CLIENTES PRÓXIMOS AO VENCIMENTO (CASSIO)</b>")
    linhas.append(f"📅 <i>Consulta: {hoje.strftime('%d/%m/%Y às %H:%M')}</i>\n")

    if vencem_hoje:
        linhas.append("🚨 <b>VENCEM HOJE:</b>")
        for c in vencem_hoje:
            nome = c.get("nome", "Cliente")
            valor = c.get("plano", "").replace("Plano:", "").strip()
            user = c.get("usuario", "")
            tel = c.get("whatsapp", "")
            txt_tel = f"\n  📱 WhatsApp: {tel}" if tel else ""
            linhas.append(f"• <b>{nome}</b> (Login: <code>{user}</code>) — 💰 {valor}{txt_tel}")
        linhas.append("")

    if vencem_breve:
        linhas.append(f"⚠️ <b>VENCEM NOS PRÓXIMOS {dias_alerta} DIAS:</b>")
        for c in vencem_breve:
            nome = c.get("nome", "Cliente")
            dias = c.get("dias_restantes")
            venc = c.get("vencimento", "").split(",")[0]
            valor = c.get("plano", "").replace("Plano:", "").strip()
            user = c.get("usuario", "")
            tel = c.get("whatsapp", "")
            txt_tel = f" | 📱 {tel}" if tel else ""
            txt_dia = "amanhã" if dias == 1 else f"em {dias} dias"
            linhas.append(f"• <b>{nome}</b> (Login: <code>{user}</code>){txt_tel}\n  📅 {venc} ({txt_dia}) | 💰 {valor}")
        linhas.append("")

    if not vencem_hoje and not vencem_breve:
        linhas.append(f"✅ <i>Nenhum cliente vencendo nos próximos {dias_alerta} dias!</i>\n")

    if vencidos:
        linhas.append(f"❌ <b>Já Vencidos ({len(vencidos)}):</b>")
        for c in vencidos:
            nome = c.get("nome", "Cliente")
            venc = c.get("vencimento", "").split(",")[0]
            linhas.append(f"• {nome} (Venceu em {venc})")
        linhas.append("")

    linhas.append(f"📊 Total de clientes monitorados: <b>{len(clientes)}</b>")
    return "\n".join(linhas)

def formatar_relatorio_todos(clientes: list) -> str:
    """Gera lista completa de todos os clientes monitorados (apenas Cassio / P2Player)."""
    hoje = datetime.now()
    linhas = []
    linhas.append("📋 <b>LISTA DE TODOS OS CLIENTES (CASSIO)</b>")
    linhas.append(f"👥 Total: <b>{len(clientes)} clientes</b>\n")

    for i, c in enumerate(clientes, start=1):
        nome = c.get("nome", "Cliente")
        user = c.get("usuario", c.get("id", ""))
        venc = c.get("vencimento", "").split(",")[0]
        plano = c.get("plano", "").replace("Plano:", "").strip()
        tel = c.get("whatsapp", "")
        txt_tel = f" | 📱 {tel}" if tel else ""
        txt_plano = f" | 💰 {plano}" if plano else ""
        linhas.append(f"{i}. <b>{nome}</b>")
        linhas.append(f"   👤 Login: <code>{user}</code> | 📅 Venc: {venc}{txt_plano}{txt_tel}\n")

    linhas.append(f"<i>Atualizado em {hoje.strftime('%d/%m/%Y às %H:%M')}</i>")
    return "\n".join(linhas)

def formatar_detalhe_cliente(c: dict) -> str:
    """Formata os dados completos de acesso (login, senha, etc) de um cliente."""
    nome = c.get("nome", "Cliente")
    user = c.get("usuario", c.get("id", ""))
    senha = c.get("senha", "Não capturada")
    venc = c.get("vencimento", "")
    plano = c.get("plano", "")
    tel = c.get("whatsapp", "")

    linhas = [
        f"🔐 <b>DADOS DE ACESSO - {nome}</b>\n",
        f"👤 <b>Usuário:</b> <code>{user}</code>",
        f"🔑 <b>Senha:</b> <code>{senha}</code>",
        f"📅 <b>Vencimento:</b> {venc}",
        f"💰 <b>Plano:</b> {plano}"
    ]
    if tel:
        linhas.append(f"📱 <b>WhatsApp:</b> {tel}")
    
    linhas.append("\n<i>Toque no Usuário ou na Senha para copiar rapidamente!</i>")
    return "\n".join(linhas)

def tentar_fazer_login(page, usuario, senha):
    """Detecta campos de login e realiza autenticação no Chrome real."""
    try:
        cassio_el = page.locator("text='Cassio'")
        if cassio_el.count() > 0:
            cassio_el.first.click()
            page.wait_for_timeout(1000)
        
        pass_input = page.locator("input[type='password']")
        if pass_input.count() > 0 and senha:
            pass_input.first.fill(senha)
            btn_entrar = page.locator("button:has-text('Entrar'), button[type='submit']")
            if btn_entrar.count() > 0:
                btn_entrar.first.click()
            else:
                pass_input.first.press("Enter")
            page.wait_for_timeout(5000)
            return True
        return False
    except Exception as e:
        print(f"[LOGIN] Erro: {e}")
        return False

def extrair_clientes_completos(page) -> list:
    """Extrai os dados da tabela e visita cada página de edição para extrair as senhas."""
    page.wait_for_timeout(3000)
    
    page.evaluate("""() => {
        const modal = document.querySelector('#latestChangesModal, .modal.show');
        if (modal) modal.remove();
        const backdrop = document.querySelector('.modal-backdrop');
        if (backdrop) backdrop.remove();
    }""")
    page.keyboard.press("Escape")
    page.wait_for_timeout(500)

    clientes_base = page.evaluate("""() => {
        const rows = document.querySelectorAll('tbody tr');
        const result = [];
        
        rows.forEach(r => {
            const tds = r.querySelectorAll('td');
            if (tds.length >= 4) {
                const colUsuario = tds[0].innerText.trim();
                const colDatas = tds[1].innerText.trim();
                const colSituacao = tds[2].innerText.trim();
                const colDetalhes = tds[3].innerText.trim();

                if (colUsuario.toUpperCase().includes('MAXPLAYER')) return;
                if (!colUsuario.toUpperCase().includes('P2PLAYER') && !colUsuario.toUpperCase().includes('CASSIO')) return;

                const idMatch = colUsuario.match(/\\b\\d{6,10}\\b/);
                const id = idMatch ? idMatch[0] : '';
                if (!id) return;

                const dataMatch = colDatas.match(/\\d{2}\\/\\d{2}\\/\\d{4}(?:,\\s*\\d{2}:\\d{2}:\\d{2})?/);
                const vencimento = dataMatch ? dataMatch[0] : '';

                const aEdit = r.querySelector('a[href*="#/customers/edit/"]');
                const editHref = aEdit ? aEdit.getAttribute('href') : '';

                const linhasDetalhes = colDetalhes.split('\\n').map(s => s.trim()).filter(Boolean);
                let nome = '';
                let plano = '';
                let whatsapp = '';

                linhasDetalhes.forEach(l => {
                    const lLower = l.toLowerCase();
                    if (lLower.startsWith('plano:') || l.includes('R$')) {
                        plano = l.replace('Plano:', '').trim();
                    } else if (l.replace(/\\D/g, '').length >= 10 && !l.includes('R$')) {
                        whatsapp = l.replace(/\\D/g, '');
                    } else if (!nome && !l.includes('Plano') && !l.includes('Conex') && !l.includes('R$')) {
                        nome = l;
                    }
                });

                result.push({
                    id: id,
                    usuario: id,
                    nome: nome || `Cliente ${id}`,
                    vencimento: vencimento,
                    status: colSituacao.toLowerCase().includes('ativo') ? 'Ativo' : 'Vencido',
                    plano: plano || 'R$ 20,00',
                    whatsapp: whatsapp,
                    editHref: editHref,
                    senha: ''
                });
            }
        });
        return result;
    }""")

    print(f"[EXTRACAO] Encontrados {len(clientes_base)} clientes. Coletando senhas...")

    for i, c in enumerate(clientes_base, start=1):
        href = c.get("editHref")
        if href:
            url_edit = f"https://painel.p2player.top/{href.lstrip('/')}"
            try:
                page.goto(url_edit, wait_until="load", timeout=15000)
                page.wait_for_timeout(1500)

                senha_val = page.evaluate("""() => {
                    const inp = document.querySelector("input[placeholder*='Deixe em branco'], input[placeholder*='mesmo']");
                    if (inp && inp.value) return inp.value;
                    const inputs = Array.from(document.querySelectorAll("input[type='text']"));
                    for (let j = 0; j < inputs.length; j++) {
                        if (inputs[j].placeholder && inputs[j].placeholder.includes('Deixe em branco')) {
                            return inputs[j].value;
                        }
                    }
                    return '';
                }""")

                if senha_val:
                    c["senha"] = senha_val
                    print(f"  [{i}/{len(clientes_base)}] {c['nome']}: Senha obtida ({senha_val})")
                else:
                    print(f"  [{i}/{len(clientes_base)}] {c['nome']}: Senha não encontrada")
            except Exception as e:
                print(f"  [{i}/{len(clientes_base)}] Erro ao obter senha de {c['nome']}: {e}")

        c.pop("editHref", None)

    return clientes_base

def sincronizar_com_nuvem(clientes: list):
    """Envia a base de clientes extraída para a nuvem no Render."""
    config = carregar_config()
    url_nuvem = config.get("url_nuvem", "").strip()
    if not url_nuvem:
        return

    endpoint = f"{url_nuvem.rstrip('/')}/sync"
    try:
        print(f"[SYNC] Enviando dados para a nuvem: {endpoint}...")
        resp = requests.post(endpoint, json=clientes, timeout=15)
        if resp.status_code == 200:
            print(f"[SYNC SUCESSO] Nuvem atualizada com {len(clientes)} clientes!")
        else:
            print(f"[SYNC AVISO] Servidor retornou status {resp.status_code}")
    except Exception as e:
        print(f"[SYNC ERRO] Falha ao conectar na nuvem: {e}")

def executar_monitor(silencioso: bool = True, notificar_telegram: bool = True) -> list:
    """Executa o processo de consulta do painel com coleta completa de senhas e sync na nuvem."""
    config = carregar_config()
    url_painel = config.get("url_painel", "https://painel.p2player.top")
    credenciais = config.get("credenciais", {})
    usuario = credenciais.get("usuario", "Cassio")
    senha = credenciais.get("senha", "")
    
    os.makedirs(SESSAO_DIR, exist_ok=True)
    
    args_chrome = [
        "--disable-blink-features=AutomationControlled",
        "--no-sandbox"
    ]
    if silencioso:
        args_chrome.extend(["--window-position=-2500,-2500", "--window-size=1280,800"])
    else:
        args_chrome.append("--start-maximized")

    print(f"[STATUS] Abrindo Chrome ({'Invisivel' if silencioso else 'Visivel'})...")
    clientes_extraidos = []

    with sync_playwright() as p:
        browser = p.chromium.launch_persistent_context(
            user_data_dir=SESSAO_DIR,
            channel="chrome",
            headless=False,
            args=args_chrome,
            ignore_default_args=["--enable-automation"]
        )

        page = browser.pages[0] if browser.pages else browser.new_page()

        page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)

        url_clientes = f"{url_painel.rstrip('/')}/#/customers"
        page.goto(url_clientes, wait_until="load", timeout=45000)
        page.wait_for_timeout(3000)

        if "sign-in" in page.url or page.locator("input[type='password']").count() > 0:
            tentar_fazer_login(page, usuario, senha)

        if "/customers" not in page.url:
            page.goto(url_clientes, wait_until="load", timeout=30000)

        page.wait_for_timeout(3000)

        clientes_extraidos = extrair_clientes_completos(page)
        print(f"[SUCESSO] Total de clientes sincronizados localmente: {len(clientes_extraidos)}")

        with open(CLIENTES_JSON, "w", encoding="utf-8") as f:
            json.dump(clientes_extraidos, f, ensure_ascii=False, indent=2)

        browser.close()

    # Envia para o Render na nuvem
    if clientes_extraidos:
        sincronizar_com_nuvem(clientes_extraidos)

        # Se solicitado, envia mensagem de confirmação no Telegram
        if notificar_telegram and config.get("telegram", {}).get("ativo", False):
            dias_alerta = config.get("configuracoes", {}).get("dias_alerta_proximos", 5)
            relatorio = formatar_relatorio_proximos(clientes_extraidos, dias_alerta)
            msg_inicio = "☀️ <b>PC INICIADO: PAINEL SINCRONIZADO COM SUCESSO!</b>\n\n" + relatorio
            enviar_mensagem_telegram(msg_inicio)

    return clientes_extraidos

if __name__ == "__main__":
    executar_monitor(silencioso=True, notificar_telegram=True)
