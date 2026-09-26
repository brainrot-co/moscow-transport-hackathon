# План реализации ML-контура, Backend и Frontend

**Проект:** прогноз пассажиропотока трамвайных маршрутов
**Дата подготовки:** 26.09.2026
**Статус:** рабочий план реализации
**Базовый контракт:** [backend/ml-backend-contract.md](../backend/ml-backend-contract.md)

## Текущий прогресс

Реализованы и проверены:

- `ForecastSnapshot`, Parquet/JSON loader, атомарный `ForecastStore` и reload в lifespan;
- единая семантика `value`/`yhat_model`/`yhat`, приоритет `actual > short > year`;
- corrections engine, effects, draft preview и сценарная валидация;
- hour/day/week/month aggregation с явным `source: mixed`;
- `GET /forecast/meta`, `GET /forecast`, `POST /forecast/preview`;
- Scenario model, Alembic migration и CRUD endpoint’ы с USER/ADMIN RBAC;
- frontend API client/hook, dashboard data states, Dockerfile/nginx и общий compose;
- README-инструкции для backend/frontend.

Пока не завершены: справочники маршрутов/остановок, status/accuracy endpoint’ы, CSV/XLSX export, полноценная карта и UI CRUD сценариев. Они остаются следующими задачами по чек-листу ниже.

## 1. Цель

Собрать запускаемый через Docker веб-сервис, который:

- принимает и агрегирует выгрузки валидаций;
- строит краткосрочный и годовой прогнозы ML-воркером;
- безопасно публикует прогнозы через общий read-only том;
- отдаёт через FastAPI факт, прогноз, метаданные, маршруты, остановки и поправки;
- позволяет диспетчеру создавать сценарии и мгновенно просматривать их влияние;
- показывает данные на dashboard с графиками и картой;
- экспортирует результат в CSV/XLSX;
- переживает пустой том, неполные данные, сбой worker, устаревший прогноз и перезапуск backend.

План рассчитан на существующую структуру проекта. Уже реализованные части ML не переписываются без необходимости: основной объём работ находится в интеграции backend/frontend, контрактных тестах и production/demo compose.

## 2. Зафиксированные решения

### 2.1. Границы ответственности

| Компонент | Ответственность | Не делает |
|---|---|---|
| `ingest` | принимает CSV, дедуплицирует, строит raw/actuals/day status, двигает watermark | не строит прогноз |
| `ml-worker` | строит short/year forecast, effects, quality checks, публикует runs | не обслуживает HTTP |
| `backend` | читает ML snapshot, применяет поправки, агрегирует, авторизует и экспортирует | не запускает ML-инференс |
| `frontend` | dashboard, карта, фильтры, сценарии, графики, экспорт | не читает общий том |
| PostgreSQL | пользователи и сохранённые сценарии backend | не хранит ML-файлы |
| Redis | текущая инфраструктура auth/лимитирования | не является источником прогнозов |

ML и backend не вызывают друг друга по HTTP. Единственный контракт между ними: структура `/data`, `active.json`, JSON metadata и Parquet-файлы.

### 2.2. Формат годового прогноза

В документации описан годовой прогноз по дням, а текущий `ml/src/mtml/worker/year.py` фактически публикует почасовые строки. Для первой реализации выбрать **единую почасовую схему для short и year**:

- `forecasts.parquet` всегда содержит `route, ts, yhat, q10, q90`;
- `short` покрывает почасовой горизонт 61 день;
- `year` покрывает почасовой горизонт 365 дней либо используется как почасовой fallback за границей short;
- backend агрегирует почасовые строки в день/неделю/месяц;
- `meta.horizon.step` для обоих run равен `hour`.

Если размер годового файла станет неприемлемым, это оформляется отдельной версией схемы, а не скрытым изменением текущего API.

### 2.3. Время

Все расчёты используют `Europe/Moscow` без смешивания naive и aware timestamp. В demo «сейчас» берётся из `/data/state/clock.json`; системное время используется только в production-режиме при отсутствии виртуальных часов.

### 2.4. Источники данных

Для каждой строки ответа используется единая схема. Поле `value` предназначено только для фактического значения, а поля `yhat_model` и `yhat` — только для прогноза:

```json
{
  "route": 7,
  "ts": "2026-10-01T10:00:00+03:00",
  "source": "actual",
  "value": 120,
  "yhat_model": null,
  "yhat": null,
  "q10": null,
  "q90": null,
  "estimated": false,
  "applied": []
}
```

Для прогнозной строки `value` равен `null`, `yhat_model` содержит исходное значение модели, а `yhat` — значение после поправок. Для фактической строки используется исключительно `value`; поправки к факту не применяются.

Детерминированный приоритет источника для каждой строки маршрут × час:

1. `actual`, если timestamp не позже watermark и день имеет статус `final`;
2. `forecast`, если валидная строка есть в short run;
3. `forecast_seasonal`, если валидной строки в short нет, но она есть в year run;
4. отсутствие прогноза, если оба run не содержат валидную строку. Ноль не подставляется.

Если short и year содержат один и тот же timestamp, short всегда имеет приоритет. При загрузке snapshot backend обязан проверить, что short и year имеют совместимые `schema_version`, временную зону, формат шага, набор маршрутов и согласованный цикл данных (`data_cutoff`/watermark). Несовместимый run не участвует в выборе источника, а предыдущий рабочий snapshot сохраняется.

`partial` до watermark не показывается как факт: для него используется прогноз. Факт никогда не корректируется сценариями.

## 3. Текущее состояние и разрыв до цели

### Уже есть

- FastAPI-приложение, health, JWT auth, users, PostgreSQL и Redis.
- ML ingest с SHA-256 дедупликацией и ключом raw-валидации.
- Агрегация `actuals_hourly.parquet`, `day_status.parquet` и watermark.
- Chronos/наивные forecaster’ы, short/year worker, effects, quality и atomic publish.
- Общий том `tram-data` и demo clock.
- React 19 + TypeScript + Vite и базовый dashboard shell.
- Документы контракта, поправок и integration guide.

### Не хватает

- Backend `ForecastStore`, загрузчика Parquet/JSON и фонового reload.
- Backend API прогноза, маршрутов, остановок, статуса, факторов и экспорта.
- Таблицы/CRUD сценариев и RBAC для их изменения.
- Формулы применения model factors и scenario multipliers.
- Общего production/demo compose, подключения `tram-data:ro` и frontend proxy.
- Frontend API-клиента, реальных состояний загрузки и данных графиков/карты.
- `reference/correction_factors.json` в поставляемом demo-наборе.
- Интеграционных, контрактных, нагрузочных и end-to-end тестов.
- Инструкции жюри и честных измерений производительности в README.

### Критические несоответствия, которые устранить до реализации API

1. **Годовой шаг:** закрепить единый `hour`, как указано выше, и синхронно проверить worker, contract и schemas.
2. **Формат факторов:** использовать форму из `backend/corrections-spec.md` (`model_factors`, `scenario_types`) и возвращать `schema_version`.
3. **Роутинг:** все новые endpoint’ы регистрировать под существующим `/api/v1`; health оставить под `/health`.
4. **Пустой том:** отсутствие `active.json` является штатным состоянием `forecast_unavailable`, а не причиной падения приложения.
5. **Авторизация:** чтение dashboard доступно роли `USER`, изменение сценариев только `ADMIN` или отдельной роли dispatcher.

## 4. Целевая архитектура

```text
CSV -> /data/inbox -> ingest -> raw/actuals/status/watermark
                                      |
                                      v
                                ml-worker
                         -> runs/<id> + active.json
                                      |
                                      v  read-only
             PostgreSQL <-> backend ForecastStore -> REST API -> React dashboard
                                      |
                                      +-> CSV/XLSX export
```

### 4.1. Backend-слои

Предлагаемая структура:

```text
backend/app/
  api/v1/endpoints/
    forecast.py
    routes.py
    scenarios.py
    corrections.py
    status.py
    exports.py
  ml/
    models.py             # внутренние snapshot-модели
    store.py              # immutable active snapshot
    loader.py             # JSON/Parquet loading and validation
    aggregation.py        # hour/day/week/month
    corrections.py        # effects and scenarios formula
    references.py         # routes/stops/factors
  schemas/
    forecast.py
    route.py
    scenario.py
    correction.py
    status.py
    common.py
  services/
    forecast_service.py
    scenario_service.py
    export_service.py
  crud/
    scenario.py
  models/
    scenario.py
```

`ForecastStore` загружает данные в память и отдаёт неизменяемый snapshot. Reload строит новый snapshot рядом со старым, валидирует его и только потом заменяет ссылку. HTTP-запросы никогда не видят частично загруженный run.

### 4.2. Что хранить в памяти

- активные `short` и `year` forecasts;
- `effects.parquet` short;
- `meta.json` обоих run;
- `active.json`;
- actuals и day status;
- watermark, clock, worker status;
- routes, stops, correction reference;
- индекс по `(route, ts)` и `(route, date, factor)` для быстрого фильтра.

Parquet загружается через `pyarrow`/`pandas` или другой согласованный columnar reader. Нельзя читать файлы с диска на каждый API-запрос.

### 4.3. Жизненный цикл приложения

В `backend/app/lifespan.py` добавить:

1. создание DB/Redis как сейчас;
2. создание `ForecastStore(DATA_DIR)`;
3. начальную загрузку snapshot;
4. запуск background reload task с `BACKEND_RELOAD_SEC`;
5. корректную остановку task и освобождение ресурсов.

Ошибка начальной загрузки не должна ломать backend: store стартует в состоянии `not_ready`, health сообщает причину, а API прогноза возвращает понятный `503 forecast_unavailable`.

## 5. REST API

Ниже приведён целевой контракт. Все даты передаются в ISO-8601, все интервалы дат включительные, если не указано обратное. Для больших выборок обязателен лимит периода и/или pagination.

### 5.1. Health

Существующие endpoint’ы сохранить:

| Метод | URL | Ответ |
|---|---|---|
| `GET` | `/health/live` | процесс жив |
| `GET` | `/health/ready` | DB, Redis и состояние обязательных зависимостей |

Расширить readiness так, чтобы отсутствие forecast snapshot не делало auth-сервис недоступным. Добавить отдельный статус ML в `/api/v1/status`.

### 5.2. Общие правила ответа и ошибки

Успешный ответ должен содержать `schema_version`, где это применимо. Ошибки FastAPI привести к единой форме:

```json
{
  "error": {
    "code": "invalid_date_range",
    "message": "date_to must be greater than or equal to date_from",
    "details": {}
  }
}
```

Минимальные коды: `invalid_params`, `not_found`, `forecast_unavailable`, `forecast_stale`, `unsupported_granularity`, `scenario_overlap_warning`, `internal_error`.

### 5.3. Forecast metadata

`GET /api/v1/forecast/meta`

Назначение: инициализация dashboard и отображение доверия к данным.

Ответ:

```json
{
  "schema_version": 1,
  "available": true,
  "short_run_id": "short-...",
  "year_run_id": "year-...",
  "published_at": "2025-11-02T03:01:05",
  "watermark": "2025-10-31",
  "data_cutoff": "2025-10-31",
  "now": "2025-11-01T03:00:00",
  "model": {"short": "chronos2...", "year": "seasonal"},
  "horizons": {"short_end": "2025-12-31T23:00:00", "year_end": "2026-10-31T23:00:00"},
  "cold_start_routes": [5],
  "stale": false,
  "worker": {"last_success_at": "...", "last_error": null},
  "quality": {"wape": 0.89}
}
```

При пустом или невалидном snapshot возвращать `200` с `available: false`, если метаданные состояния можно прочитать; прогнозный endpoint при этом возвращает `503`.

### 5.4. Forecast data

`GET /api/v1/forecast`

Параметры:

| Параметр | Тип | Обязательность | Правило |
|---|---|---:|---|
| `date_from` | date/datetime | да | начало периода |
| `date_to` | date/datetime | да | конец периода |
| `routes` | `int[]` | нет | по умолчанию все доступные |
| `granularity` | enum | да | `hour`, `day`, `week`, `month` |
| `include_actual` | bool | нет | по умолчанию true |
| `include_quantiles` | bool | нет | имеет смысл для hour |
| `corrections` | enum | нет | `saved` или `none`, default `saved` |
| `scenario_ids` | UUID[] | нет | дополнительные сохранённые сценарии |
| `limit` | int | нет | защитный лимит строк |

Ответ:

```json
{
  "schema_version": 1,
  "query": {"date_from": "...", "date_to": "...", "granularity": "day"},
  "data": [
    {
      "route": 7,
      "ts": "2025-11-19",
      "source": "forecast",
      "value": null,
      "yhat_model": 24100,
      "yhat": 16870,
      "q10": null,
      "q90": null,
      "estimated": false,
      "applied": []
    }
  ],
  "meta": {"watermark": "2025-10-31", "stale": false}
}
```

Правила:

- для `actual` значение факта находится только в `value`, а `yhat_model`, `yhat`, `q10` и `q90` равны `null`;
- для `forecast` и `forecast_seasonal` `value` равен `null`, `yhat_model` показывает исходный прогноз, а `yhat` — итог после поправок;
- для остановки значение считается как `route_yhat * weight`, `estimated: true`;
- для маршрута из `cold_start_routes` не выдавать ложный ноль: отдавать `availability: cold_start` и использовать agreed fallback только если он опубликован worker’ом;
- агрегирование выполняется после выбора источника и применения поправок к прогнозным часовым строкам;
- порядок выбора источника: `actual` (final и не позже watermark) → `short` → `year` → отсутствие строки;
- при отсутствии строки в обоих run возвращается `availability: unavailable`, а не нулевое значение;
- квантили не складывать при агрегации, на `day/week/month` возвращать `null` или отдельный интервал, если он будет реализован.

### 5.5. Preview без сохранения

`POST /api/v1/forecast/preview`

Принимает тот же период и фильтры, что `/forecast`, плюс draft-поправки. Endpoint не пишет ни в PostgreSQL, ни в ML volume.

```json
{
  "date_from": "2025-11-17",
  "date_to": "2025-11-23",
  "routes": [7],
  "granularity": "day",
  "model_factors": {"holiday": 0.7, "school_holiday": 1.0},
  "draft": [
    {
      "kind": "scenario",
      "factor": "route_shortened",
      "value": 0.7,
      "routes": [7],
      "date_from": "2025-11-18",
      "date_to": "2025-11-22",
      "days": "weekdays",
      "hour_from": null,
      "hour_to": null
    }
  ]
}
```

Возвращать обычный forecast response, `persisted: false`, предупреждения о пересечениях и список применённых draft/saved corrections.

### 5.6. Маршруты и остановки

| Метод | URL | Назначение |
|---|---|---|
| `GET` | `/api/v1/routes` | список маршрутов, поиск и pagination |
| `GET` | `/api/v1/routes/{route_id}` | карточка маршрута |
| `GET` | `/api/v1/routes/{route_id}/stops` | остановки с порядком, координатами и weight |

Источники: `reference/routes.parquet`, `reference/stops.parquet`. Ответ остановки должен включать `estimated: true` для пассажиропотока, потому что исходные валидации не содержат реального места посадки.

Опционально добавить:

- `GET /api/v1/routes/map` для геометрии, если geometry появится в справочнике;
- фильтры `active`, `search`, `bbox`.

### 5.7. Поправки и reference

`GET /api/v1/corrections/reference`

Источник: `reference/correction_factors.json`. Возвращает:

- `model_factors`: holiday, school_holiday, диапазон, step, default, описание;
- `scenario_types`: route_closed, route_shortened, heavy_rain, heavy_snow, mass_event, custom;
- provenance/estimate/source для каждого экспертного множителя.

`GET /api/v1/corrections/model-effects`

Параметры: `date_from`, `date_to`, `routes`, `factor`. Возвращает `log_effect`, `yhat_without` и пояснение для панели фактора.

### 5.8. Сценарии

| Метод | URL | Auth | Назначение |
|---|---|---|---|
| `GET` | `/api/v1/scenarios` | USER | список с фильтрами `active`, `from`, `to`, `route` |
| `POST` | `/api/v1/scenarios` | ADMIN/dispatcher | создать |
| `GET` | `/api/v1/scenarios/{id}` | USER | получить |
| `PATCH` | `/api/v1/scenarios/{id}` | ADMIN/dispatcher | изменить/включить/выключить |
| `DELETE` | `/api/v1/scenarios/{id}` | ADMIN/dispatcher | удалить или soft-delete |

Модель `scenarios`:

- `id UUID`;
- `kind: model_factor | scenario`;
- `factor`;
- `value: 0..2`;
- `routes: int[] | null`;
- `date_from`, `date_to`;
- `days: all | weekdays | weekends`;
- `hour_from`, `hour_to`;
- `title`, `comment`, `source_url`;
- `active`;
- `created_by`, `created_at`, `updated_at`.

Валидации: корректный диапазон дат, часы 0..23, маршруты из reference либо явное предупреждение, `value` в допустимом диапазоне, обязательный `factor` из reference. Удаление лучше реализовать как soft-delete или аудитируемое выключение.

### 5.9. Status и ingestion

| Метод | URL | Ответ |
|---|---|---|
| `GET` | `/api/v1/status` | сводный статус всей системы |
| `GET` | `/api/v1/data/status` | watermark, latest_data, final/partial/missing |
| `GET` | `/api/v1/data/batches` | последние batch’и из `ingestion/batches.parquet` |
| `GET` | `/api/v1/worker/status` | last success/error, active runs, quality |
| `GET` | `/api/v1/accuracy` | `monitoring/accuracy.parquet` для dashboard |

Секреты, traceback и внутренние пути в API не возвращать.

### 5.10. Export

`GET /api/v1/exports/forecast.csv`
`GET /api/v1/exports/forecast.xlsx`

Параметры совпадают с `/forecast`. Экспорт содержит:

- маршрут, timestamp/период;
- источник (`actual`, `forecast`, `forecast_seasonal`);
- `model_forecast`;
- `adjusted_forecast`;
- q10/q90 только для почасового результата;
- `estimated`;
- применённые сценарии и их множители;
- watermark и run id в metadata/заголовках.

XLSX генерировать в памяти с ограничением периода и `Content-Disposition`. Для больших выборок CSV предпочтительнее. Экспорт не должен блокировать event loop: тяжёлую сериализацию выполнять в threadpool.

## 6. Формула поправок

Для каждой будущей строки маршрут × час:

$$
yhat_{adj} = yhat \\times \\prod_f \\exp(log\_effect_f \\times (k_f - 1)) \\times \\prod_s m_s
$$

где:

- `k_f` — сила model factor, по умолчанию `1.0`;
- `m_s` — scenario multiplier, например `0.7` для сокращения маршрута;
- отсутствующий `log_effect` даёт множитель `1`;
- пересекающиеся сценарии перемножаются;
- результат ограничивается снизу нулём;
- q10/q90 умножаются на тот же общий множитель;
- после поправок выполняется агрегация.

Нужны unit-тесты на нулевой/единичный множитель, пересечение сценариев, будни/выходные, часы, маршрут `null`, границы дат и факт до watermark.

## 7. Схема базы и миграции

Добавить `backend/app/models/scenario.py`, Pydantic schemas и Alembic migration.

Индексы:

- `active`;
- `date_from`, `date_to`;
- `created_by`;
- при необходимости GIN по `routes`.

Не хранить прогнозы и Parquet в PostgreSQL. PostgreSQL хранит только пользовательские сценарии и аудит их изменений. Миграция должна быть обратимой в рамках принятого процесса проекта.

## 8. Frontend-план

### 8.1. API и состояние

Добавить:

```text
frontend/src/api/client.ts
frontend/src/api/forecast.ts
frontend/src/api/routes.ts
frontend/src/api/scenarios.ts
frontend/src/api/status.ts
frontend/src/types/api.ts
frontend/src/hooks/useForecast.ts
frontend/src/hooks/useScenarios.ts
```

Минимальный client:

- базовый URL из `VITE_API_URL`;
- credentials/cookie и Bearer flow согласно существующему auth;
- единый разбор API errors;
- AbortController для смены фильтров;
- timeout и retry только для безопасных GET;
- cache последнего успешного snapshot, чтобы график не исчезал при кратком reload.

### 8.2. Dashboard

Сохранить существующий `/dashboard`, но заменить статические данные на API:

1. header: время системы, watermark, published_at, stale badge;
2. фильтры: дата/период, маршрут, остановка, гранулярность;
3. KPI: текущий факт/прогноз, пик, top routes, качество;
4. график: модель и итог с поправками, actual/forecast разными стилями;
5. карта: маршрут/остановки, цвет по нагрузке, tooltip по timestamp;
6. панель факторов модели;
7. список сохранённых сценариев;
8. форма draft-сценария и preview;
9. экспорт CSV/XLSX;
10. состояния loading, empty, error, stale, cold-start и partial/anomaly.

Не показывать пользователю значения остановок как точный факт: рядом должно быть обозначение оценки.

### 8.3. Map

Выбрать и зафиксировать одну библиотеку карт, совместимую с лицензией и demo-средой. Для первой версии достаточно:

- координат stops.parquet;
- линии/точки остановок;
- выделения выбранного маршрута;
- цвета по значению прогнозной нагрузки;
- синхронизации карты и графика;
- корректного empty/error состояния без пустого «декоративного» контейнера.

### 8.4. Сценарии UX

- изменение slider вызывает `/forecast/preview` с debounce;
- сохранение вызывает `POST /scenarios`, после чего перезагружается forecast;
- «Модель»/«С поправками» переключает `corrections=none/saved`;
- пересечения показываются предупреждением до сохранения;
- сценарий в прошлом не меняет факт;
- cold-start и stale видны в интерфейсе явно.

## 9. Docker и конфигурация

### Корневой `docker-compose.yml`

Раскомментировать и довести до рабочего состояния:

- `backend` собирается из `./backend`;
- `DATA_DIR=/data`;
- `tram-data:/data:ro`;
- порт `8000`;
- зависимости на DB, Redis и ML volume readiness;
- `frontend` собирается из `./frontend` и публикуется через nginx;
- frontend получает API base URL через build/runtime config.

### Backend image

Добавить в backend dependencies:

- `pyarrow`;
- `pandas` или согласованный минимальный reader;
- `openpyxl` для XLSX;
- при необходимости `orjson`.

Сохранить Python `>=3.12`, ruff/black/mypy style проекта.

### Demo

Проверить сценарий:

```text
docker compose -f docker-compose.yml -f compose.demo.yml up --build
```

В demo backend должен использовать virtual clock, переживать первоначальное отсутствие `active.json` и после начальной загрузки автоматически увидеть новый run.

### Настройки backend

Добавить в settings:

| Переменная | Default | Назначение |
|---|---:|---|
| `DATA_DIR` | `/data` | read-only ML volume |
| `BACKEND_RELOAD_SEC` | `30` | период reload active.json |
| `STALE_AFTER_DAYS` | `3` | порог stale |
| `MAX_FORECAST_DAYS` | `365` | защита API |
| `CORS_ORIGINS` | demo value | origin frontend |
| `EXPORT_MAX_ROWS` | agreed limit | защита экспорта |

## 10. Порядок реализации

### Этап 0. Контракт и baseline

- [ ] подтвердить почасовой формат year;
- [ ] зафиксировать JSON response forecast и error envelope;
- [ ] создать `reference/correction_factors.json` в demo data;
- [ ] проверить фактические колонки всех Parquet после запуска ML;
- [ ] определить диапазон demo и список маршрутов.

**Результат:** backend и frontend разрабатываются по одной схеме.

### Этап 1. Backend ML storage

- [ ] добавить зависимости Parquet/XLSX;
- [ ] реализовать typed internal models;
- [ ] реализовать loader с проверками schema_version, columns, dtypes, uniqueness;
- [ ] реализовать `ForecastStore` и atomic snapshot swap;
- [ ] подключить store к lifespan/reload task;
- [ ] обработать empty/corrupt/stale snapshot;
- [ ] покрыть loader/store unit-тестами.

**Результат:** backend умеет безопасно читать активный ML run независимо от API.

### Этап 2. Backend forecast engine

- [ ] реализовать timezone/virtual clock helper;
- [ ] реализовать source resolution с приоритетом `actual > short > year > unavailable`;
- [ ] реализовать единую схему строки: факт только в `value`, прогноз только в `yhat_model/yhat`;
- [ ] валидировать совместимость short/year по schema, timezone, шагу, маршрутам и data cutoff;
- [ ] реализовать hour/day/week/month aggregation;
- [ ] реализовать stop weights;
- [ ] реализовать correction formula;
- [ ] добавить мета-информацию и applied corrections;
- [ ] добавить `forecast/meta`, `forecast`, `forecast/preview`;
- [ ] добавить contract tests на JSON.

**Результат:** работающий read-only forecast API.

### Этап 3. Сценарии и статус

- [ ] добавить Scenario model и Alembic migration;
- [ ] добавить Pydantic validation и CRUD;
- [ ] добавить RBAC;
- [ ] добавить reference/model effects endpoints;
- [ ] добавить data/worker/status/accuracy endpoints;
- [ ] добавить предупреждения пересечений и прошлых событий.

**Результат:** сохранённые поправки и наблюдаемость системы.

### Этап 4. Экспорт

- [ ] переиспользовать forecast service для CSV/XLSX;
- [ ] добавить лимиты, streaming/threadpool и Content-Disposition;
- [ ] проверить кириллицу, timezone, целочисленное округление и applied corrections;
- [ ] добавить тест скачивания и открытия XLSX.

### Этап 5. Frontend integration

- [ ] добавить API client/types/hooks;
- [ ] подключить auth и обработку refresh;
- [ ] заменить hardcoded dashboard data;
- [ ] реализовать график actual/model/adjusted;
- [ ] реализовать фильтры и granularities;
- [ ] реализовать карту stops/routes;
- [ ] реализовать factors/scenarios/preview/save;
- [ ] реализовать status/stale/cold-start/error states;
- [ ] подключить export buttons и toast/error feedback.

### Этап 6. Compose и demo

- [ ] собрать единый stack;
- [ ] проверить volume read-only;
- [ ] проверить service health и restart;
- [ ] проверить пустой том, новый batch, новый run и reload;
- [ ] добавить README с командами запуска и URL.

### Этап 7. Performance и сдача

- [ ] добавить нагрузочный сценарий для `/forecast`;
- [ ] измерить p50/p95/p99, RPS, RAM, CPU;
- [ ] проверить короткий/длинный период и размер ответа;
- [ ] записать результаты в README;
- [ ] собрать ссылки на ML artifacts, внешние источники и архитектурную схему;
- [ ] провести demo rehearsal по сценарию диспетчера.

## 11. Тестовая стратегия

### ML regression

Существующие тесты ML сохранить и расширить проверками:

- схема опубликованного short/year;
- atomic publish и rollback;
- monotonic watermark;
- dedupe одного и повторного файла;
- partial/final/missing;
- cold-start;
- качество и отсутствие отрицательных forecast;
- соответствие `active.json` папкам runs.

### Backend unit

- timestamp normalization;
- source resolution и конфликт short/year;
- единую семантику `value`/`yhat_model`/`yhat` для actual и forecast;
- aggregation;
- correction formula;
- route stop weight;
- stale calculation;
- schema validation;
- empty/corrupted files;
- scenario overlap and bounds.

### Backend integration

- `GET /forecast/meta` с fixture volume;
- reload после замены `active.json`;
- старый snapshot при повреждённом новом run;
- forecast with/without corrections;
- preview не создаёт записи;
- RBAC scenarios;
- CSV/XLSX response;
- auth/health regression.

### Frontend

- TypeScript build и ESLint;
- API error/loading/empty states;
- переключение corrections;
- debounce preview;
- filter changes and abort;
- rendering of actual/forecast/stale/cold-start;
- mobile/desktop smoke test.

### E2E demo сценарий

1. Запустить compose с пустым/начальным томом.
2. Убедиться, что frontend открывается, а dashboard показывает «прогноз ещё не готов».
3. Дождаться ingest и worker.
4. Проверить смену run в `active.json` и reload backend.
5. Выбрать маршрут и период.
6. Создать draft ремонта и увидеть изменение графика.
7. Сохранить сценарий и проверить новый forecast.
8. Выгрузить CSV/XLSX.
9. Перезапустить backend и убедиться в восстановлении snapshot.

## 12. Производительность и ограничения

Целевой backend должен держать активный ML snapshot в памяти и не читать Parquet в request path. До финального замера нельзя заявлять соответствие p95/RPS.

Измерять минимум:

- `/health/live` baseline;
- `/api/v1/forecast` для одного маршрута/дня;
- `/forecast` для всех маршрутов/месяца;
- `/forecast` для всех маршрутов/года;
- `/forecast/preview` с несколькими сценариями;
- export CSV/XLSX отдельно.

Фиксировать: число маршрутов, строк в ответе, concurrency, CPU, RAM, p50/p95/p99, error rate. Нагрузка должна использовать production-like Docker limits.

Ограничения первой версии:

- stop values являются оценкой через `weight`, а не реальными посадками на остановке;
- перенос пассажиров между маршрутами не моделируется автоматически;
- сценарии не обучают ML и не меняют исторический факт;
- погодный сценарий вводится вручную, если автоматический источник не подключён;
- за пределами year horizon данных нет;
- годовой forecast наследует ограничение выбранного почасового формата;
- качество зависит от полноты и задержек валидаций.

## 13. Definition of Done

Реализация считается готовой, когда:

- [ ] `docker compose ... up --build` поднимает ingest, worker, backend, frontend, DB и Redis;
- [ ] backend читает общий том только `:ro`;
- [ ] пустой том не вызывает crash-loop;
- [ ] active run загружается при старте и после reload;
- [ ] повреждённый новый run не заменяет рабочий старый;
- [ ] `/api/v1/forecast` отдаёт actual/forecast/seasonal с корректным source;
- [ ] работают час/день/неделя/месяц и маршрут/остановка;
- [ ] model factors и scenarios применяются до агрегации;
- [ ] preview ничего не сохраняет;
- [ ] сценарии защищены RBAC и миграцией;
- [ ] frontend показывает график, карту, факторы, сценарии и stale/error states;
- [ ] CSV и XLSX содержат model и adjusted значения;
- [ ] есть тесты на основной путь и сбои;
- [ ] README содержит URL, команды, API, архитектуру, внешние источники и реальные performance measurements.

## 14. Открытые решения перед стартом разработки

1. Нужна ли отдельная роль `dispatcher`, или достаточно `ADMIN` для CRUD сценариев?
2. Должны ли сценарии быть общими для всех пользователей или поддерживать личный draft?
3. Какой картографический провайдер разрешён для demo и поставки?
4. Оставляем ли year почасовым навсегда или готовим schema v2 для дневного файла?
5. Какой fallback разрешён для cold-start: наивный прогноз из worker или явный `no_data`?
6. Какие внешние источники реально подключаются в финальной версии: календарь, погода, трафик, события?
7. Какой максимальный диапазон разрешить в interactive forecast и export?
8. Нужна ли запись фактической accuracy после каждого нового final дня в backend API или достаточно `monitoring/accuracy.parquet`?

До ответа на эти вопросы можно начинать этапы 0–2, потому что они не блокируют базовый loader и read-only forecast API. Ответы обязательны до реализации UX сценариев, compose production и финального README.
