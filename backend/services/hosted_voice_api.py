"""Opt-in adapter from OSS profiles/generation to the hosted v1 contract.

Local VoiceStudio never calls this module unless the caller explicitly requests
``hosted`` execution *and* all VSS_HOSTED_* settings are present.  It stages
text/reference bytes as hosted Artifacts, creates a consent-backed Voice, and
uses durable Jobs; no local path, source recording URL, or plaintext text is
sent in a Job snapshot.
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

import httpx


class HostedVoiceError(RuntimeError):
    """A safe, user-actionable hosted adapter failure."""


@dataclass(frozen=True)
class HostedSettings:
    base_url: str
    token: str
    project_id: str
    model_id: str
    model_version: str
    base_voice_id: str
    consent_text_version: str

    @classmethod
    def from_environment(cls) -> "HostedSettings | None":
        values = {
            name: os.environ.get(name, "").strip()
            for name in (
                "VSS_HOSTED_API_BASE", "VSS_HOSTED_API_TOKEN",
                "VSS_HOSTED_PROJECT_ID", "VSS_HOSTED_MODEL_ID",
                "VSS_HOSTED_MODEL_VERSION", "VSS_HOSTED_BASE_VOICE_ID",
            )
        }
        if not any(values.values()):
            return None
        missing = [name for name, value in values.items() if not value]
        if missing:
            raise HostedVoiceError("Hosted execution is incomplete; configure " + ", ".join(missing) + ".")
        base_url = values["VSS_HOSTED_API_BASE"].rstrip("/")
        if not base_url.startswith(("http://", "https://")):
            raise HostedVoiceError("VSS_HOSTED_API_BASE must be an http(s) URL.")
        return cls(
            base_url=base_url, token=values["VSS_HOSTED_API_TOKEN"],
            project_id=values["VSS_HOSTED_PROJECT_ID"], model_id=values["VSS_HOSTED_MODEL_ID"],
            model_version=values["VSS_HOSTED_MODEL_VERSION"], base_voice_id=values["VSS_HOSTED_BASE_VOICE_ID"],
            consent_text_version=os.environ.get("VSS_HOSTED_CONSENT_TEXT_VERSION", "oss-spoken-consent-v1").strip() or "oss-spoken-consent-v1",
        )


class HostedVoiceClient:
    def __init__(self, settings: HostedSettings, client: httpx.AsyncClient | None = None):
        self.settings = settings
        self.client = client or httpx.AsyncClient(base_url=settings.base_url, timeout=60)
        self._owns_client = client is None

    async def aclose(self) -> None:
        if self._owns_client:
            await self.client.aclose()

    def _headers(self, *, idempotency: bool = False) -> dict[str, str]:
        headers = {"Authorization": f"Bearer {self.settings.token}"}
        if idempotency:
            headers["Idempotency-Key"] = str(uuid.uuid4())
        return headers

    async def _request(self, method: str, path: str, *, json: dict | None = None, headers: dict | None = None) -> httpx.Response:
        response = await self.client.request(method, path, json=json, headers=headers)
        if response.is_error:
            detail = "hosted service rejected the request"
            try:
                body = response.json()
                detail = body.get("error", {}).get("message") or body.get("detail") or detail
            except ValueError:
                pass
            raise HostedVoiceError(f"Hosted request failed ({response.status_code}): {detail}")
        return response

    async def upload_artifact(self, *, purpose: str, media_type: str, payload: bytes) -> str:
        digest = hashlib.sha256(payload).hexdigest()
        grant = (await self._request("POST", "/v1/artifacts/upload-authorizations", json={
            "project_id": self.settings.project_id, "purpose": purpose, "media_type": media_type,
            "size_bytes": len(payload), "sha256": digest,
        }, headers=self._headers())).json()
        put_headers = {k: v for k, v in (grant.get("required_headers") or {}).items() if k.lower() not in {"host", "content-length"}}
        put_headers.setdefault("Content-Type", media_type)
        response = await self.client.request(grant.get("method", "PUT"), grant["url"], content=payload, headers=put_headers)
        if response.is_error:
            raise HostedVoiceError(f"Hosted Artifact upload failed ({response.status_code}).")
        await self._request("POST", f"/v1/artifacts/{grant['artifact_id']}/complete", json={"size_bytes": len(payload), "sha256": digest}, headers=self._headers())
        return grant["artifact_id"]

    async def create_voice(self, *, name: str, description: str, reference_path: str) -> str:
        payload = Path(reference_path).read_bytes()
        if not payload:
            raise HostedVoiceError("The reference recording is empty.")
        suffix = Path(reference_path).suffix.lower()
        media_type = {".wav": "audio/wav", ".mp3": "audio/mpeg", ".flac": "audio/flac"}.get(suffix, "audio/wav")
        reference_id = await self.upload_artifact(purpose="reference_audio", media_type=media_type, payload=payload)
        voice = await self._request("POST", "/v1/voices", json={
            "project_id": self.settings.project_id, "display_name": name, "description": description[:1024],
            "reference_audio_artifact_id": reference_id,
            "consent": {"attestation_text_version": self.settings.consent_text_version},
        }, headers=self._headers(idempotency=True))
        return voice.json()["id"]

    async def synthesize(self, *, text: str, profile_voice_id: str, language: str | None = None) -> bytes:
        text_artifact = await self.upload_artifact(purpose="input", media_type="text/plain", payload=text.encode("utf-8"))
        configuration = {"voice_id": self.settings.base_voice_id, "voice_reference_id": profile_voice_id, "output_format": "wav"}
        if language and language != "Auto":
            configuration["language"] = language
        job = await self._request("POST", "/v1/jobs", json={
            "project_id": self.settings.project_id, "workflow": "tts",
            "model": {"id": self.settings.model_id, "version": self.settings.model_version},
            "input": {"text_artifact_id": text_artifact}, "configuration": configuration,
        }, headers=self._headers(idempotency=True))
        job_id = job.json()["job_id"]
        deadline = time.monotonic() + 15 * 60
        while time.monotonic() < deadline:
            view = (await self._request("GET", f"/v1/jobs/{job_id}", headers=self._headers())).json()
            if view.get("state") == "succeeded":
                outputs = view.get("output_artifact_ids") or []
                if not outputs:
                    raise HostedVoiceError("Hosted synthesis completed without audio output.")
                grant = (await self._request("POST", f"/v1/artifacts/{outputs[0]}/download-authorization", headers=self._headers())).json()
                audio = await self.client.request(grant.get("method", "GET"), grant["url"])
                if audio.is_error:
                    raise HostedVoiceError("Hosted synthesis output could not be downloaded.")
                return audio.content
            if view.get("state") in {"failed", "canceled"}:
                raise HostedVoiceError("Hosted synthesis did not complete successfully.")
            await asyncio.sleep(0.5)
        raise HostedVoiceError("Hosted synthesis timed out waiting for its durable Job.")
