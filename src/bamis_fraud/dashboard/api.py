"""
ROLE
----
Backend (FastAPI recommande) servant les donnees au dashboard : liste des
alertes recentes, fiche client (scores + explication + reseau), etat des
enveloppes de seuil. Lit exclusivement les fichiers de outputs/ et
data/features/ -- ne recalcule jamais de score a la volee (le calcul lourd
reste dans le pipeline batch).

ENDPOINTS PREVUS
------------------
- GET /alerts?min_score=&date_from=&date_to=
- GET /customers/{customer_id}  # scores + top facteurs + graphe local
- GET /customers/{customer_id}/network  # sous-graphe pour visualisation
- GET /budget/{customer_id}  # consommation par service
- GET /kpis  # agregats pour la page d'accueil du dashboard

ENTREES
-------
- outputs/submissions/*.csv
- data/graph/edgelist.parquet (pour la vue reseau d'un client)

SORTIES
-------
- API HTTP consommee par dashboard/app.py
"""
