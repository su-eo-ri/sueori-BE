-- PM 제품 결정(2026-09-19): "지문자" 카테고리도 비로그인 3회 체험 대상에 포함.
-- 근거: 기존 무료체험(가족)은 동적(DTW) 채점만 경험시키는데, 지문자를 포함하면
-- 정적(cosine) 채점도 비로그인 단계에서 경험 가능. 단일 정지자세라 성공 확률이
-- 높아 첫 시도 성공 경험을 주기 좋고, 카메라 채점 가치 검증(P0 가설) 범위도 넓어짐.
update public.categories set is_free_tier = true where slug = 'fingerspelling';
