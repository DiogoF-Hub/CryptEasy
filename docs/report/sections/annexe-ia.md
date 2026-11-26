# Annexe : utilisation de l'intelligence artificielle

<!-- BROUILLON (PR en draft) : chaque membre complète sa ligne et sa partie, puis l'équipe valide le texte ensemble avant de fusionner. Yani décide où l'annexe se place dans le rapport. À vérifier aussi : ce que les consignes du module disent sur l'usage de l'IA. -->

Cette annexe dit, pour chaque membre, quels outils d'intelligence artificielle ont été utilisés, pour quoi, et comment le résultat a été vérifié. Les durées « réelles » du tableau de bord (section 3) incluent ce travail assisté : l'écart avec les estimations s'explique en partie par là.

## Qui a utilisé quoi

| Membre | Outil | Pour quoi | Comment c'est vérifié |
|---|---|---|---|
| Sam | Claude (Anthropic), dans Claude Code | code de `keystore/` et de ses tests (#11 à #13), packaging et CI (#18 à #20), relecture de PR, rédaction des sections 7.2, 7.4 et 8.1 | voir ci-dessous |
| Diogo | Claude Code | code de `core/` et ses tests (#6 à #8, #10, #55, #60), aide à la re-planification et aux documents de gestion de projet, README, relectures de PR, brouillons de messages à l'équipe | voir ci-dessous |
| Yanis | *à compléter* | *à compléter* | *à compléter* |
| Yani | Claude (Anthropic) | organisation de ses tâches, premiers jets et relecture des sections du rapport et des slides, checklist des tests manuels (#23), aide au code de l'archivage des dossiers (#9, #60) et à Git | voir ci-dessous |

## Sam

**Utilisation.** L'assistant a écrit, à partir des issues et de la spécification :

- le code de `keystore/` et ses tests (#11 à #13), puis son branchement sur `core/keys.py` et `core/kdf.py` ;
- la recette PyInstaller, le test de fumée et les étapes de CI (#18 à #20), y compris la solution pour la fenêtre Linux ;
- des relectures : la PR #50 et la PR #59 de Yanis. Elles ont trouvé des fichiers piégés qui figeaient ou faisaient planter l'application, devenus les issues #55 et #60 ;
- des textes : issues, commentaires de PR, et les sections 7.2, 7.4 et 8.1 du rapport.

**Contrôle.**

- Chaque commit et chaque push ont été validés par Sam avant d'être faits, et chaque PR a été relue et fusionnée par Diogo.
- Le code est couvert par les tests automatiques, qui tournent sous Linux et Windows à chaque push (section 8.1).
- Les problèmes de sécurité signalés pendant les relectures ont été reproduits par un script avant d'être signalés à l'équipe.
- Chaque affirmation des sections 7.2, 7.4 et 8.1 a été vérifiée contre le code, la documentation et GitHub avant l'envoi.

## Diogo

**Utilisation.** L'assistant a écrit, à partir de la spécification et de mes consignes :

- le code de `core/` et ses tests (#6 à #8, #10), puis les correctifs #55 et #60 ;
- une aide pour les documents de gestion de projet (re-planification du 8/11, issues du board), le README et le DEV_README ;
- des relectures des PR de l'équipe (par exemple le message attendu du test F4, ou le nom vide dans « existe déjà », trouvé en relisant #59).

**Contrôle.**

- Le code de `core/` est écrit dans mon propre style (fonctions simples, chaque étape commentée), pour que je puisse expliquer chaque ligne à l'oral. Quand ce n'était pas le cas, je l'ai fait réécrire : `pem_guard.py` a été réécrit dans mon style (#55), d'où 2,5 h au lieu de 1,5.
- Rien n'a été publié sans que je le relise : commits, PR, commentaires et messages.
- Le moteur est couvert par 127 tests automatiques, qui tournent sous Linux et Windows à chaque PR. Les fichiers piégés de #55 et #60, trouvés par Sam en relisant les PR #50 et #59, sont devenus des tests.

## Yani

**Utilisation.** Je me suis servi de l'assistant comme d'un relecteur et d'un aide à la rédaction, à partir de nos sources (cahier des charges, spécification, board, historique Git) :

- pour organiser mon travail : découper mes tâches et les placer avant chaque échéance, entre les semaines à l'IUT et en entreprise ;
- pour le rapport et les slides : construire le plan, proposer un premier jet à partir des données du dépôt, puis le reformuler et le raccourcir ;
- pour la checklist des tests manuels (#23) : la dériver de la spécification, test par test ;
- pour le code de l'archivage des dossiers (#9, #60) et pour Git, que je maîtrisais mal au début du projet : comprendre les erreurs et les commandes, plutôt que de les recopier.

**Contrôle.**

- **Les faits viennent de nos sources, pas de l'assistant.** Chaque date, durée et numéro d'issue du rapport a été vérifié dans le board, l'historique Git ou le journal des décisions. Quand un premier jet ne collait pas aux sources, je l'ai corrigé ou supprimé.
- **Les résultats des tests sont les miens.** L'assistant a aidé à écrire la checklist, mais j'ai moi-même déroulé les 49 tests sous Windows et les 16 tests sur chacun des trois systèmes Linux, et noté chaque résultat (section 8.2).
- **Le code passe par les mêmes contrôles que celui des autres** : les tests automatiques sous Linux et Windows, et une relecture de Diogo avant chaque fusion. Je n'ai rien poussé que je ne savais pas expliquer.
- **Rien n'a été publié sans relecture** : chaque texte a été relu et réécrit avec mes mots, puis relu par l'équipe dans sa PR.
