from app.agents.emergency_router import EmergencyRouter


def router():
    return EmergencyRouter()


def test_chest_pain_triggers():
    hits = router().check("我爸现在胸痛，出了一身汗")
    assert any(hit.rule_id == "EM_CHEST_PAIN" for hit in hits)


def test_suicide_signal_triggers():
    hits = router().check("我不想活了，想自杀")
    assert any(hit.rule_id == "EM_SUICIDE" for hit in hits)


def test_stroke_signal_triggers():
    hits = router().check("突然嘴歪，一侧肢体无力")
    assert any(hit.rule_id == "EM_STROKE" for hit in hits)


def test_normal_consult_does_not_trigger():
    assert router().check("最近睡眠不太好，想吃点清淡的") == []


def test_empty_text_does_not_trigger():
    assert router().check("   ") == []


def test_multiple_hits_reported():
    hits = router().check("胸痛而且喘不上气")
    rule_ids = {hit.rule_id for hit in hits}
    assert {"EM_CHEST_PAIN", "EM_DYSPNEA"} <= rule_ids


def test_trigger_reason_joins_messages():
    hits = router().check("胸痛")
    assert "胸痛" in router().trigger_reason(hits)
