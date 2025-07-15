import requests

class TelegramBot:
    def __init__(self, bot_token, chat_id):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{bot_token}"

    def enviar_mensagem(self, mensagem, reply_to_message_id=None):
        url = f"{self.base_url}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": mensagem,
            "parse_mode": "HTML"
        }
        if reply_to_message_id is not None:
            payload["reply_to_message_id"] = reply_to_message_id
        try:
            response = requests.post(url, json=payload, timeout=5)
            data = response.json()
            if data.get("ok"):
                return data["result"]["message_id"]
            else:
                print(f"Erro ao enviar mensagem: {data}")
                return None
        except Exception as e:
            print(f"Erro no envio para Telegram: {e}")
            return None
