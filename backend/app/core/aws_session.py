import os
from functools import lru_cache

import boto3
from botocore.credentials import AssumeRoleCredentialFetcher, DeferredRefreshableCredentials
from botocore.session import Session as BotocoreSession

from app.config import Settings, get_settings


@lru_cache
def _get_source_session() -> boto3.Session:
    """Return the base session backed by the local profile or EC2 role."""
    settings = get_settings()
    kwargs: dict = {}
    if settings.aws_profile:
        kwargs["profile_name"] = settings.aws_profile
    elif os.environ.get("AWS_PROFILE") == "":
        # docker compose's env_file exports the blank `AWS_PROFILE=` line as an
        # empty-string env var, which botocore reads as a profile named "" and
        # raises ProfileNotFound; treat empty as unset so the credential chain
        # can fall through to env keys / instance role
        del os.environ["AWS_PROFILE"]
    if settings.aws_region:
        kwargs["region_name"] = settings.aws_region
    return boto3.Session(**kwargs)


def _assume_role_session(source_session: boto3.Session, settings: Settings) -> boto3.Session:
    """Build an automatically refreshing session for the monitoring account."""
    extra_args = {"RoleSessionName": settings.aws_role_session_name}
    if settings.aws_role_external_id:
        extra_args["ExternalId"] = settings.aws_role_external_id

    fetcher = AssumeRoleCredentialFetcher(
        client_creator=source_session._session.create_client,
        source_credentials=source_session.get_credentials(),
        role_arn=settings.aws_role_arn,
        extra_args=extra_args,
    )
    credentials = DeferredRefreshableCredentials(
        method="assume-role",
        refresh_using=fetcher.fetch_credentials,
    )
    botocore_session = BotocoreSession()
    botocore_session._credentials = credentials
    botocore_session.set_config_variable("region", settings.aws_region)
    return boto3.Session(botocore_session=botocore_session)


@lru_cache
def get_boto3_session() -> boto3.Session:
    """Return the AWS session used by the app, optionally assumed into account B."""
    settings = get_settings()
    source_session = _get_source_session()
    if not settings.aws_role_arn:
        return source_session
    return _assume_role_session(source_session, settings)


def get_logs_client():
    return get_boto3_session().client("logs")


def get_cloudtrail_client():
    return get_boto3_session().client("cloudtrail")
