"""Генерирует demo-данные для PoC: галерею сотрудников, синтетические кадры и demo-события.

Запускается один раз (`python -m poc.build_demo_data`), результат коммитится в poc/data/.
Не часть runtime pipeline — только подготовка фикстур.
"""

import json
from pathlib import Path

import cv2
import numpy as np

DATA_DIR = Path(__file__).parent / "data"
FRAMES_DIR = DATA_DIR / "frames"

N_EMPLOYEES = 12
EMBEDDING_DIM = 512
SEED = 42


def _make_frame(path: Path, sharp: bool) -> None:
    """Синтетический кадр для реальной проверки blur через OpenCV Laplacian variance.

    sharp=True — высокочастотный паттерн (высокая variance, "хорошее" качество).
    sharp=False — тот же паттерн после сильного гауссова блюра ("плохое" качество).
    """
    rng = np.random.default_rng(0)
    img = (rng.integers(0, 256, size=(240, 240, 3))).astype(np.uint8)
    # шахматный паттерн поверх шума — даёт стабильно высокие границы для sharp-варианта
    step = 12
    for y in range(0, 240, step):
        for x in range(0, 240, step):
            if (x // step + y // step) % 2 == 0:
                img[y : y + step, x : x + step] = 255 - img[y : y + step, x : x + step]
    if not sharp:
        img = cv2.GaussianBlur(img, (25, 25), sigmaX=12)
    cv2.imwrite(str(path), img)


def _embedding_near(rng: np.random.Generator, target: np.ndarray, noise_scale: float) -> np.ndarray:
    vec = target + rng.normal(scale=noise_scale, size=target.shape)
    return vec / np.linalg.norm(vec)


def main() -> None:
    FRAMES_DIR.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(SEED)

    # MOCK: галерея — случайные L2-нормализованные векторы вместо реальных ArcFace
    # эмбеддингов сотрудников. В целевой системе — вывод buffalo_l, см. docs/ml.md.
    gallery = rng.normal(size=(N_EMPLOYEES, EMBEDDING_DIM))
    gallery = gallery / np.linalg.norm(gallery, axis=1, keepdims=True)
    employee_ids = [f"emp-{i + 1:03d}" for i in range(N_EMPLOYEES)]

    np.save(DATA_DIR / "gallery_embeddings.npy", gallery.astype(np.float32))
    (DATA_DIR / "gallery_index.json").write_text(
        json.dumps({eid: i for i, eid in enumerate(employee_ids)}, ensure_ascii=False, indent=2)
    )

    _make_frame(FRAMES_DIR / "sharp.jpg", sharp=True)
    _make_frame(FRAMES_DIR / "blurry.jpg", sharp=False)

    target_happy = gallery[employee_ids.index("emp-003")]
    embedding_happy = _embedding_near(rng, target_happy, noise_scale=0.06)

    embedding_quality_issue = _embedding_near(rng, target_happy, noise_scale=0.06)

    embedding_spoof = _embedding_near(rng, target_happy, noise_scale=0.06)

    # два близких кандидата: смесь emp-005 и emp-006 -> малый margin_to_second_best
    target_a = gallery[employee_ids.index("emp-005")]
    target_b = gallery[employee_ids.index("emp-006")]
    mixed = 0.5 * target_a + 0.5 * target_b
    embedding_ambiguous = mixed / np.linalg.norm(mixed)

    embedding_offline = _embedding_near(rng, target_happy, noise_scale=0.06)

    demo_embeddings = {
        "e-1001": embedding_happy,
        "e-1002": embedding_quality_issue,
        "e-1003": embedding_spoof,
        "e-1004": embedding_ambiguous,
        "e-1005": embedding_offline,
    }
    np.savez(
        DATA_DIR / "demo_embeddings.npz",
        **{k: v.astype(np.float32) for k, v in demo_embeddings.items()},
    )

    events = [
        {
            "event_id": "e-1001",
            "gate_id": "gate-1",
            "camera_id": "cam-1a",
            "captured_at": "2026-08-12T08:52:03+03:00",
            "frame_uri": "poc/data/frames/sharp.jpg",
            "metadata": {
                "direction": "in",
                "illumination": "normal",
                "occlusion_hint": "none",
                "head_pose_hint": "frontal",
                "edge_node": "edge-gate-1",
                "network": "online",
                "cache_age_minutes": 2,
                "mock_liveness_score": 0.97,
            },
        },
        {
            "event_id": "e-1002",
            "gate_id": "gate-1",
            "camera_id": "cam-1b",
            "captured_at": "2026-08-12T08:53:10+03:00",
            "frame_uri": "poc/data/frames/blurry.jpg",
            "metadata": {
                "direction": "in",
                "illumination": "backlight",
                "occlusion_hint": "mask",
                "head_pose_hint": "frontal",
                "edge_node": "edge-gate-1",
                "network": "online",
                "cache_age_minutes": 1,
                "mock_liveness_score": 0.95,
            },
        },
        {
            "event_id": "e-1003",
            "gate_id": "gate-2",
            "camera_id": "cam-2a",
            "captured_at": "2026-08-12T08:55:41+03:00",
            "frame_uri": "poc/data/frames/sharp.jpg",
            "metadata": {
                "direction": "in",
                "illumination": "normal",
                "occlusion_hint": "none",
                "head_pose_hint": "frontal",
                "edge_node": "edge-gate-2",
                "network": "online",
                "cache_age_minutes": 1,
                "mock_liveness_score": 0.12,
            },
        },
        {
            "event_id": "e-1004",
            "gate_id": "gate-2",
            "camera_id": "cam-2b",
            "captured_at": "2026-08-12T09:01:22+03:00",
            "frame_uri": "poc/data/frames/sharp.jpg",
            "metadata": {
                "direction": "in",
                "illumination": "normal",
                "occlusion_hint": "none",
                "head_pose_hint": "slight_turn",
                "edge_node": "edge-gate-2",
                "network": "online",
                "cache_age_minutes": 1,
                "mock_liveness_score": 0.96,
            },
        },
        {
            "event_id": "e-1005",
            "gate_id": "gate-3",
            "camera_id": "cam-3a",
            "captured_at": "2026-08-12T09:10:05+03:00",
            "frame_uri": "poc/data/frames/sharp.jpg",
            "metadata": {
                "direction": "in",
                "illumination": "normal",
                "occlusion_hint": "none",
                "head_pose_hint": "frontal",
                "edge_node": "edge-gate-3",
                "network": "offline",
                "cache_age_minutes": 240,
                "mock_liveness_score": 0.97,
            },
        },
    ]
    (DATA_DIR / "demo_events.json").write_text(json.dumps(events, ensure_ascii=False, indent=2))

    print(f"Gallery: {N_EMPLOYEES} employees -> {DATA_DIR / 'gallery_embeddings.npy'}")
    print(f"Demo events: {len(events)} -> {DATA_DIR / 'demo_events.json'}")


if __name__ == "__main__":
    main()
