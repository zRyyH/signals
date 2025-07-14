from datetime import datetime
import bot_telegram
import logging
import json
import time
import pymongo
from pymongo import MongoClient
import statistics

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger(__name__)


class MongoDBTradingSignals:
    def __init__(self):
        self.config = self.load_config()
        self.connect_mongodb()
        self.BotTelegram = bot_telegram.TelegramBot(
            bot_token=self.config["telegram"]["bot_token"],
            chat_id=self.config["telegram"]["chat_id"],
        )
        self.running = False
        self.active_signals = {}
        self.performance_stats = {
            "total_signals": 0,
            "wins": 0,
            "losses": 0,
            "win_rate": 0.0,
            "pair_stats": {},
        }

    def connect_mongodb(self):
        try:
            self.mongo_client = MongoClient(
                f"mongodb://{self.config['mongodb']['username']}:{self.config['mongodb']['password']}@{self.config['mongodb']['ip']}:{self.config['mongodb']['port']}/"
            )
            self.db = self.mongo_client[self.config["mongodb"]["db"]]
            logger.info("✅ Conectado ao MongoDB")
        except Exception as e:
            logger.error(f"❌ Erro ao conectar ao MongoDB: {e}")
            raise

    def load_config(self):
        default_config = {
            "telegram": {"bot_token": "SEU_TOKEN_AQUI", "chat_id": "SEU_CHAT_ID_AQUI"},
            "pairs": ["EURUSD", "GBPUSD", "USDJPY", "AUDCAD", "USDCAD"],
            "gale_levels": ["G0", "G1", "G2"],
            "mongodb": {
                "db": "candles",
                "ip": "",
                "port": 27017,
                "username": "",
                "password": "",
            },
            "settings": {
                "rsi_period": 14,
                "rsi_oversold": 25,
                "rsi_overbought": 75,
                "ma_period": 21,
                "signal_cooldown": 180,
                "expiration_minutes": 1,
                "macd_fast": 12,
                "macd_slow": 26,
                "macd_signal": 9,
                "bb_period": 20,
                "bb_deviation": 2,
                "min_quality_score": 6,
                "volatility_filter": True,
                "trend_filter": True,
            },
            "advanced": {
                "adaptive_rsi": True,
                "multi_timeframe": True,
                "market_session_filter": True,
                "max_signals_per_hour": 3,
                "blackout_hours": [22, 23, 0, 1, 2, 3, 4, 5],
            },
        }

        try:
            with open("config.json", "r") as f:
                config = json.load(f)
            # Merge missing keys
            for section in default_config:
                if section not in config:
                    config[section] = default_config[section]
                elif isinstance(default_config[section], dict):
                    for key, value in default_config[section].items():
                        if key not in config[section]:
                            config[section][key] = value
            # Save updated config
            with open("config.json", "w") as f:
                json.dump(config, f, indent=2)
            return config
        except FileNotFoundError:
            with open("config.json", "w") as f:
                json.dump(default_config, f, indent=2)
            print("📋 Arquivo config.json criado. Configure suas credenciais!")
            return default_config

    def send_message(self, message, reply_to_message_id=None):
        try:
            return self.BotTelegram.enviar_mensagem(
                message, reply_to_message_id=reply_to_message_id
            )
        except Exception as e:
            logger.error(f"Erro ao enviar mensagem: {e}")
            return None

    def get_candles(self, pair, count=100):
        try:
            collection = self.db[pair]
            candles = list(collection.find().sort("timestamp", -1).limit(count))
            if not candles:
                return []

            formatted_candles = [
                {
                    "open": c["open"],
                    "high": c["high"],
                    "low": c["low"],
                    "close": c["close"],
                    "timestamp": c["timestamp"],
                }
                for c in candles
            ]

            return list(reversed(formatted_candles))
        except Exception as e:
            logger.error(f"❌ Erro ao obter candles para {pair}: {e}")
            return []

    def calculate_rsi(self, candles, period=14):
        if len(candles) < period + 1:
            return None
        closes = [float(c["close"]) for c in candles[-period - 1 :]]
        gains = [max(0, closes[i] - closes[i - 1]) for i in range(1, len(closes))]
        losses = [max(0, closes[i - 1] - closes[i]) for i in range(1, len(closes))]
        avg_gain = sum(gains[-period:]) / period
        avg_loss = sum(losses[-period:]) / period
        if avg_loss == 0:
            return 100
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    def calculate_adaptive_rsi(self, candles, pair):
        if not self.config["advanced"]["adaptive_rsi"]:
            return self.calculate_rsi(candles, self.config["settings"]["rsi_period"])

        if len(candles) < 20:
            return self.calculate_rsi(candles, 14)

        recent_closes = [float(c["close"]) for c in candles[-20:]]
        volatility = statistics.stdev(recent_closes) / statistics.mean(recent_closes)

        if volatility > 0.02:
            period = 9
        elif volatility < 0.005:
            period = 21
        else:
            period = 14

        return self.calculate_rsi(candles, period)

    def calculate_ema(self, candles, period):
        if len(candles) < period:
            return None
        closes = [float(c["close"]) for c in candles]
        multiplier = 2 / (period + 1)
        ema = sum(closes[:period]) / period
        for i in range(period, len(closes)):
            ema = (closes[i] * multiplier) + (ema * (1 - multiplier))
        return ema

    def calculate_macd(self, candles, fast=12, slow=26, signal=9):
        if len(candles) < slow + signal:
            return None, None, None

        closes = [float(c["close"]) for c in candles]

        def calc_ema_series(data, period):
            multiplier = 2 / (period + 1)
            ema_values = [sum(data[:period]) / period]
            for i in range(period, len(data)):
                ema_values.append(
                    (data[i] * multiplier) + (ema_values[-1] * (1 - multiplier))
                )
            return ema_values

        ema_fast = calc_ema_series(closes, fast)
        ema_slow = calc_ema_series(closes, slow)
        min_length = min(len(ema_fast), len(ema_slow))
        macd_line = [
            ema_fast[-min_length:][i] - ema_slow[-min_length:][i]
            for i in range(min_length)
        ]

        if len(macd_line) >= signal:
            signal_line = calc_ema_series(macd_line, signal)
            return macd_line[-1], signal_line[-1], macd_line[-1] - signal_line[-1]

        return None, None, None

    def calculate_bollinger_bands(self, candles, period=20, deviation=2):
        if len(candles) < period:
            return None, None, None
        closes = [float(c["close"]) for c in candles[-period:]]
        middle = sum(closes) / len(closes)
        variance = sum((x - middle) ** 2 for x in closes) / len(closes)
        std_dev = variance**0.5
        return middle + (std_dev * deviation), middle, middle - (std_dev * deviation)

    def calculate_atr(self, candles, period=14):
        if len(candles) < period + 1:
            return None
        true_ranges = []
        for i in range(1, len(candles)):
            high, low = float(candles[i]["high"]), float(candles[i]["low"])
            close_prev = float(candles[i - 1]["close"])
            tr = max(high - low, abs(high - close_prev), abs(low - close_prev))
            true_ranges.append(tr)
        return sum(true_ranges[-period:]) / period

    def get_market_session(self):
        hour = datetime.now().hour
        if 2 <= hour < 8:
            return "ASIAN"
        elif 8 <= hour < 16:
            return "LONDON"
        elif 16 <= hour < 22:
            return "NY"
        return "OFF_HOURS"

    def is_high_liquidity_time(self):
        session = self.get_market_session()
        return session in ["LONDON", "NY"] or 16 <= datetime.now().hour < 17

    def get_trend_direction(self, candles):
        if len(candles) < 50:
            return "SIDEWAYS"
        ema_fast = self.calculate_ema(candles, 21)
        ema_slow = self.calculate_ema(candles, 55)
        if ema_fast is None or ema_slow is None:
            return "SIDEWAYS"

        price = float(candles[-1]["close"])
        if price > ema_fast > ema_slow:
            return "STRONG_UP"
        elif price < ema_fast < ema_slow:
            return "STRONG_DOWN"
        elif price > ema_slow and ema_fast > ema_slow:
            return "WEAK_UP"
        elif price < ema_slow and ema_fast < ema_slow:
            return "WEAK_DOWN"
        return "SIDEWAYS"

    def verify_signal_quality(self, signal):
        try:
            rsi, direction = signal["rsi"], signal["direction"]
            macd_line, macd_signal, macd_histogram = (
                signal.get("macd_line", 0),
                signal.get("macd_signal", 0),
                signal.get("macd_histogram", 0),
            )
            bb_position, trend = signal.get("bb_position", "MIDDLE"), signal.get(
                "trend", "SIDEWAYS"
            )
            market_session, atr = signal.get("market_session", "OFF_HOURS"), signal.get(
                "atr", 0
            )

            quality_score = 0
            issues = []

            # RSI (0-4 points)
            if direction == "CALL":
                if rsi < 20:
                    quality_score += 4
                elif rsi < 25:
                    quality_score += 3
                elif rsi < 30:
                    quality_score += 2
                else:
                    issues.append("RSI insuficiente para CALL")
            else:  # PUT
                if rsi > 80:
                    quality_score += 4
                elif rsi > 75:
                    quality_score += 3
                elif rsi > 70:
                    quality_score += 2
                else:
                    issues.append("RSI insuficiente para PUT")

            # MACD (0-3 points)
            if direction == "CALL":
                if macd_line > macd_signal and macd_histogram > 0:
                    quality_score += 3
                elif macd_line > macd_signal:
                    quality_score += 2
                elif macd_histogram > 0:
                    quality_score += 1
                else:
                    issues.append("MACD não confirma CALL")
            else:
                if macd_line < macd_signal and macd_histogram < 0:
                    quality_score += 3
                elif macd_line < macd_signal:
                    quality_score += 2
                elif macd_histogram < 0:
                    quality_score += 1
                else:
                    issues.append("MACD não confirma PUT")

            # Bollinger Bands, Trend, Session, Volatility (0-2, 0-2, 0-1, 0-1 points)
            if (direction == "CALL" and bb_position == "LOWER") or (
                direction == "PUT" and bb_position == "UPPER"
            ):
                quality_score += 2
            elif bb_position == "MIDDLE":
                quality_score += 1

            if self.config["settings"]["trend_filter"]:
                if (direction == "CALL" and trend in ["WEAK_UP", "STRONG_UP"]) or (
                    direction == "PUT" and trend in ["WEAK_DOWN", "STRONG_DOWN"]
                ):
                    quality_score += 2
                elif trend == "SIDEWAYS":
                    quality_score += 1
                else:
                    issues.append(f"Contra tendência ({trend})")

            if market_session in ["LONDON", "NY"]:
                quality_score += 1
            elif market_session == "OFF_HOURS":
                issues.append("Baixa liquidez")

            if self.config["settings"]["volatility_filter"] and 0.0001 < atr < 0.005:
                quality_score += 1
            elif atr >= 0.005:
                issues.append("Volatilidade alta")
            elif atr <= 0.0001:
                issues.append("Volatilidade baixa")

            # Strength bonus
            strength = signal["strength"]
            if strength == "EXTREMA":
                quality_score += 2
            elif strength == "MUITO FORTE":
                quality_score += 1

            min_score = self.config["settings"]["min_quality_score"]
            signal_valid = quality_score >= min_score

            return {
                "valid": signal_valid,
                "score": quality_score,
                "max_score": 17,
                "issues": issues,
                "recommendation": "ENVIAR" if signal_valid else "REJEITAR",
            }
        except Exception as e:
            logger.error(f"❌ Erro na verificação: {e}")
            return {
                "valid": False,
                "score": 0,
                "issues": ["Erro na verificação"],
                "recommendation": "REJEITAR",
            }

    def analyze_pair(self, pair):
        candles = self.get_candles(pair, 100)
        if len(candles) < 60:
            return None

        # Check blackout hours
        if self.config["advanced"]["market_session_filter"]:
            if datetime.now().hour in self.config["advanced"]["blackout_hours"]:
                return None

        # Calculate indicators
        settings = self.config["settings"]
        rsi = self.calculate_adaptive_rsi(candles, pair)
        ema = self.calculate_ema(candles, settings["ma_period"])
        price = float(candles[-1]["close"])
        macd_line, macd_signal, macd_histogram = self.calculate_macd(
            candles,
            settings["macd_fast"],
            settings["macd_slow"],
            settings["macd_signal"],
        )
        bb_upper, bb_middle, bb_lower = self.calculate_bollinger_bands(
            candles, settings["bb_period"], settings["bb_deviation"]
        )
        atr = self.calculate_atr(candles)
        trend = self.get_trend_direction(candles)
        market_session = self.get_market_session()

        if any(x is None for x in [rsi, ema, macd_line, bb_upper]):
            return None

        # Bollinger position
        if price <= bb_lower:
            bb_position = "LOWER"
        elif price >= bb_upper:
            bb_position = "UPPER"
        else:
            bb_position = "MIDDLE"

        # Signal logic
        signal = None
        if (
            rsi < settings["rsi_oversold"]
            and price < ema
            and macd_line > macd_signal
            and bb_position in ["LOWER", "MIDDLE"]
        ):
            signal = "CALL"
        elif (
            rsi > settings["rsi_overbought"]
            and price > ema
            and macd_line < macd_signal
            and bb_position in ["UPPER", "MIDDLE"]
        ):
            signal = "PUT"

        if signal:
            # Determine strength
            rsi_extreme = rsi < 20 or rsi > 80
            rsi_strong = rsi < 25 or rsi > 75
            macd_strong = abs(macd_histogram) > 0.0001 if macd_histogram else False
            bb_extreme = bb_position in ["LOWER", "UPPER"]
            trend_aligned = (
                signal == "CALL" and trend in ["WEAK_UP", "STRONG_UP"]
            ) or (signal == "PUT" and trend in ["WEAK_DOWN", "STRONG_DOWN"])

            if rsi_extreme and macd_strong and bb_extreme and trend_aligned:
                strength = "EXTREMA"
            elif (rsi_extreme and macd_strong) or (rsi_strong and bb_extreme):
                strength = "MUITO FORTE"
            elif rsi_strong or macd_strong:
                strength = "FORTE"
            else:
                strength = "MÉDIO"

            signal_data = {
                "pair": pair,
                "direction": signal,
                "time": datetime.now().strftime("%H:%M:%S"),
                "rsi": round(rsi, 1),
                "price": round(price, 5),
                "ema": round(ema, 5),
                "strength": strength,
                "macd_line": round(macd_line, 6),
                "macd_signal": round(macd_signal, 6),
                "macd_histogram": round(macd_histogram, 6),
                "bb_position": bb_position,
                "bb_upper": round(bb_upper, 5),
                "bb_lower": round(bb_lower, 5),
                "trend": trend,
                "market_session": market_session,
                "atr": round(atr, 6) if atr else 0,
            }

            verification = self.verify_signal_quality(signal_data)
            signal_data["verification"] = verification
            return signal_data

        return None

    def check_signal_limits(self, pair):
        max_signals = self.config["advanced"]["max_signals_per_hour"]
        if not max_signals:
            return True

        current_time = time.time()
        hour_ago = current_time - 3600
        signals_last_hour = sum(
            1
            for signal_data in self.active_signals.values()
            if signal_data["pair"] == pair and signal_data["timestamp"] > hour_ago
        )
        return signals_last_hour < max_signals

    def update_performance_stats(self, pair, result):
        self.performance_stats["total_signals"] += 1
        if result:
            self.performance_stats["wins"] += 1
        else:
            self.performance_stats["losses"] += 1

        total = self.performance_stats["total_signals"]
        self.performance_stats["win_rate"] = (
            (self.performance_stats["wins"] / total) * 100 if total > 0 else 0
        )

        if pair not in self.performance_stats["pair_stats"]:
            self.performance_stats["pair_stats"][pair] = {
                "wins": 0,
                "total": 0,
                "win_rate": 0,
            }

        self.performance_stats["pair_stats"][pair]["total"] += 1
        if result:
            self.performance_stats["pair_stats"][pair]["wins"] += 1

        pair_total = self.performance_stats["pair_stats"][pair]["total"]
        pair_wins = self.performance_stats["pair_stats"][pair]["wins"]
        self.performance_stats["pair_stats"][pair]["win_rate"] = (
            pair_wins / pair_total
        ) * 100

    def check_signal_results(self):
        if not self.active_signals:
            return

        current_time = time.time()
        signals_to_remove = []

        for signal_id, signal_data in self.active_signals.items():
            time_elapsed = current_time - signal_data["timestamp"]
            expiration_seconds = (signal_data["expiration_minutes"] + 1) * 60

            if time_elapsed >= expiration_seconds:
                result = self.verify_signal_result(signal_data)
                if result:
                    self.send_signal_result(signal_data, result)
                    self.update_performance_stats(
                        signal_data["pair"], result["success"]
                    )
                signals_to_remove.append(signal_id)

        for signal_id in signals_to_remove:
            del self.active_signals[signal_id]

    def verify_signal_result(self, signal_data):
        try:
            pair = signal_data["pair"]
            entry_price = signal_data["entry_price"]
            direction = signal_data["direction"]

            current_candles = self.get_candles(pair, 5)
            if not current_candles:
                return None

            current_price = float(current_candles[-1]["close"])
            price_difference = current_price - entry_price
            success = (direction == "CALL" and price_difference > 0) or (
                direction == "PUT" and price_difference < 0
            )

            return {
                "success": success,
                "entry_price": entry_price,
                "current_price": current_price,
                "price_difference": price_difference,
                "percentage_change": (price_difference / entry_price) * 100,
            }
        except Exception as e:
            logger.error(f"❌ Erro ao verificar resultado: {e}")
            return None

    def send_signal_result(self, signal_data, result):
        try:
            original_message_id = signal_data.get("original_message_id")
            emoji = "🟢" if result["success"] else "🔴"
            status = "GAIN" if result["success"] else "LOSS"
            message = f"{emoji} {status} - ${result['current_price']:.5f}"
            self.send_message(message, reply_to_message_id=original_message_id)
        except Exception as e:
            logger.error(f"❌ Erro ao enviar resultado: {e}")

    def send_daily_report(self):
        try:
            stats = self.performance_stats
            if stats["total_signals"] == 0:
                return

            report = f"""📊 **RELATÓRIO DIÁRIO**
━━━━━━━━━━━━━━━━━━
🎯 **Sinais**: {stats['total_signals']} | ✅ **Ganhos**: {stats['wins']} | ❌ **Perdas**: {stats['losses']}
📈 **Taxa de Acerto**: {stats['win_rate']:.1f}%

📌 **Por Par**:
"""
            for pair, pair_stats in stats["pair_stats"].items():
                report += f"• {pair}: {pair_stats['win_rate']:.1f}% ({pair_stats['wins']}/{pair_stats['total']})\n"

            self.send_message(report)
        except Exception as e:
            logger.error(f"❌ Erro ao enviar relatório: {e}")

    def print_signal(self, signal):
        if not signal["verification"]["valid"]:
            logger.info(
                f"⚠️ Sinal rejeitado: Score {signal['verification']['score']}/{signal['verification']['max_score']}"
            )
            return

        emoji = "🟢" if signal["direction"] == "CALL" else "🔴"
        expiration = self.config["settings"]["expiration_minutes"]
        strength_emojis = {
            "EXTREMA": "🔥💎",
            "MUITO FORTE": "🔥💪",
            "FORTE": "💪",
            "MÉDIO": "⚡",
        }
        strength_emoji = strength_emojis.get(signal["strength"], "⚡")

        lines = [
            f"{emoji} {signal['pair']} - {signal['direction']}",
            f"⏰ {signal['time']} | ⏳ {expiration}min",
            f"{strength_emoji} {signal['strength']} | Score: {signal['verification']['score']}/17",
            f"📊 RSI: {signal['rsi']} | Trend: {signal['trend']}",
            f"📈 MACD: {signal['macd_line']:.6f} | BB: {signal['bb_position']}",
            f"🌍 {signal['market_session']} | 💰 ${signal['price']}",
            "",
            "🎲 GALES:",
        ]

        for i, gale in enumerate(self.config["gale_levels"]):
            valor = round(1.0 * (2.2**i), 2)
            lines.append(f"   {gale}: ${valor}")

        message = "\n".join(lines + [""])
        message_id = self.send_message(message)

        signal_id = f"{signal['pair']}_{signal['time'].replace(':', '')}"
        self.active_signals[signal_id] = {
            "pair": signal["pair"],
            "direction": signal["direction"],
            "entry_price": signal["price"],
            "entry_time": signal["time"],
            "expiration_minutes": expiration,
            "timestamp": time.time(),
            "original_message_id": message_id,
            "signal_quality": signal["verification"]["score"],
        }

    def run(self):
        logger.info("🚀 Sistema MongoDB Trading Signals AVANÇADO Iniciado")
        logger.info(f"📊 Pares: {', '.join(self.config['pairs'])}")
        logger.info(f"🎯 Score Mínimo: {self.config['settings']['min_quality_score']}")
        logger.info("🔧 Filtros: RSI Adaptativo, MACD, Bollinger Bands, Tendência")

        signal_history = {}
        self.running = True
        last_report_day = datetime.now().day

        while self.running:
            try:
                current_time = datetime.now()
                logger.info(f"\n🔍 Análise - {current_time.strftime('%H:%M:%S')}")

                self.check_signal_results()

                # Daily report
                if current_time.day != last_report_day and current_time.hour == 0:
                    self.send_daily_report()
                    last_report_day = current_time.day
                    self.performance_stats = {
                        "total_signals": 0,
                        "wins": 0,
                        "losses": 0,
                        "win_rate": 0.0,
                        "pair_stats": {},
                    }

                # Check trading hours
                if (
                    not self.is_high_liquidity_time()
                    and self.config["advanced"]["market_session_filter"]
                ):
                    logger.info("   ⏸️ Horário de baixa liquidez")
                    time.sleep(300)
                    continue

                for pair in self.config["pairs"]:
                    if not self.check_signal_limits(pair):
                        continue

                    signal = self.analyze_pair(pair)
                    if signal:
                        last_time = signal_history.get(pair, 0)
                        cooldown = self.config["settings"]["signal_cooldown"]

                        if time.time() - last_time >= cooldown:
                            self.print_signal(signal)
                            signal_history[pair] = time.time()
                        else:
                            remaining = int(cooldown - (time.time() - last_time))
                            logger.info(f"   ⏱️ {pair}: Aguarde {remaining}s")

                if self.performance_stats["total_signals"] > 0:
                    logger.info(
                        f"📊 Stats: {self.performance_stats['wins']}/{self.performance_stats['total_signals']} ({self.performance_stats['win_rate']:.1f}%)"
                    )

                for i in range(45, 0, -1):
                    if i % 15 == 0:
                        logger.info(f"   ⏳ Próxima análise: {i}s")
                    time.sleep(1)

            except KeyboardInterrupt:
                logger.info("\n🛑 Sistema parado")
                self.running = False
            except Exception as e:
                logger.error(f"\n❌ Erro: {e}")
                time.sleep(10)


def main():
    try:
        system = MongoDBTradingSignals()
        system.run()
    except Exception as e:
        logger.error(f"❌ Erro crítico: {e}")


if __name__ == "__main__":
    main()
