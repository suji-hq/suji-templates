# Build-only unpacking stage. Package archives are pure JavaScript and have no dependencies.
FROM --platform=$BUILDPLATFORM docker.io/library/alpine:3.24.1@sha256:28bd5fe8b56d1bd048e5babf5b10710ebe0bae67db86916198a6eec434943f8b AS packages
ADD --checksum=sha256:29c4b8e0b2d86cb8795571c1959012ce057a14ecfd34858335f47c31e770a04f https://registry.npmjs.org/undici/-/undici-6.29.1.tgz /tmp/undici6.tgz
ADD --checksum=sha256:c98bd3881137c11341e8be8d2ec509ebf973b6f8b36d0a4c6d2afcda15e0d712 https://registry.npmjs.org/undici/-/undici-7.30.1.tgz /tmp/undici7.tgz
ADD --checksum=sha256:e03fa2ed347527c915026c04810d3b9bcf9893a2176b314aa4c29c945612d18c https://registry.npmjs.org/undici/-/undici-8.12.3.tgz /tmp/undici8.tgz
RUN mkdir /undici6 /undici7 /undici8 && tar -xzf /tmp/undici6.tgz --strip-components=1 -C /undici6 && tar -xzf /tmp/undici7.tgz --strip-components=1 -C /undici7 && tar -xzf /tmp/undici8.tgz --strip-components=1 -C /undici8

FROM docker.io/ghost:6.72.0@sha256:c0d83a8d45222b3f37a897572000050ab8e6e507d3eee5a35b3ef8345c7293d6
# Preserve the upstream root entrypoint, which initializes ownership and drops privileges.
RUN ["node", "-e", "const fs=require('fs'); if(process.version!=='v22.23.4')throw Error('unexpected Node'); for(const v of ['6.28.1','7.29.1','8.11.0']){const p='/var/lib/ghost/versions/6.72.0/node_modules/.pnpm/undici@'+v+'/node_modules/undici'; if(require(p+'/package.json').version!==v)throw Error('unexpected Undici');fs.rmSync(p,{recursive:true});}"]
COPY --from=packages --chown=node:node /undici6/ /var/lib/ghost/versions/6.72.0/node_modules/.pnpm/undici@6.28.1/node_modules/undici/
COPY --from=packages --chown=node:node /undici7/ /var/lib/ghost/versions/6.72.0/node_modules/.pnpm/undici@7.29.1/node_modules/undici/
COPY --from=packages --chown=node:node /undici8/ /var/lib/ghost/versions/6.72.0/node_modules/.pnpm/undici@8.11.0/node_modules/undici/
LABEL org.opencontainers.image.source="https://github.com/suji-hq/suji-templates" \
      org.opencontainers.image.version="6.72.0-suji.1" \
      org.opencontainers.image.description="Ghost 6.72.0 with Undici security updates; upstream Node 22.23.4 preserved"
