# Deploy to Google Cloud Run

This guide deploys the blackjack trainer (FastAPI + WebSocket + xterm.js) to Cloud Run using `gcloud run deploy --source .`, which builds from the `Dockerfile` via Cloud Build and pushes to Artifact Registry automatically.

The app has no external dependencies — no database, no API keys, no secrets.

---

## Prerequisites

- [gcloud CLI](https://cloud.google.com/sdk/docs/install) installed and authenticated (`gcloud auth login`)
- A GCP project with billing enabled
- Docker (optional, for local testing before deploying)

---

## GCP Project Setup

```bash
# Set your project
gcloud config set project YOUR_PROJECT_ID
```
```
# Enable required APIs
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com
```

---

## Service Account

Create a dedicated service account for the Cloud Run service. This app makes no GCP API calls at runtime, so no roles are needed — least-privilege by default.

```bash
gcloud iam service-accounts create blackjack-runner \
  --display-name="Blackjack Trainer Cloud Run SA"
```

---

## Deploy

### Step 1: Initial deploy (get the service URL)

`WS_ALLOWED_ORIGINS` must be set to the service URL, but the URL isn't known until after the first deploy. Run the initial deploy without it:

```bash
gcloud run deploy blackjack-trainer \
  --source . \
  --region us-central1 \
  --service-account blackjack-runner@YOUR_PROJECT_ID.iam.gserviceaccount.com \
  --session-affinity \
  --timeout 600 \
  --memory 512Mi \
  --min-instances 0 \
  --max-instances 3 \
  --allow-unauthenticated
```

Flag reference:

| Flag | Value | Reason |
|---|---|---|
| `--source .` | — | Build from `Dockerfile` via Cloud Build |
| `--session-affinity` | — | Route each client to the same instance for the WebSocket lifetime |
| `--timeout` | `600` | 10 min; longer than the 300s WebSocket idle timeout so Cloud Run doesn't cut connections |
| `--memory` | `512Mi` | Small app; no large data in memory |
| `--min-instances` | `0` | Scale to zero when idle |
| `--max-instances` | `3` | Cap to prevent runaway costs |
| `--allow-unauthenticated` | — | Public access; remove for private/internal use and add IAM bindings instead |

### Step 2: Lock WebSocket origins

Get the service URL from the deploy output, or retrieve it:

```bash
gcloud run services describe blackjack-trainer \
  --region us-central1 \
  --format="value(status.url)"
```

Redeploy with the origin restriction set:

```bash
gcloud run deploy blackjack-trainer \
  --source . \
  --region us-central1 \
  --service-account blackjack-runner@YOUR_PROJECT_ID.iam.gserviceaccount.com \
  --session-affinity \
  --timeout 600 \
  --memory 512Mi \
  --min-instances 0 \
  --max-instances 3 \
  --allow-unauthenticated \
  --set-env-vars WS_ALLOWED_ORIGINS=https://YOUR_SERVICE_URL
```

Replace `YOUR_SERVICE_URL` with the URL from Step 1 (e.g. `blackjack-trainer-abc123-uc.a.run.app`).

---

## Verify

```bash
# Confirm the service URL
gcloud run services describe blackjack-trainer \
  --region us-central1 \
  --format="value(status.url)"

# Tail recent logs
gcloud run services logs read blackjack-trainer \
  --region us-central1 \
  --limit 50
```

Open the service URL in a browser and confirm the terminal loads and the game starts.

---

## Local Docker Test

Test the container locally before deploying:

```bash
docker build -t blackjack-trainer .
docker run -p 8080:8080 -e PORT=8080 blackjack-trainer
# Open http://localhost:8080
```

---

## Redeploy After Code Changes

Run the same deploy command from Step 2. Cloud Build will detect changed layers and rebuild only what's needed.

---

## Cleanup

```bash
# Delete the Cloud Run service
gcloud run services delete blackjack-trainer --region us-central1

# List and delete Artifact Registry images (if desired)
gcloud artifacts docker images list \
  us-central1-docker.pkg.dev/YOUR_PROJECT_ID/cloud-run-source-deploy/blackjack-trainer

gcloud artifacts docker images delete \
  us-central1-docker.pkg.dev/YOUR_PROJECT_ID/cloud-run-source-deploy/blackjack-trainer \
  --delete-tags --quiet
```
