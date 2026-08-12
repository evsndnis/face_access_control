## Роль и контекст

Ты помогаешь мне выполнить тестовое ML system design задание за жёсткий тайм-бокс 4 часа: **CV/ML-система распознавания лиц на проходной офисного кампуса** (allow / deny / manual_review, edge+central архитектура, PoC на Python с InsightFace + FAISS). Сейчас — **Блок 0 (25 минут)**: только каркас репозитория, git-история и единый контракт данных, которым будут пользоваться все последующие блоки (architecture.md, ml.md, PoC). Не пиши бизнес-логику и не подключай реальные модели — это будет в следующих блоках. Цель блока — структура, которая компилируется/импортируется и коммитится.

## Что нужно сделать

### 1. Инициализировать репозиторий
```bash
git init
```
Создать `.gitignore` для Python-проекта (venv, __pycache__, *.pyc, .env, data/raw, models/*.onnx если будем кэшировать веса, .DS_Store).

### 2. Создать структуру каталогов и файлов-заглушек

```
.
├── README.md
├── AI_USAGE.md
├── SELF_REVIEW.md
├── docs/
│   ├── architecture.md
│   ├── ml.md
│   ├── monitoring.md
│   └── risks-and-ops.md
├── src/
│   ├── __init__.py
│   └── schemas.py
├── poc/
│   ├── __init__.py
│   ├── data/            # demo-изображения / synthetic-галерея (заполним в Блоке 3)
│   └── demo.py          # заглушка entrypoint, пока raise NotImplementedError
├── tests/
│   └── test_smoke.py    # заглушка pytest-теста
├── requirements.txt
└── .gitignore
```

Каждый `docs/*.md` и `AI_USAGE.md`, `SELF_REVIEW.md` — создать с заголовком верхнего уровня и списком секций-заголовков (без содержимого, только `## Секция` + `_TODO: заполнить в блоке N_`), **строго по секциям из задания**, чтобы в блоках 1–5 просто дописывать текст, не придумывая структуру заново:

- **docs/architecture.md**: `## Компоненты`, `## Data flow (happy path)`, `## Edge vs central: что и почему`, `## Синхронный hot path vs асинхронные части`, `## Хранилища`, `## Интеграция с турникетом`, `## Интерфейс ручной проверки охраны`, `## Fallback-пути при сбоях`, `## Диаграммы (Mermaid)`.
- **docs/ml.md**: `## CV/ML-задачи в системе`, `## Verification vs identification`, `## One-to-many поиск (ANN)`, `## Пороги и three-way decision`, `## Что правилами, а что моделью`, `## Baseline и метрики выбора`, `## Validation set и delayed labels`, `## LLM в системе — где да, где нет`.
- **docs/monitoring.md**: `## Технические метрики`, `## ML-метрики`, `## Бизнес-метрики`, `## Алерты`, `## Data drift vs model drift`, `## Audit trail`.
- **docs/risks-and-ops.md**: `## Low-latency, надёжность, деградация`, `## Privacy, safety, governance`.
- **AI_USAGE.md**: `## Декомпозиция задачи`, `## Архитектура`, `## Выбор CV/ML-подходов`, `## PoC`, `## Тесты и документация`, `## Риски и edge cases`, `## Ошибки AI и как исправлены`, `## Проверка безопасности биометрического дизайна`.
- **SELF_REVIEW.md**: `## Самая слабая часть`, `## Допущения`, `## Нерешённые риски`, `## Компромиссы ради demo`, `## Что улучшить за 2 дня`, `## Что доработать перед production`, `## Что нельзя без legal/security review`, `## Что не стоит автоматизировать полностью`, `## Какие данные пилота остановили бы проект`.

### 3. README.md — сразу с реальным содержанием (не заглушка)

Заполни по структуре из задания, коротко (README должен читаться за пару минут):
- 1 абзац: что делает решение (CV/ML-система решения о проходе по лицу с ручным контролем охраны для сомнительных случаев).
- Как запустить PoC (команда — добавим после Блока 3, пока `TODO`).
- Какой сценарий демонстрируется: happy path (allow) + risky path (manual_review, offline).
- Таблица «реализовано реально vs mock vs архитектурный дизайн» (пока пустая, с колонками: Компонент | Статус | Комментарий).
- Допущения и ограничения — TODO, заполним по ходу.
- Риски вне MVP — TODO.
- **3–5 предложений бизнес-ценности** — напиши сразу: сокращение очереди в пик 8:45–9:45, снижение ручного разбора охраной (~40 случаев/день × ~120 ₽), снижение затрат на перевыпуск карт, при этом безопасность не приносится в жертву скорости (false accept — инцидент безопасности, обрабатывается консервативными порогами и manual_review).

### 4. src/schemas.py — единый контракт данных (ключевое!)

Определи Pydantic-модели (или dataclasses, если Pydantic не хотим тянуть в PoC — на твой выбор, но обоснуй одной строкой комментария) для запроса и ответа `/v1/access/verify`, СТРОГО повторяющие поля из задания, чтобы architecture.md, ml.md и PoC ссылались на один и тот же контракт:

**Request** (`AccessVerifyRequest`): `event_id: str`, `gate_id: str`, `camera_id: str`, `captured_at: datetime`, `frame_uri: str`, `metadata: dict` (со свободными полями: `direction`, `illumination`, `occlusion_hint`, `head_pose_hint`, `edge_node`, `network`, `cache_age_minutes`).

**Quality** (`QualityInfo`): `face_detected: bool`, `quality_score: float`, `liveness_score: float`.

**Response** (`AccessVerifyResponse`): `event_id: str`, `decision_id: str`, `decision: Literal["allow", "deny", "manual_review"]`, `employee_id: str | None`, `match_score: float | None`, `margin_to_second_best: float | None`, `quality: QualityInfo`, `reasons: list[str]`, `turnstile_command: Literal["open", "hold"]`, `requires_human_review: bool`, `degraded_mode: bool`, `audit_id: str`, `latency_ms: int`.

Добавь docstring-комментарий над классами: «Единый контракт, на который ссылаются docs/architecture.md и docs/ml.md — не менять без синхронизации доков».

### 5. requirements.txt — заготовка (без установки пока)
```
pydantic>=2
pytest
# добавим в Блоке 3: insightface, onnxruntime, faiss-cpu, opencv-python-headless, numpy
```

### 6. poc/demo.py и tests/test_smoke.py — заглушки, но с правильными сигнатурами

`poc/demo.py`: функция `def run_happy_path() -> AccessVerifyResponse: raise NotImplementedError("Block 3")` и `def run_risky_path() -> AccessVerifyResponse: raise NotImplementedError("Block 3")`, плюс `if __name__ == "__main__":` с вызовом обеих и печатью результата — чтобы в Блоке 3 нужно было только реализовать тела функций.

`tests/test_smoke.py`: тест-заглушки `test_happy_path_allows()` и `test_risky_path_does_not_open()` с `pytest.mark.skip(reason="implement in Block 3")` — чтобы структура smoke-теста была видна с самого начала.

### 7. Закоммитить

Сделать **осмысленный первый коммит** (не «init»):
```bash
git add -A
git commit -m "scaffold: repo structure, README skeleton, shared decision schema (Block 0)"
```

## Критерии готовности (проверь перед тем как остановиться)

- [ ] `git log` показывает минимум 1 коммит с содержательным сообщением.
- [ ] Все файлы из дерева выше существуют.
- [ ] `python -c "from src.schemas import AccessVerifyRequest, AccessVerifyResponse"` не падает.
- [ ] README.md реально читаем за 1–2 минуты, без TODO в разделе бизнес-ценности.
- [ ] Каждый docs/*.md, AI_USAGE.md, SELF_REVIEW.md содержит заголовки секций 1-в-1 как в задании (это чек-лист для проверяющего).
- [ ] Ничего лишнего не реализовано (никакой ML-логики, никаких моделей) — только каркас.

Не задавай уточняющих вопросов по стилю — просто следуй структуре выше. Если нужно выбрать между Pydantic и dataclasses — возьми Pydantic (валидация пригодится в PoC для сериализации ответа в JSON-лог).