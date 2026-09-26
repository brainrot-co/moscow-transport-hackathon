import argparse
from pathlib import Path

import duckdb
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from mtml.data import ROOT

OUT_DIR = ROOT / "ml" / "artifacts" / "plots"
COLUMNS = {
    "tran_no": "BIGINT",
    "device_no": "BIGINT",
    "tran_date_time": "TIMESTAMP",
    "begin_date_time": "VARCHAR",
    "input_date_time": "VARCHAR",
    "crd_hashcode": "VARCHAR",
    "validation_result": "INTEGER",
    "tran_type_id": "INTEGER",
    "place_id": "INTEGER",
    "good_type": "VARCHAR",
    "pass_route": "VARCHAR",
    "ngpt_route": "VARCHAR",
    "bus_exit_no": "INTEGER",
    "garage_number": "INTEGER",
}
THREE_SIGMA = 0.9973  # доля нормального распределения внутри ±3σ

INK, MUTED, GRID = "#1b2124", "#5b6569", "#e3e7e5"
LINE, POINT, ALERT = "#2c6a6e", "#9aa3a7", "#b3302a"


def load(csv: Path, start: str, end: str):
    columns = ", ".join(f"'{k}': '{v}'" for k, v in COLUMNS.items())
    con = duckdb.connect()
    con.execute("SET preserve_insertion_order = false")
    return con.execute(f"""
        SELECT CAST(split_part(ngpt_route, ' ', 1) AS INTEGER) AS route,
               CAST(tran_date_time AS DATE) AS day,
               epoch(try_strptime(input_date_time, '%Y-%m-%d %H:%M:%S') - tran_date_time) / 3600
                   AS lag_h,
               date_diff('day', CAST(tran_date_time AS DATE),
                         CAST(try_strptime(input_date_time, '%Y-%m-%d %H:%M:%S') AS DATE)) AS lag_d
        FROM read_csv('{csv}', delim=';', header=true, auto_detect=false, columns={{{columns}}},
                      quote='', escape='', strict_mode=false, parallel=false, new_line='\\n')
        WHERE validation_result = 1 AND CAST(tran_date_time AS DATE) BETWEEN '{start}' AND '{end}'
    """).df()


def style(ax: plt.Axes):
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=MUTED, labelsize=9)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def plot_curve(df: pd.DataFrame, path: Path):
    lag = np.sort(df["lag_h"].clip(lower=1 / 60).to_numpy())
    share = np.arange(1, len(lag) + 1) / len(lag) * 100
    grid = np.geomspace(1 / 60, lag.max(), 400)
    curve = np.interp(grid, lag, share)
    q3s = float(np.quantile(lag, THREE_SIGMA))
    marks = {"1 мин": 1 / 60, "1 ч": 1, "D+1": 24, "D+3": 72, "D+7": 168, "D+30": 720}

    fig, ax = plt.subplots(figsize=(10, 4.6), dpi=160)
    style(ax)
    ax.plot(grid, curve, color=LINE, linewidth=2)
    ax.axhline(THREE_SIGMA * 100, color=ALERT, linewidth=1, linestyle=(0, (4, 3)))
    ax.axvline(q3s, color=ALERT, linewidth=1, linestyle=(0, (4, 3)))
    ax.scatter(
        [q3s], [THREE_SIGMA * 100], s=36, color=ALERT, zorder=3, edgecolor="white", linewidth=1.5
    )
    ax.text(
        1 / 60 * 1.3,
        THREE_SIGMA * 100 + 0.12,
        f"3σ = 99.73% валидаций дня: через {q3s / 24:.0f} дн.",
        ha="left",
        va="bottom",
        color=ALERT,
        fontsize=9.5,
    )
    for label, hours in marks.items():
        if hours < 1:  # за первую минуту приходит ~56%, точка ниже оси
            continue
        value = float(np.interp(hours, lag, share))
        ax.scatter([hours], [value], s=22, color=LINE, zorder=3, edgecolor="white", linewidth=1.2)
        ax.annotate(
            f"{label}\n{value:.1f}%",
            (hours, value),
            xytext=(0, -30),
            textcoords="offset points",
            ha="center",
            color=MUTED,
            fontsize=8.5,
        )
    ax.set_xscale("log")
    ax.set_xticks(list(marks.values()))
    ax.set_xticklabels(list(marks.keys()))
    ax.set_ylim(88, 100.4)
    ax.set_ylabel("пришло от всех валидаций дня, %", color=MUTED, fontsize=9.5)
    ax.set_xlabel(
        "задержка выгрузки (input_date_time − tran_date_time), логарифмическая шкала",
        color=MUTED,
        fontsize=9.5,
    )
    ax.set_title(
        "Кривая дозагрузки валидаций, сентябрь 2025", loc="left", color=INK, fontsize=12.5, pad=12
    )
    fig.text(
        0.01,
        0.01,
        "100% = всё, что пришло к выгрузке test.csv (~2 месяца); настоящий итог дня чуть больше.",
        color=MUTED,
        fontsize=8,
    )
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return {
        "quantile_3sigma_days": round(q3s / 24, 1),
        **{k: round(float(np.interp(v, lag, share)), 2) for k, v in marks.items()},
    }


def plot_days(df: pd.DataFrame, path: Path):
    days = (
        df.assign(ok=df["lag_d"] <= 1)
        .groupby(["route", "day"])
        .agg(n=("ok", "size"), pct=("ok", "mean"))
        .reset_index()
    )
    days["pct"] *= 100
    mean, sigma = days["pct"].mean(), days["pct"].std()
    low = mean - 3 * sigma
    days["outlier"] = days["pct"] < low

    fig, ax = plt.subplots(figsize=(10, 4.6), dpi=160)
    style(ax)
    normal, out = days[~days["outlier"]], days[days["outlier"]]
    ax.scatter(normal["day"], normal["pct"], s=16, color=POINT, alpha=0.8, linewidth=0)
    ax.scatter(
        out["day"], out["pct"], s=30, color=ALERT, zorder=3, edgecolor="white", linewidth=1.2
    )
    ax.axhline(mean, color=LINE, linewidth=1.5)
    ax.axhline(low, color=ALERT, linewidth=1, linestyle=(0, (4, 3)))
    ax.text(
        days["day"].max(),
        mean + 0.25,
        f"среднее {mean:.1f}%",
        ha="right",
        va="bottom",
        color=INK,
        fontsize=9,
    )
    ax.text(
        days["day"].max(),
        low - 0.25,
        f"−3σ = {low:.1f}%  (σ = {sigma:.2f} п.п.)",
        ha="right",
        va="top",
        color=ALERT,
        fontsize=9,
    )
    for row in out.itertuples():
        ax.annotate(
            f"м.{row.route}, {row.day:%d.%m}, n={row.n:,}".replace(",", " "),
            (row.day, row.pct),
            xytext=(6, 0),
            textcoords="offset points",
            va="center",
            color=INK,
            fontsize=8.5,
        )
    ax.set_ylabel("пришло к концу D+1, %", color=MUTED, fontsize=9.5)
    ax.set_title(
        "Полнота дня маршрута к концу следующих суток, сентябрь 2025",
        loc="left",
        color=INK,
        fontsize=12.5,
        pad=12,
    )
    ax.xaxis.set_major_formatter(plt.matplotlib.dates.DateFormatter("%d.%m"))
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return days


def main():
    parser = argparse.ArgumentParser(
        description="Задержка выгрузки валидаций: кривая дозагрузки и полнота дней к D+1"
    )
    parser.add_argument("--csv", type=Path, default=ROOT / "dataset" / "test.csv")
    parser.add_argument("--start", default="2025-09-01")
    parser.add_argument("--end", default="2025-09-30")
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    df = load(args.csv, args.start, args.end)
    summary = plot_curve(df, OUT_DIR / "arrival_lag_curve.png")
    days = plot_days(df, OUT_DIR / "arrival_completeness_d1.png")
    days.to_csv(OUT_DIR / "arrival_completeness_d1.csv", index=False)
    print("кривая дозагрузки:", summary)
    print(days[days["outlier"]].to_string(index=False))
    print(f"-> {OUT_DIR}")


if __name__ == "__main__":
    main()
