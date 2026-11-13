"""Train every ML module and build the evaluation report.

    python -m ml.train_all
"""
from __future__ import annotations

from ml.anomaly_detection import anomaly
from ml.churn_prediction import churn
from ml.customer_segmentation import segmentation
from ml.demand_forecasting import demand
from ml.model_evaluation.report import write_report
from ml.revenue_forecasting import forecast
from src.logging.logger import get_logger, log_step

log = get_logger("ml")


def train_all() -> dict:
    out = {}
    for name, fn in [("customer_segmentation", segmentation.train), ("churn_prediction", churn.train),
                     ("revenue_forecasting", forecast.train), ("demand_forecasting", demand.train),
                     ("anomaly_detection", anomaly.train)]:
        with log_step(f"ml:{name}", log):
            out[name] = fn()
    write_report(out)
    return out


if __name__ == "__main__":
    train_all()
