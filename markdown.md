# Промпт для IDE-ассистента — Блок 3: Proof-of-Concept

## Контекст задания (весь, без сокращений)

Я выполняю тестовое ML system design задание с тайм-боксом 4 часа: спроектировать CV/ML-систему распознавания лиц на проходной офисного кампуса — от кадра с камеры до решения о проходе (allow/deny/manual_review), с ручным контролем охраны для сомнительных случаев. Задание учебное. **PoC — не главная цель задания и не production-код**: это вспомогательный артефакт, подтверждающий, что один выбранный фрагмент архитектуры складывается в работающий сценарий. Не жертвуй качеством документации ради объёма PoC-кода — код должен быть компактным и честным, с явными пометками, что mock, а что реально.

**Что обязательно должен показать PoC:**
1. **Happy path**: кадр/mock-событие с камеры → детекция лица → оценка качества кадра → liveness check (mock допустим) → эмбеддинг (реальный или mock) → сравнение с базой разрешённых сотрудников → решение **allow** → турникет «открывается» (mock-вызов) → access event пишется в лог с причиной.
2. **Risky/fallback path**: лицо не найдено, ИЛИ низкое качество кадра, ИЛИ сомнительный liveness, ИЛИ малый margin к второму кандидату, ИЛИ offline-режим → решение **manual_review** (или deny), турникет **НЕ открывается автоматически**, причина решения видна в логе.
3. Допустимо использовать готовую CV-библиотеку, mock-модель, заранее подготовленные эмбеддинги, synthetic/demo-изображения — но нужно явно объяснить в README/комментариях, что упрощено и чем заменяется в целевой архитектуре.

**Формальные требования к сдаче, которые проверяет PoC:**
- PoC запускается по инструкции одной командой.
- Есть smoke-test/demo-скрипт.
- Happy path выдаёт `allow` для demo-сотрудника.
- Risky/fallback path не открывает доступ автоматически.
- Access events пишутся в лог/хранилище с причиной решения (`reasons`).

## Единый контракт данных (не менять, уже зафиксирован в `src/schemas.py` в Блоке 0)

Request (`AccessVerifyRequest`): `event_id, gate_id, camera_id, captured_at, frame_uri, metadata` (metadata: `direction, illumination, occlusion_hint, head_pose_hint, edge_node, network, cache_age_minutes`).

Response (`AccessVerifyResponse`): `event_id, decision_id, decision (allow|deny|manual_review), employee_id, match_score, margin_to_second_best, quality {face_detected, quality_score, liveness_score}, reasons[], turnstile_command (open|hold), requires_human_review, degraded_mode, audit_id, latency_ms`.

В Блоке 0 также созданы заглушки: `poc/demo.py` с функциями `run_happy_path() -> AccessVerifyResponse` и `run_risky_path() -> AccessVerifyResponse` (сейчас `raise NotImplementedError`), и `tests/test_smoke.py` с skip-тестами `test_happy_path_allows()` / `test_risky_path_does_not_open()`. Твоя задача — реализовать тела этих функций и снять skip с тестов.

## Уже принятые технические решения (Блоки 1–2), PoC должен им соответствовать, но в упрощённом виде

- **Детекция + эмбеддинг**: в целевой архитектуре — SCRFD (детекция) + ArcFace/InsightFace buffalo_l (эмбеддинг, 512-D, cosine similarity). В PoC — используем реальную библиотеку **InsightFace** (`pip install insightface onnxruntime`), модель-пак `buffalo_l` — она включает и детектор, и recognition-модель, значит закрывает обе задачи одним пакетом. Если библиотека не ставится/падает за 10 минут (сеть, версии, GPU/CPU-конфликт) — **не трать время на дебаг зависимостей, переключайся на fallback ниже**.
  - **Fallback (заранее одобрен)**: mock-эмбеддинги — заранее сгенерированный `poc/data/gallery_embeddings.npy` (например, случайные 512-D векторы, L2-нормализованные, для 10–15 «сотрудников») + для «пробного» лица либо тоже случайный вектор с управляемой похожестью на одного из галереи (для happy path — специально близкий вектор; для risky — специально неоднозначный/далёкий). Явно закомментировать в коде: `# MOCK: в реальной системе — ArcFace embedding из кадра, см. docs/ml.md`.
- **Quality-check**: реальная простая метрика — Laplacian variance (blur) через OpenCV + проверка минимального размера лица (bounding box). Не нужен ML для этого в PoC.
- **Liveness**: **mock** — допустимо и ожидаемо согласно заданию. Реализовать как функцию, принимающую флаг/метаданные события (например по `metadata.note` или отдельному полю `mock_liveness_score` в demo-событии) и возвращающую `liveness_score`. Явно закомментировать: `# MOCK: в реальной системе — Silent-Face-Anti-Spoofing, см. docs/ml.md`.
- **1:N matching**: реальный **FAISS** (`pip install faiss-cpu`), индекс `IndexFlatIP` или `IndexHNSWFlat` над L2-нормализованными эмбеддингами (cosine через inner product). При 10–15 демо-векторах разница Flat/HNSW не важна — бери `IndexFlatIP` для простоты, но добавь комментарий `# В целевой архитектуре — FAISS HNSW для sub-second на сотнях тысяч векторов, см. docs/ml.md`.
- **Three-way decision (policy engine)**: отдельная чистая функция `decide(match_score, margin_to_second_best, quality_score, liveness_score, network_status) -> (decision, reasons)`, реализующая логику из docs/ml.md: T_high/T_low по match_score, gate по margin, gate по quality/liveness, offline → консервативный manual_review. Пороги — захардкодить как константы модуля с комментарием, что в проде калибруются на данных (см. docs/ml.md).
- **Турникет**: mock-функция `send_turnstile_command(gate_id, command, idempotency_key) -> bool` — просто логирует вызов и возвращает True/False, никакой реальной интеграции. Обязательно принимает `idempotency_key` (используй `audit_id`) — это демонстрирует архитектурное решение из docs/architecture.md, даже если реального дедупликатора в PoC нет (можно просто держать `set()` уже виденных ключей в памяти процесса и логировать, если ключ повторный).
- **Audit log**: структурированный **JSON Lines** файл `poc/data/audit_log.jsonl` — одна строка = один `AccessVerifyResponse` (сериализованный через pydantic `.model_dump_json()`) плюс сырые входные метаданные события. Никаких сырых изображений в логе не хранить (даже в PoC — держи эту дисциплину, это прямая демонстрация принципа из docs/risks-and-ops.md).

## Задача: пошагово (ориентировочные тайм-боксы внутри блока)

**Шаг 1 — данные для демо.** Создать `poc/data/demo_events.json` — список из 5 событий по образцу референсных из задания (см. ниже), и `poc/data/gallery_embeddings.npy` + `poc/data/gallery_index.json` (`employee_id → индекс в galley`) для 10-15 demo-сотрудников.

Референсные demo-события (адаптируй под свою реализацию, но сохрани смысл):
1. `e-1001` — online, normal illumination → должен дать **allow**.
2. `e-1002` — online, backlight + occlusion_hint=mask → низкое quality_score → **manual_review**.
3. `e-1003` — online, попытка spoofing (в demo — просто мок с низким liveness_score) → **deny/manual_review**, турникет не открывается.
4. `e-1004` — online, два близких кандидата (маленький margin_to_second_best) → **manual_review**.
5. `e-1005` — offline, cache_age_minutes=240 → **manual_review** (degraded_mode=true), НЕ allow, даже если скор хороший — офлайн-неуверенность должна побеждать.

**Шаг 2 — reasons и quality.** Реализовать функции `detect_and_embed(frame_or_mock) -> (embedding, quality_score, face_detected)` и `check_liveness(...) -> liveness_score` (с учётом fallback-варианта из раздела выше).

**Шаг 3 — ANN search.** Загрузка `gallery_embeddings.npy` в FAISS-индекс при старте, функция `search(embedding) -> (employee_id, match_score, margin_to_second_best)` (top-2 поиск, margin = score[0] - score[1]).

**Шаг 4  — policy engine.** Реализовать `decide(...)` с порогами и правилами (см. выше), возвращающую `decision` и список `reasons` (человекочитаемые строки: `"quality_ok"`, `"liveness_below_threshold"`, `"margin_too_small"`, `"offline_conservative_decision"` и т.п. — по аналогии с примером ответа API в задании).

**Шаг 5 — сборка pipeline и demo.py.** Реализовать `run_happy_path()` и `run_risky_path()` в `poc/demo.py`: каждая функция берёт соответствующее demo-событие, прогоняет весь pipeline (detect → quality → liveness → embed → search → decide → turnstile command → audit log write) и возвращает `AccessVerifyResponse`. В `if __name__ == "__main__":` — прогнать обе, красиво напечатать в консоль результат (decision, reasons, latency_ms) для обоих путей плюс путь к audit log файлу.

**Шаг 6 — smoke-тест и README.** Снять `@pytest.mark.skip` в `tests/test_smoke.py`, реализовать проверки: `test_happy_path_allows()` — `response.decision == "allow"` и `response.turnstile_command == "open"`; `test_risky_path_does_not_open()` — `response.decision != "allow"` и `response.turnstile_command == "hold"`. Обновить `README.md`: раздел «Как запустить PoC» — конкретные команды (`pip install -r requirements.txt`, `python -m poc.demo`, `pytest tests/`), обновить таблицу «реализовано реально vs mock» (детекция/embedding — реально если InsightFace завёлся или mock если fallback; liveness — mock; ANN — реально FAISS; турникет — mock; audit log — реально).

## Формат и ограничения

- Код — Python, стиль простой и читаемый, докстринги короткие, не переусложняй абстракциями (никаких лишних классов/фреймворков — это PoC на 70 минут).
- Каждое упрощение — с комментарием `# MOCK: ...` или `# SIMPLIFIED: ...`, указывающим, что в целевой архитектуре (см. docs/architecture.md, docs/ml.md).
- Если на Шаге 1 установка InsightFace/onnxruntime не поднимается за ~10 минут — **сразу** переключайся на fallback с mock-эмбеддингами и не трать время дальше, это заранее одобренное решение, не спрашивай.
- В конце обязательно прогнать `python -m poc.demo` и `pytest tests/` и убедиться, что всё зелёное — покажи мне финальный вывод обеих команд.
- Не трогай docs/*.md и AI_USAGE.md/SELF_REVIEW.md в этом блоке — они не в скоупе.

## Критерии готовности

- [ ] `python -m poc.demo` запускается без ошибок, печатает `allow` для happy path и `manual_review`/`deny` (с `turnstile_command=hold`) для risky path.
- [ ] `pytest tests/` — оба smoke-теста зелёные, ни одного skip.
- [ ] `poc/data/audit_log.jsonl` содержит записи с `reasons` после запуска demo.
- [ ] Offline-событие (#5) даёт консервативное решение независимо от match_score.
- [ ] README.md обновлён с рабочей командой запуска и честной таблицей real/mock.
- [ ] Все mock-места явно закомментированы со ссылкой на целевой подход из docs/ml.md.
- [ ] Git-коммит с сообщением вида `poc: end-to-end happy + risky path, FAISS matching, policy engine (Block 3)`.

Не задавай уточняющих вопросов — весь необходимый контекст и все fallback-решения даны выше, действуй.