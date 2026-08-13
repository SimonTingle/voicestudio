# Hosted Voice integration

VoiceStudio remains local-first. `/profiles` and `/generate` keep their local
SQLite and on-device synthesis behaviour unless a caller explicitly asks for a
hosted operation. No profile or generation is uploaded merely because hosted
configuration exists.

To enable the optional adapter, configure the backend environment:

```text
VSS_HOSTED_API_BASE=http://127.0.0.1:8080
VSS_HOSTED_API_TOKEN=<scoped API credential>
VSS_HOSTED_PROJECT_ID=<hosted project id>
VSS_HOSTED_MODEL_ID=<approved TTS model id>
VSS_HOSTED_MODEL_VERSION=<approved model version>
VSS_HOSTED_BASE_VOICE_ID=<model-approved base voice>
VSS_HOSTED_CONSENT_TEXT_VERSION=oss-spoken-consent-v1
```

First record ownership consent in the local profile UI, then explicitly call
`POST /profiles/{profile_id}/hosted-sync`. The adapter uploads the reference
recording through hosted Artifact grants and creates a consent-backed
`/v1/voices` record; it never sends a local path or a consent recording. The
returned hosted ID is stored only as local synchronization metadata.

Call `POST /generate` with `hosted=true` and that synchronized `profile_id` to
use the hosted durable `/v1/jobs` path. The adapter stages text as an Artifact,
polls the durable Job, and downloads the result only through a temporary grant.
Without `hosted=true`, `/generate` stays entirely on-device.
