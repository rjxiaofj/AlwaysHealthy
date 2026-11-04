from typing import Any

from app.tools.risk_engine.rule_loader import Rule


def _comparable(value: Any, target: Any) -> bool:
    if isinstance(value, bool) or isinstance(target, bool):
        return False
    try:
        float(value)
        float(target)
    except (TypeError, ValueError):
        return False
    return True


def compare(value: Any, operator: str, target: Any) -> bool:
    if operator == "in":
        return value in (target or [])
    if operator == "not_in":
        return value not in (target or [])
    if operator == "between":
        if not isinstance(target, (list, tuple)) or len(target) != 2:
            return False
        if not _comparable(value, target[0]):
            return False
        return float(target[0]) <= float(value) <= float(target[1])

    if operator in ("==", "!="):
        equal = value == target
        return equal if operator == "==" else not equal

    if operator in (">=", ">", "<=", "<"):
        if not _comparable(value, target):
            return False
        left, right = float(value), float(target)
        if operator == ">=":
            return left >= right
        if operator == ">":
            return left > right
        if operator == "<=":
            return left <= right
        return left < right

    return False


def filters_ok(rule: Rule, snapshot: dict[str, Any]) -> bool:
    for key, expected in rule.filters.items():
        if key == "age_gte":
            age = snapshot.get("age")
            if age is None or float(age) < float(expected):
                return False
            continue
        if snapshot.get(key) != expected:
            return False
    return True


def match_rule(rule: Rule, snapshot: dict[str, Any]) -> bool:
    if rule.status != "active":
        return False
    if not filters_ok(rule, snapshot):
        return False

    if rule.operator == "all":
        for item in rule.threshold:
            value = snapshot.get(item.get("indicator"))
            if value is None:
                return False
            if not compare(value, item.get("operator", "=="), item.get("value")):
                return False
        return True

    value = snapshot.get(rule.indicator)
    if value is None:
        return False
    return compare(value, rule.operator, rule.threshold)
