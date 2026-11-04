from app.core.config import get_settings

URGENT_TEMPLATE = (
    "你描述的情况可能属于需要立即处理的紧急状况：{reason}。\n\n"
    "请立刻拨打当地急救电话 {phone}，或让身边的人陪同前往最近医院急诊。"
    "如果现在独自一人，先打开房门并联系一位能马上赶到的人。\n\n"
    "在等待救援期间不要自行驾车，不要服用陌生药物，不要按任何健康建议先观察。\n\n"
    "本平台无法判断你是否已经处于危险之中，也不能代替急救人员。"
    "这条提示不构成诊断，只是提醒你优先获得现场医疗帮助。"
)

MENTAL_TEMPLATE = (
    "你现在的处境听起来很危险，我很在意你的安全。\n\n"
    "请立刻联系当地急救电话 {phone}，或拨打心理援助热线 12356。"
    "如果身边有人，请告诉他们你现在的状态，让对方陪着你。\n\n"
    "如果可以，先把可能伤害自己的物品移开，去一个有其他人的地方。\n\n"
    "我不是急救人员，无法在现场保护你，现在最重要的是让真实的人来到你身边。"
)

SELF_HARM_RULES = {"EM_SUICIDE"}


def render_emergency(hits) -> str:
    settings = get_settings()
    reason = "；".join(hit.message for hit in hits) or "出现高危信号"
    rule_ids = {hit.rule_id for hit in hits}
    if rule_ids & SELF_HARM_RULES:
        return MENTAL_TEMPLATE.format(phone=settings.emergency_phone)
    return URGENT_TEMPLATE.format(reason=reason, phone=settings.emergency_phone)
