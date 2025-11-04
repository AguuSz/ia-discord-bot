FROM python:3.11-slim

# Establecer directorio de trabajo
WORKDIR /app

# Copiar archivos de dependencias
COPY requirements.txt .

# Instalar dependencias de Python
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el código del bot y utilidades
COPY bot.py .
COPY utils/ ./utils/

# Comando para ejecutar el bot
CMD ["python", "bot.py"]
