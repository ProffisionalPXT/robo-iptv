import os
import sys
import json
from flask import Flask, jsonify, request

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CLIENTES_JSON = os.path.join(BASE_DIR, "clientes_extraidos.json")

# Inicia o bot do Telegram em segundo plano
from bot_telegram import iniciar_bot_em_background
iniciar_bot_em_background()

@app.route("/")
def index():
    return "🚀 Bot IPTV Monitor - Ativo e Online 24h!", 200

@app.route("/health")
def health():
    total_clientes = 0
    if os.path.exists(CLIENTES_JSON):
        try:
            with open(CLIENTES_JSON, "r", encoding="utf-8") as f:
                total_clientes = len(json.load(f))
        except Exception:
            pass
    return jsonify({
        "status": "online",
        "service": "iptv-monitor-bot",
        "clientes_salvos": total_clientes
    }), 200

@app.route("/sync", methods=["POST"])
def sync_clientes():
    """Recebe a base de clientes atualizada do computador local e salva na nuvem."""
    try:
        dados = request.get_json(force=True)
        if isinstance(dados, list):
            with open(CLIENTES_JSON, "w", encoding="utf-8") as f:
                json.dump(dados, f, ensure_ascii=False, indent=2)
            print(f"[SYNC] Recebida atualização da nuvem com {len(dados)} clientes.")
            return jsonify({
                "sucesso": True,
                "mensagem": f"Base sincronizada com sucesso ({len(dados)} clientes)."
            }), 200
        else:
            return jsonify({"sucesso": False, "erro": "Formato inválido"}), 400
    except Exception as e:
        return jsonify({"sucesso": False, "erro": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
