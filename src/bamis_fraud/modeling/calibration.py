"""
ROLE
----
Le livrable attendu est une PROBABILITE (pas seulement un score relatif) :
"Le score doit etre une probabilite, et non seulement une reponse fraude/
normale". Les modeles d'arbres (Random Forest, boosting) produisent des
scores mal calibres en probabilite brute -- ce module recalibre la sortie.

ENTREES
-------
- Modele entraine + scores bruts sur un jeu de calibration distinct du test

SORTIES
-------
- Modele de calibration (Platt scaling ou isotonic regression) sauvegarde
  a cote du modele principal dans models/

FONCTIONS PREVUES
------------------
- fit_platt_scaling(raw_scores, y_true) -> calibrator
- fit_isotonic(raw_scores, y_true) -> calibrator
- apply_calibration(calibrator, raw_scores) -> probabilities
"""
