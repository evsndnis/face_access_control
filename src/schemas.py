"""Единый контракт данных для /v1/access/verify.

Pydantic выбран вместо dataclasses: нужна валидация полей и готовая
сериализация в JSON для audit-лога и ответа API в PoC.

Единый контракт, на который ссылаются docs/architecture.md и docs/ml.md —
не менять без синхронизации доков.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class AccessVerifyRequest(BaseModel):
    """Единый контракт, на который ссылаются docs/architecture.md и docs/ml.md — не менять без синхронизации доков."""

    event_id: str
    gate_id: str
    camera_id: str
    captured_at: datetime
    frame_uri: str
    metadata: dict
    # metadata со свободными полями: direction, illumination, occlusion_hint,
    # head_pose_hint, edge_node, network, cache_age_minutes


class QualityInfo(BaseModel):
    """Единый контракт, на который ссылаются docs/architecture.md и docs/ml.md — не менять без синхронизации доков."""

    face_detected: bool
    quality_score: float
    liveness_score: float


class AccessVerifyResponse(BaseModel):
    """Единый контракт, на который ссылаются docs/architecture.md и docs/ml.md — не менять без синхронизации доков."""

    event_id: str
    decision_id: str
    decision: Literal["allow", "deny", "manual_review"]
    employee_id: str | None
    match_score: float | None
    margin_to_second_best: float | None
    quality: QualityInfo
    reasons: list[str]
    turnstile_command: Literal["open", "hold"]
    requires_human_review: bool
    degraded_mode: bool
    audit_id: str
    latency_ms: int
