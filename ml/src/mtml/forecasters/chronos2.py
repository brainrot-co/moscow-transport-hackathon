from typing import Literal

import pandas as pd
import torch

from mtml.forecasters.base import check_contiguous, horizon_hours

# route_hour_daily — 216 дневных рядов с горизонтом 61 шаг вместо почасового ряда на 1464 шага:
# так прогноз не уходит за штатный горизонт модели и не деградирует к концу
Layout = Literal["hourly", "route_hour_daily"]


def default_device():
    if torch.cuda.is_available():
        return "cuda"
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"


class Chronos2Forecaster:
    def __init__(
        self,
        layout: Layout = "hourly",
        model_id: str = "amazon/chronos-2",
        device: str | None = None,
        context_length: int | None = None,
        cross_learning: bool = False,
        quantiles: tuple[float, ...] = (0.1, 0.5, 0.9),
        batch_size: int = 256,
        covariates: pd.DataFrame | None = None,
        past_covariates: tuple[str, ...] = (),
        future_covariates: tuple[str, ...] = (),
    ):
        wanted = past_covariates + future_covariates
        if wanted and covariates is None:
            raise ValueError(f"Заданы ковариаты {list(wanted)}, но не передана таблица covariates")
        missing = [c for c in wanted if c not in covariates.columns] if wanted else []
        if missing:
            raise ValueError(f"В таблице covariates нет колонок {missing}")
        self.layout = layout
        self.model_id = model_id
        self.device = device or default_device()
        self.context_length = context_length
        self.cross_learning = cross_learning
        self.quantiles = quantiles
        self.batch_size = batch_size
        self.covariates = covariates
        self.past_covariates = past_covariates
        self.future_covariates = future_covariates
        suffix = "_xl" if cross_learning else ""
        ctx = f"_ctx{context_length}" if context_length else ""
        cov = ("_fc" if future_covariates else "") + ("_pc" if past_covariates else "")
        self.name = f"chronos2_{layout}{ctx}{suffix}{cov}"
        self._pipeline = None

    @property
    def pipeline(self):
        if self._pipeline is None:
            from chronos import Chronos2Pipeline

            self._pipeline = Chronos2Pipeline.from_pretrained(self.model_id, device_map=self.device)
        return self._pipeline

    def fit(self, history: pd.DataFrame):
        # zero-shot: обучения нет, история — это контекст для прогноза
        self.history = history
        return self

    def predict(self, start: str | pd.Timestamp, end: str | pd.Timestamp):
        check_contiguous(self.history, start)
        hours = horizon_hours(start, end)
        grid = pd.MultiIndex.from_product(
            [self.history["route"].unique(), hours], names=["route", "ts"]
        )
        context = self._with_covariates(self.history, self.past_covariates + self.future_covariates)
        future = self._with_covariates(grid.to_frame(index=False), self.future_covariates)
        if self.layout == "hourly":
            to_chronos = {"route": "item_id", "ts": "timestamp"}
            context, future = context.rename(columns=to_chronos), future.rename(columns=to_chronos)
            prediction_length, freq = len(hours), "h"
        else:
            context, future = self._daily_layout(context), self._daily_layout(future)
            prediction_length, freq = len(hours) // 24, "D"

        raw = self.pipeline.predict_df(
            context,
            # колонки, которых нет в future_df, Chronos считает прошлыми ковариатами
            future_df=future if self.future_covariates else None,
            id_column="item_id",
            timestamp_column="timestamp",
            target="y",
            prediction_length=prediction_length,
            quantile_levels=list(self.quantiles),
            batch_size=self.batch_size,
            context_length=self.context_length,
            cross_learning=self.cross_learning,
            freq=freq,
        )
        return self._to_canonical(raw)

    def _with_covariates(self, frame: pd.DataFrame, columns: tuple[str, ...]):
        if not columns:
            return frame
        # признаки бывают общими на город (только ts) и по маршрутам (route + ts)
        keys = ["route", "ts"] if "route" in self.covariates.columns else ["ts"]
        merged = frame.merge(self.covariates[[*keys, *columns]], on=keys, how="left")
        missing = merged[list(columns)].isna().any(axis=1)
        if missing.any():
            raise ValueError(
                f"Нет значений ковариат {list(columns)} для {int(missing.sum())} точек, "
                f"первая {merged.loc[missing, 'ts'].min()}"
            )
        return merged

    @staticmethod
    def _daily_layout(frame: pd.DataFrame):
        return frame.drop(columns=["route", "ts"]).assign(
            item_id=frame["route"].astype(str) + "_" + frame["ts"].dt.hour.astype(str),
            timestamp=frame["ts"].dt.normalize(),
        )

    def _to_canonical(self, raw: pd.DataFrame):
        out = pd.DataFrame()
        if self.layout == "hourly":
            out["route"] = raw["item_id"].astype(int)
            out["ts"] = pd.to_datetime(raw["timestamp"])
        else:
            route_hour = raw["item_id"].str.split("_", expand=True).astype(int)
            out["route"] = route_hour[0]
            out["ts"] = pd.to_datetime(raw["timestamp"]) + pd.to_timedelta(route_hour[1], unit="h")
        for q in self.quantiles:
            out[f"q{q}"] = raw[str(q)].clip(lower=0).to_numpy()
        # медиана минимизирует сумму абсолютных ошибок, т.е. WAPE
        out["yhat"] = out["q0.5"]
        return out.sort_values(["route", "ts"], ignore_index=True)
