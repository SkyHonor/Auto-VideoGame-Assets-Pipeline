# AssetForge — MVP сервиса генерации игровых ассетов

Веб-сервис, который превращает текстовые промпты в стилизованные игровые ассеты
(персонажи, иконки-пропсы) через локальный **ComfyUI**, хранит результаты и
метаданные в **MinIO + MongoDB** и проводит их через процесс согласования
«исполнитель → арт-директор → выдача».

> Продолжение исследовательской части репозитория (`baseline/`, EDA, бенчмарки):
> обученные style-LoRA и подобранные пайплайны генерации здесь «упакованы» в
> продуктовый MVP.

---

## 1. Архитектура

```
                 ┌──────────────────────────────────────────────┐
                 │                  Frontend (SPA)               │
                 │      React + Vite + TS, отдаётся через nginx   │
                 │   • Исполнитель: промпты, параметры, батчи     │
                 │   • Арт-директор: приём/отклонение пакетов     │
                 └───────────────┬──────────────────────────────┘
                                 │  /api (nginx reverse-proxy)
                                 ▼
                 ┌──────────────────────────────────────────────┐
                 │             Backend REST API (FastAPI)         │
                 │   auth (JWT) · packages · generation · review  │
                 └───┬───────────────┬───────────────┬───────────┘
        Beanie ODM   │               │ Celery task   │ presigned/stream
                     ▼               ▼               ▼
              ┌────────────┐  ┌────────────┐  ┌────────────┐
              │  MongoDB   │  │   Redis     │  │   MinIO    │
              │ доменная   │  │ брокер +    │  │ бинарники  │
              │  модель    │  │ результаты  │  │ картинок   │
              └────────────┘  └─────┬──────┘  └────────────┘
                                    │ разбирают очередь
                          ┌─────────▼─────────┐
                          │  Celery worker(s) │  ← масштабируются:
                          │  --scale worker=N │    docker compose up --scale worker=N
                          └─────────┬─────────┘
                                    │ HTTP workflow
                    ┌───────────────┼───────────────┐
                    ▼                               ▼
             ┌────────────┐                  ┌────────────┐
             │  ComfyUI   │  (GPU)           │  Ollama    │  (LLM prompt expand)
             │  base+LoRA │                  │  qwen2.5   │
             └────────────┘                  └────────────┘
```

Ключевая идея — **разделение синхронного API и асинхронной генерации**. API
только ставит задачу в очередь и мгновенно отвечает `job_id`; тяжёлую работу на
GPU выполняют воркеры, которых можно горизонтально масштабировать под нагрузку.

---

## 2. Доменная модель

Роли (`UserRole`): `executor` (исполнитель), `art-director` (арт-директор).

| Сущность    | Назначение                                                             |
|-------------|------------------------------------------------------------------------|
| **User**    | Учётная запись, роль определяет доступный интерфейс и права.           |
| **Package** | Единица согласования — набор ассетов на одну тему. Проходит статусы.   |
| **Job**     | Одна задача генерации (1 промпт → батч из N картинок), статус выполнения.|
| **Image**   | Метаданные ассета (промпт, seed, размеры, workflow) + ключ объекта в MinIO. |
| **Review**  | Решение арт-директора (approve/reject) с комментарием, история.        |

**Жизненный цикл пакета** (`PackageStatus`):

```
draft ──generate──▶ (draft) ──submit──▶ pending_review
   ▲                                          │
   │                                    ┌──────┴───────┐
   └──────────── reject ◀───────────────┤  art-director │
                                        └──────┬───────┘
                                          approve
                                               ▼
                                           approved ──▶ download / в производство
```

- Исполнитель редактирует и генерирует только пока пакет `draft`/`rejected`.
- После `submit` пакет блокируется на редактирование и ждёт ревью.
- `approved` пакет доступен для скачивания ZIP-архивом.

---

## 3. Технологический стек

| Слой            | Технологии                                                        |
|-----------------|-------------------------------------------------------------------|
| Frontend        | React 18, TypeScript, Vite, nginx                                 |
| Backend / REST  | FastAPI, Pydantic v2, JWT (python-jose), Passlib                  |
| СУБД / ODM      | MongoDB 7 + Beanie (async ODM поверх Motor)                       |
| Object storage  | MinIO (S3-совместимое), клиент `minio`                            |
| Очередь / воркеры | Celery + Redis (broker & result backend)                        |
| Инференс        | ComfyUI (HTTP API), Ollama (расширение промптов LLM)              |
| Тесты           | pytest, mongomock-motor, ASGITransport                            |
| Упаковка        | Docker, docker-compose (профили `gpu`, `models`)                 |

---

## 4. Структура

```
service/
├── docker-compose.yml         # весь стек одной командой
├── .env.example               # конфигурация (по умолчанию mock-режим без GPU)
├── backend/
│   ├── Dockerfile             # один образ для API и для worker
│   ├── app/
│   │   ├── main.py            # сборка FastAPI, lifespan (init БД, bootstrap)
│   │   ├── core/              # config (env), security (JWT/хеши)
│   │   ├── models/            # доменная модель (Beanie Documents, enums)
│   │   ├── schemas.py         # request/response DTO + сериализаторы
│   │   ├── db/                # подключение MongoDB
│   │   ├── services/          # storage(MinIO), comfy_client, llm, workflow, flow
│   │   ├── workflows/         # ComfyUI-графы (character.json, props.json)
│   │   ├── api/routers/       # auth, packages, generation, images, health
│   │   └── workers/           # celery_app + tasks (генерация)
│   └── tests/                 # unit + integration (26 тестов)
├── frontend/
│   ├── Dockerfile             # multi-stage: vite build → nginx
│   ├── nginx.conf             # SPA + reverse-proxy /api → backend
│   └── src/                   # App, Executor, Director, api-клиент, стили
└── models/
    ├── base-downloader/       # разовая загрузка базовых чекпоинтов из HuggingFace
    └── lora-store/            # смонтированные style-LoRA проекта
```

---

## 5. Быстрый старт (без GPU, «из коробки»)

Работает в mock-режиме: воркеры генерируют детерминированные изображения-плейсхолдеры
(как `DRY_RUN` в ноутбуках), поэтому весь пайплайн можно продемонстрировать без видеокарты.

```bash
cd service
cp .env.example .env
docker compose up --build
```

| Сервис        | URL                        |
|---------------|----------------------------|
| UI            | http://localhost:5173      |
| API + Swagger | http://localhost:8000/docs |
| MinIO консоль | http://localhost:9001      |

**Демо-аккаунты** (создаются автоматически при первом запуске):

| Роль          | Логин      | Пароль        |
|---------------|------------|---------------|
| Исполнитель   | `artist`   | `artist123`   |
| Арт-директор  | `director` | `director123` |

Сценарий демонстрации: войти как `artist` → создать пакет → задать промпт и
параметры → сгенерировать батч → «Send for review» → войти как `director` →
approve/reject с комментарием → скачать одобренный пакет.

---

## 6. Масштабирование воркеров

Генерация вынесена в отдельный сервис `worker`. Пул масштабируется горизонтально
без изменения кода — просто добавляем реплики, которые разбирают одну очередь Redis:

```bash
docker compose up --scale worker=4
```

Каждый воркер — отдельный процесс Celery (`--concurrency=1`), что для GPU-инференса
корректнее, чем много потоков в одном процессе.

---

## 7. Реальный GPU-инференс

```bash
# 1) один раз выкачать базовые модели в общий volume
docker compose --profile models up model-init

# 2) положить обученные LoRA в models/lora-store/ (см. его README)

# 3) в .env выставить COMFYUI_MOCK=false, затем поднять GPU-профиль
docker compose --profile gpu up --build
```

`comfyui` требует NVIDIA GPU (в compose проброшены устройства через
`deploy.resources`). `ollama` используется, когда исполнитель включает тумблер
**LLM prompt expansion**.

---

## 8. REST API (кратко)

Базовый префикс: `/api/v1`. Авторизация: `Authorization: Bearer <JWT>`.

| Метод | Путь                          | Роль            | Описание                          |
|-------|-------------------------------|-----------------|-----------------------------------|
| POST  | `/auth/login`                 | —               | Логин, выдача JWT                 |
| GET   | `/auth/me`                    | любая           | Текущий пользователь              |
| GET   | `/packages?status=`           | обе             | Список пакетов (для роли)         |
| POST  | `/packages`                   | executor        | Создать пакет                     |
| GET   | `/packages/{id}`              | обе             | Пакет по id                       |
| GET   | `/packages/{id}/images`       | обе             | Ассеты пакета                     |
| POST  | `/packages/{id}/generate`     | executor        | Поставить задачу генерации        |
| POST  | `/packages/{id}/submit`       | executor        | Отправить на согласование         |
| POST  | `/packages/{id}/review`       | art-director    | Approve / reject + комментарий    |
| GET   | `/packages/{id}/reviews`      | обе             | История ревью                     |
| GET   | `/packages/{id}/download`     | обе             | ZIP одобренного пакета            |
| GET   | `/jobs/{id}`                  | executor        | Статус задачи генерации           |
| GET   | `/images/{id}/file`           | обе             | Бинарник картинки из MinIO        |
| GET   | `/health`                     | —               | Проверка живости                  |

Полная интерактивная спецификация — в Swagger UI (`/docs`).

---

## 9. Тесты

Критичные части покрыты unit- и integration-тестами (auth, бизнес-правила
жизненного цикла пакета, RBAC, поток генерации через мок ComfyUI/MinIO).

```bash
cd service/backend
pip install -r requirements.txt
pytest -q            # 26 passed
```

Тесты изолированы: MongoDB подменяется `mongomock-motor`, MinIO и ComfyUI —
in-memory моками, поэтому не требуют внешних сервисов и работают в CI.

---

## 10. Соответствие критериям задания

| Критерий задания                                  | Реализация                                                        |
|---------------------------------------------------|-------------------------------------------------------------------|
| Доменная модель                                   | `app/models/*` (User, Package, Job, Image, Review) + статусы/роли |
| Хранение данных за счёт СУБД                       | MongoDB (метаданные) + MinIO (бинарники) через Beanie/minio       |
| REST-интерфейс                                     | FastAPI, версионированный `/api/v1`, Swagger                      |
| Пользовательский интерфейс                         | React SPA с двумя ролевыми режимами                               |
| Покрытие тестами критичных частей                  | pytest: 26 тестов (unit + integration)                            |
| Упаковка в Docker                                  | Dockerfile backend/frontend + docker-compose                      |
| Масштабирование воркеров с моделью                 | отдельный `worker`, `--scale worker=N`, общая очередь Redis       |
