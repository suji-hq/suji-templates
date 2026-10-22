# NocoDB security image

This image preserves NocoDB 2026.09.1 and its exact upstream Alpine base, entrypoint, data paths and configuration. It replaces only the Node binary with official Node 24.22.1 for the target architecture and the eleven installed Undici packages with their fixed same-major releases. Native Node ABI remains 137. Package archive hashes are pinned; no npm lifecycle script is executed. The build refuses an unexpected upstream runtime or package layout.

`packages.json` records each original and replacement version. `verify.cjs` recursively checks installed package metadata, including the aliased `undici8`, exercises HTTP fetch from every copy, and verifies native SQLite and Sharp operations. `smoke.py` checks initial signup, authentication, rejected credentials, base/table creation, record CRUD and persistence after restart using a disposable localhost-only container and volume. Cleanup runs even on failure. No external AI provider is configured.

The vendor image contains an optional lz4 native addon that already fails to load with an exec-format error on amd64. This packaging change preserves that pre-existing behavior; it does not claim to repair or validate every optional external database/AI integration. SQLite, image processing and the tested application flows pass with the original ABI.

The publication workflow validates pull requests without write credentials. Only an explicit dispatch of the reviewed main branch can publish, after the same tests pass; it refuses an existing release tag. The catalogue is updated separately after anonymous image pull verification. Future upstream upgrades require updating this pinned recipe and repeating these checks.

```sh
docker build -t marketplace-nocodb:test images/nocodb
docker run --rm --network none --read-only -i --entrypoint node marketplace-nocodb:test < images/nocodb/verify.cjs
python3 images/nocodb/smoke.py marketplace-nocodb:test
```
