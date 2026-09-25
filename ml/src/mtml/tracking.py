import platform
import subprocess
import tempfile
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

import matplotlib.pyplot as plt
import mlflow
import mlflow.data
import pandas as pd
from matplotlib.figure import Figure

from mtml import plots
from mtml.backtest import BacktestResult
from mtml.data import ROOT
from mtml.forecasters.base import Forecaster
from mtml.metrics import daily_scores

MLFLOW_DIR = ROOT / "ml" / "mlflow"
TRACKING_URI = f"sqlite:///{MLFLOW_DIR / 'mlflow.db'}"
DEFAULT_EXPERIMENT = "tram-forecast"
_PARAM_TYPES = (int, float, str, bool, tuple, list, type(None))


def setup(experiment: str = DEFAULT_EXPERIMENT):
    """UI: uv run mlflow ui --backend-store-uri sqlite:///ml/mlflow/mlflow.db"""
    MLFLOW_DIR.mkdir(parents=True, exist_ok=True)
    mlflow.set_tracking_uri(TRACKING_URI)
    if mlflow.get_experiment_by_name(experiment) is None:
        # явный artifact_location — иначе артефакты лягут относительно cwd блокнота
        mlflow.create_experiment(experiment, artifact_location=(MLFLOW_DIR / "artifacts").as_uri())
    return mlflow.set_experiment(experiment).experiment_id


def forecaster_params(forecaster: Forecaster):
    """Только публичные скалярные атрибуты: история и таблицы признаков в параметры не попадают."""
    params = {"model_class": type(forecaster).__name__}
    for key, value in vars(forecaster).items():
        if not key.startswith("_") and isinstance(value, _PARAM_TYPES):
            params[key] = value
    return params


def env_tags():
    tags = {
        "python": platform.python_version(),
        "machine": platform.machine(),
        "os": platform.platform(),
    }
    for pkg in ("chronos-forecasting", "torch", "pandas", "mlflow", "transformers"):
        try:
            tags[f"pkg.{pkg}"] = version(pkg)
        except PackageNotFoundError:
            pass
    try:
        git = ["git", "-C", str(ROOT)]
        tags["git.commit"] = subprocess.check_output([*git, "rev-parse", "HEAD"], text=True).strip()
        tags["git.branch"] = subprocess.check_output(
            [*git, "rev-parse", "--abbrev-ref", "HEAD"], text=True
        ).strip()
        dirty = subprocess.check_output([*git, "status", "--porcelain"], text=True).strip()
        tags["git.dirty"] = str(bool(dirty))
    except (OSError, subprocess.CalledProcessError):
        pass
    return tags


def log_nested_metrics(metrics: dict, prefix: str = ""):
    """{"wape_score": .., "by_route": {"17": ..}} -> wape_score, by_route/17, ..."""
    flat = {}
    for key, value in metrics.items():
        name = f"{prefix}{key}"
        if isinstance(value, dict):
            flat |= {f"{name}/{k}": v for k, v in value.items() if isinstance(v, int | float)}
        elif isinstance(value, int | float):
            flat[name] = value
    mlflow.log_metrics(flat)


def log_series_metric(name: str, values: pd.Series):
    for step, value in enumerate(values.to_numpy()):
        mlflow.log_metric(name, float(value), step=step)


def log_dataset(df: pd.DataFrame, name: str, context: str):
    ds = mlflow.data.from_pandas(df, name=name, targets="y" if "y" in df.columns else None)
    mlflow.log_input(ds, context=context)
    mlflow.log_params(
        {
            f"data.{context}.rows": len(df),
            f"data.{context}.start": str(df["ts"].min()),
            f"data.{context}.end": str(df["ts"].max()),
            f"data.{context}.routes": ",".join(map(str, sorted(df["route"].unique()))),
        }
    )


def log_frame(df: pd.DataFrame, artifact_path: str, fmt: str = "parquet"):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / artifact_path
        path.parent.mkdir(parents=True, exist_ok=True)
        if fmt == "parquet":
            df.to_parquet(path, index=False)
        else:
            df.to_csv(path, sep=";", index=False)
        parent = str(Path(artifact_path).parent)
        mlflow.log_artifact(str(path), artifact_path=None if parent == "." else parent)


def log_fig(fig: Figure, name: str):
    mlflow.log_figure(fig, f"plots/{name}.png")
    plt.close(fig)


def log_backtest(
    result: BacktestResult,
    run_name: str | None = None,
    tags: dict | None = None,
    description: str | None = None,
):
    forecaster = result.forecaster
    with mlflow.start_run(run_name=run_name or forecaster.name, description=description) as run:
        mlflow.set_tags(
            {"stage": "backtest", "model": forecaster.name, **env_tags(), **(tags or {})}
        )
        mlflow.log_params(forecaster_params(forecaster))
        mlflow.log_params(
            {
                "cutoff": result.cutoff,
                "end": result.end,
                "horizon_days": result.truth["ts"].dt.normalize().nunique(),
            }
        )
        log_dataset(result.history, "history", "training")
        log_dataset(result.truth, "truth", "evaluation")

        log_nested_metrics(result.metrics)
        mlflow.log_metric("predict_seconds", result.seconds)
        scores = daily_scores(result.preds, result.truth)
        log_series_metric("daily_wape_score", scores)
        mlflow.log_dict(result.metrics, "metrics.json")

        log_frame(result.preds, "preds.parquet")
        # у XRegChronos — поправочные коэффициенты ridge по признакам
        if isinstance(getattr(forecaster, "coefficients", None), pd.DataFrame):
            log_frame(forecaster.coefficients, "coefficients.csv", "csv")
        log_frame(
            scores.rename("wape_score").rename_axis("date").reset_index(), "daily_scores.csv", "csv"
        )

        log_fig(plots.daily_totals(result.preds, result.truth, result.history), "daily_totals")
        log_fig(plots.hourly_week(result.preds, result.truth), "hourly_last_week")
        log_fig(plots.hourly_profile(result.preds, result.truth), "hourly_profile")
        log_fig(plots.score_heatmap(result.preds, result.truth, "dow"), "score_route_dow")
        log_fig(plots.score_heatmap(result.preds, result.truth, "hour"), "score_route_hour")
        log_fig(plots.daily_score_curve(scores), "daily_score_curve")
        return run.info.run_id


def log_submission(
    forecaster: Forecaster,
    history: pd.DataFrame,
    preds: pd.DataFrame,
    submission: pd.DataFrame,
    run_name: str | None = None,
    backtest_run_id: str | None = None,
    tags: dict | None = None,
):
    """Скор с платформы дописывается позже через log_leaderboard_score."""
    with mlflow.start_run(run_name=run_name or f"submission_{forecaster.name}") as run:
        mlflow.set_tags(
            {"stage": "submission", "model": forecaster.name, **env_tags(), **(tags or {})}
        )
        if backtest_run_id:
            mlflow.set_tag("backtest_run_id", backtest_run_id)
        mlflow.log_params(forecaster_params(forecaster))
        mlflow.log_params(
            {"forecast_start": str(preds["ts"].min()), "forecast_end": str(preds["ts"].max())}
        )
        log_dataset(history, "history", "training")

        by_route = submission.groupby("route")["prediction"].sum()
        by_month = submission.groupby(submission["date"].str[:7])["prediction"].sum()
        mlflow.log_metrics(
            {
                "pred_total": float(submission["prediction"].sum()),
                "pred_rows": float(len(submission)),
            }
        )
        mlflow.log_metrics({f"pred_total/route_{k}": float(v) for k, v in by_route.items()})
        mlflow.log_metrics({f"pred_total/{k}": float(v) for k, v in by_month.items()})
        day_totals = submission.groupby("date")["prediction"].sum()
        log_series_metric("pred_daily_total", day_totals)

        log_frame(preds, "preds.parquet")
        log_frame(submission, "submission.csv", "csv")
        log_fig(plots.forecast_overview(preds, history), "forecast_overview")
        return run.info.run_id


def log_leaderboard_score(run_id: str, score: float):
    with mlflow.start_run(run_id=run_id):
        mlflow.log_metric("leaderboard_wape_score", score)


def runs_table(
    experiment: str = DEFAULT_EXPERIMENT,
    stage: str | None = "backtest",
    extra: list[str] | None = None,
):
    filter_string = f"tags.stage = '{stage}'" if stage else ""
    runs = mlflow.search_runs(experiment_names=[experiment], filter_string=filter_string)
    if runs.empty:
        return runs
    cols = ["run_id", "tags.mlflow.runName", "start_time"]
    wanted = [
        "metrics.wape_score",
        "metrics.wape_score_daily_totals",
        "metrics.bias",
        "metrics.coverage_80",
        "metrics.by_month/9",
        "metrics.by_month/10",
        "metrics.predict_seconds",
        "metrics.leaderboard_wape_score",
        "metrics.pred_total",
        "params.layout",
        "params.context_length",
        "params.cross_learning",
        "params.cutoff",
        *(extra or []),
    ]
    cols += [c for c in wanted if c in runs.columns]
    sort = "metrics.wape_score" if "metrics.wape_score" in runs.columns else "start_time"
    table = runs[cols].sort_values(sort, ascending=False, ignore_index=True)
    return table.rename(
        columns=lambda c: c.split(".", 1)[-1] if c != "tags.mlflow.runName" else "run"
    )
