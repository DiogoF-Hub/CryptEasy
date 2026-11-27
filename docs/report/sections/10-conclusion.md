# 10. Conclusion

## Le bilan par rapport au cahier des charges

CryptEasy fait ce que le cahier des charges demandait. L'application génère des paires de clés RSA ou X25519, chiffre un fichier pour un destinataire avec un chiffrement hybride, le déchiffre avec une clé privée protégée par une phrase secrète, et garde un carnet de contacts. Elle est livrée sous la forme d'un exécutable Windows autonome, publié le 22 novembre (`v1.0.0rc1`). Nous avons ajouté le chiffrement de dossiers, les niveaux de sécurité, une interface en français et en anglais, et un binaire Linux. La signature des fichiers et la version macOS n'ont pas été faites, mais la signature est déjà préparée dans les clés (section 9).

Le résultat est vérifié : 636 tests automatiques à chaque modification, sous Windows et Linux, et des tests manuels sur l'exécutable, sans aucun bug bloquant (section 8).

## Ce que nous retenons de la gestion de projet

Le plan du cahier des charges n'a pas tenu : le développement a démarré avec cinq semaines de retard. Ce qui a sauvé le projet, c'est de l'avoir reconnu le 8 novembre et d'avoir changé de méthode plutôt que de serrer le même planning. Nous avons réorganisé le projet en trois sprints d'une semaine, avec une revue à chaque fin, des rôles répartis selon ce que chacun savait faire, et un board où chaque tâche a une estimation et un temps réel. Ce rythme a vraiment rendu le projet dynamique : chaque semaine avait un objectif clair et une échéance proche, ce qui nous avait justement manqué au début. Les sprints ont tenu l'essentiel de leurs objectifs et la date de rendu est respectée : au final, ce retard n'a pas été si grave.

Nous retenons aussi que les outils de suivi servent autant à raconter le projet qu'à le mener. Le board, l'historique Git, les comptes rendus et le journal des décisions nous ont permis d'écrire ce rapport avec des dates et des chiffres réels, et non de mémoire. Enfin, la relecture systématique du code, décidée au départ pour la qualité, a trouvé de vraies failles de sécurité avant qu'elles n'arrivent dans l'exécutable.

Si c'était à refaire, nous travaillerions en sprints d'une semaine dès la fin du cahier des charges : nous aurions vu notre retard tout de suite, au lieu de le découvrir cinq semaines plus tard.
