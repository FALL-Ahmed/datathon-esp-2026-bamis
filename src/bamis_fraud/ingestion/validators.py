"""
Controles d'integrite executes juste apres le chargement, avant toute
feature engineering. Objectif : detecter au plus tot une regression de
schema, une derive de format de date, ou une explosion de valeurs
manquantes sur une colonne critique.

Usage :
    python -m bamis_fraud.ingestion.validators --input data/interim/transactions_raw_typed.parquet
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

# Borne haute de montant plausible, etablie empiriquement sur le fichier
# complet (voir ARCHITECTURE.md section 0, point 4) : le montant le plus
# eleve parmi les transactions non-aberrantes est 9 000 000 MRU. Les 72
# lignes identifiees comme aberrantes commencent a 10^16 -- aucune valeur
# intermediaire n'existe entre les deux, donc ce seuil separe proprement les
# vraies transactions des valeurs sentinelles corrompues du systeme source
# (toutes au statut REGISTERED, transactions jamais finalisees).
MAX_PLAUSIBLE_AMOUNT = 10_000_000


def check_unique_transaction_code(df: pd.DataFrame) -> dict:
    n_dup = int(df["TRANSACTION_CODE"].duplicated().sum())
    return {"rule": "unique_transaction_code", "passed": n_dup == 0, "n_duplicates": n_dup}


def check_amount_bounded(df: pd.DataFrame, max_amount: float = MAX_PLAUSIBLE_AMOUNT) -> dict:
    outliers = df["TRANSACTION_AMOUNT"] > max_amount
    n_outliers = int(outliers.sum())
    return {
        "rule": "amount_bounded",
        "passed": n_outliers == 0,
        "n_outliers": n_outliers,
        "max_plausible_amount": max_amount,
        "outlier_transaction_codes": df.loc[outliers, "TRANSACTION_CODE"].tolist()[:200],
    }


def check_service_code_in_reference_list(df: pd.DataFrame, thresholds_path: str | Path) -> dict:
    thresholds = pd.read_csv(thresholds_path)
    known = set(thresholds["SERVICE_CODE"].astype(str))
    observed = set(df["SERVICE_CODE"].astype(str).unique())
    unknown = observed - known
    return {
        "rule": "service_code_in_reference_list",
        "passed": len(unknown) == 0,
        "unknown_service_codes": sorted(unknown),
    }


def check_critical_columns_not_empty(df: pd.DataFrame) -> dict:
    critical = ["TRANSACTION_CODE", "SERVICE_CODE", "TRANSACTION_AMOUNT", "TRANSACTION_DATE"]
    results = {}
    all_passed = True
    for col in critical:
        n_missing = int(df[col].isna().sum())
        results[col] = n_missing
        if n_missing > 0:
            all_passed = False
    return {"rule": "critical_columns_not_empty", "passed": all_passed, "n_missing_by_column": results}


def run_all_validations(df: pd.DataFrame, thresholds_path: str | Path) -> dict:
    return {
        "n_rows": len(df),
        "checks": [
            check_unique_transaction_code(df),
            check_amount_bounded(df),
            check_service_code_in_reference_list(df, thresholds_path),
            check_critical_columns_not_empty(df),
        ],
    }


def quarantine_amount_outliers(
    df: pd.DataFrame, max_amount: float = MAX_PLAUSIBLE_AMOUNT
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Isole les lignes a montant aberrant (cf. MAX_PLAUSIBLE_AMOUNT) avant
    tout feature engineering -- une seule valeur non bornee suffit a fausser
    une moyenne glissante ou un ratio pour tout le client concerne."""
    is_valid = df["TRANSACTION_AMOUNT"] <= max_amount
    return df.loc[is_valid].copy(), df.loc[~is_valid].copy()


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--thresholds", default="configs/thresholds/seuils_services.csv")
    parser.add_argument("--output", default="outputs/reports/validation_report.json")
    args = parser.parse_args()

    df = pd.read_parquet(args.input)
    report = run_all_validations(df, args.thresholds)

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"{report['n_rows']:,} lignes validees.")
    for check in report["checks"]:
        status = "OK" if check["passed"] else "ECHEC"
        print(f"  [{status}] {check['rule']}")
    print(f"\nRapport ecrit dans {out_path}")


if __name__ == "__main__":
    main()
