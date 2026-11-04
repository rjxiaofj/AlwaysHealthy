from typing import Any


def narrate(summary: dict[str, Any]) -> str:
    total = summary.get("task_total", 0)
    done = summary.get("task_completed", 0)
    rate = summary.get("completion_rate", 0)

    parts = [f"本周期共安排 {total} 项任务，已记录完成 {done} 项，完成率 {rate}%。"]
    if total == 0:
        return "当前计划还没有任务记录，先在计划页确认计划是否已生效。"
    if rate >= 80:
        parts.append("执行情况比较稳定，可以保持现有节奏。")
    elif rate >= 50:
        parts.append("执行了一半以上，先看看剩下的任务是不是时间点不合适。")
    else:
        parts.append("完成率偏低，更可能是任务安排与作息冲突，不建议直接理解成身体状态变差。")

    metrics = summary.get("metrics", [])
    if metrics:
        lead = metrics[0]
        if lead.get("change") is None:
            parts.append(f"{lead['label']}目前只有一次记录，还看不出趋势。")
        else:
            direction = "上升" if lead["change"] > 0 else "下降" if lead["change"] < 0 else "持平"
            parts.append(
                f"{lead['label']}从 {lead['points'][0].value} 变为 {lead['latest']}{lead['unit']}，整体{direction}。"
                "单周期的变化只能作为观察线索，不能说明病情变化。"
            )
    else:
        parts.append("周期内没有指标记录，趋势部分无法判断。")

    for note in summary.get("notes", []):
        if note not in parts:
            parts.append(note)
    return "".join(parts)
