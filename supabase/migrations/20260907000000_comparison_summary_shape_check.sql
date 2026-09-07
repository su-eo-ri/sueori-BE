-- comparisonSummary 필드 스펙 확정(2026-09-07, ERD 문서 참고)에 따라 최소한의 형태 검증을 추가.
-- 내용물(랜드마크 값 등)은 클라이언트가 계산한 채점 결과를 신뢰하고 그대로 저장하므로 값 자체는
-- 검증하지 않고, 필수 top-level 키 존재만 확인한다.
alter table public.practice_sessions
  add constraint comparison_summary_shape check (
    comparison_summary ? 'version'
    and comparison_summary ? 'algorithm'
    and comparison_summary ? 'landmarkDeltas'
  );
