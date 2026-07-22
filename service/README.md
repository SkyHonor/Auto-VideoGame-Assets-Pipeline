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
| Инференс        | **Anima Base (Cosmos2)** через ComfyUI, Ollama (LLM prompt expand) |
| Тесты           | pytest, mongomock-motor, ASGITransport                            |
| Упаковка        | Docker, docker-compose (единая GPU-сборка, one-command deploy)     |

---

## 3.1. Из чего собран стек (provenance)

Все компоненты происходят из официальных источников и закреплены на конкретные
версии — сборка детерминирована и воспроизводима на любой машине с NVIDIA GPU.

| Сервис              | Источник                                             | Тип                         |
|---------------------|------------------------------------------------------|-----------------------------|
| backend / worker    | собственный `backend/Dockerfile`                     | сборка из исходников проекта |
| frontend            | собственный `frontend/Dockerfile`                    | сборка из исходников проекта |
| **ComfyUI**         | `github.com/comfyanonymous/ComfyUI` (официальный)    | **сборка из офиц. репозитория** |
| **Ollama**          | `ollama/ollama:0.3.14` (официальный образ)           | офиц. образ + auto `pull`   |
| MongoDB             | `mongo:7.0` (официальный образ)                      | офиц. образ                 |
| Redis               | `redis:7.4-alpine` (официальный образ)              | офиц. образ                 |
| MinIO               | `minio/minio:RELEASE.2024-10-13...` (официальный)   | офиц. образ                 |
| Модели (Anima Base) | `huggingface.co/SkyHonor/*` (публичные)             | auto-download на старте      |

ComfyUI собирается из официального GitHub поверх официального образа
`pytorch/pytorch` с CUDA — см. `comfyui/Dockerfile`. Ollama-модель и веса моделей
скачиваются автоматически при первом `docker compose up`, ручная настройка не требуется.

---

## 4. Структура

```
service/
├── docker-compose.yml         # production-стек (реальный GPU-инференс)
├── docker-compose.demo.yml    # demo-стек (без GPU, mock — запуск где угодно)
├── .env.example               # конфигурация (модели, БД, ComfyUI, Ollama)
├── comfyui/                    # Dockerfile сборки ComfyUI из офиц. GitHub
├── ollama/                    # init-скрипт auto-pull LLM из офиц. реестра
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
    ├── base-downloader/       # авто-загрузка Anima Base из HuggingFace
    ├── lora-downloader/       # авто-загрузка LoRA из HuggingFace
    ├── checkpoints/           # (том) скачанные базовые веса → ComfyUI
    └── lora-store/            # (том) скачанные LoRA → ComfyUI
```

---

## 5. Развёртывание

Есть два режима: **demo** (запускается где угодно, без GPU) и **production**
(реальный GPU-инференс).

### 5.1. Demo-режим (без GPU, запускается на любой машине)

Для быстрой демонстрации всего продуктового потока без видеокарты и без
скачивания моделей. Воркер генерирует детерминированные placeholder-изображения
(флаг `COMFYUI_MOCK=true`), но все остальные части реальны: авторизация,
очередь Celery, MongoDB, MinIO, согласование, скачивание.

```bash
cd service
docker compose -f docker-compose.demo.yml up --build
```

Ничего настраивать не нужно (`.env` не требуется). Подходит для ноутбука, CI,
машины без NVIDIA GPU. Полный сценарий (генерация → ревью → скачивание)
работает точно так же, как в production.

### 5.2. Production-режим (реальный GPU-инференс, одна команда)

**Требования к хосту:** NVIDIA GPU + NVIDIA Container Toolkit + свободное место
на диске (~30 ГБ под образы и веса моделей). Больше ничего настраивать не нужно.

> **NVIDIA Container Toolkit** — прослойка от NVIDIA, дающая Docker-контейнерам
> доступ к видеокарте (пробрасывает драйвер и устройства GPU внутрь контейнера).
> На Windows ставится вместе с Docker Desktop + WSL2 при наличии драйвера NVIDIA;
> на Linux — пакетом `nvidia-container-toolkit`. Именно он делает рабочим блок
> `deploy.resources.reservations.devices` в compose-файле.

```bash
cd service
cp .env.example .env
docker compose up --build -d
```

При первом запуске автоматически:
1. Собирается ComfyUI из официального репозитория `comfyanonymous/ComfyUI`.
2. `model-init` / `lora-init` скачивают веса Anima Base + LoRA из публичных
   репозиториев `SkyHonor/*` на HuggingFace (ручных шагов нет).
3. ComfyUI стартует только после того, как модели скачаны
   (`depends_on: service_completed_successfully`).
4. `ollama-init` автоматически подтягивает LLM `qwen2.5:3b` из официального
   реестра Ollama для расширения промптов.

| Сервис        | URL                        |
|---------------|----------------------------|
| UI            | http://localhost:5173      |
| API + Swagger | http://localhost:8000/docs |
| ComfyUI       | http://localhost:8188      |
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

## 7. Модели инференса (Anima Base)

Все веса автоматически скачиваются сервисами `model-init` / `lora-init` из
публичных HuggingFace-репозиториев `SkyHonor/*` при первом `docker compose up`.
Загрузка идемпотентна: уже скачанные файлы пропускаются.

**Что загружается (~6 GB):**
- **Anima Base** (Cosmos2): `anima-base-v1.0.safetensors` (UNet),
  `qwen_3_06b_base.safetensors` (Text Encoder), `qwen_image_vae.safetensors` (VAE)
  — репозиторий `SkyHonor/Anima`
- **Turbo LoRA**: `anima-turbo-lora-v0.2.safetensors` (ускорение инференса)
  — репозиторий `SkyHonor/Acceleration_Lora`
- **Style LoRA**: `SlyToon-Anima-v1.safetensors` (персонажи, триггер `@sltn`),
  `SpellIcons-Anima-v1.safetensors` (пропсы, триггер `@spll_icn`)
  — репозиторий `SkyHonor/Prototype`

Список моделей задаётся переменными `BASE_MODELS` / `LORA_MODELS` в `.env`
(формат `repo_id:filename`), поэтому подменить набор весов можно без правки кода.
`comfyui` и `ollama` требуют NVIDIA GPU (проброс устройств через `deploy.resources`).
LLM `qwen2.5:3b` используется, когда исполнитель включает тумблер
**LLM prompt expansion** в UI.

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
