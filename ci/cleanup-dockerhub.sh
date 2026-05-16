#!/bin/sh
# CLEANUP_MODE=sha → delete old SHA tags, keep newest 5
set -e

: "${DOCKER_USERNAME:?}"
: "${DOCKER_PASSWORD:?}"
: "${REPO_PATH:?}"

TOKEN=$(curl -sf -X POST "https://hub.docker.com/v2/users/login" \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"$DOCKER_USERNAME\",\"password\":\"$DOCKER_PASSWORD\"}" \
  | jq -r .token)

delete_tag() {
  TAG=$1
  echo "Deleting tag: $TAG"
  curl -sf -X DELETE \
    "https://hub.docker.com/v2/repositories/${REPO_PATH}/tags/${TAG}/" \
    -H "Authorization: JWT $TOKEN"
}

TAGS=$(curl -sf \
  "https://hub.docker.com/v2/repositories/${REPO_PATH}/tags/?page_size=100" \
  -H "Authorization: JWT $TOKEN" \
  | jq -r '[.results[] | select(.name | test("^[0-9a-f]{40}$")) | .name] | .[5:] | .[]')

if [ -z "$TAGS" ]; then
  echo "No old SHA tags to clean up."
  exit 0
fi

echo "$TAGS" | while IFS= read -r tag; do
  delete_tag "$tag"
done

echo "Cleanup done."
