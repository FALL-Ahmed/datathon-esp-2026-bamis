"""
Niveau 1 de la strategie en 3 niveaux recommandee par le cahier des
charges : regles metier explicites, simples, 100% interpretables.

ROLE DOUBLE, DECISION DU 2026-07-19 : ce module n'est plus seulement une
baseline de comparaison. Le cahier des charges garde la verite terrain pour
lui ("le jury comparera vos notes a la verite qu'il garde de cote") --
aucun fichier de labels ne sera fourni, ni pour le train ni pour le test
(voir configs/schema_map.yaml -> decision_2026_07_19_pas_de_labels_a_attendre
et ARCHITECTURE.md section 0). Consequence : la sortie de ce module sert de
PSEUDO-LABEL D'ENTRAINEMENT pour modeling/train.py (niveau 2), en plus de
rester une feature d'entree du modele et un filet de securite explicable.

Regles volontairement SIMPLES (c'est le principe du niveau 1) -- les cas
limites (ex. un agent legitime a haut volume) ne sont PAS traites finement
ici, c'est le role du modele ML (niveau 2) d'apprendre les nuances a partir
de ces exemples grossiers. Tous les seuils sont dans configs/config.yaml,
jamais codes en dur.

REGLES IMPLEMENTEES
---------------------
- R1 : montant > seuil_vigilance_unitaire du service (deja calcule dans
  threshold_features.is_above_unit_threshold)
- R2 : cumul_jour > seuil_cumul_journalier (deja calcule dans
  threshold_features.daily_cumulative_ratio > 1)
- R3 : montant proche du seuil (80-100%) ET plusieurs operations sur 24h
  -> fractionnement suspect (C-01)
- R4 : rafale absolue sur 1h au-dessus d'un seuil configurable (C-07) --
  regle volontairement simple, va flaguer des agents legitimes a ce stade,
  c'est attendu et documente
- R5 : nouveau beneficiaire + montant superieur au maximum historique du
  client -> F-03
- R6 : operation nocturne (heure configurable) + montant tres eloigne de
  l'habitude du client (zscore eleve) -> F-01
- R7 : profil "reception puis reexpedition rapide" (ratio recu/envoye
  proche de 1, delai court) -> approximation mule C-02

SORTIES
-------
- data/features/rule_flags.parquet : un flag booleen par regle (feature
  d'entree du modele ML) + rule_suspicion_score (nombre de regles
  declenchees, 0 a 7) + pseudo_label_fraud (bool, rule_suspicion_score >=
  seuil configurable). NE JAMAIS reentrainer le modele avec le meme flag
  individuel a la fois en feature ET comme le SEUL ingredient du label --
  le pseudo-label agrege plusieurs regles justement pour ne pas etre une
  simple recopie d'une colonne d'entree.

NOTE : ce module fait un merge ad-hoc des 4 fichiers de features existants
(threshold, behavioral, velocity, network) + transactions_clean, en
attendant que feature_engineering/feature_store.py (pas encore implemente)
fasse cet assemblage proprement pour tout le pipeline.

Usage :
    python -m bamis_fraud.rules.business_rules --transactions data/processed/transactions_clean.parquet
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import yaml


DEFAULT_RULES_CONFIG = {
    "fractionnement_min_ops_24h": 3,
    "fractionnement_ratio_band": [0.8, 1.0],
    "rafale_max_transactions_1h": 15,
    "nouveau_beneficiaire_ratio_max_habituel": 1.0,  # montant > max historique
    "nuit_heure_debut": 22,
    "nuit_heure_fin": 6,
    "nuit_zscore_min": 3.0,
    "mule_ratio_band": [0.8, 1.2],
    "mule_delai_max_minutes": 30,
    "pseudo_label_min_rules_triggered": 2,
}


def load_rules_config(config_path: str | Path = "configs/config.yaml") -> dict:
    path = Path(config_path)
    if not path.exists():
        return DEFAULT_RULES_CONFIG
    with open(path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    rules_cfg = dict(DEFAULT_RULES_CONFIG)
    rules_cfg.update(cfg.get("business_rules", {}))
    return rules_cfg


def load_and_merge_features(
    transactions_path: str | Path,
    threshold_path: str = "data/features/threshold_features.parquet",
    behavioral_path: str = "data/features/behavioral_features.parquet",
    velocity_path: str = "data/features/velocity_features.parquet",
    network_path: str = "data/features/network_features_light.parquet",
) -> pd.DataFrame:
    tx = pd.read_parquet(transactions_path)[
        ["TRANSACTION_CODE", "TRANSACTION_DATE", "SERVICE_CODE", "TRANSACTION_AMOUNT"]
    ]
    threshold = pd.read_parquet(threshold_path).drop(
        columns=["source_customer_id", "SERVICE_CODE", "TRANSACTION_DATE", "TRANSACTION_AMOUNT"]
    )
    behavioral = pd.read_parquet(behavioral_path).drop(
        columns=["source_customer_id", "TRANSACTION_DATE"]
    )
    velocity = pd.read_parquet(velocity_path).drop(columns=["source_customer_id", "TRANSACTION_DATE"])
    network = pd.read_parquet(network_path).drop(columns=["source_customer_id", "TRANSACTION_DATE"])

    df = tx.merge(threshold, on="TRANSACTION_CODE", how="left")
    df = df.merge(behavioral, on="TRANSACTION_CODE", how="left")
    df = df.merge(velocity, on="TRANSACTION_CODE", how="left")
    df = df.merge(network, on="TRANSACTION_CODE", how="left")
    return df


def apply_business_rules(df: pd.DataFrame, rules_cfg: dict) -> pd.DataFrame:
    df = df.copy()

    # R1 / R2 : deja calcules dans threshold_features
    df["rule_R1_above_unit_threshold"] = df["is_above_unit_threshold"].fillna(False)
    df["rule_R2_above_daily_cumulative"] = (df["daily_cumulative_ratio"] > 1.0).fillna(False)

    # R3 : fractionnement -- proche du seuil + plusieurs operations sur 24h
    lo, hi = rules_cfg["fractionnement_ratio_band"]
    near_threshold = df["amount_to_service_threshold_ratio"].between(lo, hi)
    many_ops = df["nb_transactions_24h"] >= rules_cfg["fractionnement_min_ops_24h"]
    df["rule_R3_fractionnement"] = (near_threshold & many_ops).fillna(False)

    # R4 : rafale absolue
    df["rule_R4_rafale"] = (df["nb_transactions_1h"] > rules_cfg["rafale_max_transactions_1h"]).fillna(False)

    # R5 : nouveau beneficiaire + montant record pour ce client (utilise le
    # ratio deja calcule par behavioral_features.py : amount / max_historique)
    is_record = df["amount_to_customer_habitual_max_ratio"] > rules_cfg[
        "nouveau_beneficiaire_ratio_max_habituel"
    ]
    df["rule_R5_nouveau_beneficiaire_gros_montant"] = (
        df["is_new_beneficiary"].fillna(False) & is_record.fillna(False)
    )

    # R6 : nuit + montant hors norme
    # La fenetre nuit peut soit traverser minuit (ex. 22h->6h, debut > fin)
    # soit non (ex. 0h->7h, debut < fin) -- les deux cas doivent etre geres,
    # sinon une fenetre non-traversante comme 0h->7h rend la condition OR
    # toujours vraie (hour >= 0 est toujours vrai).
    hour = df["TRANSACTION_DATE"].dt.hour
    debut, fin = rules_cfg["nuit_heure_debut"], rules_cfg["nuit_heure_fin"]
    if debut <= fin:
        is_night = (hour >= debut) & (hour < fin)
    else:
        is_night = (hour >= debut) | (hour < fin)
    is_outlier = df["zscore_vs_customer_history"].abs() > rules_cfg["nuit_zscore_min"]
    df["rule_R6_nocturne_hors_norme"] = (is_night & is_outlier.fillna(False))

    # R7 : profil mule (reception rapide puis reexpedition)
    mlo, mhi = rules_cfg["mule_ratio_band"]
    ratio_ok = df["ratio_montant_recu_envoye_past"].between(mlo, mhi)
    delai_ok = df["delai_depuis_derniere_reception_minutes"].between(0, rules_cfg["mule_delai_max_minutes"])
    df["rule_R7_profil_mule"] = (ratio_ok.fillna(False) & delai_ok.fillna(False))

    rule_cols = [c for c in df.columns if c.startswith("rule_R")]
    df["rule_suspicion_score"] = df[rule_cols].sum(axis=1)
    df["pseudo_label_fraud"] = df["rule_suspicion_score"] >= rules_cfg["pseudo_label_min_rules_triggered"]

    return df


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--transactions", default="data/processed/transactions_clean.parquet")
    parser.add_argument("--config", default="configs/config.yaml")
    parser.add_argument("--output", default="data/features/rule_flags.parquet")
    args = parser.parse_args()

    rules_cfg = load_rules_config(args.config)
    df = load_and_merge_features(args.transactions)
    df = apply_business_rules(df, rules_cfg)

    keep_cols = ["TRANSACTION_CODE"] + [c for c in df.columns if c.startswith("rule_R")] + [
        "rule_suspicion_score",
        "pseudo_label_fraud",
    ]
    out_df = df[keep_cols]

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_parquet(out_path, index=False)

    print(f"{len(out_df):,} lignes ecrites dans {out_path}")
    for col in [c for c in out_df.columns if c.startswith("rule_R")]:
        print(f"  {col} : {out_df[col].sum():,} ({out_df[col].mean():.3%})")
    print(f"\npseudo_label_fraud (>= {rules_cfg['pseudo_label_min_rules_triggered']} regles declenchees) : "
          f"{int(out_df['pseudo_label_fraud'].sum()):,} ({out_df['pseudo_label_fraud'].mean():.3%})")
    print("\nDistribution du score de suspicion :")
    print(out_df["rule_suspicion_score"].value_counts().sort_index())


if __name__ == "__main__":
    main()
