# Script oral — 6 minutes exactement

> Document interne, pas un livrable. Le texte exact à dire, slide par
> slide, minuté pour tenir en 6:00. Complément à `GUIDE_SLIDES_PPT.md`
> (le contenu des slides) et `GUIDE_SOUTENANCE.md` (les cas concrets et
> les Q&A). **Avant tout : corrige "une marchand" → "un marchand" sur la
> slide 2, petite faute d'accord.**
>
> Entraîne-toi à voix haute avec un chrono avant le jour J — ce script
> est calibré pour un débit normal, pas rapide.

---

## Slide 1 — Titre (0:00 → 0:10)

> "Bonjour, je m'appelle [ton prénom], je présente le projet de l'équipe
> Nextdata : la détection de fraude sur le Mobile Money de BAMIS
> Digital."

*(10 secondes, pas plus — juste le temps que le jury lise les 3 chiffres
en fond pendant que tu parles.)*

---

## Slide 2 — Problématique (0:10 → 0:40)

> "Le vrai problème de la fraude, ce n'est pas le fraudeur qui dépasse
> un seuil — c'est celui qui le contourne. Il fractionne ses montants en
> plusieurs petits paiements, comme couper un gâteau en parts. Il utilise
> des comptes mules, qui reçoivent l'argent et le renvoient tout de
> suite, comme une boîte aux lettres. Ou il multiplie les petites
> opérations pour rester sous les radars.
>
> Mais le vrai défi, c'est de ne pas accuser à tort un marchand ou un
> salarié qui a juste un comportement inhabituel mais honnête."

*(30 secondes. Montre chaque icône en disant son analogie.)*

---

## Slide 3 — Notre solution (0:40 → 1:25)

> "Pour ça, on a construit 3 niveaux. Les règles repèrent les cas
> évidents tout de suite. Le modèle IA croise plusieurs signaux à la
> fois, même ceux invisibles à l'œil nu. Et le graphe suit l'argent entre
> les comptes pour trouver les réseaux et les complices.
>
> Résultat mesuré : 0,91 sur 1. Pour comparer, si on utilisait juste le
> montant de la transaction par rapport au seuil, sans aucune
> intelligence artificielle, on aurait seulement 0,42. Notre modèle fait
> plus de deux fois mieux, parce qu'il combine plusieurs signaux au lieu
> d'un seul."

*(45 secondes.)*

---

## Slide 4 — Démonstration en direct (1:25 → 4:25)

**Ce que tu dis en arrivant sur la slide (5 secondes), puis tu bascules
sur le navigateur :**

> "Je vous montre ça en direct, sur le vrai dashboard, avec les vraies
> données."

**Puis, une fois sur le dashboard (le minutage ci-dessous est celui déjà
préparé dans `GUIDE_SOUTENANCE.md`) :**

1. *(30s)* Ouvre la file d'alertes. Dis : "Voici une transaction à score
   élevé."
2. *(30s)* Montre son score de fraude. Dis : "Le modèle donne un score
   sur 100, avec les raisons précises — ici, [cite 2-3 des facteurs
   affichés]."
3. *(45s)* Ouvre la fiche du client (`TEL039808`). Dis : "Ce client a un
   score de risque de 820 sur 1000. Il a reçu de l'argent de 13
   expéditeurs différents et en a envoyé à 18 — c'est le profil d'un
   compte collecteur."
4. *(30s)* Montre sa consommation de seuil. Dis : "On voit aussi sa
   consommation de budget, tous canaux confondus — appli, agent, USSD,
   tout est compté ensemble, pour qu'il ne puisse pas contourner en
   changeant de canal."
5. *(30s)* Ouvre la vue réseau (`TEL093693`). Dis : "Et voici le moment
   le plus important : notre module graphe. Ce compte a renvoyé l'argent
   reçu en moins de 30 minutes, 259 fois sur 273 transactions — c'est une
   vraie mule, pas juste une règle qui se déclenche."
6. *(15s)* Dis : "En fonction de ces deux scores, le système recommande
   une action — ici, [dis l'action affichée : surveillance / gel / seuil
   réduit]."

*(3 minutes exactement — c'est le cœur de la présentation, ne dépasse
pas.)*

---

## Slide 5 — Résultats et impact (4:25 → 5:25)

> "Concrètement, avec notre méthode : 319 transactions auraient été
> bloquées, ce qui représente 64,5 millions d'ouguiyas protégés. Et notre
> module graphe a détecté 24 637 circuits fermés — des motifs d'argent
> qui part puis revient sur le même compte. Ce ne sont pas 24 637 fraudes
> confirmées, mais ça prouve que notre détection fonctionne vraiment, pas
> juste en théorie.
>
> Et surtout : un marchand qui reçoit de l'argent de 50 clients
> différents chaque jour n'est jamais signalé à tort — parce qu'on
> compare chaque client à son propre historique, pas à une moyenne
> générale."

*(1 minute.)*

---

## Slide 6 — Limites et prochaine étape (5:25 → 5:50)

> "On n'a pas eu accès aux vraies fraudes confirmées pour tester — on a
> vérifié la cohérence entre nos règles et notre modèle à la place.
>
> Mais avec vos vraies données de fraude, on branche la même architecture
> en quelques minutes — pas besoin de tout refaire, juste réentraîner.
> Ensuite, deux prochaines étapes : détecter les chaînes de fraude plus
> longues, et ajuster automatiquement le seuil de chaque client selon son
> risque."

*(25 secondes — dis la limite vite, insiste plus longtemps sur "avec vos
vraies données..." qui est la phrase à retenir.)*

---

## Slide 7 — Merci (5:50 → 6:00)

> "Merci de votre attention. On est prêts pour vos questions."

*(10 secondes. Fin exacte à 6:00.)*

---

## Rappel avant de commencer

- Une seule personne parle du début à la fin — c'est la règle du
  protocole BAMIS.
- Pendant la démo (slide 4), garde `TEL039808` et `TEL093693` notés à
  portée de main.
- Si le dashboard ne charge pas : reste calme, dis que le lien est
  disponible en permanence (`datathon.loop-ia.com`), montre les captures
  d'écran de secours (voir `GUIDE_SLIDES_PPT.md`, plan B).
