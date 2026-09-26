# Moscow Transport Hackathon

## Запуск полного demo-стека

```powershell
docker compose up --build
```

Backend автоматически применяет Alembic migrations при старте контейнера.

После запуска:

- frontend: http://localhost:3000
- backend Swagger: http://localhost:8000/docs
- liveness: http://localhost:8000/health/live

Backend подключает `tram-data` только на чтение. ML-контур (`ingest` и `ml-worker`) публикует `active.json` и Parquet атомарно. Если прогноза ещё нет, API не падает: `/api/v1/forecast/meta` возвращает `available: false`, а `/api/v1/forecast` возвращает `503 forecast_unavailable`.

## Backend API для frontend

Все endpoint’ы требуют Bearer access token пользователя, кроме health/auth endpoint’ов.

| Метод | URL | Назначение |
|---|---|---|
| GET | `/api/v1/forecast/meta` | активные runs, watermark, cutoff и stale-состояние |
| GET | `/api/v1/forecast` | прогноз/факт; параметры `date_from`, `date_to`, `routes`, `granularity` |
| POST | `/api/v1/forecast/preview` | draft-поправки без сохранения |
| GET | `/api/v1/scenarios` | сохранённые сценарии; чтение доступно USER |
| POST/PATCH/DELETE | `/api/v1/scenarios` | изменение сценариев; требуется ADMIN |

Поддерживаемые `granularity`: `hour`, `day`, `week`, `month`.

### Единая строка прогноза

```json
{
	"route": 7,
	"ts": "2026-10-01T10:00:00+03:00",
	"source": "forecast",
	"value": null,
	"yhat_model": 2410,
	"yhat": 1687,
	"q10": 1512,
	"q90": 1904,
	"estimated": false,
	"applied": []
}
```

- `actual`: факт находится только в `value`; `yhat_model`, `yhat`, квантили равны `null`.
- `forecast`/`forecast_seasonal`: `value` равен `null`, `yhat_model` является исходным прогнозом, `yhat` учитывает поправки.
- `mixed`: агрегированный период пересекает факт и прогноз; `value` содержит сумму факта, `yhat*` прогнозную часть.
- `availability: unavailable` означает отсутствие строки, это не нулевой пассажиропоток.

Приоритет источников: `actual` (final и не позже watermark) → `short` → `year` → unavailable.

### Preview

```json
POST /api/v1/forecast/preview
{
	"date_from": "2026-10-01T00:00:00+03:00",
	"date_to": "2026-10-01T23:00:00+03:00",
	"routes": [7],
	"model_factors": {"holiday": 0.7},
	"draft": [
		{
			"kind": "scenario",
			"factor": "route_shortened",
			"value": 0.7,
			"routes": [7],
			"date_from": "2026-10-01",
			"date_to": "2026-10-01",
			"days": "all"
		}
	]
}
```

Preview ничего не сохраняет. Факт не корректируется. Поправки применяются к почасовым строкам до агрегации.

## Инструкция для frontend-разработчиков

В `frontend/src/api/forecast.ts` находятся типы `ForecastRow`, `ForecastMeta`, `ForecastResponse` и функции API. Базовый URL задаётся через `VITE_API_URL`; по умолчанию используется относительный `/api/v1`, который проксирует nginx.

Локальный запуск frontend:

```powershell
cd frontend
npm ci
npm run dev
```

Для API вне Docker создайте `frontend/.env.local`:

```text
VITE_API_URL=http://localhost:8000/api/v1
```

UI должен отдельно обрабатывать состояния `loading`, `forecast_unavailable`, `stale`, `mixed`, `cold_start` и `availability: unavailable`. Не отображайте `value` как прогноз и не применяйте сценарии к строкам `source: actual`.

## Backend разработка

```powershell
cd backend
poetry install
poetry run alembic upgrade head
poetry run pytest -q
poetry run ruff check app tests
```

Прогнозный snapshot читается из `DATA_DIR` и обновляется каждые `BACKEND_RELOAD_SEC`. Новый run принимается только после проверки схемы, маршрутов, шага, timezone и `data_cutoff` short/year.

Подробный backlog реализации: [docs/ml-backend-implementation-plan.md](docs/ml-backend-implementation-plan.md).
