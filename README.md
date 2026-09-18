# Murmure

Une application Windows de dictée vocale **locale**, en français, avec Faster-Whisper.

## Lancer

Sur cette machine, l’environnement et le modèle **Base** sont déjà installés : double-cliquez sur **`run.bat`**.

Après une mise à jour, utilisez d’abord **Quitter Murmure** dans le menu de son icône près de l’horloge, puis relancez. Fermer seulement la fenêtre la laisse active avec l’ancienne version.

Murmure déclare son identité Windows (`JulesGossiaux.Murmure`) avant de créer sa fenêtre. La distribution `dist\Murmure\Murmure.exe` contient l’icône Murmure dans son exécutable. Après `build.bat`, un raccourci **`Murmure.lnk`** est créé sur le Bureau avec cet exécutable comme cible et comme source de l’icône : épinglez ce raccourci (ou l’exécutable) à la barre des tâches. N’épinglez pas `run.bat`, car Windows l’associe au lanceur Python et peut alors afficher l’icône Python.

Une distribution autonome se trouve également dans **`dist\Murmure\Murmure.exe`**. Conservez le dossier `Murmure` entier, notamment `_internal` : l’exécutable n’est pas un fichier isolé.

Sur une nouvelle installation :

1. Installez Python **3.11 à 3.13 x64** si nécessaire.
2. Double-cliquez sur **`setup.bat`** et attendez la fin de l’installation.
3. Double-cliquez sur **`run.bat`**. Le premier téléchargement du modèle nécessite Internet ; la suite fonctionne hors ligne.

Le mode autonome n’a pas besoin de Python installé. Sur un autre ordinateur, il doit télécharger son modèle au premier démarrage, ou retrouver un cache copié dans le dossier de données.

## Dicter

1. Attendez **« Prêt à dicter »**.
2. Placez le curseur dans un champ de votre application.
3. **Ctrl + Espace** commence la capture ; appuyez de nouveau pour terminer.
4. L’overlay montre l’enregistrement puis la transcription. Le texte est enregistré dans l’historique avant son insertion.

**Échap annule l’enregistrement en cours** : le microphone s’arrête, l’audio et l’entrée provisoire sont supprimés, sans transcription ni insertion. Échap n’est réservé globalement que pendant la capture. Le bouton **Annuler · Échap** dans l’application est également disponible.

Le bouton de dictée et l’action de la zone de notification masquent la fenêtre et vous laissent **3 secondes** pour placer le curseur. Le raccourci global démarre directement, sans compte à rebours.

Fermer la fenêtre laisse normalement Murmure actif. Double-cliquez sur son icône dans la zone de notification pour la rouvrir. Pour arrêter complètement : clic droit sur l’icône → **Quitter Murmure**. Les pressions pendant une transcription sont ignorées, afin de ne pas lancer de tâches concurrentes.

## Réglages

- **Raccourci** : cliquez sur le champ, appuyez sur une combinaison et appliquez. La capture utilise les touches Windows réelles, notamment sur AZERTY. L’ancien raccourci est suspendu pendant la saisie, puis rétabli tant que le nouveau n’a pas été appliqué. S’il est occupé, un message l’indique. Les touches de fonction seules (par exemple F9) sont également acceptées, sous réserve des réservations Windows.
- **Microphone** : périphérique Windows par défaut ou appareil précis. Le bouton ↻ actualise la liste. Windows peut présenter plusieurs interfaces du même appareil.
- **Modèle** : Tiny privilégie la vitesse ; Base reste le plus rapide ; **Small est recommandé** pour améliorer la précision sans trop augmenter l’attente (mesuré ici : environ 2 secondes pour 7,4 secondes d’audio sur CPU). **Large v3 Turbo** est disponible pour une reconnaissance multilingue plus puissante, mais son nom ne garantit pas une latence inférieure sur CPU et son téléchargement est important ; Medium reste disponible. Chaque choix affiche son explication dans les paramètres. Tailles approximatives : Tiny 75 Mo, Base 145 Mo, Small 485 Mo, Turbo 1,6 Go, Medium 1,5 Go. Sélectionnez le modèle, puis **Appliquer les paramètres**. Le premier téléchargement et le chargement se font en arrière-plan ; le modèle reste ensuite en mémoire.

Le temps de transcription mesuré est affiché après chaque dictée. Un modèle plus grand peut dépasser 2 secondes sur CPU, et une longue dictée peut dépasser 10 secondes : aucun délai maximal n’est garanti. Si votre priorité est 1–2 secondes, commencez par Small sur cette machine, puis comparez avec Turbo. Le nom Turbo décrit l’accélération de son architecture ; il ne signifie pas qu’il est plus rapide que Base ou Small.

Dans les paramètres, **Corriger automatiquement le texte** active un second modèle local compact. Murmure utilise **Qwen2.5-0.5B-Instruct Q4_K_M** (environ 491 Mo, CPU, licence Apache-2.0) pour corriger l’orthographe, la grammaire et les mots manifestement mal transcrits. Il est téléchargé au premier texte à corriger dans le dossier des modèles, puis fonctionne hors ligne. La correction est désactivée par défaut et n’ajoute aucun délai lorsqu’elle est désactivée.
- **Langue** : français initialement, détection automatique ou six autres langues.
- **Vocabulaire** : expressions et acronymes, un par ligne, transmis à Faster-Whisper via `hotwords`. Ce sont des indications, pas un dictionnaire de remplacement garanti. Les listes courtes fonctionnent mieux.
- **Sons**, **fermeture vers la zone de notification** et **démarrage à l’ouverture de Windows** sont facultatifs. Le lancement automatique utilise uniquement la clé de registre de votre utilisateur.
- **Apparence** : thème clair ou sombre, aperçu immédiat puis conservation avec **Appliquer les paramètres**.
- **Emplacement de l’historique** : choisissez un dossier, puis appliquez. Les textes existants sont transférés via une copie SQLite vérifiée. Un dossier contenant déjà un historique n’est jamais écrasé. Les audios temporaires, modèles et réglages restent dans le dossier de l’application.

Si vous quittez les paramètres, fermez la fenêtre ou quittez l’application avec des modifications non appliquées, Murmure propose **Appliquer**, **Ne pas appliquer** ou **Annuler**. Ne pas appliquer rétablit aussi le thème précédent.

## Historique et confidentialité

Par défaut, les données sont dans **`%LOCALAPPDATA%\Murmure`** ; les paramètres permettent d’ouvrir ce dossier. L’emplacement de l’historique peut être changé séparément : seul `history.sqlite3` est déplacé, avec ses textes, dates, durées et états. Le dossier `pending` contenant l’audio reste dans le dossier de l’application.

| Fichier / dossier | Contenu |
| --- | --- |
| `settings.json` | Paramètres enregistrés atomiquement |
| `history.sqlite3` | Textes, dates, durées, états et messages d’erreur |
| `pending\` | Audio PCM temporaire ou en attente de récupération |
| `models\` | Modèles téléchargés et utilisables hors ligne |
| `murmure.log` | Diagnostic avec rotation : 2 Mo par fichier, 3 archives |

Aucun audio ni texte n’est envoyé à un serveur. Seuls les modèles proviennent de Hugging Face ; la télémétrie du client est désactivée. Le cache local est essayé avant toute requête réseau. Les données locales ne sont pas chiffrées par l’application.

L’audio est écrit au fil de la capture, sans accumuler tout l’enregistrement en RAM. Une fois la transcription enregistrée, il est supprimé. En cas d’erreur ou d’arrêt pendant l’enregistrement, ouvrez l’historique et cliquez **Récupérer l’audio**. Une récupération n’insère pas automatiquement du texte dans une autre application.

L’historique permet de rechercher, de corriger le texte au clavier, de copier, de supprimer une entrée ou de tout effacer avec confirmation. Les champs **Dernière dictée** et **Historique** sont modifiables ; les corrections sont enregistrées automatiquement après une courte pause de saisie et avant de changer de page ou de fermer. Les deux vues restent synchronisées. Les enregistrements dont l’audio attend une récupération ne sont pas modifiables avant transcription. **Afficher davantage** donne accès aux entrées plus anciennes. Les fichiers de récupération sont supprimés avec leur entrée.

## Insertion Windows

Murmure envoie des événements clavier Unicode avec `SendInput`. Il ne remplace pas le presse-papiers pour la dictée automatique. Le bouton **Copier** le remplace explicitement, comme attendu.

L’application mémorise la fenêtre et le contrôle actif, attend que Ctrl/Alt/Maj/Windows soient relâchés, puis vérifie la cible entre les lots de caractères. Si la cible change, le texte reste dans l’historique. Elle ne ramène jamais de force une autre fenêtre au premier plan.

Windows ne fournit pas d’accusé de réception du texte par chaque application. Certains contrôles personnalisés, jeux, sessions distantes ou applications lancées en administrateur peuvent ignorer ou bloquer les événements. Dans ce cas, utilisez **Historique → Copier**, puis collez vous-même. Si une insertion a été interrompue, une partie du texte peut déjà être présente. Gardez le curseur dans le champ voulu jusqu’à la fin : plusieurs champs de navigateur peuvent partager le même contrôle Windows, et déplacer le curseur dans un champ n’est pas détectable universellement.

## Moteur et fiabilité

- Interface **PySide6 / Qt Widgets**, avec overlay qui n’active pas sa fenêtre et icône de notification native.
- Un worker dédié conserve **Faster-Whisper** en mémoire. Chargement, téléchargement, transcription et capture n’utilisent pas le thread graphique.
- **CPU int8**, ou NVIDIA CUDA en float16 si disponible. Une erreur CUDA déclenche une reprise CPU, y compris pendant l’inférence. Sur cette machine équipée d’une Radeon AMD, le CPU est utilisé.
- Décodage `beam_size=1`, température 0, filtre vocal Silero, pas de contexte entre segments, pour privilégier la réactivité et réduire les répétitions.
- Les longues captures sont transcrites en blocs de 90 secondes au maximum, avec une coupure recherchée près d’un silence dans les 5 dernières secondes. Il n’y a pas de limite volontaire de durée ; la capacité disque reste la limite. Une parole continue peut subir une erreur à une jonction de blocs.
- SQLite en mode WAL et synchronisation FULL ; le texte est validé avant toute insertion. La capture est journalisée avant l’ouverture du microphone. Les audios PCM n’ont pas d’en-tête à réparer après un crash.
- Une seule instance par utilisateur. Une nouvelle tentative de lancement indique où retrouver l’instance existante.
- Quitter pendant une transcription ou un téléchargement attend la fin de la tâche. Quitter pendant la capture conserve l’audio pour récupération. Une panne électrique peut perdre les derniers octets encore présents dans les caches du système.

## Développement et validation

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m pip check
```

Tests d’intégration réels, à lancer volontairement :

```powershell
.\.venv\Scripts\python.exe tools\prepare_model.py
.\.venv\Scripts\python.exe tools\integration_check.py
.\.venv\Scripts\python.exe launch.py --smoke-test --load-model
```

Le test d’intégration ouvre sa propre fenêtre de saisie, teste le raccourci, l’overlay et Unicode, ouvre le microphone environ une seconde, puis supprime cette capture. Il génère aussi une phrase française avec la voix Windows **Microsoft Hortense Desktop** et la transcrit hors ligne. Il requiert donc cette voix pour sa partie synthèse. Les résultats et les seuls audios synthétiques sont dans `artifacts\integration`.

Le smoke test ouvre les quatre pages, enregistre leurs captures dans `screenshots` sous le dossier de données puis quitte. `--load-model` charge également le moteur et produit `smoke-result.json`. Pour isoler les données de test : variable d’environnement `MURMURE_DATA_DIR`.

Pour construire l’exécutable : **`build.bat`**. La configuration PyInstaller produit un dossier autonome, avec les bibliothèques natives et le VAD, sans terminal et sans nécessiter de privilèges administrateur. Le binaire n’est pas signé. Pour distribuer, conservez aussi les licences des dépendances incluses.

Les responsabilités sont séparées dans `storage.py`, `audio.py`, `engine.py`, `windows.py`, `controller.py`, `ui.py`, `widgets.py` et `app.py`. Les tests critiques sont dans `tests/`.

## Références techniques

- [Faster-Whisper : moteur, CUDA, transcription et VAD](https://github.com/SYSTRAN/faster-whisper)
- [API Faster-Whisper : `hotwords` et options de transcription](https://github.com/SYSTRAN/faster-whisper/blob/master/faster_whisper/transcribe.py)
- [Qwen2.5-0.5B-Instruct GGUF](https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF)
- [llama-cpp-python](https://github.com/abetlen/llama-cpp-python)
- [Microsoft : RegisterHotKey et MOD_NOREPEAT](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-registerhotkey)
- [Microsoft : SendInput et restrictions UIPI](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-sendinput)
