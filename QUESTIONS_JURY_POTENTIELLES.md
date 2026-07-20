# Questions potentielles du jury — checklist complète

> Document de préparation interne, complément à `GUIDE_SOUTENANCE.md`.
> **Ce n'est pas un livrable.** Contrairement à `GUIDE_SOUTENANCE.md` (6
> questions très probables, avec réponse courte + longue entièrement
> rédigées), ce fichier couvre le champ large : toutes les questions
> plausibles sur l'ensemble du projet, avec une piste de réponse courte
> (1-3 phrases) pour ne jamais être pris au dépourvu. Vu le format réel
> (4 minutes de questions seulement), le jury n'en posera que 2-4 —
> l'objectif ici est d'être prêt pour n'importe laquelle, pas de toutes
> les réciter.
>
> ★ = très probable (déjà traité en détail dans `GUIDE_SOUTENANCE.md`,
> juste un renvoi ici) · sans étoile = possible, réponse courte fournie.

## A. Préparation des données

**Comment avez-vous découvert que le fichier avait 26 colonnes au lieu
des 23 annoncées ?**
> Audit statistique par position (`schema_audit.py`) : on a compté le
> nombre de champs réels par ligne sur les 1,6M lignes plutôt que de
> faire confiance au dictionnaire de données, et inféré le type de
> chaque colonne (motif téléphone, date, montant...) pour reconstruire
> le vrai mapping.

**Comment avez-vous géré les 63 lignes à date aberrante et les 72 à
montant aberrant ?**
> Mises en quarantaine avant tout calcul (`preprocessing/cleaning.py`) —
> une seule valeur aberrante dans un historique client suffit à fausser
> tous les indicateurs comportementaux qui en dépendent.

**Pourquoi ne pas avoir utilisé `CHANNEL_TYPE` alors que c'est une
colonne citée comme importante par le cahier des charges ?**
> Vérifiée et jugée à confiance basse dans `schema_map.yaml` (38-51 % de
> vides irréguliers, même cause que le décalage de colonnes) — on a
> préféré ne pas construire de règle sur une donnée qu'on ne peut pas
> garantir plutôt que de bâtir un signal non fiable. Conséquence
> assumée : C-08 (changement de canal) n'est pas détecté spécifiquement.

**Comment distinguez-vous une transaction interne (BAMIS-BAMIS) d'une
transaction externe (GIMTEL) ?**
> Sur `DESTINATION_CUSTOMER` : vide = interne, rempli = externe via
> GIMTEL, exactement comme précisé dans le cahier des charges.

**Que faites-vous des transactions rejetées ou en attente
(`TRANSACTION_STATUS`) ?**
> Un flag `is_validated` les exclut de tous les cumuls réels (budget,
> vélocité) — une transaction rejetée n'a jamais fait bouger d'argent.

## B. Volet A — règles, modèle, graphe

★ **Pourquoi CatBoost et pas XGBoost/LightGBM/Random Forest ?** →
`GUIDE_SOUTENANCE.md`, réponse déjà rédigée (ordered boosting contre
l'étiquette imparfaite, peu de réglage, comparé chiffré 0,91 vs 0,42 vs
0,31).

★ **Comment avez-vous construit le pseudo-label sans vérité terrain ?**
→ `GUIDE_SOUTENANCE.md` (≥2 règles déclenchées = exemple de fraude,
0,47 % des transactions).

**Comment évitez-vous la fuite de données (leakage) ?**
> Trois niveaux : split walk-forward jamais aléatoire, embargo de 7
> jours entre train et validation, et exclusion explicite des flags de
> règles des variables d'entrée du modèle (sinon il recopierait
> trivialement la formule du pseudo-label). Contrôles automatiques qui
> font échouer le pipeline en cas de problème (`leakage_checks.py`,
> testé par `tests/test_leakage_checks.py`).

**À quelle fréquence recommandez-vous de réentraîner le modèle ?**
> Pas de recommandation chiffrée testée — limite assumée. Piste
> raisonnable : mensuel, aligné sur le cycle de calcul du seuil
> budgétaire, à valider avec BAMIS selon la vitesse réelle d'évolution
> des patterns de fraude.

**Comment gérez-vous le déséquilibre de classes (~0,5 % de fraude) ?**
> Aucun sur-échantillonnage (SMOTE) — CatBoost gère le déséquilibre
> nativement via sa fonction de perte, et un ré-échantillonnage aurait
> ajouté un risque de fuite temporelle supplémentaire à documenter.

**Le score est-il une vraie probabilité calibrée ou juste un score de
classement ?**
> Non calibré au sens probabiliste strict — limite assumée
> explicitement dans `NOTE_METHODOLOGIQUE.md` section 8. Sans
> conséquence sur l'AUC-PR (qui ne dépend que du classement), mais à
> signaler si le score doit être interprété comme une vraie probabilité.

**Pourquoi l'AUC-PR en validation croisée (0,76) est si différent du
holdout final (0,91) ?**
> Variance élevée attendue : chaque repli de validation croisée ne
> contient qu'une poignée de cas positifs (replis individuels : 0,48 /
> 0,93 / 0,87), alors que le holdout final concentre 554 cas positifs
> sur 212 222 exemples — échantillon plus stable statistiquement.

**Le modèle explique-t-il ses décisions (SHAP, feature importance) ou
seulement les règles ?**
> L'explicabilité chiffrée vient des règles (5 facteurs pondérés,
> `explainability.py`) et du score de risque volet C. Pas d'analyse SHAP
> formelle sur CatBoost lui-même — amélioration possible listée en
> section 9 de `NOTE_METHODOLOGIQUE.md`.

**Comment le module graphe scalerait-il avec 10x plus de transactions ?**
> Le point sensible identifié et déjà corrigé : la détection de circuits
> fermés utilisait initialement un self-join classique qui produisait un
> produit croisé (plantage mémoire sur une paire à 10 584 transactions),
> remplacé par `merge_asof` — passe de "plante" à 10 secondes sur 1,36M
> transactions. La même logique reste O(n log n), donc scalable.

**Pourquoi limiter la détection de circuits à une boucle A→B→A (longueur
2) et pas des chaînes plus longues ?**
> Limite de temps assumée (section 8 de `NOTE_METHODOLOGIQUE.md`) : les
> chaînes 3+ sauts (C-05) demandent d'explorer des chemins sur 163 000
> comptes, un coût de calcul nettement supérieur pour un gain marginal
> jugé plus faible dans le temps disponible.

**Sur combien d'événements minimum un compte est-il considéré comme
mule ?**
> Le score de mule pénalise volontairement les événements isolés — un
> compte avec un seul pass-through pèse peu (`n_quick_passthrough=1`),
> le score croît avec `log(1 + nb occurrences)` pour privilégier la
> répétition plutôt qu'un seul événement (voir test
> `tests/test_graph_detection.py` qui vérifie exactement ce
> comportement).

## C. Volet B — gestion budget et seuils

**Comment le seuil mensuel est-il calculé puisqu'aucun seuil mensuel
officiel n'existe dans le fichier fourni ?**
> Estimé à 30× le seuil journalier (`budget/budget_engine.py`),
> hypothèse documentée et assumée, à remplacer immédiatement si BAMIS
> fournit un vrai seuil mensuel — jamais présenté comme une valeur
> officielle.

**Un client qui dépasse son seuil est-il bloqué automatiquement ou
seulement signalé ?**
> Le pipeline signale (alertes à 50/80/95/100 %) — la décision de
> blocage effectif reste une politique métier à la main de BAMIS, pas
> automatisée dans cette solution.

**Comment gérez-vous le fractionnement réparti sur plusieurs comptes du
même client (C-10) ?**
> Non couvert — limite assumée. Techniquement faisable via le module
> graphe (regrouper les comptes qui partagent un même bénéficiaire
> récurrent ou un pattern temporel synchronisé), mais pas implémenté
> faute de temps.

**Les seuils recommandés (bonus) sont-ils recalculés en temps réel ?**
> Non, en batch — recalculés à chaque exécution du pipeline
> (`scripts/bonus_recommend_thresholds.py`), pas de mise à jour
> transaction par transaction.

## D. Volet C — classement client

**Pourquoi utiliser le maximum plutôt que la moyenne au sein d'un
sous-critère combinant plusieurs indicateurs ?**
> Un client extrême sur un seul indicateur fort ne doit pas être dilué
> par ses autres indicateurs normaux — vérifié empiriquement, documenté
> dans `NOTE_METHODOLOGIQUE.md` section 4.

**Le score d'un client peut-il redescendre après avoir été classé
"Critique" ?**
> Oui en théorie — le score est recalculé à chaque exécution du pipeline
> à partir de l'historique complet à date, pas un état persistant qui ne
> ferait qu'augmenter. Pas de mécanisme de "decay" temporel testé
> spécifiquement.

★ **Pourquoi 175 689 clients dans `classement_clients.csv` alors que
seuls 40 866 ont émis une transaction ?** → déjà expliqué en détail dans
`ARCHITECTURE.md` et `NOTE_METHODOLOGIQUE.md` section 4 : population
étendue à tous les comptes vus (source OU destination) pour détecter les
comptes purement collecteurs (fan-in, C-03).

**Comment traitez-vous un nouveau client sans historique (cold start) ?**
> Ses indicateurs comportementaux (écart à son historique propre) sont
> non calculables à la première transaction — `behavioral_features.py`
> le signale explicitement (2,51 % des transactions sont "sans
> historique"). Pas de règle spéciale cold-start au-delà de ça, limite
> non creusée davantage faute de temps.

## E. Validation et méthodologie

**Pourquoi un split à 3 replis et pas 5 ou 10 ?**
> Compromis temps/robustesse avec un budget de 2 jours — 3 replis
> suffisent à observer la variance (visible dans l'écart-type de
> l'AUC-PR CV) sans multiplier le temps d'entraînement.

**Pourquoi un embargo de 7 jours précisément ?**
> Marge de sécurité pour couvrir le délai possible de clôture différée
> d'un indicateur cumulatif (ex. cumul journalier calculé a posteriori)
> — valeur ronde et prudente, pas optimisée finement.

**Comment savez-vous que le modèle ne va pas se dégrader avec le temps
(data drift) ?**
> Pas de mécanisme de suivi de drift implémenté — limite assumée. Le
> holdout final (période la plus récente, jamais vue) sert de test
> partiel de robustesse temporelle, mais un vrai monitoring de
> production reste à construire.

## F. Limites déjà documentées (à assumer sans détour si posées)

★ **Si le jury a une vraie vérité terrain différente de votre
pseudo-label, votre 0,91 tiendrait-il ?** → `GUIDE_SOUTENANCE.md`,
réponse déjà rédigée ("on ne peut pas être sûrs à 100%, ce qu'on peut
montrer c'est la cohérence croisée règles/scores").

**Le bug dans `network_features.py` — quel a été l'impact réel sur le
modèle ?**
> Mesuré, pas supposé : les deux colonnes touchées
> (`nb_expediteurs_distincts_past` / `nb_destinataires_distincts_past`)
> ont été retirées de `FEATURE_COLUMNS` et le modèle réentraîné le
> 2026-07-20. Résultat : AUC-PR holdout quasi identique (0,9139 → 0,9130,
> écart de 0,0009, dans le bruit) — ces deux variables ne portaient pas
> de signal utile, leur suppression n'a rien coûté au modèle.

★ **D'où viennent vos multiplicateurs de seuil (×1.5, ×0.7...) ?** →
`GUIDE_SOUTENANCE.md`, réponse déjà rédigée.

## G. Bonus, dashboard, reproductibilité

**Le dashboard est-il connecté en temps réel aux données ou c'est un
export statique ?**
> Export statique généré par `dashboard/export_data.py` à partir des
> vrais fichiers de sortie du pipeline — pas de connexion live à une
> base de données. Assumé et adapté au contexte datathon (pas
> d'infrastructure de production).

**Comment le jury peut-il relancer votre pipeline de bout en bout ?**
> Une seule commande, `python scripts/run_all.py`, teste de bout en bout
> le 2026-07-19 (13 minutes, exit code 0) — 10 étapes enchaînées,
> s'arrête au premier échec. Détail dans `README.md` section 3.

**Combien de temps prend l'entraînement complet, et est-ce reproductible
à l'identique ?**
> Quelques minutes (validation croisée + entraînement final). Seed fixée
> (`random_seed: 42` partout, `utils/seed.py`) pour la reproductibilité
> — mêmes résultats à chaque exécution sur la même machine/version de
> CatBoost.

**Pourquoi Python plutôt qu'un autre langage ou un outil no-code ?**
> Écosystème data science standard (pandas, scikit-learn, CatBoost,
> NetworkX pour le graphe) — permet règles, ML et graphe dans un seul
> pipeline cohérent et testable, avec des bibliothèques matures pour
> chaque niveau demandé par le cahier des charges.

## H. Questions "pièges" génériques (à anticiper même sans réponse
chiffrée)

**Si BAMIS vous donnait accès aux vraies fraudes confirmées, combien de
temps pour réentraîner et valider ?**
> Le pipeline est déjà prêt pour ça : remplacer le pseudo-label par les
> vraies étiquettes dans `modeling/train.py` ne change pas
> l'architecture, juste la colonne cible — réentraînement en quelques
> minutes une fois les données reçues.

**Avez-vous chiffré le coût d'un faux positif vs un faux négatif pour
BAMIS ?**
> Non chiffré en MRU — limite assumée. La table précision/rappel à
> plusieurs seuils (`NOTE_METHODOLOGIQUE.md` section 7) donne le nombre
> d'alertes générées par seuil, ce qui permet à BAMIS de faire cet
> arbitrage métier eux-mêmes selon leur coût réel de traitement d'une
> alerte.

**Comment votre solution s'adapterait-elle à un nouveau service
(SERVICE_13) ajouté demain ?**
> Directement — les seuils sont lus depuis `seuils_services.csv` (jamais
> en dur), il suffit d'ajouter une ligne pour ce service ; aucune
> variable ni règle n'est codée en dur par nom de service.

**Qu'est-ce qui vous a le plus surpris dans les données ?**
> Le décalage de 23 à 26 colonnes causé par une virgule non protégée
> dans l'export des dates (section 0 de `ARCHITECTURE.md`) — invisible
> tant qu'on ne compare pas les valeurs à leur sens attendu, et le bug
> `network_features.py` (544 vs 13 expéditeurs) qui ne se reproduisait
> pas sur un petit échantillon isolé, seulement à l'échelle complète.

**Si vous aviez eu 5 jours au lieu de 2, qu'auriez-vous fait
différemment ?**
> Directement la liste de `NOTE_METHODOLOGIQUE.md` section 9 :
> réentraîner après correction du bug, réintégrer le module graphe
> complet dans le score client, calibration probabiliste formelle,
> détection C-05/C-10/C-08.
