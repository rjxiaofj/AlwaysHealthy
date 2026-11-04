import pytest

from app.tools.risk_engine.engine import RiskEngine, aggregate_level


@pytest.fixture(scope="module")
def engine():
    return RiskEngine()


def base_snapshot(**overrides):
    snapshot = {
        "age": 35,
        "sex": "male",
        "height_cm": 175,
        "weight_kg": 70,
        "bmi": 22.9,
        "systolic_bp": 118,
        "diastolic_bp": 76,
        "sleep_hours": 7.5,
        "exercise_days": 4,
        "sedentary_hours": 5,
        "phq2_score": 0,
        "phq9_score": 2,
        "stress_level": "low",
        "smoking_status": "never",
    }
    snapshot.update(overrides)
    return snapshot


def test_all_low_when_nothing_triggered(engine):
    result = engine.evaluate(base_snapshot())
    assert result["overall_level"] == "低"
    assert result["urgency"] == "非紧急"


def test_blood_pressure_threshold_equal_is_hit(engine):
    result = engine.evaluate(base_snapshot(systolic_bp=140, diastolic_bp=90))
    cardio = result["dimensions"]["cardiovascular"]
    assert cardio["level"] == "中"
    assert any(item["rule_id"] == "CV_SBP_140" for item in cardio["risk_factors"])


def test_blood_pressure_below_threshold_is_not_hit(engine):
    result = engine.evaluate(base_snapshot(systolic_bp=139, diastolic_bp=89))
    assert result["dimensions"]["cardiovascular"]["level"] == "低"


def test_high_blood_pressure_sets_urgency(engine):
    result = engine.evaluate(base_snapshot(systolic_bp=165, diastolic_bp=102))
    assert result["dimensions"]["cardiovascular"]["level"] == "高"
    assert result["urgency"] == "需尽快就医"


def test_bmi_uses_chinese_cut_points(engine):
    assert engine.evaluate(base_snapshot(bmi=23.9))["dimensions"]["metabolic"]["level"] == "低"
    assert engine.evaluate(base_snapshot(bmi=24))["dimensions"]["metabolic"]["level"] == "中"
    assert engine.evaluate(base_snapshot(bmi=28))["dimensions"]["metabolic"]["level"] == "高"


def test_missing_data_marks_dimension_unknown(engine):
    result = engine.evaluate(base_snapshot(sleep_hours=None))
    assert result["dimensions"]["sleep"]["level"] == "信息不足"
    assert "平均睡眠时长" in result["dimensions"]["sleep"]["missing_data"]
    assert result["overall_level"] == "信息不足"


def test_known_risk_not_lowered_by_missing_dimension(engine):
    result = engine.evaluate(base_snapshot(bmi=29, phq9_score=None, phq2_score=None))
    assert result["dimensions"]["metabolic"]["level"] == "高"
    assert result["overall_level"] == "高"


def test_aggregate_priority():
    assert aggregate_level(["低", "中", "信息不足"]) == "中"
    assert aggregate_level(["低", "高"]) == "高"
    assert aggregate_level(["低", "低"]) == "低"
    assert aggregate_level(["低", "信息不足"]) == "信息不足"


def test_fasting_flag_adds_limitation(engine):
    result = engine.evaluate(base_snapshot(fasting_glucose=5.4))
    assert any("空腹" in item for item in result["dimensions"]["metabolic"]["limitations"])
