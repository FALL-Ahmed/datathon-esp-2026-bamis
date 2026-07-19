"""
Convertit les sorties du module graphe (mule_detection.py,
pattern_detection.py) en une table de features PAR CLIENT, exploitable par
scoring/customer_scoring.py (critere "Role dans un reseau", 200 points) et
par un futur entrainement ML incluant le signal reseau complet.

FEATURES PRODUITES
-------------------
- mule_score, passthrough_rate, n_quick_passthrough (mule_detection.py)
- n_expediteurs_distincts, n_destinataires_distincts (fan-in/fan-out,
  recalcules sur la POPULATION COMPLETE ici, pas seulement le top-N
  "leaderboard" sauvegarde par pattern_detection.py)
- n_circuits_fermes, is_in_closed_circuit (pattern_detection.py)

PERIMETRE NON COUVERT (voir pattern_detection.py) : chaines de rebond 3+
sauts (C-05) et fractionnement multi-comptes (C-10) -- pas de colonnes
correspondantes ici, documente comme limite assumee.

Usage :
    python -m bamis_fraud.graph.graph_features
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from bamis_fraud.graph.pattern_detection import detect_fan_in, detect_fan_out


def build_graph_features(
    edgelist_path: str = "data/graph/edgelist.parquet",
    mule_scores_path: str = "data/graph/mule_scores.parquet",
    closed_circuits_path: str = "data/graph/closed_circuits.parquet",
) -> pd.DataFrame:
    edgelist = pd.read_parquet(edgelist_path)

    fan_in = detect_fan_in(edgelist, top_n=None).rename(columns={"phone": "source_customer_id"})
    fan_out = detect_fan_out(edgelist, top_n=None).rename(columns={"phone": "source_customer_id"})

    mule = pd.read_parquet(mule_scores_path).rename(columns={"phone": "source_customer_id"})[
        ["source_customer_id", "mule_score", "passthrough_rate", "n_quick_passthrough"]
    ]

    circuits = pd.read_parquet(closed_circuits_path)
    circuit_counts_a = circuits.groupby("compte_A").size()
    circuit_counts_b = circuits.groupby("compte_B").size()
    circuit_counts = pd.concat([circuit_counts_a, circuit_counts_b]).groupby(level=0).sum().reset_index()
    circuit_counts.columns = ["source_customer_id", "n_circuits_fermes"]

    features = fan_in.merge(fan_out, on="source_customer_id", how="outer")
    features = features.merge(mule, on="source_customer_id", how="left")
    features = features.merge(circuit_counts, on="source_customer_id", how="left")

    features["n_expediteurs_distincts"] = features["n_expediteurs_distincts"].fillna(0).astype(int)
    features["n_destinataires_distincts"] = features["n_destinataires_distincts"].fillna(0).astype(int)
    features["n_circuits_fermes"] = features["n_circuits_fermes"].fillna(0).astype(int)
    features["is_in_closed_circuit"] = features["n_circuits_fermes"] > 0
    features["mule_score"] = features["mule_score"].fillna(0.0)
    features["passthrough_rate"] = features["passthrough_rate"].fillna(0.0)
    features["n_quick_passthrough"] = features["n_quick_passthrough"].fillna(0).astype(int)

    return features


def main() -> None:
    features = build_graph_features()

    out_path = Path("data/features/graph_features.parquet")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    features.to_parquet(out_path, index=False)

    print(f"{len(features):,} comptes avec features graphe, ecrit dans {out_path}")
    print(f"Comptes impliques dans au moins un circuit ferme : {features['is_in_closed_circuit'].sum():,}")
    print(f"Comptes avec au moins 3 pass-through rapides repetes : "
          f"{(features['n_quick_passthrough'] >= 3).sum():,}")


if __name__ == "__main__":
    main()
