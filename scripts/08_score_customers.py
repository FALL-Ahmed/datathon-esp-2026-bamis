"""
Etape 8/10. Calcule les scores de risque et de valeur par client
(scoring/customer_scoring.py), la segmentation, la matrice de traitement
(scoring/treatment_matrix.py) et les explications en langage simple
(scoring/explainability.py).

Usage :
    python scripts/08_score_customers.py

Sortie : data/features/customer_risk_value_scores.parquet
"""
from __future__ import annotations

import argparse
import time
from pathlib import Path

from bamis_fraud.scoring.customer_scoring import build_customer_scores, load_config
from bamis_fraud.scoring.treatment_matrix import add_recommended_actions
from bamis_fraud.scoring.explainability import add_explanations


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="configs/config.yaml")
    parser.add_argument("--output", default="data/features/customer_risk_value_scores.parquet")
    args = parser.parse_args()

    t0 = time.time()
    cfg = load_config(args.config)

    print("Calcul des scores de risque et de valeur...")
    df = build_customer_scores(args.config)

    print("Matrice de traitement...")
    df = add_recommended_actions(df, cfg["treatment_matrix"])

    print("Explications en langage simple...")
    df = add_explanations(df)

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out_path, index=False)

    print(f"\n{len(df):,} clients scores en {time.time() - t0:.1f}s, ecrit dans {out_path}")
    print("\nSegments de risque :")
    print(df["segment_risque"].value_counts())
    print("\nSegments de valeur :")
    print(df["segment_valeur"].value_counts())
    print("\nActions recommandees :")
    print(df["action_recommandee"].value_counts())
    print("\nExemple d'explication (client au risque le plus eleve) :")
    top_risk = df.loc[df["score_risque"].idxmax()]
    print(f"  Client {top_risk['source_customer_id']} -- score risque {top_risk['score_risque']}, segment {top_risk['segment_risque']}")
    print(f"  {top_risk['explication_risque']}")


if __name__ == "__main__":
    main()
