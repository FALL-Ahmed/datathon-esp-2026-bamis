"""
Evaluation exclusivement centree sur l'AUC-PR (metrique officielle du
jury) -- l'accuracy n'est calculee qu'a titre indicatif et jamais utilisee
pour selectionner un modele (rappel explicite du cahier des charges : avec
~1% de fraude, l'accuracy est trompeuse -- predire "tout est normal" donne
~99% d'accuracy et 0% de rappel).

METRIQUES CALCULEES
---------------------
- AUC-PR (aire sous la courbe precision-rappel, sklearn average_precision_score)
- Precision / Rappel a plusieurs seuils de decision
- Nombre de faux positifs en absolu (critere "peu de fausses alertes", 15%)

Usage :
    depuis modeling/train.py
"""
from __future__ import annotations

import numpy as np
from sklearn.metrics import average_precision_score, precision_score, recall_score, f1_score


def compute_auc_pr(y_true, y_scores) -> float:
    return float(average_precision_score(y_true, y_scores))


def compute_precision_recall_at_threshold(y_true, y_scores, threshold: float) -> dict:
    y_pred = (np.asarray(y_scores) >= threshold).astype(int)
    y_true = np.asarray(y_true)
    n_positive_pred = int(y_pred.sum())
    n_true_positive = int(((y_pred == 1) & (y_true == 1)).sum())
    n_false_positive = n_positive_pred - n_true_positive
    return {
        "threshold": threshold,
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "f1": float(f1_score(y_true, y_pred, zero_division=0)),
        "n_alertes": n_positive_pred,
        "n_vrais_positifs": n_true_positive,
        "n_faux_positifs": n_false_positive,
    }


def evaluate_predictions(y_true, y_scores, thresholds: list[float] = None) -> dict:
    if thresholds is None:
        thresholds = [0.1, 0.3, 0.5, 0.7, 0.9]
    return {
        "auc_pr": compute_auc_pr(y_true, y_scores),
        "n_examples": len(y_true),
        "n_positifs_reels": int(np.asarray(y_true).sum()),
        "par_seuil": [compute_precision_recall_at_threshold(y_true, y_scores, t) for t in thresholds],
    }
