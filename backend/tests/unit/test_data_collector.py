from app.agents import data_collector
from app.agents.profile_validator import validate


def test_extract_basic_fields():
    text = "我今年39岁，男，身高175，体重88公斤，血压150/95"
    found = data_collector.extract(text)
    assert found["age"] == 39
    assert found["sex"] == "male"
    assert found["height_cm"] == 175
    assert found["weight_kg"] == 88
    assert found["systolic_bp"] == 150
    assert found["diastolic_bp"] == 95


def test_extract_jin_converted_to_kg():
    found = data_collector.extract("体重140斤")
    assert found["weight_kg"] == 70


def test_extract_lifestyle_flags():
    found = data_collector.extract("每周运动1天，久坐9小时，口味重，吸烟")
    assert found["exercise_days"] == 1
    assert found["sedentary_hours"] == 9
    assert found["salt_intake_high"] is True
    assert found["smoking_status"] == "current"


def test_negation_kept():
    found = data_collector.extract("不吸烟，不喝酒")
    assert found["smoking_status"] == "never"
    assert found["drinking_frequency"] == "never"


def test_bmi_computed_on_merge():
    merged = data_collector.merge_into({}, {"height_cm": 175.0, "weight_kg": 88.0})
    assert merged["bmi"] == 28.7


def test_follow_up_skips_known_fields():
    questions = data_collector.follow_up_questions({"age": 30, "sex": "male", "height_cm": 170, "weight_kg": 60})
    assert all("年龄" not in item for item in questions)


def test_validator_rejects_minor():
    result = validate({"age": 16})
    assert result["ok"] is False
    assert any("18 岁" in item for item in result["errors"])


def test_validator_rejects_reversed_bp():
    result = validate({"age": 30, "systolic_bp": 80, "diastolic_bp": 120})
    assert result["ok"] is False


def test_validator_flags_unconfirmed_fasting():
    result = validate({"age": 30, "fasting_glucose": 5.6})
    assert result["ok"] is True
    assert any("空腹" in item for item in result["warnings"])
