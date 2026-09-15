from app.services.llm.prompt_v5 import PROMPT_VERSION, SYSTEM_PROMPT


def test_prompt_v5_requires_the_entire_result_to_be_one_sentence():
    assert PROMPT_VERSION == 'log_analysis/v5'
    assert 'entire response must be exactly one literal sentence' in SYSTEM_PROMPT
    assert 'no heading, list, paragraph break, or second sentence' in SYSTEM_PROMPT
    assert 'highest-impact conclusion' in SYSTEM_PROMPT
    assert '[1-4, 22, 25-26, 36-39]' in SYSTEM_PROMPT
    assert 'Never include an index that was not supplied' in SYSTEM_PROMPT
