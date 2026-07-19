"""
Construit le graphe transactionnel : noeuds = telephones (SOURCE_PHONE /
DESTINATION_PHONE -- identifiant client stable, cf.
preprocessing/customer_resolution.py, aucun identifiant client independant
n'etant fiable dans ce fichier), aretes = transactions (montant,
horodatage, code transaction).

Le cahier des charges est explicite : "les schemas C-02 a C-06 et C-09 sont
invisibles si l'on regarde les transactions une par une" -- ce module est
le prealable a toute detection de mule/chaine/circuit reelle (niveau 3),
au-dela des approximations tabulaires deja construites dans
feature_engineering/network_features.py (niveau 1-2).

Seules les transactions avec un DESTINATION_PHONE renseigne forment une
arete exploitable (~95,7% des lignes, cf. audit -- les sorties GIMTEL sans
correspondant identifie ou les transactions sans destinataire ne peuvent
pas etre representees comme un lien entre deux comptes).

Usage :
    python -m bamis_fraud.graph.graph_builder
"""
from __future__ import annotations

from pathlib import Path

import networkx as nx
import pandas as pd


def build_edgelist(
    transactions_path: str = "data/processed/transactions_clean.parquet",
) -> pd.DataFrame:
    df = pd.read_parquet(
        transactions_path,
        columns=["TRANSACTION_CODE", "SOURCE_PHONE", "DESTINATION_PHONE", "TRANSACTION_DATE",
                  "TRANSACTION_AMOUNT", "is_validated"],
    )
    df = df[(df["DESTINATION_PHONE"] != "") & df["is_validated"]].copy()
    df = df.sort_values("TRANSACTION_DATE").reset_index(drop=True)
    return df[["TRANSACTION_CODE", "SOURCE_PHONE", "DESTINATION_PHONE", "TRANSACTION_DATE", "TRANSACTION_AMOUNT"]]


def build_directed_graph(edgelist: pd.DataFrame) -> nx.MultiDiGraph:
    """MultiDiGraph (pas DiGraph) : plusieurs transactions entre les memes
    deux comptes doivent rester des aretes distinctes (chacune avec sa
    propre date/montant), pas fusionnees en une seule."""
    g = nx.MultiDiGraph()
    edges = [
        (row.SOURCE_PHONE, row.DESTINATION_PHONE, {
            "transaction_code": row.TRANSACTION_CODE,
            "date": row.TRANSACTION_DATE,
            "amount": row.TRANSACTION_AMOUNT,
        })
        for row in edgelist.itertuples()
    ]
    g.add_edges_from(edges)
    return g


def main() -> None:
    import time

    t0 = time.time()
    edgelist = build_edgelist()
    print(f"Edgelist construite : {len(edgelist):,} aretes en {time.time()-t0:.1f}s")

    out_path = Path("data/graph/edgelist.parquet")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    edgelist.to_parquet(out_path, index=False)
    print(f"Ecrit dans {out_path}")

    t0 = time.time()
    g = build_directed_graph(edgelist)
    print(f"Graphe construit en {time.time()-t0:.1f}s : "
          f"{g.number_of_nodes():,} noeuds, {g.number_of_edges():,} aretes")


if __name__ == "__main__":
    main()
