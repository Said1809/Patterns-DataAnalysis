# Вариант 13 — Интерактивный анализ набора данных

Приложение для загрузки CSV/JSON, фильтрации продаж, построения сводок и графиков. Реализованы паттерны лабораторных работ 1–5 (как в примере варианта 16).

## Запуск

```bash
pip install -r requirements.txt
python main.py
```

По умолчанию загружается `data/sales.csv`. Можно открыть свой CSV/JSON кнопкой «Открыть CSV/JSON».

## Управление

- фильтры: регион, категория, канал
- метрика: `revenue` / `units`
- группировка: region / category / channel / product
- тип графика: bar / line / pie
- «Сохранить прототип» / «Загрузить прототип» — копирование запроса (Prototype)
- «Сохранить график» — экспорт PNG

## Паттерны

| ЛР | Паттерны | Где в коде |
|----|----------|------------|
| 1 | Singleton, Builder | `AppConfig`, `AnalysisQueryBuilder` |
| 2 | Abstract Factory, Prototype | `ChartFactory`, `AnalysisQuery.clone` |
| 3 | Adapter, Bridge | `Csv/JsonDatasetAdapter`, `Chart` + `ChartRenderer` |
| 4 | Composite, Decorator | `MetricGroup`, `StatsOverlayDecorator` |
| 5 | Facade, Flyweight | `AnalysisApp`, `StyleFlyweightFactory` |

Отчёты: `docs/lab1.md` … `docs/lab5.md`.
