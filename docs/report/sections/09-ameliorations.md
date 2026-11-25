# 9. Pistes d'amélioration

> **Rédacteur :** Yani · **Objectif :** 1 page · **Issue :** #46
>
> Premier jet. La partie « Organisation » est à valider en équipe à la revue finale du 28/11 (#39).
>
> *Supprime ce bloc de consignes (les lignes qui commencent par `>`) quand ta partie est finie.*

## Fonctionnalités non réalisées

**La signature de fichiers.** Le cahier des charges la prévoyait comme fonction complémentaire. Le 8 novembre, faute de temps, nous l'avons gardée en objectif secondaire, sans la planifier dans les sprints. Le plus dur est pourtant déjà fait : depuis le 18 octobre, chaque paire de clés contient aussi une clé de signature Ed25519. Ajouter la signature ne changerait donc rien aux clés et aux contacts existants : il resterait à signer le paquet au chiffrement et à vérifier la signature au déchiffrement.

**La version macOS.** Elle n'était pas prioritaire dans le planning du 8 novembre et n'a pas été faite. Le code Python ne dépend pas du système : il manque surtout une étape de build sur un runner macOS dans la CI, puis un test sur un vrai Mac.

## Améliorations techniques

**Signer l'exécutable Windows.** Au premier lancement, Windows SmartScreen affiche « Windows a protégé votre ordinateur », parce que l'exe n'est pas signé (constaté pendant les tests manuels, #24). L'utilisateur doit cliquer sur « Informations complémentaires », puis « Exécuter quand même ». Un certificat de signature de code supprimerait cet avertissement, mais il est payant.

**L'espacement des cartes de la page Info (#67).** En testant l'exe, Diogo a remarqué que certaines cartes de la page Info se touchent, sans espace entre elles. Le problème est uniquement visuel : rien n'est cassé. Il a été trouvé après le gel du code du 22 novembre, où nous avions décidé de ne plus corriger que les bugs qui empêchent l'appli de fonctionner. Nous l'avons donc noté dans l'issue #67 plutôt que de le corriger : ce serait la première correction d'une prochaine version.

**Tester la fenêtre de l'appli dans la CI.** La CI construit le binaire Linux et le lance, mais sans sa fenêtre, parce qu'elle n'a pas d'écran. La fenêtre n'a donc été vérifiée qu'à la main (Debian 13, Ubuntu 22.04 et 26.04). Un écran virtuel dans la CI permettrait de la vérifier à chaque modification.

## Organisation : ce que nous ferions autrement

*À compléter avec l'équipe le 28/11. Pistes issues des revues de sprint :*

- **Commencer le code plus tôt.** Le développement a démarré avec 5 semaines de retard sur le cahier des charges. Des sprints courts dès septembre auraient montré ce retard bien avant le 8 novembre.
- **Livrer tôt ce dont les autres ont besoin.** L'exe est arrivé le dernier jour du sprint 2, ce qui a repoussé les tests manuels après le gel du code.
- **Écrire le rapport en Markdown dès le début.** Le Word partagé cassait la mise en forme ; nous sommes passés à un fichier par section le 24 novembre.
