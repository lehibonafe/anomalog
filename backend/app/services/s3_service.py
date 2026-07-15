import gzip
from datetime import datetime

from app.config import Settings
from app.core.aws_session import get_s3_client
from app.schemas.common import LogEvent
from app.schemas.s3 import (
    S3Bucket,
    S3BucketsResponse,
    S3ContentResponse,
    S3Object,
    S3ObjectContentInfo,
    S3ObjectsResponse,
)
from app.services.masking import mask_message


def list_buckets() -> S3BucketsResponse:
    client = get_s3_client()
    resp = client.list_buckets()
    buckets = [
        S3Bucket(name=b["Name"], creation_date=b.get("CreationDate"))
        for b in resp.get("Buckets", [])
    ]
    return S3BucketsResponse(buckets=buckets)


def list_objects(
    bucket: str,
    prefix: str | None,
    start: datetime | None,
    end: datetime | None,
    continuation_token: str | None,
    max_keys: int,
) -> S3ObjectsResponse:
    client = get_s3_client()
    kwargs: dict = {"Bucket": bucket, "MaxKeys": max_keys}
    if prefix:
        kwargs["Prefix"] = prefix
    if continuation_token:
        kwargs["ContinuationToken"] = continuation_token
    resp = client.list_objects_v2(**kwargs)

    objects = []
    for obj in resp.get("Contents", []):
        last_modified = obj["LastModified"]
        if start and last_modified < start:
            continue
        if end and last_modified > end:
            continue
        objects.append(
            S3Object(key=obj["Key"], size=obj["Size"], last_modified=last_modified)
        )

    next_token = resp.get("NextContinuationToken") if resp.get("IsTruncated") else None
    return S3ObjectsResponse(objects=objects, continuation_token=next_token)


def fetch_object_content(
    bucket: str, keys: list[str], settings: Settings
) -> S3ContentResponse:
    client = get_s3_client()
    all_events: list[LogEvent] = []
    object_infos: list[S3ObjectContentInfo] = []
    total_bytes = 0
    truncated_overall = False
    line_idx = 0

    for key in keys:
        if total_bytes >= settings.max_s3_total_bytes:
            truncated_overall = True
            break

        obj = client.get_object(Bucket=bucket, Key=key)
        body = obj["Body"]
        stream = gzip.GzipFile(fileobj=body) if key.endswith(".gz") else body

        remaining_budget = min(
            settings.max_s3_object_bytes, settings.max_s3_total_bytes - total_bytes
        )
        data = stream.read(remaining_budget + 1)
        obj_truncated = len(data) > remaining_budget
        if obj_truncated:
            data = data[:remaining_budget]
            truncated_overall = True

        text = data.decode("utf-8", errors="replace")
        lines = text.splitlines()
        for line in lines:
            all_events.append(
                LogEvent(
                    source="s3",
                    origin=bucket,
                    stream_or_key=key,
                    timestamp=None,
                    message=mask_message(line),
                    line_index=line_idx,
                )
            )
            line_idx += 1

        total_bytes += len(data)
        object_infos.append(
            S3ObjectContentInfo(
                key=key,
                byte_size=len(data),
                truncated=obj_truncated,
                line_count=len(lines),
            )
        )

    return S3ContentResponse(
        events=all_events, objects=object_infos, truncated_overall=truncated_overall
    )
