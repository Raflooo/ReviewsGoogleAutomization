"""
analyzer.py
-----------
Toma reseñas nuevas (texto crudo) y usa la API GRATUITA de Google Gemini
(a través de Google AI Studio) para:
  1. Clasificar el sentimiento (positivo / neutral / negativo).
  2. Detectar si menciona un problema, y en qué categoría.
  3. Sugerir una tarea concreta + una solución sugerida.

Se usa Gemini en vez de Claude porque tiene un nivel gratis real (sin
tarjeta de crédito, sin vencimiento) usando los modelos "Flash". Alcanza
de sobra para analizar reseñas de unos pocos negocios por día.

Devuelve datos estructurados en JSON, listos para guardar en la base
y agrupar con problemas ya existentes.
"""

import json
import os

import google.generativeai as genai

MODEL = "gemini-2.5-flash"

CATEGORIES = [
    "instalaciones",  # iluminación, limpieza, temperatura, baños, mobiliario
    "atencion",        # mala atención, lentitud, falta de personal
    "producto",        # calidad, precio, tamaño, presentación
    "servicio",        # tiempo de espera, errores, pedidos
    "ambiente",        # música, olores, organización, comodidad
]

SYSTEM_PROMPT = f"""Sos un analista que lee reseñas de clientes de negocios
(restaurantes, locales, etc.) y extrae información estructurada para un
sistema de gestión de tareas.

Para cada reseña que te pasen, respondé ÚNICAMENTE con un objeto JSON
(sin texto adicional, sin markdown) con esta forma exacta:

{{
  "sentiment": "positivo" | "neutral" | "negativo",
  "has_problem": true | false,
  "problem_category": una de {CATEGORIES} o null si no hay problema,
  "problem_label": string corto (2-4 palabras, ej: "Iluminación",
                    "Tiempo de espera") o null,
  "task_title": string corto en imperativo (ej: "Revisar la iluminación")
                 o null si no hay problema,
  "suggested_solution": una sugerencia concreta y accionable, o null,
  "severity": "alta" | "media" | "baja"
}}

Reglas:
- "alta" es para quejas de seguridad, higiene, o reseñas de 1 estrella
  con problema explícito.
- Si la reseña es puramente positiva, "has_problem" debe ser false y el
  resto de los campos de problema deben ser null.
- No inventes información que no esté en el texto de la reseña.
"""


def analyze_review(review_text: str, rating: int | None = None, api_key: str | None = None) -> dict:
    """Analiza una única reseña y devuelve el resultado estructurado."""
    genai.configure(api_key=api_key or os.environ["GEMINI_API_KEY"])
    model = genai.GenerativeModel(MODEL, system_instruction=SYSTEM_PROMPT)

    user_content = f"Puntuación: {rating if rating else 'desconocida'} estrellas\nTexto de la reseña: {review_text}"

    response = model.generate_content(
        user_content,
        generation_config={"max_output_tokens": 500, "response_mime_type": "application/json"},
    )

    raw_text = response.text or ""
    cleaned = raw_text.replace("```json", "").replace("```", "").strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # Si la IA no devolvió JSON limpio, devolvemos un resultado neutro
        # en vez de romper todo el proceso de análisis.
        return {
            "sentiment": "neutral",
            "has_problem": False,
            "problem_category": None,
            "problem_label": None,
            "task_title": None,
            "suggested_solution": None,
            "severity": "baja",
        }


def find_matching_problem(existing_problems: list[dict], category: str, label: str) -> dict | None:
    """
    Busca si ya existe un problema abierto con la misma categoría y una
    etiqueta similar (comparación simple de texto), para agrupar reseñas
    en vez de crear un problema nuevo por cada una.
    """
    label_lower = label.lower().strip()
    for problem in existing_problems:
        if problem["category"] != category:
            continue
        existing_label = problem["label"].lower().strip()
        # Coincidencia simple: mismo texto, o uno contiene al otro
        if existing_label == label_lower or existing_label in label_lower or label_lower in existing_label:
            return problem
    return None


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Uso: python analyzer.py 'texto de la reseña'")
        sys.exit(1)

    result = analyze_review(sys.argv[1])
    print(json.dumps(result, indent=2, ensure_ascii=False))
