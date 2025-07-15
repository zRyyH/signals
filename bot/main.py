import time
import json
import logging
from datetime import datetime
from pymongo import MongoClient
from bot_telegram import TelegramBot

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

GALES = [
    ("G0", 1.0),
    ("G1", 2.2),
    ("G2", 4.84)
]

class SignalBot:
    def __init__(self):
        self.config = self.load_config()
        mongo_conf = self.config["mongodb"]
        try:
            self.mongo_client = MongoClient(
                f"mongodb://{mongo_conf['username']}:{mongo_conf['password']}@"
                f"{mongo_conf['ip']}:{mongo_conf['port']}/",
                serverSelectionTimeoutMS=5000
            )
            self.mongo_client.server_info()
            logger.info("✅ Conectado ao MongoDB com sucesso!")
        except Exception as e:
            logger.error(f"❌ Erro ao conectar no MongoDB: {e}")
            raise SystemExit(1)

        self.db = self.mongo_client[mongo_conf["db"]]
        tele_conf = self.config["telegram"]
        self.bot = TelegramBot(
            bot_token=tele_conf["bot_token"],
            chat_id=tele_conf["chat_id"]
        )
        self.active_signals = []
        self.pairs = self.config["pairs"]
        self.rsi_period = self.config["settings"]["rsi_period"]
        self.ema_period = self.config["settings"]["ma_period"]
        self.signal_cooldown = self.config["settings"]["signal_cooldown"]
        self.expiration_minutes = self.config["settings"]["expiration_minutes"]
        self.analysis_interval = self.config["settings"]["analysis_interval"]
        self.one_signal_at_a_time = self.config.get("one_signal_at_a_time", False)

    def load_config(self):
        with open("config.json") as f:
            return json.load(f)

    def in_blackout(self):
        blackout = self.config.get("blackout", {})
        if not blackout.get("enabled"):
            return False
        now = datetime.now()
        start = blackout.get("start_hour", 23)
        end = blackout.get("end_hour", 5)
        current_hour = now.hour
        if start > end:
            return (current_hour >= start or current_hour < end)
        return (start <= current_hour < end)

    def get_candles(self, pair, n=60):
        candles = list(self.db[pair].find({}, {"_id": 0}).sort("timestamp", -1).limit(n))
        if candles:
            last_candle_time = candles[0].get("timestamp") if candles else None
            logger.info(f"[{pair}] Encontrou {len(candles)} candles. Último timestamp: {last_candle_time}")
        else:
            logger.warning(f"[{pair}] Nenhum candle encontrado no banco!")
        return list(reversed(candles))

    def rsi(self, closes, period):
        if len(closes) < period + 1:
            return None
        gains = [max(closes[i] - closes[i-1], 0) for i in range(1, len(closes))]
        losses = [max(closes[i-1] - closes[i], 0) for i in range(1, len(closes))]
        avg_gain = sum(gains[-period:]) / period
        avg_loss = sum(losses[-period:]) / period
        if avg_loss == 0:
            return 100
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    def ema(self, closes, period):
        if len(closes) < period:
            return None
        ema = sum(closes[:period]) / period
        k = 2 / (period + 1)
        for price in closes[period:]:
            ema = price * k + ema * (1 - k)
        return ema

    def macd(self, closes):
        if len(closes) < 35:
            return None, None
        ema_fast = self.ema(closes, 12)
        ema_slow = self.ema(closes, 26)
        if ema_fast is None or ema_slow is None:
            return None, None
        macd_line = ema_fast - ema_slow
        return macd_line, None

    def analyze_pair(self, pair):
        candles = self.get_candles(pair)
        if len(candles) < self.rsi_period + 1:
            logger.warning(f"[{pair}] Poucos candles para análise: {len(candles)}")
            return None
        closes = [float(c["close"]) for c in candles]
        price = closes[-1]
        rsi_val = self.rsi(closes, self.rsi_period)
        ema_val = self.ema(closes, self.ema_period)
        macd_val, _ = self.macd(closes)
        logger.info(
            f"[{pair}] price={price}, RSI={rsi_val}, EMA={ema_val}, MACD={macd_val}"
        )

        rsi_oversold = self.config["settings"].get("rsi_oversold", 25)
        rsi_overbought = self.config["settings"].get("rsi_overbought", 75)
        macd_positive = self.config["settings"].get("macd_positive", 0)
        macd_negative = self.config["settings"].get("macd_negative", 0)

        forca = "FORTE" if (rsi_val < 20 or rsi_val > 80) else "MÉDIO"

        if rsi_val is not None and ema_val is not None and macd_val is not None:
            if rsi_val < rsi_oversold and price < ema_val and macd_val > macd_positive:
                logger.info(f"[{pair}] Sinal de CALL gerado!")
                return {"pair": pair, "dir": "CALL", "price": price, "rsi": rsi_val, "forca": forca}
            elif rsi_val > rsi_overbought and price > ema_val and macd_val < macd_negative:
                logger.info(f"[{pair}] Sinal de PUT gerado!")
                return {"pair": pair, "dir": "PUT", "price": price, "rsi": rsi_val, "forca": forca}
            else:
                logger.info(f"[{pair}] Nenhum sinal enviado, critérios não atendidos.")
        else:
            logger.warning(f"[{pair}] Indicadores insuficientes para gerar sinal.")

        return None

    def signal_message(self, signal):
        emoji = "🟢" if signal["dir"] == "CALL" else "🔴"
        forca_emoji = "⚡"
        exp = self.expiration_minutes
        gale_text = "\n".join([f"   {g[0]}: ${g[1]}" for g in GALES])
        return (
            f"{emoji} {signal['pair']} - {signal['dir']}\n"
            f"⏰ {datetime.now().strftime('%H:%M:%S')} | ⏳ {exp}min\n"
            f"{forca_emoji} FORCA {signal['forca']}\n"
            f"📊 RSI: {signal['rsi']:.1f} | 💰 ${signal['price']:.5f}\n\n"
            "🎲 GALES:\n" + gale_text
        )

    def send_signal(self, signal):
        msg = self.signal_message(signal)
        logger.info(f"Enviando sinal: {msg.replace(chr(10),' ')}")
        message_id = self.bot.enviar_mensagem(msg)
        logger.info(f"[SINAL ENVIADO] Pair: {signal['pair']} | message_id: {message_id}")
        self.active_signals.append({
            "pair": signal["pair"],
            "price": signal["price"],
            "dir": signal["dir"],
            "timestamp": time.time(),
            "message_id": message_id
        })

    def check_results(self):
        expired = []
        for idx, sig in enumerate(self.active_signals):
            elapsed = time.time() - sig["timestamp"]
            logger.info(f"[CHECANDO EXPIRAÇÃO] Pair: {sig['pair']} | Elapsed: {elapsed:.2f}s | Limite: {self.expiration_minutes * 60}s")
            if elapsed > self.expiration_minutes * 60:
                closes = [float(c["close"]) for c in self.get_candles(sig["pair"], 2)]
                logger.info(f"[EXPIRADO] Pair: {sig['pair']} | closes: {closes}")
                if not closes:
                    logger.warning(f"[SEM CANDLES PARA RESULTADO] Pair: {sig['pair']}")
                    continue
                current = closes[-1]
                result = (
                    (sig["dir"] == "CALL" and current > sig["price"]) or
                    (sig["dir"] == "PUT" and current < sig["price"])
                )
                resp_msg = f"{'🟢 GAIN' if result else '🔴 LOSS'} - {sig['pair']} ({current:.5f})"
                logger.info(f"[REPLY] Respondendo sinal do pair {sig['pair']} | message_id: {sig['message_id']} | Mensagem: {resp_msg}")
                reply_result = self.bot.enviar_mensagem(resp_msg, reply_to_message_id=sig["message_id"])
                logger.info(f"[REPLY ENVIADO] reply_to_message_id: {sig['message_id']} | Resultado: {reply_result}")
                expired.append(idx)
        for idx in reversed(expired):
            del self.active_signals[idx]

    def run(self):
        last_signal_time = {p: 0 for p in self.pairs}
        logger.info(f"Iniciando análise dos pares: {', '.join(self.pairs)}")
        while True:
            if self.in_blackout():
                logger.info("[BLACKOUT] Bot pausado por horário configurado.")
                time.sleep(60)
                continue

            # --- MODO ONE-SIGNAL ---
            if self.one_signal_at_a_time and len(self.active_signals) > 0:
                logger.info("[MODO ÚNICO] Aguardando sinal atual expirar antes de enviar outro.")
                self.check_results()
                time.sleep(self.analysis_interval)
                continue

            for pair in self.pairs:
                if time.time() - last_signal_time[pair] < self.signal_cooldown:
                    continue
                signal = self.analyze_pair(pair)
                if signal:
                    self.send_signal(signal)
                    last_signal_time[pair] = time.time()
                    if self.one_signal_at_a_time:
                        break
            self.check_results()
            time.sleep(self.analysis_interval)

if __name__ == "__main__":
    SignalBot().run()
