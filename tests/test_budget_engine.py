"""
Verifie l'exigence C-08 : une meme somme de transactions sur deux canaux
differents (ex. 3 operations sur l'appli + 2 sur agent, meme client, meme
service, meme jour) doit produire UN SEUL cumul journalier, pas deux
compteurs separes qui repartiraient de zero par canal.
"""
from __future__ import annotations

import pandas as pd

from bamis_fraud.budget.budget_engine import compute_daily_consumption


def _thresholds() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "SERVICE_CODE": ["SERVICE_06"],
            "SEUIL_VIGILANCE_UNITAIRE_MRU": [20000],
            "SEUIL_CUMUL_JOURNALIER_MRU": [80000],
        }
    )


def test_daily_cumulative_sums_across_channels_not_reset_per_channel():
    df = pd.DataFrame(
        {
            "source_customer_id": ["C1"] * 5,
            "SERVICE_CODE": ["SERVICE_06"] * 5,
            "TRANSACTION_DATE": pd.to_datetime(
                ["2026-01-01 08:00", "2026-01-01 09:00", "2026-01-01 10:00",
                 "2026-01-01 14:00", "2026-01-01 15:00"]
            ),
            "TRANSACTION_AMOUNT": [10000, 10000, 10000, 10000, 10000],
            "CHANNEL_TYPE": ["APP", "APP", "APP", "AGENT", "AGENT"],
            "is_validated": [True, True, True, True, True],
        }
    )

    daily = compute_daily_consumption(df, _thresholds())

    # une seule ligne (client x service x jour), pas une par canal
    assert len(daily) == 1
    row = daily.iloc[0]
    assert row["montant_consomme_jour"] == 50000
    assert row["taux_consommation_jour"] == 50000 / 80000


def test_daily_cumulative_excludes_non_validated_transactions():
    df = pd.DataFrame(
        {
            "source_customer_id": ["C1", "C1"],
            "SERVICE_CODE": ["SERVICE_06", "SERVICE_06"],
            "TRANSACTION_DATE": pd.to_datetime(["2026-01-01 08:00", "2026-01-01 09:00"]),
            "TRANSACTION_AMOUNT": [10000, 999999],
            "CHANNEL_TYPE": ["APP", "AGENT"],
            "is_validated": [True, False],
        }
    )

    daily = compute_daily_consumption(df, _thresholds())

    assert daily.iloc[0]["montant_consomme_jour"] == 10000
