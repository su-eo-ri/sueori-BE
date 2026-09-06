-- anon/authenticated 롤에 public 스키마 테이블 GRANT가 누락되어 RLS 정책 평가 이전 단계인
-- 42501 permission denied가 발생함(FE PoC에서 발견, 2026-09-06). RLS 정책만으로는 부족하고
-- 테이블 자체에 대한 GRANT가 별도로 필요하다.
grant usage on schema public to anon, authenticated;

grant select on public.categories, public.words, public.reference_landmarks
  to anon, authenticated;

grant select, insert, update, delete on public.practice_sessions, public.favorites
  to authenticated;
