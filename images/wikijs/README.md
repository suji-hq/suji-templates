# Wiki.js security image

Preserve the latest stable Wiki.js 2.x release, 2.5.316, its exact Alpine image layers and configuration. The official stable series moved to https://github.com/requarks/wiki-v2; the 3.0 beta from the old repository is not used. Replace only Node 24.21.0 with the official architecture-matched 24.22.1 binary and both Undici copies (application and bundled npm) with fixed version 6.29.1. All sources are pinned by digest, and package extraction executes no installation scripts. Node ABI remains 137; the build checks native SQLite on each target architecture.

Verification recursively enumerates actual package metadata and exercises both HTTP clients plus SQLite. The isolated smoke performs initial setup, owner login, rejected credentials, denied anonymous writes, page publishing/public reading, persistence across restart and deletion. Container, named volume and any image-declared anonymous volumes are removed even on failure. No external database is configured by the smoke.

Publication requires an explicit main-branch workflow dispatch after validation. Pull requests receive no package write credentials. Existing tags are refused; the catalogue changes separately after anonymous pull verification. Future upstream updates require refreshing this recipe and repeating its checks.

```sh
docker build -t marketplace-wikijs:test images/wikijs
docker run --rm --network none --read-only -i --entrypoint node marketplace-wikijs:test < images/wikijs/verify.cjs
python3 images/wikijs/smoke.py marketplace-wikijs:test
```
