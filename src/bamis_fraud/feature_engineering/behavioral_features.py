"""
Compare chaque transaction non pas au seuil du service, mais a l'HISTORIQUE
PROPRE du client (montant median, montant maximum habituel, frequence) --
deuxieme comparaison obligatoire du cahier des charges ("vous devez
comparer chaque montant [...] a l'habitude du client, calculee sur son
propre historique"). C'est aussi le principal levier CONTRE LES FAUX
POSITIFS : un marchand qui reçoit de gros montants tous les jours ne doit
pas être signalé par rapport au seuil du service, mais son *écart à sa
propre normalité* doit rester faible -- l'exemple concret trouvé pendant
l'audit (un compte a 3400 operations/24h, actif ainsi depuis 4 ans) est
precisement le cas que ces features doivent neutraliser.

FEATURES PRODUITES
-------------------
- amount_to_customer_median_ratio
- amount_to_customer_habitual_max_ratio
- zscore_vs_customer_history
- is_new_beneficiary (F-03 : nouveau beneficiaire jamais vu avant)
- days_since_last_transaction
- n_transactions_historique (profondeur de l'historique disponible -- une
  transaction avec peu d'historique doit voir ses ratios ci-dessus traites
  avec prudence par le modele, ce compteur le permet)

ATTENTION LEAKAGE (verifie par construction ici, pas seulement documente)
--------------------------------------------------------------------------
Toute statistique "historique du client" est calculee en EXPANDING WINDOW
puis DECALEE D'UNE LIGNE (shift) pour n'inclure que les transactions
STRICTEMENT ANTERIEURES a la ligne courante -- la transaction courante ne
doit jamais contribuer a sa propre comparaison. La toute premiere
transaction d'un client n'a donc aucun historique (valeurs NaN) : c'est
attendu, pas un bug -- voir n_transactions_historique == 0.

Usage :
    python -m bamis_fraud.feature_engineering.behavioral_features --input data/processed/transactions_clean.parquet
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


def add_behavioral_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values(["source_customer_id", "TRANSACTION_DATE"]).copy()
    gkey = df["source_customer_id"]

    df["n_transactions_historique"] = df.groupby(gkey).cumcount()

    # IMPORTANT : on decale le MONTANT par groupe D'ABORD (shift respecte les
    # frontieres de groupe via groupby), puis on calcule l'expanding sur la
    # serie decalee. Faire l'inverse (expanding().shift(1)) est un piege :
    # le shift() final s'applique alors au tableau A PLAT, sans respecter
    # les frontieres de client, et fait fuiter la derniere valeur d'un
    # client dans la premiere ligne du client suivant.
    amt_shifted = df.groupby(gkey)["TRANSACTION_AMOUNT"].shift(1)
    g_shifted = amt_shifted.groupby(gkey)

    df["customer_median_past"] = g_shifted.expanding().median().reset_index(level=0, drop=True)
    df["customer_max_past"] = g_shifted.expanding().max().reset_index(level=0, drop=True)
    df["customer_mean_past"] = g_shifted.expanding().mean().reset_index(level=0, drop=True)
    df["customer_std_past"] = g_shifted.expanding().std().reset_index(level=0, drop=True)

    df["amount_to_customer_median_ratio"] = (
        df["TRANSACTION_AMOUNT"] / df["customer_median_past"]
    )
    df["amount_to_customer_habitual_max_ratio"] = (
        df["TRANSACTION_AMOUNT"] / df["customer_max_past"]
    )
    df["zscore_vs_customer_history"] = (
        df["TRANSACTION_AMOUNT"] - df["customer_mean_past"]
    ) / df["customer_std_past"].replace(0, np.nan)

    # frequence : delai depuis la derniere transaction du meme client
    prev_date = df.groupby("source_customer_id", group_keys=False)["TRANSACTION_DATE"].shift(1)
    df["days_since_last_transaction"] = (df["TRANSACTION_DATE"] - prev_date).dt.total_seconds() / 86400

    # F-03 : nouveau beneficiaire jamais vu avant par ce client
    def _is_new_beneficiary(group: pd.DataFrame) -> pd.Series:
        seen = set()
        flags = []
        for dest in group["DESTINATION_PHONE"]:
            flags.append(dest != "" and dest not in seen)
            if dest != "":
                seen.add(dest)
        return pd.Series(flags, index=group.index)

    df["is_new_beneficiary"] = (
        df.groupby("source_customer_id", group_keys=False)[["DESTINATION_PHONE"]]
        .apply(_is_new_beneficiary)
    )

    return df


def main() -> None:
    import argparse
    import time

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", default="data/features/behavioral_features.parquet")
    args = parser.parse_args()

    df = pd.read_parquet(args.input)
    t0 = time.time()
    df = add_behavioral_features(df)
    print(f"Features comportementales calculees en {time.time() - t0:.1f}s")

    keep_cols = [
        "TRANSACTION_CODE",
        "source_customer_id",
        "TRANSACTION_DATE",
        "n_transactions_historique",
        "amount_to_customer_median_ratio",
        "amount_to_customer_habitual_max_ratio",
        "zscore_vs_customer_history",
        "days_since_last_transaction",
        "is_new_beneficiary",
    ]
    out_df = df[keep_cols]

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_parquet(out_path, index=False)

    n_no_history = int((out_df["n_transactions_historique"] == 0).sum())
    print(f"{len(out_df):,} lignes ecrites dans {out_path}")
    print(f"Transactions sans historique (premiere du client) : {n_no_history:,} "
          f"({n_no_history / len(out_df):.2%})")
    print(f"Part avec nouveau beneficiaire (F-03) : {out_df['is_new_beneficiary'].mean():.2%}")
    print("amount_to_customer_median_ratio (avec historique) :")
    with_hist = out_df[out_df["n_transactions_historique"] > 0]
    print(with_hist["amount_to_customer_median_ratio"].describe())


if __name__ == "__main__":
    main()
