# Build-only unpacking stage. Package archives are pure JavaScript and have no dependencies.
FROM --platform=$BUILDPLATFORM docker.io/library/alpine:3.24.1@sha256:28bd5fe8b56d1bd048e5babf5b10710ebe0bae67db86916198a6eec434943f8b AS packages
ADD --checksum=sha256:29c4b8e0b2d86cb8795571c1959012ce057a14ecfd34858335f47c31e770a04f https://registry.npmjs.org/undici/-/undici-6.29.1.tgz /tmp/undici6.tgz
ADD --checksum=sha256:c98bd3881137c11341e8be8d2ec509ebf973b6f8b36d0a4c6d2afcda15e0d712 https://registry.npmjs.org/undici/-/undici-7.30.1.tgz /tmp/undici7.tgz
RUN mkdir /undici6 /undici7 && tar -xzf /tmp/undici6.tgz --strip-components=1 -C /undici6 && tar -xzf /tmp/undici7.tgz --strip-components=1 -C /undici7

FROM docker.io/n8nio/n8n:2.44.6@sha256:d02752c6ab446ae9db8deec2f9cc887c378f77cdcad31650814df936b7386dfb
USER root
# Abort on unexpected vendor layout/version; remove all old files before copying.
RUN ["node", "-e", "const fs=require('fs'); if(process.version!=='v26.12.1')throw Error('unexpected Node'); for(const v of ['6.29.0','7.29.1']){const p='/usr/local/lib/node_modules/n8n/node_modules/.pnpm/undici@'+v+'/node_modules/undici'; if(require(p+'/package.json').version!==v)throw Error('unexpected Undici');fs.rmSync(p,{recursive:true});}"]
COPY --from=packages --chown=node:node /undici6/ /usr/local/lib/node_modules/n8n/node_modules/.pnpm/undici@6.29.0/node_modules/undici/
COPY --from=packages --chown=node:node /undici7/ /usr/local/lib/node_modules/n8n/node_modules/.pnpm/undici@7.29.1/node_modules/undici/
USER node
LABEL org.opencontainers.image.source="https://github.com/suji-hq/suji-templates" \
      org.opencontainers.image.version="2.44.6-suji.1" \
      org.opencontainers.image.description="n8n 2.44.6 with Undici security updates 6.29.1 and 7.30.1; upstream Node 26.12.1 preserved"
