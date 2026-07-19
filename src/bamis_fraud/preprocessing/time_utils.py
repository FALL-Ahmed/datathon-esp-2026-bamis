"""
ROLE
----
Utilitaires temporels partages : decoupage jour/nuit (F-01 "souvent la
nuit"), jour de semaine/week-end, calcul de fenetres glissantes alignees sur
l'horodatage exact de chaque transaction (pas de fenetre calendaire naive,
pour rester coherent avec la contrainte "aucune information posterieure a
la transaction evaluee").

FONCTIONS PREVUES
------------------
- is_night(ts, night_start=22, night_end=6) -> bool
- is_weekend(ts) -> bool
- rolling_window_bounds(ts, window) -> (start, end)
"""
