# Prompt para Extensión de Chrome de Claude
## LinkedIn Keyword Researcher — Extracción Manual

Copia el bloque entre las líneas `===` y pégalo en la extensión de Chrome de Claude
mientras tienes abierta una página de resultados de LinkedIn.

---

## PROMPT BASE (para páginas de resultados de búsqueda)

```
===
Eres un asistente especializado en identificar leads de negocio para una empresa
de call center / BPO / staffing. Estoy viendo una página de resultados de LinkedIn.

Analiza TODO el contenido visible en la pantalla y extrae TODOS los resultados
(personas, posts, empresas) que encuentres.

Para cada resultado, extrae:
- nombre: Nombre completo de la persona o empresa
- cargo: Título o cargo actual
- empresa: Empresa donde trabaja o nombre de la empresa
- ubicacion: Ciudad/país si aparece
- url_perfil: URL del perfil (formato /in/username o /company/name)
- tipo: "post" | "persona" | "empresa"
- contenido_post: Si es un post, los primeros 300 caracteres del texto
- fecha_post: Fecha del post si aparece (ej: "hace 2 horas", "1 día")
- relevancia: Del 1 al 5, qué tan relevante es para contactar sobre servicios
  de call center, BPO, outsourcing o staffing (5 = muy urgente / claramente busca)
- razon_relevancia: En 1 línea, por qué es relevante

Formato de salida: tabla Markdown con todas las columnas.
Luego, debajo de la tabla, lista SOLO los de relevancia 4 o 5 con un breve
mensaje de apertura personalizado que podría enviarles por LinkedIn.

Si no hay resultados visibles, dímelo y sugiere qué buscar.
===
```

---

## VARIANTE: Para páginas de POSTS específicos

Usa este prompt cuando hagas clic en un post y quieras analizar
quién comentó o reaccionó (señal de interés muy fuerte):

```
===
Estoy viendo un post de LinkedIn sobre [call center / hiring / staffing / BPO].
Analiza la pantalla completa y extrae:

1. AUTOR DEL POST:
   - nombre, cargo, empresa, URL perfil
   - resumen del post en 2 líneas
   - ¿el autor está buscando servicios o los ofrece?

2. PERSONAS QUE COMENTARON (si son visibles):
   Para cada comentarista:
   - nombre, cargo, empresa, URL perfil
   - texto del comentario
   - nivel de interés (1-5): ¿parece que necesita un call center/BPO?

3. ACCIÓN RECOMENDADA:
   ¿A quién contactar primero y con qué mensaje de apertura?

Formato: secciones claras con tabla para los comentaristas.
===
```

---

## VARIANTE: Para perfil individual

Usa este prompt cuando visites el perfil de alguien prometedor:

```
===
Estoy viendo un perfil de LinkedIn. Analiza toda la información visible:

1. DATOS DEL PERFIL: nombre, cargo actual, empresa, ubicación, URL
2. EXPERIENCIA: ¿tiene historial en call center, BPO, operaciones, CX, staffing?
3. ACTIVIDAD RECIENTE: posts o comentarios visibles, ¿mencionan alguna necesidad?
4. SEÑALES DE COMPRA: ¿hay indicios de que estén buscando servicios externos?
   (ej: expansión de equipo, nuevo mercado, quejas de operaciones, etc.)
5. SCORE LEAD (1-10): probabilidad de que necesiten nuestros servicios ahora
6. MENSAJE DE CONEXIÓN (300 caracteres): redacta un mensaje personalizado
   para enviarle solicitud de conexión, mencionando algo específico de su perfil.

Sé directo y honesto en el análisis.
===
```

---

## VARIANTE: Búsqueda de señales de demanda activa

Para buscar personas que PÚBLICAMENTE están pidiendo servicios de call center:

```
===
Analiza esta página de LinkedIn. Busco señales de que alguien necesita
contratar o externalizar servicios de call center, BPO, atención al cliente
o staffing de agentes.

Señales positivas a detectar:
✅ "looking for a call center partner"
✅ "we need to outsource customer service"
✅ "hiring 50+ agents" / contratando muchos agentes
✅ "scaling our support team"
✅ "need help with customer service overflow"
✅ Empresas en crecimiento buscando soporte operacional
✅ Posts sobre frustración con su operación actual de CX
✅ Ofertas de trabajo masivas en call center (señal de que tienen volumen)

Para cada señal encontrada, dime:
- nombre y cargo de quien publicó
- URL del perfil
- extracto del texto relevante
- nivel de urgencia (Alta / Media / Baja)
- mensaje de acercamiento sugerido

Si no hay señales claras en esta página, dímelo.
===
```
