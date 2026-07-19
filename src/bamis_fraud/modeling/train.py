"""
Orchestration de l'entrainement, dans l'ordre de complexite croissante
defini dans ARCHITECTURE.md section 7 (baseline -> regression logistique ->
CatBoost, modele candidat par defaut). Gestion explicite du desequilibre de
classes (~0.5% de pseudo-fraude) via class_weight/auto_class_weights,
jamais de sur-echantillonnage qui casserait la structure temporelle.

CIBLE : pseudo_label_fraud (cf. rules/business_rules.py) -- aucun label
officiel n'est fourni par le jury, voir configs/schema_map.yaml ->
decision_2026_07_19_pas_de_labels_a_attendre.

Usage :
    python -m bamis_fraud.modeling.train
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from catboost import CatBoostClassifier
from sklearn.linear_model import LogisticRegression

from bamis_fraud.modeling.datasets import load_feature_matrix, prepare_splits
from bamis_fraud.modeling.evaluate import evaluate_predictions
from bamis_fraud.utils.seed import set_global_seed

BOOL_COLUMNS = ["is_above_unit_threshold", "is_new_beneficiary", "is_external_gimtel"]


def load_model_config(path: str = "configs/model_config.yaml") -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _prep_X(X: pd.DataFrame) -> pd.DataFrame:
    """CatBoost gere nativement les NaN numeriques, mais pas les booleens
    Python ni les valeurs infinies -- conversion explicite en 0/1, et les
    +-inf (ex. ratio_montant_recu_envoye_past quand le denominateur est nul,
    cf. network_features.py) sont remplaces par NaN plutot que laisses tels
    quels (scikit-learn plante dessus, CatBoost les tolere mais les traite
    mal statistiquement)."""
    X = X.copy()
    for col in BOOL_COLUMNS:
        if col in X.columns:
            X[col] = X[col].astype(float)
    X = X.replace([np.inf, -np.inf], np.nan)
    return X


def train_baseline(X: pd.DataFrame) -> pd.Series:
    """Regle "montant / seuil" en score continu -- plancher de reference,
    aucun entrainement necessaire."""
    return X["amount_to_service_threshold_ratio"].fillna(0).clip(upper=5) / 5


def train_logistic_regression(X_train, y_train, config: dict) -> LogisticRegression:
    X_filled = X_train.fillna(-1)
    model = LogisticRegression(
        penalty=config["penalty"],
        C=config["C"],
        class_weight=config["class_weight"],
        max_iter=config["max_iter"],
        solver=config["solver"],
        random_state=config.get("random_seed", 42),
    )
    model.fit(X_filled, y_train)
    return model


def train_catboost(X_train, y_train, X_valid, y_valid, config: dict) -> CatBoostClassifier:
    model = CatBoostClassifier(
        iterations=config["iterations"],
        depth=config["depth"],
        learning_rate=config["learning_rate"],
        auto_class_weights=config["auto_class_weights"],
        eval_metric="AUC",  # PRAUC non disponible nativement dans cette version -- AUC en early-stopping, AUC-PR calcule separement par evaluate.py
        random_seed=config.get("random_seed", 42),
        early_stopping_rounds=config["early_stopping_rounds"],
        verbose=False,
    )
    model.fit(X_train, y_train, eval_set=(X_valid, y_valid), use_best_model=True)
    return model


def run_cross_validation(df: pd.DataFrame, model_cfg: dict) -> dict:
    """Entraine baseline + LR + CatBoost sur chacun des 3 folds
    walk-forward, retourne l'AUC-PR de chaque modele sur chaque fold."""
    splits = prepare_splits(df)
    X, y = splits["X"], splits["y"]
    X = _prep_X(X)

    results = {"folds": []}
    for i, (train_idx, valid_idx) in enumerate(splits["folds"], start=1):
        X_train, y_train = X.loc[train_idx], y.loc[train_idx]
        X_valid, y_valid = X.loc[valid_idx], y.loc[valid_idx]

        fold_result = {"fold": i, "n_train": len(train_idx), "n_valid": len(valid_idx)}

        baseline_scores = train_baseline(X_valid)
        fold_result["baseline_auc_pr"] = evaluate_predictions(y_valid, baseline_scores)["auc_pr"]

        lr_model = train_logistic_regression(X_train, y_train, model_cfg["logistic_regression"])
        lr_scores = lr_model.predict_proba(X_valid.fillna(-1))[:, 1]
        fold_result["logistic_regression_auc_pr"] = evaluate_predictions(y_valid, lr_scores)["auc_pr"]

        cb_model = train_catboost(X_train, y_train, X_valid, y_valid, model_cfg["catboost"])
        cb_scores = cb_model.predict_proba(X_valid)[:, 1]
        fold_result["catboost_auc_pr"] = evaluate_predictions(y_valid, cb_scores)["auc_pr"]

        results["folds"].append(fold_result)
        print(f"Fold {i} : baseline={fold_result['baseline_auc_pr']:.4f}  "
              f"LR={fold_result['logistic_regression_auc_pr']:.4f}  "
              f"CatBoost={fold_result['catboost_auc_pr']:.4f}")

    for model_name in ["baseline_auc_pr", "logistic_regression_auc_pr", "catboost_auc_pr"]:
        values = [f[model_name] for f in results["folds"]]
        results[f"{model_name}_mean"] = float(np.mean(values))
        results[f"{model_name}_std"] = float(np.std(values))

    return results, splits


def train_final_model(df: pd.DataFrame, splits: dict, model_cfg: dict) -> tuple[CatBoostClassifier, dict]:
    """Modele final : entraine sur TOUT sauf le holdout, evalue UNE SEULE
    FOIS sur le holdout (jamais vu ni pendant les folds, ni pendant le
    tuning)."""
    X, y = _prep_X(splits["X"]), splits["y"]
    holdout_idx = splits["holdout_index"]
    train_idx = df.index.difference(holdout_idx)

    X_train, y_train = X.loc[train_idx], y.loc[train_idx]
    X_holdout, y_holdout = X.loc[holdout_idx], y.loc[holdout_idx]

    # petite tranche de validation interne (10% le plus recent du train) pour l'early stopping
    n_val = int(len(train_idx) * 0.1)
    train_sorted = df.loc[train_idx].sort_values("TRANSACTION_DATE").index
    inner_train_idx, inner_val_idx = train_sorted[:-n_val], train_sorted[-n_val:]

    model = train_catboost(
        X.loc[inner_train_idx], y.loc[inner_train_idx],
        X.loc[inner_val_idx], y.loc[inner_val_idx],
        model_cfg["catboost"],
    )

    holdout_scores = model.predict_proba(X_holdout)[:, 1]
    holdout_eval = evaluate_predictions(y_holdout, holdout_scores)
    return model, holdout_eval


def main() -> None:
    model_cfg = load_model_config()
    set_global_seed(model_cfg.get("random_seed", 42))

    df = load_feature_matrix()

    print("=== Validation croisee temporelle (3 folds) ===")
    cv_results, splits = run_cross_validation(df, model_cfg)
    print(f"\nMoyenne CatBoost AUC-PR : {cv_results['catboost_auc_pr_mean']:.4f} "
          f"(+/- {cv_results['catboost_auc_pr_std']:.4f})")
    print(f"Moyenne baseline AUC-PR : {cv_results['baseline_auc_pr_mean']:.4f}")
    print(f"Moyenne LR AUC-PR : {cv_results['logistic_regression_auc_pr_mean']:.4f}")

    print("\n=== Modele final (entraine sur tout sauf holdout) ===")
    final_model, holdout_eval = train_final_model(df, splits, model_cfg)
    print(f"AUC-PR sur le holdout final (jamais vu) : {holdout_eval['auc_pr']:.4f}")
    print(f"Nombre de cas positifs dans le holdout : {holdout_eval['n_positifs_reels']}")

    Path("models").mkdir(exist_ok=True)
    final_model.save_model("models/catboost_v1.cbm")

    Path("outputs/reports").mkdir(parents=True, exist_ok=True)
    with open("outputs/reports/training_metrics.json", "w", encoding="utf-8") as f:
        json.dump({"cross_validation": cv_results, "holdout_evaluation": holdout_eval}, f, indent=2, default=str)

    print("\nModele sauvegarde dans models/catboost_v1.cbm")
    print("Metriques ecrites dans outputs/reports/training_metrics.json")


if __name__ == "__main__":
    main()
