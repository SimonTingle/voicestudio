import asyncio

import httpx
import pytest

from services.hosted_voice_api import HostedSettings, HostedVoiceClient, HostedVoiceError


_NAMES = (
    "VSS_HOSTED_API_BASE", "VSS_HOSTED_API_TOKEN", "VSS_HOSTED_PROJECT_ID",
    "VSS_HOSTED_MODEL_ID", "VSS_HOSTED_MODEL_VERSION", "VSS_HOSTED_BASE_VOICE_ID",
)


def test_hosted_adapter_is_disabled_without_configuration(monkeypatch):
    for name in _NAMES:
        monkeypatch.delenv(name, raising=False)
    assert HostedSettings.from_environment() is None


def test_hosted_adapter_refuses_partial_configuration(monkeypatch):
    for name in _NAMES:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("VSS_HOSTED_API_BASE", "http://127.0.0.1:8080")
    with pytest.raises(HostedVoiceError, match="VSS_HOSTED_API_TOKEN"):
        HostedSettings.from_environment()


def test_hosted_adapter_requires_http_endpoint(monkeypatch):
    values = {
        "VSS_HOSTED_API_BASE": "not-a-url",
        "VSS_HOSTED_API_TOKEN": "token",
        "VSS_HOSTED_PROJECT_ID": "project",
        "VSS_HOSTED_MODEL_ID": "model",
        "VSS_HOSTED_MODEL_VERSION": "v1",
        "VSS_HOSTED_BASE_VOICE_ID": "base",
    }
    for name, value in values.items():
        monkeypatch.setenv(name, value)
    with pytest.raises(HostedVoiceError, match="http"):
        HostedSettings.from_environment()


def test_create_voice_uses_artifact_grants_then_canonical_voice_resource(tmp_path):
    reference = tmp_path / "reference.wav"
    reference.write_bytes(b"reference-audio")
    settings = HostedSettings("https://api.test", "token", "project", "model", "v1", "base", "oss-spoken-consent-v1")
    requests = []

    def handler(request):
        requests.append(request)
        if request.url.path == "/v1/artifacts/upload-authorizations":
            return httpx.Response(200, json={"artifact_id": "artifact-ref", "method": "PUT", "url": "https://objects.test/ref", "required_headers": {}})
        if request.url.host == "objects.test":
            return httpx.Response(200)
        if request.url.path == "/v1/artifacts/artifact-ref/complete":
            return httpx.Response(200, json={})
        if request.url.path == "/v1/voices":
            return httpx.Response(201, json={"id": "hosted-voice"})
        return httpx.Response(404)

    async def create():
        client = HostedVoiceClient(settings, httpx.AsyncClient(base_url=settings.base_url, transport=httpx.MockTransport(handler)))
        return await client.create_voice(name="Local profile", description="description", reference_path=str(reference))

    assert asyncio.run(create()) == "hosted-voice"
    voice_request = next(request for request in requests if request.url.path == "/v1/voices")
    body = __import__("json").loads(voice_request.content)
    assert body["project_id"] == "project"
    assert body["reference_audio_artifact_id"] == "artifact-ref"
    assert body["consent"]["attestation_text_version"] == "oss-spoken-consent-v1"
