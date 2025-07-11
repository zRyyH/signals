from datetime import datetime
import bot_telegram
import logging
import json
import time
from pymongo import MongoClient


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger(__name__)


class MongoDBTradingSignals:
    def __init__(self):
        """Inicializa o sistema MongoDB Trading Signals"""
        self.config = self.load_config()

        # Conecta ao MongoDB
        self.connect_mongodb()

        self.BotTelegram = bot_telegram.TelegramBot(
            bot_token=self.config["telegram"]["bot_token"],
            chat_id=self.config["telegram"]["chat_id"],
        )

        self.running = False

    def connect_mongodb(self):
        """Conecta ao MongoDB"""
        try:
            # Conecta ao MongoDB
            self.mongo_client = MongoClient(
                "mongodb://signals:signals1234@207.180.193.45:27017/"
            )
            self.db = self.mongo_client["candles"]
            logger.info("✅ Conectado ao MongoDB")
        except Exception as e:
            logger.error(f"❌ Erro ao conectar ao MongoDB: {e}")
            raise

    def load_config(self):
        """Carrega configurações do arquivo config.json"""
        try:
            with open("config.json", "r") as f:
                return json.load(f)
        except FileNotFoundError:
            config = {
                "telegram": {
                    "bot_token": "SEU_TOKEN_AQUI",
                    "chat_id": "SEU_CHAT_ID_AQUI",
                },
                "pairs": ["EURUSD", "GBPUSD", "USDJPY", "AUDCAD", "USDCAD"],
                "gale_levels": ["G0", "G1", "G2"],
                "settings": {
                    "rsi_period": 14,
                    "rsi_oversold": 30,
                    "rsi_overbought": 70,
                    "ma_period": 20,
                    "signal_cooldown": 120,
                    "expiration_minutes": 1,
                },
            }

            with open("config.json", "w") as f:
                json.dump(config, f, indent=2)

            print("📋 Arquivo config.json criado. Configure suas credenciais!")
            return config

    def send_message(self, message):
        """Envia mensagem para o Telegram"""
        try:
            self.BotTelegram.enviar_mensagem(message)
            logger.info(f"Mensagem enviada: {message}")
        except Exception as e:
            logger.error(f"Erro ao enviar mensagem: {e}")

    def get_candles_from_mongodb(self, pair, count=50):
        """Obtém candles do MongoDB"""
        try:
            # Busca os candles mais recentes
            collection = self.db[pair]
            candles = list(collection.find().sort("timestamp", -1).limit(count))

            if not candles:
                logger.warning(f"⚠️ Nenhum candle encontrado para {pair}")
                return []

            # Converte para o formato esperado
            formatted_candles = []
            for candle in candles:
                formatted_candles.append(
                    {
                        "open": candle["open"],
                        "high": candle["high"],
                        "low": candle["low"],
                        "close": candle["close"],
                        "timestamp": candle["timestamp"],
                    }
                )

            # Inverte para ordem cronológica
            formatted_candles.reverse()

            logger.info(f"📊 Obtidos {len(formatted_candles)} candles para {pair}")
            return formatted_candles

        except Exception as e:
            logger.error(f"❌ Erro ao obter candles do MongoDB para {pair}: {e}")
            return []

    def get_candles(self, pair, count=50):
        """Obtém candles do MongoDB"""
        return self.get_candles_from_mongodb(pair, count)

    def calculate_rsi(self, candles, period=14):
        """Calcula RSI"""
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

    def calculate_ma(self, candles, period=20):
        """Calcula média móvel"""
        if len(candles) < period:
            return None

        closes = [float(c["close"]) for c in candles[-period:]]
        return sum(closes) / len(closes)

    def verify_signal_quality(self, signal):
        """Verifica a qualidade do sinal"""
        try:
            rsi = signal["rsi"]
            strength = signal["strength"]
            direction = signal["direction"]

            # Critérios de qualidade
            quality_score = 0
            issues = []

            # Verifica RSI
            if direction == "CALL":
                if rsi < 25:
                    quality_score += 3
                elif rsi < 30:
                    quality_score += 2
                else:
                    issues.append("RSI não está muito baixo para CALL")
            else:  # PUT
                if rsi > 75:
                    quality_score += 3
                elif rsi > 70:
                    quality_score += 2
                else:
                    issues.append("RSI não está muito alto para PUT")

            # Verifica força
            if strength == "FORTE":
                quality_score += 2
            elif strength == "MÉDIO":
                quality_score += 1

            # Determina se o sinal é válido
            signal_valid = quality_score >= 3

            verification_result = {
                "valid": signal_valid,
                "score": quality_score,
                "issues": issues,
                "recommendation": "ENVIAR" if signal_valid else "REJEITAR",
            }

            logger.info(f"🔍 Verificação do sinal: {verification_result}")
            return verification_result

        except Exception as e:
            logger.error(f"❌ Erro na verificação do sinal: {e}")
            return {
                "valid": False,
                "score": 0,
                "issues": ["Erro na verificação"],
                "recommendation": "REJEITAR",
            }

    def analyze_pair(self, pair):
        """Analisa um par"""
        candles = self.get_candles(pair, 50)
        if len(candles) < 30:
            return None

        settings = self.config["settings"]
        rsi = self.calculate_rsi(candles, settings["rsi_period"])
        ma = self.calculate_ma(candles, settings["ma_period"])
        price = float(candles[-1]["close"])

        if rsi is None or ma is None:
            return None

        # Lógica de sinal
        signal = None
        if rsi < settings["rsi_oversold"] and price < ma:
            signal = "CALL"
        elif rsi > settings["rsi_overbought"] and price > ma:
            signal = "PUT"

        if signal:
            strength = "FORTE" if (rsi < 25 or rsi > 75) else "MÉDIO"
            signal_data = {
                "pair": pair,
                "direction": signal,
                "time": datetime.now().strftime("%H:%M:%S"),
                "rsi": round(rsi, 1),
                "price": round(price, 5),
                "ma": round(ma, 5),
                "strength": strength,
            }

            # Verifica a qualidade do sinal
            verification = self.verify_signal_quality(signal_data)
            signal_data["verification"] = verification

            return signal_data

        return None

    def print_signal(self, signal):
        """Imprime sinal limpo em uma única mensagem"""
        # Só envia se o sinal foi aprovado na verificação
        if not signal["verification"]["valid"]:
            logger.info(
                f"⚠️ Sinal rejeitado: {signal['verification']['recommendation']}"
            )
            return

        emoji = "🟢" if signal["direction"] == "CALL" else "🔴"
        expiration = self.config["settings"]["expiration_minutes"]

        # Monta as linhas da mensagem
        lines = [
            "=" * 50,
            "🚨 SINAL VERIFICADO E APROVADO",
            "=" * 50,
            f"{emoji} {signal['pair']} - {signal['direction']}",
            f"⏰ {signal['time']} | ⏳ {expiration}min",
            f"💪 Força: {signal['strength']}",
            f"📊 RSI: {signal['rsi']} | Preço: {signal['price']} | MA: {signal['ma']}",
            f"✅ Score de Qualidade: {signal['verification']['score']}/5",
            "",
            "🎲 GALES:",
        ]

        # Adiciona níveis de gale
        for i, gale in enumerate(self.config["gale_levels"]):
            valor = round(1.0 * (2.2**i), 2)
            lines.append(f"   {gale}: ${valor}")

        lines.append("=" * 50)

        # Une tudo em uma única string
        message = "\n".join(lines)
        self.send_message(message)

    def run(self):
        """Executa o sistema"""
        logger.info("🚀 Sistema MongoDB Trading Signals Iniciado")
        logger.info(f"📊 Pares: {', '.join(self.config['pairs'])}")
        logger.info(f"🎲 Gales: {', '.join(self.config['gale_levels'])}")
        logger.info("📈 Fonte de dados: MongoDB")

        signal_history = {}
        self.running = True

        while self.running:
            self.config = self.load_config()

            try:
                logger.info(f"\n🔍 Análise - {datetime.now().strftime('%H:%M:%S')}")

                for pair in self.config["pairs"]:
                    logger.info(f"   Analisando {pair}...")

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

                    time.sleep(1)

                logger.info("   ✅ Análise concluída")

                # Aguarda próxima análise
                for i in range(30, 0, -1):
                    logger.info(f"   ⏳ Próxima análise: {i}s")
                    time.sleep(1)

            except KeyboardInterrupt:
                logger.info("\n🛑 Sistema parado")
                self.running = False
            except Exception as e:
                logger.error(f"\n❌ Erro: {e}")
                time.sleep(5)


def main():
    try:
        system = MongoDBTradingSignals()
        system.run()
    except Exception as e:
        logger.error(f"❌ Erro: {e}")


if __name__ == "__main__":
    main()
