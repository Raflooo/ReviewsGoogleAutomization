-- ============================================================
-- Esquema de base de datos - TapReviews
-- Pensado para Supabase (PostgreSQL). Correr esto en el SQL
-- Editor de tu proyecto de Supabase antes de correr los scripts.
-- ============================================================

create extension if not exists "pgcrypto";

-- Negocios que estamos monitoreando
create table if not exists businesses (
    id uuid primary key default gen_random_uuid(),
    name text not null,
    profile_url text not null unique,        -- link de Google Maps / Yelp
    source text not null default 'google_maps', -- google_maps | yelp | tripadvisor
    owner_email text,
    created_at timestamptz not null default now(),
    last_checked_at timestamptz
);

-- Cada reseña individual detectada
create table if not exists reviews (
    id uuid primary key default gen_random_uuid(),
    business_id uuid not null references businesses(id) on delete cascade,
    external_review_hash text not null,      -- hash de autor+fecha+texto (dedupe)
    author text,
    rating int,                               -- 1 a 5
    review_text text,
    review_date date,
    sentiment text,                           -- positivo | neutral | negativo
    is_archived boolean not null default false, -- true si tiene más de 1 año
    scraped_at timestamptz not null default now(),
    unique (business_id, external_review_hash)
);

-- Problemas detectados y agrupados por la IA (ej: "Iluminación")
create table if not exists problems (
    id uuid primary key default gen_random_uuid(),
    business_id uuid not null references businesses(id) on delete cascade,
    category text not null,                   -- instalaciones | atencion | producto | servicio | ambiente
    label text not null,                      -- ej: "Iluminación", "Tiempo de espera"
    affected_reviews_count int not null default 1,
    priority text not null default 'media',   -- alta | media | baja
    status text not null default 'pendiente', -- pendiente | en_progreso | solucionado | archivado
    first_seen_at timestamptz not null default now(),
    last_seen_at timestamptz not null default now()
);

-- Relación reseña <-> problema (una reseña puede tocar varios problemas)
create table if not exists review_problems (
    review_id uuid not null references reviews(id) on delete cascade,
    problem_id uuid not null references problems(id) on delete cascade,
    primary key (review_id, problem_id)
);

-- Tareas generadas a partir de los problemas
create table if not exists tasks (
    id uuid primary key default gen_random_uuid(),
    business_id uuid not null references businesses(id) on delete cascade,
    problem_id uuid references problems(id) on delete set null,
    title text not null,
    description text,
    priority text not null default 'media',
    status text not null default 'pendiente', -- pendiente | en_progreso | solucionado | archivado
    suggested_solution text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists idx_reviews_business on reviews(business_id);
create index if not exists idx_problems_business on problems(business_id);
create index if not exists idx_tasks_business on tasks(business_id);
