import pytest
from pydantic import ValidationError

from tac.models import EvaluationResult


VALID = {
    "decision": "accept",
    "confidence": "high",
    "dimensions": {
        "工程价值": "high",
        "技术深度": "high",
        "原创性": "medium",
        "可复用性": "high",
        "可读性": "high",
    },
    "summary": "一篇有长期工程价值的文章。",
    "tags": ["Architecture"],
    "recommendation_reason": "解释了取舍和边界。",
    "full_reasoning": "内部判断依据。",
}


def test_evaluation_result_accepts_strict_schema():
    result = EvaluationResult.model_validate(VALID)
    assert result.decision.value == "accept"
    assert result.dimensions.engineering_value.value == "high"


def test_evaluation_result_rejects_missing_field():
    data = dict(VALID)
    data.pop("full_reasoning")
    with pytest.raises(ValidationError):
        EvaluationResult.model_validate(data)

