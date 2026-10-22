FROM --platform=$BUILDPLATFORM docker.io/library/alpine:3.24.1@sha256:28bd5fe8b56d1bd048e5babf5b10710ebe0bae67db86916198a6eec434943f8b AS packages
ADD --checksum=sha256:29c4b8e0b2d86cb8795571c1959012ce057a14ecfd34858335f47c31e770a04f https://registry.npmjs.org/undici/-/undici-6.29.1.tgz /tmp/undici6.tgz
ADD --checksum=sha256:e03fa2ed347527c915026c04810d3b9bcf9893a2176b314aa4c29c945612d18c https://registry.npmjs.org/undici/-/undici-8.12.3.tgz /tmp/undici8.tgz
RUN mkdir /undici6 /undici8 && tar -xzf /tmp/undici6.tgz --strip-components=1 -C /undici6 && tar -xzf /tmp/undici8.tgz --strip-components=1 -C /undici8

FROM docker.io/library/node:24.22.1-bookworm-slim@sha256:55fb5f5a527ea2c5c4a95f963e48ef90aa38c7b346054fdc8ee9957a2b55d205 AS node
FROM ghcr.io/openclaw/openclaw:2026.10.5@sha256:f40d1e66fd14d8c5b49c832f4100f83b53fdc01f5108f7db11de38fd0ee6dbe5
USER root
# Exact upstream package layout guards; replacing pure-JS packages needs no install scripts.
RUN ["node", "-e", "const fs=require('fs');if(process.version!=='v24.21.0')throw Error('unexpected Node');for(const [p,v] of [['/app/node_modules/.pnpm/npm@12.2.0/node_modules/npm/node_modules/undici','6.28.0'],['/app/node_modules/.pnpm/undici@8.11.2/node_modules/undici','8.11.2'],['/usr/local/lib/node_modules/npm/node_modules/undici','8.12.2']]){if(require(p+'/package.json').version!==v)throw Error('unexpected Undici');fs.rmSync(p,{recursive:true});}"]
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=packages --chown=node:node /undici6/ /app/node_modules/.pnpm/npm@12.2.0/node_modules/npm/node_modules/undici/
COPY --from=packages --chown=node:node /undici8/ /app/node_modules/.pnpm/undici@8.11.2/node_modules/undici/
COPY --from=packages /undici8/ /usr/local/lib/node_modules/npm/node_modules/undici/
ENV NODE_VERSION=24.22.1
USER node
RUN ["node", "-e", "if(process.versions.modules!=='137')throw Error('unexpected ABI');const db=new(require('node:sqlite').DatabaseSync)(':memory:',{allowExtension:true});require('sqlite-vec').load(db);if(db.prepare('select vec_version() as version').get().version!=='v0.1.9')throw Error('native sqlite-vec mismatch');db.close()"]
LABEL org.opencontainers.image.source="https://github.com/suji-hq/suji-templates" \
      org.opencontainers.image.version="2026.10.5-suji.1" \
      org.opencontainers.image.description="OpenClaw 2026.10.5 with Node 24.22.1 and Undici security updates"
