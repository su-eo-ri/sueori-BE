-- Fixes: 20260908010000's anonymous-practice-limit INSERT policy on
-- practice_sessions includes a WITH CHECK subquery that SELECTs from
-- practice_sessions itself:
--   (select count(*) from public.practice_sessions where user_id = (select auth.uid())) < 3
-- Evaluating that subquery re-triggers RLS on practice_sessions, which
-- re-evaluates the same INSERT policy, causing Postgres to fail every
-- insert with 42P17 "infinite recursion detected in policy for relation
-- practice_sessions" (found 2026-09-21 via regression test execution —
-- every insert had been broken since PR #2 merged on 2026-09-08).
--
-- Fix: move the self-count into a SECURITY DEFINER function. Because the
-- function runs as its owner (the migration role, which owns the table and
-- is therefore exempt from its own RLS), the internal SELECT bypasses RLS
-- entirely instead of re-entering the policy being evaluated.
create or replace function public.count_own_practice_sessions()
returns bigint
language sql
security definer
set search_path = ''
stable
as $$
  select count(*) from public.practice_sessions where user_id = auth.uid();
$$;

revoke all on function public.count_own_practice_sessions() from public;
grant execute on function public.count_own_practice_sessions() to authenticated;

drop policy "users insert their own practice sessions" on public.practice_sessions;

create policy "users insert their own practice sessions" on public.practice_sessions
  for insert to authenticated
  with check (
    (select auth.uid()) = user_id
    and (
      coalesce(((select auth.jwt()) ->> 'is_anonymous')::boolean, false) = false
      or (
        exists (
          select 1
          from public.words w
          join public.categories c on c.id = w.category_id
          where w.id = practice_sessions.word_id
            and c.is_free_tier
        )
        and public.count_own_practice_sessions() < 3
      )
    )
  );
