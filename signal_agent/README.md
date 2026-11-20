# Agente de señales (11 skills de day trading → Telegram)

Señales de **COMPRA** y **VENTA** con **Stop Loss** y **Take Profit**, enviadas a tu celular por Telegram.
Construido sobre las 11 skills de [day-trader-skill](https://github.com/Jakeschincariol/day-trader-skill)
(MIT), copiadas en `.claude/skills/trader-*`.

## Piezas

| archivo | qué es |
| --- | --- |
| `.claude/agents/trader-signals.md` | el subagente de Claude Code especialista en las 11 skills |
| `.claude/skills/trader-*` | las 11 skills (scanner, news, entry, exit, timemachine, budget, risk, broker, alerts, analyst, pelosi) |
| `signal_agent/run_signals.py` | orquestador: corre el pipeline y manda las señales |
| `signal_agent/telegram_push.py` | envío a Telegram (solo librería estándar) |

## Puesta en marcha

1. En `.env` ya tienes `TELEGRAM_BOT_TOKEN` y `TELEGRAM_CHAT_ID`. Prueba:
   `python3 signal_agent/run_signals.py test`
2. El primer ciclo crea `trader/config.json` (presupuesto $5,000, pérdida máx. $50 por operación, paper).
   Edítalo con tus valores.
3. Durante la sesión de NYSE (9:30–16:00 hora de Nueva York):
   ```bash
   python3 signal_agent/run_signals.py loop --symbols TSLA,NVDA,AMD --every 60
   # o que el scanner busque candidatos:
   python3 signal_agent/run_signals.py loop --scan --max-symbols 25
   ```
   Desde Claude Code: pide *"usa el agente trader-signals y arranca las señales para TSLA y NVDA"*.

Sin dependencias extra: Python 3.8+.

## Qué llega al celular

```
🟢 SEÑAL DE COMPRA — TSLA
Setup: ruptura del rango de apertura (10:15 AM, velas 5m)
▶️ Entrada: $364.18
🛑 Stop Loss: $358.32  (opening-range midpoint)
🎯 Take Profit: $370.04  (1R)
Riesgo/acción: $5.86 · R:R 1.00
⏰ Cerrar a más tardar: 15:55 ET
📏 Tamaño: 8 acciones ($2913.44) · pérdida en SL $46.88
✅ Risk check: PASS
🔮 Time Machine (10000 replays): TP primero 29.4% · SL primero 25.5% · abierto al cierre 45.1%
```

Y luego, mientras la operación está abierta: `🔴 SEÑAL DE VENTA — TSLA: tocó el STOP LOSS`,
`💰 … tocó el TAKE PROFIT` o `⏰ … cerrar antes del cierre`.

## Límites (léelos)

- **Solo largos**: las skills v2 no generan entradas en corto. "Venta" = cerrar la compra (SL, TP o flat-by).
- **Acciones de EE. UU. con horario NYSE** (datos gratis de Yahoo, con retraso). Sirve para CFD sobre
  acciones de EE. UU.; no para forex, cripto u oro (para eso sigue el bot MA/RSI de `trading_app.py`).
- Las alertas se revisan cada `--every` segundos con cotizaciones retrasadas: el precio puede cruzar
  un nivel entre dos revisiones. Pon el SL/TP como orden bracket en el broker.
- **Nunca coloca órdenes.** No es asesoría financiera; la mayoría de quienes hacen day trading pierden dinero.
