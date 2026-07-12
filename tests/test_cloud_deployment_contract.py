from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _yaml(path: str) -> dict:
    payload = yaml.safe_load(_text(path))
    assert isinstance(payload, dict)
    return payload


def _render_services() -> tuple[dict, dict, dict[str, object]]:
    blueprint = _yaml("render.yaml")
    services = {service["name"]: service for service in blueprint["services"]}
    groups = {group["name"]: group for group in blueprint["envVarGroups"]}
    defaults = {
        item["key"]: item["value"]
        for item in groups["contentengine-production-defaults"]["envVars"]
    }
    return services["contentengine-web"], services["contentengine-generation-worker"], defaults


def test_render_blueprint_deploys_authenticated_web_and_supervised_worker() -> None:
    web, worker, defaults = _render_services()

    assert web["type"] == "web"
    assert worker["type"] == "worker"
    assert web["runtime"] == worker["runtime"] == "docker"
    assert web["autoDeployTrigger"] == worker["autoDeployTrigger"] == "checksPass"
    assert web["preDeployCommand"] == "python scripts/predeploy.py"
    assert worker["preDeployCommand"] == "python scripts/predeploy.py"
    assert web["healthCheckPath"] == "/ready"
    assert "run_product_ugc_queue_worker.py" in worker["dockerCommand"]
    assert defaults["QVF_AUTH_REQUIRED"] == "true"


def test_render_services_are_stateless_and_fail_closed_to_remote_storage() -> None:
    web, worker, defaults = _render_services()
    blueprint = _text("render.yaml")

    assert defaults["QVF_RUNTIME_PROFILE"] == "production"
    assert defaults["QVF_SESSION_COOKIE_SAMESITE"] == "strict"
    assert defaults["QVF_DEPLOYMENT_ENV"] == "production"
    assert defaults["QVF_STORAGE_BACKEND"] == "supabase"
    assert defaults["QVF_STORAGE_BUCKET"] == "contentengine-private"
    assert defaults["QVF_AUTO_INIT_DB"] == "false"
    assert defaults["QVF_SUPABASE_READINESS_TIMEOUT_SECONDS"] == "5"
    assert all("disk" not in service for service in (web, worker))
    assert "QVF_MEDIA_ROOT" not in blueprint
    assert "sqlite:///" not in blueprint
    assert "127.0.0.1" not in blueprint


def test_render_blueprint_never_commits_production_credentials() -> None:
    web, worker, _defaults = _render_services()
    web_env = {item.get("key"): item for item in web["envVars"] if item.get("key")}
    worker_env = {item.get("key"): item for item in worker["envVars"] if item.get("key")}

    for secret_name in (
        "QVF_DATABASE_URL",
        "QVF_PUBLIC_APP_URL",
        "SUPABASE_URL",
        "SUPABASE_PUBLISHABLE_KEY",
        "SUPABASE_SECRET_KEY",
        "QVF_SUPABASE_JWKS_URL",
        "QVF_SUPABASE_ISSUER",
        "OPENAI_API_KEY",
        "RUNWAYML_API_SECRET",
    ):
        assert web_env[secret_name] == {"key": secret_name, "sync": False}
        assert worker_env[secret_name]["fromService"] == {
            "type": "web",
            "name": "contentengine-web",
            "envVarKey": secret_name,
        }
    assert "SUPABASE_SERVICE_ROLE_KEY" not in web_env
    assert "SUPABASE_SERVICE_ROLE_KEY" not in worker_env


def test_github_checks_and_container_release_are_repository_managed() -> None:
    _yaml(".github/workflows/ci.yml")
    _yaml(".github/workflows/container.yml")
    ci = _text(".github/workflows/ci.yml")
    container = _text(".github/workflows/container.yml")

    assert "Validate deployment YAML syntax" in ci
    assert "python -m pytest -q" in ci
    assert "docker build" in ci
    assert "postgres-migration" in ci
    assert "python scripts/predeploy.py" in ci
    assert "MigrationContext.configure" in ci
    assert "--check-heads" not in ci
    assert "branches:\n      - main" in ci
    assert "workflow_run:" in container
    assert "github.event.workflow_run.conclusion == 'success'" in container
    assert "workflow_run.head_sha" in container
    assert "github.ref == 'refs/heads/main'" in container
    assert 'name=ghcr.io/${GITHUB_REPOSITORY,,}' in container
    assert "docker/build-push-action" in container
    assert "actions/attest@v4" in container


def test_runtime_image_drops_root_and_uses_cloud_entrypoint() -> None:
    dockerfile = _text("Dockerfile")
    web_entrypoint = _text("scripts/run_web.py")

    assert "USER contentengine" in dockerfile
    assert 'CMD ["python", "scripts/run_web.py"]' in dockerfile
    assert "Path(__file__).resolve().parents[1]" in web_entrypoint
    assert "sys.path.insert(0, str(ROOT))" in web_entrypoint
    assert "tesseract-ocr-rus" in dockerfile
    assert "STOPSIGNAL SIGTERM" in dockerfile
    assert "VOLUME" not in dockerfile
    assert "chown -R contentengine:contentengine /app\n" not in dockerfile


def test_docker_context_excludes_secrets_and_local_state() -> None:
    dockerignore = _text(".dockerignore")

    for marker in (".env.*", "*.db", "*.sqlite", "media/", "logs/", "test_media/"):
        assert marker in dockerignore
    assert "!.env.example" not in dockerignore


def test_cloud_documentation_rejects_localhost_as_creator_product() -> None:
    guide = _text("docs/CLOUD_DEPLOYMENT.md")
    normalized = " ".join(guide.split())

    assert "Creators receive one public HTTPS URL" in guide
    assert "never share a local password" in guide
    assert "Do not attach a Render disk" in guide
    assert "QVF_DEPLOYMENT_ENV=production" in guide
    assert "one canonical server secret" in guide
    assert "QVF_LOCAL_AUTH_PASSWORD_HASH" in guide
    assert "sslmode=require" in guide
    assert "It never writes a probe object" in normalized
    assert "Local profile" in guide
    assert "not a hosting method" in normalized
