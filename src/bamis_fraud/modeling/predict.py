"""
Applique le modele CatBoost entraine (modeling/train.py) a un jeu de
transactions, dans l'ORDRE EXACT d'entree (piege explicitement signale par
le cahier des charges : "oublier l'ordre exact des transactions du fichier
test") -- aucun tri, aucun reindex.

STATUT (2026-07-19) : aucun fichier de test officiel n'a ete recu du jury
(et n'est probablement jamais fourni, voir
configs/schema_map.yaml -> decision_2026_07_19_pas_de_labels_a_attendre).
Ce script tourne donc par defaut sur feature_matrix_transactions.parquet
(l'ensemble des transactions connues) pour produire un exemple complet et
fonctionnel du format de soumission. Le jour ou un fichier de test officiel
arrive : le faire passer par le MEME pipeline complet
(ingestion/schema_audit -> loader -> preprocessing -> feature_engineering
-> feature_store) puis pointer --input vers le nouveau
feature_matrix_transactions -- ce script n'a besoin d'aucune modification.

PAS DE CALIBRATION SUPPLEMENTAIRE (modeling/calibration.py non implemente,
limite assumee) : CatBoost est entraine avec class-weighting equilibre et
la fonction de perte par defaut (Logloss), ses predict_proba sont deja des
probabilites raisonnables sans etape de calibration separee. A ameliorer
si le temps le permet.

Usage :
    python -m bamis_fraud.modeling.predict
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from catboost import CatBoostClassifier

from bamis_fraud.feature_engineering.feature_store import FEATURE_COLUMNS
from bamis_fraud.modeling.train import BOOL_COLUMNS


def load_model(path: str = "models/catboost_v1.cbm") -> CatBoostClassifier:
    model = CatBoostClassifier()
    model.load_model(path)
    return model


def _prep_X_for_inference(df: pd.DataFrame) -> pd.DataFrame:
    X = df[FEATURE_COLUMNS].copy()
    for col in BOOL_COLUMNS:
        if col in X.columns:
            X[col] = X[col].astype(float)
    X = X.replace([np.inf, -np.inf], np.nan)
    return X


def predict_fraud_scores(model: CatBoostClassifier, X: pd.DataFrame) -> np.ndarray:
    return model.predict_proba(X)[:, 1]


def run_predict(
    feature_matrix_path: str = "data/features/feature_matrix_transactions.parquet",
    model_path: str = "models/catboost_v1.cbm",
    output_path: str = "data/features/test_predictions.parquet",
) -> pd.DataFrame:
    df = pd.read_parquet(feature_matrix_path)  # ordre d'origine preserve, aucun tri
    model = load_model(model_path)
    X = _prep_X_for_inference(df)

    scores = predict_fraud_scores(model, X)
    out = pd.DataFrame({"TRANSACTION_CODE": df["TRANSACTION_CODE"], "score_fraude": scores})

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(output_path, index=False)
    return out


def main() -> None:
    import argparse

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
