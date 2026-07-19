"""
Implemente le volet B : pour chaque client x service, cumule les montants
sur la journee et le mois, TOUS CANAUX CONFONDUS, pour empecher le
contournement C-08 ("le compteur ne repart pas de zero quand le client
change de canal"). Concretement : on ne groupe JAMAIS par canal dans les
cumuls ci-dessous -- la protection anti-C-08 vient de l'absence
deliberee de CHANNEL_TYPE dans les colonnes de regroupement, pas d'un
traitement special de cette colonne (qui reste d'ailleurs a confidence
basse dans configs/schema_map.yaml).

Seuls les montants des transactions VALIDATED comptent dans les cumuls --
une transaction rejetee ou incomplete n'a jamais fait bouger d'argent (voir
preprocessing/cleaning.py, colonne is_validated).

Les seuils sont TOUJOURS lus depuis configs/thresholds/seuils_services.csv,
jamais codes en dur -- le jury peut modifier ce fichier.

LIMITE ASSUMEE : le cahier des charges demande de comparer le cumul mensuel
a "un seuil du service", mais seuils_services.csv ne fournit qu'un seuil de
cumul JOURNALIER, pas de seuil mensuel explicite. En l'absence de cette
valeur officielle, un seuil mensuel est derive par
seuil_journalier x configs/config.yaml -> budget.monthly_multiplier (30 par
defaut). C'est une hypothese documentee, pas une valeur officielle -- a
remplacer immediatement si les organisateurs fournissent un vrai seuil
mensuel.

Usage :
    python -m bamis_fraud.budget.budget_engine --input data/processed/transactions_clean.parquet
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import yaml


def load_thresholds(path: str | Path) -> pd.DataFrame:
    thresholds = pd.read_csv(path)
    thresholds["SERVICE_CODE"] = thresholds["SERVICE_CODE"].astype(str).str.strip().str.upper()
    return thresholds


def load_monthly_multiplier(config_path: str | Path = "configs/config.yaml") -> float:
    path = Path(config_path)
    if not path.exists():
        return 30.0
    with open(path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    return float(cfg.get("budget", {}).get("monthly_multiplier", 30.0))


def compute_daily_consumption(df: pd.DataFrame, thresholds: pd.DataFrame) -> pd.DataFrame:
    validated = df[df["is_validated"]].copy()
    validated["periode_jour"] = validated["TRANSACTION_DATE"].dt.date

    daily = (
        validated.groupby(["source_customer_id", "SERVICE_CODE", "periode_jour"], observed=True)[
            "TRANSACTION_AMOUNT"
        ]
        .sum()
        .reset_index()
        .rename(columns={"TRANSACTION_AMOUNT": "montant_consomme_jour"})
    )
    daily = daily.merge(
        thresholds[["SERVICE_CODE", "SEUIL_CUMUL_JOURNALIER_MRU"]], on="SERVICE_CODE", how="left"
    )
    daily["taux_consommation_jour"] = (
        daily["montant_consomme_jour"] / daily["SEUIL_CUMUL_JOURNALIER_MRU"]
    )
    daily["montant_restant_jour"] = daily["SEUIL_CUMUL_JOURNALIER_MRU"] - daily["montant_consomme_jour"]
    return daily


def compute_monthly_consumption(
    df: pd.DataFrame, thresholds: pd.DataFrame, monthly_multiplier: float
) -> pd.DataFrame:
    validated = df[df["is_validated"]].copy()
    validated["periode_mois"] = validated["TRANSACTION_DATE"].dt.to_period("M").astype(str)

    monthly = (
        validated.groupby(["source_customer_id", "SERVICE_CODE", "periode_mois"], observed=True)[
            "TRANSACTION_AMOUNT"
        ]
        .sum()
        .reset_index()
        .rename(columns={"TRANSACTION_AMOUNT": "montant_consomme_mois"})
    )
    monthly = monthly.merge(
        thresholds[["SERVICE_CODE", "SEUIL_CUMUL_JOURNALIER_MRU"]], on="SERVICE_CODE", how="left"
    )
    monthly["seuil_cumul_mensuel_estime"] = monthly["SEUIL_CUMUL_JOURNALIER_MRU"] * monthly_multiplier
    monthly["taux_consommation_mois"] = (
        monthly["montant_consomme_mois"] / monthly["seuil_cumul_mensuel_estime"]
    )
    monthly["montant_restant_mois"] = (
        monthly["seuil_cumul_mensuel_estime"] - monthly["montant_consomme_mois"]
    )
    monthly = monthly.drop(columns=["SEUIL_CUMUL_JOURNALIER_MRU"])
    return monthly


def build_budget_consumption(
    df: pd.DataFrame, thresholds_path: str | Path, config_path: str | Path
) -> pd.DataFrame:
    thresholds = load_thresholds(thresholds_path)
    monthly_multiplier = load_monthly_multiplier(config_path)

    daily = compute_daily_consumption(df, thresholds)
    monthly = compute_monthly_consumption(df, thresholds, monthly_multiplier)

    # rattache a chaque ligne journaliere le cumul mensuel correspondant
    daily["periode_mois"] = pd.to_datetime(daily["periode_jour"]).dt.to_period("M").astype(str)
    merged = daily.merge(
        monthly,
        on=["source_customer_id", "SERVICE_CODE", "periode_mois"],
        how="left",
    )
    return merged


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default="data/processed/transactions_clean.parquet")
    parser.add_argument("--thresholds", default="configs/thresholds/seuils_services.csv")
    parser.add_argument("--config", default="configs/config.yaml")
    parser.add_argument("--output", default="data/features/budget_consumption.parquet")
    args = parser.parse_args()

    df = pd.read_parquet(args.input)
    out = build_budget_consumption(df, args.thresholds, args.config)

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(out_path, index=False)

    print(f"{len(out):,} lignes (client x service x jour) ecrites dans {out_path}")
    print(f"Clients-service-jours au-dessus du seuil journalier : "
          f"{(out['taux_consommation_jour'] > 1).sum():,} ({(out['taux_consommation_jour'] > 1).mean():.3%})")
    print(f"Clients-service-jours au-dessus du seuil mensuel (estime) : "
          f"{(out['taux_consommation_mois'] > 1).sum():,} ({(out['taux_consommation_mois'] > 1).mean():.3%})")


if __name__ == "__main__":
    main()
