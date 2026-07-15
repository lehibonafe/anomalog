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


def test_leaves_ordinary_log_lines_untouched():
    text = "2026-01-01T00:00:00Z INFO service started on port 8080"
    assert mask_message(text) == text
