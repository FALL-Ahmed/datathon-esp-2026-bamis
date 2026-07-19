"""
Implemente la matrice de traitement croisant segment de valeur x segment de
risque -> action recommandee (seuil majore, seuil normal, seuil reduit,
surveillance, surveillance renforcee, gel/investigation), telle que definie
dans le cahier des charges. Table lue depuis configs/config.yaml ->
treatment_matrix, jamais codee en dur.

Usage :
    depuis scoring/customer_scoring.py ou scripts/08_score_customers.py
"""
from __future__ import annotations

import pandas as pd


def _value_matrix_key(value_segment: str) -> str:
    """Platine et Or partagent la meme ligne dans la matrice du cahier des
    charges -- cf. configs/config.yaml -> treatment_matrix.Platine_or_Or."""
    if value_segment in ("Platine", "Or"):
        return "Platine_or_Or"
    return value_segment


def get_recommended_action(value_segment: str, risk_segment: str, matrix_config: dict) -> str:
    key = _value_matrix_key(value_segment)
    row = matrix_config.get(key, {})
    return row.get(risk_segment, "Indetermine")


def add_recommended_actions(df: pd.DataFrame, matrix_config: dict) -> pd.DataFrame:
    df = df.copy()
    df["action_recommandee"] = [
        get_recommended_action(v, r, matrix_config)
        for v, r in zip(df["segment_valeur"], df["segment_risque"])
    ]
    return df
