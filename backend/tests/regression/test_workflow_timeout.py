import asyncio
from types import SimpleNamespace
from uuid import uuid4

from app.services.graph_service import GraphService


class HangingGraph:
    """永远不返回的 astream：模拟某个节点卡住（模型不回、检索挂起）。

    真实场景里前端 180 秒会断连，但那只断开浏览器这一侧，后端的 run 仍挂在
    running，下次进聊天页看到一条永远「进行中」的记录。
    """

    def __init__(self) -> None:
        self.cancelled = False

    async def astream(self, *args, **kwargs):
        try:
            await asyncio.sleep(5)
        except asyncio.CancelledError:
            self.cancelled = True
            raise
        yield {}


def _service(budget: float) -> tuple[GraphService, list[tuple[str, str]]]:
    # 不走 __init__：它会去 build_main_graph，这里只验 _stream 的超时分支
    service = object.__new__(GraphService)
    service.graph = HangingGraph()
    service.settings = SimpleNamespace(workflow_timeout_seconds=budget)

    failures: list[tuple[str, str]] = []

    async def fake_fail(ctx, message, code="GRAPH_EXECUTION_ERROR"):
        failures.append((message, code))

    service._fail = fake_fail
    return service, failures


async def test_hanging_workflow_stops_at_budget():
    service, failures = _service(0.05)
    ctx = SimpleNamespace(run_id=uuid4(), conversation=SimpleNamespace(thread_id="thread-1"))

    events = [event async for event in service._stream({}, ctx, resume=False)]

    assert len(events) == 1
    name, payload = events[0]
    assert name == "run_error"
    assert payload["code"] == "WORKFLOW_TIMEOUT"
    assert payload["run_id"] == str(ctx.run_id)
    assert "预期时间内完成" in payload["message"]
    # 状态要标成 failed，且错误码能跟普通崩溃区分开
    assert failures and failures[0][1] == "WORKFLOW_TIMEOUT"
    # 超时必须真的把上游取消掉，不能只是不再读
    assert service.graph.cancelled is True


class BrokenGraph:
    """普通崩溃：用来确认超时分支没把别的异常一起吞掉。"""

    async def astream(self, *args, **kwargs):
        raise ValueError("boom")
        yield  # pragma: no cover


async def test_other_failures_are_not_reported_as_timeout():
    # TimeoutError 是 OSError 的子类，捕获顺序写反的话普通崩溃会被说成「超时」，
    # 用户拿到的建议就全错了
    service, failures = _service(0.05)
    service.graph = BrokenGraph()
    ctx = SimpleNamespace(run_id=uuid4(), conversation=SimpleNamespace(thread_id="thread-2"))

    events = [event async for event in service._stream({}, ctx, resume=False)]

    assert len(events) == 1
    assert events[0][1]["code"] == "GRAPH_EXECUTION_ERROR"
    assert failures and failures[0][1] == "GRAPH_EXECUTION_ERROR"
