-- 비로그인(익명) 사용자의 체험 3회 제한을 서버(RLS)에서 강제한다.
-- 재설계 이후 게스트도 user_id가 항상 채워지므로, 로그인 여부를 구분하는 유일한 신호는
-- JWT의 is_anonymous 클레임뿐이다. 카운팅은 별도 카운터 테이블 없이 practice_sessions를
-- user_id로 COUNT한다. 클라이언트(session.user.isAnonymous)로는 UI 안내만 하고, 실제
-- 차단은 여기서 해야 한다 — REST 직접 호출로 클라이언트 쪽 제한은 우회 가능하기 때문.
--
-- 한계(설계상 불가피, PM/기획 공유 필요): 앱 재설치로 새 익명 UUID가 발급되면 카운트가
-- 다시 0부터 시작한다. 이 마이그레이션으로는 해결되지 않는 문제다.
drop policy "users manage their own practice sessions" on public.practice_sessions;

create policy "users select their own practice sessions" on public.practice_sessions
  for select to authenticated
  using ((select auth.uid()) = user_id);

create policy "users insert their own practice sessions" on public.practice_sessions
  for insert to authenticated
  with check (
    (select auth.uid()) = user_id
    and (
      coalesce(((select auth.jwt()) ->> 'is_anonymous')::boolean, false) = false
      or (select count(*) from public.practice_sessions where user_id = (select auth.uid())) < 3
    )
  );

create policy "users update their own practice sessions" on public.practice_sessions
  for update to authenticated
  using ((select auth.uid()) = user_id)
  with check ((select auth.uid()) = user_id);

create policy "users delete their own practice sessions" on public.practice_sessions
  for delete to authenticated
  using ((select auth.uid()) = user_id);
