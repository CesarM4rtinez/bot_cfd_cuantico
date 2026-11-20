#!/usr/bin/env python3
"""Señales de COMPRA / VENTA con Stop Loss y Take Profit, al celular por Telegram.

Encadena las skills del pack day-trader-skill (.claude/skills/trader-*):

  scanner -> entry -> exit -> timemachine -> budget -> risk   => 🟢 señal de COMPRA (entrada, SL, TP)
  alerts (stop / target / flat-by)                            => 🔴 señal de VENTA (salida)

Nunca coloca órdenes: solo notifica. Tú decides si operas.

Uso:
  python3 signal_agent/run_signals.py once  --symbols TSLA,NVDA,AMD
  python3 signal_agent/run_signals.py loop  --symbols TSLA,NVDA --every 60
  python3 signal_agent/run_signals.py loop  --scan                 # usa /trader-scanner (orb) para buscar
  python3 signal_agent/run_signals.py test                         # mensaje de prueba al celular
Flags útiles: --stop or-mid|or-low|pct:X|atr:K  --target 2R|1R|1.5R  --no-timemachine  --dry-run
              --now "2026-10-19 10:15" (hora NY, para reproducir un día)
"""

import argparse
import datetime
import html
import json
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SKILLS = os.path.join(ROOT, ".claude", "skills")
TRADER = os.path.join(ROOT, "trader")
STATE = os.path.join(TRADER, "state", "signals.json")

sys.path.insert(0, HERE)
from telegram_push import TelegramPush, load_env  # noqa: E402

TOOLS = {
    "scan": "trader-scanner/scan.py",
    "entry": "trader-entry/entry.py",
    "exit": "trader-exit/exit.py",
    "tm": "trader-timemachine/timemachine.py",
    "size": "trader-budget/size.py",
    "risk": "trader-risk/check.py",
    "alerts": "trader-alerts/alerts.py",
    "news": "trader-news/news.py",
}


# ------------------------------------------------------------------ utilidades

def log(msg):
    print("%s  %s" % (datetime.datetime.now().strftime("%H:%M:%S"), msg), flush=True)


def tool(name, *args, now=None, timeout=600):
    """Ejecuta una herramienta de la skill desde la raíz del proyecto. Devuelve (code, json|None, stderr)."""
    cmd = [sys.executable, os.path.join(SKILLS, TOOLS[name])] + [str(a) for a in args]
    if now:
        cmd += ["--now", now]
    try:
        p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return 124, None, "timeout"
    data = None
    out = p.stdout.strip()
    if out:
        try:
            data = json.loads(out)
        except ValueError:
            data = None
    return p.returncode, data, (p.stderr.strip() or (out if data is None else ""))


def read_json(path, default):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return default


def write_json(path, doc):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2)
        fh.write("\n")


def money(x):
    return "$%.2f" % float(x) if x is not None else "-"


def pct(x):
    return "%.1f%%" % (100.0 * float(x)) if x is not None else "-"


def ensure_config():
    """trader/config.json es el reglamento de budget/risk. Si falta, se crea desde el ejemplo."""
    cfg = os.path.join(TRADER, "config.json")
    if not os.path.exists(cfg):
        os.makedirs(TRADER, exist_ok=True)
        shutil.copy(os.path.join(SKILLS, "trader-budget", "config.example.json"), cfg)
        log("Creado trader/config.json desde el ejemplo (budget $5,000, pérdida máx $50/trade, paper). "
            "Edítalo con tus valores.")
    return read_json(cfg, {})


# ------------------------------------------------------------------ mensajes

def buy_message(plan, tm, sizing, risk, news_items):
    sym = plan["symbol"]
    lines = [
        "🟢 <b>SEÑAL DE COMPRA — %s</b>" % html.escape(sym),
        "Setup: %s (%s, velas %s)" % (
            "ruptura del rango de apertura" if plan.get("setup") == "orb" else "cierre sobre nivel",
            html.escape(str(plan.get("entry_time") or "")), plan.get("interval", "5m")),
        "",
        "▶️ Entrada: <b>%s</b>" % money(plan["entry"]),
        "🛑 Stop Loss: <b>%s</b>  (%s)" % (money(plan["stop"]), html.escape(plan.get("stop_label") or plan.get("stop_rule", ""))),
        "🎯 Take Profit: <b>%s</b>  (%s)" % (money(plan["target"]), html.escape(plan.get("target_label") or "")),
        "Riesgo/acción: %s · R:R %.2f" % (money(plan["risk_per_share"]), float(plan["reward_risk"])),
        "⏰ Cerrar a más tardar: %s ET (sin overnight)" % html.escape(str(plan.get("flat_by") or "15:55")),
    ]
    if sizing:
        if sizing.get("refusal"):
            lines.append("📏 Tamaño: sin orden — %s" % html.escape(sizing["refusal"]))
        else:
            lines.append("📏 Tamaño: %d acciones (%s) · pérdida en SL %s" % (
                int(sizing.get("qty") or 0), money(sizing.get("cost")), money(sizing.get("max_loss"))))
    if risk:
        r = (risk.get("results") or [{}])[0]
        if r.get("verdict") == "PASS":
            lines.append("✅ Risk check: PASS")
        elif r.get("verdict") == "BLOCK":
            lines.append("⛔ Risk check: BLOCK — %s" % html.escape("; ".join(r.get("reasons") or [])))
    if tm and tm.get("mc"):
        mc, hist = tm["mc"], tm.get("history") or {}
        lines.append("🔮 Time Machine (%d replays): TP primero %s · SL primero %s · abierto al cierre %s" % (
            mc.get("replays", 0), pct(mc.get("p_target")), pct(mc.get("p_stop")), pct(mc.get("p_neither"))))
        if hist.get("triggered"):
            lines.append("   Histórico %d sesiones: disparó %d → TP %d, SL %d, ninguno %d" % (
                hist.get("sessions", 0), hist["triggered"], hist.get("target", 0), hist.get("stop", 0),
                hist.get("close", 0)))
        if tm.get("verdict"):
            lines.append("   " + html.escape(tm["verdict"]))
    if news_items:
        lines.append("📰 Noticias recientes:")
        for it in news_items[:3]:
            lines.append("   • " + html.escape(str(it)[:140]))
    lines += ["", "<i>Datos Yahoo gratuitos (pueden tener retraso). No se colocó ninguna orden. "
                  "No es asesoría financiera.</i>"]
    return "\n".join(lines)


def ring_message(ring):
    rid = ring.get("id", "")
    sym = html.escape(ring.get("symbol") or "")
    msg = html.escape(ring.get("message", ""))
    if rid.endswith("-plan-stop"):
        head = "🔴 <b>SEÑAL DE VENTA — %s: tocó el STOP LOSS</b>" % sym
    elif rid.endswith("-plan-target"):
        head = "💰 <b>SEÑAL DE VENTA — %s: tocó el TAKE PROFIT</b>" % sym
    elif rid.endswith("-flat-by"):
        head = "⏰ <b>SEÑAL DE VENTA — %s: cerrar antes del cierre</b>" % sym
    else:
        head = "🔔 <b>Alerta %s</b>" % sym
    return "%s\n%s\n<i>Si usas orden bracket, el SL/TP ya está en el broker; si no, cierra manualmente.</i>" % (head, msg)


# ------------------------------------------------------------------ pipeline

def recent_news(sym, now):
    code, data, _ = tool("news", "--tickers", sym, "--hours", "12", "--no-sec", "--json", timeout=60)
    items = []
    if isinstance(data, dict):
        for key in ("items", "news", "headlines"):
            if isinstance(data.get(key), list):
                items = data[key]
                break
    elif isinstance(data, list):
        items = data
    out = []
    for it in items:
        if isinstance(it, dict):
            out.append(it.get("title") or it.get("headline") or "")
    return [x for x in out if x]


def process_symbol(sym, a, day_dir, push):
    """Devuelve True si se envió una señal de compra."""
    entry_path = os.path.join(day_dir, "%s-entry.json" % sym)
    entry_args = ["check", sym, "--json", "--write", entry_path, "--setup", a.setup, "--interval", a.interval]
    if a.min_volume_x:
        entry_args += ["--min-volume-x", a.min_volume_x]
    if a.offline:
        entry_args += ["--offline", a.offline]
    code, res, err = tool("entry", *entry_args, now=a.now)
    if not isinstance(res, dict):
        log("%-6s entry: %s" % (sym, err or "sin datos"))
        return False
    status = res.get("status")
    if status != "triggered":
        last = (res.get("last") or {})
        log("%-6s %s %s" % (sym, status, ("%+.2f%% vs nivel" % last["vs_level_pct"])
                            if last.get("vs_level_pct") is not None else (res.get("reason") or "")))
        return False

    # Exit Planner: SL y TP antes de entrar
    plan_path = os.path.join(day_dir, "%s-plan.json" % sym)
    exit_args = ["plan", "--from", entry_path, "--stop", a.stop, "--target", a.target, "--write", plan_path, "--json"]
    if a.offline and a.stop.startswith("atr"):
        exit_args += ["--offline", a.offline]
    code, plan, err = tool("exit", *exit_args, now=a.now)
    if not isinstance(plan, dict) or "stop" not in plan:
        log("%-6s disparó, pero el plan fue rechazado: %s" % (sym, err))
        push.send("⚠️ <b>%s</b> disparó entrada, pero el Exit Planner rechazó el plan:\n%s"
                  % (html.escape(sym), html.escape(err or "")))
        return True

    tm = None
    if not a.no_timemachine:
        tm_args = ["run", "--plan", plan_path, "--json", "--replays", a.replays]
        if a.tm_offline:
            tm_args += ["--offline", a.tm_offline]
        _, tm, err = tool("tm", *tm_args, now=a.now)
        if not isinstance(tm, dict):
            log("%-6s time machine: %s" % (sym, err))
            tm = None

    orders_path = os.path.join(day_dir, "%s-orders.json" % sym)
    _, sz, err = tool("size", "--plan", plan_path, "--write", orders_path, "--json", now=a.now)
    sizing = sz.get("sizing") if isinstance(sz, dict) else None
    risk = None
    if isinstance(sz, dict) and sz.get("orders"):
        _, risk, _ = tool("risk", "--orders", orders_path, "--no-write", "--json", now=a.now)

    news_items = [] if (a.offline or a.no_news) else recent_news(sym, a.now)

    push.send(buy_message(plan, tm, sizing, risk if isinstance(risk, dict) else None, news_items))
    log("%-6s 🟢 COMPRA enviada: entrada %s SL %s TP %s" % (sym, plan["entry"], plan["stop"], plan["target"]))

    # Price Alerts: stop, target y flat-by para la señal de VENTA
    _, _, err = tool("alerts", "add", "--from-plan", "--plan", plan_path, now=None)
    return True


def check_exits(a, push):
    rules = read_json(os.path.join(TRADER, "alerts.json"), {})
    if not rules.get("rules"):
        return
    args = ["check", "--json"]
    if a.quotes_offline:
        args += ["--offline", a.quotes_offline]
    _, data, err = tool("alerts", *args, now=a.now, timeout=120)
    if not isinstance(data, dict):
        log("alerts: %s" % err)
        return
    for ring in data.get("rings") or []:
        push.send(ring_message(ring))
        log("🔴 %s" % ring.get("message"))


def candidates(a):
    if a.symbols:
        return [s.strip().upper() for s in a.symbols.split(",") if s.strip()]
    if a.scan:
        scan_args = ["orb", "--json", "--quiet"]
        if a.watchlist:
            scan_args += ["--watchlist", a.watchlist]
        if a.offline_scan:
            scan_args += ["--offline", a.offline_scan]
        tool("scan", *scan_args, now=a.now, timeout=900)
        wl = read_json(os.path.join(TRADER, "watchlist.json"), {})
        return [str(h["symbol"]).upper() for h in (wl.get("hits") or []) if h.get("symbol")][: a.max_symbols]
    env = os.environ.get("SIGNAL_SYMBOLS", "")
    return [s.strip().upper() for s in env.split(",") if s.strip()]


def market_open(a):
    _, st, _ = tool("alerts", "clock", "--json", now=a.now)
    return st if isinstance(st, dict) else {"open": True, "date": None}


def cycle(a, push):
    st = market_open(a)
    if not st.get("open") and not a.ignore_clock:
        log("NYSE cerrado (%s). Próxima apertura: %s" % (st.get("reason"), st.get("next_open")))
        return st
    today = st.get("date") or datetime.date.today().isoformat()
    day_dir = os.path.join(TRADER, "signals", today)
    state = read_json(STATE, {})
    sent = state.setdefault(today, [])
    syms = candidates(a)
    if not syms:
        log("Sin símbolos: usa --symbols TSLA,NVDA, --scan, o SIGNAL_SYMBOLS en .env")
    for sym in syms:
        if sym in sent:
            continue
        try:
            if process_symbol(sym, a, day_dir, push):
                sent.append(sym)
                write_json(STATE, state)
        except Exception as e:  # una acción no debe tumbar el loop
            log("%-6s error: %s" % (sym, e))
        if not a.offline:
            time.sleep(0.5)
    check_exits(a, push)
    return st


def main(argv=None):
    load_env()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", choices=["once", "loop", "test"])
    ap.add_argument("--symbols", help="tickers separados por coma (si no, --scan o SIGNAL_SYMBOLS)")
    ap.add_argument("--scan", action="store_true", help="buscar candidatos con /trader-scanner orb")
    ap.add_argument("--watchlist", help="limitar el scan a esta lista (archivo)")
    ap.add_argument("--max-symbols", type=int, default=25)
    ap.add_argument("--setup", default="orb", choices=["orb", "level"])
    ap.add_argument("--interval", default="5m", choices=["5m", "1m"])
    ap.add_argument("--min-volume-x", type=float)
    ap.add_argument("--stop", default="or-mid", help="or-mid (default), or-low, pct:X, atr:K, price:X")
    ap.add_argument("--target", default="2R", help="2R (default), 1R, 1.5R, price:X")
    ap.add_argument("--replays", type=int, default=10000)
    ap.add_argument("--no-timemachine", action="store_true")
    ap.add_argument("--no-news", action="store_true")
    ap.add_argument("--every", type=int, default=60, help="segundos entre ciclos en modo loop")
    ap.add_argument("--dry-run", action="store_true", help="imprimir en vez de mandar a Telegram")
    ap.add_argument("--ignore-clock", action="store_true")
    ap.add_argument("--now", help='hora de NY fija, p.ej. "2026-10-19 10:15" (reproducir un día)')
    ap.add_argument("--offline", help="(pruebas) gráfico Yahoo guardado para entry")
    ap.add_argument("--tm-offline", help="(pruebas) 60 días de velas guardadas para la time machine")
    ap.add_argument("--quotes-offline", help="(pruebas) carpeta de cotizaciones para alerts")
    ap.add_argument("--offline-scan", help="(pruebas) fixture para el scanner")
    a = ap.parse_args(argv)

    push = TelegramPush(dry_run=a.dry_run)
    if a.mode == "test":
        ok = push.send("✅ <b>Bot de señales conectado</b>\nRecibirás aquí las señales de COMPRA/VENTA con SL y TP.")
        return 0 if ok else 1

    ensure_config()
    if a.mode == "once":
        cycle(a, push)
        return 0
    log("Loop de señales cada %ds. Ctrl+C para salir." % a.every)
    while True:
        st = cycle(a, push)
        wait = a.every if (st.get("open") or a.ignore_clock) else max(a.every, 300)
        try:
            time.sleep(wait)
        except KeyboardInterrupt:
            return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(0)
