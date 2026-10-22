# Ghost security image

Pinned Ghost6.72.0 upstream image, with its Node22.23.4 preserved. Only the three installed Undici package trees are replaced with official npm archives verified against registry SHA512 integrity and fixed SHA256 checksums. Directory names and symlinks stay unchanged, package metadata reports6.29.1/7.30.1/8.12.3. No install scripts. Upstream entrypoint and privilege dropping preserved.

CI verifies real runtime/package versions, local HTTP fetches through each package, owner setup and authentication, a published post, restart persistence, and cleanup of the disposable container/volume. Publication is manual from reviewed main only; validate must pass, no existing release tag may be overwritten. The resulting GHCR package must be publicly pullable before a catalog manifest references its digest.
