from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.config import Settings
from app.services.masking import mask_message, mask_messages_batch


def make_settings(**overrides) -> Settings:
    overrides.setdefault("masking_service_api_key", "test-masking-key")
    return Settings(gemini_api_key="test-key", litellm_api_key="test-litellm-key", **overrides)


@patch("app.services.masking.get_masking_http_client")
def test_empty_input_returns_empty_list(mock_get_client):
    result = mask_messages_batch([], make_settings())
    assert result == []
    mock_get_client.assert_not_called()


@patch("app.services.masking.get_masking_http_client")
def test_no_api_key_uses_local_masking_only_without_calling_client_getter(mock_get_client):
    texts = ["contact me at jane@example.com", "plain log line"]

    result = mask_messages_batch(texts, make_settings(masking_service_api_key=None))

    assert result == [mask_message(t) for t in texts]
    mock_get_client.assert_not_called()


@patch("app.services.masking.get_masking_http_client")
def test_client_getter_returns_none_uses_local_masking_only(mock_get_client):
    mock_get_client.return_value = None
    texts = ["contact me at jane@example.com", "plain log line"]

    result = mask_messages_batch(texts, make_settings())

    assert result == [mask_message(t) for t in texts]


@patch("app.services.masking.get_masking_http_client")
def test_success_uses_external_result_not_local(mock_get_client):
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "masked_data": {"0": "[EXTERNAL_1] said hi", "1": "line two [EXTERNAL_2]"}
    }
    mock_client.post.return_value = mock_response

    texts = ["Alice said hi", "line two Bob"]
    result = mask_messages_batch(texts, make_settings())

    assert result == ["[EXTERNAL_1] said hi", "line two [EXTERNAL_2]"]
    assert result != [mask_message(t) for t in texts]
    mock_client.post.assert_called_once()
    call_args = mock_client.post.call_args
    assert call_args.args[0] == "/api/mask/structured/"
    assert call_args.kwargs["json"] == {
        "data": {"0": "Alice said hi", "1": "line two Bob"},
        "mask_fields": ["0", "1"],
        "mode": "pipeline",
    }


@pytest.mark.parametrize(
    "make_failure",
    [
        lambda resp: setattr(
            resp, "raise_for_status", MagicMock(side_effect=httpx.HTTPStatusError(
                "bad request", request=MagicMock(), response=MagicMock(status_code=400)
            ))
        ),
        lambda resp: setattr(
            resp, "raise_for_status", MagicMock(side_effect=httpx.HTTPStatusError(
                "server error", request=MagicMock(), response=MagicMock(status_code=500)
            ))
        ),
    ],
)
@patch("app.services.masking.get_masking_http_client")
def test_http_status_error_falls_back_to_local(mock_get_client, make_failure):
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client
    mock_response = MagicMock()
    make_failure(mock_response)
    mock_client.post.return_value = mock_response

    texts = ["contact jane@example.com"]
    result = mask_messages_batch(texts, make_settings())

    assert result == [mask_message(t) for t in texts]


@patch("app.services.masking.get_masking_http_client")
def test_connection_error_falls_back_to_local(mock_get_client):
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client
    mock_client.post.side_effect = httpx.ConnectError("connection refused")

    texts = ["contact jane@example.com"]
    result = mask_messages_batch(texts, make_settings())

    assert result == [mask_message(t) for t in texts]


@patch("app.services.masking.get_masking_http_client")
def test_timeout_falls_back_to_local(mock_get_client):
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client
    mock_client.post.side_effect = httpx.TimeoutException("timed out")

    texts = ["contact jane@example.com"]
    result = mask_messages_batch(texts, make_settings())

    assert result == [mask_message(t) for t in texts]


@patch("app.services.masking.get_masking_http_client")
def test_malformed_response_falls_back_to_local(mock_get_client):
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client
    mock_response = MagicMock()
    mock_response.json.return_value = {"masked_data": {}}  # missing expected keys
    mock_client.post.return_value = mock_response

    texts = ["contact jane@example.com"]
    result = mask_messages_batch(texts, make_settings())

    assert result == [mask_message(t) for t in texts]


@patch("app.services.masking.get_masking_http_client")
def test_partial_batch_failure_falls_back_only_for_failed_chunk(mock_get_client):
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client

    success_response = MagicMock()
    success_response.json.return_value = {"masked_data": {"0": "[EXTERNAL_1]", "1": "[EXTERNAL_2]"}}

    mock_client.post.side_effect = [
        success_response,
        httpx.ConnectError("connection refused"),
    ]

    texts = ["line a", "line b", "jane@example.com", "line d"]
    settings = make_settings(masking_service_batch_size=2)

    result = mask_messages_batch(texts, settings)

    assert result[0] == "[EXTERNAL_1]"
    assert result[1] == "[EXTERNAL_2]"
    assert result[2] == mask_message("jane@example.com")
    assert result[3] == mask_message("line d")
    assert mock_client.post.call_count == 2


@patch("app.services.masking.get_masking_http_client")
def test_fail_fast_stops_calling_external_after_first_failure(mock_get_client):
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client
    mock_client.post.side_effect = httpx.ConnectError("connection refused")

    texts = ["a", "b", "c", "d"]
    settings = make_settings(masking_service_batch_size=1)

    result = mask_messages_batch(texts, settings)

    assert result == [mask_message(t) for t in texts]
    mock_client.post.assert_called_once()
