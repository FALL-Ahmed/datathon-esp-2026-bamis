"""
BONUS volet B : propose un seuil personnalise (majore/reduit) en fonction
de la classe de risque du client -- lien explicite demande par le cahier des
charges entre volet C et volet B ("proposez un seuil plus haut ou plus bas
selon la classe de risque du client (lien avec le volet C)"). Ne modifie
jamais le fichier seuils_services.csv source -- produit une recommandation
separee que BAMIS peut valider manuellement.

Le multiplicateur applique depend de l'action_recommandee deja calculee par
scoring/treatment_matrix.py, qui croise segment_valeur x segment_risque
selon la matrice exacte du cahier des charges -- ce module ne reinvente pas
un second croisement, il traduit l'action textuelle deja decidee en un
seuil chiffre. Les multiplicateurs eux-memes sont lus depuis
configs/config.yaml -> budget.threshold_multipliers, jamais codes en dur :
ce sont des hypotheses commerciales (pas des valeurs officielles BAMIS),
documentees comme telles dans la justification generee pour chaque ligne.

On ne recommande un seuil que pour les couples (client, service) reellement
observes dans data/features/budget_consumption.parquet -- pas de produit
cartesien client x tous les services, qui recommanderait un seuil pour des
services que le client n'a jamais utilises.

Usage :
    python -m bamis_fraud.budget.threshold_recommender

Sortie :
    outputs/reports/recommandations_seuils.csv (client_id, service_code,
    seuil_unitaire_actuel, seuil_unitaire_recommande,
    seuil_cumul_journalier_actuel, seuil_cumul_journalier_recommande,
    segment_valeur, segment_risque, action_recommandee, justification)
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import yaml


def load_config(path: str | Path = "configs/config.yaml") -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def recommend_threshold(base_threshold: float, action_recommandee: str, multipliers: dict) -> float:
    """Un seul point de calcul du seuil recommande, reutilise pour le seuil
    unitaire et le seuil de cumul journalier -- la logique de multiplicateur
    ne doit exister qu'une fois."""
    if pd.isna(base_threshold):
        return base_threshold
    multiplier = multipliers.get(action_recommandee, 1.0)
    return round(float(base_threshold) * multiplier, 0)


def _justification(segment_valeur: str, segment_risque: str, action: str, multiplier: float) -> str:
    if multiplier == 1.0:
        effet = "seuil inchangé (x1.0)"
    elif multiplier == 0.0:
        effet = "seuil ramené à 0 : compte gelé, toute opération doit être validée manuellement"
    elif multiplier > 1.0:
        effet = f"seuil multiplié par {multiplier} : moins de friction pour un bon client à faible risque"
    else:
        effet = f"seuil multiplié par {multiplier} : plus de friction pour limiter l'exposition"
    return f"Client segment {segment_valeur} / risque {segment_risque} → action « {action} » → {effet}."


def build_threshold_recommendations(
    scores: pd.DataFrame,
    client_services: pd.DataFrame,
    thresholds: pd.DataFrame,
    multipliers: dict,
) -> pd.DataFrame:
    """
    scores : data/features/customer_risk_value_scores.parquet -- segment_valeur,
        segment_risque, action_recommandee deja calcules par le volet C
        (scoring/customer_scoring.py + scoring/treatment_matrix.py).
    client_services : couples (source_customer_id, SERVICE_CODE) reellement
        observes (issus de data/features/budget_consumption.parquet).
    thresholds : configs/thresholds/seuils_services.csv -- seuils officiels
        actuels, jamais modifies ici.
    """
    base = client_services.merge(
        thresholds[["SERVICE_CODE", "SEUIL_VIGILANCE_UNITAIRE_MRU", "SEUIL_CUMUL_JOURNALIER_MRU"]],
        on="SERVICE_CODE",
        how="left",
    ).merge(
        scores[["source_customer_id", "segment_valeur", "segment_risque", "action_recommandee"]],
        on="source_customer_id",
        how="left",
    )

    base["seuil_unitaire_recommande"] = [
        recommend_threshold(u, a, multipliers)
        for u, a in zip(base["SEUIL_VIGILANCE_UNITAIRE_MRU"], base["action_recommandee"])
    ]
    base["seuil_cumul_journalier_recommande"] = [
        recommend_threshold(c, a, multipliers)
        for c, a in zip(base["SEUIL_CUMUL_JOURNALIER_MRU"], base["action_recommandee"])
    ]
    base["justification"] = [
        _justification(v, r, a, multipliers.get(a, 1.0))
        for v, r, a in zip(base["segment_valeur"], base["segment_risque"], base["action_recommandee"])
    ]

    out = base.rename(
        columns={
            "source_customer_id": "client_id",
            "SERVICE_CODE": "service_code",
            "SEUIL_VIGILANCE_UNITAIRE_MRU": "seuil_unitaire_actuel",
            "SEUIL_CUMUL_JOURNALIER_MRU": "seuil_cumul_journalier_actuel",
        }
    )[
        [
            "client_id",
            "service_code",
            "seuil_unitaire_actuel",
            "seuil_unitaire_recommande",
            "seuil_cumul_journalier_actuel",
            "seuil_cumul_journalier_recommande",
            "segment_valeur",
            "segment_risque",
            "action_recommandee",
            "justification",
        ]
    ]
    return out


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scores", default="data/features/customer_risk_value_scores.parquet")
    parser.add_argument("--budget-consumption", default="data/features/budget_consumption.parquet")
    parser.add_argument("--thresholds", default="configs/thresholds/seuils_services.csv")
    parser.add_argument("--config", default="configs/config.yaml")
    parser.add_argument("--output", default="outputs/reports/recommandations_seuils.csv")
    args = parser.parse_args()

    cfg = load_config(args.config)
    multipliers = cfg.get("budget", {}).get("threshold_multipliers", {})

    scores = pd.read_parquet(args.scores)
    budget_consumption = pd.read_parquet(args.budget_consumption)
    client_services = budget_consumption[["source_customer_id", "SERVICE_CODE"]].drop_duplicates()

    thresholds = pd.read_csv(args.thresholds)
    thresholds["SERVICE_CODE"] = thresholds["SERVICE_CODE"].astype(str).str.strip().str.upper()

    out = build_threshold_recommendations(scores, client_services, thresholds, multipliers)

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(out_path, index=False)

    print(f"{len(out):,} recommandations (client x service) ecrites dans {out_path}")
    print("\nRepartition des actions recommandees :")
    print(out["action_recommandee"].value_counts())
    print("\nExemple (premiere ligne) :")
    print(out.iloc[0].to_string())


if __name__ == "__main__":
    main()
