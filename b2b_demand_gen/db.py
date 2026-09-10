"""
Base de datos SQLite para historial de generaciones — Intelsa B2B Content Generator.

SQLite fue elegido porque:
- Sin servidor adicional: es un archivo .db local
- Consultas SQL completas (búsqueda, filtros, agregaciones)
- Migración trivial a PostgreSQL si se necesita escalar a multi-usuario/SaaS
- Soporta múltiples lecturas simultáneas (escrituras serializadas automáticamente)

Schema:
  generations — registro de cada pipeline ejecutado, con tokens, status y archivos
"""

import sqlite3
from datetime import datetime
from pathlib import Path

# El archivo .db vive junto a web_app.py
DB_PATH = Path(__file__).parent / "intelsa_content.db"


def init_db() -> None:
    """Crea las tablas si no existen. Se llama al inicio de la app."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS generations (
                id                      INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at              TEXT NOT NULL,
                topic                   TEXT NOT NULL,
                page_type               TEXT NOT NULL,
                target_market           TEXT,
                output_language         TEXT DEFAULT 'es',
                company_context         TEXT,
                status                  TEXT DEFAULT 'draft',
                webflow_item_id         TEXT,
                webflow_url             TEXT,
                complete_file           TEXT,
                -- Token accounting
                keyword_tokens          INTEGER DEFAULT 0,
                copy_tokens             INTEGER DEFAULT 0,
                webflow_tokens          INTEGER DEFAULT 0,
                total_tokens            INTEGER DEFAULT 0,
                -- Cache accounting (ahorro de créditos)
                cache_read_tokens       INTEGER DEFAULT 0,
                cache_creation_tokens   INTEGER DEFAULT 0
            )
        """)
        # Índices para las queries más comunes
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_gen_created ON generations(created_at DESC)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_gen_page_type ON generations(page_type)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_gen_status ON generations(status)"
        )
        conn.commit()


def save_generation(
    topic: str,
    page_type: str,
    target_market: str,
    output_language: str,
    company_context: str,
    complete_file: str,
    keyword_tokens: int,
    copy_tokens: int,
    webflow_tokens: int,
    cache_read_tokens: int = 0,
    cache_creation_tokens: int = 0,
    status: str = "draft",
    webflow_item_id: str | None = None,
    webflow_url: str | None = None,
) -> int:
    """Guarda un nuevo registro de generación. Retorna el ID insertado."""
    total = keyword_tokens + copy_tokens + webflow_tokens
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute(
            """
            INSERT INTO generations
              (created_at, topic, page_type, target_market, output_language,
               company_context, status, webflow_item_id, webflow_url, complete_file,
               keyword_tokens, copy_tokens, webflow_tokens, total_tokens,
               cache_read_tokens, cache_creation_tokens)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                datetime.now().isoformat(),
                topic,
                page_type,
                target_market or "",
                output_language or "es",
                company_context or "",
                status,
                webflow_item_id,
                webflow_url,
                complete_file or "",
                keyword_tokens,
                copy_tokens,
                webflow_tokens,
                total,
                cache_read_tokens,
                cache_creation_tokens,
            ),
        )
        conn.commit()
        return cursor.lastrowid


def list_generations(
    limit: int = 50,
    page_type: str | None = None,
    status: str | None = None,
    language: str | None = None,
) -> list[dict]:
    """Lista generaciones recientes con filtros opcionales."""
    conditions: list[str] = []
    params: list = []

    if page_type:
        conditions.append("page_type = ?")
        params.append(page_type)
    if status:
        conditions.append("status = ?")
        params.append(status)
    if language:
        conditions.append("output_language = ?")
        params.append(language)

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    params.append(limit)

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            f"SELECT * FROM generations {where} ORDER BY created_at DESC LIMIT ?",
            params,
        ).fetchall()

    return [dict(row) for row in rows]


def get_generation(gen_id: int) -> dict | None:
    """Obtiene un registro por ID."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM generations WHERE id = ?", (gen_id,)
        ).fetchone()
    return dict(row) if row else None


def update_status(
    gen_id: int,
    status: str,
    webflow_item_id: str | None = None,
    webflow_url: str | None = None,
) -> None:
    """Actualiza el estado de un registro (draft → approved → published)."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            UPDATE generations
            SET status = ?,
                webflow_item_id = COALESCE(?, webflow_item_id),
                webflow_url = COALESCE(?, webflow_url)
            WHERE id = ?
            """,
            (status, webflow_item_id, webflow_url, gen_id),
        )
        conn.commit()


def get_stats() -> dict:
    """
    Retorna estadísticas de uso de la herramienta.
    Útil para monitorear consumo de créditos y ROI.
    """
    _cols = [
        "total_generations", "total_tokens", "total_cache_read",
        "total_cache_created", "service_count", "industry_count",
        "blog_count", "published_count", "english_count", "spanish_count",
    ]
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            """
            SELECT
                COUNT(*),
                COALESCE(SUM(total_tokens), 0),
                COALESCE(SUM(cache_read_tokens), 0),
                COALESCE(SUM(cache_creation_tokens), 0),
                SUM(CASE WHEN page_type='service' THEN 1 ELSE 0 END),
                SUM(CASE WHEN page_type='industry' THEN 1 ELSE 0 END),
                SUM(CASE WHEN page_type='blog' THEN 1 ELSE 0 END),
                SUM(CASE WHEN status='published' THEN 1 ELSE 0 END),
                SUM(CASE WHEN output_language='en' THEN 1 ELSE 0 END),
                SUM(CASE WHEN output_language='es' THEN 1 ELSE 0 END)
            FROM generations
            """
        ).fetchone()
    return dict(zip(_cols, row)) if row else dict.fromkeys(_cols, 0)
