from app.services.masking import MASK, mask_message


def test_masks_aws_access_key():
    assert mask_message("key=AKIAIOSFODNN7EXAMPLE") == f"key={MASK}"


def test_masks_jwt():
    token = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"
    assert mask_message(f"Authorization: Bearer {token}") == f"Authorization: Bearer {MASK}"


def test_masks_basic_auth_header():
    assert (
        mask_message("Authorization: Basic dXNlcjpwYXNz")
        == f"Authorization: Basic {MASK}"
    )


def test_masks_key_value_secrets_json_style():
    assert mask_message('{"password": "hunter2"}') == '{"password": ' + MASK + "}"


def test_masks_key_value_secrets_env_style():
    assert mask_message("api_key=sk-abc123XYZ") == f"api_key={MASK}"


def test_masks_email():
    assert mask_message("user login: jane.doe@example.com") == f"user login: {MASK}"


def test_masks_ssn():
    assert mask_message("ssn 123-45-6789 on file") == f"ssn {MASK} on file"


def test_masks_valid_credit_card_number():
    assert mask_message("card 4111 1111 1111 1111 charged") == f"card {MASK} charged"


def test_does_not_mask_non_luhn_digit_sequence():
    text = "request id 1234 5678 9012 3456 processed"
    assert mask_message(text) == text


def test_masks_phone_number():
    assert mask_message("call 415-555-0132 now") == f"call {MASK} now"


def test_masks_network_identifiers():
    text = "client=192.168.1.10 ipv6=2001:db8::1 mac=00:1A:2B:3C:4D:5E"
    assert mask_message(text) == f"client={MASK} ipv6={MASK} mac={MASK}"


def test_masks_iban():
    assert mask_message("iban=GB82 WEST 1234 5698 7654 32") == f"iban={MASK}"


def test_masks_provider_tokens():
    assert mask_message("token=ghp_abcdefghijklmnopqrstuvwxyz123456") == f"token={MASK}"
    assert mask_message("slack xoxb-1234567890-abcdefghijkl") == f"slack {MASK}"
    assert mask_message("stripe sk_live_abcdefghijklmnop") == f"stripe {MASK}"


def test_masks_private_key_block():
    key = "-----BEGIN PRIVATE KEY-----\nabc123\n-----END PRIVATE KEY-----"
    assert mask_message(f"loaded {key} successfully") == f"loaded {MASK} successfully"


def test_masks_database_url_password_only():
    text = "postgresql://alice:hunter2@db.example.com/app"
    assert mask_message(text) == f"postgresql://alice:{MASK}@db.example.com/app"


def test_masks_sensitive_query_parameters():
    text = "GET /callback?token=xyz789&state=keep&code=abc123"
    assert mask_message(text) == f"GET /callback?token={MASK}&state=keep&code={MASK}"


def test_masks_contextual_pii_fields():
    text = "full_name=Alice customer_id=C-123 dob=1990-01-02 address='1 Main Street'"
    assert mask_message(text) == (
        f"full_name={MASK} customer_id={MASK} dob={MASK} address={MASK}"
    )


def test_masks_aws_account_in_arn():
    text = "principal=arn:aws:iam::123456789012:role/example"
    assert mask_message(text) == f"principal=arn:aws:iam::{MASK}:role/example"


def test_leaves_ordinary_log_lines_untouched():
    text = "2026-01-01T00:00:00Z INFO service started on port 8080"
    assert mask_message(text) == text
