"""
ROLE
----
Versionne chaque modele entraine avec ses metadonnees (date, hash des
features utilisees, hyperparametres, seed, metriques de validation) pour
garantir la reproductibilite exigee par le cahier des charges ("le jury
doit pouvoir rejouer vos resultats").

ENTREES
-------
- Modele + metadonnees d'entrainement

SORTIES
-------
- models/<nom>_<version>.pkl
- models/<nom>_<version>.metadata.json

FONCTIONS PREVUES
------------------
- register_model(model, metadata) -> str  # retourne l'identifiant de version
- load_model(version) -> model
- get_production_model() -> model  # pointeur vers le modele retenu pour la soumission finale
"""
