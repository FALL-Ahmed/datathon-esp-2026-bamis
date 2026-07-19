"""
Genere les 3 livrables obligatoires du cahier des charges. Point de sortie
unique du pipeline -- toute la logique metier vit en amont (modeling/,
scoring/, budget/), ce module ne fait que renommer/formater/serialiser.

FICHIERS GENERES
------------------
1. outputs/submissions/soumission_fraude.csv
   TRANSACTION_CODE, score_fraude (probabilite [0,1])
   -- genere sur data/features/test_predictions.parquet. Aucun fichier de
   test officiel recu a ce jour (voir modeling/predict.py) : ce fichier est
   produit sur l'ensemble des transactions connues, en attendant. Meme
   pipeline reutilisable tel quel des reception d'un fichier de test.
2. outputs/submissions/classement_clients.csv
   client_id, score_risque, score_valeur, segment_risque, segment_valeur,
   top_5_facteurs_risque, top_5_facteurs_valeur, action_recommandee
3. outputs/submissions/consommation_enveloppes.csv
   client_id, service_code, montant_consomme_jour, montant_consomme_mois,
   seuil_jour, seuil_mois, taux_consommation_jour, taux_consommation_mois,
   montant_restant_jour, montant_restant_mois, niveau_alerte
   -- une ligne par (client, service) = etat le plus recent connu (pas
   l'historique complet jour par jour, qui vivrait dans
   data/features/budget_alerts.parquet si besoin de detail).

Usage :
    python -m bamis_fraud.submission.export
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd


def export_fraud_submission(predictions: pd.DataFrame, path: str) -> None:
    out = predictions[["TRANSACTION_CODE", "score_fraude"]].copy()
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(path, index=False)


def export_customer_ranking(scores: pd.DataFrame, path: str) -> None:
    rename = {
        "source_customer_id": "client_id",
        "score_risque": "score_risque",
        "score_valeur": "score_valeur",
        "segment_risque": "segment_risque",
        "segment_valeur": "segment_valeur",
        "explication_risque": "top_5_facteurs_risque",
        "explication_valeur": "top_5_facteurs_valeur",
        "action_recommandee": "action_recommandee",
    }
    out = scores.rename(columns=rename)[list(rename.values())]
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(path, index=False)


def build_budget_snapshot(budget_alerts: pd.DataFrame) -> pd.DataFrame:
    """Une ligne par (client, service) = etat le plus recent connu (pas
    l'historique jour par jour complet)."""
    idx = budget_alerts.groupby(["source_customer_id", "SERVICE_CODE"])["periode_jour"].idxmax()
    return budget_alerts.loc[idx]


def export_budget_consumption(budget_alerts: pd.DataFrame, path: str) -> None:
    snapshot = build_budget_snapshot(budget_alerts)
    rename = {
        "source_customer_id": "client_id",
        "SERVICE_CODE": "service_code",
        "montant_consomme_jour": "montant_consomme_jour",
        "montant_consomme_mois": "montant_consomme_mois",
        "SEUIL_CUMUL_JOURNALIER_MRU": "seuil_jour",
        "seuil_cumul_mensuel_estime": "seuil_mois",
        "taux_consommation_jour": "taux_consommation_jour",
        "taux_consommation_mois": "taux_consommation_mois",
        "montant_restant_jour": "montant_restant_jour",
        "montant_restant_mois": "montant_restant_mois",
        "niveau_alerte": "niveau_alerte",
    }
    out = snapshot.rename(columns=rename)[list(rename.values())]
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(path, index=False)


def validate_submission_format(path: str, expected_columns: list[str]) -> dict:
    df = pd.read_csv(path, nrows=5)
    missing = [c for c in expected_columns if c not in df.columns]
    extra = [c for c in df.columns if c not in expected_columns]
    n_rows = sum(1 for _ in open(path, encoding="utf-8")) - 1
    return {
        "path": path,
        "passed": len(missing) == 0,
        "missing_columns": missing,
        "extra_columns": extra,
        "n_rows": n_rows,
    }


def main() -> None:
    out_dir = Path("outputs/submissions")

    predictions = pd.read_parquet("data/features/test_predictions.parquet")
    export_fraud_submission(predictions, str(out_dir / "soumission_fraude.csv"))

    scores = pd.read_parquet("data/features/customer_risk_value_scores.parquet")
    export_customer_ranking(scores, str(out_dir / "classement_clients.csv"))

    budget_alerts = pd.read_parquet("data/features/budget_alerts.parquet")
    export_budget_consumption(budget_alerts, str(out_dir / "consommation_enveloppes.csv"))

    checks = [
        validate_submission_format(str(out_dir / "soumission_fraude.csv"), ["TRANSACTION_CODE", "score_fraude"]),
        validate_submission_format(
            str(out_dir / "classement_clients.csv"),
            ["client_id", "score_risque", "score_valeur", "segment_risque", "segment_valeur",
             "top_5_facteurs_risque", "top_5_facteurs_valeur", "action_recommandee"],
        ),
        validate_submission_format(
            str(out_dir / "consommation_enveloppes.csv"),
            ["client_id", "service_code", "montant_consomme_jour", "montant_consomme_mois",
             "seuil_jour", "seuil_mois", "taux_consommation_jour", "taux_consommation_mois",
             "montant_restant_jour", "montant_restant_mois", "niveau_alerte"],
        ),
    ]

    for c in checks:
        status = "OK" if c["passed"] else "ECHEC"
        print(f"[{status}] {c['path']} -- {c['n_rows']:,} lignes"
              + (f" -- colonnes manquantes: {c['missing_columns']}" if c["missing_columns"] else ""))


if __name__ == "__main__":
    main()
