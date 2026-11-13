"""Reviews transform.

Grain = (review_id, order_id). The same review_id can legitimately appear on
several orders (one survey answered for a multi-order purchase), so review_id
alone is NOT a key. A few orders also have more than one review; for
order-level satisfaction we keep the most recently answered review
(``is_latest_for_order``) to avoid double counting.
"""
from __future__ import annotations

import pandas as pd

from src.transformation.common import CleaningLog, drop_exact_duplicates

DATASET = "reviews"


def transform(df: pd.DataFrame, log: CleaningLog) -> pd.DataFrame:
    out = drop_exact_duplicates(df.copy(), DATASET, log, ["review_id", "order_id"])
    out["has_comment"] = out.review_comment_message.notna()
    out["response_hours"] = ((out.review_answer_timestamp - out.review_creation_date).dt.total_seconds() / 3600).round(2)
    out = out.sort_values(["order_id", "review_answer_timestamp"], ascending=[True, False])
    out["is_latest_for_order"] = ~out.duplicated("order_id", keep="first")
    log.add(DATASET, "flag_latest_review_per_order", int((~out.is_latest_for_order).sum()),
            "older reviews for the same order flagged (kept, not deleted)")
    out["sentiment_band"] = pd.cut(out.review_score.astype(float), [0, 2, 3, 5],
                                   labels=["negative", "neutral", "positive"]).astype("string")
    return out.reset_index(drop=True)
