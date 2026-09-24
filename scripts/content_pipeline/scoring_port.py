"""
FE 채점기(sueori-MVP-FE packages/scoring_poc/lib/src/)의 Python 이식본.
normalize.dart / landmark_distance.dart / dtw_scorer.dart와 같은 계산을 해야 한다.
기준 데이터를 정제할 때 FE와 같은 점수로 before/after를 비교하려고 쓴다.
"""
import math

import numpy as np

DTW_DECAY = 6.5
CAPTURE_MS = 33  # FE 동적 녹화 캡처 간격 (PR #12 이전 100ms)


def to_array(frames: list[dict]) -> np.ndarray:
    """frames JSON([{landmarks:[{x,y,z}×21], ...}]) → (N, 21, 3)."""
    return np.array([[[p["x"], p["y"], p["z"]] for p in f["landmarks"]] for f in frames], dtype=float)


PALM = [0, 5, 9, 13, 17]


def normalize(arr: np.ndarray) -> np.ndarray:
    """normalizeAndFlatten: 손목(0) 원점, 손바닥 5점(0,5,9,13,17) 쌍별 3D 거리 최댓값으로 스케일.

    (N,21,3) → (N,21,3). FE PR #12 이전에는 손목~중지 MCP(9) 거리였는데, 손을 돌릴 때
    그 거리가 짧아지면서 실제 움직임이 부풀려져 바뀌었다.
    """
    pts = arr[:, PALM, :]
    scale = np.linalg.norm(pts[:, :, None, :] - pts[:, None, :, :], axis=3).reshape(len(arr), -1).max(axis=1)
    scale = np.where(scale < 1e-9, 1.0, scale)
    return (arr - arr[:, 0:1, :]) / scale[:, None, None]


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


def relative_times(frames: list[dict], fps: float = 30.0) -> np.ndarray:
    """frames[0]을 0으로 둔 상대 시각(ms). tMs가 없으면 i*1000/fps (FE와 같음)."""
    if all("tMs" in f for f in frames):
        t = np.array([f["tMs"] for f in frames], dtype=float)
        return t - t[0]
    return np.arange(len(frames)) * 1000.0 / fps


def recording_ms(frames: list[dict]) -> int:
    """FE 녹화 길이: tMs가 있으면 (last - first) × 1.2를 반올림해 2000~8000ms, 없으면 3000ms."""
    if not all("tMs" in f for f in frames):
        return 3000
    return int(min(8000, max(2000, round((frames[-1]["tMs"] - frames[0]["tMs"]) * 1.2))))


def playback(arr: np.ndarray, times: np.ndarray, length_ms: int) -> np.ndarray:
    """FE 교차표의 '재생': t = 0, 33, … < 녹화 길이에서 tMs ≤ t인 마지막 프레임(끝나면 마지막 자세 유지)."""
    ts = np.arange(0, length_ms, CAPTURE_MS)
    return arr[np.searchsorted(times, ts, side="right") - 1]


def still(arr: np.ndarray, index: int, length_ms: int) -> np.ndarray:
    """FE 교차표의 '정지': frames[index]를 floor(녹화 길이 / 33)장 반복."""
    return np.repeat(arr[index : index + 1], length_ms // CAPTURE_MS, axis=0)


def cross_table(words: dict[str, list[dict]]) -> tuple[list[str], list[list[float]]]:
    """행 = 기준, 열 = 각 단어 재생 + 정지(첫) + 정지(중간). 녹화 길이는 기준(행) 단어로 정한다."""
    names = list(words)
    arrays = {n: to_array(words[n]) for n in names}
    times = {n: relative_times(words[n]) for n in names}
    rows = []
    for ref_name in names:
        ref, length = arrays[ref_name], recording_ms(words[ref_name])
        row = [dtw_score(ref, playback(arrays[c], times[c], length)) for c in names]
        row += [dtw_score(ref, still(ref, 0, length)), dtw_score(ref, still(ref, len(ref) // 2, length))]
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
