# Contributing

Спасибо за интерес к проекту! Ниже — короткие правила, чтобы вклад был удобным
для всех.

## Ветки

- `main` — стабильная ветка, только проверенный код.
- `dev` — активная разработка; фичи вливаются сюда через PR.
- Для задачи создавайте ветку от `dev`: `feature/<кратко>`, `fix/<кратко>`.

## Commit-сообщения (Conventional Commits)

Используем [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <краткое описание>

<тело: что и зачем>
```

Типы: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `ci`, `perf`.
Примеры:
- `feat(api): add per-asset regeneration endpoint`
- `fix(worker): persist LLM-expanded prompt on every image`
- `docs(readme): reorganize research into docs/`

## Перед push / PR — прогоните проверки

Backend (Python):

```bash
cd service/backend
pip install -r requirements.txt
pytest -q
```

Frontend (TypeScript):

```bash
cd service/frontend
npm ci
npx tsc --noEmit
```

Оба прогона выполняются автоматически в **CI** (`.github/workflows/ci.yml`) на
каждый push и pull request — PR не должен ломать CI.

## Локальный запуск

Быстрее всего — demo-режим без GPU:

```bash
cd service
docker compose -f docker-compose.demo.yml up --build
```

## Структура репозитория

- `service/` — исполняемый код сервиса (backend, frontend, инференс).
- `docs/` — исследование (EDA, baseline-бенчмарки, MLflow, бизнес-план).

Подробности — в [корневом README](README.md) и [service/README.md](service/README.md).
