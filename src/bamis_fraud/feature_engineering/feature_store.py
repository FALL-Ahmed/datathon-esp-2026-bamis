"""
Point de jonction unique : assemble toutes les tables de features
transaction (threshold, behavioral, velocity, network_light) en une seule
table, avec la cible d'entrainement (pseudo_label_fraud, cf.
rules/business_rules.py).

DECISION IMPORTANTE SUR LES COLONNES INCLUSES : les flags de regles
individuels (rule_R1...rule_R7) NE SONT PAS inclus comme features
d'entree du modele, alors que rule_flags.parquet est bien la source de la
cible (pseudo_label_fraud = au moins 2 regles declenchees). Raison : ces
flags sont litteralement les ingredients qui construisent la cible -- les
inclure comme feature permettrait au modele d'apprendre une simple
recopie de la formule des regles (fuite triviale, cf. l'avertissement deja
present dans rules/business_rules.py) au lieu d'apprendre a generaliser a
partir des signaux BRUTS continus (ratios, compteurs, z-scores). C'est
precisement la valeur ajoutee du "niveau 2 : machine learning" par rapport
au "niveau 1 : regles" decrite dans le cahier des charges -- le modele doit
apprendre un signal plus fin que la simple somme des regles, pas la
reproduire a l'identique.

Garantit :
- meme cle de jointure partout (TRANSACTION_CODE)
- pas de colonne dupliquee entre modules
- un seul point a modifier pour ajouter/retirer une feature du modele
  (voir configs/feature_config.yaml pour la liste des features actives)

ENTREES
-------
- data/processed/transactions_clean.parquet
- data/features/threshold_features.parquet
- data/features/behavioral_features.parquet
- data/features/velocity_features.parquet
- data/features/network_features_light.parquet
- data/features/rule_flags.parquet (uniquement pour la cible)

SORTIES
-------
- data/features/feature_matrix_transactions.parquet

Usage :
    python -m bamis_fraud.feature_engineering.feature_store
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

# Colonnes brutes gardees comme features numeriques d'entree du modele.
# Deliberement EXCLUES : rule_R1...rule_R7 (voir docstring ci-dessus).
FEATURE_COLUMNS = [
    # threshold_features
    "amount_to_service_threshold_ratio",
    "is_above_unit_threshold",
    "distance_to_threshold",
    "daily_cumulative_amount",
    "daily_cumulative_ratio",
    # behavioral_features
    "n_transactions_historique",
    "amount_to_customer_median_ratio",
    "amount_to_customer_habitual_max_ratio",
    "zscore_vs_customer_history",
    "days_since_last_transaction",
    "is_new_beneficiary",
    # velocity_features
    "nb_transactions_1h", "montant_cumule_1h",
    "nb_transactions_24h", "montant_cumule_24h",
    "nb_transactions_7j", "montant_cumule_7j",
    # network_features_light
    "montant_cumule_envoye_past",
    "montant_cumule_recu_past",
    "ratio_montant_recu_envoye_past",
    "delai_depuis_derniere_reception_minutes",
    "nb_expediteurs_distincts_past",
    "nb_destinataires_distincts_past",
    "is_external_gimtel",
]

BASE_COLUMNS = ["TRANSACTION_CODE", "source_customer_id", "SERVICE_CODE", "TRANSACTION_DATE", "TRANSACTION_AMOUNT"]


def assemble_transaction_features(
    transactions_path: str = "data/processed/transactions_clean.parquet",
    threshold_path: str = "data/features/threshold_features.parquet",
    behavioral_path: str = "data/features/behavioral_features.parquet",
    velocity_path: str = "data/features/velocity_features.parquet",
    network_path: str = "data/features/network_features_light.parquet",
    rule_flags_path: str = "data/features/rule_flags.parquet",
) -> pd.DataFrame:
    base = pd.read_parquet(transactions_path, columns=BASE_COLUMNS)

    threshold = pd.read_parquet(threshold_path).drop(
        columns=["source_customer_id", "SERVICE_CODE", "TRANSACTION_DATE", "TRANSACTION_AMOUNT"]
    )
    behavioral = pd.read_parquet(behavioral_path).drop(columns=["source_customer_id", "TRANSACTION_DATE"])
    velocity = pd.read_parquet(velocity_path).drop(columns=["source_customer_id", "TRANSACTION_DATE"])
    network = pd.read_parquet(network_path).drop(columns=["source_customer_id", "TRANSACTION_DATE"])
    rules = pd.read_parquet(rule_flags_path, columns=["TRANSACTION_CODE", "pseudo_label_fraud"])

    df = base
    for other in [threshold, behavioral, velocity, network, rules]:
        df = df.merge(other, on="TRANSACTION_CODE", how="left")

    return df


def get_feature_target_split(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    """Retourne (X, y) prets pour l'entrainement -- X = uniquement les
    colonnes numeriques brutes (FEATURE_COLUMNS), y = pseudo_label_fraud."""
    X = df[FEATURE_COLUMNS].copy()
    y = df["pseudo_label_fraud"].astype(int)
    return X, y


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="data/features/feature_matrix_transactions.parquet")
    args = parser.parse_args()

    df = assemble_transaction_features()

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out_path, index=False)

    print(f"{len(df):,} lignes, {len(df.columns)} colonnes ecrites dans {out_path}")
    print(f"Colonnes features retenues pour le modele ({len(FEATURE_COLUMNS)}) : {FEATURE_COLUMNS}")
    print(f"\nCible pseudo_label_fraud : {df['pseudo_label_fraud'].sum():,} ({df['pseudo_label_fraud'].mean():.3%})")
    print(f"\nValeurs manquantes par colonne feature :")
    print(df[FEATURE_COLUMNS].isna().sum())


if __name__ == "__main__":
    main()
