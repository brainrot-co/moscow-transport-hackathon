import argparse

from mtml import tracking
from mtml.backtest import PROXY_CUTOFF, PROXY_END, backtest
from mtml.data import load_series
from mtml.forecasters import build


def main():
    parser = argparse.ArgumentParser(
        description="Бэктест: контекст до --cutoff, WAPE-score на [--cutoff, --end]"
    )
    parser.add_argument("models", nargs="+", help="имена из mtml.forecasters.build")
    parser.add_argument("--cutoff", default=PROXY_CUTOFF)
    parser.add_argument("--end", default=PROXY_END)
    parser.add_argument("--no-mlflow", action="store_true", help="не логировать в MLflow")
    args = parser.parse_args()

    if not args.no_mlflow:
        tracking.setup()
    series = load_series(end=args.end)
    rows = []
    for name in args.models:
        result = backtest(build(name), series, args.cutoff, args.end)
        metrics = result.metrics
        run_id = None if args.no_mlflow else tracking.log_backtest(result)
        rows.append((name, metrics["wape_score"]))
        print(
            f"{name:24s} wape_score={metrics['wape_score']:.4f} {metrics['by_month']} "
            f"({result.seconds:.0f} с) mlflow_run={run_id}"
        )

    print("\nИтог (по убыванию):")
    for name, score in sorted(rows, key=lambda r: -r[1]):
        print(f"  {name:24s} {score:.4f}")


if __name__ == "__main__":
    main()
