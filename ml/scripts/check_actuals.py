import argparse

import pandas as pd

from mtml.data import load_labels
from mtml.storage import Volume


def main():
    parser = argparse.ArgumentParser(
        description="Сверка фактов из тома с разметкой организаторов (labels_day_*.csv)"
    )
    parser.parse_args()

    labels = load_labels().rename(columns={"y": "labels"})
    actuals = pd.read_parquet(Volume.from_env().actuals)
    start, end = labels["ts"].min().normalize(), labels["ts"].max()
    actuals = actuals[(actuals["ts"] >= start) & (actuals["ts"] <= end)]
    both = actuals.merge(labels, on=["route", "ts"], how="outer")
    both = both.fillna({"boardings": 0, "labels": 0})
    diff = both[both["boardings"] != both["labels"]]

    print(f"Период разметки: {start:%Y-%m-%d} – {end:%Y-%m-%d}")
    volume_total, labels_total = int(both["boardings"].sum()), int(both["labels"].sum())
    print(f"Посадок: в томе {volume_total:,}, в разметке {labels_total:,}")
    print(f"Часов маршрут × час с расхождением: {len(diff)}")
    if not diff.empty:
        by_route = diff.groupby("route")[["boardings", "labels"]].sum().astype(int)
        print(by_route.to_string())
        print(diff.head(20).to_string(index=False))


if __name__ == "__main__":
    main()
