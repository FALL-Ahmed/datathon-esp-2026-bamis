"""
ROLE
----
Capture le contournement C-08 (changement de canal une fois le seuil
atteint sur un canal) et la diversite de canaux utilisee par le score de
valeur (volet C, critere "Diversite").

FEATURES PRODUITES
-------------------
- nb_canaux_distincts_utilises_7j
- has_switched_channel_after_threshold_hit (bool)
- canal_le_plus_recent vs canal_habituel (categorique)

ENTREES
-------
- data/processed/transactions_clean.parquet (colonne CHANNEL_TYPE)
- data/features/threshold_features.parquet (pour savoir si le seuil etait
  atteint avant le changement de canal)

SORTIES
-------
- data/features/channel_features.parquet
"""
