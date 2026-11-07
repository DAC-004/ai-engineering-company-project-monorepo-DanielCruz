"""The intake JSON contract is enforced by the local decoder, not parser leniency."""
from types import SimpleNamespace
import pytest
from data.pipelines.rfp_intake import generation, agents


@pytest.mark.parametrize("json_output", [False, True])
def test_local_transport_enables_json_mode_only_when_requested(tmp_path, monkeypatch, json_output):
    model_file = tmp_path / "fictional.gguf"
    model_file.write_bytes(b"stand-in-model")
    seen = {}
    def complete(**kwargs):
        seen.update(kwargs)
        return {"choices": [{"message": {"content": '{"decision":"accept"}'}}]}
    monkeypatch.setattr(generation, "local_gguf_path", lambda: model_file)
    monkeypatch.setattr(generation, "_local_llm", SimpleNamespace(create_chat_completion=complete))
    assert generation.complete_local([{"role":"system","content":"JSON contract"}], json_output=json_output) == '{"decision":"accept"}'
    if json_output:
        assert seen["response_format"] == {"type":"json_object"}
    else:
        assert "response_format" not in seen


def test_intake_agents_request_json_without_changing_injected_callable_contract(monkeypatch):
    seen = {}
    def complete(messages, **kwargs):
        seen.update(kwargs)
        return "{}"
    monkeypatch.setattr(agents, "complete_local", complete)
    assert agents._complete([], None) == "{}"
    assert seen["json_output"] is True
    assert agents._complete([], lambda messages: "injected") == "injected"
