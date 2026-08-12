# Monitoring

## Технические метрики

- Latency p50/p95/p99 по стадиям (detect/quality/liveness/embed/ANN search) и end-to-end verify.
- Latency 1:N поиска отдельно от общего p95 (первый признак деградации при росте галереи).
- Доступность камер и edge-узлов (heartbeat/uptime по проходной и по камере).
- Ошибки интеграции с турникетом: failed commands, timeouts, доля ретраев.

## ML-метрики

- False reject rate (по delayed labels — жалобы, повторный проход по карте после отказа).
- Доля `manual_review` от общего числа событий (и её тренд по проходным).
- Доля отказов по низкому `quality_score` и liveness failure rate.
- Распределение `match_score` и `margin_to_second_best` (сдвиг распределения — ранний сигнал).

## Бизнес-метрики

Время прохода через турникет, доля автоматических проходов (`allow` без участия охраны), нагрузка на охрану — число `manual_review` в день.

## Алерты

- p95 end-to-end latency > 1с.
- Доступность камеры/edge-узла ниже порога (например uptime < 99% за скользящий час).
- Доля `manual_review` выросла сверх baseline (например +50% к недельной норме).
- Всплеск liveness failures на проходной/камере.
- PSI по quality-фичам (яркость, blur, pose) > 0.25.
- Всплеск failed turnstile commands.

## Data drift vs model drift

Data drift — сдвиг входа: освещение, качество камеры, ракурс, occlusion. Детектируется статистикой по `quality_score`/brightness/pose **без ground truth** (PSI, KS-test; PSI > 0.25 — тревожный уровень). Model drift — падение реального качества распознавания, требует labels (delayed labels из docs/ml.md: ручные проверки охраны, жалобы, повторный проход по карте). Алертить эффективнее на **совместное условие** (input drift + просадка eval-метрики) — снижает шум ложных алертов от одного лишь input drift.

Различить сбой камеры/освещения от деградации модели — сегментировать метрики **по проходной и по камере отдельно**: резкий скачок доли low-quality/отказов на одной камере при нормальных остальных → железо/освещение/загрязнение линзы; равномерный медленный рост FRR по всем узлам → модель или сдвиг популяции.

## Audit trail

Расследование конкретного события — по полям `audit_id, timestamp, camera_id, gate_id, decision, scores (match_score, margin_to_second_best, quality_score, liveness_score), reasons, model_version, threshold_version, degraded_mode`. Этого достаточно, чтобы восстановить причину решения без хранения сырых изображений или эмбеддингов в открытом виде.
