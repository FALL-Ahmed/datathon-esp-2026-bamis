"""
Construit les matrices X/y finales a partir de feature_matrix_transactions,
en appliquant le split temporel (validation/temporal_split.py). La liste de
features est celle definie dans feature_engineering/feature_store.py ->
FEATURE_COLUMNS (rule_R1...R7 volontairement exclues, voir la justification
dans ce module).

Usage :
    depuis modeling/train.py
"""
from __future__ import annotations

import pandas as pd

from bamis_fraud.feature_engineering.feature_store import FEATURE_COLUMNS
from bamis_fraud.validation.temporal_split import load_validation_config, make_rolling_time_splits
from bamis_fraud.validation.leakage_checks import run_all_checks


def load_feature_matrix(path: str = "data/features/feature_matrix_transactions.parquet") -> pd.DataFrame:
    return pd.read_parquet(path)


def build_model_matrix(df: pd.DataFrame, target_col: str = "pseudo_label_fraud") -> tuple[pd.DataFrame, pd.Series]:
    X = df[FEATURE_COLUMNS].copy()
    y = df[target_col].astype(int)
    return X, y


def prepare_splits(
    df: pd.DataFrame, config_path: str = "configs/config.yaml"
) -> dict:
    """Calcule les folds walk-forward + le holdout final, VERIFIE
    automatiquement l'absence de fuite (leve une exception sinon), et
    retourne tout ce qu'il faut pour l'entrainement."""
    cfg = load_validation_config(config_path)
    result = make_rolling_time_splits(
        df,
        n_folds=cfg["n_folds"],
        embargo=cfg["embargo"],
        holdout_fraction=cfg["test_holdout_fraction_of_timeline"],
    )
    # fail fast si un probleme de fuite est detecte -- pas d'entrainement
    # sur des folds non valides
    run_all_checks(df, result["folds"], cfg["embargo"])

    X, y = build_model_matrix(df)
    result["X"] = X
    result["y"] = y
    return result
