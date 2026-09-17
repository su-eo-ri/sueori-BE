# 콘텐츠 배치 파이프라인 (국립국어원 오픈API → Supabase)

PRD §7 확정 사항: 클라이언트/서버가 런타임에 국립국어원 API를 호출하지 않는다.
이 폴더는 **로컬에서 1회성(또는 필요 시 재실행)으로 돌리는 Python 배치 스크립트**로,
API에서 영상을 받아 MediaPipe로 손 랜드마크를 추출한 뒤 Supabase 마이그레이션 SQL을
생성한다.

## 실행 순서

```
python -m venv .venv
./.venv/Scripts/pip install mediapipe opencv-python requests supabase python-dotenv
curl -sL -o hand_landmarker.task https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task

# 1. (선택) 새 카테고리/단어 후보를 찾을 때 — API에서 넓게 훑어서 all_items.json 생성
./.venv/Scripts/python fetch_all.py

# 2. extract_landmarks.py 상단 WORDS 리스트를 원하는 단어들로 채움
#    (title/mp4/thumb는 all_items.json에서 찾아서 채워 넣기)

# 3. 실제 다운로드 + MediaPipe 추출 → extracted_landmarks.json
./.venv/Scripts/python extract_landmarks.py

# 4. extracted_landmarks.json → supabase/migrations/<timestamp>_seed_*.sql 생성
./.venv/Scripts/python generate_migration.py

# 5. 생성된 마이그레이션 검토 후 원격 반영 (사용자 승인 필요한 단계)
cd ../.. && npx supabase db push --project-ref kdtnjlvojaipppnxpnwt
```

## 설계 노트

- **`http://` → `https://` 강제 치환 필수**: 미디어 호스트(`sldict.korean.go.kr`)가
  `http://`로는 타임아웃남(2026-09-17 FE PoC에서 발견). `extract_landmarks.py`의
  `force_https()`가 모든 mp4/썸네일 URL에 적용함.
- **좌표계**: `frames`에는 MediaPipe raw 출력(x,y는 0~1 이미지 정규화 좌표, z는 손목
  기준 상대 깊이)을 그대로 저장한다. 손목 원점 이동 + 스케일 정규화는 채점 시점에
  클라이언트가 `scoring_poc/lib/src/normalize.dart`와 동일한 함수로 적용 — 정규화
  알고리즘이 바뀌어도 raw 데이터는 재사용 가능하게 하기 위함.
- **Word.type**: 이 데이터셋("일상생활수어")은 전부 완성된 수어 단어/표현 영상이라
  지문자(글자)가 아님 — 전부 `'dynamic'`으로 시딩한다. 정적(`'static'`, 지문자) 콘텐츠가
  필요해지면 별도 소스/스크립트 필요.
- **`is_free_tier`**: 기초 카테고리(비로그인 3회 체험 대상)에는 반드시 명시적으로
  `true`를 세팅할 것 — 빠뜨리면 시딩 시점부터 게스트 채점이 전면 차단되는 회귀 발생
  (PR #2 참고).
- **라이선스**: CC BY-SA 2.0(저작자표시 필요) — `reference_landmarks.source_type='kcisa_api'`,
  `source_ref`에 원본 mp4 URL을 남겨 추적한다.
- 다운로드한 영상, 추출된 랜드마크 JSON, MediaPipe 모델(`.task`), venv는 전부 `.gitignore`
  대상 — 재현 가능한 스크립트만 커밋하고 산출물(대용량/바이너리)은 커밋하지 않는다.
  실제 시딩 데이터는 생성된 마이그레이션 SQL(`supabase/migrations/`) 쪽에 남는다.
