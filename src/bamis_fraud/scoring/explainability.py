"""
Genere les "5 principaux facteurs" exiges par le cahier des charges pour
le classement client (volet C), en langage simple, pas seulement des noms
de variables techniques. Un score sans explication est explicitement
disqualifiant ("n'est pas exploitable").

APPROCHE POUR LE VOLET C (implementee ici) : les scores de risque et de
valeur sont des SOMMES PONDEREES DE 5 SOUS-CRITERES NOMMES (voir
scoring/customer_scoring.py) -- la formule est deja additive et
transparente par construction, pas besoin de SHAP. Expliquer un score
revient a trier ses 5 sous-scores par contribution decroissante et a les
traduire en phrases.

PAS ENCORE IMPLEMENTE : l'explication au niveau transaction (volet A) par
SHAP sur le modele ML, qui necessite un modele entraine
(modeling/model_registry.py, pas encore construit).

Usage :
    depuis scoring/customer_scoring.py ou scripts/08_score_customers.py
"""
from __future__ import annotations

import pandas as pd

RISK_TEMPLATES = {
    "risk_comportement_anormal": lambda r: (
        f"Comportement anormal ({r['risk_comportement_anormal']:.0f}/300 pts) : "
        f"écart moyen à son historique habituel de {r['zscore_moyen_abs']:.1f} écarts-types"
        if pd.notna(r.get("zscore_moyen_abs")) else
        f"Comportement anormal ({r['risk_comportement_anormal']:.0f}/300 pts) : pas assez d'historique pour comparer"
    ),
    "risk_contournement": lambda r: (
        f"Contournement ({r['risk_contournement']:.0f}/250 pts) : "
        f"{r['part_pres_du_seuil']:.0%} de ses opérations sont collées au seuil du service"
    ),
    "risk_role_reseau": lambda r: (
        f"Rôle dans un réseau ({r['risk_role_reseau']:.0f}/200 pts) : "
        f"a reçu de l'argent de {r['nb_expediteurs_distincts_recus']:.0f} expéditeurs différents, "
        f"envoyé à {r['nb_destinataires_distincts_envoyes']:.0f} destinataires différents"
    ),
    "risk_historique_alertes": lambda r: (
        f"Historique d'alertes ({r['risk_historique_alertes']:.0f}/150 pts) : "
        f"{r['nb_alertes_totales']:.0f} alerte(s) au total, dont {r['nb_alertes_recentes_30j']:.0f} "
        f"dans les 30 derniers jours (niveau max atteint : {r['niveau_alerte_max']})"
    ),
    "risk_profil": lambda r: (
        f"Profil ({r['risk_profil']:.0f}/100 pts) : client depuis {r['tenure_days']:.0f} jours "
        f"(KYC non disponible dans les données)"
    ),
}

VALUE_TEMPLATES = {
    "value_volume": lambda r: (
        f"Volume ({r['value_volume']:.0f}/300 pts) : a fait circuler {r['volume_total']:,.0f} MRU au total"
    ),
    "value_rentabilite": lambda r: (
        f"Rentabilité ({r['value_rentabilite']:.0f}/250 pts) : a généré {r['frais_totaux']:,.0f} MRU de frais"
    ),
    "value_regularite": lambda r: (
        f"Régularité ({r['value_regularite']:.0f}/200 pts) : actif {r['part_jours_actifs']:.0%} du temps "
        f"depuis sa première transaction"
    ),
    "value_diversite": lambda r: (
        f"Diversité ({r['value_diversite']:.0f}/150 pts) : utilise {r['nb_services_distincts']:.0f} service(s) différent(s)"
    ),
    "value_anciennete": lambda r: (
        f"Ancienneté ({r['value_anciennete']:.0f}/100 pts) : client depuis {r['tenure_days']:.0f} jours"
    ),
}


def _explain_row(row: pd.Series, templates: dict) -> str:
    ranked = sorted(templates.keys(), key=lambda c: row[c], reverse=True)
    sentences = [templates[c](row) for c in ranked]
    return " ; ".join(sentences)


def explain_risk_scores(df: pd.DataFrame) -> pd.Series:
    return df.apply(lambda r: _explain_row(r, RISK_TEMPLATES), axis=1)


def explain_value_scores(df: pd.DataFrame) -> pd.Series:
    return df.apply(lambda r: _explain_row(r, VALUE_TEMPLATES), axis=1)


def add_explanations(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["explication_risque"] = explain_risk_scores(df)
    df["explication_valeur"] = explain_value_scores(df)
    return df
