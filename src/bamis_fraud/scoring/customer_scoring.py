"""
Implemente le volet C : deux notes independantes par client, 0 a 1000.

SCORE DE RISQUE (poids exacts du cahier des charges, lus depuis
configs/config.yaml -> risk_score_weights, jamais codes en dur)
------------------------------------------------------------------
- Comportement anormal (300 pts) : ecart a l'historique propre (zscore),
  part de rafales (R4), part d'activite nocturne hors norme (R6)
- Contournement (250 pts) : part pres du seuil, fractionnement (R3),
  depassement de seuil (R1/R2), sorties GIMTEL
- Role dans un reseau (200 pts) : degre entrant/sortant (fan-in/fan-out),
  part de profil "mule" (R7) -- PAS "telephone partage entre comptes"
  (impossible a calculer sans identifiant client independant du telephone,
  voir preprocessing/customer_resolution.py)
- Historique d'alertes (150 pts) : nb alertes totales/recentes, niveau max
  (budget/alert_engine.py)
- Profil (100 pts) : anciennete SEULEMENT -- PAS de KYC (colonne absente du
  fichier source), limite documentee explicitement

SCORE DE VALEUR
-----------------
- Volume (300 pts) : montant total envoye
- Rentabilite (250 pts) : frais totaux generes (TRANSACTION_FEES)
- Regularite (200 pts) : part de jours actifs sur la duree de la relation
- Diversite (150 pts) : nombre de services distincts utilises -- PAS de
  diversite de canal (CHANNEL_TYPE a confidence basse, voir schema_map.yaml)
- Anciennete (100 pts) : duree de la relation

METHODE DE NORMALISATION : deux methodes selon la nature de l'indicateur
(choix verifie empiriquement le 2026-07-19, voir _normalize_minmax et
_normalize_rank plus bas pour le detail et la justification) -- min-max
borne pour les indicateurs concentres a zero (parts de regles, alertes),
rang percentile pour les indicateurs continus et etales (montants,
anciennete). A l'interieur de chaque sous-critere combinant plusieurs
indicateurs de risque, on retient le MAXIMUM (pas la moyenne) : un client
extreme sur un seul indicateur fort ne doit pas etre dilue par ses autres
indicateurs normaux.

SEGMENTATION (lue depuis configs/config.yaml, pas en dur)
------------------------------------------------------------
Valeur : Platine >=800, Or 600-799, Argent 400-599, Bronze <400
Risque : Faible <250, Modere 250-499, Eleve 500-749, Critique >=750

Usage :
    python -m bamis_fraud.scoring.customer_scoring
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import yaml


def load_config(config_path: str | Path = "configs/config.yaml") -> dict:
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def aggregate_customer_metrics(
    transactions_path: str = "data/processed/transactions_clean.parquet",
    threshold_path: str = "data/features/threshold_features.parquet",
    behavioral_path: str = "data/features/behavioral_features.parquet",
    network_path: str = "data/features/network_features_light.parquet",
    rule_flags_path: str = "data/features/rule_flags.parquet",
    alert_history_path: str = "data/features/customer_alert_history.parquet",
    phone_map_path: str = "data/processed/customer_phone_map.parquet",
) -> pd.DataFrame:
    """Assemble une table avec UNE LIGNE PAR CLIENT, agregeant toutes les
    metriques brutes necessaires au calcul des scores. Chaque metrique est
    encore une valeur brute (montant, taux, compteur) -- la conversion en
    points se fait dans compute_risk_score/compute_value_score.

    DECISION 2026-07-20 : la population couverte est desormais TOUS les
    comptes vus dans les donnees (175 689 -- source OU destination), pas
    seulement les 40 866 comptes ayant emis au moins une transaction. Un
    compte qui ne fait que RECEVOIR de l'argent de nombreux expediteurs
    differents est exactement le profil "collecteur" (C-03, fan-in) que le
    cahier des charges demande de detecter -- l'exclure entierement du
    classement client etait un angle mort, pas un choix delibere. Les
    metriques cote "emission" (comportement anormal, contournement, regles
    R1-R7) restent structurellement a 0 pour ces comptes, faute de
    transaction emise a analyser -- c'est correct, pas un bug : aucune
    preuve de comportement suspect en emission ne peut exister pour un
    compte qui n'emet jamais."""
    tx = pd.read_parquet(
        transactions_path,
        columns=["TRANSACTION_CODE", "source_customer_id", "destination_customer_id", "SERVICE_CODE",
                  "TRANSACTION_DATE", "TRANSACTION_AMOUNT", "TRANSACTION_FEES", "is_external_gimtel"],
    )

    # --- volume, rentabilite, diversite, activite EN EMISSION (inchange) ---
    tx["day"] = tx["TRANSACTION_DATE"].dt.date
    base = tx.groupby("source_customer_id", observed=True).agg(
        volume_total=("TRANSACTION_AMOUNT", "sum"),
        frais_totaux=("TRANSACTION_FEES", "sum"),
        nb_services_distincts=("SERVICE_CODE", "nunique"),
        nb_jours_actifs=("day", "nunique"),
        part_gimtel=("is_external_gimtel", "mean"),
        nb_transactions_total=("TRANSACTION_CODE", "count"),
    ).reset_index()

    # --- fan-out verifie (nb de destinataires distincts, calcul direct) ---
    # remplace max_destinataires_distincts (network_features_light, BOGUE
    # confirme le 2026-07-20, voir plus bas)
    sent_tx = tx[tx["destination_customer_id"] != ""]
    fanout = sent_tx.groupby("source_customer_id", observed=True).agg(
        nb_destinataires_distincts_envoyes=("destination_customer_id", "nunique"),
    ).reset_index()
    base = base.merge(fanout, on="source_customer_id", how="left")
    base["nb_destinataires_distincts_envoyes"] = base["nb_destinataires_distincts_envoyes"].fillna(0)

    # --- signal de reception (nouveau) : volume recu + fan-in (nb
    # d'expediteurs distincts) -- calcule directement depuis les
    # transactions, car les tables de features existantes (threshold/
    # behavioral/network/rules) sont toutes indexees par transaction EMISE,
    # donc structurellement vides pour un compte qui ne fait que recevoir ---
    received_tx = tx[tx["destination_customer_id"] != ""]
    received = received_tx.groupby("destination_customer_id", observed=True).agg(
        volume_recu=("TRANSACTION_AMOUNT", "sum"),
        nb_expediteurs_distincts_recus=("source_customer_id", "nunique"),
    ).reset_index().rename(columns={"destination_customer_id": "source_customer_id"})

    # --- univers complet des comptes (source OU destination, 175 689) ---
    phone_map_full = pd.read_parquet(
        phone_map_path, columns=["phone", "tenure_days"]
    ).rename(columns={"phone": "source_customer_id"})
    base = phone_map_full.merge(base, on="source_customer_id", how="left")
    base = base.merge(received, on="source_customer_id", how="left")
    base["nb_expediteurs_distincts_recus"] = base["nb_expediteurs_distincts_recus"].fillna(0)
    base["volume_recu"] = base["volume_recu"].fillna(0.0)
    for col in ["volume_total", "frais_totaux", "nb_services_distincts", "nb_jours_actifs",
                "part_gimtel", "nb_transactions_total"]:
        base[col] = base[col].fillna(0)
    # volume total CIRCULE (emis + recu) -- alignement sur la formulation du
    # cahier des charges ("montant total qu'il fait circule"), et seule
    # facon de donner une note de valeur non-nulle a un compte collecteur
    base["volume_total_circule"] = base["volume_total"] + base["volume_recu"]

    # --- comportement (behavioral_features, jointe via TRANSACTION_CODE) ---
    behavioral = pd.read_parquet(
        behavioral_path, columns=["TRANSACTION_CODE", "source_customer_id", "zscore_vs_customer_history"]
    )
    behav_agg = behavioral.groupby("source_customer_id", observed=True).agg(
        zscore_moyen_abs=("zscore_vs_customer_history", lambda s: s.abs().mean()),
    ).reset_index()

    # --- contournement (threshold_features) ---
    threshold = pd.read_parquet(
        threshold_path,
        columns=["TRANSACTION_CODE", "source_customer_id", "amount_to_service_threshold_ratio"],
    )
    threshold["pres_du_seuil"] = threshold["amount_to_service_threshold_ratio"].between(0.8, 1.0)
    thresh_agg = threshold.groupby("source_customer_id", observed=True).agg(
        part_pres_du_seuil=("pres_du_seuil", "mean"),
    ).reset_index()

    # --- role reseau : PLUS lu depuis network_features_light.parquet ---
    # BUG CONFIRME le 2026-07-20 : nb_expediteurs_distincts_past et
    # nb_destinataires_distincts_past (network_features.py, calcules via
    # merge_asof + cumsum de flags booleens) donnent des valeurs fausses a
    # l'echelle du fichier complet -- exemple verifie : TEL039808 donnait
    # "544 expediteurs distincts" alors que le compte direct sur les
    # transactions brutes donne 13 (verifie deux fois, par
    # destination_customer_id ET par DESTINATION_PHONE). Un sous-ensemble
    # isole de 71 lignes reproduit la fonction et donne le bon resultat
    # (13) -- le bug n'apparait qu'a l'echelle du fichier complet (cause
    # exacte non identifiee, probablement le merge_asof avec by= sur 175k
    # groupes). Plutot que de continuer a deboguer un pipeline merge_asof
    # complexe si pres de la remise, on remplace ces deux colonnes par un
    # calcul direct et verifie (nb_expediteurs_distincts_recus,
    # nb_destinataires_distincts_envoyes, voir plus haut) -- plus simple
    # (un comptage total, pas une version causale point-in-time), mais
    # dont chaque valeur a ete revérifiée manuellement sur les donnees
    # brutes. IMPACT A DOCUMENTER : ces deux colonnes buguees faisaient
    # partie des 24 features d'entree du modele CatBoost deja entraine
    # (feature_store.py) -- le modele n'a pas ete reentraine avec la
    # version corrigee faute de temps, limite assumee et a signaler.

    # --- regles metier (rule_flags, necessite un join pour recuperer le client) ---
    rules = pd.read_parquet(rule_flags_path)
    rule_id_map = pd.read_parquet(threshold_path, columns=["TRANSACTION_CODE", "source_customer_id"])
    rules = rules.merge(rule_id_map, on="TRANSACTION_CODE", how="left")
    rule_cols = ["rule_R1_above_unit_threshold", "rule_R2_above_daily_cumulative", "rule_R3_fractionnement",
                 "rule_R4_rafale", "rule_R6_nocturne_hors_norme", "rule_R7_profil_mule"]
    rules_agg = rules.groupby("source_customer_id", observed=True)[rule_cols].mean().reset_index()
    rules_agg.columns = ["source_customer_id"] + [f"part_{c}" for c in rule_cols]

    # --- historique d'alertes ---
    alert_history = pd.read_parquet(alert_history_path)

    # --- assemblage final (tenure_days deja fusionne dans base ci-dessus) ---
    metrics = base
    for other in [behav_agg, thresh_agg, rules_agg, alert_history]:
        metrics = metrics.merge(other, on="source_customer_id", how="left")

    metrics["part_jours_actifs"] = metrics["nb_jours_actifs"] / metrics["tenure_days"].clip(lower=1)
    metrics["nb_alertes_totales"] = metrics["nb_alertes_totales"].fillna(0)
    metrics["nb_alertes_recentes_30j"] = metrics["nb_alertes_recentes_30j"].fillna(0)
    metrics["niveau_alerte_max"] = metrics["niveau_alerte_max"].fillna("Aucune")
    metrics["zscore_moyen_abs"] = metrics["zscore_moyen_abs"].fillna(0)
    metrics["part_pres_du_seuil"] = metrics["part_pres_du_seuil"].fillna(0)
    for col in [c for c in metrics.columns if c.startswith("part_rule_")]:
        metrics[col] = metrics[col].fillna(0)

    # population pour laquelle les indicateurs cote-emission ont un sens --
    # voir _normalize_rank_scoped / _normalize_minmax_scoped
    metrics["is_sender"] = metrics["nb_transactions_total"] > 0

    return metrics


# =============================================================================
# DEUX methodes de normalisation, choisies apres verification empirique
# (2026-07-19) sur les vraies donnees -- une seule methode ne convenait pas
# a tous les types d'indicateurs :
#
# 1er essai : rang percentile classique (pd.rank(pct=True)). Casse sur les
# indicateurs de RISQUE, tres concentres a zero (99.97% des clients ont un
# taux de rafale nul, 97.1% n'ont jamais eu d'alerte) -- tous les clients a
# egalite sur zero se retrouvaient pousses vers le 50e percentile (moyenne
# du rang du bloc a egalite) au lieu de 0%. Resultat : personne sous
# 367/1000 de risque, la categorie officielle "Risque faible" (<250)
# restait vide.
#
# 2e essai : min-max borne (clip au 99e percentile). Corrige le probleme
# ci-dessus, mais casse a son tour sur les indicateurs de VALEUR (volume,
# frais), qui suivent une distribution tres etalee (quelques gros comptes,
# une masse de petits) -- une mise a l'echelle lineaire ecrasait presque
# tout le monde pres de zero (96.8% des clients en Bronze).
#
# Solution retenue : deux fonctions distinctes selon la nature de
# l'indicateur -- _normalize_minmax pour les indicateurs RARES/concentres a
# zero (parts de regles declenchees, alertes), _normalize_rank pour les
# indicateurs CONTINUS et etales (montants, anciennete) ou le classement par
# rang gere naturellement l'asymetrie de la distribution.
# =============================================================================


def _normalize_minmax(
    series: pd.Series, higher_is_worse_or_better: bool = True, clip_percentile: float = 0.99
) -> pd.Series:
    """Pour indicateurs concentres a zero (parts de regles, alertes) : mise
    a l'echelle min-max bornee au clip_percentile. Un client a zero reste a
    zero, contrairement au rang percentile qui le pousserait a tort vers le
    milieu de l'echelle."""
    filled = series.fillna(series.min() if series.notna().any() else 0)
    lower = filled.min()
    upper = filled.quantile(clip_percentile)
    if upper <= lower:
        scaled = pd.Series(0.0, index=series.index)
    else:
        scaled = ((filled - lower) / (upper - lower)).clip(0.0, 1.0)
    if not higher_is_worse_or_better:
        scaled = 1 - scaled
    return scaled


def _normalize_rank(series: pd.Series, higher_is_worse_or_better: bool = True) -> pd.Series:
    """Pour indicateurs continus et etales (montants, anciennete) : rang
    percentile, insensible a l'asymetrie de la distribution (contrairement
    au min-max). method='min' (plutot que 'average') pour qu'un eventuel
    bloc de valeurs a egalite reste pousse vers le bas de l'echelle plutot
    que vers son milieu."""
    filled = series.fillna(series.min() if series.notna().any() else 0)
    rank = filled.rank(pct=True, method="min")
    if not higher_is_worse_or_better:
        rank = 1 - rank
    return rank


def _normalize_rank_scoped(series: pd.Series, mask: pd.Series, higher_is_worse_or_better: bool = True) -> pd.Series:
    """Meme principe que _normalize_rank, mais le rang est calcule
    UNIQUEMENT parmi les lignes ou mask est vrai -- la population pour
    laquelle l'indicateur a reellement un sens. Necessaire depuis
    l'extension du classement client aux comptes recepteurs-seuls
    (2026-07-20) : classer un indicateur cote-emission (volume envoye,
    frais, etc.) sur TOUTE la population ferait bondir artificiellement le
    rang des emetteurs des qu'on ajoute une masse de comptes a zero sur cet
    indicateur -- verifie empiriquement (Bronze 53%->5%, Platine 8,6%->43%
    chez les emetteurs, sans qu'aucun n'ait change de comportement). Les
    lignes hors mask recoivent 0 (l'indicateur ne s'applique pas a elles)."""
    result = pd.Series(0.0, index=series.index)
    if mask.sum() == 0:
        return result
    result.loc[mask] = _normalize_rank(series[mask], higher_is_worse_or_better)
    return result


def _normalize_minmax_scoped(
    series: pd.Series, mask: pd.Series, higher_is_worse_or_better: bool = True, clip_percentile: float = 0.99
) -> pd.Series:
    """Meme principe que _normalize_minmax, borne a la population ou
    l'indicateur a un sens (voir _normalize_rank_scoped) -- le 99e
    percentile utilise pour le clip ne doit pas se calculer sur une masse de
    zeros structurels ajoutes par une population sans signal sur cet
    indicateur."""
    result = pd.Series(0.0, index=series.index)
    if mask.sum() == 0:
        return result
    result.loc[mask] = _normalize_minmax(series[mask], higher_is_worse_or_better, clip_percentile)
    return result


ALERT_LEVEL_RANK = {"Aucune": 0, "50%": 1, "80%": 2, "95%": 3, "100%": 4}


def compute_risk_score(metrics: pd.DataFrame, weights: dict) -> pd.DataFrame:
    df = metrics.copy()
    is_sender = df["is_sender"]

    # indicateurs concentres a zero (parts de regles booleennes) -> minmax.
    # zscore_moyen_abs est une magnitude continue -> rank. Tous bornes a
    # is_sender : un compte qui n'emet jamais n'a structurellement aucun de
    # ces signaux (voir _normalize_rank_scoped).
    comportement = pd.concat(
        [
            _normalize_rank_scoped(df["zscore_moyen_abs"], is_sender),
            _normalize_minmax_scoped(df["part_rule_R4_rafale"], is_sender),
            _normalize_minmax_scoped(df["part_rule_R6_nocturne_hors_norme"], is_sender),
        ],
        axis=1,
    ).max(axis=1)
    df["risk_comportement_anormal"] = comportement * weights["comportement_anormal"]

    contournement = pd.concat(
        [
            _normalize_minmax_scoped(df["part_pres_du_seuil"], is_sender),
            _normalize_minmax_scoped(df["part_rule_R3_fractionnement"], is_sender),
            _normalize_minmax_scoped(df["part_rule_R1_above_unit_threshold"], is_sender),
            _normalize_minmax_scoped(df["part_rule_R2_above_daily_cumulative"], is_sender),
            _normalize_minmax_scoped(df["part_gimtel"], is_sender),
        ],
        axis=1,
    ).max(axis=1)
    df["risk_contournement"] = contournement * weights["contournement"]

    role_reseau = pd.concat(
        [
            # fan-out verifie (destinataires distincts, cote emission) -> borne a is_sender
            _normalize_minmax_scoped(df["nb_destinataires_distincts_envoyes"], is_sender),
            _normalize_minmax_scoped(df["part_rule_R7_profil_mule"], is_sender),
            # fan-in verifie (C-03, expediteurs distincts recus) : NON borne
            # a is_sender, calcule sur toute la population -- c'est le seul
            # signal de risque disponible pour un compte qui ne fait QUE
            # recevoir, et le but meme de l'extension du 2026-07-20 (voir
            # aggregate_customer_metrics)
            _normalize_minmax(df["nb_expediteurs_distincts_recus"]),
        ],
        axis=1,
    ).max(axis=1)
    df["risk_role_reseau"] = role_reseau * weights["role_reseau"]

    # historique d'alertes budget (volet B) : lui aussi purement cote
    # emission (budget_engine.py agrege par source_customer_id, un compte
    # qui ne depense jamais ne consomme aucune enveloppe) -> borne a is_sender
    niveau_rank = df["niveau_alerte_max"].astype(str).map(ALERT_LEVEL_RANK).fillna(0).astype(float)
    historique_alertes = pd.concat(
        [
            _normalize_minmax_scoped(df["nb_alertes_totales"], is_sender),
            _normalize_minmax_scoped(df["nb_alertes_recentes_30j"], is_sender) * 1.5,  # alertes recentes pesent plus
            _normalize_minmax_scoped(niveau_rank, is_sender),
        ],
        axis=1,
    ).mean(axis=1).clip(upper=1.0)
    df["risk_historique_alertes"] = historique_alertes * weights["historique_alertes"]

    # profil : moins d'anciennete = plus de risque (compte recent, KYC non
    # disponible dans ce fichier -- limite documentee). tenure_days est
    # continu (peu d'egalites) -> rank.
    df["risk_profil"] = _normalize_rank(df["tenure_days"], higher_is_worse_or_better=False) * weights["profil"]

    subscore_cols = [
        "risk_comportement_anormal", "risk_contournement", "risk_role_reseau",
        "risk_historique_alertes", "risk_profil",
    ]
    df["score_risque"] = df[subscore_cols].sum(axis=1).round().astype(int)
    return df


def compute_value_score(metrics: pd.DataFrame, weights: dict) -> pd.DataFrame:
    df = metrics.copy()

    # tous des indicateurs continus/etales (montants, ratios, anciennete)
    # -> rank, insensible a l'asymetrie des distributions financieres.
    #
    # IMPORTANT (corrige le 2026-07-20 apres verification empirique, voir
    # _normalize_rank_scoped) : volume/frais/regularite/diversite sont des
    # signaux purement cote EMISSION (0 structurel pour un compte qui n'a
    # jamais envoye) -> bornes a is_sender, pour que le rang des 40 866
    # emetteurs deja valides reste identique a avant l'extension. Seule
    # l'anciennete (tenure_days) est un concept valable pour tout le monde,
    # source ou destination -> classee sur la population complete.
    is_sender = df["is_sender"]
    df["value_volume"] = _normalize_rank_scoped(df["volume_total"], is_sender) * weights["volume"]
    df["value_rentabilite"] = _normalize_rank_scoped(df["frais_totaux"], is_sender) * weights["rentabilite"]
    df["value_regularite"] = _normalize_rank_scoped(df["part_jours_actifs"], is_sender) * weights["regularite"]
    df["value_diversite"] = _normalize_rank_scoped(df["nb_services_distincts"], is_sender) * weights["diversite"]
    df["value_anciennete"] = _normalize_rank(df["tenure_days"]) * weights["anciennete"]

    subscore_cols = ["value_volume", "value_rentabilite", "value_regularite", "value_diversite", "value_anciennete"]
    df["score_valeur"] = df[subscore_cols].sum(axis=1).round().astype(int)
    return df


def assign_segment(score: pd.Series, segments_config: dict) -> pd.Series:
    conditions = []
    choices = []
    for label, bounds in segments_config.items():
        conditions.append((score >= bounds["min"]) & (score <= bounds["max"]))
        choices.append(label)
    return pd.Series(np.select(conditions, choices, default="Indetermine"), index=score.index)


def build_customer_scores(config_path: str | Path = "configs/config.yaml") -> pd.DataFrame:
    cfg = load_config(config_path)
    metrics = aggregate_customer_metrics()
    df = compute_risk_score(metrics, cfg["risk_score_weights"])
    df = compute_value_score(df, cfg["value_score_weights"])
    df["segment_risque"] = assign_segment(df["score_risque"], cfg["risk_segments"])
    df["segment_valeur"] = assign_segment(df["score_valeur"], cfg["value_segments"])
    return df


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="configs/config.yaml")
    parser.add_argument("--output", default="data/features/customer_risk_value_scores.parquet")
    args = parser.parse_args()

    df = build_customer_scores(args.config)

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out_path, index=False)

    print(f"{len(df):,} clients scores, ecrit dans {out_path}")
    print("\nDistribution segment_risque :")
    print(df["segment_risque"].value_counts())
    print("\nDistribution segment_valeur :")
    print(df["segment_valeur"].value_counts())
    print("\nscore_risque :", df["score_risque"].describe())
    print("\nscore_valeur :", df["score_valeur"].describe())


if __name__ == "__main__":
    main()
