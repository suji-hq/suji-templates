# n8n security image

This preserves the exact upstream n8n2.44.6 multiarchitecture image, including Node26.12.1, application code, native modules, user and entrypoint. Only two dependency directories change: Undici6.29.0→6.29.1 and7.29.1→7.30.1. The npm archives are checksum-pinned, contain no dependency requirements, and no install scripts run. The pnpm directory names remain unchanged so every existing symlink still resolves; package.json inside each directory records the corrected version.

References: [Undici6.29.1](https://github.com/nodejs/undici/releases/tag/v6.29.1), [Undici7.30.1](https://github.com/nodejs/undici/releases/tag/v7.30.1).

The workflow validates on PR/main without registry credentials. Publishing is a separate manual dispatch on main, after successful validation, using only GITHUB_TOKEN with packages:write. It builds both amd64 andarm64, refuses an existing release tag, and records the pushed manifest digest. No customer release notes are generated. The initial GHCR package must be made public and anonymous pull verified before the marketplace references it.

Local validation:

```sh
docker build -t marketplace-n8n:test images/n8n
docker run --rm --network none --read-only -i --entrypoint node marketplace-n8n:test < images/n8n/verify.cjs
python3 images/n8n/smoke.py marketplace-n8n:test
```

The smoke test uses only a disposable localhost-bound container and volume, with cleanup in finally. It creates a temporary owner and workflow, executes the workflow, verifies authentication and persistence, then removes the test data. It does not contact any paid integration.
