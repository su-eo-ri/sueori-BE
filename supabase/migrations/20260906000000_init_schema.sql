-- 수어리 초기 스키마
-- 기준 문서: obsidian 02-Backend/수어리 - 데이터 모델 (ERD).md
--
-- ERD 대비 의도적 변경점: User 엔티티를 별도 테이블로 만들지 않고 Supabase Auth의
-- auth.users를 그대로 사용한다. 익명(Anonymous) 로그인 시점에 이미 auth.users에
-- UUID가 생성되고, 이후 linkIdentity로 같은 UUID에 이메일/구글 계정을 연결하는
-- 구조라 deviceId -> userId 병합 로직 자체가 필요 없다 (ERD의 열린 질문 해소).
-- 그래서 practice_sessions / favorites의 userId/deviceId 이원 nullable 컬럼 대신
-- user_id 단일 컬럼(not null, auth.users 참조)만 사용한다.

create extension if not exists pgcrypto;

create table public.categories (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  slug text not null unique,
  pass_threshold int check (pass_threshold between 0 and 100),
  sort_order int not null default 0,
  created_at timestamptz not null default now()
);

create table public.words (
  id uuid primary key default gen_random_uuid(),
  category_id uuid not null references public.categories(id) on delete cascade,
  term text not null,
  type text not null check (type in ('static', 'dynamic')),
  thumbnail_asset text,
  sort_order int not null default 0,
  created_at timestamptz not null default now()
);
create index words_category_id_idx on public.words(category_id);

create table public.reference_landmarks (
  id uuid primary key default gen_random_uuid(),
  word_id uuid not null references public.words(id) on delete cascade,
  frames jsonb not null,
  model_version text not null,
  captured_at timestamptz not null default now()
);
create index reference_landmarks_word_id_idx on public.reference_landmarks(word_id);

create table public.practice_sessions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  word_id uuid not null references public.words(id) on delete restrict,
  score int not null check (score between 0 and 100),
  comparison_summary jsonb not null,
  retry_of_session_id uuid references public.practice_sessions(id) on delete set null,
  created_at timestamptz not null default now()
);
create index practice_sessions_user_id_idx on public.practice_sessions(user_id);
create index practice_sessions_word_id_idx on public.practice_sessions(word_id);

create table public.favorites (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  word_id uuid not null references public.words(id) on delete cascade,
  source text not null check (source in ('manual', 'auto_low_score')),
  resolved_at timestamptz,
  added_at timestamptz not null default now(),
  unique (user_id, word_id)
);
create index favorites_user_id_idx on public.favorites(user_id);

-- RLS: categories/words/reference_landmarks는 공개 읽기 전용 콘텐츠.
-- practice_sessions/favorites는 본인 데이터만 접근.
alter table public.categories enable row level security;
alter table public.words enable row level security;
alter table public.reference_landmarks enable row level security;
alter table public.practice_sessions enable row level security;
alter table public.favorites enable row level security;

create policy "categories are publicly readable" on public.categories
  for select using (true);
create policy "words are publicly readable" on public.words
  for select using (true);
create policy "reference landmarks are publicly readable" on public.reference_landmarks
  for select using (true);

create policy "users manage their own practice sessions" on public.practice_sessions
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);
create policy "users manage their own favorites" on public.favorites
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);
