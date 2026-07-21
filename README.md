# Auto VideoGame Assets Pipeline

Проект по автоматизации создания стилизованных игровых ассетов (персонажи,
иконки-пропсы) с помощью диффузионных моделей и обученных style-LoRA.

Репозиторий состоит из двух частей:

## 🔬 Исследование (ML)
- `baseline/` — серия бенчмарков пайплайнов генерации (ComfyUI workflows),
  A/B-тест «NLP-промпты vs теги».
- `eda_*_dataset_analysis.ipynb` — EDA датасетов персонажей и пропсов.
- `data_and_validation/`, `product_benchmarking/`, `business_plan.md` —
  валидация данных, продуктовые метрики и бизнес-контекст.

## 🚀 MVP-сервис
- **[`service/`](service/README.md)** — полноценный веб-сервис генерации: React-UI
  (исполнитель + арт-директор), REST API на FastAPI, хранение в MongoDB + MinIO,
  асинхронные Celery-воркеры поверх локального ComfyUI, упаковка в Docker и
  горизонтальное масштабирование воркеров.

  Быстрый старт (без GPU, mock-режим):
  ```bash
  cd service && cp .env.example .env && docker compose up --build
  # UI: http://localhost:5173  ·  API: http://localhost:8000/docs
  ```

Подробная архитектура, доменная модель, описание API и инструкции —
в **[service/README.md](service/README.md)**.
