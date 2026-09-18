import json
import uuid

data = json.load(open("extracted_landmarks_jamo.json", encoding="utf-8"))
picks = json.load(open("jamo_picks.json", encoding="utf-8"))
WORD_ORDER = [p["term"] for p in picks]

MODEL_VERSION = "kcisa-batch-v1_mediapipe-hand_landmarker-float16-1"


def sql_str(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"


def sql_json(obj) -> str:
    return "'" + json.dumps(obj, ensure_ascii=False).replace("'", "''") + "'::jsonb"


category_id = str(uuid.uuid4())
lines = []
lines.append("-- 국립국어원 \"일상생활수어\" 오픈API(getCTE01701) 시딩: \"지문자\" 카테고리(정적 채점 경로).")
lines.append("-- 2026-09-19 전체 3,754건 재확인 결과, 한글 자모 40개(자음19+모음21) 전부가 정지 손모양")
lines.append("-- 묘사(signDescription에 동작 서술 없음)로 개별 존재함을 확인 — 9/17 \"지문자 콘텐츠 없을 수도\"")
lines.append("-- 리스크를 기각시킨 근거(PRD §7). ReferenceLandmark.frames는 ERD 설계대로 길이 1(대표 프레임)만 저장.")
lines.append("-- is_free_tier=false로 시딩(기초/무료체험 카테고리는 \"가족\" 하나로 유지, 제품 우선순위는 별도 결정 필요).")
lines.append("-- 라이선스: CC BY-SA 2.0(저작자표시 필요) — reference_landmarks.source_type='kcisa_api', source_ref에 원본 mp4 URL 기록.")
lines.append("")
lines.append(
    f"insert into public.categories (id, name, slug, is_free_tier, sort_order) values "
    f"({sql_str(category_id)}, {sql_str('지문자')}, {sql_str('fingerspelling')}, false, 1);"
)
lines.append("")

for i, term in enumerate(WORD_ORDER):
    d = data[term]
    word_id = str(uuid.uuid4())
    ref_id = str(uuid.uuid4())
    frames = d["frames"]
    lines.append(
        f"insert into public.words (id, category_id, term, type, thumbnail_asset, sort_order) values "
        f"({sql_str(word_id)}, {sql_str(category_id)}, {sql_str(term)}, 'static', {sql_str(d['thumb'])}, {i});"
    )
    lines.append(
        f"insert into public.reference_landmarks (id, word_id, frames, model_version, source_type, source_ref) values "
        f"({sql_str(ref_id)}, {sql_str(word_id)}, {sql_json(frames)}, "
        f"{sql_str(MODEL_VERSION)}, 'kcisa_api', {sql_str(d['source_ref'])});"
    )
    lines.append("")

out = "\n".join(lines)
with open("../../supabase/migrations/20260919000000_seed_fingerspelling_category_kcisa.sql", "w", encoding="utf-8") as f:
    f.write(out)
print("wrote migration,", len(out), "bytes")
print("category_id:", category_id)
