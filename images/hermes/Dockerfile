FROM --platform=$BUILDPLATFORM docker.io/library/alpine:3.24.1@sha256:28bd5fe8b56d1bd048e5babf5b10710ebe0bae67db86916198a6eec434943f8b AS packages
ADD --checksum=sha256:6170b2d474e1c626f43cff3adc118df9fe3b573258a4fc3d850c8dbc6b079bbd https://nodejs.org/dist/v26.12.1/node-v26.12.1-linux-x64.tar.xz /node.tar.xz
ADD --checksum=sha256:29c4b8e0b2d86cb8795571c1959012ce057a14ecfd34858335f47c31e770a04f https://registry.npmjs.org/undici/-/undici-6.29.1.tgz /undici6.tgz
ADD --checksum=sha256:c98bd3881137c11341e8be8d2ec509ebf973b6f8b36d0a4c6d2afcda15e0d712 https://registry.npmjs.org/undici/-/undici-7.30.1.tgz /undici7.tgz
RUN mkdir /node && tar -xJf /node.tar.xz --strip-components=1 -C /node

FROM docker.io/nousresearch/hermes-agent:v0.22.4@sha256:7a69201726bc64db2072a1371557137c23312d29705cda2b8ea2a0214a50a4cf
ARG TARGETARCH
RUN test "$TARGETARCH" = amd64
COPY --from=packages /node/ /opt/hermes/tools/node-26.12.1-linux-x64/
COPY --from=packages --chmod=0644 /undici6.tgz /undici7.tgz /opt/hermes/pm/suji-security/
COPY --chmod=0644 pm_security.py /opt/hermes/pm/suji_security.py
COPY --chmod=0644 prepare.py /tmp/suji-hermes-prepare.py
RUN chmod 0755 /opt/hermes/pm/suji-security && /opt/hermes/.venv/bin/python /tmp/suji-hermes-prepare.py && rm /tmp/suji-hermes-prepare.py
LABEL org.opencontainers.image.source="https://github.com/suji-hq/suji-templates" \
      org.opencontainers.image.version="0.22.4-suji.1" \
      org.opencontainers.image.description="Hermes 0.22.4 with Node 26.12.1 and repair-safe Undici updates (amd64)"
