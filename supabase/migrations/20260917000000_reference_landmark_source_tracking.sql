-- reference_landmarks에 콘텐츠 출처 추적 컬럼 추가.
-- 국립국어원 오픈API(getCTE01701) 배치 파이프라인에서 저작권(CC BY-SA 2.0) 저작자표시
-- 요구사항을 지키기 위해 각 랜드마크 레코드가 어디서 왔는지 남겨야 한다.
alter table public.reference_landmarks
  add column source_type text not null default 'manual' check (source_type in ('manual', 'kcisa_api')),
  add column source_ref text;

comment on column public.reference_landmarks.source_type is '콘텐츠 출처: manual(자체 촬영) / kcisa_api(국립국어원 오픈API 배치 파이프라인)';
comment on column public.reference_landmarks.source_ref is 'source_type=kcisa_api인 경우 원본 mp4/상세페이지 URL(CC BY-SA 저작자표시용)';
