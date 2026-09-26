from typing import Literal

import numpy as np
import pandas as pd

from mtml.forecasters.chronos2 import Chronos2Forecaster

Pool = Literal["global", "route", "series"]


class XRegChronos:
    """Ridge по ковариатам в log1p, Chronos на остатках; pool — у кого общие коэффициенты."""

    def __init__(
        self,
        base: Chronos2Forecaster,
        covariates: pd.DataFrame,
        xreg_columns: tuple[str, ...],
        pool: Pool = "route",
        alpha: float = 1.0,
    ):
        self.base = base
        self.covariates = covariates
        self.xreg_columns = xreg_columns
        self.pool = pool
        self.alpha = alpha
        self.name = f"xreg_{pool}_{base.name}"

    def fit(self, history: pd.DataFrame):
        df = self._join(history)
        df["z"] = np.log1p(df["y"])
        df["series"] = df["route"].astype(str) + "_" + df["ts"].dt.hour.astype(str)
        df["group"] = {"global": "all", "route": df["route"].astype(str), "series": df["series"]}[
            self.pool
        ]

        rows = []
        for group, g in df.groupby("group"):
            beta = self._ridge(g)
            rows += [
                {"group": group, "feature": f, "beta": b}
                for f, b in zip(self.xreg_columns, beta, strict=True)
            ]
        self.coefficients = pd.DataFrame(rows)
        self.coefficients["effect_pct"] = (np.exp(self.coefficients["beta"]) - 1) * 100

        df["effect"] = self._effect(df)
        self.history = history
        # Chronos видит ряд без вклада ковариат, но с исходным уровнем и сезонностью
        self.base.fit(df.assign(y=df["z"] - df["effect"])[["route", "ts", "y"]])
        return self

    def predict(self, start: str | pd.Timestamp, end: str | pd.Timestamp):
        preds = self.base.predict(start, end)
        future = self._join(preds[["route", "ts"]])
        future["series"] = future["route"].astype(str) + "_" + future["ts"].dt.hour.astype(str)
        effect = self._effect(future).to_numpy()
        out = preds[["route", "ts"]].copy()
        # квантили монотонно переходят через expm1, медиана остаётся медианой
        for col in [c for c in preds.columns if c.startswith("q")] + ["yhat"]:
            out[col] = np.expm1(preds[col].to_numpy() + effect).clip(min=0)
        return out

    def _join(self, frame: pd.DataFrame):
        cols = ["route", "ts", *self.xreg_columns]
        merged = frame.merge(self.covariates[cols], on=["route", "ts"], how="left")
        if merged[list(self.xreg_columns)].isna().any().any():
            raise ValueError(f"Нет значений ковариат {list(self.xreg_columns)} для части точек")
        return merged

    def _ridge(self, g: pd.DataFrame):
        """Ridge с отдельным свободным членом у каждого ряда (внутригрупповое центрирование)."""
        cols = list(self.xreg_columns)
        x = g[cols].to_numpy(float) - g.groupby("series")[cols].transform("mean").to_numpy(float)
        z = (g["z"] - g.groupby("series")["z"].transform("mean")).to_numpy(float)
        return np.linalg.solve(x.T @ x + self.alpha * np.eye(len(cols)), x.T @ z)

    def _effect(self, frame: pd.DataFrame):
        key = {
            "global": pd.Series("all", index=frame.index),
            "route": frame["route"].astype(str),
            "series": frame["series"],
        }[self.pool]
        beta = self.coefficients.pivot(index="group", columns="feature", values="beta")[
            list(self.xreg_columns)
        ]
        b = beta.reindex(key.to_numpy()).to_numpy()
        return pd.Series(
            (frame[list(self.xreg_columns)].to_numpy(float) * b).sum(axis=1), index=frame.index
        )
