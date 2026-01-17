# -*- mode: Python -*-
# https://docs.tilt.dev/
#
# Tilt configuration for buun-curator

allow_k8s_contexts(k8s_context())

config.define_string('registry')
config.define_bool('port-forward')
config.define_string('extra-values-file')
config.define_bool('enable-health-logs')
config.define_bool('enable-reddit')
config.define_bool('prod-image')

cfg = config.parse()

registry = cfg.get('registry', 'localhost:30500')
default_registry(registry)

use_prod_image = cfg.get('prod-image', False)

if use_prod_image:
    # Production image build (uses experimental build mode)
    docker_build(
        'buun-curator-frontend',
        '.',
        dockerfile='Dockerfile',
    )
    print("🏗️  Using production Dockerfile with experimental build mode")
    docker_build(
        'buun-curator-worker',
        './worker',
        dockerfile='./worker/Dockerfile',
    )
    print("🏗️  Worker: Using production Dockerfile")
    docker_build(
        'buun-curator-agent',
        './agent',
        dockerfile='./agent/Dockerfile',
    )
    print("🏗️  Agent: Using production Dockerfile")
else:
    # Development image build (hot reload enabled)
    docker_build(
        'buun-curator-frontend',
        '.',
        dockerfile='Dockerfile.dev',
        ignore=['./worker', './agent'],
        live_update=[
            sync('.', '/app'),
            run('bun install', trigger=['./package.json', './bun.lock']),
        ]
    )
    print("🔥 Using development Dockerfile with live reload")
    docker_build(
        'buun-curator-worker',
        './worker',
        dockerfile='./worker/Dockerfile.dev',
        live_update=[
            sync('./worker', '/app'),
            run('uv sync --frozen', trigger=['./worker/pyproject.toml', './worker/uv.lock']),
        ],
    )
    print("🔥 Worker: Using development Dockerfile with live reload")
    docker_build(
        'buun-curator-agent',
        './agent',
        dockerfile='./agent/Dockerfile.dev',
        live_update=[
            sync('./agent', '/app'),
            run('uv sync --frozen', trigger=['./agent/pyproject.toml', './agent/uv.lock']),
        ],
    )
    print("🔥 Agent: Using development Dockerfile with live reload")

values_files = ['./charts/buun-curator/values-dev.yaml']
extra_values_file = cfg.get('extra-values-file', '')
if extra_values_file:
    values_files.append(extra_values_file)
    print("📝 Using extra values file: " + extra_values_file)

helm_set_values = []

enable_health_logs = cfg.get('enable-health-logs', False)
if enable_health_logs:
    helm_set_values.append('logging.health_request=true')
    print("📵 Health check request logs enabled")

enable_reddit = cfg.get('enable-reddit', False)
if enable_reddit:
    helm_set_values.append('reddit.enabled=true')
    print("👽 Reddit integration enabled")

helm_release = helm(
    './charts/buun-curator',
    name='buun-curator',
    values=values_files,
    set=helm_set_values,
)
k8s_yaml(helm_release)

enable_port_forwards = cfg.get('port-forward', False)
if enable_port_forwards:
    print("🚀 Access your application at: http://localhost:13000")

k8s_resource(
    'buun-curator-frontend',
    port_forwards='13000:3000' if enable_port_forwards else [],
    labels=['frontend'],
)
k8s_resource(
    'buun-curator-worker',
    labels=['worker'],
)
k8s_resource(
    'buun-curator-agent',
    port_forwards='18000:8000' if enable_port_forwards else [],
    labels=['agent'],
)
