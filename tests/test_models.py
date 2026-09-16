import pytest

from murmure.models import MODELS
from murmure.storage import Settings


@pytest.mark.parametrize("choice", MODELS, ids=lambda choice: choice.name)
def test_model_choice_survives_restart_and_is_supported(choice, tmp_path):
    from faster_whisper.utils import available_models

    assert choice.name in available_models()
    Settings(model=choice.name).save(tmp_path)
    assert Settings.load(tmp_path).model == choice.name
