from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

RULES_DIR = Path(__file__).parent / "rules"
DIMENSIONS = ("cardiovascular", "metabolic", "sleep", "mental", "lifestyle")
REQUIRED_FIELDS = (
    "rule_id",
    "rule_version",
    "indicator",
    "condition",
    "risk_level",
    "rule_source",
    "status",
)


class RuleConfigError(ValueError):
    pass


@dataclass(frozen=True)
class Rule:
    rule_id: str
    rule_version: str
    dimension: str
    indicator: str
    operator: str
    threshold: Any
    unit: str
    applicable_population: str
    risk_level: str
    message: str
    recommended_action: list[str]
    source: dict[str, Any]
    urgency: str = "非紧急"
    filters: dict[str, Any] = field(default_factory=dict)
    excluded_conditions: list[str] = field(default_factory=list)
    status: str = "active"


def _parse_condition(raw: dict[str, Any], rule_id: str) -> tuple[str, Any]:
    if "all" in raw:
        return "all", raw["all"]
    if "operator" not in raw or "value" not in raw:
        raise RuleConfigError(f"{rule_id} condition 缺少 operator 或 value")
    return raw["operator"], raw["value"]


def load_rules(path: Path) -> tuple[str, list[Rule]]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise RuleConfigError(f"{path.name} 不是合法的规则文件")
    version = str(raw.get("version", "0"))
    dimension = raw.get("dimension")
    if dimension not in DIMENSIONS:
        raise RuleConfigError(f"{path.name} dimension 不合法: {dimension}")

    rules: list[Rule] = []
    for item in raw.get("rules", []):
        missing = [f for f in REQUIRED_FIELDS if f not in item]
        if missing:
            raise RuleConfigError(f"{path.name} 规则缺少字段 {missing}")
        operator, threshold = _parse_condition(item["condition"], item["rule_id"])
        level = item["risk_level"]
        if level not in ("低", "中", "高"):
            raise RuleConfigError(f"{item['rule_id']} risk_level 不合法: {level}")
        rules.append(
            Rule(
                rule_id=item["rule_id"],
                rule_version=str(item["rule_version"]),
                dimension=dimension,
                indicator=item["indicator"],
                operator=operator,
                threshold=threshold,
                unit=item.get("unit", ""),
                applicable_population=item.get("applicable_population", "adult"),
                risk_level=level,
                message=item.get("message", item["rule_id"]),
                recommended_action=item.get("recommended_action", []),
                source=item["rule_source"],
                urgency=item.get("urgency", "非紧急"),
                filters=item.get("filters", {}),
                excluded_conditions=item.get("excluded_conditions", []),
                status=item.get("status", "active"),
            )
        )
    return version, rules


def load_all(directory: Path = RULES_DIR) -> tuple[str, dict[str, list[Rule]]]:
    by_dimension: dict[str, list[Rule]] = {d: [] for d in DIMENSIONS}
    versions: list[str] = []
    for path in sorted(directory.glob("*.yaml")):
        if path.name == "emergency.yaml":
            continue
        version, rules = load_rules(path)
        versions.append(version)
        for rule in rules:
            by_dimension[rule.dimension].append(rule)
    engine_version = "+".join(sorted(set(versions))) or "0"
    return engine_version, by_dimension
