# Rutina Diaria — LinkedIn Keyword Researcher
## 3 sesiones × ~15 minutos = leads frescos todo el día

---

## ☀️ SESIÓN 1 — Mañana (8:00–8:15 am)
**Foco: Posts recientes + señales de demanda urgente**

Abre estas URLs en LinkedIn (una por una) y usa el **Prompt Base**:

```
# Búsquedas de POSTS ordenados por recientes:
https://www.linkedin.com/search/results/content/?keywords=looking+for+call+center&sortBy=date_posted
https://www.linkedin.com/search/results/content/?keywords=need+call+center+partner&sortBy=date_posted
https://www.linkedin.com/search/results/content/?keywords=outsource+customer+service&sortBy=date_posted
https://www.linkedin.com/search/results/content/?keywords=hiring+call+center+agents&sortBy=date_posted
https://www.linkedin.com/search/results/content/?keywords=BPO+partner&sortBy=date_posted
```

**Pasos:**
1. Abre la primera URL
2. Espera que cargue (scroll hasta abajo una vez)
3. Abre la extensión de Claude → pega el **Prompt Base**
4. Copia la tabla de resultados → pega en `acumulador.py` o en tu spreadsheet
5. Repite con la siguiente URL

---

## 🌤️ SESIÓN 2 — Mediodía (12:30–12:45 pm)
**Foco: Personas con títulos relevantes + empresas en crecimiento**

```
# Búsquedas de PERSONAS:
https://www.linkedin.com/search/results/people/?keywords=VP+customer+service+hiring
https://www.linkedin.com/search/results/people/?keywords=director+operations+BPO
https://www.linkedin.com/search/results/people/?keywords=head+of+cx+outsourcing
https://www.linkedin.com/search/results/people/?keywords=customer+service+manager+staffing
https://www.linkedin.com/search/results/people/?keywords=call+center+director
```

**Pasos:**
1. Filtra por **"2do grado de conexión"** en LinkedIn para mayor facilidad de contacto
2. Usa el **Prompt Base** o **Variante Perfil Individual** en los más prometedores
3. Para los leads con score 4-5, visita su perfil y usa la **Variante Perfil Individual**

---

## 🌙 SESIÓN 3 — Tarde (5:00–5:15 pm)
**Foco: Ofertas de trabajo masivas + señales de expansión**

```
# Posts con señales de crecimiento operacional:
https://www.linkedin.com/search/results/content/?keywords=estamos+contratando+atencion+cliente&sortBy=date_posted
https://www.linkedin.com/search/results/content/?keywords=buscamos+agentes+call+center&sortBy=date_posted
https://www.linkedin.com/search/results/content/?keywords=we+are+hiring+agents&sortBy=date_posted
https://www.linkedin.com/search/results/content/?keywords=customer+support+team+growing&sortBy=date_posted
https://www.linkedin.com/search/results/content/?keywords=tercerizar+servicio+cliente&sortBy=date_posted

# Empresas relevantes:
https://www.linkedin.com/search/results/companies/?keywords=staffing+agency
https://www.linkedin.com/search/results/companies/?keywords=call+center+outsourcing
```

---

## 📋 Keywords de rotación semanal

Rota estas búsquedas durante la semana para no repetir los mismos resultados:

### Lunes / Jueves
- `call center staffing`
- `contact center outsourcing`
- `customer service BPO`

### Martes / Viernes
- `helpdesk outsource`
- `remote agents hiring`
- `staff augmentation customer service`

### Miércoles
- `inside sales outsourcing`
- `back office BPO`
- `virtual assistant staffing`

---

## 💡 Tips para maximizar resultados

1. **Filtra por fecha** — siempre usa `&sortBy=date_posted` para ver posts del día
2. **Segundo grado primero** — tienen mayor tasa de aceptación de conexión
3. **Señales de urgencia** — palabras como "urgente", "ASAP", "this week", "immediately"
4. **Comentarios de posts** — si un post tiene 20+ comentarios sobre call centers,
   analiza quién comentó (usa la Variante de Posts)
5. **Guarda el contexto** — cuando Claude te dé un score 4-5, anótalo con fecha
   para hacer seguimiento en 3-5 días

---

## 📊 Dónde guardar los leads

**Opción A (simple):** Google Sheets
- Columnas: Fecha | Nombre | Cargo | Empresa | URL | Score | Mensaje | Estado

**Opción B (script):** Ejecutar `python accumulator.py` y pegar el JSON/CSV
que genera la extensión de Claude

**Opción C (CRM):** Pegar directamente en HubSpot / Pipedrive con las notas
generadas por Claude
