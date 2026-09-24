"""
정제 전/후 교차 점수표(FE 채점 이식본 기준). refine_landmarks.py를 먼저 실행해야 한다.
행 = 기준, 열 = 각 단어 재생(30프레임 균등 리샘플) + 정지(기준 frames[0] / frames[len/2] 30번 반복).
"""
import json
from pathlib import Path

from scoring_port import cross_table, format_table, to_array

HERE = Path(__file__).parent
ORDER = ["남편,배우자,서방", "딸,여식", "할머니,조모", "동생", "남동생", "누나,누님", "형,형님"]


def report(label: str, words: dict) -> None:
    names, rows = cross_table(words)
    n = len(names)
    print(f"\n### {label}\n")
    print(format_table(names, rows))
    off = max(rows[i][j] for i in range(n) for j in range(n) if i != j)
    still = max(v for r in rows for v in r[n:])
    print(f"\n자기 재생 최소 {min(rows[i][i] for i in range(n)):.0f} · 다른 단어 최대 {off:.0f} · 정지 최대 {still:.0f}")


if __name__ == "__main__":
    before = json.loads((HERE / "extracted_landmarks_tms.json").read_text(encoding="utf-8"))
    after = {v["term"]: v for v in json.loads((HERE / "refined_landmarks.json").read_text(encoding="utf-8")).values()}
    report("정제 전", {t: to_array(before[t]["frames"]) for t in ORDER})
    report("정제 후 (refined-v1)", {t: to_array(after[t]["frames"]) for t in ORDER})
