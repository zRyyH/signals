import logging
from collections import defaultdict, deque
from datetime import datetime, timezone
from init_mongo import init_mongo_db
import websocket
import threading
import json
import time

# Setup de logging
logging.basicConfig(
    format="[%(asctime)s] %(levelname)s: %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

db = init_mongo_db()

URL = "wss://s-usc1a-nss-2015.firebaseio.com/.ws?v=5&ns=tradingfeed-b7907-default-rtdb"
raw_ticks = defaultdict(list)


def process_candles():
    while True:
        now = datetime.now(timezone.utc)
        current_minute = now.replace(second=0, microsecond=0)
        time.sleep(60 - now.second)

        for symbol, ticks in raw_ticks.items():
            if not ticks:
                continue
            prices = [float(t["price"]) for t in ticks]
            candle = {
                "timestamp": current_minute.isoformat(),
                "open": prices[0],
                "high": max(prices),
                "low": min(prices),
                "close": prices[-1],
            }
            db[symbol].insert_one(candle)
            logger.info(f"Candle salvo: {symbol} @ {current_minute.isoformat()}")
        raw_ticks.clear()


def on_message(ws, raw):
    msg = json.loads(raw)
    if msg.get("t") == "c" and msg["d"]["t"] == "h":
        client_id = msg["d"]["d"]["s"]
        subscribe = {"t": "d", "d": {"r": 1, "a": "q", "b": {"p": "/", "h": client_id}}}
        ws.send(json.dumps(subscribe))
        logger.info("🔗 Assinatura iniciada com o client_id: %s", client_id)

    elif msg.get("t") == "d":
        if msg["d"]["b"]["p"] == "ticks":
            tick_data = msg["d"]["b"]["d"]
            now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
            for symbol, price in tick_data.items():
                raw_ticks[symbol].append({"minute": now.isoformat(), "price": price})


def on_error(ws, err):
    logger.error(f"❌ Erro no WebSocket: {err}")


def on_close(ws, code, reason):
    logger.warning(f"🔒 Conexão fechada: Código={code}, Motivo={reason}")


def keep_alive(ws):
    while True:
        time.sleep(45)
        ws.send("0")


if __name__ == "__main__":
    threading.Thread(target=process_candles, daemon=True).start()
    ws = websocket.WebSocketApp(
        URL, on_message=on_message, on_error=on_error, on_close=on_close
    )
    threading.Thread(target=keep_alive, args=(ws,), daemon=True).start()
    logger.info("🚀 WebSocket iniciado")
    ws.run_forever()
