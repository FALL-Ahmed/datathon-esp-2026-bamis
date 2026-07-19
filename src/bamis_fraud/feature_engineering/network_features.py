"""
Features relationnelles calculables SANS graphe complet (approximations
rapides, niveau 1-2 de la strategie du cahier des charges), en complement
du module graph/ (niveau 3, bonus, vraie construction de graphe pour les
chaines/circuits).

FEATURES PRODUITES (toutes causales -- strictement anterieures a la
transaction courante, anti-leakage)
-------------------------------------------------------------------------
- montant_cumule_envoye_past : total envoye par ce client avant cette transaction
- montant_cumule_recu_past : total recu par ce telephone avant cette transaction
  (le telephone source d'une transaction peut aussi avoir ete destinataire
  d'autres transactions ailleurs dans le fichier -- c'est ce qu'on cherche)
- ratio_montant_recu_envoye_past : signal mule (C-02), proche de 1 = suspect
- delai_depuis_derniere_reception_minutes : temps ecoule depuis la derniere
  reception d'argent sur ce telephone -- court + ratio proche de 1 = pass-through
- nb_expediteurs_distincts_past : combien de telephones differents lui ont
  deja envoye de l'argent avant cette transaction (fan-in, C-03)
- nb_destinataires_distincts_past : combien de telephones differents il a
  deja envoye de l'argent avant cette transaction (fan-out, C-04)
- is_external_gimtel : reporte tel quel depuis preprocessing/cleaning.py

APPROXIMATION ASSUMEE (a documenter dans la note methodologique) :
delai_depuis_derniere_reception_minutes utilise la DERNIERE reception, pas
un appariement precis montant-recu / montant-renvoye. C'est une
approximation volontaire pour rester rapide a calculer sur 1,6M lignes ; le
vrai appariement fin (quelle reception precise correspond a quel renvoi)
est delegue a graph/mule_detection.py (niveau 3).

CE QUI N'EST PAS FAIT ICI : phone_shared_with_n_accounts (telephone
partage entre PLUSIEURS comptes clients differents) ne peut pas etre
calcule tant qu'aucun identifiant client independant du telephone n'est
confirme -- voir preprocessing/customer_resolution.py, meme limite.

Usage :
    python -m bamis_fraud.feature_engineering.network_features --input data/processed/transactions_clean.parquet
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd


def add_network_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values(["source_customer_id", "TRANSACTION_DATE"]).reset_index(drop=True)

    # --- cote EMETTEUR : montant envoye cumule + destinataires distincts, causal ---
    sent_cumsum_incl = df.groupby("source_customer_id")["TRANSACTION_AMOUNT"].cumsum()
    df["montant_cumule_envoye_past"] = sent_cumsum_incl - df["TRANSACTION_AMOUNT"]

    def _mark_new_destination(group: pd.DataFrame) -> pd.Series:
        seen: set[str] = set()
        flags = []
        for val in group["DESTINATION_PHONE"]:
            flags.append(val != "" and val not in seen)
            if val != "":
                seen.add(val)
        return pd.Series(flags, index=group.index)

    is_new_dest = df.groupby("source_customer_id", group_keys=False)[["DESTINATION_PHONE"]].apply(
        _mark_new_destination
    )
    dest_running_incl = df.groupby("source_customer_id", group_keys=False).apply(
        lambda g: is_new_dest.loc[g.index].cumsum()
    ).reset_index(level=0, drop=True)
    df["nb_destinataires_distincts_past"] = (dest_running_incl - is_new_dest.astype(int)).astype("int64")

    # --- cote RECEPTEUR : construit depuis le point de vue du telephone
    # destinataire de CHAQUE transaction (une transaction = un evenement de
    # reception pour DESTINATION_PHONE), puis rattache par merge_asof au
    # telephone SOURCE de chaque transaction (est-ce que ce telephone a,
    # par le passe, deja ete destinataire d'argent ailleurs ?) ---
    received = df.loc[df["DESTINATION_PHONE"] != "", ["DESTINATION_PHONE", "TRANSACTION_DATE", "TRANSACTION_AMOUNT", "SOURCE_PHONE"]].copy()
    received = received.rename(columns={"DESTINATION_PHONE": "phone"})
    received = received.sort_values(["phone", "TRANSACTION_DATE"])

    def _mark_new_sender(group: pd.DataFrame) -> pd.Series:
        seen: set[str] = set()
        flags = []
        for val in group["SOURCE_PHONE"]:
            flags.append(val != "" and val not in seen)
            if val != "":
                seen.add(val)
        return pd.Series(flags, index=group.index)

    is_new_sender = received.groupby("phone", group_keys=False)[["SOURCE_PHONE"]].apply(_mark_new_sender)
    received["nb_expediteurs_distincts_incl"] = (
        received.groupby("phone", group_keys=False)
        .apply(lambda g: is_new_sender.loc[g.index].cumsum())
        .reset_index(level=0, drop=True)
    )
    received["montant_cumule_recu_incl"] = received.groupby("phone")["TRANSACTION_AMOUNT"].cumsum()
    received["received_at"] = received["TRANSACTION_DATE"]

    received_for_merge = received[
        ["phone", "TRANSACTION_DATE", "montant_cumule_recu_incl", "nb_expediteurs_distincts_incl", "received_at"]
    ].sort_values("TRANSACTION_DATE")

    df_sorted = df.sort_values("TRANSACTION_DATE")
    merged = pd.merge_asof(
        df_sorted,
        received_for_merge,
        on="TRANSACTION_DATE",
        left_by="SOURCE_PHONE",
        right_by="phone",
        direction="backward",
        allow_exact_matches=False,
    )

    merged["montant_cumule_recu_past"] = merged["montant_cumule_recu_incl"].fillna(0.0)
    merged["nb_expediteurs_distincts_past"] = merged["nb_expediteurs_distincts_incl"].fillna(0).astype("int64")
    merged["delai_depuis_derniere_reception_minutes"] = (
        merged["TRANSACTION_DATE"] - merged["received_at"]
    ).dt.total_seconds() / 60

    merged["ratio_montant_recu_envoye_past"] = merged["montant_cumule_recu_past"] / merged[
        "montant_cumule_envoye_past"
    ].replace(0, pd.NA)

    merged = merged.drop(columns=["montant_cumule_recu_incl", "nb_expediteurs_distincts_incl", "phone", "received_at"])
    return merged


def main() -> None:
    import argparse
    import time

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", default="data/features/network_features_light.parquet")
    args = parser.parse_args()

    df = pd.read_parquet(args.input)
    t0 = time.time()
    df = add_network_features(df)
    print(f"Features reseau calculees en {time.time() - t0:.1f}s")

    keep_cols = [
        "TRANSACTION_CODE",
        "source_customer_id",
        "TRANSACTION_DATE",
        "montant_cumule_envoye_past",
        "montant_cumule_recu_past",
        "ratio_montant_recu_envoye_past",
        "delai_depuis_derniere_reception_minutes",
        "nb_expediteurs_distincts_past",
        "nb_destinataires_distincts_past",
        "is_external_gimtel",
    ]
    out_df = df[keep_cols]

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_parquet(out_path, index=False)

    print(f"{len(out_df):,} lignes ecrites dans {out_path}")
    mule_like = (
        (out_df["ratio_montant_recu_envoye_past"].between(0.8, 1.2))
        & (out_df["delai_depuis_derniere_reception_minutes"].between(0, 30))
    )
    print(f"Transactions au profil 'pass-through rapide' (signal mule C-02, approx.) : "
          f"{int(mule_like.sum()):,} ({mule_like.mean():.3%})")
    print(f"nb_expediteurs_distincts_past : max={out_df['nb_expediteurs_distincts_past'].max()}, "
          f"p99={out_df['nb_expediteurs_distincts_past'].quantile(0.99):.1f}")


if __name__ == "__main__":
    main()
