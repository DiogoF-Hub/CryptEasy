# Annexe : utilisation de l'intelligence artificielle

<!-- BROUILLON (PR en draft) : chaque membre complète sa ligne et sa partie, puis l'équipe valide le texte ensemble avant de fusionner. Yani décide où l'annexe se place dans le rapport. À vérifier aussi : ce que les consignes du module disent sur l'usage de l'IA. -->

Cette annexe dit, pour chaque membre, quels outils d'intelligence artificielle ont été utilisés, pour quoi, et comment le résultat a été vérifié. Les durées « réelles » du tableau de bord (section 3) incluent ce travail assisté : l'écart avec les estimations s'explique en partie par là.

## Qui a utilisé quoi

| Membre | Outil | Pour quoi | Comment c'est vérifié |
|---|---|---|---|
| Sam | Claude (Anthropic), dans Claude Code | code de `keystore/` et de ses tests (#11 à #13), packaging et CI (#18 à #20), relecture de PR, rédaction des sections 7.2, 7.4 et 8.1 | voir ci-dessous |
| Diogo | *à compléter* | *à compléter* | *à compléter* |
| Yanis | *à compléter* | *à compléter* | *à compléter* |
| Yani | *à compléter* | *à compléter* | *à compléter* |

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

