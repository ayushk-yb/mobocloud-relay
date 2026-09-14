import json
import os

from download_bot.state import State


def test_marks_and_detects_processed(tmp_path):
    state = State(str(tmp_path))
    assert not state.already_processed(5)
    state.mark_processed(5)
    assert state.already_processed(5)


def test_last_update_id_advances(tmp_path):
    state = State(str(tmp_path))
    state.mark_processed(10)
    assert state.last_update_id == 11


def test_survives_restart(tmp_path):
    state1 = State(str(tmp_path))
    state1.mark_processed(7)

    state2 = State(str(tmp_path))
    assert state2.already_processed(7)
    assert state2.last_update_id == 8


def test_corrupted_state_file_does_not_crash(tmp_path):
    state_file = tmp_path / "state.json"
    state_file.write_text("not valid json{{{")

    state = State(str(tmp_path))
    assert state.last_update_id == 0
    state.mark_processed(1)
    assert json.loads(state_file.read_text())["last_update_id"] == 2
