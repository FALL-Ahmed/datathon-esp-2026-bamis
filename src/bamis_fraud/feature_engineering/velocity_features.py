"""
Compteurs glissants (vitesse d'activite) par client, cle du reperage des
rafales (C-07 "trop d'operations") et du fractionnement (C-01). Chaque
fenetre est calculee de maniere STRICTEMENT causale : au moment de la ligne
courante, elle inclut cette ligne et toutes les transactions anterieures du
meme client dans la fenetre -- jamais de transaction future (anti-leakage,
cf. ARCHITECTURE.md section 6).

FEATURES PRODUITES (fenetres 1h / 24h / 7j, glissantes sur TRANSACTION_DATE,
par source_customer_id)
-------------------------------------------------------------------------
- nb_transactions_1h / 24h / 7j
- montant_cumule_1h / 24h / 7j

Pas encore implemente (necessite une agregation plus couteuse, voir note en
fin de fichier) : nb_beneficiaires_distincts, acceleration vs moyenne
habituelle -- laisses pour une iteration suivante une fois le reste du
pipeline stabilise.

Usage :
    python -m bamis_fraud.feature_engineering.velocity_features --input data/processed/transactions_clean.parquet
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

WINDOWS = {"1h": "1h", "24h": "24h", "7j": "7D"}


def add_velocity_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values(["source_customer_id", "TRANSACTION_DATE"]).copy()

    grouped = df.groupby("source_customer_id", group_keys=False)
    for label, pandas_window in WINDOWS.items():
        roll = grouped.rolling(pandas_window, on="TRANSACTION_DATE")["TRANSACTION_AMOUNT"]
        df[f"nb_transactions_{label}"] = roll.count().to_numpy()
        df[f"montant_cumule_{label}"] = roll.sum().to_numpy()

    return df


def main() -> None:
    import argparse
    import time

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", default="data/features/velocity_features.parquet")
    args = parser.parse_args()

    df = pd.read_parquet(args.input)
    t0 = time.time()
    df = add_velocity_features(df)
    print(f"Features de velocite calculees en {time.time() - t0:.1f}s")

    keep_cols = ["TRANSACTION_CODE", "source_customer_id", "TRANSACTION_DATE"] + [
        f"{metric}_{label}" for label in WINDOWS for metric in ("nb_transactions", "montant_cumule")
    ]
    out_df = df[keep_cols]

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_parquet(out_path, index=False)

    print(f"{len(out_df):,} lignes ecrites dans {out_path}")
    print(f"nb_transactions_1h : max={out_df['nb_transactions_1h'].max():.0f}, "
          f"p99={out_df['nb_transactions_1h'].quantile(0.99):.1f}")
    print(f"nb_transactions_24h : max={out_df['nb_transactions_24h'].max():.0f}, "
          f"p99={out_df['nb_transactions_24h'].quantile(0.99):.1f}")


if __name__ == "__main__":
    main()
