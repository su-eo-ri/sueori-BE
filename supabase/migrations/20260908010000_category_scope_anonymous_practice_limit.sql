-- PRD §5.1: 비로그인 사용자는 "기초 카테고리"에서만, 총 3회까지 채점 시도 가능하고
-- 다른 카테고리는 채점(insert) 자체가 비활성화돼야 한다. 앞선 마이그레이션
-- (20260908000000)은 카테고리 구분 없이 전체 COUNT로만 3회를 제한했는데, 이러면
-- REST 직접 호출로 다른 카테고리에서도 3회를 소진할 수 있어 PRD와 어긋난다.
--
-- categories에 아직 시드 데이터가 없어 "기초 카테고리"가 어떤 행인지 지금은 정할 수
-- 없으므로, 우선 플래그 컬럼만 추가해둔다. 실제 값(어느 카테고리를 true로 할지)은
-- 콘텐츠 시딩 시점에 채워야 한다.
alter table public.categories
  add column is_free_tier boolean not null default false;

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
        and (select count(*) from public.practice_sessions where user_id = (select auth.uid())) < 3
      )
    )
  );
