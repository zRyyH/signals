import telebot
import logging
import re
from datetime import datetime

logger = logging.getLogger(__name__)


class TelegramBot:
    def __init__(self, bot_token, chat_id):
        self.bot_token = bot_token
        self.chat_id = chat_id

        if not self.bot_token or self.bot_token == "SEU_TOKEN_AQUI":
            raise ValueError("❌ Configure o bot_token no arquivo config.json")

        if not self.chat_id or self.chat_id == "SEU_CHAT_ID_AQUI":
            raise ValueError("❌ Configure o chat_id no arquivo config.json")

        self.bot = telebot.TeleBot(self.bot_token)

    def verificar_sinal(self, mensagem: str):
        """Verifica se a mensagem contém um sinal válido"""
        try:
            # Verifica se é uma mensagem de sinal
            if "SINAL VERIFICADO E APROVADO" not in mensagem:
                return {
                    "is_signal": False,
                    "valid": False,
                    "details": "Não é uma mensagem de sinal"
                }
            
            # Extrai informações do sinal
            signal_info = {}
            
            # Extrai o par e direção
            pair_match = re.search(r'[🟢🔴] ([A-Z]+-?[A-Z]*) - (CALL|PUT)', mensagem)
            if pair_match:
                signal_info["pair"] = pair_match.group(1)
                signal_info["direction"] = pair_match.group(2)
            
            # Extrai horário
            time_match = re.search(r'⏰ (\d{2}:\d{2}:\d{2})', mensagem)
            if time_match:
                signal_info["time"] = time_match.group(1)
            
            # Extrai RSI
            rsi_match = re.search(r'RSI: ([\d.]+)', mensagem)
            if rsi_match:
                signal_info["rsi"] = float(rsi_match.group(1))
            
            # Extrai força
            strength_match = re.search(r'Força: (FORTE|MÉDIO)', mensagem)
            if strength_match:
                signal_info["strength"] = strength_match.group(1)
            
            # Extrai score de qualidade
            score_match = re.search(r'Score de Qualidade: (\d+)/5', mensagem)
            if score_match:
                signal_info["quality_score"] = int(score_match.group(1))
            
            # Validações
            validation_issues = []
            
            # Verifica se tem todas as informações necessárias
            required_fields = ["pair", "direction", "time", "rsi", "strength"]
            for field in required_fields:
                if field not in signal_info:
                    validation_issues.append(f"Campo {field} não encontrado")
            
            # Verifica se o RSI está em níveis adequados
            if "rsi" in signal_info and "direction" in signal_info:
                rsi = signal_info["rsi"]
                direction = signal_info["direction"]
                
                if direction == "CALL" and rsi > 35:
                    validation_issues.append("RSI muito alto para CALL")
                elif direction == "PUT" and rsi < 65:
                    validation_issues.append("RSI muito baixo para PUT")
            
            # Verifica score de qualidade
            if "quality_score" in signal_info:
                if signal_info["quality_score"] < 3:
                    validation_issues.append("Score de qualidade muito baixo")
            
            # Verifica se o horário é recente (últimos 5 minutos)
            if "time" in signal_info:
                try:
                    signal_time = datetime.strptime(signal_info["time"], "%H:%M:%S")
                    current_time = datetime.now()
                    signal_datetime = signal_time.replace(
                        year=current_time.year,
                        month=current_time.month,
                        day=current_time.day
                    )
                    
                    time_diff = abs((current_time - signal_datetime).total_seconds())
                    if time_diff > 300:  # 5 minutos
                        validation_issues.append("Sinal muito antigo")
                except:
                    validation_issues.append("Formato de horário inválido")
            
            is_valid = len(validation_issues) == 0
            
            verification_result = {
                "is_signal": True,
                "valid": is_valid,
                "signal_info": signal_info,
                "issues": validation_issues,
                "recommendation": "ENVIAR" if is_valid else "REJEITAR"
            }
            
            logger.info(f"🔍 Verificação do sinal no Telegram: {verification_result}")
            return verification_result
            
        except Exception as e:
            logger.error(f"❌ Erro na verificação do sinal: {e}")
            return {
                "is_signal": False,
                "valid": False,
                "details": f"Erro na verificação: {str(e)}"
            }

    def enviar_mensagem(self, mensagem: str):
        """Envia mensagem para o Telegram com verificação"""
        try:
            # Verifica o sinal antes de enviar
            verification = self.verificar_sinal(mensagem)
            
            if verification["is_signal"]:
                if not verification["valid"]:
                    # Log do motivo da rejeição
                    logger.warning(f"⚠️ Sinal rejeitado pelo bot Telegram:")
                    for issue in verification["issues"]:
                        logger.warning(f"   - {issue}")
                    
                    # Envia mensagem de rejeição
                    rejection_message = f"❌ SINAL REJEITADO\n\nMotivos:\n"
                    for issue in verification["issues"]:
                        rejection_message += f"• {issue}\n"
                    
                    self.bot.send_message(self.chat_id, rejection_message)
                    return False
                else:
                    # Sinal aprovado, adiciona carimbo de verificação
                    verified_message = f"✅ SINAL VERIFICADO PELO BOT\n\n{mensagem}"
                    self.bot.send_message(self.chat_id, verified_message)
                    logger.info("✅ Sinal aprovado e enviado")
                    return True
            else:
                # Mensagem normal (não é sinal)
                self.bot.send_message(self.chat_id, mensagem)
                return True
                
        except Exception as e:
            logger.error(f"❌ Erro ao enviar mensagem: {e}")
            return False

    def enviar_sinal_aprovado(self, signal_data):
        """Envia sinal que já foi pré-aprovado"""
        try:
            # Formata mensagem do sinal aprovado
            emoji = "🟢" if signal_data["direction"] == "CALL" else "🔴"
            
            message = f"""
✅ SINAL DUPLA VERIFICAÇÃO APROVADO
{"="*50}
{emoji} {signal_data["pair"]} - {signal_data["direction"]}
⏰ {signal_data["time"]} | ⏳ 1min
💪 Força: {signal_data["strength"]}
📊 RSI: {signal_data["rsi"]} | Preço: {signal_data["price"]}
🎯 Score: {signal_data.get("quality_score", "N/A")}/5
{"="*50}
"""
            
            self.bot.send_message(self.chat_id, message)
            logger.info("✅ Sinal pré-aprovado enviado")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro ao enviar sinal aprovado: {e}")
            return False