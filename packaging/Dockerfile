# Build environment for packaging/build.sh.
# The same image builds amd64 and arm64 packages; run it on a host of the target architecture.
FROM ubuntu:noble

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates binutils dpkg \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.11.32 /uv /usr/local/bin/uv
COPY --from=ghcr.io/goreleaser/nfpm:v2.43.0 /usr/bin/nfpm /usr/local/bin/nfpm

WORKDIR /infrahouse-toolkit
ENTRYPOINT ["/infrahouse-toolkit/packaging/build.sh"]
