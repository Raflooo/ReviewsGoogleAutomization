"""
main.py
-------
Orquestador principal. Este es el script que corre el cron job
(GitHub Actions) cada X horas.

Para cada negocio guardado en la base:
  1. Scrapea las reseñas actuales del perfil.
  2. Compara contra lo que ya teníamos guardado -> detecta reseñas NUEVAS.
  3. Para cada reseña nueva: la analiza con IA, la agrupa a un problema
     existente o crea uno nuevo, y genera/actualiza una tarea.
  4. Archiva reseñas y tareas de más de 1 año sin actividad.
"""

import os
from datetime import date, timedelta

from dotenv import load_dotenv
from supabase import create_client

from scraper import scrape_reviews
from analyzer import analyze_review, find_matching_problem

load_dotenv()

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


def get_businesses():
    response = supabase.table("businesses").select("*").execute()
    return response.data


def get_existing_review_hashes(business_id: str) -> set[str]:
    response = (
        supabase.table("reviews")
        .select("external_review_hash")
        .eq("business_id", business_id)
        .execute()
    )
    return {row["external_review_hash"] for row in response.data}


def get_open_problems(business_id: str) -> list[dict]:
    response = (
        supabase.table("problems")
        .select("*")
        .eq("business_id", business_id)
        .neq("status", "archivado")
        .execute()
    )
    return response.data


def process_business(business: dict):
    business_id = business["id"]
    print(f"\n== Procesando: {business['name']} ==")

    scraped = scrape_reviews(business["profile_url"])
    print(f"  Reseñas encontradas en el perfil: {len(scraped)}")

    existing_hashes = get_existing_review_hashes(business_id)
    new_reviews = [r for r in scraped if r.review_hash not in existing_hashes]
    print(f"  Reseñas NUEVAS detectadas: {len(new_reviews)}")

    if not new_reviews:
        supabase.table("businesses").update(
            {"last_checked_at": "now()"}
        ).eq("id", business_id).execute()
        return

    open_problems = get_open_problems(business_id)

    for review in new_reviews:
        # 1. Guardar la reseña
        review_row = (
            supabase.table("reviews")
            .insert(
                {
                    "business_id": business_id,
                    "external_review_hash": review.review_hash,
                    "author": review.author,
                    "rating": review.rating,
                    "review_text": review.text,
                    "review_date": review.review_date.isoformat() if review.review_date else None,
                }
            )
            .execute()
            .data[0]
        )

        # 2. Analizar con IA
        analysis = analyze_review(review.text, review.rating)

        supabase.table("reviews").update({"sentiment": analysis["sentiment"]}).eq(
            "id", review_row["id"]
        ).execute()

        if not analysis.get("has_problem"):
            continue

        # 3. Agrupar con un problema existente, o crear uno nuevo
        match = find_matching_problem(
            open_problems, analysis["problem_category"], analysis["problem_label"]
        )

        if match:
            supabase.table("problems").update(
                {
                    "affected_reviews_count": match["affected_reviews_count"] + 1,
                    "last_seen_at": "now()",
                }
            ).eq("id", match["id"]).execute()
            problem_id = match["id"]
        else:
            new_problem = (
                supabase.table("problems")
                .insert(
                    {
                        "business_id": business_id,
                        "category": analysis["problem_category"],
                        "label": analysis["problem_label"],
                        "affected_reviews_count": 1,
                        "priority": analysis["severity"],
                    }
                )
                .execute()
                .data[0]
            )
            problem_id = new_problem["id"]
            open_problems.append(new_problem)  # para que agrupe con esta en el mismo run

        supabase.table("review_problems").insert(
            {"review_id": review_row["id"], "problem_id": problem_id}
        ).execute()

        # 4. Crear (o actualizar) la tarea asociada
        existing_task = (
            supabase.table("tasks")
            .select("*")
            .eq("problem_id", problem_id)
            .neq("status", "solucionado")
            .execute()
            .data
        )

        if not existing_task:
            supabase.table("tasks").insert(
                {
                    "business_id": business_id,
                    "problem_id": problem_id,
                    "title": analysis["task_title"],
                    "priority": analysis["severity"],
                    "suggested_solution": analysis["suggested_solution"],
                }
            ).execute()

    supabase.table("businesses").update({"last_checked_at": "now()"}).eq(
        "id", business_id
    ).execute()


def archive_old_reviews():
    """Archiva reseñas de más de 1 año y las tareas asociadas."""
    one_year_ago = (date.today() - timedelta(days=365)).isoformat()

    old_reviews = (
        supabase.table("reviews")
        .select("id")
        .lt("review_date", one_year_ago)
        .eq("is_archived", False)
        .execute()
        .data
    )

    if not old_reviews:
        return

    ids = [r["id"] for r in old_reviews]
    supabase.table("reviews").update({"is_archived": True}).in_("id", ids).execute()
    print(f"\nSe archivaron {len(ids)} reseñas de más de 1 año.")


def main():
    businesses = get_businesses()
    print(f"Negocios a procesar: {len(businesses)}")

    for business in businesses:
        try:
            process_business(business)
        except Exception as e:
            import traceback
            print(f"  ! Error procesando {business['name']}: {e}")
            traceback.print_exc()
            continue

    archive_old_reviews()
    print("\nListo.")


if __name__ == "__main__":
    main()
