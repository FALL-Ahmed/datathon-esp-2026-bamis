# Architecture technique — BAMIS Fraud Detection (Datathon ESP 2026)

Document de référence de l'équipe. Rédigé après audit du jeu de données réel
(`DATASET_ESP-2026.csv`, 1 627 757 lignes) et lecture intégrale du cahier
des charges (`Defi BAMIS ESP 2026.docx`). Aucun code métier n'est encore
écrit à ce stade — ce document et le squelette de projet livré avec
(`src/`, `configs/`, `scripts/`, `tests/`) forment la base sur laquelle
l'entraînement démarrera dès l'analyse des données terminée.

**Principe directeur : faire exactement ce que le cahier des charges
demande, au format exact demandé, avant d'ajouter quoi que ce soit en
bonus.** Le barème le confirme — 95 % de la note porte sur les livrables
obligatoires (fraude, seuils, classement, doc) et seulement 5 points de
plus (dans le "peu de faux positifs" et le "contournement") viennent
récompenser l'effort supplémentaire. Le graphe et le dashboard sont des
multiplicateurs de points sur une base déjà solide, pas un substitut à
cette base.

---

## 0. Constat critique — vérifié sur l'intégralité du fichier (1 627 757 lignes)

**Mise à jour :** cette section a été revalidée par un audit complet (pas
un échantillon) exécuté via `ingestion/schema_audit.py` sur les 1 627 757
lignes réelles. Le rapport brut est dans
`outputs/reports/schema_audit_report.json`, le mapping corrigé dans
`configs/schema_map.yaml`. Plusieurs hypothèses posées sur un échantillon
initial de 100 000 lignes se sont révélées **fausses à grande échelle** —
la correction elle-même est une leçon méthodologique : un échantillon pris
sur les premières lignes d'un fichier trié chronologiquement n'est pas
représentatif si le système source a évolué dans le temps (ce qui est
précisément le cas ici).

**1. Le fichier CSV réel ne correspond pas au dictionnaire de données du
cahier des charges.** Le cahier des charges déclare 23 colonnes. Le fichier
réel contient un socle de **26 champs présents sur 100 % des lignes**
(positions 0 à 25), plus 0 à 4 champs supplémentaires quasi intégralement
vides (positions 26 à 29, artefact d'export sans signal — à ignorer, pas
un second schéma comme d'abord supposé).

**Cause identifiée :** les trois colonnes de date (`TRANSACTION_DATE`,
`REQUEST_DATE`, `RESPONSE_DATE`) exportent une fraction sub-seconde après
une **virgule non protégée par des guillemets** :

```
12/06/22 15:05:44,421000000
```

Cette virgule est lue par n'importe quel parseur CSV standard (y compris
`pandas.read_csv()` avec ses réglages par défaut) comme un **séparateur de
colonne**, ce qui décale silencieusement toutes les colonnes suivantes.

**2. Plusieurs colonnes avaient été mal identifiées sur l'échantillon
initial, corrigées après audit complet :**
- Position 18 : ce n'est **pas** `DESTINATION_CUSTOMER` comme supposé
  initialement, mais `PARTNER_REFERENCE` (codes d'institution à faible
  cardinalité, motif `INS0000##`, 19 valeurs distinctes) — ce qui colle
  exactement à la description du cahier des charges ("ne détermine pas
  l'interne/externe").
- Position 19 : c'est `TRANSACTION_DIRECTION` (`OUTBOUND`/`INBOUND`), pas
  la position 20 comme d'abord deviné.
- Position 20 : c'est plutôt `QR_INDICATOR` (motif tri-état `U`/`N`/`Y`).
- Positions 16-17 : d'abord suspectées d'être `SOURCE_CUSTOMER`, elles se
  révèlent en fait être des références de traitement/rapprochement (très
  faible cardinalité — 2095 et 348 valeurs distinctes pour 1,6M lignes — et
  une courbe d'adoption progressive nette entre 2022 et 2026, signature
  d'un processus déployé dans le temps, pas d'un identifiant client).
- **Le meilleur candidat pour `DESTINATION_CUSTOMER` (la colonne pivot
  interne/externe GIMTEL) est maintenant la position 15**, remplie sur
  seulement 1,1 % des lignes — un taux bien plus cohérent avec "minorité de
  transactions externes" que les 55-62 % observés sur les positions 16-18.
  **À confirmer en priorité avant de construire les features GIMTEL (5.8).**
- Plusieurs colonnes que l'échantillon initial donnait comme "quasi 100 %
  vides" (positions 21 à 25, y compris le candidat `CHANNEL_TYPE`) sont en
  réalité remplies à 49-98 % sur le fichier complet — leur signification
  précise reste à revalider, `CHANNEL_TYPE` en priorité car il conditionne
  la détection de C-08.

**3. Deux découvertes supplémentaires, décisives pour la suite :**
- **Plage de dates réelle : du 5 juin 2022 (avec 63 lignes datées de 2003,
  anomalie à mettre en quarantaine) au 15 juillet 2026 — soit jusqu'à 3
  jours avant aujourd'hui.** Volume en forte croissance : 37k lignes en
  2022, 102k en 2023, 295k en 2024, 717k en 2025, déjà 477k sur les 6.5
  premiers mois de 2026. Près de 75 % du volume total est concentré sur
  2025-2026 — la validation temporelle (section 6) doit être conçue sur
  cette base, pas sur une hypothèse abstraite de fenêtres courtes.
- **Aucune colonne cible de fraude n'existe dans ce fichier.** Un scan
  complet à la recherche d'un flag binaire à faible prévalence (~1 %,
  cohérence avec le cahier des charges) n'a trouvé qu'un candidat à 3
  lignes sur 1,6M — du bruit. Ce fichier est très probablement un **dump
  brut non étiqueté**.

  **Décision d'équipe (2026-07-19), ne pas attendre de labels :** le
  cahier des charges dit explicitement "le jury comparera vos notes à la
  vérité qu'il garde de côté" (section 4, volet A) — la vérité terrain
  n'est **jamais donnée**, ni pour l'entraînement ni pour le test, ce n'est
  pas une pièce manquante en transit. Conséquence directe sur la lecture du
  "Niveau 2 : machine learning entraîné sur les exemples étiquetés" du
  cahier des charges : les exemples étiquetés ne peuvent venir que de
  **nous-mêmes**. Stratégie retenue : **apprentissage faiblement
  supervisé** — `rules/business_rules.py` (niveau 1, F-01 à F-06, C-01 à
  C-10) génère un score de suspicion par des règles explicites ; ce score
  sert de **pseudo-label** pour entraîner le modèle ML (niveau 2), qui
  apprend à généraliser au-delà des règles strictes plutôt que de les
  reproduire telles quelles. Le graphe (niveau 3) enrichit les deux
  ensuite. Ce choix ne bloque donc plus rien : `modeling/train.py`
  consomme les sorties de `rules/business_rules.py` comme cible
  d'entraînement, pas un fichier externe attendu. Détail dans
  `configs/schema_map.yaml` → `decision_2026_07_19_pas_de_labels_a_attendre`.
  De la même façon, `configs/thresholds/seuils_services.csv` est traité
  comme la grille officielle (recréée depuis le tableau du cahier des
  charges) et non comme un placeholder en attente d'un fichier séparé —
  voir `configs/thresholds/README_SEUILS.md`.

**Deux fichiers annoncés par le cahier des charges n'ont pas été reçus en
tant que fichiers séparés — traités comme suit (décision d'équipe
2026-07-19, voir ci-dessus) :**
- `seuils_services.csv` : pas d'attente d'un fichier séparé. Le tableau du
  cahier des charges fait foi, il est déjà encodé dans
  `configs/thresholds/seuils_services.csv`. Si le jury publie un fichier
  différent en cours de route, il suffira de le substituer — aucun code ne
  change, puisque tout est lu dynamiquement depuis ce CSV.
- Jeu de données de **test** et vérité terrain fraude : ne seront **jamais**
  fournis (voir citation du cahier des charges ci-dessus). Le pipeline
  (`scripts/06_predict_fraud.py`) reste conçu pour ingérer un futur fichier
  de test via le même chemin que le train (`ingestion/schema_audit.py`
  d'abord) au cas où l'organisateur en publierait bien un pour l'évaluation
  finale — mais l'entraînement, lui, ne dépend plus de cette hypothèse.

**Fait, concrètement :** `ingestion/schema_audit.py` et
`ingestion/loader.py` sont implémentés (pas des stubs) et exécutés sur le
fichier complet — 1 627 694 lignes chargées et typées dans
`data/interim/transactions_raw_typed.parquet` (63 lignes datées de 2003
mises en quarantaine dans `data/interim/transactions_quarantined_dates.parquet`).
Reste à confirmer avec les organisateurs les points listés dans
`configs/schema_map.yaml` → `action_items_avant_feature_engineering` avant
de bâtir les features GIMTEL et canal dessus.

**4. Anomalie de montant découverte pendant le chargement complet, à
gérer dans `ingestion/validators.py` avant tout feature engineering :** 72
lignes sur 1 627 757 (0,0044 %) ont un `TRANSACTION_AMOUNT` absurde (jusqu'à
10⁶⁰ MRU), vérifié directement dans le CSV source — ce n'est pas un artefact
du loader. Ces lignes sont **toutes** au statut `TRANSACTION_STATUS =
REGISTERED` (majoritairement `SERVICE_05`, 10 029 des 10 912 lignes
REGISTERED), très probablement une valeur sentinelle du système source pour
des transactions enregistrées mais jamais réellement finalisées (10 840 des
10 912 lignes REGISTERED ont un montant parfaitement normal, donc ce n'est
pas systématique au statut REGISTERED — seulement une poignée de cas
limites). Une seule de ces 72 valeurs suffirait à faire exploser un ratio,
une moyenne glissante ou un z-score sur tout le compte client concerné :
`ingestion/validators.py` doit borner ou exclure ces montants avant que
`feature_engineering/` ne s'en serve.

---

## 1. Arborescence du projet

Déjà créée sur disque (`D:\Datathon`). Vue d'ensemble :

```
Datathon/
├── ARCHITECTURE.md                 # ce document
├── README.md                       # mode d'emploi (installation, ordre d'exécution)
├── requirements.txt
├── pyproject.toml                  # src/bamis_fraud installable (pip install -e .)
├── .gitignore
│
├── configs/
│   ├── config.yaml                 # seeds, fenêtres, poids de score, alertes — jamais en dur
│   ├── feature_config.yaml         # liste des features actives par catégorie
│   ├── model_config.yaml           # hyperparamètres par modèle
│   ├── schema_map.yaml             # mapping colonne réelle -> nom métier (voir section 0)
│   └── thresholds/
│       ├── seuils_services.csv     # seuils par service (paramétrable, jamais codé en dur)
│       └── README_SEUILS.md
│
├── data/
│   ├── raw/                        # CSV brut, jamais modifié
│   ├── interim/                    # après réparation du parsing / réalignement colonnes
│   ├── processed/                  # après nettoyage, typage, dédoublonnage
│   ├── features/                   # tables de features (transaction, client, budget, graphe)
│   ├── graph/                      # edgelist, objet graphe, scores mules/patterns
│   └── external/                   # référentiels tiers éventuels
│
├── notebooks/                      # EDA uniquement — jamais de logique de production
│
├── src/bamis_fraud/                # package Python installable
│   ├── ingestion/                  # schema_audit, loader, validators
│   ├── preprocessing/              # cleaning, customer_resolution, time_utils
│   ├── feature_engineering/        # threshold, behavioral, velocity, network, channel, temporal, feature_store
│   ├── graph/                      # graph_builder, mule_detection, pattern_detection, graph_features
│   ├── budget/                     # budget_engine, alert_engine, threshold_recommender
│   ├── scoring/                    # customer_scoring, explainability, treatment_matrix
│   ├── rules/                      # business_rules (niveau 1, règles explicables)
│   ├── modeling/                   # datasets, train, evaluate, calibration, predict, model_registry
│   ├── validation/                 # temporal_split, leakage_checks
│   ├── submission/                 # export (les 3 CSV finaux)
│   ├── dashboard/                  # api (FastAPI) + app (Streamlit) + components
│   └── utils/                      # logging, io, seed
│
├── scripts/                        # 01 à 09 + run_all.py — orchestration CLI, un point d'entrée par étape
├── tests/                          # non-régression sur les règles critiques (voir section 6)
├── models/                         # modèles sérialisés + metadata JSON (versionnés)
└── outputs/
    ├── submissions/                # soumission_fraude.csv, classement_clients.csv, consommation_enveloppes.csv
    ├── reports/                    # figures, métriques, rapports d'audit
    └── dashboard_exports/
```

**Choix structurants et pourquoi :**

- **`src/bamis_fraud/` en package installable** (`pyproject.toml`,
  `pip install -e .`) plutôt qu'un tas de scripts qui s'importent entre eux
  par chemin relatif : ça évite les hacks `sys.path.append(...)` que le
  jury verrait immédiatement comme un signe d'amateurisme, et ça rend le
  code testable proprement (`tests/` importe le package normalement).
- **Séparation stricte `data/raw` → `interim` → `processed` → `features`** :
  chaque étape ne réécrit jamais la précédente. Si un bug est découvert
  dans le feature engineering un jour avant la deadline, on repart de
  `processed/` sans tout recharger depuis le CSV brut de 385 Mo.
  `interim/` existe spécifiquement pour isoler le problème de la section 0
  (réparation du schéma) du nettoyage fonctionnel (section suivante).
- **`notebooks/` cantonné à l'EDA** : le cahier des charges ne demande pas
  un notebook, et un jury qui doit relire un notebook de 2000 cellules pour
  comprendre la logique perd du temps et perd confiance. Toute logique
  réutilisée vit dans `src/`.
- **`configs/` séparé du code** : c'est la réponse structurelle directe à
  l'exigence répétée trois fois dans le cahier des charges ("ne les codez
  pas en dur"). Un seuil, un poids de score, une fenêtre temporelle : tout
  ça se change dans un YAML/CSV, jamais dans un `.py`.
- **`scripts/` numérotés** : le jury doit pouvoir "relancer la solution
  sans modifier manuellement le code" — une suite `01_...` à `09_...` plus
  un `run_all.py` rend l'ordre d'exécution évident sans avoir à lire la
  documentation en détail.

---

## 2. Pipeline complet — du CSV brut à la soumission finale

```
 0. AUDIT DE SCHÉMA (bloquant)
    DATASET_ESP-2026.csv (brut, colonnes décalées)
      │  ingestion/schema_audit.py
      ▼
    configs/schema_map.yaml (validé ou mis à jour)

 1. INGESTION
    │  ingestion/loader.py (lecture selon schema_map, fusion date+fraction, typage)
      ▼
    data/interim/transactions_raw_typed.parquet
      │  ingestion/validators.py (contrôles bloquants : unicité, plages, cohérence)
      ▼
 2. NETTOYAGE
    │  preprocessing/cleaning.py (dédoublonnage technique, flag doublons fonctionnels F-06,
    │                              normalisation, résolution interne/externe GIMTEL)
    │  preprocessing/customer_resolution.py (identifiant client stable, téléphones partagés)
      ▼
    data/processed/transactions_clean.parquet
    data/processed/customer_phone_map.parquet

 3. FEATURE ENGINEERING (parallélisable entre sous-étapes)
    ├─ feature_engineering/threshold_features.py     (besoin: thresholds/seuils_services.csv)
    ├─ feature_engineering/behavioral_features.py    (besoin: historique client, expanding window)
    ├─ feature_engineering/velocity_features.py      (besoin: tri temporel par client)
    ├─ feature_engineering/network_features.py       (besoin: customer_phone_map)
    ├─ feature_engineering/channel_features.py       (besoin: threshold_features pour C-08)
    ├─ feature_engineering/temporal_features.py
    ├─ rules/business_rules.py                       (besoin: threshold_features, velocity_features)
    └─ budget/budget_engine.py + alert_engine.py      (besoin: thresholds/seuils_services.csv)
      │
      ▼
 4. GRAPHE (bonus, mais alimente le modèle ML — donc à lancer avant l'entraînement)
    graph/graph_builder.py → graph/mule_detection.py + pattern_detection.py → graph/graph_features.py

 5. ASSEMBLAGE
    feature_engineering/feature_store.py (jointure de toutes les tables ci-dessus)
      ▼
    data/features/feature_matrix_transactions.parquet
    data/features/feature_matrix_customers.parquet

 6. VALIDATION & ENTRAÎNEMENT
    validation/temporal_split.py → validation/leakage_checks.py
      ▼
    modeling/datasets.py → modeling/train.py (baseline → LR → RF → boosting)
      ▼
    modeling/evaluate.py (AUC-PR) → modeling/calibration.py → modeling/model_registry.py
      ▼
    models/<modele_final>.pkl

 7. SCORING DU JEU DE TEST (volet A)
    modeling/predict.py → data/features/test_predictions.parquet

 8. SCORING CLIENT (volet C) & BUDGET (volet B)
    scoring/customer_scoring.py → scoring/explainability.py → scoring/treatment_matrix.py
    budget/budget_engine.py (déjà calculé étape 3, réappliqué sur test si besoin)

 9. EXPORT FINAL
    submission/export.py
      ▼
    outputs/submissions/soumission_fraude.csv
    outputs/submissions/classement_clients.csv
    outputs/submissions/consommation_enveloppes.csv

10. BONUS
    dashboard/api.py + dashboard/app.py (lit uniquement outputs/ et data/features/, ne recalcule rien)
```

Chaque flèche correspond à un script numéroté dans `scripts/` (section 8).
`scripts/run_all.py` exécute les étapes 0 à 9 dans l'ordre et s'arrête au
premier échec (fail fast) plutôt que de continuer sur des données
corrompues.

---

## 3. Modules Python — rôle de chacun

Le contenu détaillé (entrées, sorties, fonctions prévues) est dans le
docstring de chaque fichier sous `src/bamis_fraud/`. Résumé :

| Module | Rôle en une phrase |
|---|---|
| `ingestion/schema_audit.py` | Détecte la vraie structure du CSV, produit `schema_map.yaml` |
| `ingestion/loader.py` | Charge le CSV selon le mapping validé, fusionne date+fraction, type les colonnes |
| `ingestion/validators.py` | Contrôles bloquants post-chargement (fail fast si régression) |
| `preprocessing/cleaning.py` | Dédoublonnage technique, flag doublons fonctionnels (F-06), normalisation |
| `preprocessing/customer_resolution.py` | Identifiant client stable, détection téléphones partagés |
| `preprocessing/time_utils.py` | Utilitaires jour/nuit, week-end, fenêtres glissantes |
| `feature_engineering/threshold_features.py` | Ratio montant/seuil du service, dépassement, cumul/seuil |
| `feature_engineering/behavioral_features.py` | Écart à l'historique propre du client (médiane, max, fréquence) |
| `feature_engineering/velocity_features.py` | Compteurs glissants 1h/24h/7j (rafales, fractionnement) |
| `feature_engineering/network_features.py` | Fan-in/out léger, ratio in/out, téléphone partagé, GIMTEL |
| `feature_engineering/channel_features.py` | Diversité de canaux, changement de canal après seuil atteint (C-08) |
| `feature_engineering/temporal_features.py` | Heure, nuit, latence requête/réponse (signal d'automatisation) |
| `feature_engineering/feature_store.py` | Jointure finale de toutes les tables de features, versioning |
| `graph/graph_builder.py` | Construit le graphe transactionnel (comptes = nœuds, transactions = arêtes) |
| `graph/mule_detection.py` | Score de compte mule (pass-through ratio + délai) — C-02 |
| `graph/pattern_detection.py` | Fan-in, fan-out, chaînes de rebond, circuits fermés, fractionnement multi-comptes — C-03 à C-06, C-10 |
| `graph/graph_features.py` | Convertit les détections graphe en colonnes numériques pour le modèle |
| `budget/budget_engine.py` | Cumul jour/mois par client×service, tous canaux confondus |
| `budget/alert_engine.py` | Niveaux d'alerte 50/80/95/100 %, historique d'alertes |
| `budget/threshold_recommender.py` | Bonus : seuil personnalisé selon classe de risque |
| `scoring/customer_scoring.py` | Score de risque et score de valeur /1000, segmentation |
| `scoring/explainability.py` | Top 5 facteurs par score, en langage simple (SHAP + templates) |
| `scoring/treatment_matrix.py` | Croise risque×valeur → action recommandée |
| `rules/business_rules.py` | Règles métier explicites niveau 1 (baseline explicable) |
| `validation/temporal_split.py` | Split chronologique glissant avec embargo |
| `validation/leakage_checks.py` | Détection automatique de fuite temporelle |
| `modeling/datasets.py` | Construit X/y à partir des features actives et du split |
| `modeling/train.py` | Entraîne baseline → LR → RF → CatBoost/LightGBM/XGBoost |
| `modeling/evaluate.py` | AUC-PR, precision/recall, matrice de confusion, courbe PR |
| `modeling/calibration.py` | Calibre les scores en vraies probabilités (Platt/isotonic) |
| `modeling/predict.py` | Score le jeu de test, préserve l'ordre exact des transactions |
| `modeling/model_registry.py` | Versionne modèle + métadonnées pour la reproductibilité |
| `submission/export.py` | Génère les 3 CSV finaux au format exact attendu |
| `dashboard/api.py` | Backend FastAPI (alertes, fiche client, réseau, KPI) |
| `dashboard/app.py` | Frontend Streamlit consommé par le jury |
| `utils/logging_utils.py`, `io_utils.py`, `seed.py` | Logging centralisé, I/O standardisé, graines aléatoires fixées |

---

## 4. Pipeline Machine Learning idéal — étapes, ordre, dépendances

```
1. Baseline règle "montant / seuil" en score continu
   dépend de : threshold_features
   sert de : plancher de comparaison — si le ML ne bat pas ça, il ne sert à rien

2. Split temporel + vérification anti-fuite
   dépend de : feature_matrix_transactions complet (toutes catégories, y compris graphe)
   bloque : tout entraînement tant que leakage_checks n'est pas vert

3. Entraînement modèles (ordre de complexité croissante, section 7)
   dépend de : (2)
   produit : un modèle par famille + ses métriques AUC-PR en validation croisée temporelle

4. Sélection du modèle final
   critère unique : AUC-PR en validation (jamais l'accuracy)
   dépend de : (3)

5. Calibration des probabilités
   dépend de : (4), sur un jeu de calibration distinct du test final

6. Évaluation finale + explicabilité (SHAP)
   dépend de : (5)

7. Scoring du jeu de test officiel
   dépend de : (5), + repasser le jeu de test par TOUT le pipeline d'ingestion/
   feature engineering identique au train (même schema_audit, même feature_store)
```

Point d'attention structurant : **le pipeline de features doit être
strictement identique entre train et test** (même code, mêmes fenêtres,
même fichier de seuils). C'est pour ça que `feature_engineering/` et
`ingestion/` ne prennent jamais de branchement `if is_train:` — un seul
chemin de code, appelé une fois par `scripts/03_build_features.py` sur le
train et une fois par `scripts/06_predict_fraud.py` sur le test.

---

## 5. Stratégie de Feature Engineering, par catégorie

### 5.1 Features transactionnelles (seuil)
**Pourquoi :** c'est la première comparaison obligatoire du cahier des
charges ("au seuil de son service"). C'est aussi la feature la plus simple
à calculer et probablement la plus discriminante à elle seule.
**Variables :** `amount_to_service_threshold_ratio`, `is_above_unit_threshold`,
`distance_to_threshold` (proche de 0 et positif = signal de fractionnement
C-01), `daily_cumulative_ratio`.
**Colonnes sources :** `TRANSACTION_AMOUNT`, `SERVICE_CODE` +
`configs/thresholds/seuils_services.csv`.

### 5.2 Features comportementales (historique client)
**Pourquoi :** deuxième comparaison obligatoire ("à l'habitude du client").
C'est aussi le levier n°1 contre les faux positifs — un marchand qui reçoit
de gros montants tous les jours ne doit pas être signalé par rapport au
seuil du service, mais son *propre* écart à sa propre normalité doit rester
faible.
**Variables :** `amount_to_customer_median_ratio`,
`amount_to_customer_habitual_max_ratio`, `zscore_vs_customer_history`,
`is_new_beneficiary` (F-03), `days_since_last_transaction`,
`customer_activity_break_score` (F-02, détection de rupture).
**Colonnes sources :** historique propre par `SOURCE_CUSTOMER`, calculé en
expanding window strictement passée.

### 5.3 Features de vélocité / temporelles
**Pourquoi :** capte les rafales (C-07) et le fractionnement temporel
(C-01) — un fraudeur qui découpe agit vite, un client normal non.
**Variables :** compteurs et montants cumulés glissants 1h/24h/7j, nombre
de bénéficiaires distincts sur la fenêtre, accélération vs rythme habituel,
heure de la journée, indicateur nuit (F-01), week-end, latence
requête/réponse et sa régularité (signal d'automatisation explicitement
mentionné par le cahier des charges).
**Colonnes sources :** `TRANSACTION_DATE`, `REQUEST_DATE`, `RESPONSE_DATE`
(reconstruites via la fusion date+fraction, section 0).

### 5.4 Features réseau (légères, sans graphe complet)
**Pourquoi :** premières approximations des schémas invisibles en
transaction-par-transaction (mule, fan-in/out), calculables rapidement en
agrégats, en attendant/complément du vrai module graphe.
**Variables :** ratio montant reçu/envoyé (signal mule), délai médian
réception→réexpédition, nombre d'expéditeurs/destinataires distincts,
téléphone partagé entre plusieurs comptes, indicateur sortie GIMTEL (C-09).
**Colonnes sources :** `SOURCE_CUSTOMER`, `DESTINATION_CUSTOMER`,
`SOURCE_PHONE`, `DESTINATION_PHONE` (positions réelles, cf. schema_map),
`DESTINATION_CUSTOMER` rempli = externe GIMTEL.

### 5.5 Features canal
**Pourquoi :** capte directement C-08 (changement de canal après seuil
atteint) et alimente le critère "diversité" du score de valeur.
**Variables :** nombre de canaux distincts sur 7 jours, indicateur de
changement de canal juste après avoir atteint le seuil sur le canal
précédent.
**Colonnes sources :** `CHANNEL_TYPE` (confiance basse dans le mapping
actuel — à revalider en priorité, cf. section 0).

### 5.6 Features budget (volet B)
**Pourquoi :** volet obligatoire à part entière (15 % de la note), et
alimente aussi les features de seuil ci-dessus côté transaction.
**Variables :** consommation jour/mois par client×service, tous canaux
additionnés, taux de consommation, reste disponible, niveau d'alerte.
**Colonnes sources :** `TRANSACTION_AMOUNT`, `SERVICE_CODE`,
`TRANSACTION_DATE`, `CHANNEL_TYPE` + `seuils_services.csv`.

### 5.7 Features graphe (bonus, poids fort dans le barème — 20 %)
**Pourquoi :** seule catégorie capable de capter C-02 à C-06 et C-09,
explicitement décrits comme invisibles en transaction-par-transaction.
**Variables :** score mule, pass-through ratio et délai, percentile de
degré entrant/sortant, appartenance à une chaîne de rebond et sa longueur,
appartenance à un circuit fermé, score de fractionnement multi-comptes.
**Colonnes sources :** l'edgelist construite à partir de toutes les
transactions (comptes = nœuds).

### 5.8 Features GIMTEL (interne/externe)
**Pourquoi :** distinction explicitement soulignée deux fois dans le
cahier des charges comme clé de lecture — un fraudeur peut sortir vers
GIMTEL pour brouiller la piste.
**Variables :** `is_external_gimtel` (dérivée de `DESTINATION_CUSTOMER`
rempli/vide), fréquence de sorties GIMTEL récentes du client, montant
cumulé sorti vers GIMTEL sur 24h/7j.
**Colonnes sources :** `DESTINATION_CUSTOMER` — position à confiance
`medium` dans le mapping actuel, à revalider avant de bâtir dessus (c'est
une colonne pivot, une erreur ici fausserait toute la lecture GIMTEL).

### 5.9 Features historiques / profil client (volet C)
**Pourquoi :** alimente les critères "Profil" (100 pts, risque) et
"Ancienneté" (100 pts, valeur) et "Historique d'alertes" (150 pts, risque).
**Variables :** ancienneté de la relation (première transaction observée),
nombre total d'alertes générées (depuis `budget/alert_engine.py`),
récence de la dernière alerte, complétude KYC si disponible dans une
colonne exploitable.
**Colonnes sources :** min(`TRANSACTION_DATE`) par client, historique
d'alertes calculé section 5.6.

---

## 6. Pipeline de validation

**Trois pièges explicitement listés par le cahier des charges, et comment
on les évite :**

1. **Data leakage temporel** ("calculer les habitudes d'un client avec des
   données futures") → toute feature "historique client" est calculée en
   **expanding window strictement antérieure** à `TRANSACTION_DATE` de la
   ligne courante. Contrôlé automatiquement par
   `validation/leakage_checks.py`, qui échoue explicitement (pas un warning
   silencieux) si une feature viole cette propriété sur un échantillon de
   contrôle.
2. **Erreurs temporelles / découpage aléatoire** ("jamais de découpage
   aléatoire, le modèle verrait le futur") → **validation glissante
   walk-forward** (rolling-origin), jamais de `train_test_split(shuffle=True)`.
3. **Mauvais split** (fuite entre les fenêtres glissantes de features et la
   période de validation) → un **embargo** est inséré entre la fin de la
   fenêtre d'entraînement et le début de la validation, de durée au moins
   égale à la plus longue fenêtre de feature utilisée (7 jours). Sans cet
   embargo, une transaction de validation très proche de la frontière
   "verrait" indirectement des transactions d'entraînement dans ses
   compteurs glissants — un leakage subtil mais réel.

**Schéma retenu : validation croisée temporelle à 3 replis (walk-forward),
holdout final sur la dernière tranche.**

```
Temps  ─────────────────────────────────────────────────────►
        [ train F1 ][emb][val F1]
        [   train F2    ][emb][val F2]
        [      train F3      ][emb][val F3]
        [           train complet          ][emb][ TEST FINAL (jamais tuné dessus) ]
```

**Calage sur la plage réelle des données (confirmé par l'audit complet,
section 0) :** le fichier couvre juin 2022 → juillet 2026, avec ~75 % du
volume concentré sur 2025-2026 (37k lignes en 2022, 102k en 2023, 295k en
2024, 717k en 2025, 477k déjà sur les 6,5 premiers mois de 2026). Les
années 2022-2023, à faible volume et sur un système probablement moins
mature, servent surtout de **période de préchauffage** pour les features
historiques (ancienneté, expanding windows) plutôt que de véritable fenêtre
de validation. Recommandation concrète : caler les 3 replis glissants dans
la fenêtre 2024-2026 (ex. val F1 = un mois de mi-2025, val F2 = fin 2025,
val F3 = début-mi 2026), avec le dernier mois disponible (ou le fichier de
test officiel une fois reçu) comme holdout final jamais utilisé pour le
tuning. Les 63 lignes datées de 2003 (anomalie confirmée, cf. section 0)
sont mises en quarantaine par `ingestion/loader.py` avant tout calcul de
fenêtre — une seule ligne mal datée dans une fenêtre expanding suffirait à
fausser tout l'historique "ancien" du client concerné.

**Pourquoi ce choix plutôt qu'un simple split train/test unique :** avec
~1 % de fraude, un split unique donne une estimation d'AUC-PR très
bruitée (peu d'exemples positifs en validation). Trois replis glissants
donnent une estimation plus stable de la performance ET permettent de
vérifier que le modèle ne se dégrade pas dans le temps (dérive de
comportement des fraudeurs) — un signal utile à montrer au jury en
soutenance.

**Métrique de sélection : AUC-PR exclusivement**, jamais l'accuracy — le
cahier des charges le dit noir sur blanc, et c'est mathématiquement évident
avec ~1 % de prévalence (un modèle qui prédit toujours "normal" obtient
~99 % d'accuracy et 0 % de rappel).

---

## 7. Modèles, dans l'ordre, et pourquoi

```
0. Règle "montant / seuil du service" en score continu (rules/business_rules.py)
      │  plancher de référence : si un modèle ne bat pas ça sur l'AUC-PR, il est inutile
      ▼
1. Régression logistique (class_weight="balanced")
      │  rapide à entraîner, coefficients directement interprétables
      │  (utile pour l'explicabilité et pour détecter des features cassées tôt)
      ▼
2. Random Forest
      │  capture les interactions non-linéaires simples, robuste au bruit,
      │  peu d'hyperparamètres à régler — bon point de repère intermédiaire
      ▼
3. CatBoost
      │  premier modèle de boosting essayé : gère nativement les catégorielles
      │  (SERVICE_CODE, CHANNEL_TYPE) sans encodage manuel, bonne stabilité
      │  sur données déséquilibrées — MODÈLE CANDIDAT PAR DÉFAUT pour la
      │  soumission si le temps est serré
      ▼
4. LightGBM
      │  entraînement très rapide sur 1,6M lignes — sert à itérer vite sur
      │  le feature engineering ET de second modèle pour la combinaison ci-dessous
      ▼
5. Comparaison CatBoost vs LightGBM par AUC-PR (validation croisée temporelle)
      ▼
6. Moyenne pondérée simple des deux scores (ex. 0.6×CatBoost + 0.4×LightGBM,
   ou 50/50 si les AUC-PR de validation sont proches)
      │  ne garder cette moyenne que si elle bat le meilleur modèle seul sur
      │  l'AUC-PR de validation — sinon revenir au meilleur modèle seul
      ▼
7. [SEULEMENT SI 1-6 sont solides ET qu'il reste du temps] XGBoost + stacking
      │  voir méthodologie anti-fuite ci-dessous — jamais improvisé en fin de
      │  course, sinon risque de casser un résultat déjà correct
```

**Pourquoi cet ordre précisément :**
- Chaque étape sert de **garde-fou de complexité** : si la régression
  logistique linéaire obtient déjà un excellent AUC-PR, ça signale que le
  signal est majoritairement porté par quelques features fortes (ratio au
  seuil, écart à l'historique) — précieux à savoir pour l'explicabilité et
  pour ne pas sur-investir dans un modèle inutilement complexe en 2 jours.
- **CatBoost avant LightGBM** parce qu'il gère nativement les colonnes
  catégorielles à cardinalité modérée (`SERVICE_CODE` a 12 modalités,
  `CHANNEL_TYPE` quelques-unes) sans encodage manuel, ce qui fait gagner du
  temps de développement — un facteur qui compte sur 2 jours. C'est le
  modèle qui doit être prêt à sortir une soumission valide en premier.
- **LightGBM en second modèle rapide**, pas en remplaçant de CatBoost :
  l'objectif n'est pas de le préférer, mais d'avoir un deuxième point de
  vue suffisamment différent pour qu'une combinaison simple (étape 6) ait
  une chance d'apporter quelque chose.
- **Moyenne pondérée avant stacking** : une moyenne simple des deux scores
  ne demande aucune infrastructure supplémentaire et ne peut pas introduire
  de fuite si elle est calculée sur des scores de validation déjà propres.
  On ne la garde que si elle mesure un gain réel d'AUC-PR — sinon elle
  n'est qu'une complexité inutile.
- **XGBoost et le stacking en tout dernier, et seulement si le temps le
  permet.** Un vrai stacking correct exige des prédictions **hors-fold**
  (chaque modèle de base doit prédire une période qu'il n'a pas vue à
  l'entraînement, avec le même découpage temporel walk-forward que la
  section 6) avant d'entraîner le méta-modèle — sinon le méta-modèle
  apprend sur des prédictions in-sample et le stacking devient lui-même une
  source de fuite, invisible tant que personne ne vérifie. C'est un risque
  d'exécution que l'équipe ne doit prendre qu'après avoir sécurisé un
  modèle simple qui fonctionne et livre les 3 CSV.
- Le modèle final retenu n'est **pas nécessairement le plus complexe** — la
  décision se fait uniquement sur l'AUC-PR en validation temporelle, jamais
  par défaut sur "le modèle le plus sophistiqué".

**Sur le déséquilibre de classes (~1 % de fraude, hypothèse à confirmer
avec les vraies proportions du jeu de données) :** `class_weight`/
`scale_pos_weight` plutôt que du sur-échantillonnage (SMOTE et dérivés),
parce que le sur-échantillonnage sur données temporelles risque de casser
la structure chronologique et d'introduire un leakage indirect (des
copies synthétiques d'une fraude passée peuvent "fuiter" de l'information
vers la période de validation si mal isolées).

**Décision explicite : pas de Graph Neural Network entraîné.** La
littérature montre qu'un GNN capture mieux la coordination entre comptes
qu'un modèle tabulaire pur (ex. gains rapportés par des systèmes de
production comme celui de Visa sur la détection de mules), mais un vrai
pipeline GNN — identifiants de nœuds, échantillonnage de graphe, choix
d'architecture, entraînement, validation temporelle, explicabilité — est
hors de portée en 2 jours sur 1,6M transactions, en plus du reste des
livrables. La solution retenue capture l'essentiel du signal réseau à
moindre risque : construire le graphe (`graph/graph_builder.py`) puis
**transformer ses propriétés en colonnes tabulaires classiques**
(`mule_score`, `pass_through_ratio`, `fan_in_degree_percentile`, etc., déjà
détaillées section 5.7) injectées dans CatBoost/LightGBM. Cette approche
est documentée comme un compromis efficace dans la littérature sur la
détection de fraude en graphe, et correspond exactement à ce que
`graph/graph_features.py` fait déjà dans cette architecture.

---

## 8. Scripts nécessaires

Déjà créés dans `scripts/` (stubs avec docstring de rôle, à implémenter) :

| Script | Rôle |
|---|---|
| `01_audit_schema.py` | Valide/reconstruit `schema_map.yaml` — bloquant, à lancer en premier sur chaque nouveau fichier reçu |
| `02_build_dataset.py` | Ingestion + nettoyage → `transactions_clean.parquet` |
| `03_build_features.py` | Toutes les features non-graphe + budget |
| `04_build_graph_features.py` | Construction graphe + détection mules/patterns |
| `05_train_model.py` | Split, anti-leakage, entraînement, calibration, évaluation |
| `06_predict_fraud.py` | Applique le pipeline complet au jeu de test officiel |
| `07_compute_budget.py` | Consommation d'enveloppes finale (train + test) |
| `08_score_customers.py` | Scores risque/valeur, segments, explications |
| `09_generate_submission.py` | Génère les 3 CSV finaux, valide leur format |
| `run_all.py` | Enchaîne 01 à 09, fail-fast, journalisé |

---

## 9. Dashboard — ce que verra le jury

**Objectif du dashboard : démontrer que la solution est exploitable par
BAMIS, pas juste montrer un score.** Il ne recalcule rien à la volée — il
lit uniquement les fichiers déjà produits par le pipeline batch
(`outputs/`, `data/features/`), pour rester fiable pendant la démo.

**Pages :**

1. **Vue d'ensemble**
   - KPI : nombre de transactions analysées, taux de fraude détecté, AUC-PR
     du modèle, nombre d'alertes actives, nombre de clients en zone
     critique.
   - Courbe précision-rappel du modèle retenu.
   - Histogramme des scores de fraude (distribution, pour montrer que le
     modèle sépare bien les classes).

2. **File d'alertes** (transactions)
   - Table triable/filtrable : score de fraude, service, canal, montant,
     ratio au seuil, statut interne/externe GIMTEL.
   - Filtres : plage de score, plage de dates, service, canal, direction.
   - Clic sur une ligne → explication en 5 facteurs (langage simple).

3. **Fiche client**
   - Score de risque et score de valeur (jauges 0-1000), segment.
   - Top 5 facteurs de chaque score, en phrases lisibles.
   - Historique de consommation de seuil par service (jour/mois).
   - Action recommandée (matrice de traitement).
   - Mini-carte du réseau local du client (voisins directs dans le graphe).

4. **Suivi des enveloppes / seuils**
   - Vue par client×service : consommé / seuil / reste, niveau d'alerte
     (50/80/95/100 %), avec agrégation multi-canal visible explicitement
     (montrer que USSD + appli + agent sont bien additionnés — c'est un
     point de preuve direct contre C-08).

5. **Exploration du graphe** (bonus)
   - Visualisation interactive d'un sous-réseau suspect (mule, chaîne,
     circuit fermé) — le scénario de démonstration s'appuiera dessus
     (voir `GUIDE_SOUTENANCE.md`).

**Choix technique :** Streamlit pour la vitesse de développement en 2
jours (moins de code que Dash pour un résultat présentable), FastAPI en
backend séparé pour garder la logique de requêtage isolée et testable —
mais si le temps manque, un Streamlit monolithique (sans API séparée) est
un repli acceptable qui ne coûte rien sur le barème (le dashboard est
bonus, pas noté sur son architecture interne).

---

## 10. Priorités — budget de 2 jours

Classement direct par poids du barème officiel :

| Critère jury | Poids |
|---|---|
| AUC-PR (détection de fraude) | 30 % |
| Détection contournements/réseaux | 20 % |
| Peu de faux positifs | 15 % |
| Gestion budget/seuils | 15 % |
| Classement client explicable | 15 % |
| Documentation/reproductibilité | 5 % |

**Indispensable (sans ça, il n'y a pas de note) :**
- Audit de schéma (section 0) — bloquant, tout le reste en dépend.
- Ingestion + nettoyage + features seuil + features comportementales
  (5.1, 5.2).
- Split temporel correct + anti-leakage (section 6) — un AUC-PR calculé
  sur un split cassé est pire qu'inutile, il est trompeur.
- Un modèle ML entraîné et calibré, même simple (LR ou RF suffit comme
  filet de sécurité si le temps manque pour le boosting).
- Les 3 fichiers CSV **au format exact demandé**, avec vérification finale
  du format avant remise (`submission/export.py` → validation).
- README + note méthodologique minimale (même 3 pages sobres valent mieux
  que 0 page — c'est 5 % garanti pour un coût de rédaction faible).

**Important (fait gagner des points significatifs) :**
- Features de vélocité et de canal (5.3, 5.5) — accessibles rapidement,
  gain direct sur AUC-PR et sur C-07/C-08.
- Budget engine complet multi-canal (volet B, 15 %) — mécanique, pas de
  recherche requise, donc bon rapport effort/points.
- Scoring client complet avec les 5 pondérations exactes du barème et
  segmentation (volet C, 15 %) — formule additive transparente, rapide à
  implémenter une fois les features prêtes.
- Explicabilité (top 5 facteurs) — obligatoire pour que le classement
  client soit noté ("un score sans explication n'est pas exploitable"), et
  peu coûteuse si les scores sont déjà des sommes pondérées de sous-scores
  nommés.
- CatBoost (modèle candidat par défaut) plutôt que la régression logistique
  seule — l'écart d'AUC-PR justifie l'investissement si le temps le permet.
  Dès que CatBoost tourne et produit une soumission valide, c'est le
  premier filet de sécurité "ML correct" de l'équipe — sécurisé avant de
  toucher à quoi que ce soit d'autre en modélisation.

**Bonus (différenciant mais après le reste sécurisé) :**
- Module graphe complet (mule + patterns) — 20 % du barème, donc
  potentiellement très rentable, mais seulement une fois les livrables
  obligatoires solides. Un mule scoring simple (pass-through ratio) est
  déjà utile même sans détection de chaînes/circuits complète. Ces scores
  restent des **features tabulaires** injectées dans CatBoost (voir
  décision section 7) — pas d'entraînement de GNN.
- LightGBM en second modèle + moyenne pondérée simple avec CatBoost (voir
  section 7, étapes 4-6) — ne garder que si elle mesure un gain d'AUC-PR
  réel en validation, sinon revenir à CatBoost seul.
- Dashboard interactif — aide énormément à la soutenance mais ne rapporte
  aucun point isolé au barème écrit ; sa valeur est dans l'impression
  laissée au jury en démo.
- `threshold_recommender.py` (seuil adaptatif selon risque) — bonus
  explicitement signalé comme optionnel dans le cahier des charges.

**Abandonnable si le temps manque :**
- XGBoost et tout stacking à méta-modèle (voir section 7, étape 7) — le
  stacking mal fait (sans prédictions hors-fold correctement isolées dans
  le temps) est une source de fuite silencieuse ; ne pas l'improviser en
  fin de course sous pression, il vaut mieux livrer CatBoost seul (ou
  CatBoost + moyenne LightGBM) proprement calibré.
- Détection exhaustive de tous les patterns graphe (C-03 à C-06, C-10) —
  se concentrer sur mule (C-02) et fan-in/fan-out (C-03/C-04) qui sont les
  plus simples à implémenter et les plus visuellement démontrables ;
  chaînes et circuits fermés (C-05/C-06) demandent plus de temps pour un
  gain marginal si la démo montre déjà un cas mule convaincant.
- API FastAPI séparée pour le dashboard — Streamlit seul suffit.
- `graph/pattern_detection.py` : la fonction `detect_closed_circuits` peut
  être la première sacrifiée (les circuits fermés sont rares et coûteux à
  détecter exhaustivement, contrairement au fan-in/fan-out qui est un
  simple calcul de degré).

**Piège à ne pas commettre (explicitement listé dans le cahier des
charges, à afficher au-dessus de l'écran de l'équipe) :** ne pas
"consacrer tout le temps au Machine Learning et négliger les autres
critères" — 70 % du barème n'est PAS le modèle ML. Un modèle moyen avec un
volet B et un volet C complets et bien expliqués rapporte plus qu'un
modèle superbement tuné livré sans classement client exploitable.

---

## 11. Ce qui reste à faire avant le premier entraînement

1. Lancer `scripts/01_audit_schema.py` sur l'intégralité du fichier réel
   (pas l'échantillon utilisé pour ce document) et corriger
   `configs/schema_map.yaml` si l'inférence diverge à grande échelle.
2. Confirmer avec les organisateurs (ou dans un fichier complémentaire non
   encore trouvé) : le vrai `seuils_services.csv`, le nom exact de la
   colonne cible de fraude dans le train, la structure du fichier de test.
3. Implémenter `ingestion/loader.py` en s'appuyant sur le mapping validé —
   première ligne de code du projet.
4. Une fois `transactions_clean.parquet` obtenu, relire ce document et
   ajuster les hypothèses de fenêtres temporelles (section 5.3) selon la
   plage réelle de dates couverte par le jeu de données.
