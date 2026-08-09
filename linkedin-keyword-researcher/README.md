# LinkedIn Keyword Researcher

Monitorea LinkedIn en busca de personas y empresas que mencionen keywords relacionadas con **call centers, staffing, hiring y BPO** para detectar oportunidades de negocio en tiempo real.

---

## Características

| Feature | Detalle |
|---|---|
| 🔍 Búsqueda multi-keyword | Posts, personas y empresas |
| 📂 Categorías configurables | BPO, Hiring, Staffing, Señales de demanda |
| 💾 Almacenamiento CSV | Sin duplicados entre ejecuciones |
| 🔔 Alertas | Consola con colores, Email (Gmail) y Slack |
| ⏰ Modo programado | Ejecuta cada N minutos automáticamente |
| 🤖 Anti-detección | Delays aleatorios, user-agent realista |

---

## Instalación

```bash
# 1. Instalar dependencias Python
pip install -r requirements.txt

# 2. Instalar browsers de Playwright (solo una vez)
playwright install chromium

# 3. Configurar credenciales
cp .env.example .env
# Editar .env con tu email y contraseña de LinkedIn
```

---

## Uso

### Ejecución única
```bash
python main.py
```

### Loop automático cada 60 minutos
```bash
python main.py --schedule 60
```

### Buscar keywords específicas
```bash
python main.py --keywords "hiring manager" "staffing agency" "outsourcing"
```

### Ver el browser en pantalla (útil para debug o verificación manual)
```bash
python main.py --no-headless
```

### Ver reporte de leads guardados
```bash
python main.py --report
```

### Opciones completas
```bash
python main.py --help
```

---

## Configuración de Keywords

Edita `config.py` para personalizar:

```python
KEYWORD_GROUPS = {
    "BPO / Call Center": [
        "call center", "BPO", "contact center", ...
    ],
    "Hiring / Staffing": [
        "hiring", "staffing", "recruitment", ...
    ],
    # Agrega tus propias categorías
    "Mi nicho": [
        "mi keyword 1", "mi keyword 2",
    ],
}
```

---

## Resultados

Los resultados se guardan en `results/leads.csv` con las columnas:

| Campo | Descripción |
|---|---|
| `keyword` | Keyword que disparó el resultado |
| `keyword_group` | Categoría de la keyword |
| `search_type` | posts / people / companies |
| `name` | Nombre del autor / persona / empresa |
| `title` | Cargo o industria |
| `company` | Empresa |
| `location` | Ubicación |
| `profile_url` | Enlace directo al perfil de LinkedIn |
| `post_content` | Fragmento del post (solo para posts) |
| `post_date` | Fecha del post |
| `found_at` | Timestamp de la detección |

---

## Alertas

### Email (Gmail)
1. Activa verificación en 2 pasos en tu cuenta Google
2. Crea una [App Password](https://myaccount.google.com/apppasswords)
3. Completa `SMTP_USER`, `SMTP_PASS` y `ALERT_EMAIL` en `.env`

### Slack
1. Crea una app en https://api.slack.com/apps
2. Activa "Incoming Webhooks"
3. Copia la URL al campo `SLACK_WEBHOOK_URL` en `.env`

---

## Notas importantes

- LinkedIn **no permite scraping** en sus Términos de Servicio. Úsalo con moderación y bajo tu propio riesgo.
- Usa delays entre búsquedas para reducir la probabilidad de bloqueo.
- Si LinkedIn pide verificación (captcha/checkpoint), ejecuta con `--no-headless` para resolverlo manualmente.
- Recomendado: máximo 2-3 ejecuciones por día por cuenta.
