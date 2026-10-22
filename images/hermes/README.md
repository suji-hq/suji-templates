# Hermes security image (linux/amd64)

The base is official `nousresearch/hermes-agent:v0.22.4`, pinned by OCI digest.
The upstream project switched from calendar tags to semantic releases; the older
Docker Hub calendar `latest` must not be used to select a release.

The overlay preserves application code, the s6 entrypoint, gateway command,
`/opt/data` persistence, authentication and dashboard environment variables. s6
starts as root for ownership setup, while application processes run as UID10000.
Only the bundled tool runtime is changed:

- Node26.7.0 → official Node26.12.1 (same major);
- npm's two copies of Undici6.27.0/6.28.0 →6.29.1;
- Photon sidecar Undici7.30.0 →7.30.1.

## Repair-safe tool management

Hermes PM owns Node/npm pins and installed facts. `prepare.py` checks the exact
upstream SHA256 of `pm/packages.py`, `pm/lock.json` and `tools/facts.json`, then
updates the amd64 Node pin, installed version, artifact hash, path and tree digest
together. The old Node store entry is removed. Other tool facts and npm's own
version12.0.2 stay unchanged. This image intentionally supports only amd64;
unsupported architectures fail during build and have no alternative download.

Two narrow `stage()` hooks call `pm_security.py` before PM atomically publishes
Node/npm, including after a repair. The helper accepts only the expected npm
layout and versions, verifies the bundled Undici tarball SHA256, disallows archive
links and path escapes, and fails closed. The archive is immutable and readable
by the final user. No runtime network fallback or floating dependency is added.
The Node/npm repair continues to use PM's original verified downloader and pinned
upstream URLs. Photon lives in the immutable application tree.

## Validation

```sh
docker build --platform linux/amd64 -t marketplace-hermes:test .
docker run --rm --network none --user 10000:10000 -i \
  --entrypoint /opt/hermes/.venv/bin/python marketplace-hermes:test < verify.py
docker run --rm --memory 1536m --cpus 1 \
  --tmpfs /tmp/repair-home:rw,exec,size=768m \
  -e HERMES_HOME=/tmp/repair-home -i \
  --entrypoint /opt/hermes/.venv/bin/python marketplace-hermes:test < repair-test.py
MARKETPLACE_SMOKE_IMAGE=marketplace-hermes:test python3 smoke.py
```

The repair test removes tool trees only inside its disposable container and
re-downloads the two pinned archives. It verifies both real PM stage hooks,
patched packages, tree digests and UID10000. Negative cases reject corrupted
archives, unexpected versions and symlink escapes without changing the target.

The tracked `compose.test.yaml` retains the catalogue's4GiB/2CPU service contract.
The smoke uses a disposable internal network/volume, publishes no port, provides
no model key, and tests dashboard/login, rejected credentials, authenticated
session, persistence and session survival across restart. Cleanup checks confirm
no test containers, volumes or networks remain. No LLM request or channel send is
performed; paid inference and external channel connectivity are not claimed.

CI validates every image change. Publication is an explicit main-branch dispatch
with write permission only in the publication job; existing tags are rejected.
The catalogue image pin is changed separately after a public digest exists.
