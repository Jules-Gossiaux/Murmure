# Validation — 17 septembre 2026

## Modèles

L’option **Small** est maintenant marquée recommandée dans l’interface. Sur le CPU de cette machine, le même audio français synthétique de 7,4 secondes a été transcrit en **1,99 seconde** avec Small, après un chargement du modèle de 1,77 seconde. Le texte est plus complet que Base sur cette phrase de test. Le modèle reste chargé entre les dictées.

Large v3 Turbo est également sélectionnable et multilingue. Il est volontairement présenté avec un avertissement : le dépôt occupe environ 1,6 Go et son architecture Turbo n’implique pas une transcription plus rapide sur CPU. Le cache local présent sur cette machine était incomplet, donc je n’ai pas prétendu mesurer Turbo ; son premier démarrage devra terminer le téléchargement.

## Révision 1.1 — corrections et ajouts demandés

**39 tests automatisés réussis.** Les 17 nouveaux cas couvrent la saisie et l’application immédiate d’un raccourci, les touches AZERTY et les touches de fonction seules, les trois choix de confirmation des paramètres, l’annulation de fermeture, les corrections persistantes des textes sans déplacement du curseur, le thème et son abandon, la migration de l’historique avec conservation des audios, le retour à l’état initial si la configuration ne peut pas être écrite, le refus d’écraser un historique existant et Échap pendant le démarrage du microphone ou l’enregistrement.

Le test Windows réel `tools/integration_check.py --windows-only` confirme également le remplacement effectif du raccourci (ancien inactif, nouveau actif), l’événement Échap global et sa libération. Il réexécute les vérifications Unicode, presse-papiers et overlay sans enregistrer le microphone. Résultats : `artifacts/integration/windows-revision.json`.

Les captures peuplées des deux thèmes et d’une fenêtre compacte sont produites par `tools/visual_check.py` dans `artifacts/revision-visual`. Elles ont été inspectées : texte sélectionné lisible, champs modifiables et bouton Copier séparé du champ. Les paires de couleurs principales (texte, sous-titre, sélection, bouton principal, boutons désactivés) ont un rapport de contraste calculé d’au moins 4,5:1 dans les deux thèmes.

Les données réelles de l’utilisateur n’ont pas été déplacées : le nouveau dossier ne prend effet qu’après son choix et l’application des paramètres.

L’exécutable 1.1 reconstruit a été lancé avec des données de test isolées en thème sombre : les quatre pages ont été capturées, le journal est sans erreur et la fermeture retourne le code 0 (`artifacts/exe-revision`). Ce contrôle de la révision n’a pas rechargé le modèle, dont le fonctionnement avait été vérifié séparément.

## Environnement vérifié

- Windows x64, Python 3.11.5.
- PySide6 Essentials 6.11.2, Faster-Whisper 1.2.1, CTranslate2 4.8.2, sounddevice 0.5.6.
- GPU détecté : AMD Radeon RX 6500 XT ; moteur testé sur CPU int8.
- Microphone par défaut : casque HyperX Virtual Surround Sound.

## Tests automatisés : 22 réussis

`python -m pytest -q` vérifie :

- paramètres persistants, valeurs invalides, sauvegarde d’une configuration corrompue ;
- historique Unicode, recherche avec accents et caractères spéciaux, suppression, accès concurrents et intégrité SQLite ;
- persistance des enregistrements interrompus, suppression de l’audio après conservation du texte ;
- doubles/triples pressions rapides, raccourci ignoré lorsque le moteur est occupé ;
- texte enregistré avant insertion, insertion échouée sans perte, transcription échouée puis récupération ;
- arrêt pendant une capture, attente de la prise en compte du résultat avant fermeture des ressources ;
- erreur de microphone et transcription vide ;
- disposition mémoire Win32 des événements, refus d’une cible absente ou modifiée ;
- enregistrement Windows réel d’un raccourci, conflit réel, conservation de l’ancien raccourci, remplacement à chaud ;
- modèle chargé depuis le cache et réutilisé ;
- repli CUDA vers CPU simulé au chargement et pendant l’itération des segments ;
- découpage d’une capture de 184 secondes sans perte d’échantillons.

`ruff check`, `ruff format --check`, `compileall` et `pip check` passent également.

## Intégration Windows réelle

`tools/integration_check.py` a réussi :

- création d’un contrôle EDIT dans un autre processus ;
- insertion exacte de « Bonjour, été, cœur, FSRS ! 日本語 🙂 » ;
- préservation du texte du presse-papiers ;
- overlay affiché sans changement de fenêtre ni de contrôle actif ;
- raccourci global généré par événements clavier, avec une seule activation malgré une répétition de touche ;
- capture du microphone physique : **0,96 s à 44 100 Hz**, sans erreur PortAudio. L’audio capturé a ensuite été supprimé, sans transcription ;
- synthèse vocale française locale via Microsoft Hortense Desktop puis transcription avec le réseau Hugging Face désactivé ;
- conservation du même objet modèle entre les utilisations et filtrage d’un audio silencieux.

Mesure indicative, sur une phrase synthétique : **7,44 s d’audio → 0,75 s de transcription CPU** ; chargement du moteur : **1,13 s**. Ce n’est pas une garantie de latence pour d’autres voix, durées ou modèles.

La phrase transcrite était : « Bonjour, ceci est un test de dicté vocale. Le texte reste sur cet ordinateur. » L’erreur « dicté » illustre que la reconnaissance n’est pas parfaite, même sur un échantillon propre.

Résultats détaillés : `artifacts/integration/results.json`.

## Interface et distribution

L’application source a été réellement lancée. Les quatre pages ont été capturées et inspectées visuellement à l’échelle Windows de cette machine. Le moteur a atteint l’état **Prêt à dicter · base · CPU**, puis l’application a quitté proprement. Le cache Base est prêt dans `%LOCALAPPDATA%\Murmure\models`.

Une distribution PyInstaller a été construite dans `dist/Murmure` (environ 330 Mo hors modèle). **L’exécutable autonome a également été lancé avec `HF_HUB_OFFLINE=1` : moteur prêt sur CPU, quatre pages capturées et fermeture normale avec code de sortie 0, sans erreur dans le journal.** Le test de lancement avec chargement réel du modèle est reproductible avec :

```powershell
.\dist\Murmure\Murmure.exe --smoke-test --load-model
```

Le résultat machine et les captures sont dans `%LOCALAPPDATA%\Murmure\smoke-result.json` et `screenshots/`.

## À vérifier manuellement

- Une dictée parlée par l’utilisateur, dans son environnement sonore : niveau du microphone, qualité du français, acronymes et ponctuation.
- Le raccourci choisi et l’insertion dans ses applications réelles : VS Code, navigateur, Word, Discord, etc. Le test automatisé a utilisé un contrôle Windows standard, pas chacune de ces applications.
- Le comportement des champs personnalisés ou élevés en administrateur. `SendInput` ne garantit pas qu’une application accepte le texte ; l’historique reste le recours.
- Un débranchement physique du microphone pendant une dictée, la mise en veille et la reprise de Windows.
- Le démarrage à l’ouverture d’une vraie session Windows ; la machine n’a pas été déconnectée ni redémarrée pour ce test.
- CUDA sur une carte NVIDIA avec ses bibliothèques compatibles. Le repli a été testé par simulation ; cette machine ne permet pas le test GPU réel.
- Distribution sur une autre machine, installation Python vierge, signature et éventuel avertissement SmartScreen. L’exécutable est non signé.
