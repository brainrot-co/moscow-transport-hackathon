import argparse
import json

from mtml import tracking
from mtml.backtest import RUNS_DIR
from mtml.data import load_series
from mtml.forecasters import build
from mtml.submission import SUBMISSION_END, SUBMISSION_START, to_submission, write_submission


def main():
    parser = argparse.ArgumentParser(
        description="Прогноз на ноябрь–декабрь по всей истории (январь–октябрь) -> submission.csv."
    )
    parser.add_argument("model", help="имя из mtml.forecasters.build")
    parser.add_argument("--backtest-run-id", help="run прокси-бэктеста этой же модели в MLflow")
    parser.add_argument("--no-mlflow", action="store_true", help="не логировать в MLflow")
    args = parser.parse_args()

    series = load_series()
    forecaster = build(args.model)
    preds = forecaster.fit(series).predict(SUBMISSION_START, SUBMISSION_END)

    run_dir = RUNS_DIR / f"submission_{args.model}"
    run_dir.mkdir(parents=True, exist_ok=True)
    preds.to_parquet(run_dir / "preds.parquet", index=False)
    sub = to_submission(preds)
    write_submission(sub, run_dir / "submission.csv")
    summary = {
        "model": args.model,
        "rows": len(sub),
        "total": int(sub["prediction"].sum()),
        "by_route": sub.groupby("route")["prediction"].sum().to_dict(),
    }
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2, default=int))
    print(json.dumps(summary, indent=2, default=int))
    print(f"-> {run_dir / 'submission.csv'}")

    if not args.no_mlflow:
        tracking.setup()
        run_id = tracking.log_submission(
            forecaster, series, preds, sub, backtest_run_id=args.backtest_run_id
        )
        print(f"mlflow_run={run_id}")


if __name__ == "__main__":
    main()
