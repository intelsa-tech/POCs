# Claude Telegram Bot (OpenClaw-style)

Bot de Telegram powered by **Claude claude-opus-4-6** con memoria de conversación por usuario, análisis de imágenes y razonamiento avanzado (adaptive thinking).

## Características

| Feature | Detalle |
|---|---|
| 🧠 Modelo | Claude claude-opus-4-6 con adaptive thinking |
| 💬 Multi-turno | Historial de conversación por usuario en memoria |
| 🖼️ Imágenes | Análisis de fotos enviadas por Telegram |
| 🔐 Whitelist | Lista de usuarios autorizados (opcional) |
| 🔄 `/new` | Reiniciar conversación |

## Setup rápido

### 1. Obtener tokens

**Telegram Bot Token:**
1. Habla con [@BotFather](https://t.me/BotFather) en Telegram
2. Envía `/newbot` y sigue las instrucciones
3. Copia el token que te da

**Anthropic API Key:**
1. Ve a [console.anthropic.com](https://console.anthropic.com)
2. Crea una API key

### 2. Instalar dependencias

```bash
cd telegram_bot
pip install -r requirements.txt
```

### 3. Configurar variables de entorno

```bash
cp .env.example .env
# Edita .env con tus tokens
```

Contenido de `.env`:
```env
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrSTUvwxYZ
ANTHROPIC_API_KEY=sk-ant-...

# Opcional: solo estos usuarios pueden usar el bot (IDs separados por coma)
ALLOWED_USER_IDS=123456789

# Opcional: personalidad del bot
SYSTEM_PROMPT=Eres un asistente de IA útil y conciso.

# Opcional: turnos de historial a mantener (default: 20)
MAX_HISTORY_TURNS=20
```

> **¿Cómo saber tu user ID?** Habla con [@userinfobot](https://t.me/userinfobot) en Telegram.

### 4. Ejecutar

```bash
python bot.py
```

## Comandos del bot

| Comando | Descripción |
|---|---|
| `/start` | Bienvenida e instrucciones |
| `/help` | Lista de comandos y capacidades |
| `/new` | Borrar historial y empezar de cero |

## Uso

- **Chat normal**: escribe cualquier mensaje y Claude responderá manteniendo el contexto
- **Imágenes**: envía una foto con o sin caption; Claude la analizará
- **Conversación larga**: el bot mantiene los últimos `MAX_HISTORY_TURNS` turnos (configurable)

## Despliegue en producción

### Opción A: servidor VPS / VM

```bash
# Instalar como servicio systemd
sudo nano /etc/systemd/system/claude-telegram-bot.service
```

```ini
[Unit]
Description=Claude Telegram Bot
After=network.target

[Service]
Type=simple
User=tu_usuario
WorkingDirectory=/ruta/al/telegram_bot
EnvironmentFile=/ruta/al/telegram_bot/.env
ExecStart=/usr/bin/python3 bot.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable --now claude-telegram-bot
```

### Opción B: Docker

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY bot.py .
CMD ["python", "bot.py"]
```

```bash
docker build -t claude-telegram-bot .
docker run -d --env-file .env --restart unless-stopped claude-telegram-bot
```

### Opción C: Railway / Render / Fly.io

Sube el directorio `telegram_bot/` como proyecto y configura las variables de entorno en el dashboard de la plataforma.

## Costos aproximados

El bot usa **Claude claude-opus-4-6** ($5/1M tokens input, $25/1M tokens output). Para uso personal liviano (100-200 mensajes/día), espera menos de $1-2/mes.

Para reducir costos, cambia `MODEL = "claude-haiku-4-5"` en `bot.py`.
