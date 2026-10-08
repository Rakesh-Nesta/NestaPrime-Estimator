#!/usr/bin/env bash
set -euo pipefail
sha=$1
[[ $sha =~ ^[0-9a-f]{40}$ ]]
mkdir -p release
image="nestaprime-release:$sha-$GITHUB_RUN_ID-$GITHUB_RUN_ATTEMPT"
docker build --platform linux/amd64 --label "org.opencontainers.image.revision=$sha" -t "$image" source > build-backend.log 2>&1
id=$(docker image inspect --format '{{.Id}}' "$image")
printf '%s\n' "$image" > release/image-tag
printf '%s\n' "$id" > release/image-id
printf '%s\n' "$sha" > release/commit
# Inventory is taken FROM THE IMAGE; audit tools never alter the release image.
docker run --rm --entrypoint python "$id" -m pip list --format=freeze > release/backend-packages.txt
python -m pip install 'pip-audit==2.9.0' > audit-install.log 2>&1
# Audit the complete installed inventory without the retired ecdsa exception.
pip-audit --no-deps --disable-pip -r release/backend-packages.txt -f json -o release/backend-audit.json > release/backend-audit.log 2>&1
docker save "$image" | gzip > release/backend.tar.gz
docker build --platform linux/amd64 -f source/frontend/Dockerfile --target export --build-arg VITE_API_URL=/api --output type=local,dest=frontend-export source/frontend > build-frontend.log 2>&1
test -s frontend-export/dist/index.html
printf '%s\n' "$sha" > frontend-export/dist/release.txt
tar -C frontend-export/dist -czf release/frontend.tar.gz .
python deploy/automation/package_release.py
