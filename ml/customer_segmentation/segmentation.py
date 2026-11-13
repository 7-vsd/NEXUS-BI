"""A. Customer segmentation – RFM scoring + K-Means clustering.

Unit: customer_unique_id with >= 1 revenue order that has items.
Features: log1p(recency_days), log1p(frequency), log1p(monetary), standardised.
k is chosen by silhouette score (evaluated on a seeded 15k sample) within
k = 3..8 – the range a marketing team can act on – and the elbow curve is
saved for review. Clusters are named from their centroid profile.
"""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

from src.config.settings import settings
from ml.common import FIG_DIR, REPORT_DIR, SEED, load_processed, metadata, save_json, save_model

MODULE = "customer_segmentation"

STRATEGIES = {
    "Loyal Repeat Buyers": "Protect: VIP perks, early access, referral programme; monitor for lapses.",
    "Recent One-Time Buyers": "Drive the 2nd order: post-delivery cross-sell within 30-60 days, review request, free-shipping threshold.",
    "Lapsed One-Time Buyers": "Low-cost automated win-back (email/push) on the category bought; exclude from paid retargeting.",
    "Recent High-Value": "Convert to second purchase: personalised cross-sell within 30-60 days, premium service.",
    "Recent Low-Value": "Nurture: welcome journey, category discovery, low-cost free-shipping thresholds.",
    "Lapsed High-Value": "Win-back: targeted reactivation offers on previously bought categories.",
    "Lapsed Low-Value": "Low-cost reactivation (email/push only); exclude from paid retargeting.",
}
RFM_STRATEGIES = {
    "Champions": "Reward and retain; ask for reviews/referrals.",
    "Loyal - Lapsing": "Re-engage loyal buyers before they churn.",
    "New High-Value": "Onboard and drive the second order.",
    "New Low-Value": "Nurture with discovery content.",
    "Needs Attention": "Time-limited incentive to return.",
    "At Risk - High Value": "Personal win-back offer.",
    "Hibernating": "Low-cost automated reactivation only.",
}


def rfm_table(cm: pd.DataFrame) -> pd.DataFrame:
    snapshot = cm.last_order.max().normalize() + pd.Timedelta(days=1)
    rfm = pd.DataFrame({
        "customer_unique_id": cm.customer_unique_id,
        "recency_days": (snapshot - cm.last_order.dt.normalize()).dt.days,
        "frequency": cm.orders.astype(int),
        "monetary": cm.revenue.round(2),
        "customer_state": cm.customer_state,
    })
    # Same scoring rules as SQL Q17 / mv_customer_rfm (quintiles; F is categorical because ~97% buy once)
    rfm["r_score"] = 6 - pd.qcut(rfm.recency_days.rank(method="first"), 5, labels=False).add(1)
    rfm["f_score"] = np.select([rfm.frequency >= 3, rfm.frequency == 2], [5, 4], 1)
    rfm["m_score"] = pd.qcut(rfm.monetary.rank(method="first"), 5, labels=False).add(1)
    rfm["rfm_segment"] = np.select(
        [(rfm.f_score >= 4) & (rfm.r_score >= 4), rfm.f_score >= 4, (rfm.r_score >= 4) & (rfm.m_score >= 4),
         rfm.r_score >= 4, rfm.r_score == 3, rfm.m_score >= 4],
        ["Champions", "Loyal - Lapsing", "New High-Value", "New Low-Value", "Needs Attention", "At Risk - High Value"],
        "Hibernating")
    return rfm


def name_clusters(profile: pd.DataFrame, overall: pd.DataFrame) -> dict[int, str]:
    med_r, med_m = overall.recency_days.median(), overall.monetary.median()
    names: dict[int, str] = {}
    for c, row in profile.iterrows():
        if row.frequency_mean >= 1.5:
            n = "Loyal Repeat Buyers"
        else:
            recent = row.recency_median <= med_r
            ratio = row.monetary_median / med_m
            # value qualifier only when spend differs materially (>20%) from the overall median
            if ratio >= 1.2:
                n = ("Recent" if recent else "Lapsed") + " High-Value"
            elif ratio <= 0.8:
                n = ("Recent" if recent else "Lapsed") + " Low-Value"
            else:
                n = ("Recent" if recent else "Lapsed") + " One-Time Buyers"
        names[c] = n
    # disambiguate duplicates by monetary order
    seen: dict[str, int] = {}
    for c in profile.sort_values("monetary_median", ascending=False).index:
        n = names[c]
        seen[n] = seen.get(n, 0) + 1
        if seen[n] > 1:
            names[c] = f"{n} ({seen[n]})"
    return names


def train(k_range=range(2, 11), sample_size: int = 15000) -> dict:
    cm = load_processed("customer_mart")
    rfm = rfm_table(cm)
    X_raw = np.log1p(rfm[["recency_days", "frequency", "monetary"]].astype(float))
    scaler = StandardScaler().fit(X_raw)
    X = scaler.transform(X_raw)
    rng = np.random.default_rng(SEED)
    idx = rng.choice(len(X), size=min(sample_size, len(X)), replace=False)

    curve = []
    for k in k_range:
        km = KMeans(n_clusters=k, n_init=10, random_state=SEED).fit(X)
        sil = silhouette_score(X[idx], km.labels_[idx]) if k > 1 else np.nan
        curve.append({"k": k, "inertia": float(km.inertia_), "silhouette": float(sil)})
    curve_df = pd.DataFrame(curve)
    eligible = curve_df[curve_df.k.between(3, 8)]
    best_k = int(eligible.loc[eligible.silhouette.idxmax(), "k"])
    model = KMeans(n_clusters=best_k, n_init=20, random_state=SEED).fit(X)
    rfm["cluster"] = model.labels_

    prof = rfm.groupby("cluster").agg(customers=("customer_unique_id", "size"),
                                      recency_mean=("recency_days", "mean"), recency_median=("recency_days", "median"),
                                      frequency_mean=("frequency", "mean"), monetary_mean=("monetary", "mean"),
                                      monetary_median=("monetary", "median"), revenue=("monetary", "sum"))
    names = name_clusters(prof, rfm)
    prof["cluster_name"] = prof.index.map(names)
    prof["revenue_share_pct"] = (100 * prof.revenue / prof.revenue.sum()).round(2)
    prof["customer_share_pct"] = (100 * prof.customers / prof.customers.sum()).round(2)
    prof["recommended_strategy"] = prof.cluster_name.map(lambda n: STRATEGIES.get(n.split(" (")[0], ""))
    rfm["cluster_name"] = rfm.cluster.map(names)
    rfm["recommended_strategy"] = rfm.cluster_name.map(lambda n: STRATEGIES.get(n.split(" (")[0], ""))
    rfm_prof = rfm.groupby("rfm_segment").agg(customers=("customer_unique_id", "size"),
                                              avg_recency=("recency_days", "mean"), avg_monetary=("monetary", "mean"),
                                              revenue=("monetary", "sum")).reset_index()
    rfm_prof["strategy"] = rfm_prof.rfm_segment.map(RFM_STRATEGIES)

    # ---- persist
    save_model({"scaler": scaler, "kmeans": model, "cluster_names": names,
                "features": ["recency_days", "frequency", "monetary"], "transform": "log1p"}, MODULE, "kmeans_rfm")
    rfm.to_parquet(settings.processed_dir / "customer_segments.parquet", index=False)
    prof.reset_index().to_csv(REPORT_DIR / "segmentation_cluster_profile.csv", index=False)
    rfm_prof.to_csv(REPORT_DIR / "segmentation_rfm_profile.csv", index=False)
    curve_df.to_csv(REPORT_DIR / "segmentation_k_selection.csv", index=False)

    fig, ax1 = plt.subplots(figsize=(8, 4.5))
    ax1.plot(curve_df.k, curve_df.inertia, "o-", color="#13294b", label="Inertia (within-cluster SS)")
    ax1.set_xlabel("Number of clusters k"); ax1.set_ylabel("Inertia")
    ax2 = ax1.twinx()
    ax2.plot(curve_df.k, curve_df.silhouette, "s--", color="#14b8a6", label="Silhouette (15k sample)")
    ax2.set_ylabel("Silhouette score")
    ax1.axvline(best_k, color="#ef4444", ls=":", label=f"Selected k={best_k}")
    fig.legend(loc="upper right", bbox_to_anchor=(0.88, 0.88), fontsize=8)
    ax1.set_title("K-Means model selection: elbow & silhouette (RFM, log-scaled)")
    fig.tight_layout(); fig.savefig(FIG_DIR / "segmentation_elbow_silhouette.png", dpi=130); plt.close(fig)

    metrics = {
        "customers": int(len(rfm)), "selected_k": best_k,
        "silhouette_selected": float(eligible.silhouette.max()),
        "k_curve": curve, "clusters": prof.reset_index().to_dict(orient="records"),
        "rfm_segments": rfm_prof.to_dict(orient="records"),
        "snapshot_date": str(cm.last_order.max().normalize() + pd.Timedelta(days=1)),
    }
    save_json(metadata(MODULE, algorithm="KMeans", **{k: v for k, v in metrics.items() if k != "clusters"}),
              MODULE, "metadata")
    save_json(metrics, MODULE, "metrics")
    return metrics


def assign_segment(recency_days: float, frequency: float, monetary: float, bundle: dict | None = None) -> dict:
    """Score a single customer with the saved model (used by the API)."""
    from ml.common import load_model

    b = bundle or load_model(MODULE, "kmeans_rfm")
    x = b["scaler"].transform(np.log1p(np.array([[recency_days, frequency, monetary]], dtype=float)))
    c = int(b["kmeans"].predict(x)[0])
    name = b["cluster_names"][c]
    return {"cluster": c, "cluster_name": name, "recommended_strategy": STRATEGIES.get(name.split(" (")[0], "")}


if __name__ == "__main__":
    m = train()
    print("k =", m["selected_k"], "silhouette =", round(m["silhouette_selected"], 4))
