import pandas as pd


def wape_score(y: pd.Series, yhat: pd.Series):
    total = y.sum()
    # в срезах без посадок (часы 2–3 ночи) WAPE не определён
    if total == 0:
        return float("nan")
    return max(0.0, 1.0 - float((y - yhat).abs().sum() / total))


def join_truth(preds: pd.DataFrame, truth: pd.DataFrame):
    """yhat обрезается в ≥ 0 и округляется, как при проверке на платформе."""
    df = truth.merge(preds, on=["route", "ts"], how="left", validate="1:1")
    if df["yhat"].isna().any():
        raise ValueError(f"В прогнозе нет {int(df['yhat'].isna().sum())} точек из эталона")
    df["yhat"] = df["yhat"].clip(lower=0).round()
    df["err"] = df["yhat"] - df["y"]
    return df


def evaluate(preds: pd.DataFrame, truth: pd.DataFrame):
    df = join_truth(preds, truth)

    def by(key: pd.Series):
        return {str(k): round(wape_score(g["y"], g["yhat"]), 4) for k, g in df.groupby(key)}

    day_y = df.groupby([df["route"], df["ts"].dt.normalize()])[["y", "yhat"]].sum()
    result = {
        "wape_score": round(wape_score(df["y"], df["yhat"]), 4),
        # насколько хорошо угадан дневной объём, без учёта распределения по часам
        "wape_score_daily_totals": round(wape_score(day_y["y"], day_y["yhat"]), 4),
        "mae": round(float(df["err"].abs().mean()), 2),
        # >0 — в сумме переоцениваем, <0 — недооцениваем
        "bias": round(float(df["err"].sum() / df["y"].sum()), 4),
        "by_route": by(df["route"]),
        "by_month": by(df["ts"].dt.month),
        "by_dow": by(df["ts"].dt.dayofweek),
        "by_hour": by(df["ts"].dt.hour),
    }
    if {"q0.1", "q0.9"}.issubset(df.columns):
        inside = (df["y"] >= df["q0.1"]) & (df["y"] <= df["q0.9"])
        result["coverage_80"] = round(float(inside.mean()), 4)
        result["interval_width_80"] = round(float((df["q0.9"] - df["q0.1"]).mean()), 2)
    return result


def daily_scores(preds: pd.DataFrame, truth: pd.DataFrame):
    df = join_truth(preds, truth)
    return df.groupby(df["ts"].dt.normalize()).apply(lambda g: wape_score(g["y"], g["yhat"]))
