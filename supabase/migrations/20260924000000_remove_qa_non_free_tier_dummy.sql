-- QA용 더미 카테고리(20260917020000)가 운영 홈 화면에 노출되지 않도록 배포 전 제거.
-- practice_sessions.word_id가 on delete restrict라 먼저 지우고, 나머지는 cascade로 정리된다.
delete from public.practice_sessions
where word_id in (
  select id from public.words
  where category_id = '11111111-1111-4111-8111-111111111111'
);

delete from public.categories
where id = '11111111-1111-4111-8111-111111111111';
