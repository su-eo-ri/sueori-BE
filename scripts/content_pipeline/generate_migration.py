import json
import uuid

data = json.load(open("extracted_landmarks.json", encoding="utf-8"))

WORD_ORDER = ["형,형님", "누나,누님", "남동생", "동생", "할머니,조모", "딸,여식", "남편,배우자,서방"]

def sql_str(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"

def sql_json(obj) -> str:
    return "'" + json.dumps(obj, ensure_ascii=False).replace("'", "''") + "'::jsonb"

category_id = str(uuid.uuid4())
lines = []
lines.append("-- 국립국어원 \"일상생활수어\" 오픈API(getCTE01701) 배치 파이프라인 1차 시딩: \"가족\" 카테고리.")
lines.append("-- 비로그인 3회 체험 대상(기초) 카테고리로 is_free_tier=true 명시 세팅함 — 빠뜨리면")
lines.append("-- 게스트 채점이 전면 차단되는 회귀가 생김(PR #2 / PRD 시딩 체크리스트 참고).")
lines.append("-- 라이선스: CC BY-SA 2.0(저작자표시 필요) — reference_landmarks.source_type='kcisa_api',")
lines.append("-- source_ref에 원본 mp4 URL 기록. modelVersion으로 재추출 필요 시점 추적.")
lines.append("")
lines.append(
    f"insert into public.categories (id, name, slug, is_free_tier, sort_order) values "
    f"({sql_str(category_id)}, {sql_str('가족')}, {sql_str('family')}, true, 0);"
)
lines.append("")

for i, term in enumerate(WORD_ORDER):
    d = data[term]
    word_id = str(uuid.uuid4())
    ref_id = str(uuid.uuid4())
    frames = d["frames"]
    lines.append(
        f"insert into public.words (id, category_id, term, type, thumbnail_asset, sort_order) values "
        f"({sql_str(word_id)}, {sql_str(category_id)}, {sql_str(term)}, 'dynamic', {sql_str(d['thumb'])}, {i});"
    )
    lines.append(
        f"insert into public.reference_landmarks (id, word_id, frames, model_version, source_type, source_ref) values "
        f"({sql_str(ref_id)}, {sql_str(word_id)}, {sql_json(frames)}, "
        f"{sql_str('kcisa-batch-v1_mediapipe-hand_landmarker-float16-1')}, 'kcisa_api', {sql_str(d['source_ref'])});"
    )
    lines.append("")

out = "\n".join(lines)
with open("../../supabase/migrations/20260917010000_seed_family_category_kcisa.sql", "w", encoding="utf-8") as f:
    f.write(out)
print("wrote migration,", len(out), "bytes")
print("category_id:", category_id)
