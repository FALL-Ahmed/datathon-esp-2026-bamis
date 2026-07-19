"""
Detection de schemas de reseau via le graphe reel (pas une approximation
tabulaire) : fan-in (C-03), fan-out (C-04), circuits fermes courts (C-06).

PERIMETRE VOLONTAIREMENT LIMITE (voir ARCHITECTURE.md section 11,
priorites) : les chaines de rebond a 3+ sauts (C-05) et le fractionnement
multi-comptes (C-10) sont explicitement ABANDONNES dans ce premier passage
-- la jointure temporelle necessaire pour les chaines (edgelist x edgelist
avec contrainte d'ordre croissant) est bien plus couteuse et le gain
marginal est plus faible que fan-in/fan-out (qui sont un simple calcul de
degre) et les circuits courts (qui se detectent avec un seul self-join
borne). A ajouter si le temps le permet apres avoir securise le reste.

LOGIQUE
-------
- fan-in / fan-out : nombre d'EXPEDITEURS/DESTINATAIRES DISTINCTS par
  compte sur l'ensemble de la periode -- calcul de degre, vectorise via
  groupby (pas de parcours de graphe noeud par noeud, trop lent a cette
  echelle).
- circuits fermes (longueur 2 uniquement, A->B puis B->A) : self-join de
  l'edgelist sur (source,destination) <-> (destination,source), filtre par
  delai maximum configurable. Un "boomerang" simple, pas la detection
  generale de cycles de longueur arbitraire (NP-difficile a grande echelle,
  hors de portee en 2 jours).

Usage :
    python -m bamis_fraud.graph.pattern_detection
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import yaml


def load_pattern_config(config_path: str = "configs/config.yaml") -> dict:
    with open(config_path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    return cfg.get("graph", {})


def detect_fan_in(edgelist: pd.DataFrame, top_n: int | None = None) -> pd.DataFrame:
    fan_in = (
        edgelist.groupby("DESTINATION_PHONE", observed=True)["SOURCE_PHONE"]
        .nunique()
        .reset_index()
        .rename(columns={"DESTINATION_PHONE": "phone", "SOURCE_PHONE": "n_expediteurs_distincts"})
        .sort_values("n_expediteurs_distincts", ascending=False)
    )
    return fan_in.head(top_n) if top_n else fan_in


def detect_fan_out(edgelist: pd.DataFrame, top_n: int | None = None) -> pd.DataFrame:
    fan_out = (
        edgelist.groupby("SOURCE_PHONE", observed=True)["DESTINATION_PHONE"]
        .nunique()
        .reset_index()
        .rename(columns={"SOURCE_PHONE": "phone", "DESTINATION_PHONE": "n_destinataires_distincts"})
        .sort_values("n_destinataires_distincts", ascending=False)
    )
    return fan_out.head(top_n) if top_n else fan_out


def detect_closed_circuits(
    edgelist: pd.DataFrame, max_delay: str = "7d", max_transactions_per_pair: int = 50
) -> pd.DataFrame:
    """A envoie a B, B renvoie a A dans le delai max -- circuit ferme de
    longueur 2 (le "boomerang" du cahier des charges).

    IMPLEMENTATION : merge_asof (correspondance au plus proche dans le
    temps, by=paire de comptes) plutot qu'un self-join classique. Un
    self-join sur (source,dest)<->(dest,source) produit un PRODUIT CROISE
    pour chaque paire -- teste en premier, a fait planter le process par
    manque de memoire a cause de quelques paires agent/hub avec des
    milliers de transactions entre elles (ex. 10584 transactions pour une
    seule paire). merge_asof est O(n log n), jamais de produit croise.

    max_transactions_per_pair exclut ces paires extremes AVANT le calcul :
    une paire avec des milliers d'allers-retours est une relation
    commerciale routiniere (agent <-> compte d'equilibrage), pas un
    candidat plausible de circuit de fraude -- un vrai C-06 implique
    typiquement une poignee de transactions, pas un flux continu."""
    max_delay_td = pd.Timedelta(max_delay)
    cols = ["TRANSACTION_CODE", "SOURCE_PHONE", "DESTINATION_PHONE", "TRANSACTION_DATE", "TRANSACTION_AMOUNT"]
    e = edgelist[cols].copy()

    pair_counts = e.groupby(["SOURCE_PHONE", "DESTINATION_PHONE"]).size()
    safe_pairs = pair_counts[pair_counts <= max_transactions_per_pair].index
    e = e.set_index(["SOURCE_PHONE", "DESTINATION_PHONE"]).loc[safe_pairs].reset_index()

    # paire non ordonnee (cle commune aux deux sens A->B et B->A)
    e["paire"] = [tuple(sorted((s, d))) for s, d in zip(e["SOURCE_PHONE"], e["DESTINATION_PHONE"])]

    aller = e.sort_values("TRANSACTION_DATE").reset_index(drop=True)
    retour = e.sort_values("TRANSACTION_DATE").reset_index(drop=True)
    # merge_asof ne suffixe jamais la colonne 'on' -- on garde une copie de
    # la date du retour sous un autre nom pour pouvoir calculer le delai apres coup
    retour["TRANSACTION_DATE_retour_copy"] = retour["TRANSACTION_DATE"]

    matched = pd.merge_asof(
        aller,
        retour,
        on="TRANSACTION_DATE",
        by="paire",
        direction="forward",
        tolerance=max_delay_td,
        suffixes=("_aller", "_retour"),
        allow_exact_matches=False,
    )
    # ne garder que les vrais aller-retour : sens oppose, match trouve
    matched = matched.dropna(subset=["TRANSACTION_CODE_retour"])
    matched = matched[matched["SOURCE_PHONE_aller"] != matched["SOURCE_PHONE_retour"]]
    matched["delai"] = matched["TRANSACTION_DATE_retour_copy"] - matched["TRANSACTION_DATE"]

    result = matched[
        ["SOURCE_PHONE_aller", "DESTINATION_PHONE_aller", "TRANSACTION_CODE_aller", "TRANSACTION_CODE_retour",
         "TRANSACTION_AMOUNT_aller", "TRANSACTION_AMOUNT_retour", "delai"]
    ].rename(columns={"SOURCE_PHONE_aller": "compte_A", "DESTINATION_PHONE_aller": "compte_B"})
    return result.drop_duplicates(subset=["TRANSACTION_CODE_aller", "TRANSACTION_CODE_retour"])


def main() -> None:
    import time

    cfg = load_pattern_config()
    edgelist = pd.read_parquet("data/graph/edgelist.parquet")

    fan_in = detect_fan_in(edgelist, top_n=cfg.get("fan_in_top_n", 200))
    fan_out = detect_fan_out(edgelist, top_n=cfg.get("fan_out_top_n", 200))

    t0 = time.time()
    circuits = detect_closed_circuits(edgelist, max_delay=cfg.get("closed_circuit_max_delay", "7d"))
    print(f"Circuits fermes detectes en {time.time()-t0:.1f}s")

    out_dir = Path("data/graph")
    fan_in.to_parquet(out_dir / "fan_in.parquet", index=False)
    fan_out.to_parquet(out_dir / "fan_out.parquet", index=False)
    circuits.to_parquet(out_dir / "closed_circuits.parquet", index=False)

    print(f"\nFan-in (top 5) :\n{fan_in.head(5).to_string(index=False)}")
    print(f"\nFan-out (top 5) :\n{fan_out.head(5).to_string(index=False)}")
    print(f"\n{len(circuits):,} circuits fermes (A->B->A) trouves, delai <= {cfg.get('closed_circuit_max_delay', '7d')}")
    if len(circuits):
        print(circuits.sort_values("delai").head(5).to_string(index=False))


if __name__ == "__main__":
    main()
