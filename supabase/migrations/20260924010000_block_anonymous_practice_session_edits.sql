-- Fixes #10: 게스트(익명)가 본인 practice_sessions를 지우거나 고쳐서 서버 제한을 우회할 수 있었다.
-- - DELETE: insert 정책의 3회 제한은 count_own_practice_sessions()(남아 있는 본인 행 수)로
--   판단하므로, 지우면 카운트가 다시 0이 된다.
-- - UPDATE: 무료 카테고리 단어로 저장한 뒤 word_id를 유료 카테고리 단어로 바꿀 수 있었다.
-- 게스트의 UPDATE/DELETE를 막는다. FE는 practice_sessions에 select/insert만 쓴다.
drop policy "users update their own practice sessions" on public.practice_sessions;
drop policy "users delete their own practice sessions" on public.practice_sessions;

create policy "users update their own practice sessions" on public.practice_sessions
  for update to authenticated
  using (
    (select auth.uid()) = user_id
    and coalesce(((select auth.jwt()) ->> 'is_anonymous')::boolean, false) = false
  )
  with check (
    (select auth.uid()) = user_id
    and coalesce(((select auth.jwt()) ->> 'is_anonymous')::boolean, false) = false
  );

create policy "users delete their own practice sessions" on public.practice_sessions
  for delete to authenticated
  using (
    (select auth.uid()) = user_id
    and coalesce(((select auth.jwt()) ->> 'is_anonymous')::boolean, false) = false
  );
