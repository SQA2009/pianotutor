from pianotutor.persistence.db import Database
from pianotutor.persistence.repositories.settings_repo import SettingsRepository


def test_settings_repo_set_and_get(tmp_path):
    db = Database(tmp_path / "test.db")
    repo = SettingsRepository(db)

    assert repo.get("audio_device") is None

    repo.set("audio_device", "4")
    assert repo.get("audio_device") == "4"

    repo.set("audio_device", "9")
    assert repo.get("audio_device") == "9"

    db.close()
