"""
Etape 5/10. Entraine le modele de detection de fraude (volet A, niveau 2) :
validation croisee temporelle a 3 folds, comparaison baseline -> regression
logistique -> CatBoost, entrainement final sur tout sauf le holdout, puis
evaluation AUC-PR sur ce holdout jamais vu (modeling/train.py, qui appelle
lui-meme modeling/evaluate.py). Seed fixee (configs/config.yaml ->
random_seed) pour la reproductibilite.

LIMITE ASSUMEE : pas d'etape de calibration probabiliste separee
(modeling/calibration.py n'est qu'un plan non code, voir
NOTE_METHODOLOGIQUE.md section 8) -- le score produit est une probabilite
brute du modele, non recalibree.

Usage :
    python scripts/05_train_model.py

Sortie : models/catboost_v1.cbm, outputs/reports/training_metrics.json
"""
from __future__ import annotations

import time

from bamis_fraud.modeling.train import main as train_main


def main() -> None:
    t0 = time.time()
    train_main()
    print(f"\nEtape 5 terminee en {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
