"""
Verifie que amount_to_service_threshold_ratio change bien quand
seuils_services.csv change (non-regression sur l'exigence "seuils jamais
en dur") : on charge un seuil alternatif dans le test et on verifie que le
ratio calcule suit.
"""
from __future__ import annotations

import pandas as pd

from bamis_fraud.feature_engineering.threshold_features import (
    add_daily_cumulative_features,
    add_threshold_ratio_features,
)


def _transactions() -> pd.DataFrame:
    return pd.DataFrame({
        "source_customer_id": ["C1"],
        "SERVICE_CODE": ["SERVICE_06"],
        "TRANSACTION_AMOUNT": [10000.0],
        "TRANSACTION_DATE": pd.to_datetime(["2026-01-01 10:00:00"]),
        "is_validated": [True],
    })


def test_ratio_follows_official_threshold_value():
    thresholds = pd.DataFrame({
        "SERVICE_CODE": ["SERVICE_06"],
        "SEUIL_VIGILANCE_UNITAIRE_MRU": [20000],
        "SEUIL_CUMUL_JOURNALIER_MRU": [80000],
    })

    out = add_threshold_ratio_features(_transactions(), thresholds)

    assert out["amount_to_service_threshold_ratio"].iloc[0] == 10000.0 / 20000
    assert out["is_above_unit_threshold"].iloc[0] == False


def test_ratio_changes_when_threshold_file_is_swapped():
    """Le coeur de l'exigence : le meme montant, le meme service, donne un
    ratio DIFFERENT si seuils_services.csv change -- preuve qu'aucune
    valeur de seuil n'est codee en dur dans le code de calcul."""
    thresholds_official = pd.DataFrame({
        "SERVICE_CODE": ["SERVICE_06"],
        "SEUIL_VIGILANCE_UNITAIRE_MRU": [20000],
        "SEUIL_CUMUL_JOURNALIER_MRU": [80000],
    })
    thresholds_alternate = pd.DataFrame({
        "SERVICE_CODE": ["SERVICE_06"],
        "SEUIL_VIGILANCE_UNITAIRE_MRU": [5000],  # seuil modifie par le jury, hypothese
        "SEUIL_CUMUL_JOURNALIER_MRU": [80000],
    })

    ratio_official = add_threshold_ratio_features(_transactions(), thresholds_official)[
        "amount_to_service_threshold_ratio"
    ].iloc[0]
    ratio_alternate = add_threshold_ratio_features(_transactions(), thresholds_alternate)[
        "amount_to_service_threshold_ratio"
    ].iloc[0]

    assert ratio_official != ratio_alternate
    assert ratio_official == 0.5
    assert ratio_alternate == 2.0
    # avec le seuil abaisse a 5000, le meme montant de 10000 passe au-dessus du seuil
    above_official = add_threshold_ratio_features(_transactions(), thresholds_official)[
        "is_above_unit_threshold"
    ].iloc[0]
    above_alternate = add_threshold_ratio_features(_transactions(), thresholds_alternate)[
        "is_above_unit_threshold"
    ].iloc[0]
    assert above_official == False
    assert above_alternate == True


def test_daily_cumulative_ratio_uses_daily_threshold_not_unit_threshold():
    df = pd.DataFrame({
        "source_customer_id": ["C1", "C1"],
        "SERVICE_CODE": ["SERVICE_06", "SERVICE_06"],
        "TRANSACTION_AMOUNT": [30000.0, 30000.0],
        "TRANSACTION_DATE": pd.to_datetime(["2026-01-01 09:00:00", "2026-01-01 15:00:00"]),
        "is_validated": [True, True],
        "SEUIL_CUMUL_JOURNALIER_MRU": [80000, 80000],
    })

    out = add_daily_cumulative_features(df)

    assert out["daily_cumulative_amount"].iloc[-1] == 60000
    assert out["daily_cumulative_ratio"].iloc[-1] == 60000 / 80000
