import os
import sys
from flask import Flask, jsonify

app = Flask(__name__)

# Importa e inicia o bot do Telegram em segundo plano
from bot_telegram import iniciar_bot_em_background
iniciar_bot_em_background()

@app.route("/")
def index():
    return "🚀 Bot IPTV Monitor - Ativo e Online 24h!", 200

@app.route("/health")
def health():
    return jsonify({"status": "online", "service": "iptv-monitor-bot"}), 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
