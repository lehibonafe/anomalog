from functools import lru_cache

import boto3

from app.config import get_settings


@lru_cache
def get_boto3_session() -> boto3.Session:
    settings = get_settings()
    kwargs: dict = {}
    if settings.aws_profile:
        kwargs["profile_name"] = settings.aws_profile
    if settings.aws_region:
        kwargs["region_name"] = settings.aws_region
    return boto3.Session(**kwargs)


def get_logs_client():
    return get_boto3_session().client("logs")


def get_s3_client():
    return get_boto3_session().client("s3")
