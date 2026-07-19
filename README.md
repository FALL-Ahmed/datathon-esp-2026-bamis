# BAMIS Fraud Detection — Datathon ESP 2026

Détection de fraude, gestion intelligente des seuils et classement client
sur le wallet BAMIS Digital. Voir [`ARCHITECTURE.md`](ARCHITECTURE.md) pour
le détail complet de la démarche, des features et des choix techniques.

> **Statut actuel (2026-07-20 : projet complet.** Ingestion, nettoyage,
> volets A/B/C, entraînement CatBoost (AUC-PR 0,91 sur test temporel jamais
> vu), module graphe bonus (mules, fan-in/fan-out, 24 637 circuits fermés),
> dashboard bonus, bonus seuil personnalisé par classe de risque
> (`recommandations_seuils.csv`), et les 3 CSV finaux (dont
> `classement_clients.csv` étendu à 175 689 clients le 2026-07-20) tournent
> tous via des scripts testés et reproductibles depuis zéro, y compris en
> une seule commande (`scripts/run_all.py`, testé de bout en bout le
> 2026-07-19). `NOTE_METHODOLOGIQUE.md` est
> complète. Restent volontairement non faits (mineur/non prioritaire,
> justifié dans `NOTE_METHODOLOGIQUE.md` section 8-9) :
> `channel_features.py`/`temporal_features.py`, calibration probabiliste,
> réintégration des features graphe dans le score client. Détail module par
> module : section 9 ci-dessous.

## 1. Fichiers nécessaires

| Fichier | Emplacement attendu | Statut |
|---|---|---|
| `DATASET_ESP-2026.csv` | `data/raw/DATASET_ESP-2026.csv` | déjà copié, présent |
| `seuils_services.csv` | `configs/thresholds/seuils_services.csv` | **considéré comme officiel** (reconstruit depuis le tableau du cahier des charges — aucun fichier séparé n'est attendu, voir `configs/thresholds/README_SEUILS.md`) |
| Jeu de test / vérité terrain fraude | — | **ne sera pas fourni** par le jury (il garde la vérité de côté) — voir `ARCHITECTURE.md` section 0 |

## 2. Installation des dépendances

```bash
python -m venv .venv
.venv\Scripts\activate          # PowerShell : .venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -e .                # installe src/bamis_fraud en mode editable
```

## 3. Ordre d'exécution des scripts

```bash
python scripts/01_audit_schema.py          # FONCTIONNEL — audit du CSV brut, ~65s
python scripts/02_build_dataset.py         # FONCTIONNEL — ingestion + quarantaine + nettoyage, ~85s
python scripts/03_build_features.py        # FONCTIONNEL — seuil + comportement + vélocité + réseau, ~230s
python scripts/04_build_graph_features.py  # FONCTIONNEL — bonus, graphe mules/patterns/circuits fermés
python scripts/05_train_model.py           # FONCTIONNEL — validation croisee + entrainement final + evaluation holdout, AUC-PR 0.91, ~5-10min
python scripts/06_predict_fraud.py         # FONCTIONNEL — score chaque transaction avec le modele entraine, ~15s
python scripts/07_compute_budget.py        # FONCTIONNEL — volet B complet, ~11s
python scripts/08_score_customers.py       # FONCTIONNEL — volet C complet, ~14s
python scripts/09_generate_submission.py   # FONCTIONNEL — genere les 3 CSV finaux + valide leur format, ~10s
python scripts/bonus_recommend_thresholds.py  # FONCTIONNEL — bonus, seuil personnalisé par classe de risque (lien volet C -> B), ~5s
```

Tous les scripts 01 à 09 et le bonus `bonus_recommend_thresholds.py` sont
testés de bout en bout sur les 1 627 757 lignes réelles (pas des stubs) —
voir section 9 pour le détail des résultats obtenus sur chaque étape.

Ou en une seule commande (le jury doit pouvoir relancer toute la solution
sans intervention manuelle — exigence explicite du cahier des charges) :

```bash
python scripts/run_all.py --config configs/config.yaml
python scripts/run_all.py --skip-training   # reutilise models/catboost_v1.cbm deja entraine
```

Le pipeline s'arrête au premier échec (fail fast) — il ne continue jamais
sur des données dont l'intégrité n'a pas été validée. Chaque étape est
journalisée (durée, succès/échec) dans `outputs/reports/pipeline_run.log`.
**Testé de bout en bout le 2026-07-19 avec `--skip-training`** : les 10
étapes (dont le bonus) passent, pipeline complet en 13,1 min, régénère les
3 CSV finaux avec les mêmes volumes que ci-dessus (1 627 622 /
175 689 / 67 107 lignes).

## 4. Fichiers générés

Dans `outputs/submissions/` — **les 3 livrables obligatoires, déjà générés
et testés sur les vraies données :**

- `soumission_fraude.csv` — `TRANSACTION_CODE`, `score_fraude` (probabilité 0-1) — **1 627 622 lignes**. Généré sur l'ensemble des transactions connues, faute de fichier de test officiel reçu du jury (voir `modeling/predict.py` — réutilisable tel quel dès réception d'un vrai fichier de test)
- `classement_clients.csv` — `client_id`, `score_risque`/1000, `score_valeur`/1000, segments, `top_5_facteurs_risque`, `top_5_facteurs_valeur`, `action_recommandee` — **175 689 lignes** (un par client vu comme émetteur OU destinataire, étendu depuis 40 866 le 2026-07-20 — voir `ARCHITECTURE.md`)
- `consommation_enveloppes.csv` — `client_id`, `service_code`, consommation jour/mois, seuil jour/mois, taux, reste, `niveau_alerte` — **67 107 lignes** (une par combinaison client×service, état le plus récent connu)

Format de chaque fichier validé automatiquement par
`submission/export.py` (colonnes attendues présentes, pas de colonne
manquante) avant l'écriture finale.

Dans `outputs/reports/` — **bonus volet B, lien risque → seuil :**

- `recommandations_seuils.csv` — `client_id`, `service_code`, seuils actuel/recommandé (unitaire et cumul journalier), segments, `action_recommandee`, `justification` en langage simple — **67 107 lignes**. Traduit en seuils chiffrés la matrice de traitement du volet C ("proposez un seuil plus haut ou plus bas selon la classe de risque du client"), via `budget/threshold_recommender.py`. Multiplicateurs (×1.5 à ×0 selon l'action) lus depuis `configs/config.yaml`, jamais codés en dur — ce sont des hypothèses commerciales à valider par BAMIS, pas des valeurs officielles.

## 5. Lancer le tableau de bord (bonus)

**Décision d'architecture (2026-07-19) : page HTML/CSS/JS autonome plutôt
que Streamlit** (jugée pas assez soignée visuellement) et plutôt que
React+API (trop de pièces mobiles à faire tourner en même temps le jour de
la démo). Une seule commande génère un fichier `.html` unique, avec toutes
les données déjà embarquées dedans — **aucun serveur à lancer, aucun
risque que "ça ne démarre pas" devant le jury.**

```bash
python -m bamis_fraud.dashboard.export_data
```

Puis ouvrir `outputs/dashboard_exports/dashboard.html` directement dans un
navigateur (double-clic). Trois vues : Vue d'ensemble (KPIs + segmentation
risque/valeur en anneaux), File d'alertes (transactions les plus
suspectes, filtrable), Clients à risque (classement, clic sur une ligne
pour l'explication complète du score). Thème sombre par défaut avec
bascule vers un thème clair, palette validée contraste/daltonisme (voir
skill `dataviz`), identité visuelle BAMIS Digital (logo réel embarqué,
orange/vert de la marque).

Comme les autres modules, il ne lit que les fichiers déjà générés dans
`outputs/` et `data/features/` — il ne recalcule jamais de score. Il faut
donc avoir exécuté le pipeline complet (au moins `02`, `03`, `07`, `08` et
un entraînement via `modeling/train.py`) avant de le lancer.

## 6. Reproductibilité

Toutes les graines aléatoires sont fixées de façon centralisée
(`src/bamis_fraud/utils/seed.py`, valeur par défaut dans
`configs/config.yaml` → `random_seed: 42`). Aucun seuil, poids de score ou
fenêtre temporelle n'est codé en dur dans le code Python — tout est lu
depuis `configs/`.

## 7. Structure du projet

Voir `ARCHITECTURE.md` section 1 pour l'arborescence complète commentée.

## 8. Tests

```bash
pytest tests/   # pytest deja dans requirements.txt
```

**17 tests, tous passants** (vérifié le 2026-07-19 : `17 passed in 2.34s`).
Couvre en priorité les points de rupture les plus coûteux en cas d'erreur
silencieuse : parsing du schéma réel et fusion des dates à fraction
sub-seconde (`test_loader.py`), non-durcissement des seuils
(`test_threshold_features.py`), agrégation multi-canal correcte, anti C-08
(`test_budget_engine.py`), absence de fuite temporelle sur un split corrompu
volontairement (`test_leakage_checks.py`), détection de mule et de circuit
fermé A→B→A sur cas synthétiques (`test_graph_detection.py`).

## 9. État d'avancement détaillé (mis à jour au fil de l'eau)

**Modules fonctionnels, testés sur les 1 627 757 lignes réelles :**

| Module | Résultat obtenu |
|---|---|
| `ingestion/schema_audit.py` | Structure réelle confirmée : 26 champs sur 100% des lignes (pas les 23 déclarés) |
| `ingestion/loader.py` | 1 627 757 lignes chargées et typées, dates fusionnées correctement |
| `ingestion/validators.py` | 63 dates aberrantes + 72 montants aberrants détectés et isolés |
| `preprocessing/cleaning.py` | 0 doublon technique, 130 743 paires F-06 flaguées, 18 053 transactions GIMTEL (candidat) |
| `preprocessing/customer_resolution.py` | 175 689 téléphones distincts identifiés comme clients |
| `feature_engineering/threshold_features.py` | 0,78% des transactions au-dessus du seuil, 2,16% en zone de fractionnement (80-100% du seuil) |
| `feature_engineering/behavioral_features.py` | Écart à l'historique propre du client calculé (médiane, max, fréquence), causal et anti-fuite vérifié |
| `feature_engineering/velocity_features.py` | Compteurs de rafale 1h/24h/7j (ex. un agent légitime détecté à 3400 opérations/24h — pas une fraude, confirmé par l'historique du compte) |
| `feature_engineering/network_features.py` | Ratio montant reçu/envoyé + délai depuis dernière réception (signal mule C-02, approximation niveau 1-2) |
| `rules/business_rules.py` | 7 règles simples (R1-R7, cf. F-01 à F-06 / C-01 à C-10) appliquées sur les 1,6M lignes ; score de suspicion agrégé ; **pseudo-label d'entraînement = 0,466% des transactions** (≥2 règles déclenchées en même temps) — cohérent avec le taux "~1%" donné en exemple par le cahier des charges. Trois paramètres recalibrés le 2026-07-19 sur la vraie distribution des données (voir `configs/config.yaml` pour le détail de chaque mesure) : `night_window` (0h-7h plutôt que 22h-6h, qui incluait à tort des heures d'activité normale), `mule_ratio_band` resserré à [0.9,1.1] (la bande initiale [0.8,1.2] matchait 28% des transactions à elle seule — pas sélective), `fractionnement_min_ops_24h` confirmé à 3 (déjà bien calibré, correspond au 75e percentile réel) |
| `budget/budget_engine.py` | Cumul jour/mois par client×service, tous canaux confondus (946 850 combinaisons client×service×jour) ; 0,25% au-dessus du seuil journalier officiel. Seuil mensuel non fourni par le cahier des charges — estimé à seuil_jour×30, hypothèse documentée à remplacer si un vrai seuil mensuel est communiqué |
| `budget/alert_engine.py` | Niveaux d'alerte 50/80/95/100% appliqués ; 1 167 clients avec au moins une alerte sur la période complète |
| `scoring/customer_scoring.py` | Scores de risque et de valeur (0-1000) pour 40 866 clients. Segments risque : 52,8% Faible, 43,4% Modéré, 3,7% Élevé, 0,1% Critique (42 clients). Segments valeur : 53,1% Bronze, 20,5% Argent, 17,9% Or, 8,6% Platine. **Deux bugs de méthode trouvés et corrigés par test empirique** (voir le code pour le détail complet) : (1) normalisation par rang percentile inadaptée aux indicateurs concentrés à zéro (99,97% des clients à taux de rafale nul se retrouvaient poussés au 50e percentile au lieu de 0% — personne ne descendait sous 367/1000, la catégorie "Risque faible" restait vide) → corrigé par mise à l'échelle min-max pour ces indicateurs ; (2) agrégation par moyenne au sein d'un sous-critère diluait un client extrême sur un seul indicateur fort → corrigée par le maximum |
| `scoring/treatment_matrix.py` | Croise segment valeur × segment risque → action recommandée (7 actions possibles, ex. 42 clients en "Gel, investigation") |
| `scoring/explainability.py` | Génère les 5 facteurs en langage simple pour chaque score (formule additive transparente, pas besoin de SHAP) |
| `feature_engineering/feature_store.py` | Assemble les 5 fichiers de features transaction en une seule matrice (1,6M lignes, 24 colonnes). Les flags `rule_R1...R7` sont volontairement exclus des features d'entrée du modèle (ce sont les ingrédients du pseudo-label — les inclure serait une fuite triviale, le modèle recopierait juste la formule des règles au lieu de généraliser) |
| `validation/temporal_split.py` | Découpage walk-forward à 3 replis + embargo 7 jours + holdout final. `test_holdout_fraction_of_timeline` recalibré le 2026-07-19 (0.15 → 0.05) après vérification empirique : même à 5% du temps, le holdout contient déjà 554 cas de pseudo-fraude (largement suffisant pour un AUC-PR stable), et préserve 87% des données pour l'entraînement au lieu de 65% |
| `validation/leakage_checks.py` | 3 contrôles automatiques (chevauchement de dates, respect de l'embargo, doublons de transaction) — échec explicite si un problème est détecté, jamais un warning silencieux. PASS sur les 3 replis |
| `modeling/train.py` | Baseline (0,42 AUC-PR) → régression logistique (0,31, non réglée finement, sert juste de garde-fou) → **CatBoost (0,76 en moyenne sur 3 replis, 0,91 sur le test final jamais vu, 554 cas)**. Modèle sauvegardé dans `models/catboost_v1.cbm` |
| `modeling/evaluate.py` | AUC-PR (sklearn `average_precision_score`) + precision/recall à plusieurs seuils — jamais l'accuracy |
| `dashboard/export_data.py` + `template.html` | Tableau de bord HTML/CSS/JS autonome (page unique, aucun serveur), thème sombre/clair, identité BAMIS Digital (logo réel embarqué), 3 vues (KPIs, alertes, clients), testé avec Playwright (captures d'écran des 2 thèmes + 4 vues, tout fonctionne) |
| `modeling/predict.py` | Score chaque transaction avec le modèle CatBoost entraîné, préserve l'ordre d'entrée exact (piège explicitement cité par le cahier des charges). Tourne sur `feature_matrix_transactions.parquet` faute de fichier de test officiel — réutilisable tel quel dès réception |
| `submission/export.py` | **Génère les 3 CSV finaux obligatoires**, avec validation automatique du format (colonnes attendues) avant écriture. `soumission_fraude.csv` (1 627 622 lignes), `classement_clients.csv` (40 866 lignes), `consommation_enveloppes.csv` (67 107 lignes, une par client×service) |
| `graph/graph_builder.py` | Construit le graphe transactionnel réel (163 259 comptes, 1 363 346 transactions), ~25s |
| `graph/mule_detection.py` | Score mule par compte, exige la répétition (pas un cas isolé). Meilleur candidat trouvé : 259 pass-through rapides sur 273 transactions (95%) |
| `graph/pattern_detection.py` | Fan-in/fan-out (comptes collecteurs/distributeurs), circuits fermés A→B→A (24 637 trouvés en 7 jours). **Un bug mémoire trouvé et corrigé avant de perdre du temps à le déboguer en aveugle** : le premier essai (self-join classique) a fait planter le process — une poignée de paires agent/hub ont des milliers de transactions entre elles, créant un produit croisé énorme. Remplacé par `merge_asof` (recherche par proximité temporelle, jamais de produit croisé) |
| `graph/graph_features.py` | Assemble tout par compte (163 259 comptes) — 11 410 comptes impliqués dans au moins un circuit fermé, 5 779 avec au moins 3 pass-through rapides répétés |

**Périmètre du module graphe volontairement limité** (voir `graph/pattern_detection.py`) : chaînes de rebond à 3+ sauts (C-05) et fractionnement multi-comptes (C-10) non implémentés — jugés trop coûteux à calculer correctement pour le gain marginal par rapport à fan-in/fan-out et aux circuits courts, conformément aux priorités de `ARCHITECTURE.md` section 10.

**Orchestration :** `scripts/01_audit_schema.py`, `02_build_dataset.py`,
`03_build_features.py`, `04_build_graph_features.py`, `06_predict_fraud.py`,
`07_compute_budget.py`, `08_score_customers.py`, `09_generate_submission.py`
enchaînent 25 modules automatiquement. `feature_store.py` + `validation/` +
`modeling/train.py` (non encore câblés dans un script numéroté, lancés
directement) produisent le modèle entraîné en amont. `dashboard/export_data.py`
génère le tableau de bord à la demande.

**Pas encore fait :** `channel_features.py`, `temporal_features.py`,
`modeling/calibration.py` (limite assumée — CatBoost non recalibré
séparément), `scripts/05` non câblé (entraînement lancé directement via
`modeling/train.py`), intégration des features graphe dans
`scoring/customer_scoring.py` (le module graphe est fonctionnel et livre
ses propres sorties, mais n'est pas encore reconnecté au score de risque
volet C — actuellement basé sur les features réseau légères de
`network_features.py`).
