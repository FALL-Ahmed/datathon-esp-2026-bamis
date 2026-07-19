"""
Extrait les donnees necessaires au tableau de bord et les compacte en un
seul fichier JSON, injecte ensuite dans une page HTML autonome
(dashboard/template.html -> outputs/dashboard_exports/dashboard.html).

Choix delibere : pas de serveur, pas de fetch() -- les donnees sont
EMBARQUEES directement dans le HTML final. La page s'ouvre en double-clic
dans n'importe quel navigateur, sans rien lancer en parallele. C'est le
critere n1 pour une demonstration fiable devant le jury (voir discussion
d'architecture -- risque zero que "ca ne demarre pas").

Le dashboard ne recalcule jamais rien : il lit uniquement les fichiers deja
produits par le pipeline batch (outputs/, data/features/).

Usage :
    python -m bamis_fraud.dashboard.export_data
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import networkx as nx
import numpy as np
import pandas as pd

from bamis_fraud.submission.export import build_budget_snapshot

TOP_N_ALERTS = 150
TOP_N_CUSTOMERS = 150
TOP_N_NOTIFICATIONS = 100
TOP_N_BUDGET = 200

# libelles FR des regles, en langage metier plutot qu'en code (R1, R2...) --
# retour utilisateur 2026-07-20 : "le jury comprend immediatement" avec des
# phrases completes, pas des codes a decoder
RULE_LABELS_FR = {
    "rule_R1_above_unit_threshold": "Dépassement du seuil",
    "rule_R2_above_daily_cumulative": "Dépassement du cumul journalier",
    "rule_R3_fractionnement": "Fractionnement",
    "rule_R4_rafale": "Rafale de transactions",
    "rule_R5_nouveau_beneficiaire_gros_montant": "Nouveau bénéficiaire + montant inhabituel",
    "rule_R6_nocturne_hors_norme": "Activité nocturne inhabituelle",
    "rule_R7_profil_mule": "Profil de compte relais (mule)",
}


def _niveau_alerte(suspicion_score: int) -> dict:
    """Traduit le score de suspicion (0-7 regles) en un niveau d'alerte
    metier avec emoji -- plus parlant que l'affichage brut 'X/7' seul pour
    un jury non technique (retour 2026-07-20)."""
    if suspicion_score >= 4:
        return {"label": "Critique", "emoji": "🔴", "color": "var(--critical)"}
    if suspicion_score == 3:
        return {"label": "Élevé", "emoji": "🟠", "color": "var(--serious)"}
    if suspicion_score == 2:
        return {"label": "Modéré", "emoji": "🟡", "color": "var(--warning)"}
    return {"label": "Faible", "emoji": "🟢", "color": "var(--good)"}


def _score_ia_bucket(score_pct: float | None) -> dict | None:
    """Traduit le score continu du modele (0-100%) en categorie de risque
    lisible ('RISQUE CRITIQUE' etc.) plutot qu'un pourcentage brut seul --
    retour 2026-07-20, l'objectif est qu'un membre du jury comprenne en
    5 secondes sans qu'on ait besoin de l'expliquer."""
    if score_pct is None:
        return None
    if score_pct >= 80:
        return {"label": "RISQUE CRITIQUE", "emoji": "🔴", "color": "var(--critical)"}
    if score_pct >= 50:
        return {"label": "RISQUE ÉLEVÉ", "emoji": "🟠", "color": "var(--serious)"}
    if score_pct >= 20:
        return {"label": "RISQUE MODÉRÉ", "emoji": "🟡", "color": "var(--warning)"}
    return {"label": "RISQUE FAIBLE", "emoji": "🟢", "color": "var(--good)"}


def _confiance(score_pct: float | None) -> str:
    if score_pct is None:
        return "Non disponible"
    conf = score_pct if score_pct >= 50 else 100 - score_pct
    if conf >= 90:
        return "Très élevée"
    if conf >= 70:
        return "Élevée"
    if conf >= 40:
        return "Modérée"
    return "Faible"


DECISION_LABELS = {
    "BLOQUÉE": "Bloquer immédiatement",
    "EN ATTENTE": "Vérifier manuellement",
    "SURVEILLANCE": "Autoriser avec surveillance renforcée",
}


def _load_training_metrics() -> dict | None:
    path = Path("outputs/reports/training_metrics.json")
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def build_dashboard_data() -> dict:
    transactions = pd.read_parquet(
        "data/processed/transactions_clean.parquet",
        columns=["TRANSACTION_CODE", "source_customer_id", "SERVICE_CODE", "TRANSACTION_DATE",
                  "TRANSACTION_AMOUNT", "is_external_gimtel"],
    )
    rules = pd.read_parquet("data/features/rule_flags.parquet")
    scores = pd.read_parquet("data/features/customer_risk_value_scores.parquet")
    budget_alerts = pd.read_parquet("data/features/budget_alerts.parquet")
    ml_scores_path = Path("data/features/test_predictions.parquet")
    ml_scores = pd.read_parquet(ml_scores_path) if ml_scores_path.exists() else None

    n_transactions = len(transactions)
    n_customers = len(scores)
    fraud_rate_pct = round(100 * rules["pseudo_label_fraud"].mean(), 3)

    risk_segments = scores["segment_risque"].value_counts().to_dict()
    value_segments = scores["segment_valeur"].value_counts().to_dict()

    n_budget_alerts = int((budget_alerts["niveau_alerte"] != "Aucune").sum())

    training_metrics = _load_training_metrics()
    auc_pr = None
    if training_metrics:
        auc_pr = training_metrics.get("holdout_evaluation", {}).get("auc_pr")

    # --- population des transactions suspectes (pseudo_label_fraud, >=2
    # regles) -- base commune pour "File d'alertes" (triee par severite,
    # file de priorite) et "Monitoring temps reel" (triee par date, vrai
    # flux chronologique). Les deux vues melangeaient ce role avant :
    # trier uniquement par severite faisait que "temps reel" n'avait rien
    # de temporel, et que seules les transactions BLOQUEE (>=3 regles)
    # apparaissaient jamais (319 transactions a 3-4 regles, deja plus que
    # les 150 places disponibles) -- retour utilisateur 2026-07-20. ---
    alerts_all = rules.merge(transactions, on="TRANSACTION_CODE", how="left")
    if ml_scores is not None:
        alerts_all = alerts_all.merge(ml_scores, on="TRANSACTION_CODE", how="left")
    alerts_all = alerts_all[alerts_all["pseudo_label_fraud"]]

    def _build_alert_entry(row) -> dict:
        entry = {
            "transaction_code": int(row.TRANSACTION_CODE),
            "customer_id": row.source_customer_id,
            "service": row.SERVICE_CODE,
            "date": row.TRANSACTION_DATE.strftime("%Y-%m-%d %H:%M"),
            "amount": float(row.TRANSACTION_AMOUNT),
            "suspicion_score": int(row.rule_suspicion_score),
            "score_ia_pct": (
                round(float(row.score_fraude) * 100, 1)
                if ml_scores is not None and not pd.isna(row.score_fraude) else None
            ),
            "pseudo_label_fraud": bool(row.pseudo_label_fraud),
            "gimtel": bool(row.is_external_gimtel),
            "rules": [
                RULE_LABELS_FR[r]
                for r in RULE_LABELS_FR
                if getattr(row, r)
            ],
            # checklist complete (toutes les regles, pas seulement celles
            # declenchees) pour le panneau d'explicabilite -- affiche les
            # coches ET les croix, comme un vrai "pourquoi" de centre de
            # supervision plutot qu'une simple liste de tags
            "rules_checklist": [
                {"label": label, "triggered": bool(getattr(row, r))}
                for r, label in RULE_LABELS_FR.items()
            ],
            "action": (
                "BLOQUÉE" if row.rule_suspicion_score >= 3
                else "EN ATTENTE" if row.rule_suspicion_score == 2
                else "SURVEILLANCE"
            ),
        }
        entry["niveau_alerte"] = _niveau_alerte(entry["suspicion_score"])
        entry["score_ia_bucket"] = _score_ia_bucket(entry["score_ia_pct"])
        entry["confiance"] = _confiance(entry["score_ia_pct"])
        entry["decision_label"] = DECISION_LABELS[entry["action"]]
        return entry

    # "File d'alertes" : file de priorite, les cas les plus severes d'abord
    top_alerts = [
        _build_alert_entry(row)
        for row in alerts_all.sort_values("rule_suspicion_score", ascending=False).head(TOP_N_ALERTS).itertuples()
    ]

    # "Monitoring temps reel" : vrai flux chronologique, le plus recent
    # d'abord -- melange naturel de niveaux de severite, comme un vrai
    # centre de supervision qui voit passer les evenements dans l'ordre
    live_feed = [
        _build_alert_entry(row)
        for row in alerts_all.sort_values("TRANSACTION_DATE", ascending=False).head(TOP_N_ALERTS).itertuples()
    ]

    # --- intensite fraude par service x heure (volet monitoring) -- utilise
    # SERVICE_CODE et TRANSACTION_DATE, les deux seules colonnes de contexte
    # transactionnel totalement fiables (pas de region/agence dans le fichier
    # source, verifie dans configs/schema_map.yaml -- pas de heatmap
    # geographique inventee sur une hypothese non confirmee) ---
    rules_tx = rules[["TRANSACTION_CODE", "pseudo_label_fraud"]].merge(
        transactions[["TRANSACTION_CODE", "SERVICE_CODE", "TRANSACTION_DATE"]],
        on="TRANSACTION_CODE", how="left",
    )
    rules_tx["heure"] = rules_tx["TRANSACTION_DATE"].dt.hour
    # tous les services (12 au total dans les vraies donnees, SERVICE_01 a
    # SERVICE_12) -- limiter aux "top 6" les plus frequents etait arbitraire
    # et masquait des services reels sans raison (retour utilisateur 2026-07-20)
    top_services = sorted(rules_tx["SERVICE_CODE"].dropna().unique().tolist())
    hm = rules_tx[rules_tx["SERVICE_CODE"].isin(top_services)]
    heatmap_grid = (
        hm.groupby(["SERVICE_CODE", "heure"], observed=True)
        .agg(n=("TRANSACTION_CODE", "size"), n_fraud=("pseudo_label_fraud", "sum"))
        .reset_index()
    )
    heatmap_grid["fraud_rate"] = heatmap_grid["n_fraud"] / heatmap_grid["n"]
    heatmap = {
        "services": top_services,
        "cells": [
            {
                "service": row.SERVICE_CODE,
                "heure": int(row.heure),
                "n": int(row.n),
                "fraud_rate": round(float(row.fraud_rate), 4),
            }
            for row in heatmap_grid.itertuples()
        ],
    }

    # --- tendance mensuelle (volume + taux de fraude) -- vue d'ensemble sur
    # toute la periode observee (juin 2022 -> juillet 2026) ---
    rules_tx["mois"] = rules_tx["TRANSACTION_DATE"].dt.to_period("M").astype(str)
    trend_grid = (
        rules_tx.groupby("mois", observed=True)
        .agg(n=("TRANSACTION_CODE", "size"), n_fraud=("pseudo_label_fraud", "sum"))
        .reset_index()
        .sort_values("mois")
    )
    trend_grid["fraud_rate"] = trend_grid["n_fraud"] / trend_grid["n"]
    trends = [
        {"mois": row.mois, "n": int(row.n), "fraud_rate": round(float(row.fraud_rate), 4)}
        for row in trend_grid.itertuples()
    ]

    # --- reseau de comptes suspects (mules + comptes impliques dans des
    # circuits fermes) -- sous-graphe borne (<= 40 comptes "graines") pour
    # rester exploitable dans un rendu SVG navigateur ; layout precalcule en
    # Python (networkx spring_layout) plutot qu'une simulation physique JS,
    # plus fiable pour une demo live ---
    mule_scores = pd.read_parquet("data/graph/mule_scores.parquet")
    circuits = pd.read_parquet(
        "data/graph/closed_circuits.parquet",
        columns=["compte_A", "compte_B", "TRANSACTION_AMOUNT_aller"],
    )
    edgelist = pd.read_parquet(
        "data/graph/edgelist.parquet", columns=["SOURCE_PHONE", "DESTINATION_PHONE"]
    )

    # echantillon revu le 2026-07-20 v2 : la version precedente (20 mules +
    # comptes de circuits choisis INDEPENDAMMENT les uns des autres) donnait
    # un graphe majoritairement compose de points isoles -- rien ne dit
    # qu'un compte mule choisi par son mule_score a deja transige avec un
    # AUTRE mule ou un compte de circuit du meme sous-echantillon. Resultat :
    # "hyper melange", des dizaines d'etiquettes qui se chevauchent sur des
    # points sans aucune arete. Corrige en construisant un vrai ego-network :
    # pour chaque mule retenu, on ajoute ses vraies contreparties de
    # transaction (jusqu'a 2, les plus frequentes) -- ca montre le motif
    # fan-in/fan-out qui definit justement un compte mule, plutot qu'un
    # point seul sans contexte. Les circuits restent des paires COMPLETES
    # (compte_A + compte_B) pour rester des boucles fermees reconnaissables.
    # Tout noeud qui reste isole (degre 0) apres construction du sous-graphe
    # est ensuite retire -- un point sans arete n'apporte rien et encombre.
    top_mules = set(
        mule_scores[mule_scores["n_quick_passthrough"] >= 3]
        .sort_values("mule_score", ascending=False)
        .head(8)["phone"]
    )
    mule_edges = edgelist[
        edgelist["SOURCE_PHONE"].isin(top_mules) | edgelist["DESTINATION_PHONE"].isin(top_mules)
    ]
    mule_neighbors: set = set()
    for mule in top_mules:
        counterparties = pd.concat([
            mule_edges.loc[mule_edges["SOURCE_PHONE"] == mule, "DESTINATION_PHONE"],
            mule_edges.loc[mule_edges["DESTINATION_PHONE"] == mule, "SOURCE_PHONE"],
        ]).value_counts().head(2).index
        mule_neighbors.update(counterparties)
    mule_neighbors -= top_mules

    top_circuit_pairs = circuits.sort_values("TRANSACTION_AMOUNT_aller", ascending=False).head(6)
    circuit_accounts = set(top_circuit_pairs["compte_A"]) | set(top_circuit_pairs["compte_B"])

    seed_nodes = list(top_mules | mule_neighbors | circuit_accounts)
    seed_set = set(seed_nodes)

    sub_edges = edgelist[
        edgelist["SOURCE_PHONE"].isin(seed_set) & edgelist["DESTINATION_PHONE"].isin(seed_set)
        & (edgelist["SOURCE_PHONE"] != edgelist["DESTINATION_PHONE"])
    ]
    sub_edges_agg = (
        sub_edges.groupby(["SOURCE_PHONE", "DESTINATION_PHONE"], observed=True)
        .size().reset_index(name="n").head(300)
    )

    graph_g = nx.DiGraph()
    graph_g.add_nodes_from(seed_nodes)
    graph_g.add_edges_from(zip(sub_edges_agg["SOURCE_PHONE"], sub_edges_agg["DESTINATION_PHONE"]))

    connected_nodes = [n for n in seed_nodes if graph_g.degree(n) > 0]
    graph_g = graph_g.subgraph(connected_nodes).copy()
    seed_nodes = connected_nodes
    pos = nx.spring_layout(graph_g, seed=42, k=1.8 / max(1, len(connected_nodes)) ** 0.5)

    mule_score_by_id = mule_scores.set_index("phone")["mule_score"].to_dict()
    network_graph = {
        "nodes": [
            {
                "id": node_id,
                "x": round(float(pos[node_id][0]), 4),
                "y": round(float(pos[node_id][1]), 4),
                "is_mule": node_id in top_mules,
                "in_circuit": node_id in circuit_accounts,
                "mule_score": round(float(mule_score_by_id.get(node_id, 0.0)), 3),
                "degree": int(graph_g.degree(node_id)),
            }
            for node_id in seed_nodes
        ],
        "edges": [
            {"source": row.SOURCE_PHONE, "target": row.DESTINATION_PHONE, "n": int(row.n)}
            for row in sub_edges_agg.itertuples()
        ],
    }

    # --- notifications : depassements de seuil budgetaire (volet B), jamais
    # affiches nulle part avant -- seul un compteur KPI existait. On expose
    # ici le flux reel (client, service, seuil franchi, montant), classe par
    # severite puis par date, pour servir de vraie cloche de notifications. ---
    severity_order = {"100%": 3, "95%": 2, "80%": 1, "50%": 0}
    active_alerts = budget_alerts[budget_alerts["niveau_alerte"] != "Aucune"].copy()
    active_alerts["_severity_rank"] = active_alerts["niveau_alerte"].map(severity_order).fillna(-1)
    active_alerts = active_alerts.sort_values(
        ["_severity_rank", "periode_jour"], ascending=[False, False]
    ).head(TOP_N_NOTIFICATIONS)
    notifications = [
        {
            "customer_id": row.source_customer_id,
            "service": row.SERVICE_CODE,
            "niveau_alerte": row.niveau_alerte,
            "taux_jour": round(float(row.taux_consommation_jour) * 100, 1),
            "taux_mois": round(float(row.taux_consommation_mois) * 100, 1),
            "montant_consomme_jour": float(row.montant_consomme_jour),
            "date": str(row.periode_jour),
        }
        for row in active_alerts.itertuples()
    ]
    n_critical_notifications = int((budget_alerts["niveau_alerte"] == "100%").sum())

    # --- volet B, page dediee : etat ACTUEL de consommation par client x
    # service (une ligne par combinaison, pas l'historique jour par jour --
    # meme logique que le livrable officiel consommation_enveloppes.csv,
    # reutilisee via build_budget_snapshot pour ne jamais avoir deux calculs
    # differents du meme etat). Absent du dashboard jusqu'ici -- retour
    # utilisateur 2026-07-20 : "le volet B n'a pas sa page". ---
    budget_snapshot = build_budget_snapshot(budget_alerts)
    n_combinaisons = len(budget_snapshot)
    n_over_daily = int((budget_snapshot["taux_consommation_jour"] > 1).sum())
    n_over_monthly = int((budget_snapshot["taux_consommation_mois"] > 1).sum())
    n_at_100 = int((budget_snapshot["niveau_alerte"] == "100%").sum())

    budget_snapshot = budget_snapshot.copy()
    budget_snapshot["_taux_max"] = budget_snapshot[["taux_consommation_jour", "taux_consommation_mois"]].max(axis=1)
    budget_table_df = budget_snapshot.sort_values("_taux_max", ascending=False).head(TOP_N_BUDGET)
    budget_table = [
        {
            "customer_id": row.source_customer_id,
            "service": row.SERVICE_CODE,
            "montant_jour": float(row.montant_consomme_jour),
            "seuil_jour": float(row.SEUIL_CUMUL_JOURNALIER_MRU),
            "taux_jour": round(float(row.taux_consommation_jour) * 100, 1),
            "reste_jour": float(row.montant_restant_jour),
            "montant_mois": float(row.montant_consomme_mois),
            "seuil_mois": float(row.seuil_cumul_mensuel_estime),
            "taux_mois": round(float(row.taux_consommation_mois) * 100, 1),
            "reste_mois": float(row.montant_restant_mois),
            "niveau_alerte": row.niveau_alerte,
            "date": str(row.periode_jour),
        }
        for row in budget_table_df.itertuples()
    ]

    # --- fiches client : top clients par score de risque, + tout client cite
    # dans une notification (sinon un clic sur une notification tombe sur un
    # client absent du top 150 -- "Aucun client ne correspond aux filtres",
    # cul-de-sac constate en demo 2026-07-19) ---
    top_customers_df = scores.sort_values("score_risque", ascending=False).head(TOP_N_CUSTOMERS)
    notif_customer_ids = {n["customer_id"] for n in notifications}
    missing_ids = notif_customer_ids - set(top_customers_df["source_customer_id"])
    if missing_ids:
        extra_df = scores[scores["source_customer_id"].isin(missing_ids)]
        top_customers_df = pd.concat([top_customers_df, extra_df], ignore_index=True)
    top_customers = [
        {
            "customer_id": row.source_customer_id,
            "score_risque": int(row.score_risque),
            "score_valeur": int(row.score_valeur),
            "segment_risque": row.segment_risque,
            "segment_valeur": row.segment_valeur,
            "action_recommandee": row.action_recommandee,
            "explication_risque": row.explication_risque,
            "explication_valeur": row.explication_valeur,
        }
        for row in top_customers_df.itertuples()
    ]

    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "kpis": {
            "n_transactions": n_transactions,
            "n_customers": n_customers,
            "fraud_rate_pct": fraud_rate_pct,
            "auc_pr": auc_pr,
            "n_budget_alerts": n_budget_alerts,
            "n_high_risk_customers": int(risk_segments.get("Eleve", 0) + risk_segments.get("Critique", 0)),
            "n_critical_customers": int(risk_segments.get("Critique", 0)),
            "n_critical_notifications": n_critical_notifications,
            "montant_protege": float(
                transactions.merge(rules[["TRANSACTION_CODE", "rule_suspicion_score"]], on="TRANSACTION_CODE")
                .loc[lambda d: d["rule_suspicion_score"] >= 3, "TRANSACTION_AMOUNT"]
                .sum()
            ),
            "n_blocked": int((rules["rule_suspicion_score"] >= 3).sum()),
            "n_combinaisons_budget": n_combinaisons,
            "n_over_daily": n_over_daily,
            "n_over_monthly": n_over_monthly,
            "n_at_100": n_at_100,
        },
        "risk_segments": risk_segments,
        "value_segments": value_segments,
        "top_alerts": top_alerts,
        "live_feed": live_feed,
        "top_customers": top_customers,
        "notifications": notifications,
        "budget_table": budget_table,
        "heatmap": heatmap,
        "trends": trends,
        "network_graph": network_graph,
    }


def main() -> None:
    data = build_dashboard_data()

    template_path = Path(__file__).parent / "template.html"
    out_path = Path("outputs/dashboard_exports/dashboard.html")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    template = template_path.read_text(encoding="utf-8")
    html = template.replace("/*__DASHBOARD_DATA__*/", json.dumps(data, ensure_ascii=False))
    out_path.write_text(html, encoding="utf-8")

    print(f"KPIs : {data['kpis']}")
    print(f"{len(data['top_alerts'])} alertes, {len(data['top_customers'])} fiches client, "
          f"{len(data['notifications'])} notifications budget exportees")
    print(f"Dashboard genere : {out_path.resolve()}")


if __name__ == "__main__":
    main()
