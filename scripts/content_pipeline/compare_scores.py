"""
정제 전/후 교차 점수표(FE 채점 이식본 기준). refine_landmarks.py를 먼저 실행해야 한다.
행 = 기준, 열 = 각 단어 재생 + 정지(기준 frames[0] / frames[len/2]).
녹화 길이·재생·정지 규칙은 scoring_port.cross_table 참고(FE와 같음).
"""
import json
from pathlib import Path

from scoring_port import cross_table, format_table

HERE = Path(__file__).parent
ORDER = ["형,형님", "누나,누님", "남동생", "동생", "할머니,조모", "딸,여식", "남편,배우자,서방"]


def report(label: str, words: dict) -> list[list[float]]:
    names, rows = cross_table(words)
    n = len(names)
    print(f"\n### {label}\n")
    print(format_table(names, rows))
    off = max(rows[i][j] for i in range(n) for j in range(n) if i != j)
    still = max(v for r in rows for v in r[n:])
    print(f"\n자기 재생 최소 {min(rows[i][i] for i in range(n)):.0f} · 다른 단어 최대 {off:.0f} · 정지 최대 {still:.0f}")
    return rows


if __name__ == "__main__":
    extracted = json.loads((HERE / "extracted_landmarks_tms.json").read_text(encoding="utf-8"))
    after = {v["term"]: v for v in json.loads((HERE / "refined_landmarks.json").read_text(encoding="utf-8")).values()}
    # 정제 전 운영 frames에는 tMs가 없으므로 빼고 계산한다(FE도 tMs 없으면 녹화 3초, i*1000/30 재생).
    before = {t: [{k: v for k, v in f.items() if k != "tMs"} for f in extracted[t]["frames"]] for t in ORDER}
    report("정제 전", before)
    report("정제 후 (refined-v1)", {t: after[t]["frames"] for t in ORDER})
