# 4. Difficultés rencontrées et traitement

> **Rédacteur :** Yani · **Objectif :** 1,5 page · **Issue :** #33
>
> Premier jet, à relire et à reformuler. Sources : `docs/pm/risks.md`, `docs/pm/planning-v2.md`, comptes rendus dans `docs/pm/meetings/`.
>
> *Supprime ce bloc de consignes (les lignes qui commencent par `>`) quand ta partie est finie.*

Le cahier des charges listait cinq risques. Nous avons suivi ce registre à chaque réunion de fin de sprint, en notant pour chaque risque s'il s'était produit et ce que nous avions fait (`docs/pm/risks.md`). Deux des risques prévus se sont réalisés, et d'autres difficultés sont apparues en cours de route. Pour chacune, nous décrivons ce qui s'est passé, ce que nous avons fait, et si cela a fonctionné.

## 4.1 Un démarrage tardif (risque R1)

**Ce qui s'est passé :** le développement a commencé avec 5 semaines de retard sur le cahier des charges. Nos autres cours avaient leurs propres projets, et aucune échéance proche ne nous poussait à démarrer.

**Ce que nous avons fait :** le 8 novembre, nous avons remplacé les phases du cahier des charges par 3 sprints d'une semaine, chacun avec un objectif et une revue (section 2.3).

**Est-ce que ça a marché ?** Oui. Les phases finissent 2 à 3 semaines après les dates du cahier des charges, mais les objectifs des sprints ont été tenus et la date de rendu est respectée.

## 4.2 Un écart de compétences (risque R2)

**Ce qui s'est passé :** le cahier des charges prévoyait cet écart en cryptographie. Il portait en fait sur Python et Git en général : le découpage par composant, un membre par composant, ne correspondait pas à ce que chacun savait faire.

**Ce que nous avons fait :** le 8 novembre, nous avons réparti les rôles selon les compétences (section 2.3). Yani a pris le rapport, les tests et les slides, puis s'est formé à Git au fil du projet.

**Est-ce que ça a marché ?** Oui. Chacun a travaillé là où il était le plus utile, et Yani a fini par coder lui aussi : l'archivage des dossiers (#9) et une partie des correctifs de sécurité (#60), avec des pull requests relues comme le reste de l'équipe.

## 4.3 Des semaines inégalement chargées

**Ce qui s'est passé :** nous alternons entre l'IUT et l'entreprise. Le sprint 1, en semaine à l'IUT, avait plus de tâches que le sprint 2, en semaine en entreprise. Diogo, avec 26 heures prévues au sprint 1, était le plus chargé.

**Ce que nous avons fait :** le 10 novembre, l'archivage des dossiers (#9) est passé de Diogo à Yani. À la revue du 14 novembre, les tests du moteur (#10) ont été décalés au sprint 2.

**Est-ce que ça a marché ?** En partie. La charge est restée globalement équilibrée sur l'ensemble du projet, mais au sprint 2, l'équipe n'a commencé ses tâches que le mercredi, à cause des autres projets en cours.

## 4.4 Un exécutable arrivé le dernier jour du sprint 2

**Ce qui s'est passé :** l'exécutable a été publié le 22 novembre, le jour du gel du code. Les tests manuels, qui en dépendaient, n'ont donc pas pu être faits avant la revue du sprint 2.

**Ce que nous avons fait :** à la revue du 22 novembre, nous avons décidé de faire les tests après le gel du code, et qu'un bug serait corrigé par le membre responsable de la partie concernée. Nous l'avons noté comme un nouveau risque (R8).

**Est-ce que ça a marché ?** Oui. Les tests ont été faits le 22 et le 23 novembre : 49 tests sur 49 réussis sous Windows, 16 sur 16 sur chacun des trois systèmes Linux. Aucun bug bloquant n'a été trouvé. Le seul souci, un défaut visuel mineur sur la page Info (#67), a été noté pour une prochaine version plutôt que corrigé.

## 4.5 Des failles trouvées en relisant le code

**Ce qui s'est passé :** en relisant deux pull requests, l'équipe a trouvé des fichiers piégés qui faisaient planter l'application ou afficher des erreurs brutes : des fichiers de clés (#55) et des paquets chiffrés (#60).

**Ce que nous avons fait :** nous avons créé une issue pour chaque problème, avec ses cas de test, et les avons corrigés avant le gel du code.

**Est-ce que ça a marché ?** Oui. Ces tâches n'étaient pas prévues et ont pris 5,5 heures, mais elles montrent l'intérêt de notre règle de départ : aucun code n'arrive sur la branche principale sans être relu.
