-- =============================================================================
-- Fit Engine — esquema para Supabase (Postgres)
--
-- Cómo usarlo:
--   1. Supabase → SQL Editor → "New query"
--   2. Pega TODO este archivo y pulsa "Run"
--   3. Es seguro correrlo más de una vez (no borra datos).
--
-- Seguridad: cada tabla tiene RLS (seguridad a nivel de fila). La base de datos
-- misma impide que un usuario lea, cree, cambie o borre filas de otro usuario,
-- aunque la app tuviera un error. Los usuarios sin sesión (rol "anon") no tienen
-- ningún acceso a estas tablas.
-- =============================================================================


-- 1) TABLAS -------------------------------------------------------------------

-- Perfil del usuario (nombre y meta de peso). Una fila por usuario.
create table if not exists public.perfil (
    id            bigint generated always as identity primary key,
    user_id       uuid not null unique default auth.uid()
                  references auth.users (id) on delete cascade,
    nombre        text check (nombre is null or char_length(nombre) <= 60),
    meta_peso_kg  real check (meta_peso_kg is null or (meta_peso_kg >= 0 and meta_peso_kg <= 200))
);

-- Actividad diaria. Una fila por usuario y por día.
create table if not exists public.actividad (
    id                  bigint generated always as identity primary key,
    user_id             uuid not null default auth.uid()
                        references auth.users (id) on delete cascade,
    fecha               date not null,
    pasos               integer not null default 0
                        check (pasos between 0 and 200000),
    minutos_ejercicio   integer not null default 0
                        check (minutos_ejercicio between 0 and 1440),
    tipo_ejercicio      text not null default 'Caminata / Cardio'
                        check (char_length(tipo_ejercicio) <= 100),
    lastre_munecas_lb   real not null default 0
                        check (lastre_munecas_lb between 0 and 10),
    lastre_tobillos_lb  real not null default 0
                        check (lastre_tobillos_lb between 0 and 10),
    protocol_rest       boolean not null default false,
    compliance_score    real not null default 0
                        check (compliance_score between 0 and 100),
    notas               text check (notas is null or char_length(notas) <= 2000),
    unique (user_id, fecha)
);

-- Peso corporal. Una fila por usuario y por día.
create table if not exists public.peso (
    id       bigint generated always as identity primary key,
    user_id  uuid not null default auth.uid()
             references auth.users (id) on delete cascade,
    fecha    date not null,
    peso_kg  real not null check (peso_kg between 30 and 200),
    unique (user_id, fecha)
);


-- 2) SEGURIDAD POR FILA (RLS) ---------------------------------------------------

alter table public.perfil    enable row level security;
alter table public.actividad enable row level security;
alter table public.peso      enable row level security;

drop policy if exists "perfil: solo el dueño" on public.perfil;
create policy "perfil: solo el dueño" on public.perfil
    for all to authenticated
    using      ((select auth.uid()) = user_id)
    with check ((select auth.uid()) = user_id);

drop policy if exists "actividad: solo el dueño" on public.actividad;
create policy "actividad: solo el dueño" on public.actividad
    for all to authenticated
    using      ((select auth.uid()) = user_id)
    with check ((select auth.uid()) = user_id);

drop policy if exists "peso: solo el dueño" on public.peso;
create policy "peso: solo el dueño" on public.peso
    for all to authenticated
    using      ((select auth.uid()) = user_id)
    with check ((select auth.uid()) = user_id);


-- 3) PERMISOS -------------------------------------------------------------------
-- Sin sesión (anon): nada. Con sesión (authenticated): lo básico, y RLS filtra por dueño.

revoke all on public.perfil, public.actividad, public.peso from anon;
grant select, insert, update, delete
    on public.perfil, public.actividad, public.peso
    to authenticated;
