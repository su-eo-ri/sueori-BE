"""
sueori 콘텐츠 배치 파이프라인 — Step 1.5: 동적 단어 기준 동작 정제

extract_landmarks.py 결과에는 손이 수어 위치로 들어오고 나가는 구간과 가끔 뒤집히는
handedness가 섞여 있어서, 기준 frames를 그대로 재생해도 FE 채점(DTW)이 통과선(80)
아래로 나온다. 이 스크립트는
  1) 캐시된 원본 영상에서 같은 설정으로 다시 추출해 프레임별 tMs(원본 영상 기준 시각)를 얻고
  2) 안전한 범위에서만 정제해 refined_landmarks.json과 마이그레이션 SQL을 만든다.
정제 기준, 기각한 방법, 검증 결과는 README.md "기준 동작 정제" 절 참고.

실행(WSL, README 참고): .venv-linux/bin/python refine_landmarks.py
"""
import json
import re
import uuid
from pathlib import Path

import numpy as np

from extract_landmarks import CACHE_DIR, MODEL_VERSION, WORDS, extract_landmarks, force_https
from scoring_port import normalize, to_array

HERE = Path(__file__).parent
TMS_PATH = HERE / "extracted_landmarks_tms.json"
REFINED_PATH = HERE / "refined_landmarks.json"
SEED_MIGRATION = HERE / "../../supabase/migrations/20260917010000_seed_family_category_kcisa.sql"
OUT_MIGRATION = HERE / "../../supabase/migrations/20260925000000_refine_family_reference_landmarks.sql"

REFINED_SUFFIX = "-refined-v1"
# 원본(09-17 시딩)보다 확실히 뒤인 고정 시각. now()를 쓰면 재실행 결과가 달라진다.
REFINED_CAPTURED_AT = "2026-09-25 00:00:00+00"

PARAMS = {
    "edge_motion": 0.15,  # 앞뒤 가장자리에서 직전 대비 이동량이 이 값을 넘는 프레임은 잘라냄
    "smooth": 2,  # 이동평균 반경(프레임). ±2 = 30fps에서 ±67ms, 60fps에서 ±33ms
}


def extract_all_with_tms() -> dict:
    """캐시된 영상에서 tMs 포함 재추출. 결과는 TMS_PATH에 캐시한다."""
    if TMS_PATH.exists():
        return json.loads(TMS_PATH.read_text(encoding="utf-8"))
    import cv2

    out = {}
    for w in WORDS:
        video = CACHE_DIR / f"{w['term'].split(',')[0]}.mp4"
        cap = cv2.VideoCapture(str(video))
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        cap.release()
        out[w["term"]] = {"fps": fps, "videoFrames": n, "durationMs": round(n / fps * 1000), "frames": extract_landmarks(video)}
        print(f"[{w['term']}] {len(out[w['term']]['frames'])} frames, video {n} frames @ {fps:.2f}fps")
    TMS_PATH.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    return out


def motion(arr: np.ndarray) -> np.ndarray:
    """정규화 좌표에서 직전 프레임 대비 관절 평균 이동량. 길이 N-1."""
    nz = normalize(arr)
    return np.linalg.norm(nz[1:] - nz[:-1], axis=2).mean(axis=1)


def refine(frames: list[dict], params: dict = PARAMS) -> tuple[list[dict], dict]:
    """정제한 frames와 단계별 통계를 돌려준다.

    1) 다수 handedness가 아닌 프레임 제거 2) 가장자리(손이 들어오고 나가는 구간) 자르기
    3) 안쪽에서 빠진 프레임은 원래 tMs 위치에 선형 보간 4) 이동평균.
    raw 좌표(0~1 이미지 좌표) 계약은 유지하고, 보간·스무딩도 raw 좌표에서 한다.
    """
    p = {**PARAMS, **params}
    arr = to_array(frames)
    t = np.array([f["tMs"] for f in frames], dtype=float)
    hands = [f["handedness"] for f in frames]
    majority = max(set(hands), key=hands.count)
    keep = np.array([h == majority for h in hands])
    stats = {"input": len(frames), "handedness": majority, "drop_handedness": int((~keep).sum())}

    idx = np.flatnonzero(keep)
    kept_motion = motion(arr[idx])
    lo, hi = 0, len(idx)
    while lo < hi - 1 and kept_motion[lo] > p["edge_motion"]:
        lo += 1
    while hi - 1 > lo and kept_motion[hi - 2] > p["edge_motion"]:
        hi -= 1
    stats["trim_head"], stats["trim_tail"] = lo, len(idx) - hi
    idx = idx[lo:hi]

    span = np.arange(idx[0], idx[-1] + 1)
    out_arr = np.empty((len(span), 21, 3))
    for c in range(21):
        for d in range(3):
            out_arr[:, c, d] = np.interp(t[span], t[idx], arr[idx, c, d])
    interpolated = ~np.isin(span, idx)
    stats["interpolated"] = int(interpolated.sum())

    if p["smooth"] > 0:
        r = p["smooth"]
        padded = np.concatenate([out_arr[:1].repeat(r, 0), out_arr, out_arr[-1:].repeat(r, 0)])
        out_arr = np.stack([padded[i : i + 2 * r + 1].mean(axis=0) for i in range(len(out_arr))])

    out = []
    for k, i in enumerate(span):
        frame = {
            "landmarks": [{"x": float(x), "y": float(y), "z": float(z)} for x, y, z in out_arr[k]],
            "handedness": majority,
            "tMs": int(t[i]),
        }
        if interpolated[k]:
            frame["interpolated"] = True
        out.append(frame)
    stats["output"] = len(out)
    stats["durationMs"] = int(t[span[-1]] - t[span[0]])
    return out, stats


def seeded_word_ids() -> dict[str, str]:
    """09-17 시딩 마이그레이션에서 term → word id."""
    sql = SEED_MIGRATION.read_text(encoding="utf-8")
    return {m.group(2): m.group(1) for m in re.finditer(r"insert into public\.words \(id, category_id, term.*?values \('([0-9a-f-]+)', '[0-9a-f-]+', '([^']+)'", sql)}


def sql_str(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"


def main():
    data = extract_all_with_tms()
    word_ids = seeded_word_ids()
    refined, lines = {}, [
        "-- 가족 7단어 기준 동작 정제본(refined-v1) 추가. 원본 행은 그대로 두고 새 행을 넣는다.",
        "-- FE는 word_id별 captured_at이 가장 최신인 행 1개를 읽으므로, 고정 captured_at으로 정제본이 선택된다.",
        "-- 생성: scripts/content_pipeline/refine_landmarks.py (정제 기준은 같은 폴더 README.md 참고)",
        f"-- 롤백: delete from public.reference_landmarks where model_version like '%{REFINED_SUFFIX}';",
        "",
    ]
    for w in WORDS:
        term = w["term"]
        frames, stats = refine(data[term]["frames"])
        word_id = word_ids[term]
        refined[word_id] = {"term": term, "fps": round(data[term]["fps"], 2), "sourceDurationMs": data[term]["durationMs"], **stats, "frames": frames}
        ref_id = uuid.uuid5(uuid.NAMESPACE_URL, f"sueori/reference_landmarks/{word_id}{REFINED_SUFFIX}")
        frames_json = json.dumps(frames, ensure_ascii=False, separators=(",", ":"))
        lines.append(
            "insert into public.reference_landmarks (id, word_id, frames, model_version, source_type, source_ref, captured_at) values "
            f"({sql_str(str(ref_id))}, {sql_str(word_id)}, {sql_str(frames_json)}::jsonb, {sql_str(MODEL_VERSION + REFINED_SUFFIX)}, "
            f"'kcisa_api', {sql_str(force_https(w['mp4']))}, {sql_str(REFINED_CAPTURED_AT)});"
        )
        print(f"[{term}] {stats}")
    REFINED_PATH.write_text(json.dumps(refined, ensure_ascii=False), encoding="utf-8")
    OUT_MIGRATION.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {REFINED_PATH.name} and {OUT_MIGRATION.name}")


if __name__ == "__main__":
    main()
