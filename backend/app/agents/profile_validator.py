from typing import Any

from app.tools.risk_engine.engine import INDICATOR_LABELS, REQUIRED_INPUTS

VALIDATORS: dict[str, tuple[float, float, str]] = {
    "height_cm": (80, 250, "身高"),
    "weight_kg": (25, 300, "体重"),
    "waist_cm": (40, 200, "腰围"),
    "systolic_bp": (60, 260, "收缩压"),
    "diastolic_bp": (30, 160, "舒张压"),
    "fasting_glucose": (2, 35, "空腹血糖"),
    "hba1c": (3, 20, "糖化血红蛋白"),
    "sleep_hours": (0, 24, "睡眠时长"),
    "sleep_latency_min": (0, 300, "入睡耗时"),
    "exercise_days": (0, 7, "每周运动天数"),
    "sedentary_hours": (0, 24, "每日久坐时长"),
}


def validate(snapshot: dict[str, Any], age_known: bool = True) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []

    age = snapshot.get("age")
    if age is None and age_known:
        warnings.append("没有出生日期，年龄相关规则无法判断")
    elif age is not None and age < 18:
        errors.append("平台第一版只覆盖 18 岁及以上成年人，未成年人评估规则不适用")

    for key, (low, high, label) in VALIDATORS.items():
        value = snapshot.get(key)
        if value is None:
            continue
        if not low <= float(value) <= high:
            errors.append(f"{label} 数值 {value} 超出可接受范围 {low} 到 {high}")

    systolic = snapshot.get("systolic_bp")
    diastolic = snapshot.get("diastolic_bp")
    if systolic is not None and diastolic is not None and diastolic >= systolic:
        errors.append("舒张压不能大于或等于收缩压，请确认读数")

    if snapshot.get("fasting_glucose") is not None and not snapshot.get("glucose_fasting_confirmed"):
        warnings.append("血糖未标记为空腹，进食状态会明显影响结果解释")

    phq9 = snapshot.get("phq9_score")
    if phq9 is not None and not 0 <= phq9 <= 27:
        errors.append("PHQ-9 总分应在 0 到 27 之间")
    phq2 = snapshot.get("phq2_score")
    if phq2 is not None and not 0 <= phq2 <= 6:
        errors.append("PHQ-2 总分应在 0 到 6 之间")

    missing: list[str] = []
    for dimension, keys in REQUIRED_INPUTS.items():
        for key in keys:
            if snapshot.get(key) is None:
                label = INDICATOR_LABELS.get(key, key)
                if label not in missing:
                    missing.append(label)

    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "missing_fields": missing,
        "assessable_dimensions": [
            dimension
            for dimension, keys in REQUIRED_INPUTS.items()
            if any(snapshot.get(key) is not None for key in keys)
        ],
    }
