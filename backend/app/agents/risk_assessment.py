import hashlib
from typing import Any

from app.integrations.llm_client import LLMClient
from app.tools.risk_engine.engine import get_engine

DIMENSION_NAMES = {
    "cardiovascular": "心血管",
    "metabolic": "代谢",
    "sleep": "睡眠与疲劳",
    "mental": "心理",
    "lifestyle": "生活方式",
}

QUERY_HINTS = {
    "cardiovascular": "成人血压判定 家庭血压测量 心血管危险因素",
    "metabolic": "体重指数 腰围 血糖 血脂 判定",
    "sleep": "成年人睡眠时长 入睡困难 睡眠卫生",
    "mental": "情绪低落 压力 筛查量表 求助",
    "lifestyle": "身体活动量 久坐 膳食 食盐 饮酒",
}

SYSTEM_PROMPT = (
    "你是健康管理平台的解释助手。只能依据给定的结构化结果与检索片段写两到三句中文说明，"
    "不得新增阈值，不得下诊断，不得推荐药物或剂量。没有依据时直接说明依据不足。"
)


def _fallback_text(dimension: str, data: dict[str, Any]) -> str:
    name = DIMENSION_NAMES.get(dimension, dimension)
    level = data["level"]
    messages = [item["message"] for item in data.get("risk_factors", [])]
    if level == "高":
        return f"{name}维度存在需要尽快评估的因素：" + "；".join(messages) + "。这些是按已审核规则匹配到的结果，不等同于疾病诊断。"
    if level == "中":
        return f"{name}维度有需要关注的因素：" + "；".join(messages) + "。建议先做记录与复测，再判断是否需要就医。"
    if level == "低":
        return f"{name}维度在当前已提供的数据中未触发需要重点关注的规则。"
    missing = "、".join(data.get("missing_data", [])) or "必要指标"
    return f"{name}维度缺少{missing}，无法给出可靠判断。"


async def assess(
    snapshot: dict[str, Any],
    retriever,
    llm: LLMClient | None = None,
    use_llm: bool = False,
) -> dict[str, Any]:
    engine = get_engine()
    result = engine.evaluate(snapshot)
    knowledge_parts: list[str] = []

    for dimension, data in result["dimensions"].items():
        query = f"{DIMENSION_NAMES.get(dimension, dimension)} " + " ".join(
            item["label"] for item in data.get("risk_factors", [])
        )
        query = query.strip() or QUERY_HINTS[dimension]
        evidences = await retriever.search(query, dimension=dimension, top_k=3)
        data["evidences"] = [item.to_dict() for item in evidences]
        knowledge_parts.extend(f"{item.source_id}:{item.version}" for item in evidences)

        merged = {item["source_id"]: item for item in data.get("evidence_sources", []) if item.get("source_id")}
        for item in evidences:
            merged.setdefault(
                item.source_id,
                {"source_id": item.source_id, "title": item.title, "version": item.version, "page": item.page},
            )
        data["evidence_sources"] = list(merged.values())

        explanation = _fallback_text(dimension, data)
        if use_llm and llm is not None:
            context = "\n".join(f"{e.chapter}：{e.content[:300]}" for e in evidences) or "无检索片段"
            prompt = (
                f"维度：{DIMENSION_NAMES.get(dimension, dimension)}\n"
                f"风险等级：{data['level']}\n"
                f"命中因素：{'；'.join(item['message'] for item in data.get('risk_factors', [])) or '无'}\n"
                f"缺失数据：{'、'.join(data.get('missing_data', [])) or '无'}\n"
                f"检索片段：{context}"
            )
            refined = await llm.try_complete(SYSTEM_PROMPT, prompt, temperature=0.2)
            if refined:
                explanation = refined.strip()
        data["explanation"] = explanation

    digest = hashlib.sha1("|".join(sorted(knowledge_parts)).encode()).hexdigest()[:12]
    result["knowledge_version"] = f"kb-{digest}" if knowledge_parts else "kb-empty"
    return result


async def consult(question: str, retriever, llm: LLMClient | None = None) -> dict[str, Any]:
    evidences = await retriever.search(question, top_k=4)
    if not evidences:
        return {
            "answer": "知识库里没有检索到足够相关的资料，这个问题我不能给出可靠解释。可以换个更具体的描述，或直接咨询医生。",
            "sources": [],
        }

    context = "\n\n".join(f"[{item.source_id} {item.chapter}] {item.content[:400]}" for item in evidences)
    answer = None
    if llm is not None:
        answer = await llm.try_complete(
            SYSTEM_PROMPT,
            f"用户问题：{question}\n检索片段：\n{context}",
            temperature=0.3,
        )
    if not answer:
        lead = evidences[0]
        answer = (
            f"根据 {lead.title}（{lead.version}）中关于{lead.chapter}的内容：{lead.content[:220]}。"
            "这里只是资料摘要，不能替代医生对你个人情况的判断。"
        )
    return {
        "answer": answer,
        "sources": [item.to_dict() for item in evidences],
    }
