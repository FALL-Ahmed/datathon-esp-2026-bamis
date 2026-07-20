# Guide des slides PPT — BAMIS Fraud Detection

> Document interne, pas un livrable. Complément à `GUIDE_SOUTENANCE.md`
> (qui donne le texte à dire et le minutage). Ici, c'est ce qu'il faut
> mettre sur chaque slide. 6 slides pour 6 minutes, une slide par minute
> environ, sauf la démo qui reste sur le dashboard en direct (pas une
> slide).

## Règle générale pour toutes les slides

- Peu de texte. Des mots-clés, pas des phrases longues.
- Un chiffre gros et visible par slide, si possible.
- Pas de jargon technique écrit sur la slide (garde ça pour ce que tu dis
  à l'oral, si le jury demande).
- Logo BAMIS en haut à gauche sur chaque slide, discret.

---

## Slide 1 — Titre

**Ce qu'il y a dessus :**
- Titre : "Détection de fraude sur le Mobile Money"
- Sous-titre : "Datathon ESP DATACLUB 2026 — Équipe Nextdata"
- Un seul visuel : le logo BAMIS, ou une icône simple (bouclier, cadenas)
- En bas : les 3 chiffres clés côte à côte, gros

```
   0,91           319              24 637
  AUC-PR    transactions       circuits fermés
             bloquées            détectés
```

**Ce que tu dis (5-10 secondes) :** ton nom, le nom de l'équipe, une
phrase d'accroche du type "notre solution détecte la fraude sans bloquer
les clients honnêtes."

**Attention avec le chiffre "24 637" :** ne dis jamais "24 637 fraudes".
Ce sont des circuits fermés **détectés** (le motif A→B→A existe), pas
des fraudes **confirmées** — une partie sont sûrement des annulations
techniques normales, pas de la triche. Le vrai message, c'est "notre
détection de circuits fonctionne et trouve de vrais motifs", pas "on a
trouvé 24 637 fraudeurs". Si le jury demande une précision là-dessus, dis
ça clairement — c'est un point déjà assumé dans `GUIDE_SOUTENANCE.md`.

---

## Slide 2 — Le problème (0:00–0:30)

**Ce qu'il y a dessus :**
- Un titre court : "Le fraudeur ne dépasse jamais le seuil — il le
  contourne"
- 3 exemples visuels côte à côte — juste un mot-clé + une icône, pas de
  phrase écrite :
  - **Fractionner** — icône : un gâteau coupé en parts (ou des flèches
    qui séparent un gros bloc en petits blocs)
  - **Compte mule** — icône : une boîte aux lettres, ou une flèche qui
    entre et ressort tout de suite
  - **Trop d'opérations** — icône : plein de petites pièces qui tombent
    rapidement dans une tirelire (montre "beaucoup de petites actions au
    lieu d'une grosse")
- Une phrase en bas, en évidence : "Le vrai défi : ne pas accuser à tort
  un marchand ou un salarié."

**Pourquoi une icône plutôt qu'une phrase :** la règle du guide, c'est
peu de texte. L'image remplace la phrase — tu gardes l'analogie
("couper un gâteau", "boîte aux lettres", "des dizaines de petites
opérations plutôt qu'une grosse") pour la dire à l'oral, pas pour
l'écrire. Ce sont les mots que
BAMIS utilise lui-même dans son cahier des charges — les dire à voix
haute montre que tu as vraiment lu et compris leur document, et l'icône
seule reste compréhensible même sans bagage technique.

**Ce que tu dis :** reprends le texte déjà préparé dans
`GUIDE_SOUTENANCE.md`, section "Problème métier" — et en montrant chaque
icône, dis son analogie à voix haute ("comme couper un gâteau en petites
parts", "une boîte aux lettres : ça entre, ça ressort", "plein de
petites opérations plutôt qu'une grosse, pour rester sous les radars").

---

## Slide 3 — Notre solution (0:30–1:15)

**Ce qu'il y a dessus :**
- Titre : "3 niveaux de détection"
- Un schéma simple à 3 boîtes, avec une flèche entre elles :

```
[ Règles ]         →   [ Modèle IA ]        →   [ Graphe (réseau) ]
Repère les cas         Croise plusieurs          Suit l'argent entre
évidents, tout de      signaux à la fois,        les comptes, trouve
suite                  même invisibles à          les réseaux et
                        l'œil nu                   les complices
```

- Un seul chiffre gros, en bas, avec sa traduction en mots simples juste
  à côté (pas juste le sigle technique) :

```
        0,91 / 1
  Note de performance du modèle
  (plus proche de 1 = meilleur)

  Plus de 2x mieux qu'une méthode
  simple, sans intelligence artificielle (0,42)
```

  Le sigle technique "AUC-PR" n'apparaît pas sur la slide — garde-le
  pour l'oral, seulement si le jury demande le nom exact de la mesure.

**Ce que tu dis :** les 3 niveaux existent parce qu'aucun seul niveau ne
suffit — les règles simples ratent les schémas complexes, le modèle seul
n'explique pas pourquoi, le graphe seul est lent sur une seule
transaction. Si le jury demande le nom de la mesure : "c'est l'AUC-PR,
la mesure recommandée par le cahier des charges pour ce genre de
problème, parce que la fraude est rare — une mesure classique comme
l'accuracy serait trompeuse."

---

## Slide 4 — Démonstration en direct (1:15–4:15)

**Ce n'est pas une vraie slide de contenu** — juste un titre de
transition ("Démonstration") puis tu bascules sur le dashboard en
direct dans le navigateur.

**Avant la soutenance :**
- Ouvre le dashboard à l'avance dans un onglet, connexion déjà testée.
- Prépare 2 cas concrets en favoris ou notés sur un papier (voir
  `GUIDE_SOUTENANCE.md`, section "Cas concrets") — ne cherche jamais en
  direct devant le jury.
- Suis exactement les 6 étapes chronométrées déjà écrites dans
  `GUIDE_SOUTENANCE.md`.

**Plan B, si internet coupe ou le dashboard charge mal :**
- Prends des **captures d'écran** des 5-6 étapes de la démo (les mêmes
  cas concrets), sauvegardées en local sur l'ordinateur, PAS dans le
  cloud — accessibles même sans connexion.
- Mets-les dans une slide de secours cachée (à la fin du PPT), prête à
  afficher si le direct plante.
- Si ça arrive : reste calme, dis simplement "le dashboard est aussi
  disponible en ligne en permanence, voici des captures en attendant" —
  ne t'excuse pas longtemps, enchaîne.
- Teste le dashboard sur le vrai wifi de la salle si possible, avant ton
  passage, pas juste chez toi la veille.

---

## Slide 5 — Résultats et impact (4:15–5:15)

**Ce qu'il y a dessus :**
- Titre : "Ce que ça change concrètement pour BAMIS"
- 3 chiffres gros, façon tableau de bord :

```
  319                    64,5 M MRU              24 637
  transactions           protégés                circuits fermés
  bloquées                                        détectés
```

- Une ligne en dessous, avec un exemple concret plutôt qu'une phrase
  abstraite : *"Un marchand qui reçoit de l'argent de 50 clients
  différents chaque jour ? Jamais signalé à tort — on compare chaque
  client à SON PROPRE historique, pas à une moyenne générale."*

**Ce que tu dis :** reprends le texte déjà préparé, section "Résultats
et impact". L'exemple du marchand est le même que celui du cas concret
"compte agent" dans `GUIDE_SOUTENANCE.md` — dis-le avec assurance, c'est
un vrai cas vérifié dans les données, pas un exemple inventé.

**Même remarque que sur la slide 1 :** dis "24 637 circuits fermés
**détectés**", jamais "24 637 fraudes". Si tu veux être encore plus
précis à l'oral : "notre module a trouvé 24 637 motifs de circuit fermé —
certains sont sûrement des annulations normales, mais ça prouve que la
détection fonctionne vraiment, pas juste en théorie."

---

## Slide 6 — Limites et prochaine étape (5:15–6:00)

Ne termine pas sur une excuse. Termine sur "ce qu'on ferait avec BAMIS
demain" — c'est ce qui donne l'effet "ah ouais" plutôt que "ah, ils ont
pas fini".

**Ce qu'il y a dessus, en 2 blocs :**

Bloc 1 — une seule limite dite vite, pas plus :
> "On n'a pas eu accès aux vraies fraudes confirmées pour tester — on a
> vérifié la cohérence entre nos règles et notre modèle à la place."

Bloc 2, plus grand, plus visible que le bloc 1 — la suite :
> "**Avec vos vraies données de fraude, on branche la même architecture
> en quelques minutes** — pas besoin de tout refaire, juste réentraîner
> le modèle sur les vrais exemples."

- En dessous, 2 lignes courtes, façon "prochaines étapes" :
  - "Détecter les chaînes de fraude plus longues (3 comptes ou plus)"
  - "Ajuster automatiquement le seuil de chaque client selon son risque"
- Dernière ligne, en gros : "Merci — questions ?"

**Ce que tu dis :** dis la limite vite et sans t'excuser, puis enchaîne
tout de suite sur la phrase "avec vos vraies données..." — c'est la
phrase que le jury doit retenir en dernier, pas la limite.

---

## Résumé du minutage

| Slide | Temps | Durée |
|---|---|---|
| 1. Titre | 0:00 | 10s (pendant que tu te présentes) |
| 2. Problème | 0:00–0:30 | 30s |
| 3. Notre solution | 0:30–1:15 | 45s |
| 4. Démo (dashboard) | 1:15–4:15 | 3 min |
| 5. Résultats | 4:15–5:15 | 1 min |
| 6. Limites + clôture | 5:15–6:00 | 45s |

6 slides au total (dont une n'est qu'une transition vers le dashboard).
Pas plus — avec seulement 6 minutes, plus de slides veut dire moins de
temps pour parler clairement de chacune.

---

## Se préparer à le dire, pas juste à l'écrire

Le contenu ne suffit pas — c'est toi qui parles pendant 6 minutes devant
le jury, pas le PPT.

- **Répète à voix haute, avec un chrono, au moins 3 fois** avant le jour
  J. Pas juste dans ta tête — les phrases qu'on pense claires deviennent
  souvent trop longues une fois dites à voix haute.
- **Ne lis jamais une slide mot à mot.** La slide montre les chiffres, tu
  expliques avec tes mots. Si tu lis, le jury lit en même temps que toi
  et décroche.
- **Le passage vers la démo (slide 4) est le moment le plus risqué** —
  entraîne-toi à basculer de la présentation au navigateur sans silence
  gênant. Dis une phrase de transition pendant que ça charge ("je vous
  montre ça en direct sur un cas réel").
- **Chronomètre chaque répétition.** Si tu dépasses 6 minutes à
  l'entraînement, coupe du contenu — ne parle pas plus vite, ça se sent
  et ça devient confus.
- Si un mot technique t'échappe pendant les questions (4 minutes après),
  c'est normal de dire "je vérifie et je vous réponds" plutôt que
  d'inventer une réponse — plus solide qu'une fausse assurance.
