import ctypes as ct

from murmure.windows import set_app_user_model_id, shell32


def test_taskbar_app_user_model_id_is_set_before_windows_are_created():
    # The function is idempotent and returns an HRESULT-backed error instead of
    # silently accepting a broken Windows shell integration.
    set_app_user_model_id("JulesGossiaux.Murmure.Tests")
    assert shell32.SetCurrentProcessExplicitAppUserModelID.argtypes == [ct.c_wchar_p]
