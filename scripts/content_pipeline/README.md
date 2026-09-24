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
- **이 PC에서는 WSL로 실행**: Windows Smart App Control이 mediapipe 네이티브 DLL을 막아서,
  `wsl -d Ubuntu`에서 `.venv-linux/bin/python ...`으로 실행한다(모델·캐시 영상은 `/mnt/c`로 공유).

## 기준 동작 정제 (동적 단어, 2026-09-25)

`extract_landmarks.py` 결과를 그대로 기준으로 쓰면, 기준 frames를 재생해도 FE 채점(DTW,
decay 6.5)이 통과선 80 아래(가족 7단어 45~69점)로 나왔다. 동적 단어는 시딩 전에 정제한다.

```
# (WSL) 1. 캐시 영상에서 tMs 포함 재추출 + 정제 → refined_landmarks.json, 마이그레이션 SQL
.venv-linux/bin/python refine_landmarks.py
# 2. 정제 전/후 교차 점수표 (PR 본문에 첨부)
.venv-linux/bin/python compare_scores.py
```

- `scoring_port.py`: FE 채점기(`sueori-MVP-FE` `packages/scoring_poc/lib/src/` normalize /
  landmark_distance / dtw_scorer)와 FE 교차표 계산 규칙의 Python 이식본.
  **FE 채점 로직이 바뀌면 이 파일도 같이 맞춰야 한다.** 현재 기준은 FE PR #12(2026-09-24 머지)다.
  - 정규화: 손목(0) 원점, 스케일 = 손바닥 5점(0,5,9,13,17) 쌍별 3D 거리 최댓값
  - 녹화 길이: 기준 frames에 `tMs`가 있으면 (마지막 − 첫 tMs) × 1.2를 반올림해 2000~8000ms, 없으면 3000ms
  - 재생: t = 0, 33, 66 … < 녹화 길이에서, 첫 프레임 기준 상대 `tMs` ≤ t인 마지막 프레임
    (동작이 끝나면 마지막 자세 유지, `tMs`가 없으면 i×1000/30ms로 간주)
  - 정지: 기준 frames[0] / frames[len/2]를 floor(녹화 길이 / 33)장 반복
  - 교차표 행 = 기준(녹화 길이도 행 단어로 정함), 열 = 각 단어 재생 + 정지 2종
  - 검증: FE PR #12 본문의 정제본 교차표 63칸과 전부 일치. PR #12 이전 규칙(손목~MCP9 스케일,
    100ms 30프레임 균등 리샘플)으로는 FE 정제 전 교차표 49칸과 일치했다.
- **tMs**: 각 프레임에 원본 영상 기준 시각(ms)을 넣는다. 손이 안 잡힌 프레임은 건너뛰므로
  이 값이 있어야 시간 간격이 보존된다. FE는 녹화 길이를 맞출 때 쓴다(무시해도 호환).

### 정제 단계 (`refine_landmarks.PARAMS`)
1. **다수 handedness가 아닌 프레임 제거** — `num_hands=1`이라 양손 수어에서 잡히는 손이 바뀌는 프레임.
2. **가장자리 자르기(`edge_motion` 0.15)** — 앞뒤에서 직전 프레임 대비 이동량(손목 원점 +
   손목~중지 MCP 거리로 정규화, 관절 평균 거리)이 0.15를 넘는 동안 잘라낸다. 손이 수어
   위치로 올라오고 내려가는 구간이다.
3. **선형 보간** — 1에서 빠진 안쪽 프레임은 원래 `tMs` 위치에 raw 좌표로 선형 보간해 채우고
   `"interpolated": true`를 표시한다.
4. **이동평균(`smooth` ±2프레임)** — raw 좌표에 적용.

좌표는 raw(0~1 이미지 좌표) 그대로라 FE 계약(`frames = [{landmarks:[{x,y,z}×21], handedness}]`,
`frames[0]`은 고스트 오버레이)을 유지한다. 가장자리를 자르므로 `frames[0]`은 수어 시작 자세다.

### 시도했다가 기각한 방법
- **이웃 중앙값 이상치 제거**(±2프레임 중앙값 대비 편차 0.15~0.35 초과 프레임 제거 후 보간):
  자기 재생은 89~100이 됐지만 **정지 자세도 92~100으로 통과**했다. 튀는 프레임 대부분이
  노이즈가 아니라 실제 동작이라, 지우면 동작이 사라지고 판별력이 무너진다.
- **손 크기 필터**(손목~MCP9 거리가 중앙값의 60% 미만인 프레임 제거): 효과가 거의 없었다.

튀는 프레임의 원인: 손을 돌리거나 손등이 카메라를 향할 때 손목~중지 MCP 거리가 평소의
40~50%로 짧아지고, 정규화가 이 거리로 나누면서 실제 움직임이 크게 부풀려진다(손목의 화면
위치 점프는 작아서 다른 손으로 건너뛴 경우는 아님). 60fps 영상 3단어(동생·남동생·누나)는
이 때문에 정제 후에도 60점대였고(PR #12 이전 채점식), FE 채점 개선으로 풀었다. FE PR #12
(손바닥 5점 스케일, 캡처 33ms, 녹화 길이 = 기준 tMs 길이 × 1.2) 이후 정제본 기준 결과:
자기 재생 형 100 / 누나 89 / 남동생 87 / 동생 82 / 할머니 100 / 딸 100 / 남편 100, 다른 단어
최대 24, 정지 최대 76(형 정지(중간), 최소 움직임 게이트 기준값). 가장 큰 원인은 100ms 캡처 간격이었다.

### 검증 기준
정제 후 교차표에서 ① 자기 재생 ≥ 80 ② 다른 단어 재생 < 80 ③ 정지 자세(기준 첫 프레임 /
가운데 프레임 반복) < 80. ②③이 깨지면 정제가 과한 것이다.

### 반영 방식
원본 행은 그대로 두고 `model_version = <원본>-refined-v1`, 고정 `captured_at`으로 새 행을
추가한다. FE는 `word_id`별 `captured_at`이 가장 최신인 행 1개를 읽으므로 FE 변경 없이 적용된다.
롤백: `delete from public.reference_landmarks where model_version like '%-refined-v1';`
