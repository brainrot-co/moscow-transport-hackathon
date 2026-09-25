import matplotlib.pyplot as plt
import pandas as pd

from mtml.metrics import join_truth, wape_score

DOW = ["пн", "вт", "ср", "чт", "пт", "сб", "вс"]


def _route_grid(routes: list[int]):
    ncols = 3
    nrows = -(-len(routes) // ncols)
    fig, axes = plt.subplots(nrows, ncols, figsize=(16, 3.2 * nrows), sharex=True)
    return fig, list(axes.ravel())


def daily_totals(
    preds: pd.DataFrame,
    truth: pd.DataFrame,
    history: pd.DataFrame | None = None,
    history_days: int = 56,
):
    df = join_truth(preds, truth)
    routes = sorted(df["route"].unique())
    fig, axes = _route_grid(routes)
    for ax, route in zip(axes, routes, strict=False):
        g = df[df["route"] == route].groupby(df["ts"].dt.normalize())[["y", "yhat"]].sum()
        if history is not None:
            h = history[history["route"] == route]
            h = h[h["ts"] >= h["ts"].max().normalize() - pd.Timedelta(days=history_days - 1)]
            ax.plot(
                h.groupby(h["ts"].dt.normalize())["y"].sum(), color="0.6", lw=1, label="история"
            )
        ax.plot(g.index, g["y"], color="k", lw=1.2, label="факт")
        ax.plot(g.index, g["yhat"], color="C1", lw=1.2, label="прогноз")
        ax.set_title(f"маршрут {route}: score {wape_score(g['y'], g['yhat']):.3f}", fontsize=10)
        ax.tick_params(axis="x", labelrotation=45, labelsize=8)
    for ax in axes[len(routes) :]:
        ax.axis("off")
    axes[0].legend(fontsize=8)
    fig.suptitle("Дневные суммы посадок")
    fig.tight_layout()
    return fig


def forecast_overview(preds: pd.DataFrame, history: pd.DataFrame, history_days: int = 91):
    """Для сабмишена, где факта нет: хвост истории и прогноз дневных сумм."""
    routes = sorted(preds["route"].unique())
    fig, axes = _route_grid(routes)
    for ax, route in zip(axes, routes, strict=False):
        h = history[
            (history["route"] == route)
            & (
                history["ts"]
                >= history["ts"].max().normalize() - pd.Timedelta(days=history_days - 1)
            )
        ]
        p = preds[preds["route"] == route]
        pd_day = p.groupby(p["ts"].dt.normalize()).sum(numeric_only=True)
        ax.plot(h.groupby(h["ts"].dt.normalize())["y"].sum(), color="k", lw=1, label="история")
        ax.plot(pd_day.index, pd_day["yhat"], color="C1", lw=1.2, label="прогноз")
        if {"q0.1", "q0.9"}.issubset(pd_day.columns):
            # сумма почасовых квантилей — грубая, завышенная оценка интервала дня
            ax.fill_between(pd_day.index, pd_day["q0.1"], pd_day["q0.9"], color="C1", alpha=0.2)
        ax.set_title(f"маршрут {route}", fontsize=10)
        ax.tick_params(axis="x", labelrotation=45, labelsize=8)
    for ax in axes[len(routes) :]:
        ax.axis("off")
    axes[0].legend(fontsize=8)
    fig.suptitle("Прогноз дневных сумм")
    fig.tight_layout()
    return fig


def hourly_week(preds: pd.DataFrame, truth: pd.DataFrame, week_start: str | None = None):
    df = join_truth(preds, truth)
    start = (
        pd.Timestamp(week_start)
        if week_start
        else df["ts"].max().normalize() - pd.Timedelta(days=6)
    )
    df = df[(df["ts"] >= start) & (df["ts"] < start + pd.Timedelta(days=7))]
    routes = sorted(df["route"].unique())
    fig, axes = _route_grid(routes)
    for ax, route in zip(axes, routes, strict=False):
        g = df[df["route"] == route]
        ax.plot(g["ts"], g["y"], color="k", lw=1, label="факт")
        ax.plot(g["ts"], g["yhat"], color="C1", lw=1, label="прогноз")
        if {"q0.1", "q0.9"}.issubset(g.columns):
            ax.fill_between(g["ts"], g["q0.1"], g["q0.9"], color="C1", alpha=0.2)
        ax.set_title(f"маршрут {route}", fontsize=10)
        ax.tick_params(axis="x", labelrotation=45, labelsize=8)
    for ax in axes[len(routes) :]:
        ax.axis("off")
    axes[0].legend(fontsize=8)
    fig.suptitle(f"Почасово, неделя с {start:%Y-%m-%d}")
    fig.tight_layout()
    return fig


def score_heatmap(preds: pd.DataFrame, truth: pd.DataFrame, cols: str = "dow"):
    df = join_truth(preds, truth)
    df["col"] = df["ts"].dt.dayofweek if cols == "dow" else df["ts"].dt.hour
    table = df.groupby(["route", "col"]).apply(lambda g: wape_score(g["y"], g["yhat"])).unstack()
    fig, ax = plt.subplots(figsize=(12 if cols == "hour" else 7, 5))
    im = ax.imshow(table.to_numpy(), cmap="RdYlGn", vmin=0.5, vmax=1.0, aspect="auto")
    ax.set_yticks(range(len(table)), table.index)
    labels = DOW if cols == "dow" else table.columns
    ax.set_xticks(range(len(table.columns)), labels)
    for (i, j), v in pd.DataFrame(table.to_numpy()).stack().items():
        ax.text(j, i, f"{v:.2f}", ha="center", va="center", fontsize=7 if cols == "hour" else 9)
    fig.colorbar(im, ax=ax)
    ax.set_title(f"WAPE-score: маршрут × {'день недели' if cols == 'dow' else 'час'}")
    fig.tight_layout()
    return fig


def hourly_profile(preds: pd.DataFrame, truth: pd.DataFrame):
    df = join_truth(preds, truth)
    weekend = df["ts"].dt.dayofweek >= 5
    fig, axes = plt.subplots(1, 2, figsize=(13, 4), sharey=True)
    for ax, mask, title in [(axes[0], ~weekend, "будни"), (axes[1], weekend, "выходные")]:
        g = df[mask].groupby([df["ts"].dt.normalize(), df["ts"].dt.hour])[["y", "yhat"]].sum()
        prof = g.groupby(level=1).mean()
        ax.plot(prof.index, prof["y"], "k-o", ms=3, label="факт")
        ax.plot(prof.index, prof["yhat"], "-o", color="C1", ms=3, label="прогноз")
        ax.set_title(title)
        ax.set_xticks(range(0, 24, 2))
    axes[0].legend()
    fig.suptitle("Средний суточный профиль (сумма по маршрутам)")
    fig.tight_layout()
    return fig


def daily_score_curve(scores: pd.Series):
    fig, ax = plt.subplots(figsize=(12, 3.5))
    ax.plot(scores.index, scores.to_numpy(), "-o", ms=3)
    for day in scores.index[scores.index.dayofweek >= 5]:
        ax.axvspan(day, day + pd.Timedelta(days=1), color="0.9", zorder=0)
    ax.set_ylabel("WAPE-score")
    ax.set_title("Качество по дням горизонта (серым — выходные)")
    fig.tight_layout()
    return fig
