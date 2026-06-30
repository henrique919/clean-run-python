from __future__ import annotations

import os
import tempfile
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from app import main as app_main
from app.store import CleanRunStore
from tests.test_auth_permissions import AsgiClient, bearer


QA_ENV_KEYS = {
    "APP_ENV",
    "CLEANRUN_ENV",
    "CLEANRUN_ENABLE_QA_ACCESS",
    "CLEANRUN_QA_ACCESS_TOKEN",
    "CLEANRUN_QA_PROJECTS",
    "CLEANRUN_QA_EMAIL",
}


@contextmanager
def qa_env(**values: str):
    previous = {key: os.environ.get(key) for key in QA_ENV_KEYS}
    for key in QA_ENV_KEYS:
        os.environ.pop(key, None)
    os.environ.update(values)
    try:
        yield
    finally:
        for key in QA_ENV_KEYS:
            os.environ.pop(key, None)
        for key, value in previous.items():
            if value is not None:
                os.environ[key] = value


def test_qa_access_is_disabled_by_default():
    client = AsgiClient(app_main.app)

    with qa_env(APP_ENV="production", CLEANRUN_ENV="production"):
        config = client.get("/api/auth/config")
        request = client.post("/api/auth/qa", json={"token": "anything"})
        state = client.get("/api/state", headers=bearer("qa:anything"))

    assert config.status_code == 200
    assert config.json()["qa_access_enabled"] is False
    assert request.status_code == 404
    assert state.status_code == 401


def test_qa_access_fails_closed_when_secret_is_missing():
    client = AsgiClient(app_main.app)

    with qa_env(APP_ENV="production", CLEANRUN_ENV="production", CLEANRUN_ENABLE_QA_ACCESS="true"):
        config = client.get("/api/auth/config")
        request = client.post("/api/auth/qa", json={"token": "anything"})

    assert config.status_code == 200
    assert config.json()["qa_access_enabled"] is False
    assert request.status_code == 404


def test_qa_access_rejects_wrong_token():
    client = AsgiClient(app_main.app)

    with qa_env(
        APP_ENV="production",
        CLEANRUN_ENV="production",
        CLEANRUN_ENABLE_QA_ACCESS="true",
        CLEANRUN_QA_ACCESS_TOKEN="correct-secret",
    ):
        request = client.post("/api/auth/qa", json={"token": "wrong-secret"})
        state = client.get("/api/state", headers=bearer("qa:wrong-secret"))

    assert request.status_code == 401
    assert state.status_code == 401


def test_qa_access_token_loads_scoped_site_manager_workspace():
    with tempfile.TemporaryDirectory() as temp_dir:
        store = CleanRunStore(Path(temp_dir) / "cleanrun.json")
        client = AsgiClient(app_main.app)
        with patch.object(app_main, "store", store), qa_env(
            APP_ENV="production",
            CLEANRUN_ENV="production",
            CLEANRUN_ENABLE_QA_ACCESS="true",
            CLEANRUN_QA_ACCESS_TOKEN="correct-secret",
            CLEANRUN_QA_PROJECTS="Jura Noosa",
            CLEANRUN_QA_EMAIL="qa.launch@cleanrun.local",
        ):
            issued = client.post("/api/auth/qa", json={"token": "correct-secret"})
            assert issued.status_code == 200

            token = issued.json()["access_token"]
            state = client.get("/api/state", headers=bearer(token))

    assert token == "qa:correct-secret"
    assert state.status_code == 200
    payload = state.json()
    assert payload["user"]["authMethod"] == "qa"
    assert payload["user"]["email"] == "qa.launch@cleanrun.local"
    assert payload["user"]["projectRoles"] == {"Jura Noosa": "site_manager"}
    assert payload["settings"]["projects"] == ["Jura Noosa"]


def test_normal_dev_auth_remains_unchanged_when_qa_is_off():
    with tempfile.TemporaryDirectory() as temp_dir:
        store = CleanRunStore(Path(temp_dir) / "cleanrun.json")
        client = AsgiClient(app_main.app)
        with patch.object(app_main, "store", store), qa_env(APP_ENV="development", CLEANRUN_ENV="development"):
            state = client.get("/api/state", headers=bearer("dev-site-manager"))

    assert state.status_code == 200
    assert state.json()["user"]["authMethod"] == "dev"

