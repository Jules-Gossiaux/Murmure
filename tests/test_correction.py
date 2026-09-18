from murmure.correction import CorrectionEngine


class FakeModel:
    def create_chat_completion(self, **kwargs):
        assert kwargs["messages"][1]["content"].startswith("Corrige ce texte en français")
        return {"choices": [{"message": {"content": "Texte corrigé."}}]}


def test_correction_uses_local_chat_model(tmp_path):
    engine = CorrectionEngine(tmp_path)
    engine.model = FakeModel()
    assert engine.correct("Texte avec faute.", "fr") == "Texte corrigé."


def test_empty_correction_does_not_load_model(tmp_path):
    engine = CorrectionEngine(tmp_path)
    assert engine.correct("  ", "fr") == "  "
    assert engine.model is None
