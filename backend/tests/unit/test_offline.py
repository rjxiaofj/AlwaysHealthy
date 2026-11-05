"""测试环境自身的守卫：用例不该联网、不该依赖模型输出。"""

from app.core.config import get_settings
from app.integrations.llm_client import get_llm


def test_model_key_is_blank_so_tests_never_call_the_api() -> None:
    # conftest 里清掉 LLM_API_KEY 就是为了这个。它一旦被改回来（或有人往 CI 里塞了密钥），
    # 整套测试会真的去打 DeepSeek：九分钟、要钱、结果随模型变，断网还直接红
    assert get_settings().llm_api_key == ""


async def test_unavailable_model_returns_none_instead_of_raising() -> None:
    # 所有调用方都靠这个约定回落到确定性文案，安全流程不能依赖模型是否活着
    llm = get_llm()

    assert llm.ready is False
    assert await llm.try_complete("你是健康助手", "我最近睡不好") is None
