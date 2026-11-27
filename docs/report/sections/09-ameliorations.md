# 9. Pistes d'amélioration

## Fonctionnalités non réalisées

**La signature de fichiers.** Le cahier des charges la prévoyait comme fonction complémentaire. Le 8 novembre, faute de temps, nous l'avons gardée en objectif secondaire, sans la planifier dans les sprints. Le plus dur est pourtant déjà fait : depuis le 18 octobre, chaque paire de clés contient aussi une clé de signature Ed25519. Ajouter la signature ne changerait donc rien aux clés et aux contacts existants : il resterait à signer le paquet au chiffrement et à vérifier la signature au déchiffrement.

**La version macOS.** Elle n'était pas prioritaire dans le planning du 8 novembre et n'a pas été faite. Le code Python ne dépend pas du système : il manque surtout une étape de build sur un runner macOS dans la CI, puis un test sur un vrai Mac.

## Améliorations techniques

**Signer l'exécutable Windows.** Au premier lancement, Windows SmartScreen affiche « Windows a protégé votre ordinateur », parce que l'exe n'est pas signé (constaté pendant les tests manuels, #24). L'utilisateur doit cliquer sur « Informations complémentaires », puis « Exécuter quand même ». Un certificat de signature de code supprimerait cet avertissement, mais il est payant.

**L'espacement des cartes de la page Info (#67).** En testant l'exe, Diogo a remarqué que certaines cartes de la page Info se touchent, sans espace entre elles. Le problème est uniquement visuel : rien n'est cassé. Il a été trouvé après le gel du code du 22 novembre, où nous avions décidé de ne plus corriger que les bugs qui empêchent l'appli de fonctionner. Nous l'avons donc noté dans l'issue #67 plutôt que de le corriger : ce serait la première correction d'une prochaine version.

**Tester la fenêtre de l'appli dans la CI.** La CI construit le binaire Linux et le lance, mais sans sa fenêtre, parce qu'elle n'a pas d'écran. La fenêtre n'a donc été vérifiée qu'à la main (Debian 13, Ubuntu 22.04 et 26.04). Un écran virtuel dans la CI permettrait de la vérifier à chaque modification.

## Organisation : ce que nous ferions autrement

**Commencer le code tout de suite, par petits morceaux.** Le développement a démarré avec 5 semaines de retard (section 4.1) : après le cahier des charges, aucune échéance proche ne nous poussait à commencer. Avec des sprints courts dès la fin septembre, même sur une petite partie du moteur, le retard se serait vu en une semaine, et pas le 8 novembre.

**Planifier selon notre rythme d'alternance.** Les semaines à l'IUT et en entreprise ne nous laissent pas le même temps libre, et nous l'avons découvert en cours de route (section 4.3). La prochaine fois, nous en tiendrions compte dès le planning, en plaçant les tâches les plus longues sur les semaines où chacun a le plus de temps.

**Livrer tôt ce dont les autres ont besoin.** L'exécutable est arrivé le dernier jour du sprint 2, et les tests manuels ont dû passer après le gel du code (section 4.4). Une première version de l'exécutable, même incomplète, dès le milieu du sprint aurait permis de commencer les tests plus tôt.

**Écrire le rapport en Markdown dès le début.** Le Word partagé cassait la mise en forme à chaque modification, et nous ne sommes passés à un fichier par section que le 24 novembre. Avec ce format dès octobre, le rapport aurait avancé au fil des sprints, relu par pull request comme le code.
