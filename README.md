# Murmure

**La dictée vocale Windows qui reste sur votre ordinateur.**

Murmure transforme votre voix en texte directement dans l’application où vous travaillez : éditeur de code, navigateur, traitement de texte ou messagerie. La transcription fonctionne localement avec [Faster-Whisper](https://github.com/SYSTRAN/faster-whisper), sans compte et sans service cloud.

## Pourquoi Murmure ?

| | Ce que vous obtenez |
| --- | --- |
| **Rapide** | Un raccourci global, une capture immédiate et des modèles adaptés à votre ordinateur. |
| **Privé** | L’audio et le texte restent locaux. Aucun compte ni serveur de transcription. |
| **Précis** | Plusieurs modèles Whisper, un vocabulaire personnalisé et une correction locale optionnelle. |
| **Discret** | Une fenêtre légère, un overlay et une icône dans la zone de notification. |
| **Contrôlable** | Historique modifiable, dossier de stockage choisi, thème sombre et annulation par Échap. |

## Installation

### Utilisateur Windows

La distribution autonome se trouve dans `dist\Murmure\`. Conservez le dossier complet, notamment `_internal`, puis lancez `Murmure.exe`. Python n’est pas nécessaire pour cette version.

Au premier lancement, Murmure télécharge le modèle de transcription choisi. Ce téléchargement est conservé localement et l’application fonctionne ensuite hors ligne. Pour l’épingler à la barre des tâches, utilisez `Murmure.exe` ou le raccourci `Murmure.lnk` créé par `build.bat` ; n’épinglez pas `run.bat`.

### Depuis le dépôt

Pré-requis : Windows 10 ou 11, Python **3.11 à 3.13 x64** et un microphone.

```powershell
setup.bat
run.bat
```

`setup.bat` installe les dépendances. `run.bat` utilise l’exécutable autonome lorsqu’il est disponible, puis revient au mode Python de développement.

## Première dictée

1. Attendez le message **Prêt à dicter**.
2. Placez le curseur dans le champ où le texte doit être inséré.
3. Appuyez sur **Ctrl + Espace** pour commencer, puis à nouveau pour terminer.
4. Le texte est transcrit, enregistré dans l’historique, puis inséré dans l’application active.

**Échap** annule une capture en cours : le microphone s’arrête, l’audio est supprimé et rien n’est transcrit ni inséré. Pour interrompre complètement Murmure, choisissez **Quitter Murmure** dans le menu de l’icône près de l’horloge.

## Correction locale

Activez **Corriger automatiquement le texte** dans les paramètres pour corriger l’orthographe, la grammaire, la conjugaison, la ponctuation et les mots manifestement mal transcrits.

Le bouton **Télécharger le correcteur maintenant** permet de préparer le modèle avant la première dictée. Murmure utilise [Qwen2.5-0.5B-Instruct Q4_K_M](https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF), un modèle local d’environ 491 Mo exécuté sur CPU. Il est téléchargé une seule fois, puis utilisable hors ligne. La correction est désactivée par défaut et n’ajoute aucun délai lorsqu’elle est désactivée.

## Paramètres

- **Raccourci global** : choisissez une combinaison compatible avec votre clavier, puis cliquez sur **Appliquer les paramètres**.
- **Modèle de transcription** : Tiny et Base privilégient la vitesse ; **Small** offre un bon compromis ; Medium et Large v3 Turbo privilégient davantage la précision. Les modèles plus grands demandent plus de mémoire et peuvent être plus lents sur CPU.
- **Langue et vocabulaire** : choisissez une langue et ajoutez vos noms, acronymes ou expressions, un par ligne.
- **Microphone** : sélectionnez l’appareil Windows à utiliser.
- **Apparence** : thème clair ou sombre.
- **Données** : choisissez le dossier de l’historique et le dossier des modèles.
- **Comportement** : sons, démarrage avec Windows et réduction vers la zone de notification.

La molette est désactivée sur les sélecteurs pour empêcher toute modification accidentelle pendant le défilement. Utilisez la liste déroulante ou les touches du clavier.

Si vous quittez les paramètres avec des changements non appliqués, Murmure propose de les appliquer, de les abandonner ou de rester dans la page.

## Historique et confidentialité

Par défaut, les données sont stockées dans `%LOCALAPPDATA%\Murmure` :

| Élément | Contenu |
| --- | --- |
| `history.sqlite3` | Textes, dates, durées et états des dictées |
| `pending\` | Audio temporaire conservé uniquement en cas d’erreur ou de récupération |
| `models\` | Modèles de transcription et de correction téléchargés |
| `settings.json` | Paramètres de l’application |

L’audio est supprimé après une transcription réussie. Vous pouvez modifier, copier ou supprimer chaque texte depuis l’historique. Le dossier de l’historique peut être déplacé depuis les paramètres ; Murmure vérifie la copie avant de changer de dossier.

Aucun audio ni texte n’est envoyé à un serveur. Les modèles sont téléchargés depuis Hugging Face lors de leur première installation. Les données locales ne sont pas chiffrées par l’application.

## Insertion dans Windows

Murmure envoie le texte Unicode au contrôle actif sans utiliser le presse-papiers pour la dictée automatique. Certains contrôles personnalisés, jeux, sessions distantes ou applications lancées en administrateur peuvent bloquer cette insertion. Dans ce cas, ouvrez l’entrée dans **Historique**, cliquez sur **Copier**, puis collez-la manuellement.

## Dépannage rapide

- **Le microphone ne fonctionne pas** : vérifiez l’autorisation Microphone de Windows et choisissez le bon appareil dans les paramètres.
- **Le modèle ne se télécharge pas** : vérifiez la connexion Internet, l’espace disque et le dossier des modèles, puis relancez l’action.
- **La fenêtre semble fermée** : Murmure peut être réduit dans la zone de notification. Double-cliquez sur son icône.
- **L’ancienne version reste ouverte après une mise à jour** : choisissez **Quitter Murmure** dans le menu de l’icône, puis relancez l’application.

## Développement

Installer les dépendances de développement et lancer les vérifications :

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
```

Construire la distribution Windows :

```powershell
build.bat
```

Le build produit `dist\Murmure\Murmure.exe` et crée `Murmure.lnk` sur le Bureau. Le binaire n’est pas signé ; conservez les licences des dépendances si vous redistribuez la version construite.

## Références

- [Faster-Whisper](https://github.com/SYSTRAN/faster-whisper)
- [Qwen2.5-0.5B-Instruct GGUF](https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF)
- [llama-cpp-python](https://github.com/abetlen/llama-cpp-python)
- [SendInput — documentation Microsoft](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-sendinput)
