"""
Implemente la regle non negociable du cahier des charges : "entrainez sur
le passe, testez sur la periode recente. Jamais de decoupage aleatoire."

STRATEGIE : validation temporelle glissante (walk-forward) a n_folds replis,
avec un EMBARGO entre train et validation (par defaut 7 jours, la plus
longue fenetre de feature utilisee -- velocity_features va jusqu'a 7j) pour
eviter qu'une fenetre glissante calculee pres de la frontiere ne "voit"
indirectement des transactions d'entrainement trop proches. Le dernier
holdout_fraction de la chronologie est reserve en TEST FINAL, jamais vu
pendant le tuning des folds.

    Temps  ────────────────────────────────────────────────►
           [ train F1 ][emb][val F1]
           [   train F2    ][emb][val F2]
           [      train F3      ][emb][val F3]
           [           train complet          ][emb][ TEST FINAL ]

Calibre sur la plage reelle du fichier (juin 2022 -> juillet 2026, cf.
ARCHITECTURE.md section 6) via configs/config.yaml -> validation.

Usage :
    python -m bamis_fraud.validation.temporal_split
"""
from __future__ import annotations

import pandas as pd
import yaml


def load_validation_config(config_path: str = "configs/config.yaml") -> dict:
    with open(config_path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    return cfg["validation"]


def make_rolling_time_splits(
    df: pd.DataFrame,
    date_col: str = "TRANSACTION_DATE",
    n_folds: int = 3,
    embargo: str = "7d",
    holdout_fraction: float = 0.15,
) -> dict:
    """Retourne un dict avec :
    - 'folds' : liste de n_folds tuples (train_index, valid_index)
    - 'holdout_index' : index du test final, jamais utilise pour le tuning
    - 'boundaries' : les dates de coupure, pour verification/log
    """
    dates = df[date_col]
    embargo_td = pd.Timedelta(embargo)
    min_date, max_date = dates.min(), dates.max()
    total_span = max_date - min_date

    holdout_start = max_date - total_span * holdout_fraction
    trainable_span = holdout_start - min_date
    chunk = trainable_span / (n_folds + 1)

    folds = []
    boundaries = []
    for i in range(1, n_folds + 1):
        val_start = min_date + chunk * i
        val_end = min_date + chunk * (i + 1)
        train_end = val_start - embargo_td

        train_mask = dates < train_end
        val_mask = (dates >= val_start) & (dates < val_end)

        train_index = df.index[train_mask]
        valid_index = df.index[val_mask]
        folds.append((train_index, valid_index))
        boundaries.append(
            {"fold": i, "train_end": train_end, "val_start": val_start, "val_end": val_end}
        )

    holdout_index = df.index[dates >= holdout_start]

    return {"folds": folds, "holdout_index": holdout_index, "boundaries": boundaries, "holdout_start": holdout_start}


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default="data/features/feature_matrix_transactions.parquet")
    parser.add_argument("--config", default="configs/config.yaml")
    args = parser.parse_args()

    df = pd.read_parquet(args.input, columns=["TRANSACTION_CODE", "TRANSACTION_DATE", "pseudo_label_fraud"])
    cfg = load_validation_config(args.config)

    result = make_rolling_time_splits(
        df,
        n_folds=cfg["n_folds"],
        embargo=cfg["embargo"],
        holdout_fraction=cfg["test_holdout_fraction_of_timeline"],
    )

    print(f"Plage totale : {df['TRANSACTION_DATE'].min()} -> {df['TRANSACTION_DATE'].max()}")
    print(f"Debut du holdout final : {result['holdout_start']}")
    print(f"Holdout final : {len(result['holdout_index']):,} lignes, "
          f"{df.loc[result['holdout_index'], 'pseudo_label_fraud'].mean():.3%} de pseudo-fraude\n")

    for (train_idx, valid_idx), b in zip(result["folds"], result["boundaries"]):
        print(f"Fold {b['fold']} : train jusqu'a {b['train_end']} ({len(train_idx):,} lignes) "
              f"-> valid [{b['val_start']} , {b['val_end']}) ({len(valid_idx):,} lignes, "
              f"{df.loc[valid_idx, 'pseudo_label_fraud'].mean():.3%} de pseudo-fraude)")


if __name__ == "__main__":
    main()
