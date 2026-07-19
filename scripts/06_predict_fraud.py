"""
Etape 6/10. Applique le modele CatBoost entraine (models/catboost_v1.cbm) a
un jeu de transactions deja passe par le pipeline de features (feature_store.py).

STATUT (2026-07-19) : aucun fichier de test officiel n'a ete recu du jury.
Par defaut, tourne sur data/features/feature_matrix_transactions.parquet
(l'ensemble des transactions connues). Des reception d'un fichier de test
officiel : le faire passer par scripts/01 -> 02 -> 03 (jusqu'a
feature_store.py inclus) pour produire un feature_matrix_transactions
equivalent, puis relancer ce script avec --input pointant dessus -- aucune
autre modification necessaire.

Usage :
    python scripts/06_predict_fraud.py
    python scripts/06_predict_fraud.py --input data/features/<nouveau_fichier_test>.parquet

Sortie : data/features/test_predictions.parquet
"""
from __future__ import annotations

import argparse

from bamis_fraud.modeling.predict import run_predict


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default="data/features/feature_matrix_transactions.parquet")
    parser.add_argument("--model", default="models/catboost_v1.cbm")
    parser.add_argument("--output", default="data/features/test_predictions.parquet")
    args = parser.parse_args()

    out = run_predict(args.input, args.model, args.output)
    print(f"{len(out):,} transactions notees, ecrit dans {args.output}")
    print(out["score_fraude"].describe())


if __name__ == "__main__":
    main()
