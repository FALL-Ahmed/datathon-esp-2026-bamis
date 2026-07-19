"""
Verifie la detection de mule (graph/mule_detection.py) sur un petit graphe
synthetique construit a la main : un compte A->B->A (circuit ferme) et un
compte B qui recoit puis renvoie 95% du montant en moins de 10 minutes
(mule) doivent etre correctement flagges, un compte marchand recevant de
50 comptes differents sans renvoyer d'argent (faux positif potentiel) ne
doit PAS etre flague comme mule.
"""
from __future__ import annotations

import pandas as pd

from bamis_fraud.graph.mule_detection import compute_mule_scores
from bamis_fraud.graph.pattern_detection import detect_closed_circuits


def test_repeated_passthrough_scores_higher_than_one_off_event(tmp_path):
    """La docstring du module insiste : un mule score doit recompenser la
    REPETITION (n_quick_passthrough), pas juste un ratio ponctuel -- un
    salarie qui recoit sa paie et paie son loyer le meme jour, une seule
    fois, ne doit pas peser autant qu'un compte qui le fait 10 fois."""
    rows = []
    # MULE1 : 5 evenements de pass-through rapide repete (ratio ~1.0, delai court)
    for _ in range(5):
        rows.append({
            "source_customer_id": "MULE1",
            "ratio_montant_recu_envoye_past": 0.95,
            "delai_depuis_derniere_reception_minutes": 5,
        })
    # SALARY1 : un seul evenement de meme profil (paie -> loyer, une fois)
    rows.append({
        "source_customer_id": "SALARY1",
        "ratio_montant_recu_envoye_past": 0.95,
        "delai_depuis_derniere_reception_minutes": 5,
    })
    # MERCHANT1 : recoit beaucoup, ne renvoie presque rien (ratio hors bande) -> jamais passthrough
    for _ in range(10):
        rows.append({
            "source_customer_id": "MERCHANT1",
            "ratio_montant_recu_envoye_past": 0.05,
            "delai_depuis_derniere_reception_minutes": 5,
        })

    nf_path = tmp_path / "network_features_light.parquet"
    pd.DataFrame(rows).to_parquet(nf_path)

    scores = compute_mule_scores(str(nf_path)).set_index("phone")

    assert scores.loc["MULE1", "n_quick_passthrough"] == 5
    assert scores.loc["SALARY1", "n_quick_passthrough"] == 1
    assert scores.loc["MERCHANT1", "n_quick_passthrough"] == 0

    # le score du mule repete doit largement depasser celui de l'evenement isole,
    # meme si les deux ont un taux de passthrough de 100% sur leurs occurrences
    assert scores.loc["MULE1", "mule_score"] > scores.loc["SALARY1", "mule_score"]
    # le marchand, jamais en bande de passthrough, ne doit avoir aucun score
    assert scores.loc["MERCHANT1", "mule_score"] == 0


def test_closed_circuit_A_to_B_to_A_is_detected():
    """Circuit ferme C-06 : A envoie a B, B renvoie a A dans le delai max."""
    edgelist = pd.DataFrame({
        "TRANSACTION_CODE": [1, 2, 3],
        "SOURCE_PHONE": ["A", "B", "C"],
        "DESTINATION_PHONE": ["B", "A", "D"],
        "TRANSACTION_DATE": pd.to_datetime([
            "2026-01-01 10:00:00", "2026-01-01 10:05:00", "2026-01-01 10:00:00",
        ]),
        "TRANSACTION_AMOUNT": [10000.0, 10000.0, 5000.0],
    })

    circuits = detect_closed_circuits(edgelist, max_delay="7d")

    # le couple A<->B doit etre detecte comme circuit ferme
    pairs = set(zip(circuits["compte_A"], circuits["compte_B"]))
    assert ("A", "B") in pairs
    # C->D est a sens unique (pas de retour) : ne doit jamais apparaitre
    assert not any("C" in p or "D" in p for p in pairs)


def test_closed_circuit_beyond_max_delay_is_not_detected():
    """Un aller-retour au-dela du delai max n'est pas un circuit ferme
    plausible (voir docstring detect_closed_circuits)."""
    edgelist = pd.DataFrame({
        "TRANSACTION_CODE": [1, 2],
        "SOURCE_PHONE": ["A", "B"],
        "DESTINATION_PHONE": ["B", "A"],
        "TRANSACTION_DATE": pd.to_datetime(["2026-01-01 10:00:00", "2026-02-01 10:00:00"]),
        "TRANSACTION_AMOUNT": [10000.0, 10000.0],
    })

    circuits = detect_closed_circuits(edgelist, max_delay="7d")

    assert len(circuits) == 0
