import json
from pathlib import Path

import pytest

from app import config
from app.config import FirebaseConfigError


SERVICE_ACCOUNT = {
    "type": "service_account",
    "project_id": "test-project",
    "client_email": "admin@test-project.iam.gserviceaccount.com",
    "private_key": "test-private-key\\n",
    "token_uri": "https://oauth2.googleapis.com/token",
}


@pytest.fixture(autouse=True)
def clean_caches(monkeypatch):
    """Isolate env vars and lru caches for every test in this module."""

    for variable in (
        "FIREBASE_SERVICE_ACCOUNT_PATH",
        "FIREBASE_SERVICE_ACCOUNT_JSON",
        "FIREBASE_PROJECT_ID",
        "FIREBASE_CLIENT_EMAIL",
        "FIREBASE_PRIVATE_KEY",
    ):
        monkeypatch.delenv(variable, raising=False)

    config.get_firebase_options.cache_clear()
    yield
    config.get_firebase_options.cache_clear()


def write_service_account(directory: Path, payload: object) -> str:
    path = directory / "service-account.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return str(path)


def test_loads_service_account_from_file_path(tmp_path, monkeypatch) -> None:
    path = write_service_account(tmp_path, SERVICE_ACCOUNT)
    monkeypatch.setenv("FIREBASE_SERVICE_ACCOUNT_PATH", path)

    options = config.get_firebase_options()

    assert options == {
        "projectId": "test-project",
        "clientEmail": "admin@test-project.iam.gserviceaccount.com",
        "privateKey": "test-private-key\n",
        "tokenUri": "https://oauth2.googleapis.com/token",
    }


def test_missing_service_account_file_raises_config_error(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("FIREBASE_SERVICE_ACCOUNT_PATH", str(tmp_path / "does-not-exist.json"))

    with pytest.raises(FirebaseConfigError):
        config.get_firebase_options()


def test_invalid_json_service_account_file_raises_config_error(tmp_path, monkeypatch) -> None:
    path = tmp_path / "service-account.json"
    path.write_text("not-json{{", encoding="utf-8")
    monkeypatch.setenv("FIREBASE_SERVICE_ACCOUNT_PATH", str(path))

    with pytest.raises(FirebaseConfigError):
        config.get_firebase_options()


def test_json_non_object_service_account_file_raises_config_error(tmp_path, monkeypatch) -> None:
    path = write_service_account(tmp_path, ["not", "an", "object"])
    monkeypatch.setenv("FIREBASE_SERVICE_ACCOUNT_PATH", path)

    with pytest.raises(FirebaseConfigError):
        config.get_firebase_options()


def test_incomplete_service_account_file_raises_config_error(tmp_path, monkeypatch) -> None:
    incomplete = {key: value for key, value in SERVICE_ACCOUNT.items() if key != "private_key"}
    path = write_service_account(tmp_path, incomplete)
    monkeypatch.setenv("FIREBASE_SERVICE_ACCOUNT_PATH", path)

    with pytest.raises(FirebaseConfigError):
        config.get_firebase_options()


def test_file_path_takes_precedence_over_inline_json(tmp_path, monkeypatch) -> None:
    path = write_service_account(tmp_path, SERVICE_ACCOUNT)
    monkeypatch.setenv("FIREBASE_SERVICE_ACCOUNT_PATH", path)
    monkeypatch.setenv(
        "FIREBASE_SERVICE_ACCOUNT_JSON",
        json.dumps({**SERVICE_ACCOUNT, "project_id": "inline-json-project"}),
    )

    options = config.get_firebase_options()

    assert options["projectId"] == "test-project"


def test_expands_user_home_in_service_account_path(tmp_path, monkeypatch) -> None:
    path = write_service_account(tmp_path, SERVICE_ACCOUNT)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("FIREBASE_SERVICE_ACCOUNT_PATH", "~/service-account.json")

    options = config.get_firebase_options()

    assert options["projectId"] == "test-project"
