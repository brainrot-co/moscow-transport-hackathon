import argparse
import json
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from mtml.data import ROOT
from mtml.storage import Volume
from mtml.worker.year import DAY_TYPES, RECENT_WEEKS, calendar_days, fit_route, hourly_profile

OUT_DIR = ROOT / "docs" / "img"
INK, MUTED, GRID = "#1b2124", "#5b6569", "#e3e7e5"
HISTORY, YEAR, SHORT, ALERT = "#8a9499", "#2c6a6e", "#b3302a", "#c77d1a"
WEEKDAYS = ["пн", "вт", "ср", "чт", "пт", "сб", "вс"]
MONTHS = ["янв", "фев", "мар", "апр", "май", "июн", "июл", "авг", "сен", "окт", "ноя", "дек"]
DAY_LABELS = {
    "saturday": "суббота",
    "sunday": "воскресенье",
    "holiday": "праздник",
    "pre_holiday": "предпраздничный",
    "post_holiday": "послепраздничный",
}
KIND_LABELS = {"workday": "рабочий день", "saturday": "суббота", "day_off": "выходной, праздник"}


def style(ax: plt.Axes):
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=MUTED, labelsize=9)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def thousands(ax: plt.Axes):
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v / 1000:.0f} тыс."))


def load_run(volume: Volume, kind: str):
    run_id = json.loads(volume.active.read_text(encoding="utf-8"))[kind]
    return pd.read_parquet(volume.runs / run_id / "forecasts.parquet")


def daily(frame: pd.DataFrame, column: str):
    return frame.groupby(frame["ts"].dt.normalize())[column].sum()


def plot_year(route: int, history: pd.DataFrame, anomaly: pd.Series, short, year, path: Path):
    fact = daily(history, "boardings")
    year_days = daily(year, "yhat")
    low, high = daily(year, "q10"), daily(year, "q90")
    short_days = daily(short, "yhat")

    fig, ax = plt.subplots(figsize=(13, 4.8), dpi=150)
    style(ax)
    ax.fill_between(year_days.index, low, high, color=YEAR, alpha=0.15, linewidth=0)
    ax.plot(fact.index, fact.to_numpy(), color=HISTORY, linewidth=1, label="факт 2025")
    marked = fact[fact.index.isin(anomaly)]
    ax.scatter(
        marked.index, marked.to_numpy(), s=14, color=ALERT, zorder=3, label="anomaly: не в обучении"
    )
    ax.plot(year_days.index, year_days.to_numpy(), color=YEAR, linewidth=1, label="годовой прогноз")
    ax.plot(
        short_days.index,
        short_days.to_numpy(),
        color=SHORT,
        linewidth=1.2,
        label="краткосрочный (Chronos)",
    )
    ax.axvline(year_days.index.min(), color=MUTED, linewidth=1, linestyle=(0, (4, 3)))
    ax.text(
        year_days.index.min(), ax.get_ylim()[1], "  водяной знак", color=MUTED, fontsize=9, va="top"
    )
    thousands(ax)
    ax.xaxis.set_major_locator(mdates.MonthLocator())
    ax.xaxis.set_major_formatter(
        plt.FuncFormatter(
            lambda v, _: f"{MONTHS[mdates.num2date(v).month - 1]}\n{mdates.num2date(v).year}"
            if mdates.num2date(v).month == 1
            else MONTHS[mdates.num2date(v).month - 1]
        )
    )
    ax.set_ylabel("посадок в день", color=MUTED, fontsize=9.5)
    ax.set_title(
        f"Маршрут {route}: факт и прогноз на год, полоса — интервал 10–90%",
        loc="left",
        color=INK,
        fontsize=12.5,
        pad=12,
    )
    ax.legend(frameon=False, fontsize=9, loc="upper left", bbox_to_anchor=(0, -0.12), ncols=4)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def plot_effects(route: int, coef: dict[str, float], path: Path):
    months = {int(k.split("_")[1]): v for k, v in coef.items() if k.startswith("month_")}
    month_pct = [0.0] + [100 * (np.exp(months[m]) - 1) for m in sorted(months)]
    month_labels = [MONTHS[0]] + [MONTHS[m - 1] for m in sorted(months)]
    day_pct = [100 * (np.exp(coef[t]) - 1) for t in DAY_TYPES] + [
        100 * (np.exp(coef["school"]) - 1)
    ]
    day_labels = [DAY_LABELS[t] for t in DAY_TYPES] + ["школьные каникулы"]

    fig, (left, right) = plt.subplots(
        1, 2, figsize=(13, 4.2), dpi=150, gridspec_kw={"width_ratios": [1.3, 1]}
    )
    for ax, values, labels, title in (
        (left, month_pct, month_labels, "Эффект месяца, % к январю"),
        (right, day_pct, day_labels, "Эффект типа дня, % к обычному рабочему"),
    ):
        style(ax)
        colors = [YEAR if v >= 0 else SHORT for v in values]
        if ax is left:
            ax.bar(labels, values, color=colors, width=0.6)
            ax.axhline(0, color=MUTED, linewidth=0.8)
            for x, v in enumerate(values):
                ax.text(
                    x,
                    v + (0.6 if v >= 0 else -0.6),
                    f"{v:+.0f}",
                    ha="center",
                    va="bottom" if v >= 0 else "top",
                    fontsize=8.5,
                    color=INK,
                )
        else:
            ax.grid(axis="y", visible=False)
            ax.grid(axis="x", color=GRID, linewidth=0.8)
            ax.barh(labels, values, color=colors, height=0.55)
            ax.axvline(0, color=MUTED, linewidth=0.8)
            ax.invert_yaxis()
            for y, v in enumerate(values):
                ax.text(
                    v + (1 if v >= 0 else -1),
                    y,
                    f"{v:+.0f}%",
                    va="center",
                    ha="left" if v >= 0 else "right",
                    fontsize=8.5,
                    color=INK,
                )
            ax.set_xlim(min(values) - 12, max(values) + 12)
        ax.set_title(title, loc="left", color=INK, fontsize=11, pad=10)
    fig.suptitle(
        f"Маршрут {route}: из чего складывается годовой прогноз (эффекты умножаются)",
        x=0.01,
        ha="left",
        color=INK,
        fontsize=12.5,
    )
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def plot_profile_and_week(route: int, profile: pd.Series, year: pd.DataFrame, path: Path):
    fig, (left, right) = plt.subplots(
        1, 2, figsize=(13, 4.2), dpi=150, gridspec_kw={"width_ratios": [1, 1.4]}
    )
    style(left)
    for kind, color in (("workday", YEAR), ("saturday", ALERT), ("day_off", SHORT)):
        share = profile.loc[kind] * 100
        left.plot(
            share.index,
            share.to_numpy(),
            color=color,
            linewidth=2,
            marker="o",
            markersize=3,
            label=KIND_LABELS[kind],
        )
    left.set_xticks(range(0, 24, 3))
    left.set_xlabel("час", color=MUTED, fontsize=9.5)
    left.set_ylabel("доля посадок дня, %", color=MUTED, fontsize=9.5)
    left.set_title(
        f"Суточный профиль за последние {RECENT_WEEKS} недель",
        loc="left",
        color=INK,
        fontsize=11,
        pad=10,
    )
    left.legend(frameon=False, fontsize=9)

    style(right)
    week = year[(year["ts"] >= "2026-03-09") & (year["ts"] < "2026-03-16")]
    right.fill_between(week["ts"], week["q10"], week["q90"], color=YEAR, alpha=0.15, linewidth=0)
    right.plot(week["ts"], week["yhat"], color=YEAR, linewidth=1.5)
    right.xaxis.set_major_locator(mdates.DayLocator())
    right.xaxis.set_major_formatter(
        plt.FuncFormatter(
            lambda v, _: f"{WEEKDAYS[mdates.num2date(v).weekday()]} {mdates.num2date(v):%d.%m}"
        )
    )
    right.set_ylabel("посадок в час", color=MUTED, fontsize=9.5)
    right.set_title(
        "Годовой прогноз почасово: неделя 9–15 марта 2026",
        loc="left",
        color=INK,
        fontsize=11,
        pad=10,
    )
    fig.suptitle(
        f"Маршрут {route}: как дневная сумма раскладывается на часы",
        x=0.01,
        ha="left",
        color=INK,
        fontsize=12.5,
    )
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(
        description="Графики годового прогноза по маршруту из опубликованных прогонов"
    )
    parser.add_argument("--route", type=int, default=17)
    args = parser.parse_args()

    volume = Volume.from_env()
    route = args.route
    actuals = pd.read_parquet(volume.actuals)
    status = pd.read_parquet(volume.day_status)
    year, short = load_run(volume, "year"), load_run(volume, "short")
    start = year["ts"].min()
    history = actuals[(actuals["route"] == route) & (actuals["ts"] < start)]
    route_status = status[(status["route"] == route) & (status["date"] < start)]
    usual_days = route_status.loc[
        (route_status["status"] == "final") & ~route_status["anomaly"], "date"
    ]
    anomaly = route_status.loc[route_status["anomaly"], "date"]

    series = history.rename(columns={"boardings": "y"}).assign(date=history["ts"].dt.normalize())
    series = series[series["date"].isin(usual_days)]
    days = calendar_days(series["date"].min(), year["ts"].max().normalize())
    daily_usual = series.groupby("date")["y"].sum().reset_index().merge(days, on="date")
    model = fit_route(daily_usual)
    names = ["intercept"] + [f"month_{m}" for m in model.months[1:]] + list(DAY_TYPES) + ["school"]
    recent = series[series["date"] > series["date"].max() - pd.Timedelta(weeks=RECENT_WEEKS)]

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    plot_year(
        route,
        history,
        anomaly,
        short[short["route"] == route],
        year[year["route"] == route],
        OUT_DIR / f"year_route{route}_forecast.png",
    )
    plot_effects(
        route, dict(zip(names, model.coef, strict=True)), OUT_DIR / f"year_route{route}_effects.png"
    )
    plot_profile_and_week(
        route,
        hourly_profile(recent, days),
        year[year["route"] == route],
        OUT_DIR / f"year_route{route}_hours.png",
    )
    print(f"-> {OUT_DIR}")


if __name__ == "__main__":
    main()
