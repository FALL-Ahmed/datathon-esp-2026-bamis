# Guide de soutenance — BAMIS Fraud Detection

> Document de préparation interne à l'équipe pour la présentation orale
> (10-15 min + démonstration). Contient le scénario de démo, les cas
> concrets à montrer, et les réponses préparées aux questions probables du
> jury. **Ce n'est pas un livrable du cahier des charges** — extrait de
> `ARCHITECTURE.md` le 2026-07-19 pour garder ce dernier focalisé sur
> l'architecture technique. Voir `NOTE_METHODOLOGIQUE.md` pour le rapport
> officiel (démarche, variables, résultats) et `ARCHITECTURE.md` pour le
> détail technique du pipeline.

## Écrans et scénario

**Structure recommandée (10 à 15 minutes), alignée sur celle suggérée par
le cahier des charges :**

1. **Problème métier** (1 min) — le fraudeur ne dépasse jamais le seuil,
   il le contourne ; le vrai défi est de ne pas signaler à tort marchands,
   salariés, locataires.
2. **Difficultés rencontrées** (1 min) — mentionner explicitement l'audit
   de schéma (section 0 de `ARCHITECTURE.md`) : c'est une preuve concrète
   de rigueur méthodologique que peu d'équipes concurrentes auront
   probablement remarquée si elles n'ont pas vérifié l'alignement des
   colonnes.
3. **Architecture de la solution** (1-2 min) — montrer le schéma du
   pipeline, insister sur "seuils jamais en dur" et "split temporel".
4. **Variables importantes** (1-2 min) — 3-4 features clés avec leur
   pouvoir discriminant (ex. importance SHAP), notamment ratio au seuil et
   écart à l'historique client.
5. **Modèle de fraude** (1 min) — ordre de modèles testés, AUC-PR obtenu,
   comparaison à la baseline règle simple (démontrer l'apport réel du ML).
6. **Détection des contournements** (2 min) — LE moment différenciant :
   montrer un compte mule détecté ou une chaîne de rebond sur le dashboard
   graphe, avec l'explication en langage simple.
7. **Gestion des seuils** (1 min) — montrer un client qui a changé de canal
   et dont le cumul continue correctement (preuve C-08).
8. **Classement des clients** (1-2 min) — une fiche client avec ses 2
   scores et ses 5 facteurs explicatifs.
9. **Démonstration live** (3-4 min) — scénario concret ci-dessous.
10. **Résultats et impact pour BAMIS** (1 min) — chiffrer : "X fraudes
    détectées sur Y transactions, Z faux positifs, gain de temps estimé
    pour les équipes de conformité".

**Scénario de démonstration concret (tel que suggéré par le cahier des
charges) :**
1. Ouvrir la file d'alertes, sélectionner une transaction à score élevé.
2. Montrer son score de fraude et ses raisons (5 facteurs).
3. Ouvrir la fiche du client associé : profil, score de risque, score de
   valeur, action recommandée.
4. Montrer sa consommation de seuil (proche de 100 %, tous canaux
   confondus).
5. Ouvrir la vue réseau : montrer les comptes liés (mule ou chaîne) si le
   cas s'y prête.
6. Conclure sur l'action recommandée par la matrice de traitement
   (surveillance, gel, seuil réduit...).

**Préparer 2-3 cas concrets à l'avance** (pas de recherche live à l'aveugle
devant le jury) : un vrai positif clair, un cas limite bien expliqué (pour
montrer la maîtrise des faux positifs), et un cas réseau (mule/chaîne) si
le module graphe est prêt.

**Cas concrets déjà repérés dans les vraies données, à retenir pour la
démonstration** (mis à jour au fil de l'avancement) :
- **Client `TEL039808` — score de risque 820/1000 (Critique).** A reçu de
  l'argent de **13 expéditeurs différents** et envoyé à 18 destinataires
  différents (signature collecteur/fan-in, C-03), 22 % de ses opérations
  collées au seuil du service, écart de 6,3 écarts-types à son historique
  habituel. Excellent cas pour illustrer le score de risque ET
  l'explicabilité en une seule fiche client
  (`data/features/customer_risk_value_scores.parquet`). **Chiffre corrigé
  le 2026-07-20** : ce cas citait auparavant "544 expéditeurs différents",
  une valeur fausse produite par un bug confirmé dans
  `feature_engineering/network_features.py` (`nb_expediteurs_distincts_past`
  / `nb_destinataires_distincts_past`, calculées via `merge_asof` + cumsum
  de flags booléens — corrects sur un sous-ensemble isolé de 71 lignes,
  faux à l'échelle du fichier complet, cause exacte non identifiée). Ces
  deux colonnes ont été retirées de `scoring/customer_scoring.py` et
  remplacées par un comptage direct sur les transactions brutes, revérifié
  manuellement. **Limite assumée à signaler si le jury demande le détail
  des features du modèle ML** : ces deux colonnes faisaient partie des 24
  features d'entrée de CatBoost (`feature_engineering/feature_store.py`) —
  le modèle n'a pas été réentraîné avec la version corrigée faute de temps
  (2 features bruitées sur 24, impact probablement limité mais non
  quantifié).
- **Compte agent (téléphone non encore identifié nommément) — jusqu'à 3400
  opérations en 24h, actif ainsi depuis 2022.** Cas limite idéal pour
  démontrer la maîtrise des faux positifs : un modèle naïf le signalerait
  immédiatement, `behavioral_features.py` le reconnaît comme normal une
  fois comparé à son propre historique sur 4 ans. À rapprocher de la phrase
  du cahier des charges : *"un marchand reçoit de l'argent de dizaines de
  personnes [...] tous ces comportements ressemblent à de la fraude sans en
  être"*.
- **72 transactions à montant aberrant (jusqu'à 10⁶⁰ MRU)** trouvées et
  mises en quarantaine lors de l'audit — bon exemple à citer pour la
  rigueur de préparation des données (section "Difficultés rencontrées" de
  la soutenance), pas pour la détection de fraude elle-même (ce sont des
  transactions `REGISTERED` jamais finalisées, un défaut du système source).
- **Compte `TEL093693` — score mule maximal.** 259 de ses 273 transactions
  (95%) sont des "reçu puis renvoyé en moins de 30 minutes" — signature
  quasi manuelle d'un compte boîte-aux-lettres (C-02). Excellent deuxième
  cas concret, complémentaire de `TEL039808` (celui-là plutôt collecteur
  fan-in).
- **24 637 circuits fermés (A→B→A) détectés en 7 jours**, dont plusieurs
  à moins de 3 secondes d'écart avec un montant identique à l'aller et au
  retour (ex. `TEL064889`↔`TEL068771`, 70 MRU dans les deux sens, 0,88
  seconde d'écart) — probablement des annulations techniques automatiques
  plutôt que de la fraude (C-06), mais démontre concrètement que la
  détection de circuits fonctionne. À mentionner avec la réserve
  correspondante si le jury demande un exemple.
- **Un bug mémoire trouvé et corrigé pendant le développement du module
  graphe** (`graph/pattern_detection.py`) — bonne histoire de méthode pour
  la soutenance : la première implémentation des circuits fermés (un
  self-join classique sur les paires de comptes) a fait planter le
  processus par manque de mémoire. Cause : quelques paires agent/hub ont
  des milliers de transactions entre elles (une paire en a 10 584), et un
  self-join produit un produit croisé pour chaque paire — un self-join sur
  10 584 transactions produit plus de 100 millions de lignes intermédiaires
  pour cette seule paire. Diagnostiqué en mesurant la distribution réelle
  du nombre de transactions par paire avant de corriger, puis remplacé par
  `merge_asof` (recherche par proximité temporelle, jamais de produit
  croisé) — passe de "plante" à 10 secondes sur les 1,36M transactions.

## Q&A préparées

**Réponse préparée à la question "Comment avez-vous validé vos scores ?"**
(question quasi certaine du jury sur le volet C — voir
`NOTE_METHODOLOGIQUE.md` section "Classement des clients" pour le détail
complet des trois corrections) :

*Version courte (30 secondes) :*
> "On a d'abord construit une méthode évidente — classer chaque client par
> rapport aux autres. En testant sur les vraies données, on a découvert un
> problème : presque tous nos indicateurs de risque sont à zéro pour
> l'immense majorité des clients, donc ce classement les regroupait tous au
> milieu au lieu de les mettre en bas. Résultat concret : zéro client en
> 'risque faible'. On l'a corrigé, revérifié, et un deuxième problème est
> apparu à l'envers sur le score de valeur — corrigé aussi. Pour vérifier
> que le résultat final tient la route, on a comparé nos scores clients à
> nos règles de détection de fraude, construites séparément : les clients
> déjà repérés par les règles ont un score de risque deux fois plus élevé
> en moyenne, et 13 fois plus de chances d'être classés 'à risque élevé'.
> Les deux systèmes, indépendants, sont d'accord entre eux."

*Version longue (si le jury insiste, "et vous êtes sûrs que c'est juste ?") :*
> "Non, on ne peut pas être sûrs à 100% — et on le dit clairement : sans
> les vraies réponses, qui restent chez le jury, aucune équipe ne peut
> prouver formellement que son score reflète la vraie fraude. Ce qu'on PEUT
> montrer, c'est la cohérence interne : deux systèmes construits
> indépendamment — nos règles sur les transactions individuelles, et notre
> score agrégé par client — pointent vers les mêmes profils suspects. C'est
> la meilleure preuve possible sans accès à la vérité terrain, et c'est
> plus rigoureux que de simplement dire 'ça a l'air bien'."

*Pourquoi cette réponse est solide :* elle ne cache pas les erreurs (elle
les raconte comme preuve de méthode), donne des chiffres précis (zéro
client en risque faible → 52,8 % après correction), et admet honnêtement
la limite (pas de vérité terrain disponible) plutôt que de sur-vendre.

**Réponse préparée à la question "Pourquoi seulement 6-7 règles sur les 16
scénarios F-01 à F-06 / C-01 à C-10 listés par BAMIS ? Et pourquoi
exactement celles-là ?"** (question probable, cette sélection peut passer
pour arbitraire si elle n'est pas justifiée) :

*Version courte (30 secondes) :*
> "Ce n'est pas 6 scénarios traités et 10 abandonnés — c'est une répartition
> sur les 3 niveaux que le cahier des charges recommande lui-même : règles,
> modèle, graphe. Les scénarios C-02 à C-06 sont traités par notre module
> graphe, pas par des règles, parce que BAMIS dit lui-même que ces schémas
> sont invisibles transaction par transaction. Ce qui reste vraiment non
> couvert, c'est 5 scénarios précis, et pour chacun on peut dire pourquoi :
> soit la donnée n'existe pas dans le fichier (compte volé, arnaque),
> soit elle existe mais on l'a jugée non fiable après vérification (canal
> utilisé), soit le coût de calcul est trop élevé pour le gain attendu
> (chaînes à 3+ sauts, fractionnement multi-comptes) — une décision de
> priorité assumée, pas un oubli."

*Version longue (si le jury demande le détail scénario par scénario) :*
> "F-01 (compte volé) demande de savoir si l'opération vient d'un nouvel
> appareil ou d'une nouvelle ville — cette information n'existe pas dans le
> fichier de transactions. F-04 (arnaque/ingénierie sociale) n'est pas
> détectable même en théorie à partir d'un historique de transactions : la
> victime envoie l'argent elle-même, volontairement, rien ne distingue ça
> d'un paiement légitime sans un signal externe comme une plainte client.
> F-05 (fraude d'un agent) et C-08 (changement de canal) dépendent tous les
> deux de la colonne qui indique le canal utilisé — on a vérifié cette
> colonne et ses valeurs ne correspondent à aucun canal attendu, donc on a
> choisi de ne pas construire de règle dessus plutôt que de bâtir sur une
> donnée qu'on ne peut pas garantir. C-05 (chaînes de rebond à 3 sauts ou
> plus) et C-10 (fractionnement réparti sur plusieurs comptes) sont
> techniquement faisables avec notre graphe, mais demandent d'explorer des
> chemins à plusieurs sauts sur 163 000 comptes, un coût de calcul beaucoup
> plus élevé que les mules et les fan-in/fan-out déjà détectés, pour un
> gain marginal qu'on a jugé plus faible compte tenu du temps disponible."

*Pourquoi cette réponse est solide :* elle recadre la question (ce n'est pas
"6 sur 16", c'est "réparti sur 3 niveaux + 5 exclusions justifiées une par
une"), et chaque exclusion a une cause vérifiable et différente (donnée
absente / donnée non fiable / coût de calcul) plutôt qu'une réponse
générique du type "pas eu le temps".

**Réponse préparée à la question "Comment avez-vous décidé quel scénario va
à quel niveau (règles / modèle / graphe) ?"** :

*Version courte (30 secondes) :*
> "Chaque niveau répond à un type de question différent. Le niveau 1
> (règles) traite ce qu'on peut voir sur une seule transaction avec un
> critère clair — seuil dépassé, trop d'opérations, nouveau bénéficiaire.
> Le niveau 2 (modèle) combine tous ces indicateurs ensemble pour capter des
> patterns qu'aucune règle écrite à la main n'attraperait seule. Le niveau 3
> (graphe) traite ce qui n'existe QUE dans la relation entre plusieurs
> comptes — un compte qui collecte de l'argent de centaines d'autres, une
> chaîne A vers B vers C, un circuit qui revient à son point de départ.
> Ce dernier type est par nature invisible transaction par transaction, il
> faut construire le graphe entier pour le voir."

*Version longue (si le jury demande le détail par scénario) :*
> "Niveau 1 : R1/R2 sont des comparaisons directes à un seuil officiel.
> C-01 (fractionnement) et C-07 (rafale) sont des comptages sur une courte
> fenêtre. F-03 (nouveau bénéficiaire + gros montant) est une combinaison de
> deux conditions booléennes. Tout ça s'exprime comme une règle simple,
> donc autant le faire directement — c'est rapide, et surtout 100%
> explicable, ce que le cahier des charges exige.
>
> Niveau 2 : le modèle ne traite pas un scénario en particulier, il apprend
> à pondérer et combiner tous les indicateurs numériques ensemble (hors les
> règles elles-mêmes, pour éviter la fuite de données). Nécessaire parce
> qu'une règle est rigide — un seuil fixe peut être contourné en restant
> juste en dessous — alors que le modèle peut repérer une transaction
> légèrement anormale sur cinq indicateurs à la fois, un pattern que
> personne n'aurait pensé à écrire comme règle explicite.
>
> Niveau 3 : C-03 (fan-in) et C-04 (fan-out) sont littéralement des comptes
> de connexions entrantes/sortantes dans un graphe — un concept qui n'existe
> pas au niveau d'une transaction isolée. C-05 (chaîne de rebond) demande de
> suivre un chemin sur plusieurs comptes. C-06 (circuit fermé) est un cycle,
> un concept de théorie des graphes. Ces scénarios ne sont pas 'plus
> difficiles', ils n'ont simplement aucun sens en dehors d'une
> représentation en graphe — BAMIS le dit lui-même dans le cahier des
> charges : 'les schémas C-02 à C-06 et C-09 sont invisibles si l'on
> regarde les transactions une par une'."

*Pourquoi cette réponse est solide :* elle montre qu'on a choisi le niveau
en fonction de la nature du signal (un seul enregistrement / une
combinaison de signaux / une structure relationnelle), pas au hasard ni par
facilité — et elle s'appuie sur une phrase que BAMIS a écrite lui-même.

**Réponse préparée à la question "Comment justifiez-vous le choix de
CatBoost ?"** :

*Version courte (30 secondes) :*
> "On a choisi CatBoost pour deux raisons concrètes : c'est la famille de
> modèles (gradient boosting) la plus utilisée dans l'industrie pour ce
> genre de données — des transactions en tableau, pas des images ni du
> texte — et elle a une technique interne pensée pour limiter le
> surapprentissage sur une étiquette imparfaite, ce qui est exactement notre
> cas avec le pseudo-label. Et surtout, on ne l'a pas choisi les yeux
> fermés : on l'a comparé à un modèle de référence basique et à une
> régression logistique, et CatBoost gagne largement (0,91 contre 0,42 et
> 0,31)."

*Version longue (si le jury demande "pourquoi CatBoost précisément, pas
XGBoost ou LightGBM ?") :*
> "Pour des données en tableau, les modèles de la famille gradient boosting
> (CatBoost, XGBoost, LightGBM) sont l'état de l'art reconnu, bien avant le
> deep learning qui est pensé pour d'autres types de données comme les
> images ou le texte. CatBoost utilise une technique interne, l'ordered
> boosting, pensée pour limiter le surapprentissage quand l'étiquette
> d'entraînement est imparfaite — ce qui est exactement notre cas avec le
> pseudo-label. Et il demande peu de réglage pour obtenir un bon résultat,
> un vrai avantage avec 2 jours devant nous. On a quand même comparé :
> LightGBM était notre deuxième choix envisagé, XGBoost et les méthodes plus
> complexes comme le stacking ont été jugés en dernier recours, plus de
> risque d'erreur pour un gain estimé faible vu le temps restant."

*Pourquoi cette réponse est solide :* elle ne se limite pas à "c'est un bon
modèle", elle justifie par la nature des données (tabulaire), une
particularité technique pertinente pour notre cas précis (pseudo-label
bruité), et une comparaison chiffrée réelle plutôt qu'une préférence.

*Point de vigilance, à ne pas dire :* ne pas mentionner "CatBoost gère
nativement les catégories" comme argument — c'est vrai en général pour
CatBoost, mais **pas utilisé dans notre implémentation précise** : le
modèle ne reçoit que 24 colonnes numériques déjà calculées
(`FEATURE_COLUMNS` dans `feature_store.py`), aucune colonne catégorielle
brute (comme `SERVICE_CODE`) ne lui est passée directement — son effet
passe uniquement par le ratio au seuil du service, déjà calculé en amont.
Si le jury demande à voir le code, cet argument ne tiendrait pas.

**Réponse préparée à la question "Sur quoi vous êtes-vous basés pour dire
que 3 règles sur 7 déclenchées, c'est le seuil de blocage ?"** :

*Version courte (30 secondes) :*
> "Honnêtement, ce seuil n'est pas issu d'une optimisation statistique — le
> seuil à 2 règles sert déjà à entraîner le modèle, donc pour illustrer une
> politique d'action plus stricte dans le dashboard, on a pris un cran
> au-dessus. Mais on a vérifié après coup si notre modèle validé (0,91)
> est d'accord avec ce choix : il classe déjà 99,8% des transactions à 2
> règles comme quasi certainement frauduleuses (score > 50%), quasiment
> autant qu'à 3 règles (100%). Le vrai saut, selon le modèle, se situe
> entre 1 et 2 règles, pas entre 2 et 3. Notre seuil à 3 est donc
> volontairement plus prudent que ce que le modèle validerait déjà — on
> préfère sous-agir que sur-bloquer des clients honnêtes tant qu'on n'a pas
> de retour de BAMIS sur le coût réel d'un faux positif."

*Chiffres à l'appui si le jury demande le détail :*

| Règles déclenchées | Score moyen du modèle | % avec score > 50% |
|---|---|---|
| 0 | 0,04% | 0,0% |
| 1 | 11,8% | 11,8% |
| 2 | 98,7% | 99,8% |
| 3 | 99,9% | 100% |
| 4 | 99,99% | 100% |

*Pourquoi cette réponse est solide :* elle ne prétend pas à une
justification qu'on n'a pas, mais transforme la question en vérification
empirique réelle (croisement avec le score du modèle validé), et le
résultat — même s'il ne confirme pas exactement le seuil choisi — est
présenté comme un choix de prudence assumé plutôt que caché.

**Version équipe (débutants) — l'analogie du bulletin scolaire**, à utiliser
pour expliquer le même bug en interne sans jargon :

> Pour chaque client, on donne deux notes sur 1000 — comme un bulletin
> scolaire, mais avec deux matières : une note de risque et une note de
> valeur. Chaque note est la moyenne pondérée de 5 "matières" (les 5
> critères du cahier des charges), chacune avec son propre coefficient.
>
> La première fois qu'on a calculé les notes, résultat impossible : **aucun
> client classé "peu risqué"**. En cherchant pourquoi, on a compris : notre
> méthode comparait chaque client aux autres, comme un classement de
> classe. Or presque tous les "élèves" avaient 0/20 sur certaines matières
> (99,97 % des clients n'ont jamais fait de rafale d'opérations, par
> exemple). Dans un classement, un gros paquet d'élèves à égalité sur 0/20
> se retrouve statistiquement **au milieu du classement, pas en dernière
> position** — c'est un piège mathématique classique du classement par
> rang quand une valeur est ultra-majoritaire. On a changé de méthode
> (comparer à une échelle fixe plutôt qu'à un classement), un deuxième
> problème est apparu à l'envers sur la note de valeur, corrigé aussi.
>
> Message pour l'équipe : ce n'est pas grave de ne pas réussir du premier
> coup — ce qui compte, c'est d'avoir vérifié le résultat, compris le
> problème, et corrigé deux fois plutôt que de livrer une note qui "a l'air
> de marcher".

**Réponse préparée à la question "D'où viennent vos multiplicateurs de
seuil (×1.5, ×0.7, ×0...) pour le bonus volet B ?"** :

*Version courte (30 secondes) :*
> "Ce ne sont pas des valeurs mesurées sur les données — on l'assume
> complètement. Ce qui est réfléchi, c'est l'ordre et l'écart entre elles :
> ils suivent exactement la sévérité croissante de la matrice de traitement
> du cahier des charges, du moins sévère au plus sévère. Le chiffre exact
> (1.5 plutôt que 1.3, par exemple) est un point de départ raisonnable,
> pensé pour être ajusté par la direction des risques de BAMIS — c'est pour
> ça qu'il est dans `config.yaml` et pas codé en dur dans le script."

*Détail des valeurs choisies et leur logique :*

| Action (matrice volet C) | Multiplicateur | Logique |
|---|---|---|
| Seuil majoré | ×1.5 | +50%, assez pour désengorger un bon client sans vider le seuil de son sens |
| Seuil normal | ×1.0 | Cas de référence, aucun changement |
| Surveillance | ×1.0 | Risque encore modéré : on regarde de plus près (alertes/dashboard) sans pénaliser financièrement |
| Surveillance renforcée | ×0.85 | Un cran sous la surveillance simple : risque "Élevé", un peu plus de friction |
| Seuil réduit | ×0.7 | -30%, ralentit sans bloquer l'usage normal |
| Seuil minimal | ×0.4 | -60%, très strict, réservé à Bronze + risque élevé |
| Gel, investigation | ×0 | Correspond littéralement au mot "Gel" — toute opération doit être validée manuellement |

*Pourquoi cette réponse est solide :* elle ne prétend pas à une calibration
qu'on n'a pas faite (aucune vérité terrain disponible pour l'optimiser), mais
montre que le choix suit une logique cohérente et documentée (ordre aligné
sur la matrice officielle du cahier des charges), et que le mécanisme est
conçu dès le départ pour être corrigé par un humain métier plutôt que figé
dans le code.
