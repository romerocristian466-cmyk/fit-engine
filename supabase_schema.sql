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


-- ─────────────────────────────────────────────────────────────────────────────
-- 4) LÍMITE DIARIO DE USO DE LA IA (Fase 3B)
-- ─────────────────────────────────────────────────────────────────────────────
-- El usuario NO puede escribir en esta tabla (solo leerla). Solo se cuenta a través
-- de la función consumir_cuota, que es atómica y usa la fecha de El Salvador.
-- Para cambiar los límites, edita los números de la función y vuelve a ejecutar.
create table if not exists public.uso_ia (
    user_id  uuid    not null default auth.uid() references auth.users(id) on delete cascade,
    fecha    date    not null,
    tipo     text    not null check (tipo in ('chat', 'foto')),
    usos     integer not null default 0 check (usos >= 0),
    primary key (user_id, fecha, tipo)
);

alter table public.uso_ia enable row level security;

drop policy if exists "uso_ia: solo lectura del dueño" on public.uso_ia;
create policy "uso_ia: solo lectura del dueño" on public.uso_ia
    for select to authenticated
    using ((select auth.uid()) = user_id);

revoke all on public.uso_ia from anon, authenticated;
grant select on public.uso_ia to authenticated;

create or replace function public.consumir_cuota(p_tipo text)
returns table (permitido boolean, usados integer, limite integer)
language plpgsql
security definer
set search_path = ''
as $$
declare
    v_uid    uuid := auth.uid();
    v_hoy    date := (now() at time zone 'America/El_Salvador')::date;
    v_limite integer;
    v_usos   integer;
begin
    if v_uid is null then
        raise exception 'Se requiere sesión';
    end if;

    v_limite := case p_tipo
        when 'chat' then 30   -- mensajes al coach por día
        when 'foto' then 5    -- fotos analizadas por día
        else null
    end;
    if v_limite is null then
        raise exception 'Tipo de uso inválido';
    end if;

    insert into public.uso_ia as u (user_id, fecha, tipo, usos)
    values (v_uid, v_hoy, p_tipo, 1)
    on conflict (user_id, fecha, tipo)
    do update set usos = u.usos + 1
        where u.usos < v_limite
    returning u.usos into v_usos;

    if found then
        return query select true, v_usos, v_limite;
    else
        select u.usos into v_usos
          from public.uso_ia u
         where u.user_id = v_uid and u.fecha = v_hoy and u.tipo = p_tipo;
        return query select false, coalesce(v_usos, v_limite), v_limite;
    end if;
end;
$$;

revoke all on function public.consumir_cuota(text) from public, anon;
grant execute on function public.consumir_cuota(text) to authenticated;
