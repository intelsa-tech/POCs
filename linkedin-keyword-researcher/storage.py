"""
LinkedIn Keyword Researcher - Storage
======================================
Guarda resultados en CSV y JSON, evita duplicados.
"""

import csv
import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import List, Set

from config import DEFAULT_CONFIG


@dataclass
class Lead:
    """Representa un lead/resultado encontrado en LinkedIn."""
    keyword: str
    keyword_group: str
    search_type: str          # posts | people | companies | jobs
    name: str
    title: str
    company: str
    location: str
    profile_url: str
    post_content: str         # Solo para search_type=posts
    post_date: str            # Solo para search_type=posts
    found_at: str = ""        # Timestamp de cuándo lo encontramos

    def __post_init__(self):
        if not self.found_at:
            self.found_at = datetime.now().isoformat()

    @property
    def unique_id(self) -> str:
        """ID único para detectar duplicados."""
        return f"{self.profile_url}::{self.keyword}"


class ResultStorage:
    def __init__(self, config=DEFAULT_CONFIG):
        self.config = config
        os.makedirs(config.output_dir, exist_ok=True)
        self.csv_path = os.path.join(config.output_dir, config.output_file)
        self.seen_path = os.path.join(config.output_dir, config.seen_file)
        self._seen_ids: Set[str] = self._load_seen()

    # ------------------------------------------------------------------
    # Seen IDs  (evitar duplicados entre ejecuciones)
    # ------------------------------------------------------------------
    def _load_seen(self) -> Set[str]:
        if os.path.exists(self.seen_path):
            with open(self.seen_path, "r", encoding="utf-8") as f:
                return set(json.load(f))
        return set()

    def _save_seen(self):
        with open(self.seen_path, "w", encoding="utf-8") as f:
            json.dump(list(self._seen_ids), f, ensure_ascii=False, indent=2)

    def is_new(self, lead: Lead) -> bool:
        return lead.unique_id not in self._seen_ids

    # ------------------------------------------------------------------
    # CSV
    # ------------------------------------------------------------------
    def _ensure_csv_header(self):
        if not os.path.exists(self.csv_path):
            with open(self.csv_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=Lead.__dataclass_fields__.keys())
                writer.writeheader()

    def save_leads(self, leads: List[Lead]) -> int:
        """Guarda leads nuevos en CSV. Retorna cuántos se guardaron."""
        new_leads = [l for l in leads if self.is_new(l)]
        if not new_leads:
            return 0

        self._ensure_csv_header()
        with open(self.csv_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=Lead.__dataclass_fields__.keys())
            for lead in new_leads:
                writer.writerow(asdict(lead))
                self._seen_ids.add(lead.unique_id)

        self._save_seen()
        return len(new_leads)

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------
    def total_saved(self) -> int:
        return len(self._seen_ids)

    def load_all_leads(self) -> List[dict]:
        if not os.path.exists(self.csv_path):
            return []
        with open(self.csv_path, "r", encoding="utf-8") as f:
            return list(csv.DictReader(f))
