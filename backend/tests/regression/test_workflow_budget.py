"""按运行类型分档的超时预算。

之前 workflow_timeout_seconds 一刀切：咨询一句话就要跑 150 秒才止损，评估长链
又可能 150 秒不够。现在进图前用 supervisor.detect 预判 intent，长链给 long、
短链给 short，判不出时退回到 workflow_timeout_seconds。
"""
from types import SimpleNamespace

from app.services.graph_service import _budget_for


def _settings(long=150.0, short=60.0, default=150.0):
    return SimpleNamespace(
        workflow_timeout_seconds=default,
        workflow_timeout_long=long,
        workflow_timeout_short=short,
    )


def test_assessment_uses_long_budget():
    # 「评估」「风险」这些词命中 assessment，走的是 collect→assess→plan→report 长链
    assert _budget_for(_settings(), "帮我评估一下我的健康风险") == 150.0


def test_plan_adjust_uses_long_budget():
    assert _budget_for(_settings(), "这个计划太长，帮我重新制定") == 150.0


def test_consult_uses_short_budget():
    # 纯咨询是单节点短链，几十秒就该结束
    assert _budget_for(_settings(), "每天喝多少水合适") == 60.0


def test_tracking_uses_short_budget():
    assert _budget_for(_settings(), "我今天有哪些任务要打卡") == 60.0


def test_report_query_uses_short_budget():
    assert _budget_for(_settings(), "我上次评估报告说了什么") == 60.0


def test_plain_body_data_is_treated_as_assessment():
    # supervisor.detect 里：用户直接报一串身体数据（无关键词）也按评估处理
    assert _budget_for(_settings(), "我 39 岁，身高 175，体重 88，血压 145/95") == 150.0


def test_empty_content_falls_back_to_default():
    assert _budget_for(_settings(), None) == 150.0
    assert _budget_for(_settings(), "") == 150.0


def test_budget_is_configurable():
    s = _settings(long=200.0, short=45.0, default=120.0)
    assert _budget_for(s, "帮我看看健康风险") == 200.0
    assert _budget_for(s, "喝水多少合适") == 45.0
    assert _budget_for(s, None) == 120.0
