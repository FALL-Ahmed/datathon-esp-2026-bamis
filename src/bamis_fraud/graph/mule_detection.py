"""
Detection specifique C-02 (compte mule / pass-through) : un compte recoit
puis renvoie presque immediatement une part importante du montant recu, de
maniere REPETEE (pas un cas isole -- un salarie qui reçoit sa paie et paie
son loyer le meme jour ne doit pas etre traite comme une mule sur la base
d'un seul evenement).

METHODE : reutilise les colonnes deja calculees par
feature_engineering/network_features.py (ratio_montant_recu_envoye_past,
delai_depuis_derniere_reception_minutes -- calculees par transaction, de
maniere causale) plutot que de refaire l'appariement depuis zero. Ce module
les AGREGE par compte pour produire un vrai score de mule au niveau du
compte, avec une exigence de repetition (n_quick_passthrough) qui manque
a l'approximation transaction-par-transaction de niveau 1-2.

mule_score = taux de pass-through rapide x log(1 + nb d'occurrences) --
un compte avec 1 seul evenement de pass-through pese peu, un compte avec
10 evenements recurrents pese beaucoup plus, meme a taux egal.

Usage :
    python -m bamis_fraud.graph.mule_detection
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import yaml

DEFAULT_RATIO_BAND = (0.7, 1.3)
DEFAULT_MAX_DELAY_MINUTES = 30


def load_mule_config(config_path: str = "configs/config.yaml") -> dict:
    path = Path(config_path)
    if not path.exists():
        return {"ratio_band": DEFAULT_RATIO_BAND, "max_delay_minutes": DEFAULT_MAX_DELAY_MINUTES}
    with open(path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    graph_cfg = cfg.get("graph", {})
    return {
        "ratio_band": tuple(graph_cfg.get("mule_ratio_band", DEFAULT_RATIO_BAND)),
        "max_delay_minutes": graph_cfg.get("mule_max_delay_minutes", DEFAULT_MAX_DELAY_MINUTES),
    }


def compute_mule_scores(
    network_features_path: str = "data/features/network_features_light.parquet",
    ratio_band: tuple[float, float] = DEFAULT_RATIO_BAND,
    max_delay_minutes: float = DEFAULT_MAX_DELAY_MINUTES,
) -> pd.DataFrame:
    nf = pd.read_parquet(
        network_features_path,
        columns=["source_customer_id", "ratio_montant_recu_envoye_past", "delai_depuis_derniere_reception_minutes"],
    )
    lo, hi = ratio_band
    nf["is_quick_passthrough"] = nf["ratio_montant_recu_envoye_past"].between(lo, hi) & nf[
        "delai_depuis_derniere_reception_minutes"
    ].between(0, max_delay_minutes)

    agg = nf.groupby("source_customer_id", observed=True).agg(
        n_transactions=("is_quick_passthrough", "size"),
        n_quick_passthrough=("is_quick_passthrough", "sum"),
        median_delay_minutes_all=("delai_depuis_derniere_reception_minutes", "median"),
    ).reset_index()

    agg["passthrough_rate"] = agg["n_quick_passthrough"] / agg["n_transactions"]
    agg["mule_score"] = agg["passthrough_rate"] * np.log1p(agg["n_quick_passthrough"])
    agg = agg.rename(columns={"source_customer_id": "phone"})
    return agg.sort_values("mule_score", ascending=False)


def main() -> None:
    cfg = load_mule_config()
    scores = compute_mule_scores(ratio_band=cfg["ratio_band"], max_delay_minutes=cfg["max_delay_minutes"])

    out_path = Path("data/graph/mule_scores.parquet")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    scores.to_parquet(out_path, index=False)

    print(f"{len(scores):,} comptes scores, ecrit dans {out_path}")
    top = scores[scores["n_quick_passthrough"] >= 3].head(10)
    print(f"\nComptes avec au moins 3 evenements de pass-through rapide repete (top 10 par score) :")
    print(top[["phone", "n_transactions", "n_quick_passthrough", "passthrough_rate", "mule_score"]].to_string(index=False))


if __name__ == "__main__":
    main()
