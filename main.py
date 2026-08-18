-- ============================================================
-- Disparo automático: cuando se agrega un negocio nuevo, la base
-- de datos le avisa a GitHub que lo lea YA, sin esperar la próxima
-- corrida programada (hasta 1 hora).
--
-- ANTES DE CORRER ESTO: necesitás un "Personal Access Token" de
-- GitHub con permiso de "Actions: Read and write" sobre el repo
-- ReviewsGoogleAutomization. Ver instrucciones en el chat.
-- ============================================================

-- 1. Activamos la extensión que permite a Postgres hacer pedidos
--    HTTP hacia afuera (para poder "avisarle" a GitHub).
create extension if not exists pg_net with schema extensions;

-- 2. Guardamos tu token de GitHub de forma encriptada. Reemplazá
--    'PEGAR_TU_TOKEN_DE_GITHUB_ACA' por el token real ANTES de
--    correr esto. Esto solo se corre UNA VEZ.
select vault.create_secret(
  'PEGAR_TU_TOKEN_DE_GITHUB_ACA',
  'github_pat',
  'Token para disparar el workflow de GitHub Actions'
);

-- 3. Función que llama a la API de GitHub para "despertar" al bot.
create or replace function public.trigger_scrape_workflow()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
  gh_token text;
begin
  select decrypted_secret into gh_token
  from vault.decrypted_secrets
  where name = 'github_pat'
  limit 1;

  perform net.http_post(
    url := 'https://api.github.com/repos/Raflooo/ReviewsGoogleAutomization/actions/workflows/scrape.yml/dispatches',
    headers := jsonb_build_object(
      'Authorization', 'Bearer ' || gh_token,
      'Accept', 'application/vnd.github+json',
      'Content-Type', 'application/json'
    ),
    body := jsonb_build_object('ref', 'main')
  );

  return new;
end;
$$;

-- 4. El "gatillo": cada vez que se inserta una fila nueva en
--    "businesses", se ejecuta la función de arriba automáticamente.
drop trigger if exists on_business_added on businesses;
create trigger on_business_added
  after insert on businesses
  for each row
  execute function trigger_scrape_workflow();

-- ============================================================
-- Listo. De acá en más, cada vez que un cliente agregue un negocio
-- desde el panel, GitHub va a arrancar a leerlo en segundos (no en
-- hasta 1 hora). El token queda guardado encriptado adentro de
-- Supabase — nunca se expone en el panel.html ni es visible para
-- los clientes.
-- ============================================================
