Salut l'équipe,

Je voulais vous expliquer où j'en suis avec les données, étape par étape, pour que
vous ayez la même image que moi en tête. Pas besoin de notions techniques pour suivre,
je vous explique tout simplement.

## Le défi, pour commencer

BAMIS Digital nous a donné 1,6 million de transactions Mobile Money réelles, entre
juin 2022 et juillet 2026. Notre boulot : construire un système capable de repérer les
transactions frauduleuses, de gérer des limites de dépenses par client, et de classer
chaque client selon son niveau de risque.

Et voici le piège auquel on fait face : **BAMIS ne nous dit jamais quelles
transactions sont vraiment frauduleuses.** Ils gardent la réponse secrète pour nous
tester à la fin. Un peu comme un examen sans corrigé. Ça change complètement la façon
dont on doit travailler, vous allez voir pourquoi juste après.

## D'abord, il a fallu comprendre ce qu'on avait entre les mains

Avant de toucher à quoi que ce soit, j'ai passé du temps à comprendre le fichier. Et
ça m'a mis la puce à l'oreille tout de suite.

BAMIS nous avait donné un document qui explique ce que chaque colonne du fichier est
censée contenir. Sauf qu'en ouvrant le vrai fichier, certaines colonnes ne contenaient
pas ce qu'elles étaient censées contenir. La cause : dans les dates, il y a une petite
fraction de seconde écrite avec une virgule qui n'aurait pas dû être là — un peu comme
une virgule en trop dans une adresse, qui décale tout ce qui vient après. Résultat : à
partir d'un certain point dans chaque ligne, toutes les colonnes suivantes étaient
décalées d'une case.

Ce genre de problème est vicieux parce qu'il **ne fait planter aucun programme**. Les
données rentrent quand même, juste au mauvais endroit. Si je ne l'avais pas repéré,
j'aurais entraîné tout le système sur des informations mélangées — en pensant lire "le
service utilisé" alors qu'en fait je lisais autre chose. J'ai dû reconstruire à la
main, colonne par colonne, la vraie correspondance, en comparant ce qui était
réellement dans le fichier avec ce qui avait du sens.

Et il y a eu un deuxième piège. Un premier essai de compréhension avait été fait sur
un petit échantillon, les 100 000 premières lignes. Les conclusions tirées de cet
échantillon se sont révélées fausses une fois vérifiées sur le fichier complet — parce
que certaines colonnes changent de comportement au fil du temps, et l'échantillon ne
représentait pas bien l'ensemble. Retenez ça, ça va nous servir tout le long du
projet : **on ne conclut jamais sur un échantillon sans revérifier sur la totalité.**

## Ensuite, on nettoie

Une fois la vraie structure comprise, j'ai vérifié la qualité des données :

- **63 dates** et **72 montants** qui n'avaient pas de sens (des valeurs impossibles).
  Je les ai mis de côté sans les supprimer, pour pouvoir les revérifier plus tard si
  besoin.
- **Des transactions en double** : la même opération apparaissait parfois deux fois
  dans le fichier. Repérées et marquées, toujours sans supprimer, pour garder une
  trace.
- **Pas de vrai numéro de client** dans le fichier. Impossible de savoir directement
  "tel client a fait ces 40 transactions". J'ai dû reconstruire cette information en
  utilisant le numéro de téléphone comme identifiant, ce qui m'a permis d'identifier
  environ **175 700 comptes actifs distincts**.
- Une colonne censée indiquer par quel canal la transaction est passée (application,
  USSD, agence...) donnait des valeurs qui ne correspondaient à aucun canal attendu.
  J'ai décidé de ne pas l'utiliser — mieux vaut ne pas se servir d'une information
  qu'on ne comprend pas plutôt que de construire quelque chose de faux dessus.

## Après, il faut construire des indicateurs utiles (le "feature engineering")

Un ordinateur ne comprend pas une transaction brute — une date, un montant, un numéro
de téléphone, ça ne lui dit rien tel quel. Il faut transformer ça en indicateurs qui
ont un sens pour repérer une fraude. En anglais on appelle ça le **feature
engineering** ("engineering" = construire, "feature" = variable/indicateur) — c'est le
terme que vous verrez partout si vous creusez le sujet, retenez-le. J'ai construit
quatre familles d'indicateurs (on dit aussi "features") :

1. **Est-ce que le montant dépasse une limite ?** Chaque service a un seuil de
   vigilance. On calcule à quel point chaque transaction s'en approche ou le dépasse.
2. **Est-ce que ce client se comporte différemment de d'habitude ?** On compare chaque
   transaction à l'historique personnel du client, pas à la moyenne de tout le monde.
   Un client qui envoie habituellement de grosses sommes n'est pas suspect s'il
   continue à le faire — ce qui compte, c'est l'écart par rapport à SES habitudes à
   lui.
3. **Est-ce qu'il y a une rafale de transactions ?** Combien d'opérations un compte a
   fait dans la dernière heure, les dernières 24h, les 7 derniers jours.
4. **Est-ce que ce compte a un comportement de "relais" ?** Certains comptes reçoivent
   de l'argent puis le renvoient presque immédiatement — un signal typique des comptes
   utilisés pour faire circuler rapidement de l'argent frauduleux. Je vous montre un
   exemple concret un peu plus bas, on en a trouvé un cas très net.

Petit détail technique qui a failli tout fausser : quand on calcule "l'écart à
l'historique du client", il faut absolument que le calcul ne mélange jamais les
historiques de deux clients différents. Mon premier calcul avait un bug très discret —
la toute première transaction d'un client se retrouvait parfois comparée à
l'historique du client précédent dans le tableau. Un peu comme comparer les notes d'un
élève à celles de l'élève assis juste avant lui sur la liste, au lieu de les comparer à
ses propres notes précédentes. Repéré et corrigé après vérification minutieuse. Ce
genre de bug a un nom technique : une **fuite de données** ("data leakage") — le
modèle "triche" en voyant une information qu'il n'aurait jamais en situation réelle.
C'est un des pièges les plus classiques en machine learning, et aussi un des plus
difficiles à repérer parce que rien ne plante, les résultats ont juste l'air "trop
beaux".

## Le vrai cœur du problème : inventer une réponse qu'on n'a pas

Je reviens là-dessus parce que c'est vraiment le point central. Sans exemples de
vraies fraudes fournis par BAMIS, impossible d'apprendre directement à un système "voici
à quoi ressemble une fraude". Ma solution : construire des **règles de bon sens**,
écrites à la main à partir de ce qu'on sait sur la fraude en général, et m'en servir
comme premier signal :

1. Le montant dépasse le seuil habituel du service.
2. Le cumul du jour dépasse la limite autorisée.
3. Le montant est juste en dessous du seuil, plusieurs fois de suite dans la journée —
   c'est la technique classique pour éviter de déclencher une alerte : fractionner un
   gros montant en plusieurs petits.
4. Rafale anormale de transactions en une heure.
5. Nouveau bénéficiaire (le client ne lui a jamais envoyé d'argent avant) ET montant
   supérieur à tout ce que ce client a déjà envoyé jusqu'ici.
6. Transaction à une heure inhabituelle ET montant très éloigné du comportement normal
   du client.
7. Profil de compte "relais" (réception puis renvoi rapide et répété).

Une transaction est marquée "suspecte" dès que deux de ces règles se déclenchent en
même temps. Résultat : **0,466% des transactions sont marquées suspectes** — un
chiffre très proche du "environ 1%" que le cahier des charges de BAMIS donnait comme
exemple. Ça me rassure sur le fait qu'on n'est pas complètement à côté de la plaque.

**Et vous allez me demander : ces 7 règles, on les a sorties d'où ?** Pas inventées au
hasard, trois sources précises :

1. **Les seuils officiels donnés par BAMIS.** Le cahier des charges du datathon
   contient un vrai tableau de seuils par service (seuil unitaire, seuil journalier).
   Les règles 1 et 2 utilisent directement ces chiffres officiels, ce n'est pas nous
   qui décidons à partir de quel montant c'est "trop".
2. **Les scénarios de fraude que BAMIS décrit eux-mêmes dans le document du défi.** Le
   cahier des charges liste explicitement des types de comportements suspects à
   surveiller — avec un nom pour chacun. Le fractionnement (couper un gros montant en
   plusieurs petits pour rester sous le seuil), la rafale de transactions, le compte
   "relais" qui fait transiter l'argent, le nouveau bénéficiaire avec un montant record,
   l'horaire inhabituel. Nos 7 règles sont la traduction en calcul de ces scénarios
   nommés par BAMIS — ce n'est donc pas nous qui avons inventé "ce qui ressemble à de la
   fraude", c'est BAMIS qui nous l'a décrit, et nous, on l'a codé.
3. **Les vraies données pour régler les seuils précis.** Savoir QUE "la rafale" est un
   signe suspect, c'est une chose (ça vient de BAMIS). Savoir à partir de COMBIEN de
   transactions par heure on doit déclencher l'alerte, c'est autre chose — ça, on l'a
   mesuré sur les vraies données (par exemple, on a regardé la vraie distribution du
   nombre de transactions par heure pour tous les comptes, et on a pris un seuil qui ne
   flague que les 1% de comptes les plus actifs, pas un chiffre sorti du chapeau). Pareil
   pour l'heure de "nuit" : mesurée sur la vraie répartition horaire, pas devinée.

Donc pour résumer si on nous pose la question : **le "quoi surveiller" vient du cahier
des charges de BAMIS, le "à partir de quand c'est suspect" vient des vraies données.**

Cette étiquette "suspecte / pas suspecte" qu'on invente nous-mêmes à partir des règles,
plutôt que de la recevoir toute faite, ça a un nom : un **pseudo-label**. "Pseudo" parce
que ce n'est pas la vraie vérité terrain, juste notre meilleure estimation. C'est ce
pseudo-label qui sert ensuite à entraîner le modèle.

## Ce que j'ai découvert en creusant, et qui vaut le coup d'être partagé

Je vous mets les découvertes les plus parlantes, celles qui montrent bien comment on
avance sur ce genre de projet.

**La définition de "la nuit" était fausse.** Mon intuition de départ : la nuit, c'est
entre 22h et 6h. En regardant la vraie répartition des transactions heure par heure,
je me suis rendu compte que 22h et 23h sont en fait des heures d'activité tout à fait
normales — presque autant de transactions qu'en pleine journée. La vraie période
calme, c'est plutôt minuit à 7h du matin. Sans cette vérification, j'aurais
faussement suspecté énormément de gens qui utilisent juste leur téléphone en soirée.

**J'ai failli accuser un agent BAMIS à tort.** Un compte réalisait environ 3 400
transactions en 24 heures — un chiffre qui a l'air absurde pour un particulier. En
creusant, j'ai compris qu'il s'agissait d'un agent BAMIS, un point de service qui
traite les opérations de nombreux clients, pas d'un fraudeur. J'ai dû recalculer le
seuil de "rafale anormale" sur les vraies données pour ne plus confondre ce genre de
compte professionnel légitime avec un comportement suspect.

**J'ai trouvé un vrai compte "relais".** Un compte reçoit de l'argent puis le renvoie
presque intégralement en quelques minutes — et ce n'est pas un coup isolé, ça s'est
produit **259 fois sur 273 transactions** de ce compte, donc 95% du temps. C'est
exactement le profil qu'on cherche : un maillon utilisé pour faire transiter
rapidement de l'argent d'un endroit à un autre, probablement pour brouiller son
origine.

**Une rafale de petites transactions identiques.** Un même compte a envoyé la même
somme, 7 100 MRU, treize fois de suite en une demi-heure, un après-midi de fin
décembre. Une seule transaction de ce montant ne dirait rien du tout ; le schéma
répété, si.

**Des circuits fermés dans le réseau de comptes.** En regardant qui envoie de l'argent
à qui à travers l'ensemble des comptes — pas transaction par transaction, mais en
reconstruisant tous les liens entre comptes comme un plan de métro — j'ai trouvé
**24 637 cas** où l'argent part d'un compte A vers un compte B puis revient vers A
dans un délai court. C'est un schéma quasiment invisible si on regarde les
transactions une par une, il ne saute aux yeux que quand on regarde le réseau dans son
ensemble.

## Où on en est avec le modèle

J'ai entraîné un système d'intelligence artificielle sur tous ces indicateurs, en
utilisant les règles ci-dessus comme signal de départ. Le modèle utilisé s'appelle
**CatBoost** — une famille de modèles dite de "gradient boosting" (il construit plein
de petits arbres de décision les uns après les autres, chacun corrigeant les erreurs du
précédent), très utilisée en détection de fraude bancaire parce qu'elle marche bien
même avec très peu de cas positifs par rapport au total (ici moins de 0,5%).

Pour vérifier qu'il généralise bien, et qu'il ne se contente pas de recopier les
règles, je l'ai testé sur une période qu'il n'a jamais vue pendant son apprentissage —
un peu comme un examen avec des questions inédites. C'est ce qu'on appelle une
**validation temporelle** : on n'entraîne jamais sur le futur pour prédire le passé, et
on ne mélange pas les dates au hasard comme on le ferait d'habitude, sinon le modèle
"trahirait" en apprenant des informations qu'il n'aurait pas en situation réelle.

Pour mesurer si le modèle est bon, on n'utilise pas le pourcentage de bonnes réponses
("accuracy") — avec seulement 0,5% de cas suspects, un modèle complètement inutile qui
répond "jamais suspect" aurait déjà 99,5% de bonnes réponses. On utilise à la place un
score adapté à ce genre de situation déséquilibrée, l'**AUC-PR**, qui va de 0 à 1. Notre
modèle obtient **0,91** sur la période jamais vue — un modèle de référence très basique
utilisé comme point de comparaison n'obtient que 0,42.

## Pourquoi 0,91 c'est bon, et pourquoi je ne cherche pas à faire mieux pour l'instant

Je m'attends à ce qu'on nous pose la question, donc autant qu'on soit tous au clair
là-dessus.

**Pourquoi 0,91 c'est un bon score.** Ce score va de 0 à 1. Il faut le comparer à deux
repères, pas le regarder tout seul :
- Un modèle "bête" qui ne fait aucun effort obtiendrait un score proche du taux réel de
  cas suspects, ici environ 0,005 (0,5%). On est à 0,91, donc très très loin au-dessus
  du hasard.
- Notre propre modèle de référence, une version simple sans effort particulier, n'obtient
  que 0,42. CatBoost fait plus de deux fois mieux.

Petite précision honnête à donner si on nous pose la question dans le détail : pendant
les tests, le score a bougé pas mal d'un essai à l'autre (entre 0,48 et 0,93 selon la
période testée), avec une moyenne à 0,76. C'est normal : on a très peu de cas suspects
au total, donc selon la période choisie pour tester, on tombe parfois sur peu de cas, ce
qui fait bouger le score dans un sens ou dans l'autre. Le chiffre le plus fiable, c'est
le 0,91 obtenu sur le test final, le plus grand et le plus représentatif (554 cas), fait
sur une période que le modèle n'a jamais vue.

**Pourquoi je n'ai pas cherché à réentraîner encore et encore pour grappiller plus de
points.** Trois raisons, et c'est important de bien les comprendre pour pouvoir les
expliquer au jury :

1. **Notre "vérité" est elle-même une invention.** On n'a pas de vraies étiquettes de
   fraude — on a construit nos propres règles pour deviner ce qui est suspect (voir plus
   haut, le "pseudo-label"). Si je pousse le modèle à coller de plus en plus près à ce
   pseudo-label, je ne le rends pas forcément meilleur pour détecter de VRAIES fraudes —
   je le rends juste meilleur pour deviner MES règles à moi. Passé un certain point, ce
   n'est plus de la détection de fraude, c'est de la triche déguisée.
2. **Le temps est limité, et le barème ne porte pas que sur le score.** Le score de
   détection compte pour une partie de la note, mais la gestion des seuils, le classement
   des clients, la détection des réseaux de fraude et la documentation comptent aussi.
   Mieux vaut un projet complet sur tous les points qu'un modèle poussé à l'extrême sur
   un seul point pendant que le reste est bâclé.
3. **On a déjà comparé plusieurs approches** (un modèle très simple, une régression
   logistique, puis CatBoost) et CatBoost gagne largement. Essayer des modèles encore
   plus compliqués prend du temps et augmente le risque de faire une erreur discrète
   difficile à repérer (comme le bug de fuite de données plus haut), pour un gain qui
   serait probablement minime.

Et un point à garder en tête pour la présentation : ce score de 0,91 mesure notre
capacité à retrouver NOS règles, pas les vraies fraudes que BAMIS connaît et qu'on n'a
jamais vues. C'est normal et attendu vu qu'on n'a pas accès aux vraies étiquettes — ce
n'est pas une faiblesse à cacher, c'est une limite du problème qu'on peut assumer et
expliquer clairement si on nous pose la question.

## Ce que je retiens, et qu'on devrait garder en tête pour la suite

- On vérifie toujours une intuition sur les données réelles avant de s'en servir —
  l'heure de nuit, le seuil de rafale, l'échantillon non représentatif, c'est trois
  fois la même leçon.
- Les cas extrêmes (l'agent à 3400 transactions, le compte relais à 95%) sont aussi
  importants à comprendre que la masse des données — ce sont eux qui montrent si nos
  règles sont trop larges ou au contraire trop timides.
- Le réseau de comptes, qui envoie à qui, raconte des choses qu'on ne voit jamais en
  regardant les transactions une par une.

## Maintenant je vous explique le reste : les 3 volets, le modèle, et le réseau

On a trois volets à livrer, BAMIS les a nommés A, B et C, et ils sont liés entre eux :
le score de risque du volet C ajuste les seuils du volet B, qui alimentent les règles
de détection du volet A.

### Volet A — La détection de fraude, ce qu'on vient de voir

C'est tout ce que je vous ai expliqué au-dessus : les règles, le pseudo-label, le
modèle CatBoost entraîné dessus, score final 0,91.

### Volet B — La gestion des seuils et budgets par client

Le système ne garde pas de plafond par client, donc c'est à nous de le calculer.
Pour chaque client, et pour chaque service qu'il utilise, on additionne tout ce qu'il a
dépensé sur la journée et sur le mois, et on compare au seuil officiel du service. On
envoie une alerte à 50%, 80%, 95% et 100% du seuil — comme une jauge d'essence qui
change de couleur en approchant de la réserve.

Un point important : on additionne **tous les canaux confondus**. Si un client atteint
son seuil sur l'application puis continue chez un agent, le compteur ne repart pas de
zéro — sinon ce serait une faille énorme (BAMIS le signale eux-mêmes dans leur document,
c'est le scénario "changement de canal", C-08 : *"la porte est fermée ? on passe par la
fenêtre"*).

Chiffres : on a calculé ça sur près d'un million de combinaisons client × service ×
jour. 0,25% dépassent déjà le seuil journalier officiel. 1 167 clients ont eu au moins
une alerte sur toute la période. Petite précision honnête : BAMIS ne nous donne pas de
seuil mensuel officiel, seulement le seuil journalier — on a estimé le seuil mensuel à
30 fois le seuil journalier, en le documentant clairement comme une hypothèse à
corriger si BAMIS communique un vrai chiffre.

### Volet C — Le classement des clients : deux notes sur 1000

Pour chaque client, on calcule deux notes indépendantes, de 0 à 1000, exactement comme
demandé :
- **Une note de risque** : est-il dangereux ? Construite à partir de 5 critères
  pondérés — comportement anormal (300 points max), contournement (250), rôle dans un
  réseau (200), historique d'alertes (150), profil/ancienneté (100). Ce sont les
  pondérations exactes données par BAMIS dans leur cahier des charges, pas inventées.
- **Une note de valeur** : est-ce un bon client ? Volume (300), régularité (200),
  rentabilité (250), diversité (150), ancienneté (100).

À partir de ces notes, chaque client tombe dans un segment (Faible/Modéré/Élevé/
Critique pour le risque, Bronze/Argent/Or/Platine pour la valeur) — encore une fois,
les seuils de segment viennent directement du document BAMIS. On croise les deux pour
obtenir une action recommandée dans une matrice de traitement (ex. un client Platine
en risque critique → gel du compte et investigation).

Petite anecdote de méthode qui vaut la peine d'être racontée : le premier calcul a
donné un résultat impossible — **zéro client classé "risque faible"**. En creusant,
j'ai compris que ma méthode comparait chaque client aux autres (comme un classement de
classe), et comme presque tous les clients ont zéro sur certains indicateurs, ils se
retrouvaient tous regroupés au milieu du classement au lieu d'être en bas. Corrigé en
changeant la façon de calculer pour ces indicateurs-là. Un deuxième problème est apparu
juste après, dans l'autre sens sur le score de valeur, corrigé aussi. Je raconte ça
parce que c'est exactement le genre de vérification qu'on doit faire systématiquement —
un résultat qui semble impossible ("zéro client dans une catégorie") est presque
toujours le signe d'un bug de méthode, pas un vrai résultat.

Chaque score est accompagné de **5 explications en langage simple** ("22% de ses
opérations sont collées au seuil", "il vide son compte en moins de 12h"...) — c'est une
exigence explicite de BAMIS : *"un score sans explication n'est pas exploitable"*.

### Le module graphe (bonus) — repérer ce qui est invisible transaction par transaction

C'est la partie la plus avancée, celle que BAMIS classe eux-mêmes en "niveau 3, bonus".
L'idée : au lieu de regarder chaque transaction séparément, on reconstruit tout le
réseau des comptes — qui envoie de l'argent à qui — comme un plan de métro avec des
comptes comme stations et des transactions comme lignes entre elles. **163 259
comptes, 1,36 million de connexions.**

Ça permet de repérer des choses complètement invisibles autrement :
- **Un compte qui collecte de l'argent de 13 personnes différentes** — signature
  typique d'un compte "collecteur".
- **Le compte relais dont je vous ai parlé** (95% de pass-through) — confirmé par le
  réseau, pas juste par un calcul isolé.
- **24 637 circuits fermés** : des cas où l'argent part d'un compte, passe par un ou
  plusieurs autres, et revient à son point de départ — un peu comme un boomerang.

Anecdote utile : la toute première version du calcul des circuits fermés a fait
planter l'ordinateur (erreur de mémoire). En cherchant pourquoi, j'ai découvert que
quelques paires de comptes (des agents à très fort volume) avaient jusqu'à 10 584
transactions entre elles — et ma méthode de calcul créait, pour chaque paire, toutes
les combinaisons possibles entre elles, ce qui explose à des centaines de millions de
lignes rien que pour cette paire. Remplacé par une méthode plus intelligente qui
cherche la transaction correspondante la plus proche dans le temps au lieu de toutes
les combiner. Résultat : de "plante" à 10 secondes.

## Le bilan, pour résumer aujourd'hui

On a couvert les 3 volets demandés, plus le module graphe bonus. Le modèle final
obtient un score de 0,91 sur des données jamais vues. Les 3 fichiers à rendre
(notes de fraude, classement des clients, consommation des seuils) sont prêts. Ce qui
nous reste : préparer la présentation orale et vérifier une dernière fois que tout
tient la route.

Voilà, c'est tout le chemin parcouru depuis le début. Dites-moi si un point n'est pas
clair, je préfère qu'on soit tous alignés avant la présentation.
