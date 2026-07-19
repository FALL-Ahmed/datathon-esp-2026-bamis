"""
Genere les niveaux d'alerte de consommation de seuil : 50%, 80%, 95%, 100%,
et conserve un historique d'alertes par client (reutilise ensuite par
scoring/customer_scoring.py, critere "Historique d'alertes", 150 points).

Le niveau d'alerte est calcule separement pour le taux journalier et le
taux mensuel (budget/budget_engine.py), puis le niveau retenu par ligne est
le PLUS SEVERE des deux -- une alerte doit remonter des qu'un des deux
seuils est franchi, pas seulement quand les deux le sont en meme temps.

Les seuils d'alerte (50/80/95/100%) viennent de configs/config.yaml ->
budget_alert_levels, jamais codes en dur.

Usage :
    python -m bamis_fraud.budget.alert_engine --input data/features/budget_consumption.parquet
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import yaml

ALERT_LABELS = ["Aucune", "50%", "80%", "95%", "100%"]


def load_alert_levels(config_path: str | Path = "configs/config.yaml") -> list[float]:
    path = Path(config_path)
    if not path.exists():
        return [0.5, 0.8, 0.95, 1.0]
    with open(path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    return cfg.get("budget_alert_levels", [0.5, 0.8, 0.95, 1.0])


def compute_alert_level(taux: pd.Series, alert_levels: list[float]) -> pd.Series:
    """Retourne un niveau d'alerte categoriel ('Aucune', '50%', '80%',
    '95%', '100%') a partir d'un taux de consommation continu."""
    bins = [-float("inf")] + list(alert_levels) + [float("inf")]
    return pd.cut(taux.fillna(0.0), bins=bins, labels=ALERT_LABELS, right=False)


def _more_severe(a: pd.Series, b: pd.Series) -> pd.Series:
    order = {label: i for i, label in enumerate(ALERT_LABELS)}
    a_rank = a.map(order)
    b_rank = b.map(order)
    return a.where(a_rank >= b_rank, b)


def build_budget_alerts(budget_consumption: pd.DataFrame, alert_levels: list[float]) -> pd.DataFrame:
    df = budget_consumption.copy()
    df["niveau_alerte_jour"] = compute_alert_level(df["taux_consommation_jour"], alert_levels)
    df["niveau_alerte_mois"] = compute_alert_level(df["taux_consommation_mois"], alert_levels)
    df["niveau_alerte"] = _more_severe(df["niveau_alerte_jour"], df["niveau_alerte_mois"])
    return df


def build_alert_history(alerts: pd.DataFrame, recent_days: int = 30) -> pd.DataFrame:
    """Historique d'alertes par client, agrege tous services confondus --
    alimente scoring/customer_scoring.py (critere 'Historique d'alertes').
    Version vectorisee (colonnes + groupby.agg, pas de groupby.apply avec
    lambda) -- indispensable avec 175k+ clients distincts, un apply par
    groupe serait bien trop lent a cette echelle."""
    order = {label: i for i, label in enumerate(ALERT_LABELS)}
    alerts = alerts.copy()
    alerts["_has_alert"] = (alerts["niveau_alerte"] != "Aucune").astype(int)
    max_date = pd.to_datetime(alerts["periode_jour"]).max()
    alerts["_is_recent"] = pd.to_datetime(alerts["periode_jour"]) >= (
        max_date - pd.Timedelta(days=recent_days)
    )
    alerts["_recent_alert"] = alerts["_has_alert"] & alerts["_is_recent"]
    alerts["_niveau_rank"] = alerts["niveau_alerte"].map(order)

    history = (
        alerts.groupby("source_customer_id", observed=True)
        .agg(
            nb_alertes_totales=("_has_alert", "sum"),
            nb_alertes_recentes_30j=("_recent_alert", "sum"),
            niveau_alerte_max_rank=("_niveau_rank", "max"),
        )
        .reset_index()
    )
    history["niveau_alerte_max"] = history["niveau_alerte_max_rank"].map(
        {v: k for k, v in order.items()}
    )
    history = history.drop(columns=["niveau_alerte_max_rank"])
    return history


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default="data/features/budget_consumption.parquet")
    parser.add_argument("--config", default="configs/config.yaml")
    parser.add_argument("--output-alerts", default="data/features/budget_alerts.parquet")
    parser.add_argument("--output-history", default="data/features/customer_alert_history.parquet")
    args = parser.parse_args()

    budget_consumption = pd.read_parquet(args.input)
    alert_levels = load_alert_levels(args.config)

    alerts = build_budget_alerts(budget_consumption, alert_levels)
    history = build_alert_history(alerts)

    Path(args.output_alerts).parent.mkdir(parents=True, exist_ok=True)
    alerts.to_parquet(args.output_alerts, index=False)
    history.to_parquet(args.output_history, index=False)

    print(f"{len(alerts):,} lignes d'alertes ecrites dans {args.output_alerts}")
    print("Repartition des niveaux d'alerte :")
    print(alerts["niveau_alerte"].value_counts())
    print(f"\n{len(history):,} clients avec historique d'alertes ecrit dans {args.output_history}")
    print(f"Clients avec au moins 1 alerte : {(history['nb_alertes_totales'] > 0).sum():,}")


if __name__ == "__main__":
    main()
