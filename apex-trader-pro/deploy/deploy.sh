#!/usr/bin/env bash
# Apex Trader Pro — one-shot deployment to Google Cloud.
#
# Prerequisites: gcloud (logged in: `gcloud auth login`), firebase CLI (`npm i -g firebase-tools`, `firebase login`),
# Node 18+, a GCP project with billing enabled and Firebase added to it.
#
# Usage:
#   export PROJECT_ID=my-project REGION=europe-west1 OWNER_EMAIL=me@example.com
#   export BYBIT_API_KEY=... BYBIT_API_SECRET=... TELEGRAM_BOT_TOKEN=... TELEGRAM_CHAT_ID=...
#   export OPENAI_API_KEY=... (optional) ANTHROPIC_API_KEY=... (optional)
#   ./deploy.sh
set -euo pipefail

: "${PROJECT_ID:?set PROJECT_ID}" "${REGION:=europe-west1}" "${OWNER_EMAIL:?set OWNER_EMAIL (your Firebase login)}"
SQL_INSTANCE="${SQL_INSTANCE:-apex-db}"
SQL_TIER="${SQL_TIER:-db-g1-small}"
REPO="apex"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/apex-backend:$(date +%Y%m%d-%H%M%S)"
RUN_SA="apex-runner@${PROJECT_ID}.iam.gserviceaccount.com"
SCHED_SA="apex-scheduler@${PROJECT_ID}.iam.gserviceaccount.com"
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(dirname "$HERE")"

gcloud config set project "$PROJECT_ID" >/dev/null

echo "==> Enabling APIs"
gcloud services enable run.googleapis.com sqladmin.googleapis.com cloudscheduler.googleapis.com \
  secretmanager.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com \
  firebase.googleapis.com identitytoolkit.googleapis.com

echo "==> Service accounts"
for sa in apex-runner apex-scheduler; do
  gcloud iam service-accounts describe "${sa}@${PROJECT_ID}.iam.gserviceaccount.com" >/dev/null 2>&1 ||
    gcloud iam service-accounts create "$sa" --display-name "Apex Trader Pro ($sa)"
done
for role in roles/secretmanager.secretAccessor roles/cloudsql.client; do
  gcloud projects add-iam-policy-binding "$PROJECT_ID" --member "serviceAccount:${RUN_SA}" --role "$role" \
    --condition=None >/dev/null
done

echo "==> Cloud SQL (PostgreSQL 15)"
if ! gcloud sql instances describe "$SQL_INSTANCE" >/dev/null 2>&1; then
  gcloud sql instances create "$SQL_INSTANCE" --database-version=POSTGRES_15 --tier="$SQL_TIER" \
    --region="$REGION" --storage-auto-increase --backup-start-time=03:00
fi
gcloud sql databases describe apex --instance "$SQL_INSTANCE" >/dev/null 2>&1 ||
  gcloud sql databases create apex --instance "$SQL_INSTANCE"
CONN="${PROJECT_ID}:${REGION}:${SQL_INSTANCE}"

secret_exists() { gcloud secrets describe "$1" >/dev/null 2>&1; }
put_secret() {  # put_secret NAME VALUE — creates the secret or adds a new version
  local name="$1" value="$2"
  [ -z "$value" ] && return 0
  secret_exists "$name" || gcloud secrets create "$name" --replication-policy=automatic >/dev/null
  printf '%s' "$value" | gcloud secrets versions add "$name" --data-file=- >/dev/null
  echo "    secret $name updated"
}

if ! secret_exists DATABASE_URL; then
  DB_PASSWORD="$(openssl rand -hex 24)"
  gcloud sql users create apex --instance "$SQL_INSTANCE" --password "$DB_PASSWORD" 2>/dev/null ||
    gcloud sql users set-password apex --instance "$SQL_INSTANCE" --password "$DB_PASSWORD"
  put_secret DATABASE_URL "postgresql://apex:${DB_PASSWORD}@/apex?host=/cloudsql/${CONN}"
fi

echo "==> Secrets"
put_secret BYBIT_API_KEY "${BYBIT_API_KEY:-}"
put_secret BYBIT_API_SECRET "${BYBIT_API_SECRET:-}"
put_secret TELEGRAM_BOT_TOKEN "${TELEGRAM_BOT_TOKEN:-}"
put_secret TELEGRAM_CHAT_ID "${TELEGRAM_CHAT_ID:-}"
put_secret OPENAI_API_KEY "${OPENAI_API_KEY:-}"
put_secret ANTHROPIC_API_KEY "${ANTHROPIC_API_KEY:-}"
put_secret GEMINI_API_KEY "${GEMINI_API_KEY:-}"
secret_exists ADMIN_SECRET || put_secret ADMIN_SECRET "$(openssl rand -hex 32)"
secret_exists LIVE_KEY_ENCRYPTION_SECRET || put_secret LIVE_KEY_ENCRYPTION_SECRET "$(openssl rand -hex 32)"
for s in BYBIT_API_KEY BYBIT_API_SECRET TELEGRAM_BOT_TOKEN TELEGRAM_CHAT_ID; do
  secret_exists "$s" || { echo "ERROR: secret $s is missing — export it and re-run"; exit 1; }
done

echo "==> Building image"
gcloud artifacts repositories describe "$REPO" --location "$REGION" >/dev/null 2>&1 ||
  gcloud artifacts repositories create "$REPO" --repository-format=docker --location "$REGION"
gcloud builds submit "$ROOT/backend" --tag "$IMAGE"

SECRETS="DATABASE_URL=DATABASE_URL:latest,BYBIT_API_KEY=BYBIT_API_KEY:latest,BYBIT_API_SECRET=BYBIT_API_SECRET:latest"
SECRETS+=",TELEGRAM_BOT_TOKEN=TELEGRAM_BOT_TOKEN:latest,TELEGRAM_CHAT_ID=TELEGRAM_CHAT_ID:latest,ADMIN_SECRET=ADMIN_SECRET:latest"
for opt in OPENAI_API_KEY ANTHROPIC_API_KEY GEMINI_API_KEY; do
  secret_exists "$opt" && SECRETS+=",${opt}=${opt}:latest"
done

# service:public(yes/no):timeout:max-instances
SERVICES=(
  "run-apex-hybrid:no:120:1"
  "monitor-positions:no:120:1"
  "reset-auto-reverse:no:60:1"
  "evolve-adaptive-nexus:no:1800:1"
  "get-balance:yes:30:3"
  "save-settings:yes:30:3"
  "get-settings:yes:30:3"
  "parse-custom-strategy:yes:120:2"
  "dashboard-api:yes:60:3"
  "telegram-command-handler:yes:60:2"
)

echo "==> Deploying Cloud Run services"
for spec in "${SERVICES[@]}"; do
  IFS=: read -r name public timeout maxi <<<"$spec"
  auth_flag="--no-allow-unauthenticated"
  [ "$public" = yes ] && auth_flag="--allow-unauthenticated"  # protected in-app by Firebase ID token / webhook secret
  gcloud run deploy "$name" --image "$IMAGE" --region "$REGION" --service-account "$RUN_SA" \
    --add-cloudsql-instances "$CONN" --set-secrets "$SECRETS" \
    --set-env-vars "APEX_SERVICE=${name},OWNER_EMAIL=${OWNER_EMAIL},GOOGLE_CLOUD_PROJECT=${PROJECT_ID},APEX_MIGRATE=true" \
    --timeout "$timeout" --max-instances "$maxi" --concurrency "$([ "$public" = yes ] && echo 20 || echo 1)" \
    --memory 512Mi --cpu 1 $auth_flag --quiet
done

echo "==> Cloud Scheduler"
ADMIN_SECRET_VALUE="$(gcloud secrets versions access latest --secret ADMIN_SECRET)"
url_of() { gcloud run services describe "$1" --region "$REGION" --format 'value(status.url)'; }
job() {  # job NAME SCHEDULE SERVICE PATH
  local name="$1" schedule="$2" svc="$3" path="$4" url
  url="$(url_of "$svc")$path"
  gcloud run services add-iam-policy-binding "$svc" --region "$REGION" \
    --member "serviceAccount:${SCHED_SA}" --role roles/run.invoker >/dev/null
  local args=(--location "$REGION" --schedule "$schedule" --time-zone UTC --uri "$url" --http-method POST
    --oidc-service-account-email "$SCHED_SA" --oidc-token-audience "$(url_of "$svc")"
    --headers "X-Admin-Secret=${ADMIN_SECRET_VALUE}" --attempt-deadline 180s)
  if gcloud scheduler jobs describe "$name" --location "$REGION" >/dev/null 2>&1; then
    gcloud scheduler jobs update http "$name" "${args[@]}" --update-headers "X-Admin-Secret=${ADMIN_SECRET_VALUE}" >/dev/null 2>&1 ||
      { gcloud scheduler jobs delete "$name" --location "$REGION" --quiet; gcloud scheduler jobs create http "$name" "${args[@]}"; }
  else
    gcloud scheduler jobs create http "$name" "${args[@]}"
  fi
}
job apex-run-hybrid "* * * * *" run-apex-hybrid /run-apex-hybrid
# Cloud Scheduler's minimum period is 1 minute: each call runs two passes 30 s apart.
job apex-monitor-positions "* * * * *" monitor-positions "/monitor-positions?passes=2&interval=30"
job apex-reset-auto-reverse "0 0 * * *" reset-auto-reverse /reset-auto-reverse
job apex-evolve-nexus "0 0 * * 0" evolve-adaptive-nexus /evolve-adaptive-nexus

echo "==> Telegram webhook"
TG_TOKEN="$(gcloud secrets versions access latest --secret TELEGRAM_BOT_TOKEN)"
TG_SECRET="$(printf 'tg:%s' "$ADMIN_SECRET_VALUE" | sha256sum | cut -d' ' -f1)"
curl -fsS "https://api.telegram.org/bot${TG_TOKEN}/setWebhook" \
  --data-urlencode "url=$(url_of telegram-command-handler)/telegram-command-handler" \
  --data-urlencode "secret_token=${TG_SECRET}" --data-urlencode 'allowed_updates=["message","callback_query"]'
echo

echo "==> Frontend (Firebase Hosting)"
sed -e "s/__REGION__/${REGION}/g" "$HERE/firebase.json.template" > "$ROOT/frontend/firebase.json"
printf '{ "projects": { "default": "%s" } }\n' "$PROJECT_ID" > "$ROOT/frontend/.firebaserc"
( cd "$ROOT/frontend" && npm ci && npm run build && firebase deploy --only hosting --project "$PROJECT_ID" )

cat <<MSG

Done. Next steps:
  1. Firebase console -> Authentication -> enable Email/Password and create the user ${OWNER_EMAIL}.
  2. Open the Hosting URL, log in, enable strategies in Settings.
  3. Trading stays in "signals only" mode until you press "Arm live trading" (or Telegram /strategies).
MSG
