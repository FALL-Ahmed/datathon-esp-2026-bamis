# seuils_services.csv — statut

**Décision d'équipe (2026-07-19) : ce fichier est traité comme la source
officielle des seuils, pas comme un placeholder en attente.** Le cahier des
charges mentionne un fichier livré séparément, mais l'équipe a jugé que ce
fichier séparé ne sera probablement pas fourni — la grille de seuils est
déjà entièrement donnée dans le tableau du cahier des charges
(`Defi BAMIS ESP 2026.docx`, section "Grille des seuils par service"), et
c'est cette grille qui a servi à construire le CSV ci-contre. Elle est donc
considérée comme faisant foi jusqu'à indication contraire du jury.

## Ce qui ne change pas si le jury publie un fichier différent

Toute la solution lit ce CSV dynamiquement (`budget/budget_engine.py`,
`feature_engineering/threshold_features.py`, `rules/business_rules.py`) et
ne code jamais un seuil en dur — c'est précisément ce que le jury vérifiera
("ces valeurs sont paramétrables, le jury pourra les modifier, ne les
codez donc pas en dur"). Si un fichier différent apparaît, il suffit de
remplacer ce CSV, sans toucher au code. Si ses colonnes sont nommées
différemment, mettre à jour uniquement `configs/config.yaml`, pas le code
métier.

## Rappel des deux comparaisons obligatoires (section 2 du cahier des charges)

Chaque montant doit être comparé de deux façons, jamais une seule :
1. **Au seuil du service** (ce fichier) — `feature_engineering/threshold_features.py`.
2. **À l'habitude du client** (médiane, maximum habituel, fréquence, calculés
   sur son propre historique) — `feature_engineering/behavioral_features.py`.

Le montant seul ne suffit jamais : un même montant peut être normal pour un
service et suspect pour un autre, et normal pour un client et suspect pour
un autre.
