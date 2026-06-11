from core.auth import verify_password


def test_correct_password_passes():
    assert verify_password("secret123", "secret123") is True


def test_wrong_password_fails():
    assert verify_password("wrong", "secret123") is False


def test_input_whitespace_stripped():
    assert verify_password("  secret123  ", "secret123") is True


def test_unset_expected_always_fails():
    assert verify_password("anything", None) is False
    assert verify_password("anything", "") is False


def test_empty_input_fails():
    assert verify_password("", "secret123") is False
