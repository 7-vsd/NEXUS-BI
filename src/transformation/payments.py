"""Payments transform: standardise payment types and installments."""
from __future__ import annotations

import pandas as pd

from src.transformation.common import CleaningLog, drop_exact_duplicates

DATASET = "payments"
PAYMENT_TYPE_LABELS = {
    "credit_card": "Credit Card",
    "boleto": "Boleto (Bank Slip)",
    "voucher": "Voucher",
    "debit_card": "Debit Card",
    "not_defined": "Not Defined",
}


def transform(df: pd.DataFrame, log: CleaningLog) -> pd.DataFrame:
    out = drop_exact_duplicates(df.copy(), DATASET, log, ["order_id", "payment_sequential"])
    out["payment_type"] = out.payment_type.str.strip().str.lower()
    zero_inst = out.payment_installments < 1
    log.add(DATASET, "installments_0_to_1", int(zero_inst.sum()), "a payment has at least 1 installment")
    out.loc[zero_inst, "payment_installments"] = 1
    out["payment_value"] = out.payment_value.round(2)
    return out.reset_index(drop=True)
