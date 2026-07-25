# Deploying ADD to GKE

Raw Kubernetes manifests for running AI-Driven Development on Google Kubernetes
Engine (GKE). Everything lives in the `add` namespace.

## Live POC endpoints (ephemeral — LB IPs change on recreate)

| What | URL |
|---|---|
| Frontend | http://8.232.238.64/ |
| API docs (Swagger) | http://8.232.238.64/api/v1/docs |
| Django admin | http://8.232.238.64/admin/ |
| **Qdrant dashboard** | **http://136.65.214.203:6333/dashboard** |

> The app URLs share the Ingress IP; Qdrant is a separate LoadBalancer
> (`add-qdrant-lb`, POC-only, no auth). These IPs are not stable — re-check with
> `kubectl -n add get ingress,svc` after a recreate.

```
namespace.yaml     Namespace: add
configmap.yaml     Non-secret config (LLM_PROVIDER, service DNS, GitHub owner…)
secret.example.yaml  Template for secrets — copy to secret.yaml (gitignored)
postgres.yaml      StatefulSet + headless Service + 5Gi PVC
redis.yaml         Deployment + Service (channel layer / cache)
qdrant.yaml        StatefulSet + Service + 5Gi PVC (vector search)
backend.yaml       Django/Daphne Deployment + Service (add-api:8001)
                   + BackendConfig (keeps WebSockets alive through the LB)
                   + init container: migrate + seed
frontend.yaml      SPA Deployment + Service (add-frontend:5173)
ingress.yaml       GCE Ingress: /api,/ws,/admin -> backend; / -> frontend
kustomization.yaml Ties it together + image registry overrides
```

## Prerequisites

- A GKE cluster and `kubectl` context pointing at it
- An Artifact Registry repo, e.g. `REGION-docker.pkg.dev/PROJECT_ID/add`
- `LLM_PROVIDER` decided: **`claude`** (needs `ANTHROPIC_API_KEY`) or **`vertex`**
  (GCP-native — see below). Ollama is intentionally **not** deployed here: it
  needs GPU nodes and large models. Local/dev still uses Ollama via docker-compose.

## 1. Build & push images

```bash
export REGION=us-central1 PROJECT_ID=your-project
export REG=$REGION-docker.pkg.dev/$PROJECT_ID/add

# Backend
docker build -t $REG/add-backend:latest .
docker push $REG/add-backend:latest

# Frontend
docker build -t $REG/add-frontend:latest ./frontend
docker push $REG/add-frontend:latest
```

Then edit `kustomization.yaml` and replace `REGION`/`PROJECT_ID` in the `images:`
block (or `kubectl kustomize` with an overlay).

## 2. Create secrets (never committed)

```bash
cp k8s/secret.example.yaml k8s/secret.yaml
# edit k8s/secret.yaml: DJANGO_SECRET_KEY, POSTGRES_PASSWORD (must match
# DATABASE_URL), GITHUB_PAT, ANTHROPIC_API_KEY
kubectl apply -f k8s/secret.yaml
```

## 3. Deploy everything else

```bash
kubectl apply -k k8s/
kubectl -n add rollout status deploy/add-api
kubectl -n add get pods
```

## 4. Get the URL

```bash
kubectl -n add get ingress add-ingress   # note the ADDRESS (may take a few min)
```

Open `http://<ADDRESS>/`. The SPA is served at `/`; it calls `/api`, `/ws`,
`/admin` and `/static` on the same host, which the Ingress routes to the backend.

## Automated deploy via GitHub Actions

`.github/workflows/deploy-gke.yml` builds + pushes both images to Artifact
Registry and applies these manifests on every push to `main` (keyless auth via
Workload Identity Federation — no JSON keys in GitHub). It creates the
`add-secrets` Secret from GitHub secrets, so `k8s/secret.yaml` is only needed for
manual `kubectl` deploys.

Configure once in **Settings ▸ Secrets and variables ▸ Actions**:

**Variables:** `GCP_PROJECT_ID`, `GCP_REGION`, `AR_REPO`, `GKE_CLUSTER`, `GKE_LOCATION`

**Secrets:** `WIF_PROVIDER`, `WIF_SERVICE_ACCOUNT`, `DJANGO_SECRET_KEY`,
`DATABASE_URL`, `POSTGRES_PASSWORD`, `DJANGO_SUPERUSER_PASSWORD`,
`ANTHROPIC_API_KEY`, `ENCRYPTION_KEY`, and `APP_GITHUB_PAT` (the app's PAT —
GitHub reserves the `GITHUB_` secret prefix, so it must use a different name).

One-time GCP setup the deployer service account needs: roles
`roles/artifactregistry.writer` and `roles/container.developer`, plus a Workload
Identity Pool/provider bound to this repo.

## Using Vertex AI (GCP-native, the "Bedrock equivalent")

1. In `configmap.yaml` set `LLM_PROVIDER: "vertex"` and `VERTEX_PROJECT: your-project`.
2. Enable **Workload Identity** on the cluster and bind the `add` KSA to a GSA
   with the *Vertex AI User* role — then no key file is needed in the pod.
3. Per-agent model overrides still work via the routing YAML
   (`vertex_ai/gemini-1.5-pro`, etc.).

## Production hardening (follow-ups, not required for a POC)

- **Frontend**: replace the vite dev image with a static build served by nginx
  on port 80 (multi-stage `node build` → `nginx`), and update `frontend.yaml`
  port + probe. The dev server is fine for a demo but not for production.
- **Secrets**: use Secret Manager + the CSI driver instead of a raw Secret.
- **DB**: consider Cloud SQL (Postgres) instead of the in-cluster StatefulSet.
- **Seeds**: move the init-container seeding into a one-shot `Job` before
  scaling the backend beyond 1 replica.
- **HTTPS**: uncomment the ManagedCertificate + static IP annotations in
  `ingress.yaml` and point DNS at the reserved IP.
- **Django**: set `DEBUG=False` and real `ALLOWED_HOSTS`/`CSRF_TRUSTED_ORIGINS`.
