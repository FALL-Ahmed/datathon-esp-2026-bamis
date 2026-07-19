"""
Filet de securite automatique contre la fuite temporelle, explicitement
listee comme piege n1 du cahier des charges ("calculer les habitudes d'un
client avec des donnees futures").

CONTROLES IMPLEMENTES (executes sur chaque fold produit par
validation/temporal_split.py, avant tout entrainement)
------------------------------------------------------------
1. check_no_date_overlap : aucune transaction de validation ne doit avoir
   une TRANSACTION_DATE anterieure a la derniere transaction d'entrainement
   (le split est bien chronologique, pas melange).
2. check_embargo_respected : l'ecart entre la derniere date d'entrainement
   et la premiere date de validation doit etre >= embargo configure.
3. check_no_duplicate_transaction_code : aucun TRANSACTION_CODE ne doit
   apparaitre a la fois dans train et dans validation.

Ce module ECHOUE EXPLICITEMENT (leve une exception) si un controle rate --
pas de warning silencieux. Un entrainement ne doit jamais demarrer sur des
folds qui n'ont pas passe ces controles.

Usage :
    python -m bamis_fraud.validation.leakage_checks
"""
from __future__ import annotations

import pandas as pd


class LeakageError(Exception):
    pass


def check_no_date_overlap(df: pd.DataFrame, train_idx, valid_idx, date_col: str = "TRANSACTION_DATE") -> None:
    max_train_date = df.loc[train_idx, date_col].max()
    min_valid_date = df.loc[valid_idx, date_col].min()
    if min_valid_date <= max_train_date:
        raise LeakageError(
            f"Chevauchement temporel : derniere date train ({max_train_date}) "
            f">= premiere date valid ({min_valid_date})"
        )


def check_embargo_respected(
    df: pd.DataFrame, train_idx, valid_idx, embargo: str, date_col: str = "TRANSACTION_DATE"
) -> None:
    max_train_date = df.loc[train_idx, date_col].max()
    min_valid_date = df.loc[valid_idx, date_col].min()
    gap = min_valid_date - max_train_date
    embargo_td = pd.Timedelta(embargo)
    if gap < embargo_td:
        raise LeakageError(
            f"Embargo non respecte : ecart reel {gap} < embargo configure {embargo_td}"
        )


def check_no_duplicate_transaction_code(
    df: pd.DataFrame, train_idx, valid_idx, id_col: str = "TRANSACTION_CODE"
) -> None:
    train_ids = set(df.loc[train_idx, id_col])
    valid_ids = set(df.loc[valid_idx, id_col])
    overlap = train_ids & valid_ids
    if overlap:
        raise LeakageError(f"{len(overlap)} TRANSACTION_CODE presents a la fois dans train et valid")


def run_all_checks(df: pd.DataFrame, folds: list, embargo: str) -> dict:
    """Execute les 3 controles sur chaque fold. Leve LeakageError au premier
    echec (fail fast) -- ne retourne un rapport que si TOUT est passe."""
    report = {"n_folds_checked": len(folds), "embargo": embargo, "status": "PASS"}
    for i, (train_idx, valid_idx) in enumerate(folds, start=1):
        check_no_date_overlap(df, train_idx, valid_idx)
        check_embargo_respected(df, train_idx, valid_idx, embargo)
        check_no_duplicate_transaction_code(df, train_idx, valid_idx)
        report[f"fold_{i}"] = "PASS"
    return report


def main() -> None:
    import json
    from pathlib import Path

    from bamis_fraud.validation.temporal_split import load_validation_config, make_rolling_time_splits

    df = pd.read_parquet(
        "data/features/feature_matrix_transactions.parquet",
        columns=["TRANSACTION_CODE", "TRANSACTION_DATE"],
    )
    cfg = load_validation_config()
    result = make_rolling_time_splits(
        df, n_folds=cfg["n_folds"], embargo=cfg["embargo"],
        holdout_fraction=cfg["test_holdout_fraction_of_timeline"],
    )

    report = run_all_checks(df, result["folds"], cfg["embargo"])

    out_path = Path("outputs/reports/leakage_check_report.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)

    print(f"Controles anti-fuite : {report['status']} sur {report['n_folds_checked']} folds")
    print(f"Rapport ecrit dans {out_path}")


if __name__ == "__main__":
    main()
