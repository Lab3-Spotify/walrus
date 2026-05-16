// output to .drone.yml (which drone really reads)
// jsonnet .drone.jsonnet | jq . | yq -P - > .drone.yml


local VALUES = {
  PROJECT_NAME:             "walrus",
  DOCKERHUB_IMAGE:          "lislab3morris/walrus",
  K8S_DEPLOYMENT_NAME:      "walrus",
  K8S_DEPLOYMENT_NAMESPACE: "walrus",
  BRANCH:                   "master",
};

local CELERY_DEPLOYMENTS = [
  "%s-celery-playlog" % VALUES.K8S_DEPLOYMENT_NAME,
  "%s-celery-beat"    % VALUES.K8S_DEPLOYMENT_NAME,
];

local ALL_DEPLOYMENTS = [VALUES.K8S_DEPLOYMENT_NAME] + CELERY_DEPLOYMENTS;

local SECRET = {
  DOCKER_USERNAME: { from_secret: "docker-username" },
  DOCKER_PASSWORD: { from_secret: "docker-password" },
};

local secret_docker_user = { kind: "secret", name: "docker-username", get: { path: "docker-username", name: "value" } };
local secret_docker_pass = { kind: "secret", name: "docker-password", get: { path: "docker-password", name: "value" } };

local node = { repo: "Lab3-Spotify-walrus" };

local trigger = {
  event:  ["push"],
  branch: [VALUES.BRANCH],
};

// ── migration check ───────────────────────────────────────
local migrationCheckPipeline = {
  kind: "pipeline",
  type: "kubernetes",
  name: "walrus-migration-check",
  node: node,
  trigger: { event: ["pull_request"] },
  steps: [
    {
      name:  "migration-dry-run",
      image: "python:3.10.13-slim",
      environment: { DJANGO_SECRET_KEY: "MIGRATION_CHECK_PIPELINE_SUPER_SECRET" },
      commands: [
        "pip install poetry==1.6.1 poetry-plugin-export",
        "poetry export -f requirements.txt --without-hashes -o requirements.txt",
        "pip install -r requirements.txt || exit 1",
        "python manage.py check || exit 1",
        "python manage.py makemigrations --dry-run --check",
      ],
    },
  ],
};

// ── test ──────────────────────────────────────────────────
local testPipeline = {
  kind: "pipeline",
  type: "kubernetes",
  name: "walrus-test",
  node: node,
  trigger: trigger,
  services: [
    {
      name:  "walrus-test-db",
      image: "postgres:14-alpine",
      environment: {
        POSTGRES_USER:     "walrus-test",
        POSTGRES_PASSWORD: "walrus-test",
        POSTGRES_DB:       "walrus-test",
      },
    },
    { name: "walrus-test-redis", image: "redis:7.4.2" },
  ],
  steps: [
    {
      name:  "install-and-test",
      image: "python:3.10.13-slim",
      environment: {
        ENV:               "test",
        DJANGO_SECRET_KEY: "TEST_PIPELINE_SUPER_SECRET",
        POSTGRES_HOST:     "walrus-test-db",
        POSTGRES_USER:     "walrus-test",
        POSTGRES_PASSWORD: "walrus-test",
        POSTGRES_DB:       "walrus-test",
        POSTGRES_PORT:     "5432",
        REDIS_HOST:        "walrus-test-redis",
        REDIS_PORT:        "6379",
      },
      commands: [
        "pip install poetry==1.6.1 poetry-plugin-export",
        "poetry export -f requirements.txt --without-hashes -o requirements.txt",
        "pip install -r requirements.txt || exit 1",
        "python manage.py test || exit 1",
      ],
    },
  ],
};

// ── build ─────────────────────────────────────────────────
local buildPipeline = {
  kind: "pipeline",
  type: "kubernetes",
  name: "walrus-build",
  node: node,
  depends_on: ["walrus-test"],
  trigger: trigger,
  steps: [
    {
      name:  "build",
      image: "plugins/docker",
      settings: {
        repo:       VALUES.DOCKERHUB_IMAGE,
        tags:       ["test-${DRONE_COMMIT_SHA}"],
        username:   SECRET.DOCKER_USERNAME,
        password:   SECRET.DOCKER_PASSWORD,
        cache_from: [VALUES.DOCKERHUB_IMAGE + ":latest"],
        buildkit:   true,
        build_args: ["BUILDKIT_INLINE_CACHE=1"],
      },
    },
  ],
};

// ── publish ───────────────────────────────────────────────
local publishPipeline = {
  kind: "pipeline",
  type: "kubernetes",
  name: "walrus-publish",
  node: node,
  depends_on: ["walrus-build"],
  trigger: trigger,
  steps: [
    {
      name:  "promote",
      image: "regclient/regctl:edge-alpine",
      environment: {
        DOCKER_USERNAME: SECRET.DOCKER_USERNAME,
        DOCKER_PASSWORD: SECRET.DOCKER_PASSWORD,
      },
      commands: [
        "regctl registry login registry-1.docker.io -u $DOCKER_USERNAME -p $DOCKER_PASSWORD",
        "regctl image copy %(img)s:test-${DRONE_COMMIT_SHA} %(img)s:${DRONE_COMMIT_SHA}" % { img: VALUES.DOCKERHUB_IMAGE },
        "regctl image copy %(img)s:test-${DRONE_COMMIT_SHA} %(img)s:latest"              % { img: VALUES.DOCKERHUB_IMAGE },
        "regctl tag delete %s:test-${DRONE_COMMIT_SHA}"                                  % VALUES.DOCKERHUB_IMAGE,
      ],
    },
  ],
};

// ── deploy ────────────────────────────────────────────────
local deployPipeline = {
  kind: "pipeline",
  type: "kubernetes",
  name: "walrus-deploy",
  node: node,
  depends_on: ["walrus-publish"],
  trigger: trigger,
  steps: [
    {
      name:  "deploy",
      image: "bitnami/kubectl",
      commands: std.map(
        function(name) "kubectl rollout restart deployment/%s -n %s" % [name, VALUES.K8S_DEPLOYMENT_NAMESPACE],
        ALL_DEPLOYMENTS
      ),
    },
    {
      name:  "verify",
      image: "bitnami/kubectl",
      commands: std.map(
        function(name) "kubectl rollout status deployment/%s -n %s --timeout=120s || exit 1" % [name, VALUES.K8S_DEPLOYMENT_NAMESPACE],
        ALL_DEPLOYMENTS
      ),
    },
    {
      name:  "cleanup-old-tags",
      image: "alpine:3",
      environment: {
        DOCKER_USERNAME: SECRET.DOCKER_USERNAME,
        DOCKER_PASSWORD: SECRET.DOCKER_PASSWORD,
      },
      commands: [
        "apk add --no-cache curl jq",
        |||
          TOKEN=$(curl -s -X POST "https://hub.docker.com/v2/users/login" \
            -H "Content-Type: application/json" \
            -d "{\"username\":\"$DOCKER_USERNAME\",\"password\":\"$DOCKER_PASSWORD\"}" \
            | jq -r .token)
          curl -s "https://hub.docker.com/v2/repositories/%(img)s/tags/?page_size=100" \
            -H "Authorization: JWT $TOKEN" \
            | jq -r '[.results[] | select(.name | test("^[0-9a-f]{40}$")) | .name] | .[5:] | .[]' \
            | xargs -r -I{} curl -s -X DELETE \
              "https://hub.docker.com/v2/repositories/%(img)s/tags/{}/" \
              -H "Authorization: JWT $TOKEN"
        ||| % { img: VALUES.DOCKERHUB_IMAGE },
      ],
    },
  ],
};

// ── output ────────────────────────────────────────────────
std.join("\n---\n", [
  std.manifestYamlDoc(p)
  for p in [
    migrationCheckPipeline,
    testPipeline,
    buildPipeline,
    publishPipeline,
    deployPipeline,
    secret_docker_user,
    secret_docker_pass,
  ]
])
