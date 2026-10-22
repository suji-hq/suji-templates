FROM --platform=$BUILDPLATFORM docker.io/library/alpine:3.24.1@sha256:28bd5fe8b56d1bd048e5babf5b10710ebe0bae67db86916198a6eec434943f8b AS packages
ADD --checksum=sha256:29c4b8e0b2d86cb8795571c1959012ce057a14ecfd34858335f47c31e770a04f https://registry.npmjs.org/undici/-/undici-6.29.1.tgz /tmp/undici6.tgz
ADD --checksum=sha256:c98bd3881137c11341e8be8d2ec509ebf973b6f8b36d0a4c6d2afcda15e0d712 https://registry.npmjs.org/undici/-/undici-7.30.1.tgz /tmp/undici7.tgz
ADD --checksum=sha256:e03fa2ed347527c915026c04810d3b9bcf9893a2176b314aa4c29c945612d18c https://registry.npmjs.org/undici/-/undici-8.12.3.tgz /tmp/undici8.tgz
RUN mkdir /undici6 /undici7 /undici8 && tar -xzf /tmp/undici6.tgz --strip-components=1 -C /undici6 && tar -xzf /tmp/undici7.tgz --strip-components=1 -C /undici7 && tar -xzf /tmp/undici8.tgz --strip-components=1 -C /undici8

FROM docker.io/library/node:24.22.1-alpine@sha256:06d7adf3e0ef61a13f1d28682726366f97a15aa1888c934d3ecec86c33918b53 AS node

FROM docker.io/nocodb/nocodb:2026.09.1@sha256:27d2fd14670db892ac721849d4f071edce47e386a1e74c921a0162644b9c213d
# Verify the exact vendor tree before replacing only Node and same-major packages.
RUN ["node", "-e", "const fs=require('fs');if(process.version!=='v24.14.0')throw Error('unexpected Node'); const e={\"/usr/src/app/node_modules/@ai-sdk/amazon-bedrock/node_modules/undici\": \"6.28.1\", \"/usr/src/app/node_modules/@ai-sdk/anthropic/node_modules/undici\": \"6.28.1\", \"/usr/src/app/node_modules/@ai-sdk/azure/node_modules/undici\": \"6.28.1\", \"/usr/src/app/node_modules/@ai-sdk/deepseek/node_modules/undici\": \"6.28.1\", \"/usr/src/app/node_modules/@ai-sdk/gateway/node_modules/undici\": \"6.28.1\", \"/usr/src/app/node_modules/@ai-sdk/google/node_modules/undici\": \"6.28.1\", \"/usr/src/app/node_modules/@ai-sdk/groq/node_modules/undici\": \"6.28.1\", \"/usr/src/app/node_modules/@ai-sdk/openai/node_modules/undici\": \"6.28.1\", \"/usr/src/app/node_modules/ai/node_modules/undici\": \"6.28.1\", \"/usr/src/app/node_modules/undici\": \"7.29.1\", \"/usr/src/app/node_modules/undici8\": \"8.10.2\"}; for(const [p,v] of Object.entries(e)){if(require(p+'/package.json').version!==v)throw Error('unexpected Undici '+p);fs.rmSync(p,{recursive:true});}"]
COPY --from=node /usr/local/bin/node /usr/local/bin/node
ENV NODE_VERSION=24.22.1
COPY --from=packages /undici6/ /usr/src/app/node_modules/@ai-sdk/amazon-bedrock/node_modules/undici/
COPY --from=packages /undici6/ /usr/src/app/node_modules/@ai-sdk/anthropic/node_modules/undici/
COPY --from=packages /undici6/ /usr/src/app/node_modules/@ai-sdk/azure/node_modules/undici/
COPY --from=packages /undici6/ /usr/src/app/node_modules/@ai-sdk/deepseek/node_modules/undici/
COPY --from=packages /undici6/ /usr/src/app/node_modules/@ai-sdk/gateway/node_modules/undici/
COPY --from=packages /undici6/ /usr/src/app/node_modules/@ai-sdk/google/node_modules/undici/
COPY --from=packages /undici6/ /usr/src/app/node_modules/@ai-sdk/groq/node_modules/undici/
COPY --from=packages /undici6/ /usr/src/app/node_modules/@ai-sdk/openai/node_modules/undici/
COPY --from=packages /undici6/ /usr/src/app/node_modules/ai/node_modules/undici/
COPY --from=packages /undici7/ /usr/src/app/node_modules/undici/
COPY --from=packages /undici8/ /usr/src/app/node_modules/undici8/
# Checked on every target architecture during the publication build.
RUN ["node", "-e", "if(process.version!=='v24.22.1'||process.versions.modules!=='137')throw Error('unexpected runtime ABI');require('sqlite3');require('sharp');"]
LABEL org.opencontainers.image.source="https://github.com/suji-hq/suji-templates" \
      org.opencontainers.image.version="2026.09.1-suji.1" \
      org.opencontainers.image.description="NocoDB 2026.09.1 with Node 24.22.1 and same-major Undici security updates"
