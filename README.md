# 🤖 Bot de Trading com Sinais Automáticos

Um sistema completo de análise técnica que coleta dados de mercado e envia sinais de trading para o Telegram.

## 📋 O que faz?

- **Coleta dados** de pares de moedas em tempo real
- **Analisa** usando RSI, MACD, Bollinger Bands
- **Envia sinais** automáticos para o Telegram
- **Acompanha resultados** e calcula taxa de acerto

## 🚀 Como usar

### 1. Configure suas credenciais

Edite o arquivo `config.json`:

```json
{
  "telegram": {
    "bot_token": "SEU_TOKEN_DO_BOT",
    "chat_id": "SEU_CHAT_ID"
  }
}
```

### 2. Execute o sistema

```bash
# Inicia o coletor de dados
docker-compose -f docker-compose.yml up -d

# Inicia o bot de sinais  
python main.py
```

## ⚙️ Configurações importantes

No `config.json` você pode ajustar:

- **Pares**: Moedas para analisar (`EURUSD`, `GBPUSD`, etc.)
- **RSI**: Níveis de sobrecompra/sobrevenda
- **Score mínimo**: Qualidade mínima dos sinais (0-17)
- **Horários**: Evita sinais em horários ruins

## 📊 Como funciona

1. **Coletor** (`collector.py`) - Pega dados do mercado
2. **Analisador** (`main.py`) - Analisa e gera sinais
3. **Telegram** - Recebe os sinais automaticamente

## 🎯 Exemplo de sinal

```
🟢 EURUSD - CALL
⏰ 14:30:25 | ⏳ 1min
🔥💎 EXTREMA | Score: 15/17
📊 RSI: 22.5 | Trend: STRONG_UP
📈 MACD: 0.000123 | BB: LOWER
🌍 LONDON | 💰 $1.08450

🎲 GALES:
   G0: $1.0
   G1: $2.2
   G2: $4.84
```

## 📦 Arquivos principais

- `main.py` - Bot principal de análise
- `collector.py` - Coleta dados do mercado
- `bot_telegram.py` - Integração com Telegram
- `config.json` - Todas as configurações
- `docker-compose.yml` - Para rodar em container

## ⚠️ Importante

- Teste sempre com conta demo primeiro
- Configure o score mínimo adequado (6-10)
- Monitore os horários de trading
- Trading envolve riscos - use com responsabilidade

## 🔧 Requisitos

- Python 3.8+
- MongoDB (já configurado)
- Bot do Telegram criado
- Conexão com internet estável
