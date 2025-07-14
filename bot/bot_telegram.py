import requests
import logging

logger = logging.getLogger(__name__)


class TelegramBot:
    def __init__(self, bot_token, chat_id):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{bot_token}"

    def enviar_mensagem(self, mensagem, reply_to_message_id=None):
        """
        Envia uma mensagem para o Telegram

        Args:
            mensagem (str): Texto da mensagem
            reply_to_message_id (int, optional): ID da mensagem para fazer reply

        Returns:
            int: ID da mensagem enviada ou None se houver erro
        """
        try:
            url = f"{self.base_url}/sendMessage"

            payload = {"chat_id": self.chat_id, "text": mensagem, "parse_mode": "HTML"}

            # Adiciona reply_to_message_id se fornecido
            if reply_to_message_id:
                payload["reply_to_message_id"] = reply_to_message_id

            response = requests.post(url, json=payload)

            if response.status_code == 200:
                result = response.json()
                if result.get("ok"):
                    message_id = result["result"]["message_id"]
                    logger.info(f"✅ Mensagem enviada com sucesso (ID: {message_id})")
                    return message_id
                else:
                    logger.error(f"❌ Erro na resposta da API: {result}")
                    return None
            else:
                logger.error(f"❌ Erro HTTP {response.status_code}: {response.text}")
                return None

        except Exception as e:
            logger.error(f"❌ Erro ao enviar mensagem: {e}")
            return None

    def enviar_foto(self, photo_path, caption=None, reply_to_message_id=None):
        """
        Envia uma foto para o Telegram

        Args:
            photo_path (str): Caminho para a foto
            caption (str, optional): Legenda da foto
            reply_to_message_id (int, optional): ID da mensagem para fazer reply

        Returns:
            int: ID da mensagem enviada ou None se houver erro
        """
        try:
            url = f"{self.base_url}/sendPhoto"

            data = {"chat_id": self.chat_id}

            if caption:
                data["caption"] = caption

            if reply_to_message_id:
                data["reply_to_message_id"] = reply_to_message_id

            with open(photo_path, "rb") as photo:
                files = {"photo": photo}
                response = requests.post(url, data=data, files=files)

            if response.status_code == 200:
                result = response.json()
                if result.get("ok"):
                    message_id = result["result"]["message_id"]
                    logger.info(f"✅ Foto enviada com sucesso (ID: {message_id})")
                    return message_id
                else:
                    logger.error(f"❌ Erro na resposta da API: {result}")
                    return None
            else:
                logger.error(f"❌ Erro HTTP {response.status_code}: {response.text}")
                return None

        except Exception as e:
            logger.error(f"❌ Erro ao enviar foto: {e}")
            return None

    def editar_mensagem(self, message_id, nova_mensagem):
        """
        Edita uma mensagem existente

        Args:
            message_id (int): ID da mensagem a ser editada
            nova_mensagem (str): Novo texto da mensagem

        Returns:
            bool: True se sucesso, False caso contrário
        """
        try:
            url = f"{self.base_url}/editMessageText"

            payload = {
                "chat_id": self.chat_id,
                "message_id": message_id,
                "text": nova_mensagem,
                "parse_mode": "HTML",
            }

            response = requests.post(url, json=payload)

            if response.status_code == 200:
                result = response.json()
                if result.get("ok"):
                    logger.info(f"✅ Mensagem editada com sucesso (ID: {message_id})")
                    return True
                else:
                    logger.error(f"❌ Erro na resposta da API: {result}")
                    return False
            else:
                logger.error(f"❌ Erro HTTP {response.status_code}: {response.text}")
                return False

        except Exception as e:
            logger.error(f"❌ Erro ao editar mensagem: {e}")
            return False

    def deletar_mensagem(self, message_id):
        """
        Deleta uma mensagem

        Args:
            message_id (int): ID da mensagem a ser deletada

        Returns:
            bool: True se sucesso, False caso contrário
        """
        try:
            url = f"{self.base_url}/deleteMessage"

            payload = {"chat_id": self.chat_id, "message_id": message_id}

            response = requests.post(url, json=payload)

            if response.status_code == 200:
                result = response.json()
                if result.get("ok"):
                    logger.info(f"✅ Mensagem deletada com sucesso (ID: {message_id})")
                    return True
                else:
                    logger.error(f"❌ Erro na resposta da API: {result}")
                    return False
            else:
                logger.error(f"❌ Erro HTTP {response.status_code}: {response.text}")
                return False

        except Exception as e:
            logger.error(f"❌ Erro ao deletar mensagem: {e}")
            return False
