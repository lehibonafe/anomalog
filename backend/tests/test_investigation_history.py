import importlib

from app.config import Settings, get_settings
from app.api import routes_investigations
from app.schemas.investigations import InvestigationWrite, SavedInvestigation
from app.services import investigation_history


def _record(question: str = "What happened?", answer: str = "Bearer secret-token") -> dict:
    return {
        "source": "CloudWatch",
        "startTime": "2026-10-20T00:00:00Z",
        "endTime": "2026-10-20T01:00:00Z",
        "turns": [{
            "id": 0,
            "question": question,
            "response": {
                "analysis": answer,
                "chunks_analyzed": 1,
                "chunks_total": 1,
                "lines_submitted": 1,
                "lines_analyzed": 1,
                "lines_omitted_by_limits": 0,
                "lines_not_analyzed": 0,
                "lines_shortened": 0,
                "lines_considered": 1,
                "lines_skipped_by_prefilter": 0,
                "model": "test-model",
                "warnings": [],
            },
        }],
    }


def test_shared_history_persists_across_connections_and_masks_text(tmp_path):
    path = str(tmp_path / "history.sqlite3")
    saved = investigation_history.save_investigation(
        path, "item-one", InvestigationWrite.model_validate(_record("Email me at user@example.com"))
    )
    assert saved.turns[0].question == "Email me at ***MASKED***"
    assert saved.turns[0].response.analysis == "Bearer ***MASKED***"

    # A second request opens a new SQLite connection and sees the same record.
    items, next_offset = investigation_history.list_investigations(path, 50, 0)
    assert [item.id for item in items] == ["item-one"]
    assert next_offset is None

    investigation_history.delete_investigation(path, "item-one")
    assert investigation_history.list_investigations(path, 50, 0)[0] == []


def test_import_does_not_overwrite_shared_edits_and_paginates(tmp_path):
    path = str(tmp_path / "history.sqlite3")
    legacy = SavedInvestigation.model_validate({
        **_record(), "id": "legacy-one", "updatedAt": "2026-10-19T00:00:00Z"
    })
    assert investigation_history.import_investigations(path, [legacy]) == 1
    investigation_history.save_investigation(
        path, "legacy-one", InvestigationWrite.model_validate(_record("Updated"))
    )
    assert investigation_history.import_investigations(path, [legacy]) == 0
    investigation_history.save_investigation(
        path, "new-two", InvestigationWrite.model_validate(_record("Second"))
    )
    first, next_offset = investigation_history.list_investigations(path, 1, 0)
    second, end_offset = investigation_history.list_investigations(path, 1, next_offset)
    assert {first[0].id, second[0].id} == {"legacy-one", "new-two"}
    assert next_offset == 1
    assert end_offset is None
    assert any(item.turns[0].question == "Updated" for item in first + second)


def test_history_routes_use_shared_store_and_are_registered(tmp_path, monkeypatch):
    monkeypatch.setenv("LITELLM_API_KEY", "test")
    get_settings.cache_clear()
    main = importlib.import_module("app.main")
    settings = Settings(
        litellm_api_key="test", anomalog_api_key="a" * 32,
        require_api_key=True, history_db_path=str(tmp_path / "history.sqlite3"),
    )
    monkeypatch.setattr(main, "settings", settings)
    saved = routes_investigations.save_investigation(
        InvestigationWrite.model_validate(_record()), "shared-one", settings
    )
    assert saved.id == "shared-one"
    listed = routes_investigations.list_investigations(50, 0, settings)
    assert [item.id for item in listed.items] == ["shared-one"]
    routes_investigations.delete_investigation("shared-one", settings)
    assert routes_investigations.list_investigations(50, 0, settings).items == []
    assert "/api/investigations" in main.app.openapi()["paths"]
    assert "/api/investigations/{investigation_id}" in main.app.openapi()["paths"]
    get_settings.cache_clear()
