# Usa imagem oficial do Python
FROM python:3.11-slim

# Cria diretório de trabalho
WORKDIR /app

# Copia os arquivos
COPY requirements.txt .
COPY main.py .
COPY bot_telegram.py .
COPY config.json .

# Instala dependências
RUN pip install --no-cache-dir -r requirements.txt

# Executa o script
CMD ["python", "main.py"]
