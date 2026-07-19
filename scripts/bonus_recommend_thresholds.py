"""
Etape bonus (hors la sequence obligatoire 01-09). Traduit la matrice de
traitement du volet C (segment_valeur x segment_risque -> action_recommandee,
scoring/treatment_matrix.py) en seuils chiffres personnalises par client x
service (budget/threshold_recommender.py) -- le bonus explicitement demande
par le cahier des charges : "proposez un seuil plus haut ou plus bas selon
la classe de risque du client (lien avec le volet C)".

Prerequis : scripts/07_compute_budget.py et scripts/08_score_customers.py
doivent avoir deja tourne (ce script lit leurs sorties).

Usage :
    python scripts/bonus_recommend_thresholds.py

Sortie : outputs/reports/recommandations_seuils.csv
"""
from __future__ import annotations

from bamis_fraud.budget.threshold_recommender import main as threshold_main

if __name__ == "__main__":
    threshold_main()
