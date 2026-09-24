"""
sueori 콘텐츠 배치 파이프라인 — 지문자(정적) 카테고리: 한글 자모 40개.

동적 단어(extract_landmarks.py)와 달리 정적 콘텐츠는 ERD 설계대로
ReferenceLandmark.frames를 길이 1로 저장한다(정지된 손 모양 하나만 필요,
채점 알고리즘도 cosine + referenceFrameIndex=0). 영상에서 손이 인식된
프레임들 중 중앙값 인덱스 프레임을 대표 프레임으로 선택한다(자모 손모양을
만들어가는 도입부/유지 구간을 피해 안정된 형태를 고르기 위한 단순 휴리스틱).
"""
import json
import time
from pathlib import Path

import cv2
import mediapipe as mp
from mediapipe.tasks.python import vision
from mediapipe.tasks.python.core.base_options import BaseOptions

from extract_landmarks import CACHE_DIR, MODEL_PATH, download, force_https

MODEL_VERSION = "kcisa-batch-v1_mediapipe-hand_landmarker-float16-1"

WORDS = json.load(open(Path(__file__).parent / "jamo_picks.json", encoding="utf-8"))


def extract_all_frames(video_path: Path) -> list[dict]:
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
                }
            )
        cap.release()
    return frames_out


def main():
    results = {}
    for w in WORDS:
        term = w["term"]
        video_path = CACHE_DIR / f"jamo_{ord(term):05x}.mp4"
        print(f"[{term}] downloading...")
        download(w["mp4"], video_path)
        print(f"[{term}] extracting landmarks...")
        t0 = time.time()
        frames = extract_all_frames(video_path)
        dt = time.time() - t0
        if not frames:
            print(f"[{term}] WARNING: no hand detected in any frame, skipping")
            continue
        representative = frames[len(frames) // 2]
        print(f"[{term}] {len(frames)} frames with a detected hand, picked frame {len(frames)//2} ({dt:.1f}s)")
        results[term] = {
            "frames": [representative],
            "thumb": force_https(w["thumb"]),
            "source_ref": force_https(w["mp4"]),
        }

    out_path = Path(__file__).parent / "extracted_landmarks_jamo.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False)
    print(f"wrote {out_path} ({out_path.stat().st_size} bytes), {len(results)}/{len(WORDS)} succeeded")


if __name__ == "__main__":
    main()
