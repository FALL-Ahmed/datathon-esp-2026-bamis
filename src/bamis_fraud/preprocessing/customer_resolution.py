"""
Construit un identifiant client stable a partir du telephone, faute d'une
colonne SOURCE_CUSTOMER fiable dans le fichier source.

CONTEXTE IMPORTANT (voir configs/schema_map.yaml) : l'audit complet du CSV
a montre que les colonnes initialement suspectees d'etre SOURCE_CUSTOMER
(positions 16-17) sont en realite des references de traitement/
rapprochement a tres faible cardinalite (2095 et 348 valeurs pour 1,6M
lignes), pas des identifiants client. AUCUNE colonne fiable d'identifiant
client independant du telephone n'a ete confirmee a ce jour. Consequence
directe : customer_id = SOURCE_PHONE (ou DESTINATION_PHONE cote
beneficiaire). Ca veut dire que la detection "un meme telephone partage
entre plusieurs comptes clients" (mentionnee dans le cahier des charges)
NE PEUT PAS etre verifiee tant qu'un identifiant client independant du
telephone n'est pas confirme -- si un tel identifiant est trouve/confirme
plus tard, ce module devra etre revu.

Ce que ce module fait concretement en attendant :
- construit customer_id = telephone (normalise)
- construit une table d'activite par telephone (premiere/derniere
  transaction vue, nombre d'operations en tant qu'emetteur/beneficiaire) --
  alimente directement les features d'anciennete (volet C) et de vitesse

Usage :
    python -m bamis_fraud.preprocessing.customer_resolution --input data/processed/transactions_clean.parquet
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd


def build_customer_id(df: pd.DataFrame) -> pd.DataFrame:
    """customer_id = SOURCE_PHONE pour l'emetteur. Voir note en tete de
    module : c'est un choix pragmatique faute de mieux, pas une certitude."""
    df = df.copy()
    df["source_customer_id"] = df["SOURCE_PHONE"]
    df["destination_customer_id"] = df["DESTINATION_PHONE"].replace("", pd.NA)
    return df


def build_phone_activity_table(df: pd.DataFrame) -> pd.DataFrame:
    """Une ligne par telephone (source OU destination), avec la fenetre
    d'activite observee et le volume de part et d'autre. Alimente
    l'anciennete (volet C) et les features reseau legeres (5.4)."""
    as_source = (
        df.groupby("SOURCE_PHONE", observed=True)
        .agg(
            first_seen_as_source=("TRANSACTION_DATE", "min"),
            last_seen_as_source=("TRANSACTION_DATE", "max"),
            n_as_source=("TRANSACTION_CODE", "count"),
            amount_sent_total=("TRANSACTION_AMOUNT", "sum"),
        )
        .reset_index()
        .rename(columns={"SOURCE_PHONE": "phone"})
    )

    dest_df = df[df["DESTINATION_PHONE"] != ""]
    as_dest = (
        dest_df.groupby("DESTINATION_PHONE", observed=True)
        .agg(
            first_seen_as_destination=("TRANSACTION_DATE", "min"),
            last_seen_as_destination=("TRANSACTION_DATE", "max"),
            n_as_destination=("TRANSACTION_CODE", "count"),
            amount_received_total=("TRANSACTION_AMOUNT", "sum"),
        )
        .reset_index()
        .rename(columns={"DESTINATION_PHONE": "phone"})
    )

    activity = as_source.merge(as_dest, on="phone", how="outer")
    for col in ["n_as_source", "n_as_destination"]:
        activity[col] = activity[col].fillna(0).astype("int64")
    for col in ["amount_sent_total", "amount_received_total"]:
        activity[col] = activity[col].fillna(0.0)

    activity["first_seen"] = activity[["first_seen_as_source", "first_seen_as_destination"]].min(axis=1)
    activity["last_seen"] = activity[["last_seen_as_source", "last_seen_as_destination"]].max(axis=1)
    activity["tenure_days"] = (activity["last_seen"] - activity["first_seen"]).dt.days

    # ratio recu/envoye -- premiere approximation d'un signal de compte
    # mule (5.4), affinee plus tard par le vrai module graphe
    total_flow = activity["amount_sent_total"] + activity["amount_received_total"]
    activity["received_to_sent_ratio"] = activity["amount_received_total"] / activity[
        "amount_sent_total"
    ].replace(0, pd.NA)

    return activity


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", default="data/processed/customer_phone_map.parquet")
    args = parser.parse_args()

    df = pd.read_parquet(args.input)
    activity = build_phone_activity_table(df)

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    activity.to_parquet(out_path, index=False)

    print(f"{len(activity):,} telephones distincts observes (source et/ou destination)")
    print(f"Anciennete mediane : {activity['tenure_days'].median():.0f} jours")
    print(f"Ecrit dans {out_path}")


if __name__ == "__main__":
    main()
