"""
ROLE
----
Frontend du tableau de bord (Streamlit recommande pour la vitesse de
developpement en 2 jours ; Dash si interactivite graphe plus poussee est
prioritaire). Voir ARCHITECTURE.md section 9 pour le detail des pages,
KPI, graphiques et filtres attendus par le jury.

PAGES PREVUES
--------------
- Vue d'ensemble (KPIs, courbe PR, volumetrie d'alertes)
- File d'alertes (triable/filtrable par score, service, canal)
- Fiche client (scores, explication, historique, reseau local)
- Suivi des enveloppes/seuils
- Exploration du graphe de fraude (mules, chaines, circuits)

ENTREES
-------
- src/bamis_fraud/dashboard/api.py

SORTIES
-------
- Application web locale (streamlit run app.py)
"""
