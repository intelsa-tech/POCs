"""
LinkedIn Keyword Researcher - Scraper
======================================
Usa Playwright para buscar keywords en LinkedIn y extraer leads.

Flujo:
  1. Login con credenciales de .env
  2. Por cada keyword → buscar Posts y/o People
  3. Extraer datos de cada resultado
  4. Retornar lista de Lead objects
"""

import asyncio
import logging
import os
import random
import re
import time
from typing import List, Optional
from urllib.parse import quote_plus

from dotenv import load_dotenv
from playwright.async_api import (
    Browser,
    BrowserContext,
    Page,
    async_playwright,
)

from config import KEYWORD_GROUPS, ALL_KEYWORDS, ScraperConfig, DEFAULT_CONFIG
from storage import Lead

load_dotenv()
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _group_for_keyword(keyword: str) -> str:
    for group, keywords in KEYWORD_GROUPS.items():
        if keyword in keywords:
            return group
    return "General"


def _clean_text(text: Optional[str]) -> str:
    if not text:
        return ""
    return " ".join(text.strip().split())


async def _human_delay(min_s: float = 1.0, max_s: float = 3.0):
    """Pausa aleatoria para simular comportamiento humano."""
    await asyncio.sleep(random.uniform(min_s, max_s))


# ---------------------------------------------------------------------------
# Scraper principal
# ---------------------------------------------------------------------------

class LinkedInScraper:
    def __init__(self, config: ScraperConfig = DEFAULT_CONFIG):
        self.config = config
        self.email = os.getenv("LINKEDIN_EMAIL", "")
        self.password = os.getenv("LINKEDIN_PASSWORD", "")
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None

    # ------------------------------------------------------------------
    # Session management
    # ------------------------------------------------------------------

    async def start(self):
        """Inicia el browser y hace login en LinkedIn."""
        if not self.email or not self.password:
            raise ValueError(
                "Credenciales de LinkedIn no encontradas. "
                "Define LINKEDIN_EMAIL y LINKEDIN_PASSWORD en el archivo .env"
            )

        playwright = await async_playwright().start()
        self._browser = await playwright.chromium.launch(
            headless=self.config.headless,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
                "--lang=es-419,es",
            ],
        )
        self._context = await self._browser.new_context(
            viewport={"width": 1280, "height": 900},
            locale="es-419",
            timezone_id="America/Bogota",
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )
        self._page = await self._context.new_page()
        self._page.set_default_timeout(self.config.page_timeout)

        # Ocultar señales de automatización
        await self._page.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )

        await self._login()

    async def _login(self):
        logger.info("Iniciando sesión en LinkedIn...")
        page = self._page
        await page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded")
        await _human_delay(1, 2)

        await page.fill("#username", self.email)
        await _human_delay(0.5, 1)
        await page.fill("#password", self.password)
        await _human_delay(0.5, 1)
        await page.click('button[type="submit"]')

        # Esperar redirección al feed
        try:
            await page.wait_for_url("**/feed/**", timeout=15_000)
            logger.info("Login exitoso.")
        except Exception:
            # Puede haber un checkpoint de verificación
            current = page.url
            if "checkpoint" in current or "challenge" in current:
                logger.warning(
                    "LinkedIn solicita verificación adicional. "
                    "Ejecuta en modo headless=False para resolverla manualmente."
                )
                # Esperar hasta 60s para que el usuario resuelva el captcha
                await page.wait_for_url("**/feed/**", timeout=60_000)
            else:
                raise RuntimeError(f"Login fallido. URL actual: {current}")

    async def close(self):
        if self._browser:
            await self._browser.close()

    # ------------------------------------------------------------------
    # Búsqueda de Posts
    # ------------------------------------------------------------------

    async def search_posts(self, keyword: str) -> List[Lead]:
        """Busca posts en LinkedIn que contengan el keyword."""
        leads: List[Lead] = []
        page = self._page
        encoded = quote_plus(keyword)
        url = (
            f"https://www.linkedin.com/search/results/content/"
            f"?keywords={encoded}&sortBy=date_posted"
        )

        logger.info(f"  [POSTS] Buscando: '{keyword}'")
        await page.goto(url, wait_until="domcontentloaded")
        await _human_delay(2, 3)

        # Scroll para cargar más resultados
        for _ in range(3):
            await page.keyboard.press("End")
            await _human_delay(self.config.delay_scroll, self.config.delay_scroll + 1)

        # Extraer cards de posts
        post_cards = await page.query_selector_all(
            "div.search-results-container li.reusable-search__result-container"
        )

        for card in post_cards[: self.config.max_results_per_keyword]:
            try:
                lead = await self._extract_post_lead(card, keyword)
                if lead:
                    leads.append(lead)
            except Exception as e:
                logger.debug(f"Error extrayendo post: {e}")

        logger.info(f"    → {len(leads)} posts encontrados")
        return leads

    async def _extract_post_lead(self, card, keyword: str) -> Optional[Lead]:
        page = self._page

        # Nombre del autor
        name_el = await card.query_selector(
            "span.entity-result__title-text a span[aria-hidden='true']"
        )
        name = _clean_text(await name_el.inner_text() if name_el else None)

        # Título / cargo
        title_el = await card.query_selector(
            "div.entity-result__primary-subtitle"
        )
        title = _clean_text(await title_el.inner_text() if title_el else None)

        # Contenido del post
        content_el = await card.query_selector(
            "p.entity-result__content-summary"
        )
        post_content = _clean_text(await content_el.inner_text() if content_el else None)

        # URL del perfil
        profile_link = await card.query_selector(
            "a.app-aware-link[href*='/in/']"
        )
        profile_url = ""
        if profile_link:
            href = await profile_link.get_attribute("href")
            match = re.search(r"(https://www\.linkedin\.com/in/[^/?]+)", href or "")
            profile_url = match.group(1) if match else (href or "")

        # Fecha del post (si aparece)
        date_el = await card.query_selector(
            "time, span.entity-result__badge-text"
        )
        post_date = _clean_text(await date_el.inner_text() if date_el else None)

        if not name and not profile_url:
            return None

        # Derivar empresa del título si está en formato "Cargo en Empresa"
        company = ""
        if title and " en " in title.lower():
            parts = re.split(r"\s+en\s+", title, maxsplit=1, flags=re.IGNORECASE)
            if len(parts) == 2:
                company = parts[1]

        return Lead(
            keyword=keyword,
            keyword_group=_group_for_keyword(keyword),
            search_type="posts",
            name=name,
            title=title,
            company=company,
            location="",
            profile_url=profile_url,
            post_content=post_content[:500],  # truncar a 500 chars
            post_date=post_date,
        )

    # ------------------------------------------------------------------
    # Búsqueda de Personas
    # ------------------------------------------------------------------

    async def search_people(self, keyword: str) -> List[Lead]:
        """Busca perfiles de personas cuyo headline/cargo contiene el keyword."""
        leads: List[Lead] = []
        encoded = quote_plus(keyword)
        url = (
            f"https://www.linkedin.com/search/results/people/"
            f"?keywords={encoded}"
        )

        logger.info(f"  [PEOPLE] Buscando: '{keyword}'")
        await self._page.goto(url, wait_until="domcontentloaded")
        await _human_delay(2, 3)

        for _ in range(2):
            await self._page.keyboard.press("End")
            await _human_delay(self.config.delay_scroll, self.config.delay_scroll + 1)

        people_cards = await self._page.query_selector_all(
            "div.search-results-container li.reusable-search__result-container"
        )

        for card in people_cards[: self.config.max_results_per_keyword]:
            try:
                lead = await self._extract_person_lead(card, keyword)
                if lead:
                    leads.append(lead)
            except Exception as e:
                logger.debug(f"Error extrayendo persona: {e}")

        logger.info(f"    → {len(leads)} personas encontradas")
        return leads

    async def _extract_person_lead(self, card, keyword: str) -> Optional[Lead]:
        name_el = await card.query_selector(
            "span.entity-result__title-text a span[aria-hidden='true']"
        )
        name = _clean_text(await name_el.inner_text() if name_el else None)

        title_el = await card.query_selector(
            "div.entity-result__primary-subtitle"
        )
        title = _clean_text(await title_el.inner_text() if title_el else None)

        location_el = await card.query_selector(
            "div.entity-result__secondary-subtitle"
        )
        location = _clean_text(await location_el.inner_text() if location_el else None)

        profile_link = await card.query_selector(
            "a.app-aware-link[href*='/in/']"
        )
        profile_url = ""
        if profile_link:
            href = await profile_link.get_attribute("href")
            match = re.search(r"(https://www\.linkedin\.com/in/[^/?]+)", href or "")
            profile_url = match.group(1) if match else (href or "")

        if not name and not profile_url:
            return None

        company = ""
        if title and " en " in title.lower():
            parts = re.split(r"\s+en\s+", title, maxsplit=1, flags=re.IGNORECASE)
            if len(parts) == 2:
                company = parts[1]

        return Lead(
            keyword=keyword,
            keyword_group=_group_for_keyword(keyword),
            search_type="people",
            name=name,
            title=title,
            company=company,
            location=location,
            profile_url=profile_url,
            post_content="",
            post_date="",
        )

    # ------------------------------------------------------------------
    # Búsqueda de Empresas
    # ------------------------------------------------------------------

    async def search_companies(self, keyword: str) -> List[Lead]:
        """Busca empresas relacionadas con el keyword."""
        leads: List[Lead] = []
        encoded = quote_plus(keyword)
        url = (
            f"https://www.linkedin.com/search/results/companies/"
            f"?keywords={encoded}"
        )

        logger.info(f"  [COMPANIES] Buscando: '{keyword}'")
        await self._page.goto(url, wait_until="domcontentloaded")
        await _human_delay(2, 3)

        company_cards = await self._page.query_selector_all(
            "div.search-results-container li.reusable-search__result-container"
        )

        for card in company_cards[: self.config.max_results_per_keyword]:
            try:
                lead = await self._extract_company_lead(card, keyword)
                if lead:
                    leads.append(lead)
            except Exception as e:
                logger.debug(f"Error extrayendo empresa: {e}")

        logger.info(f"    → {len(leads)} empresas encontradas")
        return leads

    async def _extract_company_lead(self, card, keyword: str) -> Optional[Lead]:
        name_el = await card.query_selector(
            "span.entity-result__title-text a span[aria-hidden='true']"
        )
        name = _clean_text(await name_el.inner_text() if name_el else None)

        subtitle_el = await card.query_selector(
            "div.entity-result__primary-subtitle"
        )
        industry = _clean_text(await subtitle_el.inner_text() if subtitle_el else None)

        location_el = await card.query_selector(
            "div.entity-result__secondary-subtitle"
        )
        location = _clean_text(await location_el.inner_text() if location_el else None)

        profile_link = await card.query_selector(
            "a.app-aware-link[href*='/company/']"
        )
        profile_url = ""
        if profile_link:
            href = await profile_link.get_attribute("href")
            match = re.search(r"(https://www\.linkedin\.com/company/[^/?]+)", href or "")
            profile_url = match.group(1) if match else (href or "")

        if not name and not profile_url:
            return None

        return Lead(
            keyword=keyword,
            keyword_group=_group_for_keyword(keyword),
            search_type="companies",
            name=name,
            title=industry,
            company=name,
            location=location,
            profile_url=profile_url,
            post_content="",
            post_date="",
        )

    # ------------------------------------------------------------------
    # Runner principal
    # ------------------------------------------------------------------

    async def run(self, keywords: List[str] = None) -> List[Lead]:
        """Ejecuta todas las búsquedas y retorna la lista de leads."""
        if keywords is None:
            keywords = ALL_KEYWORDS

        all_leads: List[Lead] = []

        for keyword in keywords:
            if "posts" in self.config.search_types:
                leads = await self.search_posts(keyword)
                all_leads.extend(leads)
                await _human_delay(
                    self.config.delay_between_searches,
                    self.config.delay_between_searches + 2,
                )

            if "people" in self.config.search_types:
                leads = await self.search_people(keyword)
                all_leads.extend(leads)
                await _human_delay(
                    self.config.delay_between_searches,
                    self.config.delay_between_searches + 2,
                )

            if "companies" in self.config.search_types:
                leads = await self.search_companies(keyword)
                all_leads.extend(leads)
                await _human_delay(
                    self.config.delay_between_searches,
                    self.config.delay_between_searches + 2,
                )

        return all_leads
