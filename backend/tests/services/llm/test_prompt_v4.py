from app.services.llm.prompt_v4 import PROMPT_VERSION, SYSTEM_PROMPT


def test_prompt_v4_has_apm_and_evidence_guardrails():
    assert PROMPT_VERSION == "log_analysis/v4"
    assert "traffic, errors, latency, and saturation" in SYSTEM_PROMPT
    assert "partial or filtered" in SYSTEM_PROMPT
    assert "Evidence Gaps" in SYSTEM_PROMPT
    assert "Never invent" in SYSTEM_PROMPT
