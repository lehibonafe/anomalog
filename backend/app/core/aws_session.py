import os
from functools import lru_cache

import boto3

from app.config import get_settings


@lru_cache
def get_boto3_session() -> boto3.Session:
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


def get_logs_client():
    return get_boto3_session().client("logs")


def get_s3_client():
    return get_boto3_session().client("s3")


def get_cloudtrail_client():
    return get_boto3_session().client("cloudtrail")
