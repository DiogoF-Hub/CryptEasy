# 3. Durées estimées et durées réelles

Depuis la re-planification du 8 novembre, chaque tâche du board a une estimation, donnée avant de commencer, et un temps réel, noté par la personne une fois la tâche finie. Le tableau complet est en annexe ; voici les tâches principales.

| Tâche | Qui | Estimé (h) | Réel (h) | Écart |
|---|---|---|---|---|
| #2 Re-planification et board | Diogo | 2 | 3 | +1 |
| #6 Génération des clés | Diogo | 4 | 3 | −1 |
| #7 KDF et niveaux de sécurité | Diogo | 3 | 2 | −1 |
| #8 Chiffrement hybride et paquet .zip | Diogo | 8 | 6 | −2 |
| #9 Archivage des dossiers | Yani | 3 | 3 | 0 |
| #11 à #13 Gestion des clés et ses tests | Sam | 9 | 9 | 0 |
| #14 Fusion de l'interface | Yanis | 0,5 | 2 | +1,5 |
| #18 à #20 Exécutables et release | Sam | 11 | 5 | −6 |
| #21 Branchement du vrai backend | Yanis | 6 | 8 | +2 |
| #24 Tests manuels de l'exécutable | Yani | 3 | 5 | +2 |
| #55 et #60 Correctifs de sécurité (non prévus) | Diogo, Yani | 3 | 5,5 | +2,5 |
| **Sprint 1, toutes tâches** | | **35,5** | **34** | **−4 %** |
| **Sprint 2, toutes tâches** | | **33,5** | **32** | **−4 %** |

S'y ajoutent 4 heures non estimées au sprint 1 : le thème graphique de l'interface (#53), un travail qui n'était pas prévu (voir section 5).

## Les plus gros écarts

**Les tâches d'organisation ont été sous-estimées.** La re-planification (#2), la mise en place du suivi (#3) et la réunion de lancement (#4) ont toutes pris plus de temps que prévu. Ce sont des tâches qu'on imagine courtes parce qu'elles ne produisent pas de code, mais elles demandent de se mettre d'accord à quatre.

**Le travail autour du code a été sous-estimé.** La fusion de l'interface (#14) était prévue en 30 minutes et a pris 2 heures : il ne s'agissait pas seulement de fusionner, il a fallu adapter toute l'interface aux règles du dépôt. Le branchement du vrai backend (#21) a pris 2 heures de plus que prévu. Le branchement lui-même est allé vite, mais il a fallu traduire chaque erreur du moteur en message français et anglais, puis faire tourner tous les tests de l'interface sur le vrai moteur.

**Les tâches techniques du moteur ont été surestimées.** Les clés, le KDF et le chiffrement hybride (#6 à #8) ont pris 4 heures de moins que prévu. La spécification technique écrite en octobre décrivait le moteur en détail : il n'y avait plus de choix à faire en codant. Les tests ont aussi été écrits en même temps que le code, au lieu de venir après.

**L'exécutable a été bien plus rapide que prévu.** Les tâches #18 à #20 ont pris 5 heures au lieu de 11. Sam s'est aidé d'un assistant d'IA, qui a accéléré la mise au point de la compilation et la recherche des problèmes.

**Les tests manuels ont grandi en cours de route.** Ils (#24) ont pris 5 heures au lieu de 3 : leur périmètre a été élargi à la revue du sprint 2, avec le binaire Linux à tester sur trois systèmes, et l'installation des machines virtuelles a posé des problèmes.

**Deux tâches non prévues ont été ajoutées.** Les correctifs de sécurité #55 et #60 viennent de failles trouvées en relisant les pull requests. Elles ont été estimées en les créant, puis ont pris presque deux fois plus de temps.

## Ce que nous en retenons

Au total, les écarts se compensent presque : chaque sprint finit 4 % sous son estimation. Mais ce total cache des écarts importants dans les deux sens : une estimation reste une estimation, certaines tâches prennent un peu moins, d'autres un peu plus. Pour mieux estimer à l'avenir, nous retenons cinq choses :
- **ne pas sous-estimer l'organisation** : une réunion ou une décision d'équipe prend plus de temps qu'on ne le pense ;
- **ajouter une marge aux tâches dont le périmètre peut changer**, comme les tests ;
- **garder une réserve pour l'imprévu** : les relectures de code trouvent des problèmes, et il faut du temps pour les corriger ;
- **estimer aussi ce qui entoure le code** : traduire les messages, adapter le code aux règles du dépôt ou faire passer les tests prend souvent plus de temps que la fonction elle-même ;
- **tenir compte des outils** : une spécification détaillée ou un assistant d'IA peuvent réduire fortement une tâche technique.
