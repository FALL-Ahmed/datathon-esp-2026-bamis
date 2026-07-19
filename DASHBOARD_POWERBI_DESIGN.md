# Refonte dashboard — Centre de supervision anti-fraude BAMIS (cible Power BI)

Document de conception pour la refonte du dashboard, en remplacement de la version
HTML/CSS/JS actuelle. Objectif : un produit qui donne l'impression d'un outil déjà
déployé en banque (référence : Visa Fraud Center, Mastercard Risk Platform, Stripe
Radar, Splunk, Datadog), réalisable sans effet impossible sous Power BI.

**Statut des données utilisées ici : tout ce qui suit s'appuie sur les colonnes
réellement validées dans `configs/schema_map.yaml` et les fichiers déjà produits par
le pipeline (`data/features/*.parquet`, `data/graph/*.parquet`). Quand une donnée
n'existe pas encore (ex. région/agence), c'est signalé explicitement — pas de
visualisation proposée sur une hypothèse non vérifiée.**

---

## 1. Critique du dashboard actuel (HTML)

Ce qui donne un effet "étudiant" plutôt que "logiciel professionnel" :

1. **Aucune hiérarchie d'urgence.** Les 7 cartes KPI ont toutes le même poids visuel
   — "Zone critique : 42" est aussi discret que "Transactions analysées : 1 627 622".
   Dans un centre de supervision, l'œil doit tomber sur l'urgent en moins d'une
   seconde. Rien ne joue ce rôle aujourd'hui.
2. **Pas d'effet "système vivant".** Aucun indicateur de synchronisation, aucun
   compteur qui bouge, aucune notion de débit (tx/minute). Le dashboard a l'air d'un
   rapport figé, pas d'une console qui tourne en continu.
3. **La liste d'alertes est un tableau, pas un flux.** Les lignes sont plates, toutes
   identiques visuellement à part une pastille de score. Un vrai SOC affiche un flux
   compact où la sévérité saute aux yeux avant même de lire le texte.
4. **L'explicabilité IA est déconnectée des alertes.** Le "pourquoi" n'apparaît que
   dans la fiche client (volet C), jamais au moment où l'analyste regarde une
   transaction suspecte dans la file d'alertes — c'est pourtant le moment où la
   question se pose.
5. **Aucune carte de chaleur, aucun graphe réseau visible.** Le module graphe (mules,
   fan-in/fan-out, circuits fermés) est le livrable bonus le plus impressionnant du
   projet (20 % du barème) et il n'apparaît **nulle part** sur le dashboard
   actuellement. C'est l'angle mort le plus coûteux du design actuel.
6. **Aucune tendance temporelle.** Tout est un instantané. Le jury ne peut pas voir
   si la fraude augmente, diminue, ou réagit à une contre-mesure.
7. **Le scoring de valeur client (Bronze/Argent/Or/Platine) est traité à égalité avec
   le risque.** C'est une info de fidélisation marketing, pas un signal de fraude —
   lui donner la moitié de l'écran principal dilue le narratif "sécurité".
8. **Espace mal utilisé.** Le pied de sidebar ("Datathon ESP DATACLUB 2026...") est
   du texte mort ; cet espace devrait porter un indicateur vivant (état du modèle,
   uptime, dernière synchro).

**Ce qui doit devenir l'élément principal :** la file d'alertes temps réel couplée au
panneau d'explicabilité IA (colonne gauche + colonne droite, côte à côte, jamais deux
clics de distance) — c'est le cœur d'un outil de détection de fraude, pas un
graphique de répartition.

**Ce qui doit être supprimé ou relégué en second plan :** la segmentation de valeur
client (Bronze→Platine) passe en widget secondaire, petit, en bas de page.

**Ce qui manque et doit être ajouté :** graphe réseau des comptes suspects, carte de
chaleur (voir contrainte de données en §7), courbes de tendance, explicabilité en
ligne dans le flux d'alertes.

---

## 2. Wireframe (page 16:9, ~1920×1080)

```
┌───────────────────────────────────────────────────────────────────────────────────────┐
│ [Logo BAMIS]  CENTRE DE SUPERVISION ANTI-FRAUDE     ● Système actif · CatBoost v1       │
│                                                       Synchro : il y a 4s                │
│ [Période ▾] [Canal ▾] [Segment ▾]                🔔 3        Mar 20 juil 2026 · 14:03    │
├───────────────────────────────────────────────────────────────────────────────────────┤
│ ┌────────────────┐┌──────────┐┌──────────┐┌──────────┐┌──────────┐┌──────────┐          │
│ │ ⚠ ALERTES      ││    TX    ││ FRAUDES  ││ MONTANT  ││  SCORE   ││    TX    │          │
│ │ CRITIQUES      ││ ANALYSÉES││ DÉTECTÉES││ PROTÉGÉ  ││  MODÈLE  ││ BLOQUÉES │          │
│ │                ││          ││          ││          ││          ││          │          │
│ │      42        ││1 627 622 ││  0,47 %  ││ 12,4 M   ││  91,4    ││   554    │          │
│ │  ▂▄▆█ (rouge)  ││          ││          ││   MRU    ││ AUC-PR   ││          │          │
│ └────────────────┘└──────────┘└──────────┘└──────────┘└──────────┘└──────────┘          │
│   2x plus large        gris       orange      vert       jauge        gris              │
├─────────────────────────────────────────────┬───────────────────────────────────────────┤
│ MONITORING TEMPS RÉEL                        │ POURQUOI CETTE ALERTE ?                  │
│ ───────────────────────────────────────────  │ Transaction #476054 sélectionnée         │
│ 14:03 #476054 TEL174003  250 000 MRU         │                                           │
│       ▐███▌ 4/7          [BLOQUÉE]           │            ╭──────────╮                  │
│ ───────────────────────────────────────────  │            │  98/100  │  Score IA         │
│ 14:02 #625152 TEL070001  55 500 MRU          │            ╰──────────╯                  │
│       ▐██▌  3/7        [EN ATTENTE]          │                                           │
│ ───────────────────────────────────────────  │ ✓ Montant inhabituel (+6,3 écarts-type)  │
│ 14:01 #232100 TEL115208 300 000 MRU          │ ✓ Horaire nocturne hors norme             │
│       ▐███▌ 4/7          [BLOQUÉE]           │ ✓ Profil mule (94,9 % pass-through)       │
│ ───────────────────────────────────────────  │ ✓ Dépassement seuil unitaire              │
│  ... (flux, pas une grille figée)            │ ✗ Nouveau téléphone                       │
│                                               │                                           │
│                                               │ Action recommandée : GEL + INVESTIGATION │
├───────────────────────────────────────────┬─────────────────────────────────────────────┤
│ INTENSITÉ FRAUDE — SERVICE × HEURE          │ RÉSEAU DE COMPTES SUSPECTS                 │
│ SERVICE_10 ██▓▓░░░░▓▓██▓▓░░░░░░░░░░░░░░░░  │        ●───●                                │
│ SERVICE_04 ░░░░▓▓░░░░░░▓▓░░░░░░░░░░░░░░░░  │       ╱     ╲    ● = mule (rouge)          │
│ SERVICE_01 ░░░░░░░░▓▓░░░░░░▓▓░░░░░░░░░░░░  │      ●───●───●   ─ = flux normal (gris)    │
│            0h          12h          23h     │           ╲ ╱    ▲ = circuit fermé         │
│                                               │            ●                              │
├───────────────────────────────────────────┴─────────────────────────────────────────────┤
│ ÉVOLUTION (7j / 30j / 12 mois) │ TOP RISQUE (client)  │ TOP MULES         │ VALEUR (mini) │
│  ╱╲___╱╲__╱‾╲__ fraude détectée│ TEL039808  863 ⬤     │ TEL093693  94,9%  │ Bronze  53%   │
│                                 │ TEL090022  854 ⬤     │ TEL043899  rafale │ Argent  21%   │
└───────────────────────────────────────────────────────────────────────────────────────┘
```

Découpage en 4 bandes horizontales sur une page Power BI unique :
- **Bande 1 (haut, ~6 % de la hauteur)** : en-tête + filtres.
- **Bande 2 (~18 %)** : bandeau KPI, carte "Alertes critiques" deux fois plus large
  que les autres.
- **Bande 3 (~45 %, la plus grande)** : flux d'alertes (gauche, 60 %) + explicabilité
  IA (droite, 40 %) — c'est le cœur de l'écran.
- **Bande 4 (~25 %)** : heatmap service×heure (gauche) + graphe réseau (droite).
- **Bande 5 (~12 %, bas)** : tendances + listes top (secondaire, densité réduite).

---

## 3. KPI

### Primaires (bandeau du haut)
| KPI | Source réelle | Remarque |
|---|---|---|
| Alertes critiques (hero, rouge) | `customer_risk_value_scores.segment_risque == "Critique"` + `budget_alerts.niveau_alerte == "100%"` | Élément visuellement dominant, 2x la largeur des autres |
| Transactions analysées | `transactions_clean` (count) | |
| Taux de fraude détecté | `rule_flags.pseudo_label_fraud` (moyenne) | Toujours préciser "pseudo-label, règles métier" en sous-texte — jamais présenté comme une vérité terrain |
| Montant protégé (MRU) | somme des montants des tx avec action = BLOQUÉE | Équivalent du "$ blocked" de Stripe Radar — très fintech |
| Score du modèle (AUC-PR) | `training_metrics.json` | Jauge (0–1), pas juste un chiffre |
| Transactions bloquées | count des tx avec décision = blocage | |

### Secondaires (bande basse)
Top clients à risque, top comptes mules (`mule_score`), répartition des paliers de
valeur (Bronze/Argent/Or/Platine — volontairement petit, non prioritaire).

---

## 4. Mapping visualisations Power BI

| Zone | Visuel Power BI | Faisabilité |
|---|---|---|
| Cartes KPI | `Card` / `KPI` natif, mise en forme conditionnelle sur la couleur de fond | Native, 100 % faisable |
| Score modèle | `Gauge` natif | Native |
| Flux d'alertes | `Table` natif, stylé en feed : bordures minimales, hauteur de ligne augmentée, barres de données (data bars) sur la colonne montant, couleur de fond conditionnelle par score | Natif mais demande un réglage fin — Power BI ne fera jamais un vrai composant "card feed" React ; c'est la limite honnête à annoncer |
| Explicabilité IA | **Page de drillthrough** déclenchée par clic sur une ligne du flux | Native, et c'est justement le genre d'interaction qu'un dashboard étudiant n'utilise jamais — fort effet "produit pro" |
| Heatmap service×heure | `Matrix` natif + mise en forme conditionnelle (dégradé de couleur) | Native, 100 % faisable avec les données réelles disponibles |
| Réseau de comptes suspects | Visuel personnalisé **Force-Directed Graph** ou **Network Navigator** (AppSource, gratuits) alimentés par `data/graph/edgelist.parquet` + `mule_scores.parquet` | Faisable si les visuels personnalisés sont autorisés. **Repli si interdits** : image statique pré-rendue (networkx/matplotlib, déjà générable en Python) insérée comme image, régénérée à chaque run pipeline — annoncer les deux options au jury, pas de fausse promesse |
| Tendances | `Line chart` / `Area chart` natif | Native |
| Top listes | `Bar chart` horizontal natif | Native |

---

## 5. Palette (reprend la palette déjà validée contraste/daltonisme du dashboard HTML — pas de nouveau risque)

| Rôle | Hex |
|---|---|
| Fond clair | `#F4F3EF` |
| Blanc (cartes) | `#FFFFFF` |
| Texte primaire (noir) | `#14140F` |
| Texte secondaire (gris) | `#6B6A63` |
| Accent BAMIS (orange) | `#EB6834` |
| Alerte (rouge — uniquement alertes) | `#B8281F` |
| OK (vert — uniquement statuts normaux) | `#1A8C1A` |

Aucune autre couleur. Le rouge et le vert ne doivent JAMAIS être utilisés pour autre
chose qu'une alerte / un statut OK (règle stricte demandée).

---

## 6. Typographie

**Segoe UI** partout (police native Power BI/Windows — zéro risque de rendu cassé en
démo live, contrairement à une police custom qui doit être embarquée). Regular pour
le texte, Semibold pour les chiffres KPI et les titres de section. Beaucoup d'espace
blanc entre les blocs, pas de texte de remplissage.

---

## 7. Contrainte de données à annoncer honnêtement

- **Carte de chaleur par région/agence : PAS FAISABLE avec les données actuelles.**
  Aucune colonne région/agence n'existe dans `schema_map.yaml` — vérifié, pas supposé.
  `CHANNEL_TYPE_candidate` existe mais est documenté comme non validé (priorité 2 en
  attente de revalidation).
  → **Remplacement réel et honnête : heatmap Service × Heure**, construite sur
  `SERVICE_CODE` et `TRANSACTION_DATE`, deux colonnes confirmées à 100 % fiables.
- **Graphe réseau : disponible et déjà calculé** (`data/graph/edgelist.parquet`,
  `mule_scores.parquet`, `closed_circuits.parquet` — 24 637 circuits détectés). C'est
  la donnée la plus prête à être mise en avant et actuellement la plus invisible.

---

## 8. Interactions

- **Cross-filtering natif** : cliquer une cellule de la heatmap filtre le flux
  d'alertes sur ce service/heure.
- **Drillthrough** : clic sur une ligne d'alerte → page "Fiche transaction"
  (explicabilité). Clic sur un client dans le top risque → page "Fiche client" (texte
  d'explication déjà généré par `scoring/explainability.py`, réutilisable tel quel).
- **Tooltips personnalisés** : survol d'un nœud du graphe réseau → ID client, rôle
  (mule / fan-in / fan-out), score.
- **Slicers** compacts dans l'en-tête : période, canal, segment de risque — jamais au
  milieu du canevas principal.
- **Bookmarks** : bouton "Vue temps réel" / "Vue analyse" pour basculer entre
  emphase flux live et emphase tendances/réseau — donne un effet de mode applicatif.

---

## 9. Animations/effets réalistes

- **Actualisation automatique de page** (5–15s) pour un effet de flux vivant sans
  infrastructure de streaming.
- **Transition bookmark** (fondu/push) entre les deux vues.
- Sparklines natives sur les cartes KPI (légère tendance intégrée).
- Pas de vraie animation "pulse" native — l'effet d'urgence vient du contraste
  visuel (carte 2x plus grande, rouge, bordure épaisse), pas d'un effet CSS impossible
  à reproduire.

---

## 10. Prochaine étape suggérée

Ce document est une spécification, pas un fichier `.pbix`. Décision à prendre :
construire réellement sous Power BI (nécessite Power BI Desktop + les mêmes fichiers
parquet exportés en CSV/format compatible) ou continuer sur la version HTML déjà
fonctionnelle en lui appliquant cette même structure. Les deux sont valables — le
choix dépend du temps restant avant la remise.
