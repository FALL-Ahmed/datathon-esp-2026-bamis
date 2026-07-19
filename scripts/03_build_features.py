"""
Etape 3/10. Calcule les features de transaction sur data/processed/transactions_clean.parquet :
seuil, comportement (historique client), velocite (rafales), reseau leger,
puis les regles metier niveau 1 (qui servent aussi de pseudo-label
d'entrainement, voir ARCHITECTURE.md section 0).

Implemente a ce stade : threshold_features, behavioral_features,
velocity_features, network_features_light, business_rules.
Pas encore implemente : channel_features, temporal_features, budget/alert_engine,
feature_store.py (assemblage final) -- ce script sera complete au fur et a
mesure, sans changer l'ordre des etapes deja en place. Voir ARCHITECTURE.md
pour l'etat d'avancement a jour.

Usage :
    python scripts/03_build_features.py

Sorties :
    data/features/threshold_features.parquet
    data/features/behavioral_features.parquet
    data/features/velocity_features.parquet
    data/features/network_features_light.parquet
    data/features/rule_flags.parquet
"""
from __future__ import annotations

import argparse
import time

from bamis_fraud.feature_engineering.threshold_features import main as threshold_main
from bamis_fraud.feature_engineering.behavioral_features import main as behavioral_main
from bamis_fraud.feature_engineering.velocity_features import main as velocity_main
from bamis_fraud.feature_engineering.network_features import main as network_main
from bamis_fraud.rules.business_rules import main as rules_main


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

    print("=== threshold_features ===")
    _run(threshold_main, ["threshold_features", "--input", args.input, "--thresholds", args.thresholds])

    print("\n=== behavioral_features ===")
    _run(behavioral_main, ["behavioral_features", "--input", args.input])

    print("\n=== velocity_features ===")
    _run(velocity_main, ["velocity_features", "--input", args.input])

    print("\n=== network_features ===")
    _run(network_main, ["network_features", "--input", args.input])

    print("\n=== business_rules (regles + pseudo-label) ===")
    _run(rules_main, ["business_rules", "--transactions", args.input, "--config", args.config])

    print(f"\nEtape 3 terminee en {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
