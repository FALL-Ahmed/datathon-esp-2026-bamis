"""
Nettoyage post-audit : dedoublonnage, normalisation des chaines (codes
service, statuts), gestion explicite des valeurs manquantes selon leur
signification metier.

Attention F-06 (doublon) : deux lignes avec meme montant / meme
beneficiaire a quelques minutes d'intervalle sont un signal de fraude, pas
une erreur de saisie a dedupliquer aveuglement. Le dedoublonnage ne cible
que les doublons TECHNIQUES (meme TRANSACTION_CODE reimporte, n'arrive
jamais sur ce fichier d'apres l'audit mais garde par robustesse pour un
futur fichier de test). Un flag is_probable_duplicate_pair_f06 est cree en
feature pour les doublons FONCTIONNELS, jamais supprime.

Decision sur TRANSACTION_STATUS (5 valeurs observees : VALIDATED 88.1%,
REJECTED 8.4%, INCOMPLETE 2.9%, REGISTERED 0.7%, EXPIRED <0.01%) : toutes
les lignes sont conservees (une tentative rejetee peut etre un signal utile,
ex. F-04/F-05), mais une colonne is_validated est ajoutee pour permettre au
feature engineering de restreindre les agregats de montant (historique,
seuils) aux seules transactions reellement executees -- inclure des
montants REJECTED/INCOMPLETE dans un cumul de seuil n'aurait pas de sens
metier (l'argent n'a pas bouge), et on a deja vu que les montants
REGISTERED peuvent etre corrompus (cf. ingestion/validators.py).

Usage :
    python -m bamis_fraud.preprocessing.cleaning --input data/interim/transactions_raw_typed.parquet
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

# Fenetre de detection F-06 (doublon) : deux operations identiques
# (memes telephones source/destination, meme montant) survenant a moins de
# ce delai l'une de l'autre sont flaguees comme doublon fonctionnel probable.
F06_WINDOW_MINUTES = 10


def drop_technical_duplicates(df: pd.DataFrame) -> pd.DataFrame:
    before = len(df)
    df = df.drop_duplicates(subset=["TRANSACTION_CODE"], keep="first")
    dropped = before - len(df)
    if dropped:
        print(f"drop_technical_duplicates: {dropped} lignes supprimees (TRANSACTION_CODE duplique)")
    return df


def flag_functional_duplicates(
    df: pd.DataFrame, window_minutes: int = F06_WINDOW_MINUTES
) -> pd.DataFrame:
    """F-06 : meme montant, meme beneficiaire, revient deux fois en
    quelques minutes. Ajoute une colonne booleenne, ne supprime rien."""
    df = df.sort_values("TRANSACTION_DATE").copy()
    group_cols = ["SOURCE_PHONE", "DESTINATION_PHONE", "TRANSACTION_AMOUNT"]
    prev_date = df.groupby(group_cols, observed=True)["TRANSACTION_DATE"].shift(1)
    delta = df["TRANSACTION_DATE"] - prev_date
    df["is_probable_duplicate_pair_f06"] = delta.notna() & (
        delta <= pd.Timedelta(minutes=window_minutes)
    )
    return df


def normalize_categoricals(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for col in ["SERVICE_CODE", "TRANSACTION_STATUS"]:
        df[col] = df[col].astype(str).str.strip().str.upper().astype("category")
    return df


def add_is_validated_flag(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["is_validated"] = df["TRANSACTION_STATUS"] == "VALIDATED"
    return df


def resolve_internal_vs_external(df: pd.DataFrame) -> pd.DataFrame:
    """Regle du cahier des charges : DESTINATION_CUSTOMER vide = interne,
    rempli = externe (GIMTEL). Meilleur candidat actuel pour cette colonne :
    SOURCE_CUSTOMER_or_DESTINATION_CUSTOMER_candidate (position 15, ~1.1%
    rempli sur le fichier complet -- cf. configs/schema_map.yaml, confidence
    'low'). CE MAPPING N'EST PAS CONFIRME -- is_external_gimtel doit etre
    revalide des que la colonne interne/externe est confirmee aupres des
    organisateurs. Traite comme le meilleur candidat disponible, pas comme
    une certitude."""
    df = df.copy()
    col = "SOURCE_CUSTOMER_or_DESTINATION_CUSTOMER_candidate"
    df["is_external_gimtel"] = df[col].astype(str).str.strip() != ""
    return df


def clean_transactions(df: pd.DataFrame) -> pd.DataFrame:
    df = drop_technical_duplicates(df)
    df = normalize_categoricals(df)
    df = add_is_validated_flag(df)
    df = resolve_internal_vs_external(df)
    df = flag_functional_duplicates(df)
    return df


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", default="data/processed/transactions_clean.parquet")
    args = parser.parse_args()

    df = pd.read_parquet(args.input)
    n_in = len(df)
    df = clean_transactions(df)

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out_path, index=False)

    print(f"\n{n_in:,} lignes en entree -> {len(df):,} lignes en sortie")
    print(f"Doublons fonctionnels F-06 flagues : {int(df['is_probable_duplicate_pair_f06'].sum()):,}")
    print(f"Transactions validees : {int(df['is_validated'].sum()):,} / {len(df):,}")
    print(f"Transactions externes GIMTEL (candidat) : {int(df['is_external_gimtel'].sum()):,} / {len(df):,}")
    print(f"Ecrit dans {out_path}")


if __name__ == "__main__":
    main()
