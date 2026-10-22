# OpenClaw security image

The base is official OpenClaw `2026.10.5`, pinned by OCI digest. Only Node
24.21.0 → 24.22.1 and three pure-JavaScript Undici packages change:

- application Undici 8.11.2 → 8.12.3;
- application's embedded npm Undici 6.28.0 → 6.29.1;
- global npm Undici 8.12.2 → 8.12.3.

The Node donor uses the same Debian/glibc family and Node major/ABI. The recipe
checks every original version before replacing bytes and pins all inputs by
digest or SHA256. Application code, entrypoint, user, and state paths remain
from the exact upstream image. pnpm store directory names retain their original
version spelling; `package.json` and actual loaded code carry the patched version.

The catalogue init service needs **512 MiB**, since the new CLI is OOM-killed at
256 MiB. `set -e` makes failed config writes fail the init service instead of
starting a gateway with incomplete configuration. The gateway stays at 2 GiB and
1 CPU; init stays at 0.5 CPU. Existing provider configuration, gateway token,
origin checks and device pairing are retained. Seed checks read the JSON5 file
without acquiring the running gateway's lock (separate PID namespaces). They use
exact model equality and write only when necessary through the unchanged upstream
CLI. Invalid JSON5 and external `$include` configuration fail closed; configuration
with includes must first be resolved inside the gateway. No gateway lock is removed
or bypassed for writes, and an identical re-deploy leaves configuration unchanged.

## Reproduce

Build from this directory on native amd64, then verify the runtime:

```sh
docker build --platform linux/amd64 -t suji-marketplace-openclaw:2026.10.5-suji.1 .
docker run --rm --network none --entrypoint node \
  -v "$PWD/verify.cjs:/tmp/verify.cjs:ro" \
  suji-marketplace-openclaw:2026.10.5-suji.1 /tmp/verify.cjs
python3 smoke.py
```

`smoke.py` requires PyYAML and Docker Compose, and reads the tracked
`compose.test.yaml` candidate fixture. It uses a disposable internal
Docker network, volume and random test credential, publishes no host port, and
supplies no provider key or channel token. It tests UI/readiness, gateway token
authentication, repeat-init persistence and failing/invalid-init behavior. Cleanup removes
only its own disposable resources and verifies that containers, networks and
volumes are absent. The build checks ABI137 and the actual sqlite-vec extension
on every target architecture, and runtime verification enumerates all Undici copies. `MARKETPLACE_SMOKE_IMAGE` can select the CI
candidate without changing the catalogue.

No paid model request, external channel send, or customer data is used. Channel
connectivity and model responses require separate credentials and are not claimed.
