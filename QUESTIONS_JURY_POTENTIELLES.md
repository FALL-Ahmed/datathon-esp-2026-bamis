# Questions potentielles du jury — checklist

> Document interne, complément à `GUIDE_SOUTENANCE.md`. Pas un livrable.
> Le jury n'aura que 4 minutes de questions — il n'en posera que 2-4.
> Ce fichier sert juste à ne pas être pris au dépourvu, pas à tout réciter.
>
> ★ = très probable, déjà traité en détail dans `GUIDE_SOUTENANCE.md`.

## A. Préparation des données

**Comment avez-vous vu que le fichier avait 26 colonnes au lieu de 23 ?**
> On a compté le nombre de champs réels sur les 1,6M lignes, au lieu de
> faire confiance au dictionnaire fourni. On a trouvé 26 colonnes, pas 23.

**Comment avez-vous géré les lignes avec une date ou un montant
aberrant ?**
> On les a mises de côté avant tout calcul. Une seule valeur fausse peut
> fausser tout l'historique d'un client.

**Pourquoi ne pas avoir utilisé `CHANNEL_TYPE` ?**
> On l'a vérifiée avant de l'écarter. On a cherché les valeurs attendues
> (APP, USSD, AGENT, WHATSAPP) dans tout le fichier — elles n'existent
> nulle part. La colonne est vide à 97% sur notre échantillon, et le peu
> qu'elle contient ressemble à des résidus du bug de date, pas à des
> noms de canal. On préfère le dire clairement plutôt que d'inventer une
> règle sur une donnée qu'on ne comprend pas. Conséquence : on ne détecte
> pas C-08 (changement de canal).

**Comment distinguez-vous une transaction interne d'une transaction
externe (GIMTEL) ?**
> Simple : si `DESTINATION_CUSTOMER` est vide, c'est interne. S'il est
> rempli, c'est externe.


## B. Volet A — règles, modèle, graphe

**Pourquoi CatBoost et pas XGBoost/LightGBM/Random Forest ?**
> Pour ce type de données (des transactions en tableau), le gradient
> boosting est la référence. CatBoost a une technique qui limite les
> erreurs quand l'étiquette d'entraînement n'est pas parfaite — c'est
> notre cas, puisqu'on n'a pas la vraie liste des fraudes. Et on ne l'a
> pas choisi au hasard : comparé à une baseline simple (AUC-PR 0,42) et
> à une régression logistique (0,31), CatBoost gagne largement (0,91).
>
> **À ne jamais dire :** que CatBoost "gère nativement les catégories".
> C'est vrai en général, mais pas dans notre cas — le modèle ne reçoit
> que des chiffres déjà calculés, aucune catégorie brute.

**Comment avez-vous construit vos exemples de fraude sans vérité
terrain ?**
> Une transaction est comptée comme "exemple de fraude" si au moins 2 de
> nos 7 règles se déclenchent en même temps. Ça représente 0,47% des
> transactions, proche du "~1%" donné en exemple par le cahier des
> charges.

**Comment évitez-vous que le modèle "triche" en apprenant le futur ?**
> Trois protections : on entraîne toujours sur le passé et on teste sur
> une période plus récente, jamais l'inverse. On laisse 7 jours d'écart
> entre les deux. Et on exclut nos propres règles des variables du
> modèle, sinon il recopierait juste leur formule.

**À quelle fréquence faut-il réentraîner le modèle ?**
> Pas testé précisément — à discuter avec BAMIS selon la vitesse à
> laquelle les fraudeurs changent de méthode. Une piste raisonnable :
> une fois par mois.

**Le score est-il une vraie probabilité ?**
> Non, c'est un score de classement, pas calibré comme une vraie
> probabilité. Ça ne change rien à notre résultat (AUC-PR), mais c'est
> une limite à signaler si le jury pose la question précisément.

**Comment le module graphe tiendrait-il avec 10 fois plus de données ?**
> On a déjà eu ce problème et on l'a réglé : la première version
> plantait par manque de mémoire sur une grosse paire de comptes. On l'a
> remplacée par une méthode plus efficace (`merge_asof`), qui tient
> maintenant en 10 secondes sur 1,36M transactions.

**Pourquoi seulement des circuits courts (A→B→A) et pas des chaînes plus
longues ?**
> Question de temps. Chercher des chaînes plus longues sur 163 000
> comptes coûte beaucoup plus cher en calcul, pour un gain qu'on a jugé
> plus faible avec le temps qu'on avait.

## C. Volet B — budget et seuils

**D'où vient le seuil mensuel, puisqu'il n'existe pas dans le fichier
fourni ?**
> On l'a estimé à 30 fois le seuil journalier. C'est une hypothèse
> assumée, à remplacer dès que BAMIS donne un vrai chiffre.

**Un client qui dépasse son seuil est-il bloqué automatiquement ?**
> Non. On génère une alerte, mais la décision de bloquer reste à BAMIS.
> On ne l'automatise pas.

**Et le fractionnement sur plusieurs comptes du même client (C-10) ?**
> Pas traité, faute de temps. C'est possible à faire avec le module
> graphe, mais pas fait dans cette version.

## D. Volet C — classement client

**Pourquoi prendre le maximum et pas la moyenne des indicateurs ?**
> Pour ne pas diluer un signal fort. Un client extrême sur un seul point
> ne doit pas paraître "normal" juste parce que ses autres indicateurs
> sont bas.

**Pourquoi 175 689 clients dans le fichier, alors que 40 866 seulement
ont fait une transaction ?**
> On a élargi exprès. Un compte qui ne fait QUE recevoir de l'argent de
> beaucoup de gens différents est justement le profil "collecteur" (C-03)
> que le cahier des charges demande de détecter.

**Comment traitez-vous un nouveau client sans historique ?**
> Ses indicateurs de comportement ne sont pas calculables à sa première
> transaction — le système le signale. Pas de règle spéciale au-delà de
> ça, c'est une limite qu'on assume.

## E. Validation

**Pourquoi 3 découpages temporels et pas 5 ou 10 ?**
> Compromis avec le temps qu'on avait (2 jours). 3 suffisent pour voir
> si le résultat est stable.

**Pourquoi 7 jours d'écart entre entraînement et test ?**
> Marge de sécurité, pour être sûr qu'aucune donnée calculée en retard ne
> passe d'un côté à l'autre par erreur.

**Comment savez-vous que le modèle ne va pas se dégrader avec le
temps ?**
> On ne le sait pas précisément — pas de suivi automatique mis en place.
> C'est une limite assumée, pas résolue.

## F. Limites déjà assumées

★ **Si le jury avait la vraie liste des fraudes, votre 0,91 tiendrait-il
encore ?** → réponse détaillée dans `GUIDE_SOUTENANCE.md` : on ne peut
pas garantir un chiffre exact, mais nos règles et notre modèle,
construits séparément, pointent vers les mêmes comptes suspects.

**Le bug dans `network_features.py`, quel a été son impact réel ?**
> Mesuré, pas juste supposé. On a retiré les 2 colonnes fausses et
> réentraîné le modèle le 2026-07-20. Résultat : quasiment aucun
> changement (0,9139 → 0,9130). Ces deux colonnes ne servaient à rien.

★ **D'où viennent vos multiplicateurs de seuil (×1.5, ×0.7...) ?** →
réponse détaillée dans `GUIDE_SOUTENANCE.md` : pas mesurés sur les
données, mais l'ordre suit la logique de la matrice du cahier des
charges.

## G. Bonus et reproductibilité

**Le dashboard est-il connecté en direct aux données ?**
> Non, c'est un export à partir des vrais résultats du pipeline. Pas de
> connexion en temps réel — normal pour un datathon, pas une vraie
> production.

**Comment le jury peut-il relancer tout votre travail ?**
> Une seule commande : `python scripts/run_all.py`. Testée de bout en
> bout, 13 minutes, tout fonctionne.

**Pourquoi Python ?**
> Les bonnes bibliothèques existent déjà pour tout faire : règles,
> machine learning, graphe. Ça permet un seul pipeline cohérent et
> testable.

## H. Questions pièges

**Avez-vous chiffré le coût d'une fausse alerte pour BAMIS ?**
> Non, pas en argent. On donne le nombre d'alertes générées à plusieurs
> seuils, pour que BAMIS fasse ce choix eux-mêmes selon leur propre
> coût.

**Comment votre solution s'adapterait à un nouveau service demain ?**
> Facilement. Les seuils viennent d'un fichier, pas du code. Il suffit
> d'ajouter une ligne.

**Qu'est-ce qui vous a le plus surpris ?**
> Le décalage entre 23 et 26 colonnes, invisible sans vérifier chaque
> valeur une par une. Et le bug réseau, correct sur un petit échantillon
> mais faux à grande échelle.

**Avec 5 jours au lieu de 2, qu'auriez-vous fait de plus ?**
> Calibrer vraiment les probabilités, détecter les chaînes plus longues
> (C-05) et le fractionnement multi-comptes (C-10), et connecter le vrai
> score du module graphe au score client.

**Comment vous êtes-vous répartis le travail en équipe ?**
> Réponse à adapter selon votre organisation réelle — le jury veut
> vérifier que ce n'est pas le travail d'une seule personne. Restez
> concret : qui a fait quoi (données, modèle, dashboard, rapport).

**Votre modèle peut-il désavantager injustement certains clients ?**
> C'est un vrai risque avec ce genre de système, on ne le nie pas. On
> compare toujours un client à son propre historique, pas à une moyenne
> globale — ça évite de pénaliser quelqu'un juste parce qu'il est
> différent des autres. Mais on n'a pas testé formellement l'équité du
> modèle entre différents profils de clients, c'est une limite honnête.

**Pourquoi votre solution mériterait de gagner ?**
> Trois choses concrètes : un AUC-PR mesuré et vérifié (0,91), un module
> graphe qui détecte vraiment des mules et des circuits (pas juste des
> règles), et une méthode honnête — chaque limite est documentée, pas
> cachée.
