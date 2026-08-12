"""PoC-конвейер: detect -> quality -> liveness -> embed -> search -> decide -> turnstile -> audit log.

Реализация упрощена относительно целевой архитектуры (docs/architecture.md) и
ML-подхода (docs/ml.md) — каждое упрощение помечено `# MOCK:` / `# SIMPLIFIED:`.
"""

import json
import time
import uuid
from pathlib import Path

import cv2
import faiss
import numpy as np

from src.schemas import AccessVerifyRequest, AccessVerifyResponse, QualityInfo

DATA_DIR = Path(__file__).parent / "data"
AUDIT_LOG_PATH = DATA_DIR / "audit_log.jsonl"

# SIMPLIFIED: пороги захардкожены как константы модуля. В проде калибруются на
# данных по методологии FAR/FRR (1:1) / FPIR/FNIR (1:N), см. docs/ml.md.
T_HIGH = 0.55
T_LOW = 0.25
MARGIN_MIN = 0.15
QUALITY_MIN = 0.5
LIVENESS_MIN = 0.5
CACHE_AGE_MAX_MINUTES = 30

# нормировка Laplacian variance в [0, 1]; откалибровано на demo-кадрах
# (sharp.jpg ~49000, blurry.jpg ~2) — см. poc/build_demo_data.py
QUALITY_VARIANCE_SCALE = 5000.0
MIN_FACE_SIZE_PX = 40

_TURNSTILE_SEEN_KEYS: set[str] = set()


def detect_and_embed(event: AccessVerifyRequest) -> tuple[np.ndarray | None, float, bool]:
    """Возвращает (embedding, quality_score, face_detected).

    Quality-check — реальный: Laplacian variance (blur) + минимальный размер кадра
    через OpenCV, без ML (см. docs/ml.md, "CV/ML-задачи в системе").

    # MOCK: детекция лица и эмбеддинг — не InsightFace/ArcFace, а заранее
    # подготовленный вектор из poc/data/demo_embeddings.npz по event_id.
    # В целевой системе — SCRFD (детекция) + ArcFace buffalo_l (512-D эмбеддинг),
    # см. docs/ml.md. InsightFace установлен, но скачивание весов buffalo_l не
    # уложилось в выделенное время — переключение на mock.
    """
    frame_path = Path(event.frame_uri)
    if not frame_path.is_absolute():
        frame_path = Path(__file__).parent.parent / event.frame_uri
    img = cv2.imread(str(frame_path), cv2.IMREAD_GRAYSCALE)
    if img is None:
        return None, 0.0, False

    face_detected = min(img.shape[:2]) >= MIN_FACE_SIZE_PX
    variance = cv2.Laplacian(img, cv2.CV_64F).var()
    quality_score = float(min(1.0, variance / QUALITY_VARIANCE_SCALE))

    demo_embeddings = np.load(DATA_DIR / "demo_embeddings.npz")
    if event.event_id not in demo_embeddings.files:
        return None, quality_score, face_detected
    embedding = demo_embeddings[event.event_id].astype(np.float32)

    return embedding, quality_score, face_detected


def check_liveness(event: AccessVerifyRequest) -> float:
    """# MOCK: в реальной системе — Silent-Face-Anti-Spoofing (passive), см. docs/ml.md.

    Здесь liveness_score читается из metadata.mock_liveness_score demo-события.
    """
    return float(event.metadata.get("mock_liveness_score", 0.95))


class _Gallery:
    """Загружает галерею эмбеддингов и держит FAISS-индекс для 1:N поиска."""

    def __init__(self) -> None:
        embeddings = np.load(DATA_DIR / "gallery_embeddings.npy").astype(np.float32)
        self.employee_ids = [
            eid
            for eid, _ in sorted(
                json.loads((DATA_DIR / "gallery_index.json").read_text()).items(),
                key=lambda kv: kv[1],
            )
        ]
        # cosine similarity через inner product над L2-нормализованными векторами.
        # IndexFlatIP — точный поиск, оправдан на 12 demo-сотрудниках.
        # В целевой архитектуре — FAISS HNSW для sub-second на сотнях тысяч
        # векторов, см. docs/ml.md.
        self.index = faiss.IndexFlatIP(embeddings.shape[1])
        self.index.add(embeddings)

    def search(self, embedding: np.ndarray) -> tuple[str, float, float]:
        """top-2 поиск: (employee_id, match_score, margin_to_second_best)."""
        scores, indices = self.index.search(embedding.reshape(1, -1), 2)
        top_score, second_score = float(scores[0][0]), float(scores[0][1])
        employee_id = self.employee_ids[int(indices[0][0])]
        margin = top_score - second_score
        return employee_id, top_score, margin


_gallery: _Gallery | None = None


def _get_gallery() -> _Gallery:
    global _gallery
    if _gallery is None:
        _gallery = _Gallery()
    return _gallery


def decide(
    match_score: float,
    margin_to_second_best: float,
    quality_score: float,
    liveness_score: float,
    network_status: str,
    cache_age_minutes: int,
) -> tuple[str, list[str], bool]:
    """Policy engine: пороги + gates -> (decision, reasons, degraded_mode).

    Логика из docs/ml.md ("Пороги и three-way decision"): T_high/T_low по
    match_score, gate по margin, gate по quality/liveness, offline с устаревшим
    кэшем -> консервативное решение независимо от скоров.
    """
    reasons: list[str] = []

    if network_status == "offline" and cache_age_minutes > CACHE_AGE_MAX_MINUTES:
        reasons.append("offline_conservative_decision")
        return "manual_review", reasons, True

    quality_ok = quality_score >= QUALITY_MIN
    liveness_ok = liveness_score >= LIVENESS_MIN
    margin_ok = margin_to_second_best >= MARGIN_MIN

    reasons.append("quality_ok" if quality_ok else "quality_below_threshold")
    reasons.append("liveness_ok" if liveness_ok else "liveness_below_threshold")
    if not margin_ok:
        reasons.append("margin_too_small")

    if match_score >= T_HIGH and margin_ok and quality_ok and liveness_ok:
        reasons.append("match_confident")
        return "allow", reasons, False

    if match_score < T_LOW:
        reasons.append("match_score_too_low")
        return "deny", reasons, False

    if not liveness_ok:
        reasons.append("liveness_gate_failed")

    return "manual_review", reasons, False


def send_turnstile_command(gate_id: str, command: str, idempotency_key: str) -> bool:
    """Mock-интеграция с турникетом: только логирование, без реального железа.

    Идемпотентность через `idempotency_key` (= audit_id) — демонстрация решения
    из docs/architecture.md ("Интеграция с турникетом"). Дедупликация — set() в
    памяти процесса; в проде — persisted outbox с TTL, см. docs/architecture.md.
    """
    if idempotency_key in _TURNSTILE_SEEN_KEYS:
        print(f"[turnstile] duplicate command ignored (idempotency_key={idempotency_key})")
        return True
    _TURNSTILE_SEEN_KEYS.add(idempotency_key)
    print(f"[turnstile] gate={gate_id} command={command} idempotency_key={idempotency_key}")
    return True


def write_audit_log(response: AccessVerifyResponse, raw_event: dict) -> None:
    """Одна строка JSONL = один AccessVerifyResponse + метаданные события.

    Сырые изображения в лог не пишутся — только frame_uri, не пиксели
    (принцип из docs/risks-and-ops.md соблюдается и в PoC).
    """
    record = {
        "response": json.loads(response.model_dump_json()),
        "event_metadata": raw_event["metadata"],
        "gate_id": raw_event["gate_id"],
        "camera_id": raw_event["camera_id"],
    }
    with AUDIT_LOG_PATH.open("a") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def run_event(raw_event: dict) -> AccessVerifyResponse:
    """Прогоняет одно demo-событие через весь pipeline и возвращает ответ API."""
    start = time.perf_counter()
    event = AccessVerifyRequest(**raw_event)

    embedding, quality_score, face_detected = detect_and_embed(event)
    liveness_score = check_liveness(event)

    if embedding is None or not face_detected:
        employee_id, match_score, margin = None, 0.0, 0.0
        decision, reasons, degraded_mode = "manual_review", ["face_not_detected"], False
    else:
        employee_id, match_score, margin = _get_gallery().search(embedding)
        decision, reasons, degraded_mode = decide(
            match_score=match_score,
            margin_to_second_best=margin,
            quality_score=quality_score,
            liveness_score=liveness_score,
            network_status=event.metadata.get("network", "online"),
            cache_age_minutes=event.metadata.get("cache_age_minutes", 0),
        )
        if decision != "allow":
            employee_id = employee_id if match_score >= T_LOW else None

    audit_id = str(uuid.uuid4())
    turnstile_command = "open" if decision == "allow" else "hold"
    send_turnstile_command(event.gate_id, turnstile_command, audit_id)

    latency_ms = int((time.perf_counter() - start) * 1000)

    response = AccessVerifyResponse(
        event_id=event.event_id,
        decision_id=str(uuid.uuid4()),
        decision=decision,
        employee_id=employee_id,
        match_score=match_score if embedding is not None else None,
        margin_to_second_best=margin if embedding is not None else None,
        quality=QualityInfo(
            face_detected=face_detected,
            quality_score=quality_score,
            liveness_score=liveness_score,
        ),
        reasons=reasons,
        turnstile_command=turnstile_command,
        requires_human_review=decision != "allow",
        degraded_mode=degraded_mode,
        audit_id=audit_id,
        latency_ms=latency_ms,
    )
    write_audit_log(response, raw_event)
    return response


def load_demo_events() -> dict[str, dict]:
    events = json.loads((DATA_DIR / "demo_events.json").read_text())
    return {e["event_id"]: e for e in events}
