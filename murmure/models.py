"""Multilingual model choices shared by configuration and the settings UI."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelChoice:
    name: str
    label: str
    description: str


MODELS = (
    ModelChoice(
        "tiny",
        "Tiny · vitesse maximale · ≈ 75 Mo",
        "Le plus léger, mais moins précis. Utile si la vitesse passe avant la qualité.",
    ),
    ModelChoice(
        "base",
        "Base · rapide · ≈ 145 Mo",
        "Très réactif sur CPU. Moins à l’aise avec les mots rares et les phrases difficiles.",
    ),
    ModelChoice(
        "small",
        "Small · recommandé · qualité / vitesse · ≈ 485 Mo",
        "Le choix recommandé ici : meilleure précision que Base, avec environ 2 secondes mesurées pour 7,4 secondes d’audio sur votre CPU.",
    ),
    ModelChoice(
        "large-v3-turbo",
        "Large v3 Turbo · précision avancée · ≈ 1,6 Go",
        "Un modèle multilingue plus puissant, avec un décodeur accéléré. À comparer à Small : il peut être plus lent sur CPU malgré son nom Turbo.",
    ),
    ModelChoice(
        "medium",
        "Medium · qualité · plus lent sur CPU · ≈ 1,5 Go",
        "Plus exigeant en calcul. Si votre priorité est une attente de 1 à 2 secondes, essayez Small avant Medium.",
    ),
)
MODEL_BY_NAME = {model.name: model for model in MODELS}
