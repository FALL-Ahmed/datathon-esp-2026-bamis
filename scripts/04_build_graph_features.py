"""
Etape 4/10 (bonus, niveau 3 -- mules/patterns invisibles en
transaction-par-transaction). Construit le graphe (graph_builder), detecte
mules et patterns (mule_detection, pattern_detection), exporte les
features reseau par client (graph_features).

Perimetre : fan-in, fan-out, mule (pass-through repete), circuits fermes
courts (A->B->A). PAS de chaines de rebond 3+ sauts ni de fractionnement
multi-comptes dans ce premier passage (voir pattern_detection.py pour la
justification).

Usage :
    python scripts/04_build_graph_features.py

Sortie : data/graph/edgelist.parquet, mule_scores.parquet, fan_in.parquet,
         fan_out.parquet, closed_circuits.parquet,
         data/features/graph_features.parquet
"""
from __future__ import annotations

import time

from bamis_fraud.graph.graph_builder import main as graph_builder_main
from bamis_fraud.graph.mule_detection import main as mule_detection_main
from bamis_fraud.graph.pattern_detection import main as pattern_detection_main
from bamis_fraud.graph.graph_features import main as graph_features_main


def main() -> None:
    t0 = time.time()

    print("=== graph_builder ===")
    graph_builder_main()

    print("\n=== mule_detection ===")
    mule_detection_main()

    print("\n=== pattern_detection ===")
    pattern_detection_main()

    print("\n=== graph_features ===")
    graph_features_main()

    print(f"\nEtape 4 terminee en {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
