from download_bot.auth import is_authorized


def test_authorized_chat_id_allowed():
    assert is_authorized(123, frozenset({123, 456}))


def test_unauthorized_chat_id_denied():
    assert not is_authorized(999, frozenset({123, 456}))


def test_empty_allowlist_denies_everyone():
    assert not is_authorized(123, frozenset())
