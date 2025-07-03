// output to .drone.yml (which drone really reads)
// jsonnet .drone.jsonnet | jq . | yq -P - > .drone.yml


local VALUES = {
  PROJECT_NAME:             "walrus",
  DOCKERHUB_USER:           "popopopony",
  DOCKERHUB_IMAGE:          "popopopony/walrus",
  K8S_DEPLOYMENT_NAME:      "walrus",
  K8S_DEPLOYMENT_NAMESPACE: "walrus",
  CONTAINER_NAME:           "walrus",
  BRANCH:                   "master",
};



local SECRET = {
  K8S_SERVER:           { from_secret: "K8S_SERVER" },
  K8S_TOKEN:            { from_secret: "K8S_TOKEN" },
  K8S_CA:               { from_secret: "K8S_CA" },
  DOCKER_USERNAME:      { from_secret: "DOCKER_USERNAME_pony" },
  DOCKER_PASSWORD:      { from_secret: "DOCKER_PASSWORD_pony" },
};


local CELERY_DEPLOYMENTS = [
  "%s-celery-playlog" % VALUES.K8S_DEPLOYMENT_NAME,
  "%s-celery-beat" % VALUES.K8S_DEPLOYMENT_NAME,
];


local migration_chack_pipeline = {
  kind: "pipeline",
  type: "kubernetes",
  name: "walrus-migration-check",
  node: {
    // should be equal to DRONE_RUNNER_LABELS in drone-runner
    repo: "Lab3-Spotify-walrus",
  },
  trigger: {
    event: ["pull_request"],
  },
  steps: [
    {
      name:  "migration-dry-run",
      image: "python:3.10.13-slim",
      environment:{
        DJANGO_SECRET_KEY: "MIGRATION_CHECK_PIPELINE_SUPER_SECRET"
      },
      commands: [
        "pip install -r requirements.txt || exit 1",
        "python manage.py check || exit 1",
        "python manage.py makemigrations --dry-run --check",
      ],
    },
  ],
};

local test_pipeline = {
  kind: "pipeline",
  type: "kubernetes",
  name: "walrus-test",
  node: {
    // should be equal to DRONE_RUNNER_LABELS in drone-runner
    repo: "Lab3-Spotify-walrus",
  },
  trigger: {
    event:  ["push"],
    branch: [ VALUES.BRANCH ],
  },
  services: [
    {
      name: "walrus-test-db",
      image: "postgres:14-alpine",
      environment: {
        POSTGRES_USER: "walrus-test",
        POSTGRES_PASSWORD: "walrus-test",
        POSTGRES_DB: "walrus-test",
      },
    },
    {
      name: "walrus-test-redis",
      image: "redis:7.4.2",
    },
  ],
  steps: [
    {
      name:  "install-and-test",
      image: "python:3.10.13-slim",
      environment: {
        ENV:                    "test",
        DJANGO_SECRET_KEY:      "TEST_PIPELINE_SUPER_SECRET",
        POSTGRES_HOST:          "walrus-test-db",
        POSTGRES_USER:          "walrus-test",
        POSTGRES_PASSWORD:      "walrus-test",
        POSTGRES_DB:            "walrus-test",
        POSTGRES_PORT:          "5432",
        REDIS_HOST:             "rwalrus-test-redis",
        REDIS_PORT:             "6379",
      },
      commands: [
        "pip install -r requirements.txt || exit 1",
        "python manage.py test || exit 1",
      ],
    },
  ],
};

local deploy_pipeline = {
  kind: "pipeline",
  type: "kubernetes",
  name: "walrus-deploy",
  node: {
    // should be equal to DRONE_RUNNER_LABELS in drone-runner
    repo: "Lab3-Spotify-walrus",
  },
  trigger: {
    event:  ["push"],
    branch: [ VALUES.BRANCH ],
  },
  steps: [
    {
      name:  "build and push docker image",
      image: "plugins/docker",
      settings: {
        repo:  VALUES.DOCKERHUB_IMAGE,
        tags: ["latest", "${DRONE_COMMIT_SHA}"],
        username: SECRET.DOCKER_USERNAME,
        password: SECRET.DOCKER_PASSWORD,
      },
    },
    {
      name:  "deploy to k8s",
      image: "sinlead/drone-kubectl",
      settings: {
        kubernetes_server: SECRET.K8S_SERVER,
        kubernetes_token:  SECRET.K8S_TOKEN,
        kubernetes_cert:   SECRET.K8S_CA,
        namespace: VALUES.K8S_DEPLOYMENT_NAMESPACE,
        startTimeout: 240
      },
      // commands: [
      //   std.format(
      //     "kubectl set image deployment/%s %s=%s:${DRONE_COMMIT_SHA} --namespace=%s || exit 1",
      //     [VALUES.K8S_DEPLOYMENT_NAME, VALUES.CONTAINER_NAME, VALUES.DOCKERHUB_IMAGE, VALUES.K8S_DEPLOYMENT_NAMESPACE]
      //   ),
      //   std.format(
      //     "kubectl rollout status deployment/%s --namespace=%s || exit 1",
      //     [VALUES.K8S_DEPLOYMENT_NAME, VALUES.K8S_DEPLOYMENT_NAMESPACE]
      //   ),
      //   "echo Deployment success!",
      // ],
      commands: [
        std.format(
          "kubectl set image deployment/%s %s=%s:${DRONE_COMMIT_SHA} --namespace=%s || exit 1",
          [VALUES.K8S_DEPLOYMENT_NAME, VALUES.CONTAINER_NAME, VALUES.DOCKERHUB_IMAGE, VALUES.K8S_DEPLOYMENT_NAMESPACE]
        ),
      ] +
      std.map(
        function(name)
          std.format(
            "kubectl set image deployment/%s %s=%s:${DRONE_COMMIT_SHA} --namespace=%s || exit 1",
            [name, name, VALUES.DOCKERHUB_IMAGE, VALUES.K8S_DEPLOYMENT_NAMESPACE]
          ),
        CELERY_DEPLOYMENTS
      ) +
      [
        std.format(
          "kubectl rollout status deployment/%s --namespace=%s || exit 1",
          [VALUES.K8S_DEPLOYMENT_NAME, VALUES.K8S_DEPLOYMENT_NAMESPACE]
        ),
      ] +
      std.map(
        function(name)
          std.format(
            "kubectl rollout status deployment/%s --namespace=%s || exit 1",
            [name, VALUES.K8S_DEPLOYMENT_NAMESPACE]
          ),
        CELERY_DEPLOYMENTS
      ) + [
        "echo Deployment success!",
      ]
    },
  ],
};

std.manifestYamlDoc(migration_chack_pipeline) + "\n---\n" + std.manifestYamlDoc(test_pipeline) + "\n---\n" + std.manifestYamlDoc(deploy_pipeline)
