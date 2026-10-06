from app.api.routes_meta import config
from app.config import Settings


def make_settings(**overrides) -> Settings:
    return Settings(litellm_api_key="test-key", **overrides)


def test_account_filter_capability_matches_cloudtrail_configuration():
    assert config(make_settings())["cloudtrail_account_filter_available"] is False
    assert config(make_settings(cloudtrail_log_group_identifiers=" , "))[
        "cloudtrail_account_filter_available"
    ] is False
    assert config(make_settings(cloudtrail_log_group_identifiers="group-a"))[
        "cloudtrail_account_filter_available"
    ] is True
    assert config(make_settings(aws_include_linked_accounts=True))[
        "cloudtrail_account_filter_available"
    ] is True
