from typing import NamedTuple


class MetricDef(NamedTuple):
    label: str
    unit: str
    low: float
    high: float
    hint: str = ""


# 指标编码在数据库与前端之间共用，改动会破坏历史数据解释
METRIC_DEFS: dict[str, MetricDef] = {
    "systolic_bp": MetricDef("收缩压", "mmHg", 60, 260, "静坐五分钟后测量"),
    "diastolic_bp": MetricDef("舒张压", "mmHg", 30, 160, "静坐五分钟后测量"),
    "heart_rate": MetricDef("静息心率", "bpm", 30, 220, "安静状态下测量"),
    "weight_kg": MetricDef("体重", "kg", 25, 300, "晨起空腹固定时间测量"),
    "waist_cm": MetricDef("腰围", "cm", 40, 200, "呼气末测量"),
    "fasting_glucose": MetricDef("空腹血糖", "mmol/L", 2, 35, "至少空腹八小时"),
    "hba1c": MetricDef("糖化血红蛋白", "%", 3, 20, "以化验单为准"),
    "ldl_c": MetricDef("低密度脂蛋白胆固醇", "mmol/L", 0.3, 15, "以化验单为准"),
    "hdl_c": MetricDef("高密度脂蛋白胆固醇", "mmol/L", 0.2, 5, "以化验单为准"),
    "triglycerides": MetricDef("甘油三酯", "mmol/L", 0.1, 30, "空腹八小时以上"),
    "sleep_hours": MetricDef("睡眠时长", "h", 0, 24, "按实际入睡到起床计算"),
}

# 进入评估快照的指标，未列出的仅供趋势查看
SNAPSHOT_METRICS = (
    "systolic_bp",
    "diastolic_bp",
    "weight_kg",
    "waist_cm",
    "fasting_glucose",
    "hba1c",
    "ldl_c",
    "hdl_c",
    "triglycerides",
    "sleep_hours",
)


def metric_label(code: str) -> str:
    definition = METRIC_DEFS.get(code)
    return definition.label if definition else code
