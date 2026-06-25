#!/bin/bash
set -e

echo "Looking up Project ID..."
PROJECT_ID=$(gcloud config get-value project)
if [ -z "$PROJECT_ID" ]; then
    echo "ERROR: Could not determine Project ID."
    exit 1
fi
echo "Using Project ID: $PROJECT_ID"

REPO="nkhola/ainews"

echo "1/5 Enabling IAM Credentials API..."
gcloud services enable iamcredentials.googleapis.com --project="${PROJECT_ID}"

echo "2/5 Checking Workload Identity Pool..."
gcloud iam workload-identity-pools create "github-actions-pool" \
  --project="${PROJECT_ID}" \
  --location="global" \
  --display-name="GitHub Actions Pool" || echo "Pool already exists."

echo "3/5 Creating Workload Identity Provider..."
gcloud iam workload-identity-pools providers create-oidc "github-actions-provider" \
  --project="${PROJECT_ID}" \
  --location="global" \
  --workload-identity-pool="github-actions-pool" \
  --display-name="GitHub Actions Provider" \
  --attribute-mapping="google.subject=assertion.sub,attribute.actor=assertion.actor,attribute.repository=assertion.repository" \
  --attribute-condition="attribute.repository == '${REPO}'" \
  --issuer-uri="https://token.actions.githubusercontent.com" || echo "Provider already exists."

echo "4/5 Fetching Pool ID..."
WORKLOAD_IDENTITY_POOL_ID=$(gcloud iam workload-identity-pools describe "github-actions-pool" \
  --project="${PROJECT_ID}" --location="global" --format="value(name)")

echo "5/5 Binding Service Account..."
SERVICE_ACCOUNT="github-actions-vertex@${PROJECT_ID}.iam.gserviceaccount.com"
gcloud iam service-accounts add-iam-policy-binding "${SERVICE_ACCOUNT}" \
  --project="${PROJECT_ID}" \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/${WORKLOAD_IDENTITY_POOL_ID}/attribute.repository/${REPO}"

echo ""
echo "=========================================================="
echo "✅ SUCCESS! EVERYTHING IS SETUP."
echo "Wait 3-5 minutes, then run the GitHub action."
echo "=========================================================="
