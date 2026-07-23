# 🔬 Research & Documentation

Исследовательская часть проекта **Auto VideoGame Assets Pipeline** — путь от анализа
данных и обучения style-LoRA до продуктового MVP-сервиса. Здесь собрано всё, что
обосновывает технические решения сервиса (`../service/`).

> Продуктовый сервис (архитектура, деплой, API) описан в **[корневом README](../README.md)**.

---

## 📁 Структура

| Раздел | Содержимое |
|--------|------------|
| **[`business_plan/`](business_plan/)** | Бизнес-план, продуктовый прототип и конкурентный бенчмаркинг |
| **[`eda/`](eda/)** | Разведочный анализ датасетов + описание данных и схем валидации |
| **[`baseline/`](baseline/)** | Серия из 7 бенчмарков пайплайнов генерации + A/B-тест «NLP vs теги» |
| **[`mlflow/`](mlflow/)** | `mlruns.db` — база экспериментов MLflow (KID / CLIP / LPIPS) |
| **[`presentations/`](presentations/)** | Презентации и описание проекта (локально, вне git) |


---

## 1. Разведочный анализ данных (EDA)

- **[`eda/eda_character_dataset_analysis.ipynb`](eda/eda_character_dataset_analysis.ipynb)** —
  анализ датасета персонажей: распределения Booru-тегов, баланс классов, разрешение,
  удаление дубликатов и обоснование *Bias by Design* (уклон в characters).
- **[`eda/eda_props_dataset_analysis.ipynb`](eda/eda_props_dataset_analysis.ipynb)** —
  анализ датасета предметов/иконок: теги-якоря, NLP-описания пространственных связей,
  обоснование гибридной разметки **tags + NLP**.
- **[`eda/data_and_validation.md`](eda/data_and_validation.md)** — источники и состав
  данных, брендбуки стилей (`@sltn`, `@spll_icn`), процесс разметки WD-14 и схемы валидации.

Полное описание сбора, синтетического расширения (50 → 2500+ → 1172 эталонных картинки),
ручной модерации *Human-in-the-loop* и авто-разметки (WD-14 Tagger + LLaVA-7B) —
в [`business_plan/business_plan.md`](business_plan/business_plan.md).

## 1.1. Бизнес-контекст (`business_plan/`)

- **[`business_plan/business_plan.md`](business_plan/business_plan.md)** — бизнес-план:
  проблема, сбор и подготовка данных, продуктовые метрики.
- **[`business_plan/product_prototype.md`](business_plan/product_prototype.md)** —
  ключевая гипотеза, метрики (Acceptance Rate, KID, CLIP), объём MVP.
- **[`business_plan/product_benchmarking.md`](business_plan/product_benchmarking.md)** —
  конкурентный анализ (vs Scenario, Stability AI, аутсорс) и модель монетизации.


## 2. Бенчмарки бейзлайнов (`baseline/`)

7 Jupyter-ноутбуков, разделяющих зоны ответственности: движок авто-генерации сэмплов
через ComfyUI API, 5 baseline-сценариев (чистая база, Character/Props LoRA, ±LLM-расширение)
и финальный агрегатор результатов из MLflow. Подробности, таблица метрик и выводы —
в **[`baseline/README.md`](baseline/README.md)**.

**Ключевые инсайты, которые легли в продукт:**
- **LLM-расширение промптов вредит персонажам, но помогает пропсам** — поэтому в сервисе
  LLM-расширение сделано **опциональным тумблером** на стороне исполнителя.
- **Обе style-LoRA обучены без Mode Collapse** (LPIPS `0.65–0.69` при пороге коллапса `0.10`),
  KID улучшен на **42%** (персонажи) и **50%** (пропсы) относительно базы.
- Метрики **CLIP / LPIPS** из бенчмарков стали основой автоматического **QA-гейта** в сервисе.

## 3. Эксперименты MLflow (`mlflow/`)

`mlflow/mlruns.db` — портируемая SQLite-база всех прогонов. Тяжёлые артефакты
(`mlruns/`, `mlartifacts/`) намеренно вне git. Просмотр:

```bash
cd docs/mlflow
mlflow ui --backend-store-uri sqlite:///mlruns.db
# http://localhost:5000
```
