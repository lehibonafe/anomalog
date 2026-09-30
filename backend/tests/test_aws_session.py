from unittest.mock import MagicMock, patch

from app.config import Settings
from app.core import aws_session


def make_settings(**overrides) -> Settings:
    return Settings(
        gemini_api_key="test-key",
        litellm_api_key="test-litellm-key",
        masking_service_api_key=None,
        **overrides,
    )


def test_get_boto3_session_uses_source_identity_without_role():
    source_session = MagicMock()
    aws_session.get_boto3_session.cache_clear()

    with (
        patch.object(aws_session, "get_settings", return_value=make_settings()),
        patch.object(aws_session, "_get_source_session", return_value=source_session),
        patch.object(aws_session, "_assume_role_session") as assume_role,
    ):
        result = aws_session.get_boto3_session()

    assert result is source_session
    assume_role.assert_not_called()
    aws_session.get_boto3_session.cache_clear()


def test_get_boto3_session_assumes_configured_monitoring_role():
    source_session = MagicMock()
    assumed_session = MagicMock()
    settings = make_settings(
        aws_role_arn="arn:aws:iam::222222222222:role/AnomalogMonitoringReadRole"
    )
    aws_session.get_boto3_session.cache_clear()

    with (
        patch.object(aws_session, "get_settings", return_value=settings),
        patch.object(aws_session, "_get_source_session", return_value=source_session),
        patch.object(
            aws_session,
            "_assume_role_session",
            return_value=assumed_session,
        ) as assume_role,
    ):
        result = aws_session.get_boto3_session()

    assert result is assumed_session
    assume_role.assert_called_once_with(source_session, settings)
    aws_session.get_boto3_session.cache_clear()


@patch("app.core.aws_session.boto3.Session")
@patch("app.core.aws_session.BotocoreSession")
@patch("app.core.aws_session.DeferredRefreshableCredentials")
@patch("app.core.aws_session.AssumeRoleCredentialFetcher")
def test_assumed_session_uses_refreshable_credentials_and_external_id(
    fetcher_class,
    credentials_class,
    botocore_session_class,
    boto3_session_class,
):
    source_session = MagicMock()
    source_credentials = MagicMock()
    source_session.get_credentials.return_value = source_credentials
    fetcher = fetcher_class.return_value
    credentials = credentials_class.return_value
    botocore_session = botocore_session_class.return_value
    target_session = boto3_session_class.return_value
    settings = make_settings(
        aws_region="us-east-1",
        aws_role_arn="arn:aws:iam::222222222222:role/AnomalogMonitoringReadRole",
        aws_role_external_id="shared-secret",
        aws_role_session_name="anomalog-test",
    )

    result = aws_session._assume_role_session(source_session, settings)

    fetcher_class.assert_called_once_with(
        client_creator=source_session._session.create_client,
        source_credentials=source_credentials,
        role_arn=settings.aws_role_arn,
        extra_args={
            "RoleSessionName": "anomalog-test",
            "ExternalId": "shared-secret",
        },
    )
    credentials_class.assert_called_once_with(
        method="assume-role",
        refresh_using=fetcher.fetch_credentials,
    )
    assert botocore_session._credentials is credentials
    botocore_session.set_config_variable.assert_called_once_with("region", "us-east-1")
    boto3_session_class.assert_called_once_with(botocore_session=botocore_session)
    assert result is target_session
