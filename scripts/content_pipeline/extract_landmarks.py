"""
sueori 콘텐츠 배치 파이프라인 — Step 1: 랜드마크 추출

국립국어원 "일상생활수어" 오픈API(getCTE01701)에서 확보한 mp4 영상을 다운로드해
MediaPipe HandLandmarker(VIDEO 모드)로 프레임별 21포인트 손 랜드마크를 추출한다.

좌표계는 scoring_poc/lib/src/normalize.dart와 동일 원칙(손목=0번 원점, 중지 MCP=9번
기준 스케일)을 프론트엔드가 재사용할 수 있도록, 여기서는 정규화 전 raw 좌표(x,y는
0~1 이미지 정규화 좌표, z는 손목 기준 상대 깊이 — MediaPipe 기본 출력 그대로)를 저장한다.
정규화는 채점 시점에 클라이언트가 사용자 랜드마크와 동일한 함수로 일괄 적용한다.

미디어 호스트(sldict.korean.go.kr)는 http://로는 타임아웃나서 https://로 강제 치환한다
(2026-09-17 FE PoC에서 발견된 이슈).
"""
import json
import time
import urllib.request
from pathlib import Path

import cv2
import mediapipe as mp
from mediapipe.tasks.python import vision
from mediapipe.tasks.python.core.base_options import BaseOptions

HERE = Path(__file__).parent
MODEL_PATH = HERE / "hand_landmarker.task"
CACHE_DIR = HERE / "video_cache"
CACHE_DIR.mkdir(exist_ok=True)

MODEL_VERSION = "kcisa-batch-v1_mediapipe-hand_landmarker-float16-1"

# 2026-09-17 fetch_all.py / family_picks.txt에서 선정한 "가족" 카테고리 7단어.
WORDS = [
    {
        "term": "형,형님",
        "mp4": "http://sldict.korean.go.kr/multimedia/multimedia_files/convert/20190918/615446/MOV000237632_700X466.mp4",
        "thumb": "http://sldict.korean.go.kr/multimedia/multimedia_files/convert/20190918/615446/MOV000237632_215X161.jpg",
    },
    {
        "term": "누나,누님",
        "mp4": "http://sldict.korean.go.kr/multimedia/multimedia_files/convert/20200821/733566/MOV000252709_700X466.mp4",
        "thumb": "http://sldict.korean.go.kr/multimedia/multimedia_files/convert/20200821/733566/MOV000252709_215X161.jpg",
    },
    {
        "term": "남동생",
        "mp4": "http://sldict.korean.go.kr/multimedia/multimedia_files/convert/20191007/624831/MOV000249221_700X466.mp4",
        "thumb": "http://sldict.korean.go.kr/multimedia/multimedia_files/convert/20191007/624831/MOV000249221_215X161.jpg",
    },
    {
        "term": "동생",
        "mp4": "http://sldict.korean.go.kr/multimedia/multimedia_files/convert/20200824/734925/MOV000250491_700X466.mp4",
        "thumb": "http://sldict.korean.go.kr/multimedia/multimedia_files/convert/20200824/734925/MOV000250491_215X161.jpg",
    },
    {
        "term": "할머니,조모",
        "mp4": "http://sldict.korean.go.kr/multimedia/multimedia_files/convert/20191025/630754/MOV000236360_700X466.mp4",
        "thumb": "http://sldict.korean.go.kr/multimedia/multimedia_files/convert/20191025/630754/MOV000236360_215X161.jpg",
    },
    {
        "term": "딸,여식",
        "mp4": "http://sldict.korean.go.kr/multimedia/multimedia_files/convert/20191015/627575/MOV000251200_700X466.mp4",
        "thumb": "http://sldict.korean.go.kr/multimedia/multimedia_files/convert/20191015/627575/MOV000251200_215X161.jpg",
    },
    {
        "term": "남편,배우자,서방",
        "mp4": "http://sldict.korean.go.kr/multimedia/multimedia_files/convert/20191015/627512/MOV000251575_700X466.mp4",
        "thumb": "http://sldict.korean.go.kr/multimedia/multimedia_files/convert/20191015/627512/MOV000251575_215X161.jpg",
    },
]


def force_https(url: str) -> str:
    return url.replace("http://", "https://", 1) if url.startswith("http://") else url


def download(url: str, dest: Path):
    if dest.exists():
        return
    req = urllib.request.Request(force_https(url), headers={"User-Agent": "sueori-content-pipeline/1"})
    with urllib.request.urlopen(req, timeout=30) as resp, open(dest, "wb") as f:
        f.write(resp.read())


def extract_landmarks(video_path: Path) -> list[dict]:
    options = vision.HandLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=str(MODEL_PATH)),
        running_mode=vision.RunningMode.VIDEO,
        num_hands=1,
        min_hand_detection_confidence=0.4,
        min_tracking_confidence=0.4,
    )
    frames_out = []
    with vision.HandLandmarker.create_from_options(options) as landmarker:
        cap = cv2.VideoCapture(str(video_path))
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        frame_idx = 0
        while True:
            ok, frame_bgr = cap.read()
            if not ok:
                break
            frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_rgb)
            timestamp_ms = int(frame_idx / fps * 1000)
            result = landmarker.detect_for_video(mp_image, timestamp_ms)
            frame_idx += 1
            if not result.hand_landmarks:
                continue
            hand = result.hand_landmarks[0]
            handedness = result.handedness[0][0].category_name if result.handedness else None
            frames_out.append(
                {
                    "landmarks": [{"x": lm.x, "y": lm.y, "z": lm.z} for lm in hand],
                    "handedness": handedness,
                    # 손이 안 잡힌 프레임은 건너뛰므로, 원본 영상 기준 시각을 남겨야 시간 간격이 보존된다.
                    "tMs": timestamp_ms,
                }
            )
        cap.release()
    return frames_out


def main():
    results = {}
    for w in WORDS:
        term = w["term"]
        safe_name = term.split(",")[0]
        video_path = CACHE_DIR / f"{safe_name}.mp4"
        print(f"[{term}] downloading...")
        download(w["mp4"], video_path)
        print(f"[{term}] extracting landmarks...")
        t0 = time.time()
        frames = extract_landmarks(video_path)
        dt = time.time() - t0
        print(f"[{term}] {len(frames)} frames with a detected hand ({dt:.1f}s)")
        results[term] = {
            "frames": frames,
            "thumb": force_https(w["thumb"]),
            "source_ref": force_https(w["mp4"]),
        }

    out_path = HERE / "extracted_landmarks.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False)
    print(f"wrote {out_path} ({out_path.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
