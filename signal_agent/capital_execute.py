#!/usr/bin/env python3
"""Ejecuta UNA orden autorizada en Capital.com (cuenta live), con candados de seguridad.

  python3 signal_agent/capital_execute.py check                 # login + cuenta + mercado, sin operar
  python3 signal_agent/capital_execute.py buy --confirm         # envía la orden (una sola vez)

Parámetros autorizados por el usuario (2026-11-27): GOLD, BUY, tamaño 1, SL 3620, TP 3700,
cuenta "Analista ll", al dispararse el ORB de GC=F, a más tardar 12:30 NY.
"""

import argparse
import datetime
import json
import os
import sys

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from telegram_push import load_env  # noqa: E402

BASE = "https://api-capital.backend-capital.com"
LOCK = os.path.join(ROOT, "trader", "state", "capital_executed.json")

ORDER = {"account": "Analista ll", "epic": "GOLD", "direction": "BUY", "size": 1.0,
         "stop": 3620.0, "target": 3700.0, "date": "2026-11-27", "deadline_ny": "12:30"}


def norm(name):
    return " ".join(str(name or "").lower().replace("ll", "ii").split())


def session():
    load_env()
    h = {"X-CAP-API-KEY": os.environ.get("CAPITAL_API_KEY", ""), "Content-Type": "application/json"}
    r = requests.post(BASE + "/api/v1/session", headers=h, timeout=15,
                      json={"identifier": os.environ.get("CAPITAL_API_USER", ""),
                            "password": os.environ.get("CAPITAL_API_PASSWORD", "")})
    if r.status_code != 200:
        raise SystemExit("login falló: HTTP %d %s" % (r.status_code, r.text[:200]))
    h.update({"CST": r.headers["CST"], "X-SECURITY-TOKEN": r.headers["X-SECURITY-TOKEN"]})
    return h, r.json()


def pick_account(h, current_id):
    accs = requests.get(BASE + "/api/v1/accounts", headers=h, timeout=15).json().get("accounts", [])
    match = [a for a in accs if norm(a.get("accountName")) == norm(ORDER["account"])]
    if len(match) != 1:
        raise SystemExit("no encontré exactamente una cuenta llamada %r; cuentas: %s"
                         % (ORDER["account"], [a.get("accountName") for a in accs]))
    acc = match[0]
    if acc["accountId"] != current_id:
        r = requests.put(BASE + "/api/v1/session", headers=h, json={"accountId": acc["accountId"]}, timeout=15)
        if r.status_code != 200:
            raise SystemExit("no pude cambiar a la cuenta %r: HTTP %d %s" % (acc["accountName"], r.status_code, r.text[:200]))
    return acc


def market(h):
    r = requests.get(BASE + "/api/v1/markets/" + ORDER["epic"], headers=h, timeout=15)
    if r.status_code != 200:
        raise SystemExit("mercado %s: HTTP %d %s" % (ORDER["epic"], r.status_code, r.text[:200]))
    return r.json()


def ny_now():
    # EST (UTC-5) vale para el 27-nov-2026
    return datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=5)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["check", "buy"])
    ap.add_argument("--confirm", action="store_true")
    a = ap.parse_args()

    h, s = session()
    acc = pick_account(h, s.get("currentAccountId"))
    m = market(h)
    snap, rules = m.get("snapshot", {}), m.get("dealingRules", {})
    bid, offer = snap.get("bid"), snap.get("offer")
    print("cuenta:", acc.get("accountName"), acc.get("accountType"), acc.get("currency"),
          "disponible:", (acc.get("balance") or {}).get("available"))
    print("mercado:", m.get("instrument", {}).get("name"), snap.get("marketStatus"), "bid", bid, "offer", offer)
    if a.mode == "check":
        return

    if not a.confirm:
        raise SystemExit("falta --confirm")
    if os.path.exists(LOCK):
        raise SystemExit("ya se ejecutó una orden (candado %s): no se envía otra" % LOCK)
    now = ny_now()
    if now.date().isoformat() != ORDER["date"] or now.strftime("%H:%M") > ORDER["deadline_ny"]:
        raise SystemExit("fuera de la ventana autorizada (%s hasta %s NY)" % (ORDER["date"], ORDER["deadline_ny"]))
    if snap.get("marketStatus") != "TRADEABLE":
        raise SystemExit("mercado no operable: %s" % snap.get("marketStatus"))
    if not (offer and ORDER["stop"] < offer < ORDER["target"]):
        raise SystemExit("precio %s fuera de SL %s / TP %s: no se envía" % (offer, ORDER["stop"], ORDER["target"]))

    payload = {"epic": ORDER["epic"], "direction": ORDER["direction"], "size": ORDER["size"],
               "guaranteedStop": False, "stopLevel": ORDER["stop"], "profitLevel": ORDER["target"]}
    os.makedirs(os.path.dirname(LOCK), exist_ok=True)
    with open(LOCK, "w") as fh:  # candado ANTES de enviar: nunca dos órdenes
        json.dump({"sent_at": datetime.datetime.utcnow().isoformat() + "Z", "payload": payload,
                   "offer": offer}, fh, indent=2)
    r = requests.post(BASE + "/api/v1/positions", headers=h, json=payload, timeout=15)
    print("orden: HTTP", r.status_code, r.text[:300])
    ref = (r.json() if r.headers.get("content-type", "").startswith("application/json") else {}).get("dealReference")
    if ref:
        c = requests.get(BASE + "/api/v1/confirms/" + ref, headers=h, timeout=15)
        print("confirmación:", c.status_code, c.text[:600])
        with open(LOCK) as fh:
            doc = json.load(fh)
        doc.update({"http": r.status_code, "dealReference": ref, "confirm": c.json() if c.status_code == 200 else c.text})
        with open(LOCK, "w") as fh:
            json.dump(doc, fh, indent=2)


if __name__ == "__main__":
    main()
