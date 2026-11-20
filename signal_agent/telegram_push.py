"""Envío de notificaciones a Telegram (al celular) usando solo la librería estándar.

Usa las mismas variables que el bot: TELEGRAM_BOT_TOKEN y TELEGRAM_CHAT_ID,
leídas del entorno o del archivo .env en la raíz del proyecto.
"""

import json
import os
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_env(path=None):
    """Carga KEY=VALUE de .env sin pisar variables que ya existan en el entorno."""
    path = path or os.path.join(ROOT, ".env")
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            key, val = key.strip(), val.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = val


class TelegramPush:
    def __init__(self, token=None, chat_id=None, dry_run=False):
        load_env()
        self.token = token or os.environ.get("TELEGRAM_BOT_TOKEN", "")
        self.chat_id = chat_id or os.environ.get("TELEGRAM_CHAT_ID", "")
        self.dry_run = dry_run
        if not dry_run and (not self.token or not self.chat_id):
            raise RuntimeError("Faltan TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID en el entorno o en .env "
                               "(o usa --dry-run para solo imprimir).")

    def send(self, text):
        if self.dry_run:
            print("----- [dry-run] mensaje a Telegram -----")
            print(text)
            print("----------------------------------------")
            return True
        url = "https://api.telegram.org/bot%s/sendMessage" % self.token
        data = urllib.parse.urlencode({
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": "true",
        }).encode()
        try:
            with urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=20) as resp:
                ok = json.loads(resp.read().decode()).get("ok", False)
        except Exception as e:  # red caída, token inválido, etc.
            print("Telegram: no se pudo enviar (%s)" % e)
            return False
        if not ok:
            print("Telegram respondió ok=false")
        return ok
