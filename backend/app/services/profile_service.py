from datetime import date
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import HealthProfile, MedicalHistory
from app.repositories import health as repo
from app.schemas.health import MedicalHistoryOut, ProfileOut, ProfilePatch
from app.tools.metrics import SNAPSHOT_METRICS

HISTORY_CODES = {
    "hypertension": "高血压",
    "diabetes": "糖尿病",
    "chd": "冠心病",
    "stroke": "脑卒中",
    "cvd": "心血管疾病",
    "dyslipidemia": "血脂异常",
}


def age_of(birth_date: date | None) -> int | None:
    if not birth_date:
        return None
    today = date.today()
    return today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))


def compute_bmi(height_cm: float | None, weight_kg: float | None) -> float | None:
    if not height_cm or not weight_kg:
        return None
    meters = height_cm / 100
    return round(weight_kg / (meters * meters), 1)


def _f(value) -> float | None:
    return float(value) if value is not None else None


async def ensure_profile(session: AsyncSession, user_id: UUID) -> HealthProfile:
    profile = await repo.profile_of(session, user_id)
    if profile:
        return profile
    profile = HealthProfile(user_id=user_id, lifestyle={})
    session.add(profile)
    await session.flush()
    return profile


async def patch_profile(session: AsyncSession, user_id: UUID, data: ProfilePatch) -> HealthProfile:
    profile = await ensure_profile(session, user_id)
    # exclude_unset 已经能区分「没传这个字段」与「传了 null」，所以下面不能再用
    # value is not None 过滤：那样会把清空生日、职业这类操作当成没传，点了保存也不生效
    changes = data.model_dump(exclude_unset=True)
    touched = False
    for field, value in changes.items():
        if field == "lifestyle":
            # 整体传 null 表示不动生活方式；子键传 null 表示把这个子键去掉
            if value is None:
                continue
            merged = dict(profile.lifestyle or {})
            for key, item in value.items():
                if item is None:
                    merged.pop(key, None)
                else:
                    merged[key] = item
            if merged != (profile.lifestyle or {}):
                profile.lifestyle = merged
                touched = True
        elif value is None:
            # 显式清空。本来就是空的不算改动，避免空保存也递增版本
            if getattr(profile, field) is not None:
                setattr(profile, field, value)
                touched = True
        else:
            setattr(profile, field, value)
            touched = True
    if touched:
        # 档案版本是历史评估快照的锚点，任何字段变动都要递增
        profile.profile_version = (profile.profile_version or 1) + 1
    # 会话依赖只负责 yield，不会在请求结束时提交，这里必须自己 commit，
    # 否则请求一结束事务被回滚，用户看到「档案已更新」但值根本没落库
    await session.commit()
    return profile


async def add_history(session: AsyncSession, user_id: UUID, payload) -> MedicalHistory:
    record = MedicalHistory(
        user_id=user_id,
        history_type=payload.history_type,
        condition_code=payload.condition_code,
        description=payload.description,
    )
    session.add(record)
    await session.flush()
    await session.commit()
    # commit 默认过期实例属性，后面还要读 id，显式刷新一次
    await session.refresh(record)
    return record


async def get_profile(session: AsyncSession, user_id: UUID) -> ProfileOut:
    profile = await ensure_profile(session, user_id)
    histories = await repo.histories_of(session, user_id)
    return ProfileOut(
        id=profile.id,
        birth_date=profile.birth_date,
        age=age_of(profile.birth_date) or profile.age_years,
        sex=profile.sex,
        height_cm=_f(profile.height_cm),
        weight_kg=_f(profile.weight_kg),
        bmi=compute_bmi(_f(profile.height_cm), _f(profile.weight_kg)),
        waist_cm=_f(profile.waist_cm),
        occupation=profile.occupation,
        lifestyle=profile.lifestyle or {},
        profile_version=profile.profile_version,
        medical_histories=[MedicalHistoryOut.model_validate(item) for item in histories],
    )


async def build_snapshot(session: AsyncSession, user_id: UUID) -> tuple[dict[str, Any], int]:
    profile = await ensure_profile(session, user_id)
    metrics = await repo.latest_metrics(session, user_id, SNAPSHOT_METRICS)
    histories = await repo.histories_of(session, user_id)
    lifestyle = profile.lifestyle or {}

    snapshot: dict[str, Any] = {
        "age": age_of(profile.birth_date) or profile.age_years,
        "sex": profile.sex,
        "height_cm": _f(profile.height_cm),
        "weight_kg": _f(profile.weight_kg),
        "waist_cm": _f(profile.waist_cm),
    }

    for code in SNAPSHOT_METRICS:
        record = metrics.get(code)
        if record is None:
            continue
        snapshot[code] = float(record.value)
        if code == "fasting_glucose":
            snapshot["glucose_fasting_confirmed"] = bool((record.measurement_context or {}).get("fasting"))

    # 最近一次测量比档案里的旧值更可信，只在没有记录时回落到档案
    if snapshot.get("waist_cm") is None and "waist_cm" in metrics:
        snapshot["waist_cm"] = float(metrics["waist_cm"].value)

    snapshot["bmi"] = compute_bmi(snapshot.get("height_cm"), snapshot.get("weight_kg"))

    personal = {h.condition_code for h in histories if h.history_type == "personal"}
    family = {h.condition_code for h in histories if h.history_type == "family"}
    snapshot["cvd_history"] = bool(personal & {"chd", "stroke", "cvd"})
    snapshot["cvd_family_history"] = "cvd" in family or "chd" in family

    keys = (
        "sleep_hours",
        "sleep_latency_min",
        "apnea_suspected",
        "daytime_sleepiness",
        "phq2_score",
        "phq9_score",
        "stress_level",
        "function_impaired",
        "exercise_days",
        "sedentary_hours",
        "smoking_status",
        "drinking_frequency",
        "salt_intake_high",
        "sugary_drinks_daily",
        "vegetable_servings",
    )
    for key in keys:
        snapshot.setdefault(key, lifestyle.get(key))

    return snapshot, profile.profile_version
