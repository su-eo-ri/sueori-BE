# sueori BE

수어리 백엔드. Supabase(Postgres) BaaS 기반 — 별도 서버 애플리케이션 코드는 없고, DB 스키마/RLS/Edge Function 위주.

기획/설계 문서는 obsidian 볼트 `02-Backend/`에 있음:
- 진행 상황 / TODO: `수어리 - BE 진행상황.md`
- 데이터 모델: `수어리 - 데이터 모델 (ERD).md`
- 기술 스택 결정: `03-PM-Planning/수어리 - 최종 기술 스택.md`

## 구조
- `supabase/migrations/` — Postgres 스키마 마이그레이션. Supabase CLI로 적용 (`supabase db push` 또는 `supabase migration up`, CLI는 아직 로컬 미설치).

## 스키마 관련 결정 사항
- ERD 문서는 `User`에 `userId`/`deviceId` 이원 nullable 구조를 제안했지만, 실제 스키마는 Supabase Anonymous Auth가 익명 로그인 시점부터 발급하는 `auth.users.id`를 그대로 끝까지 쓰는 방식으로 단순화함 (`linkIdentity`로 계정 연결 시에도 UUID 불변) — 자세한 이유는 첫 마이그레이션 파일 상단 주석 참고.
