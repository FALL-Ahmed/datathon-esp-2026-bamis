"""
Etape 7/10. Calcule la consommation d'enveloppes par client x service
(budget/budget_engine.py) et les niveaux d'alerte (budget/alert_engine.py)
sur l'ensemble du jeu de donnees (train + test si fourni), tous canaux
confondus (aucune colonne canal dans les regroupements -- c'est ce qui
empeche le contournement C-08).

Usage :
    python scripts/07_compute_budget.py

Sorties :
    data/features/budget_consumption.parquet
    data/features/budget_alerts.parquet
    data/features/customer_alert_history.parquet
"""
from __future__ import annotations

import argparse
import time

from bamis_fraud.budget.budget_engine import main as budget_main
from bamis_fraud.budget.alert_engine import main as alert_main


def _run(step_main, argv: list[str]) -> None:
    import sys

    sys.argv = argv
    step_main()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default="data/processed/transactions_clean.parquet")
    parser.add_argument("--thresholds", default="configs/thresholds/seuils_services.csv")
    parser.add_argument("--config", default="configs/config.yaml")
    args = parser.parse_args()

    t0 = time.time()

    print("=== budget_engine ===")
    _run(
        budget_main,
        ["budget_engine", "--input", args.input, "--thresholds", args.thresholds, "--config", args.config],
    )

    print("\n=== alert_engine ===")
    _run(
        alert_main,
        ["alert_engine", "--input", "data/features/budget_consumption.parquet", "--config", args.config],
    )

    print(f"\nEtape 7 terminee en {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
