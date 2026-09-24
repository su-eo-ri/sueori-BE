"""
FE 채점기(sueori-MVP-FE packages/scoring_poc/lib/src/)의 Python 이식본.
normalize.dart / landmark_distance.dart / dtw_scorer.dart와 같은 계산을 해야 한다.
기준 데이터를 정제할 때 FE와 같은 점수로 before/after를 비교하려고 쓴다.
"""
import math

import numpy as np

DTW_DECAY = 6.5
PLAYBACK_FRAMES = 30  # FE 3초 녹화(100ms 간격)


def to_array(frames: list[dict]) -> np.ndarray:
    """frames JSON([{landmarks:[{x,y,z}×21], ...}]) → (N, 21, 3)."""
    return np.array([[[p["x"], p["y"], p["z"]] for p in f["landmarks"]] for f in frames], dtype=float)


def normalize(arr: np.ndarray) -> np.ndarray:
    """normalizeAndFlatten: 손목(0) 원점, 손목~중지 MCP(9) 거리로 스케일. (N,21,3) → (N,21,3)."""
    wrist = arr[:, 0:1, :]
    scale = np.linalg.norm(arr[:, 9, :] - arr[:, 0, :], axis=1)
    scale = np.where(scale < 1e-9, 1.0, scale)
    return (arr - wrist) / scale[:, None, None]


def avg_landmark_distance(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """averageLandmarkDistance를 모든 쌍에 대해 계산. a (N,21,3), b (M,21,3) → (N,M)."""
    return np.linalg.norm(a[:, None, :, :] - b[None, :, :, :], axis=3).mean(axis=2)


def dtw_score(reference: np.ndarray, candidate: np.ndarray, decay: float = DTW_DECAY) -> float:
    """DtwScorer.score와 같은 계산(backtrack 동률 처리 순서 diag → up → left 포함)."""
    a, b = normalize(reference), normalize(candidate)
    n, m = len(a), len(b)
    if n == 0 or m == 0:
        return 0.0
    cost = avg_landmark_distance(a, b)
    dp = np.full((n + 1, m + 1), math.inf)
    dp[0, 0] = 0.0
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            dp[i, j] = cost[i - 1, j - 1] + min(dp[i - 1, j], dp[i, j - 1], dp[i - 1, j - 1])
    i, j, path = n, m, 0
    while i > 0 or j > 0:
        path += 1
        if i == 0:
            j -= 1
        elif j == 0:
            i -= 1
        else:
            diag, up, left = dp[i - 1, j - 1], dp[i - 1, j], dp[i, j - 1]
            mv = min(diag, up, left)
            if mv == diag:
                i, j = i - 1, j - 1
            elif mv == up:
                i -= 1
            else:
                j -= 1
    avg = dp[n, m] / path
    return float(min(100.0, max(0.0, 100 * math.exp(-decay * avg))))


def playback(arr: np.ndarray, n: int = PLAYBACK_FRAMES) -> np.ndarray:
    """FE 교차표의 '재생': frames[(i * len / 30).floor()] for i in 0..29."""
    return arr[[math.floor(i * len(arr) / n) for i in range(n)]]


def still(arr: np.ndarray, index: int, n: int = PLAYBACK_FRAMES) -> np.ndarray:
    """FE 교차표의 '정지': frames[index]를 30번 반복."""
    return np.repeat(arr[index : index + 1], n, axis=0)


def cross_table(words: dict[str, np.ndarray]) -> tuple[list[str], list[list[float]]]:
    """행 = 기준, 열 = 각 단어 재생 + 정지(첫) + 정지(중간). FE 표와 같은 배치."""
    names = list(words)
    rows = []
    for ref_name in names:
        ref = words[ref_name]
        row = [dtw_score(ref, playback(words[c])) for c in names]
        row += [dtw_score(ref, still(ref, 0)), dtw_score(ref, still(ref, len(ref) // 2))]
        rows.append(row)
    return names, rows


def format_table(names: list[str], rows: list[list[float]]) -> str:
    short = [n.split(",")[0] for n in names]
    head = "| 기준\\재생 | " + " | ".join(short) + " | 정지(첫) | 정지(중간) |"
    sep = "|" + "---|" * (len(short) + 3)
    lines = [head, sep]
    for i, r in enumerate(rows):
        cells = [f"**{round(v)}**" if j == i else str(round(v)) for j, v in enumerate(r)]
        lines.append(f"| {short[i]} | " + " | ".join(cells) + " |")
    return "\n".join(lines)
