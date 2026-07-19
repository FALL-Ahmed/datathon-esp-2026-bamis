"""
Traduit la regle metier centrale du defi : "le montant seul ne suffit pas,
il faut comparer au seuil du SERVICE". Toutes les valeurs de seuil sont
lues depuis configs/thresholds/seuils_services.csv (jamais codees en dur) --
voir configs/thresholds/README_SEUILS.md, le fichier actuel est un
placeholder recree depuis le cahier des charges, a remplacer par le fichier
officiel des sa reception, sans changer une ligne de code ici.

FEATURES PRODUITES
-------------------
- amount_to_service_threshold_ratio = TRANSACTION_AMOUNT / seuil_vigilance_unitaire
- is_above_unit_threshold (bool)
- distance_to_threshold = seuil_vigilance_unitaire - TRANSACTION_AMOUNT
  (proche de 0 et positif = signal C-01 fractionnement)
- daily_cumulative_amount = cumul du jour, meme client + meme service,
  TOUTES transactions validees jusqu'a et y compris la ligne courante
- daily_cumulative_ratio = daily_cumulative_amount / seuil_cumul_journalier

Usage :
    python -m bamis_fraud.feature_engineering.threshold_features --input data/processed/transactions_clean.parquet
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd


def load_thresholds(path: str | Path) -> pd.DataFrame:
    thresholds = pd.read_csv(path)
    thresholds["SERVICE_CODE"] = thresholds["SERVICE_CODE"].astype(str).str.strip().str.upper()
    return thresholds


def add_threshold_ratio_features(df: pd.DataFrame, thresholds: pd.DataFrame) -> pd.DataFrame:
    df = df.merge(thresholds, on="SERVICE_CODE", how="left")

    n_unmatched = df["SEUIL_VIGILANCE_UNITAIRE_MRU"].isna().sum()
    if n_unmatched:
        print(
            f"ATTENTION : {n_unmatched} lignes sans seuil correspondant "
            f"(SERVICE_CODE absent de seuils_services.csv) -- a investiguer"
        )

    df["amount_to_service_threshold_ratio"] = (
        df["TRANSACTION_AMOUNT"] / df["SEUIL_VIGILANCE_UNITAIRE_MRU"]
    )
    df["is_above_unit_threshold"] = df["amount_to_service_threshold_ratio"] > 1.0
    df["distance_to_threshold"] = df["SEUIL_VIGILANCE_UNITAIRE_MRU"] - df["TRANSACTION_AMOUNT"]
    return df


def add_daily_cumulative_features(df: pd.DataFrame) -> pd.DataFrame:
    """Cumul journalier PAR CLIENT ET PAR SERVICE, tous canaux confondus
    (le canal n'intervient pas dans le regroupement -- c'est precisement ce
    qui empeche le contournement C-08). Seules les transactions VALIDATED
    comptent dans le cumul reel (l'argent n'a pas bouge sinon)."""
    df = df.sort_values("TRANSACTION_DATE").copy()
    df["transaction_day"] = df["TRANSACTION_DATE"].dt.date

    validated_amount = df["TRANSACTION_AMOUNT"].where(df["is_validated"], 0.0)
    group_cols = ["source_customer_id", "SERVICE_CODE", "transaction_day"]
    df["daily_cumulative_amount"] = validated_amount.groupby(
        [df[c] for c in group_cols]
    ).cumsum()

    df["daily_cumulative_ratio"] = (
        df["daily_cumulative_amount"] / df["SEUIL_CUMUL_JOURNALIER_MRU"]
    )
    return df


def build_threshold_features(df: pd.DataFrame, thresholds_path: str | Path) -> pd.DataFrame:
    thresholds = load_thresholds(thresholds_path)
    df = add_threshold_ratio_features(df, thresholds)
    df = add_daily_cumulative_features(df)
    return df


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--thresholds", default="configs/thresholds/seuils_services.csv")
    parser.add_argument("--output", default="data/features/threshold_features.parquet")
    args = parser.parse_args()

    df = pd.read_parquet(args.input)
    df = build_threshold_features(df, args.thresholds)

    keep_cols = [
        "TRANSACTION_CODE",
        "source_customer_id",
        "SERVICE_CODE",
        "TRANSACTION_DATE",
        "TRANSACTION_AMOUNT",
        "amount_to_service_threshold_ratio",
        "is_above_unit_threshold",
        "distance_to_threshold",
        "daily_cumulative_amount",
        "daily_cumulative_ratio",
    ]
    out_df = df[keep_cols]

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_parquet(out_path, index=False)

    print(f"{len(out_df):,} lignes de features seuil ecrites dans {out_path}")
    print(f"Part au-dessus du seuil unitaire : {out_df['is_above_unit_threshold'].mean():.2%}")
    near_threshold = out_df["amount_to_service_threshold_ratio"].between(0.8, 1.0)
    print(f"Part entre 80% et 100% du seuil (signal fractionnement C-01) : {near_threshold.mean():.2%}")


if __name__ == "__main__":
    main()
