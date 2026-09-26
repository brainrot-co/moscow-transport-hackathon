import pandas as pd

from mtml.forecasters.base import Forecaster


class EnsembleForecaster:
    """Среднее прогнозов участников; квантили — среднее по тем участникам, у которых они есть.

    Участники работают с одной таблицей ковариат: её подмена (контрольные прогоны эффектов)
    действует на всех сразу.
    """

    def __init__(self, members: list[Forecaster]):
        self.members = members
        self.future_covariates = tuple(
            dict.fromkeys(c for m in members for c in getattr(m, "future_covariates", ()))
        )
        self.quantiles = tuple(sorted({q for m in members for q in getattr(m, "quantiles", ())}))
        self.name = "ensemble"

    @property
    def covariates(self):
        return self.members[0].covariates

    @covariates.setter
    def covariates(self, table: pd.DataFrame):
        for member in self.members:
            member.covariates = table

    def fit(self, history: pd.DataFrame):
        for member in self.members:
            member.fit(history)
        return self

    def predict(self, start: str | pd.Timestamp, end: str | pd.Timestamp):
        frames = [m.predict(start, end).set_index(["route", "ts"]) for m in self.members]
        out = pd.DataFrame({"yhat": sum(f["yhat"] for f in frames) / len(frames)})
        for column in sorted({c for f in frames for c in f.columns if c.startswith("q")}):
            with_column = [f[column] for f in frames if column in f.columns]
            out[column] = sum(with_column) / len(with_column)
        return out.reset_index().sort_values(["route", "ts"], ignore_index=True)
