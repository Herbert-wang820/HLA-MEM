from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient
from hla_orchestrator.app import create_app
from hla_orchestrator.application.errors import LLMUnavailableError, MemoryUnavailableError, PersonaUnavailableError
from hla_orchestrator.domain.models import Generation, MemoryHit, MemoryRetrieval
from hla_orchestrator.domain.persona import PersonaProfile, PersonaTrait
from hla_orchestrator.infrastructure.llm_config import LLMConfig, LLMConfigStore


class FakeMemory:
    def __init__(self, available: bool = True) -> None:
        self.available = available
        self.writes: list[dict] = []

    async def retrieve(self, query: str, top_k: int, *, request_id: str | None = None) -> MemoryRetrieval:
        if not self.available:
            raise MemoryUnavailableError("down")
        return MemoryRetrieval(
            retrieval_id="11111111-1111-4111-8111-111111111111",
            hits=(MemoryHit("22222222-2222-4222-8222-222222222222", 0.91, ("semantic",)),),
        )

    async def get_episode(self, episode_id: str) -> str | None:
        if not self.available:
            raise MemoryUnavailableError("down")
        return "我最近在喝龙井，喜欢清淡的茶。"

    async def write_episode(self, **kwargs) -> str:
        if not self.available:
            raise MemoryUnavailableError("down")
        self.writes.append(kwargs)
        return "33333333-3333-4333-8333-333333333333"


class FakePersona:
    def __init__(self, available: bool = True) -> None:
        self.available = available
        self.adaptation_version = 4
        self.adaptation_updates: list[dict] = []
        self.proposals: list[dict] = []
        self.fetches = 0

    async def fetch_profile(self) -> PersonaProfile:
        if not self.available:
            raise PersonaUnavailableError("down")
        self.fetches += 1
        return PersonaProfile(
            identity_version=2,
            adaptation_version=self.adaptation_version,
            narrative="你是一位耐心的对话伙伴。",
            traits=(PersonaTrait("tone", "温和", 0.8),),
            adaptation={"warmth": 0.6},
        )

    async def update_adaptation(self, *, expected_version, deltas, reason) -> int:
        if not self.available:
            raise PersonaUnavailableError("down")
        self.adaptation_updates.append(
            {"expectedVersion": expected_version, "deltas": deltas, "reason": reason}
        )
        self.adaptation_version += 1
        return self.adaptation_version

    async def create_identity_proposal(self, *, turn_id, rationale, changes, evidence_episode_ids) -> str:
        if not self.available:
            raise PersonaUnavailableError("down")
        self.proposals.append(
            {
                "turnId": turn_id,
                "rationale": rationale,
                "changes": changes,
                "evidenceEpisodeIds": list(evidence_episode_ids),
            }
        )
        return "44444444-4444-4444-8444-444444444444"

    async def close(self) -> None:
        return None


class FailingLLM:
    async def complete(self, *, message, memories, persona) -> Generation:
        raise LLMUnavailableError("model down")


class ScriptedLLM:
    def __init__(self, text: str) -> None:
        self.text = text
        self.personas: list[str] = []

    async def complete(self, *, message, memories, persona) -> Generation:
        self.personas.append(persona)
        return Generation(text=self.text)


def _client(
    memory: FakeMemory | None = None,
    store: LLMConfigStore | None = None,
    llm=None,
    persona: FakePersona | None = None,
) -> TestClient:
    app = create_app(
        memory_client=memory or FakeMemory(),
        config_store=store or LLMConfigStore(None, LLMConfig()),
        llm_completer=llm,
        persona_client=persona or FakePersona(),
    )
    return TestClient(app)


def _stream(client: TestClient, message: str = "我喜欢什么茶？", key: str = "turn-1") -> str:
    with client.stream(
        "POST",
        "/api/reasoning-orchestrator/v1/turns",
        headers={"Idempotency-Key": key},
        json={"sessionId": "s1", "message": message},
    ) as response:
        assert response.status_code == 200, response.read()
        assert response.headers["content-type"].startswith("text/event-stream")
        return "".join(response.iter_text())


def _done(text: str) -> dict:
    for block in text.split("\n\n"):
        if block.startswith("event: done"):
            data_line = next(line for line in block.splitlines() if line.startswith("data: "))
            return json.loads(data_line[6:])
    raise AssertionError(f"done event missing: {text!r}")


def test_health_readiness_and_metrics() -> None:
    client = _client()
    health = client.get("/internal/health")
    assert health.status_code == 200
    assert health.json()["module"] == "reasoning-orchestrator"

    ready = client.get("/internal/ready")
    assert ready.status_code == 200
    assert ready.json()["status"] == "ready"

    metrics = client.get("/internal/metrics")
    assert metrics.status_code == 200
    assert "module_ready" in metrics.text


def test_turn_streams_tokens_writes_memory_and_exposes_audit() -> None:
    memory = FakeMemory()
    persona = FakePersona()
    client = _client(memory=memory, persona=persona)
    text = _stream(client)
    done = _done(text)

    assert "event: token" in text
    assert "龙井" in text
    assert done["degraded"] is False
    assert done["usedEpisodeIds"] == ["22222222-2222-4222-8222-222222222222"]
    assert done["memories"][0]["excerpt"].startswith("我最近在喝龙井")
    assert [write["source"] for write in memory.writes] == ["conversation", "orchestrator"]
    assert done["persona"] == {
        "identityVersion": 2,
        "adaptationVersion": 4,
        "updated": False,
        "degraded": False,
        "identityProposalId": None,
    }

    turn = client.get(f"/api/reasoning-orchestrator/v1/turns/{done['turnId']}")
    assert turn.status_code == 200
    assert turn.json()["status"] == "completed"
    assert turn.json()["personaVersion"] == 2
    assert turn.json()["adaptationVersion"] == 4

    audit = client.get(f"/api/reasoning-orchestrator/v1/audits/{done['turnId']}")
    assert audit.status_code == 200
    body = audit.json()
    assert body["gateScore"] == 0.91
    assert body["candidatesConsidered"] == 1
    assert body["usedEpisodeIds"] == ["22222222-2222-4222-8222-222222222222"]


def test_model_persona_markers_update_adaptation_and_strip_from_visible_text() -> None:
    persona = FakePersona()
    llm = ScriptedLLM(
        '好的，我会更温暖。<persona_update>{"deltas":{"warmth":0.1},"reason":"用户偏好"}</persona_update>'
    )
    done = _done(_stream(_client(llm=llm, persona=persona)))

    assert "<persona_update>" not in json.dumps(done)
    assert persona.adaptation_updates == [
        {"expectedVersion": 4, "deltas": {"warmth": 0.1}, "reason": "用户偏好"}
    ]
    assert done["persona"]["updated"] is True
    assert done["persona"]["adaptationVersion"] == 5
    assert done["degraded"] is False
    assert "persona_update" not in _stream(_client(llm=llm, persona=FakePersona()))


def test_model_identity_marker_creates_proposal_not_version() -> None:
    persona = FakePersona()
    llm = ScriptedLLM(
        "我记下了。<persona_proposal>"
        '{"rationale":"用户希望更直接","changes":{"traits":[{"trait":"directness","value":"直接","confidence":0.9}],'
        '"narrative":"直接、务实"},"evidenceEpisodeIds":[]}'
        "</persona_proposal>"
    )
    text = _stream(_client(llm=llm, persona=persona))
    done = _done(text)

    assert "<persona_proposal>" not in text
    assert done["persona"]["identityProposalId"] == "44444444-4444-4444-8444-444444444444"
    assert done["persona"]["updated"] is True
    assert persona.proposals[0]["rationale"] == "用户希望更直接"
    assert persona.proposals[0]["changes"]["narrative"] == "直接、务实"


def test_persona_unavailable_is_explicit_and_never_breaks_the_turn() -> None:
    persona = FakePersona(available=False)
    text = _stream(_client(persona=persona))
    done = _done(text)
    assert done["degraded"] is True
    assert "PERSONA_UNAVAILABLE" in done["reasons"]
    assert done["persona"]["degraded"] is True
    assert "演示模式" in text


def test_invalid_persona_marker_is_stripped_and_degrades() -> None:
    persona = FakePersona()
    llm = ScriptedLLM(
        '回复。<persona_update>{"deltas":{"warmth":0.9}}</persona_update>'
        '<persona_proposal>{"rationale":"x","changes":{}}</persona_proposal>'
    )
    text = _stream(_client(llm=llm, persona=persona))
    done = _done(text)

    assert "persona_update" not in text
    assert "persona_proposal" not in text
    assert persona.adaptation_updates == []
    assert persona.proposals == []
    assert done["degraded"] is False


def test_turn_idempotency_replays_and_conflicts() -> None:
    client = _client()
    first = _done(_stream(client, key="same"))
    second = _done(_stream(client, key="same"))
    assert second["turnId"] == first["turnId"]

    response = client.post(
        "/api/reasoning-orchestrator/v1/turns",
        headers={"Idempotency-Key": "same"},
        json={"sessionId": "s1", "message": "different"},
    )
    assert response.status_code == 409
    assert response.json()["code"] == "REASONING_ORCHESTRATOR_IDEMPOTENCY_CONFLICT"


def test_memory_failure_degrades_but_still_answers() -> None:
    text = _stream(_client(memory=FakeMemory(available=False)))
    done = _done(text)
    assert done["degraded"] is True
    assert "MEMORY_UNAVAILABLE" in done["reasons"]
    assert "演示模式" in text


def test_llm_failure_falls_back_to_template_and_marks_degraded() -> None:
    text = _stream(_client(llm=FailingLLM()))
    done = _done(text)
    assert done["degraded"] is True
    assert "LLM_UNAVAILABLE" in done["reasons"]
    assert "演示模式" in text


def test_missing_idempotency_key_and_unknown_turn() -> None:
    client = _client()
    response = client.post(
        "/api/reasoning-orchestrator/v1/turns",
        json={"sessionId": "s1", "message": "hello"},
    )
    assert response.status_code == 422

    missing = client.get("/api/reasoning-orchestrator/v1/turns/does-not-exist")
    assert missing.status_code == 404
    assert missing.json()["code"] == "REASONING_ORCHESTRATOR_TURN_NOT_FOUND"


def test_tenant_in_body_is_rejected() -> None:
    response = _client().post(
        "/api/reasoning-orchestrator/v1/turns",
        headers={"Idempotency-Key": "tenant"},
        json={"sessionId": "s1", "message": "hello", "tenantId": "attacker"},
    )
    assert response.status_code == 422


def test_llm_config_saves_without_echoing_secret(tmp_path: Path) -> None:
    path = tmp_path / "llm.json"
    store = LLMConfigStore(path, LLMConfig())
    client = _client(store=store)

    initial = client.get("/internal/v1/llm/config")
    assert initial.status_code == 200
    assert initial.json()["apiKeySet"] is False

    enabled_without_key = client.put(
        "/internal/v1/llm/config",
        json={"enabled": True, "baseUrl": "http://127.0.0.1:9999/v1", "model": "demo"},
    )
    assert enabled_without_key.status_code == 422
    assert enabled_without_key.json()["code"] == "REASONING_ORCHESTRATOR_LLM_KEY_REQUIRED"

    saved = client.put(
        "/internal/v1/llm/config",
        json={
            "enabled": True,
            "baseUrl": "http://127.0.0.1:9999/v1",
            "model": "demo-model",
            "apiKey": "sk-test-secret",
            "temperature": 0.2,
            "maxTokens": 128,
        },
    )
    assert saved.status_code == 200
    assert saved.json()["apiKeySet"] is True
    assert "sk-test-secret" not in saved.text

    reloaded = LLMConfigStore(path, LLMConfig())
    assert reloaded._config.api_key == "sk-test-secret"  # noqa: SLF001 - persistence check
    assert reloaded._config.enabled is True  # noqa: SLF001
