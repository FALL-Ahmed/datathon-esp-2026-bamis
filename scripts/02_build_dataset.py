"""
Etape 2/10. Charge le CSV brut (bamis_fraud.ingestion.loader), met en
quarantaine les dates et montants aberrants (bamis_fraud.ingestion.validators),
puis nettoie et resout l'identifiant client
(bamis_fraud.preprocessing.cleaning, .customer_resolution).

Usage :
    python scripts/02_build_dataset.py --input data/raw/DATASET_ESP-2026.csv

Sorties :
    data/interim/transactions_raw_typed.parquet
    data/interim/transactions_quarantined_dates.parquet
    data/interim/transactions_quarantined_amounts.parquet
    data/processed/transactions_clean.parquet
    data/processed/customer_phone_map.parquet
"""
from __future__ import annotations

import argparse
import time
from pathlib import Path

from bamis_fraud.ingestion.loader import load_transactions, quarantine_invalid_dates
from bamis_fraud.ingestion.validators import quarantine_amount_outliers
from bamis_fraud.preprocessing.cleaning import clean_transactions
from bamis_fraud.preprocessing.customer_resolution import (
    build_customer_id,
    build_phone_activity_table,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default="data/raw/DATASET_ESP-2026.csv")
    parser.add_argument("--schema-map", default="configs/schema_map.yaml")
    args = parser.parse_args()

    t0 = time.time()
    print("Chargement du CSV brut...")
    df = load_transactions(args.input, args.schema_map)
    print(f"  {len(df):,} lignes chargees en {time.time() - t0:.1f}s")

    df, quarantined_dates = quarantine_invalid_dates(df)
    if len(quarantined_dates):
        Path("data/interim").mkdir(parents=True, exist_ok=True)
        quarantined_dates.to_parquet("data/interim/transactions_quarantined_dates.parquet", index=False)
    print(f"  {len(quarantined_dates)} lignes a date aberrante mises en quarantaine")

    df, quarantined_amounts = quarantine_amount_outliers(df)
    if len(quarantined_amounts):
        quarantined_amounts.to_parquet("data/interim/transactions_quarantined_amounts.parquet", index=False)
    print(f"  {len(quarantined_amounts)} lignes a montant aberrant mises en quarantaine")

    Path("data/interim").mkdir(parents=True, exist_ok=True)
    df.to_parquet("data/interim/transactions_raw_typed.parquet", index=False)

    print("Nettoyage...")
    df = clean_transactions(df)
    df = build_customer_id(df)

    Path("data/processed").mkdir(parents=True, exist_ok=True)
    df.to_parquet("data/processed/transactions_clean.parquet", index=False)
    print(f"  {len(df):,} lignes propres ecrites dans data/processed/transactions_clean.parquet")

    activity = build_phone_activity_table(df)
    activity.to_parquet("data/processed/customer_phone_map.parquet", index=False)
    print(f"  {len(activity):,} telephones distincts ecrits dans data/processed/customer_phone_map.parquet")

    print(f"Etape 2 terminee en {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
