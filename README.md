# TapReviews — Bot de análisis de reseñas

Sistema que entra al perfil de Google Maps de un negocio, detecta reseñas
nuevas, las analiza con IA y genera tareas automáticamente. Corre solo,
gratis, cada 6 horas.

## Qué hace cada archivo

| Archivo | Qué hace |
|---|---|
| `scraper.py` | Abre un navegador (Playwright) y extrae las reseñas del perfil |
| `analyzer.py` | Le pasa cada reseña nueva a Claude para detectar sentimiento y problemas |
| `main.py` | Orquesta todo: scrapea, compara con lo guardado, analiza lo nuevo, crea tareas |
| `db_schema.sql` | Estructura de la base de datos (negocios, reseñas, problemas, tareas) |
| `.github/workflows/scrape.yml` | El "reloj" que corre todo esto automáticamente cada 6hs, gratis |

## Puesta en marcha (todo gratis)

### 1. Base de datos — Supabase
1. Creá una cuenta gratis en [supabase.com](https://supabase.com).
2. Creá un proyecto nuevo.
3. Andá a **SQL Editor** y pegá el contenido de `db_schema.sql`, ejecutalo.
4. En **Project Settings → API** copiá:
   - `Project URL` → va en `SUPABASE_URL`
   - `service_role key` (no la `anon` pública) → va en `SUPABASE_KEY`

### 2. API de IA — Google Gemini (100% gratis, sin tarjeta)
1. Andá a [aistudio.google.com](https://aistudio.google.com) e iniciá sesión con tu cuenta de Google (la misma que usás para Gmail).
2. Buscá el botón **"Get API key"** / "Obtener clave de API".
3. Generá una clave nueva → va en `GEMINI_API_KEY`.
4. No hace falta cargar tarjeta ni pagar nada: el nivel gratis de Gemini
   permite hasta 1500 análisis por día, de sobra para varios negocios.

### 3. Cargar tus primeros negocios
En Supabase, andá a **Table Editor → businesses** e insertá una fila a mano:
- `name`: nombre del negocio
- `profile_url`: el link del perfil en Google Maps
- `source`: `google_maps`

(Después esto se puede reemplazar por un formulario/frontend donde el
usuario pega el link — hoy se carga a mano para probar rápido.)

### 4. Subir esto a GitHub y activar el cron gratis
1. Creá un repo en GitHub y subí esta carpeta.
2. Andá a **Settings → Secrets and variables → Actions** y cargá 3 secrets:
   - `SUPABASE_URL`
   - `SUPABASE_KEY`
   - `GEMINI_API_KEY`
3. Listo. El workflow en `.github/workflows/scrape.yml` va a correr solo
   cada 6 horas. También podés ir a la pestaña **Actions** del repo y
   correrlo manualmente ("Run workflow") para probarlo ya.

### 5. Probar en tu computadora antes de subirlo (recomendado)
```bash
pip install -r requirements.txt
playwright install chromium
cp .env.example .env
# completá .env con tus datos reales

python scraper.py "https://maps.google.com/?cid=TU_NEGOCIO"   # prueba solo el scraper
python main.py                                                 # corre todo el proceso
```

## Cosas importantes que tenés que saber

- **Los selectores de `scraper.py` pueden dejar de funcionar** en cualquier
  momento porque Google cambia el HTML de Maps seguido. Si un día el bot
  deja de traer reseñas, revisá los comentarios `# SELECTOR` en ese
  archivo — ahí es donde hay que actualizar.
- **El scraping de Google Maps no está permitido por sus Términos de
  Servicio.** Esto es válido como punto de partida técnico para probar
  la idea (MVP), pero si el negocio crece en serio conviene evaluar
  migrar a la Google Business Profile API oficial (requiere que cada
  negocio te autorice el acceso, pero es estable a largo plazo).
- **Costos: $0.** Supabase, GitHub Actions, Playwright y la API de Gemini
  (nivel gratis, hasta 1500 análisis por día) no requieren tarjeta ni pago
  en los volúmenes que vas a usar al principio. Si en el futuro el negocio
  crece mucho y superás ese límite diario, ahí recién se evalúa pasar a
  un plan pago.

## Qué falta para tener el producto completo

Esto es el "motor" (scraping + análisis + tareas). Todavía falta:
- El frontend (panel con diseño estilo Apple, formulario para pegar el link).
- Notificaciones (email/push) cuando aparece una reseña nueva o baja el puntaje.
- Login de usuarios y planes de suscripción.

Si querés, el siguiente paso natural es el panel web donde el dueño ve
las tareas y reseñas — avisame y lo armamos.
