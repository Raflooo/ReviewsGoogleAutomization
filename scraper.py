"""
scraper.py
----------
Entra al perfil de Google Maps de un negocio con un navegador real
(Playwright) y extrae la lista de reseñas visibles: autor, puntuación,
texto, y fecha aproximada.

IMPORTANTE - LEER ANTES DE USAR:
- Google cambia el HTML de Maps con frecuencia. Los selectores de abajo
  funcionaban al momento de escribir esto, pero es NORMAL que dejen de
  andar en algún momento. Si el scraper deja de traer resultados, el
  primer paso es abrir Google Maps en un navegador normal, inspeccionar
  el elemento de una reseña, y actualizar los selectores marcados con
  # SELECTOR más abajo.
- El scraping de Google Maps no está permitido por sus Términos de
  Servicio. Este script es un punto de partida técnico para un MVP/
  prueba de concepto, no una solución legalmente "segura" para producción
  a gran escala. Ver el README para alternativas (API oficial).
- Google puede mostrar CAPTCHAs o bloquear la IP si se hacen muchas
  requests seguidas. Este script incluye pausas para reducir ese riesgo,
  pero no las elimina.
"""

import hashlib
import re
import time
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional

from playwright.sync_api import sync_playwright, Page


@dataclass
class ScrapedReview:
    author: str
    rating: Optional[int]
    text: str
    review_date: Optional[date]
    review_hash: str


def _relative_to_date(relative_text: str) -> Optional[date]:
    """Convierte 'hace 3 semanas', 'hace un mes', etc. a una fecha aproximada."""
    if not relative_text:
        return None
    text = relative_text.lower().strip()
    today = date.today()

    match = re.search(r"(\d+)?\s*(día|dias|día|semana|mes|meses|año|años)", text)
    if not match:
        return today  # "hoy" / "ahora" / no reconocido -> asumimos reciente

    n = int(match.group(1)) if match.group(1) else 1
    unit = match.group(2)

    if "día" in unit or "dias" in unit:
        return today - timedelta(days=n)
    if "semana" in unit:
        return today - timedelta(weeks=n)
    if "mes" in unit:
        return today - timedelta(days=30 * n)
    if "año" in unit:
        return today - timedelta(days=365 * n)
    return today


def _make_hash(author: str, review_date_text: str, text: str) -> str:
    """Genera un identificador único y estable por reseña para detectar duplicados."""
    raw = f"{author.strip().lower()}|{review_date_text.strip().lower()}|{text.strip().lower()[:80]}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _open_reviews_tab(page: Page):
    """Hace click en la pestaña/botón de reseñas del perfil de Google Maps."""
    # SELECTOR: botón que dice "Reseñas" en el perfil del negocio
    page.wait_for_selector("button[aria-label*='Reseñas'], button[aria-label*='Reviews']", timeout=15000)
    page.click("button[aria-label*='Reseñas'], button[aria-label*='Reviews']")
    page.wait_for_timeout(2000)


def _scroll_reviews_panel(page: Page, max_scrolls: int = 15):
    """Scrollea el panel de reseñas para que Google cargue más contenido."""
    # SELECTOR: contenedor scrolleable de reseñas
    panel_selector = "div.m6QErb[aria-label]"
    try:
        panel = page.query_selector(panel_selector)
    except Exception:
        panel = None

    if not panel:
        return

    for _ in range(max_scrolls):
        page.evaluate(
            "(el) => el.scrollTo(0, el.scrollHeight)", panel
        )
        page.wait_for_timeout(1500)  # dejamos que cargue, y bajamos el riesgo de bloqueo


def scrape_reviews(profile_url: str, max_reviews: int = 60) -> list[ScrapedReview]:
    """
    Punto de entrada principal. Abre el link del negocio y devuelve
    una lista de reseñas extraídas (las más recientes primero, si
    el ordenamiento por fecha se pudo forzar).
    """
    reviews: list[ScrapedReview] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(locale="es-AR")
        page = context.new_page()

        page.goto(profile_url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(2000)

        _open_reviews_tab(page)

        # Intento de ordenar por "Más recientes" en vez de "Más relevantes"
        try:
            page.click("button[aria-label*='Ordenar'], button[aria-label*='Sort']", timeout=5000)
            page.wait_for_timeout(500)
            page.click("text=Más recientes", timeout=5000)
            page.wait_for_timeout(1500)
        except Exception:
            pass  # si no aparece el botón, seguimos con el orden default

        _scroll_reviews_panel(page, max_scrolls=max(5, max_reviews // 4))

        # SELECTOR: cada tarjeta individual de reseña
        review_cards = page.query_selector_all("div[data-review-id], div.jftiEf")

        for card in review_cards[:max_reviews]:
            try:
                author_el = card.query_selector("div.d4r55, [class*='author']")
                author = author_el.inner_text().strip() if author_el else "Anónimo"

                rating_el = card.query_selector("span[aria-label*='estrellas'], span[aria-label*='stars']")
                rating = None
                if rating_el:
                    label = rating_el.get_attribute("aria-label") or ""
                    m = re.search(r"(\d)", label)
                    if m:
                        rating = int(m.group(1))

                text_el = card.query_selector("span.wiI7pd, [class*='review-text']")
                text = text_el.inner_text().strip() if text_el else ""

                date_el = card.query_selector("span.rsqaWe, [class*='date']")
                date_text = date_el.inner_text().strip() if date_el else ""
                review_date = _relative_to_date(date_text)

                review_hash = _make_hash(author, date_text, text)

                reviews.append(
                    ScrapedReview(
                        author=author,
                        rating=rating,
                        text=text,
                        review_date=review_date,
                        review_hash=review_hash,
                    )
                )
            except Exception as e:
                # Una reseña individual falló al parsear -> la salteamos, no
                # frenamos todo el scraping por eso.
                print(f"  ! No se pudo parsear una reseña: {e}")
                continue

        browser.close()

    return reviews


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Uso: python scraper.py <link_del_negocio_en_google_maps>")
        sys.exit(1)

    url = sys.argv[1]
    print(f"Scrapeando: {url}")
    result = scrape_reviews(url)
    print(f"Se encontraron {len(result)} reseñas.")
    for r in result[:5]:
        print(f"- {r.author} ({r.rating}★, {r.review_date}): {r.text[:80]}")
