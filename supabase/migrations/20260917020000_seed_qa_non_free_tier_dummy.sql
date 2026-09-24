-- Postman 회귀 테스트 2번(non-free-tier 카테고리 채점 시도 → 차단 확인) 전용 더미 데이터.
-- 실제 콘텐츠가 아님 — 이름/슬러그에 qa- 접두사를 붙여 구분, reference_landmarks는
-- 만들지 않음(20260908010000의 RLS 체크는 words.category_id -> is_free_tier만 봄).
insert into public.categories (id, name, slug, is_free_tier, sort_order)
values ('11111111-1111-4111-8111-111111111111', 'QA 전용(유료 카테고리 테스트)', 'qa-non-free-tier-test', false, 999);

insert into public.words (id, category_id, term, type, sort_order)
values ('22222222-2222-4222-8222-222222222222', '11111111-1111-4111-8111-111111111111', 'QA 테스트 단어', 'dynamic', 0);
