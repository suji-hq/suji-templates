FROM --platform=$BUILDPLATFORM docker.io/library/alpine:3.24.1@sha256:28bd5fe8b56d1bd048e5babf5b10710ebe0bae67db86916198a6eec434943f8b AS packages
ADD --checksum=sha256:29c4b8e0b2d86cb8795571c1959012ce057a14ecfd34858335f47c31e770a04f https://registry.npmjs.org/undici/-/undici-6.29.1.tgz /tmp/undici6.tgz
RUN mkdir /undici6 && tar -xzf /tmp/undici6.tgz --strip-components=1 -C /undici6

FROM docker.io/library/node:24.22.1-alpine@sha256:06d7adf3e0ef61a13f1d28682726366f97a15aa1888c934d3ecec86c33918b53 AS node

FROM docker.io/requarks/wiki:2.5.316@sha256:fffff288a52f76e5b8c19a4fbcd0f3e538e96edea642c4f2d813d54d59a876de
USER root
RUN ["node", "-e", "const fs=require('fs');if(process.version!=='v24.21.0')throw Error('unexpected Node');for(const [p,v] of Object.entries({'/wiki/node_modules/undici':'6.29.0','/usr/local/lib/node_modules/npm/node_modules/undici':'6.27.0'})){if(require(p+'/package.json').version!==v)throw Error('unexpected Undici');fs.rmSync(p,{recursive:true});}"]
COPY --from=node /usr/local/bin/node /usr/local/bin/node
ENV NODE_VERSION=24.22.1
COPY --from=packages --chown=node:node /undici6/ /wiki/node_modules/undici/
COPY --from=packages /undici6/ /usr/local/lib/node_modules/npm/node_modules/undici/
USER node
RUN ["node", "-e", "if(process.version!=='v24.22.1'||process.versions.modules!=='137')throw Error('unexpected runtime ABI');require('sqlite3');"]
LABEL org.opencontainers.image.source="https://github.com/suji-hq/suji-templates" \
      org.opencontainers.image.version="2.5.316-suji.1" \
      org.opencontainers.image.description="Wiki.js 2.5.316 with Node 24.22.1 and Undici 6.29.1 security updates"
