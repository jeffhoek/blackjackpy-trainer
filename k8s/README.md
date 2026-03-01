# blackjackpy-trainer — EKS Deployment Runbook

Deploys the blackjackpy-trainer FastAPI + WebSocket app to the `eks-proto` cluster in `us-east-2`
using Amazon ECR for images and an AWS Application Load Balancer for ingress.

---

## Architecture Overview

```
GitHub (push to main)
  ↓
[Build Job]
  • OIDC → AWS credentials (no long-lived keys)
  • docker build → push to ECR (tag: commit SHA)
  ↓
[Deploy Job]
  • Check EKS cluster is active (skips gracefully if not)
  • kubectl apply k8s/ manifests
  • Rolling update with new image tag
  • Wait for rollout (120s timeout)
  ↓
AWS EKS (eks-proto, us-east-2)
  └─ Namespace: blackjack
     ├─ Deployment: blackjack-trainer (2 replicas)
     ├─ Service: ClusterIP (port 80 → 8080)
     └─ Ingress: ALB (internet-facing, sticky sessions, 600s idle timeout)
          ↓
     FastAPI app (port 8080)
     • xterm.js terminal UI over WebSocket (/ws)
     • Basic strategy trainer game logic
```

### Why sticky sessions?

The game state is held in memory per WebSocket connection. With 2 replicas, the ALB must
route each browser to the same pod for the duration of the session. The ingress is configured
with 24-hour stickiness so reconnects after brief drops land on the same pod.

### K8s files in this directory

| File | Purpose |
|------|---------|
| `namespace.yaml` | `blackjack` namespace |
| `deployment.yaml` | 2-replica Deployment |
| `service.yaml` | ClusterIP, port 80 → 8080 |
| `ingress.yaml` | ALB ingress, sticky sessions, 600s idle timeout |

CI/CD workflow: `../.github/workflows/deploy.yml` (triggers on push to `main`, also manually dispatchable)

---

## Prerequisites

| Tool | Purpose | Install |
|------|---------|---------|
| `aws` CLI v2 | ECR login, EKS kubeconfig, IAM setup | https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html |
| `kubectl` | Apply manifests, check pod and ingress status | `brew install kubectl` |
| `eksctl` | Grant the deploy IAM role kubectl access | `brew install eksctl` |
| `docker` or `podman` | Local image build and test | `brew install podman` |

AWS requirements:
- AWS CLI configured with a principal that has IAM and ECR admin access for the setup steps
- EKS cluster `eks-proto` is **ACTIVE** in `us-east-2` (required for Phase 2 only)
- AWS Load Balancer Controller is provisioned by the cluster Terraform — no manual Helm install needed

---

## Phase 1 — Before the cluster exists

Everything in this phase requires only the AWS CLI, Docker, and git. No active EKS cluster needed.

### Step 1 — Create the ECR repository

ECR is where GitHub Actions pushes the container image. The repository must exist before the first push.

- Create the repository with vulnerability scanning enabled on every push

```bash
aws ecr create-repository \
  --repository-name blackjackpy-trainer \
  --region us-east-2 \
  --image-scanning-configuration scanOnPush=true
```

Note the `repositoryUri` in the output — it looks like:
`123456789012.dkr.ecr.us-east-2.amazonaws.com/blackjackpy-trainer`

- Verify the repository exists at any time

```bash
aws ecr describe-repositories \
  --repository-names blackjackpy-trainer \
  --region us-east-2
```

---

### Step 2 — Register the GitHub OIDC provider in AWS IAM

**What is OIDC?** GitHub Actions runners mint short-lived tokens signed by GitHub's identity
provider (`token.actions.githubusercontent.com`). AWS IAM can trust these tokens instead of
requiring long-lived access keys stored as secrets. You register GitHub's provider once per AWS
account — all repositories in the account share it.

- Check if the provider is already registered (it only needs to exist once)

```bash
aws iam list-open-id-connect-providers | grep token.actions.githubusercontent.com
```

If nothing is returned, register it:

- Register GitHub's OIDC provider with its public thumbprint

```bash
aws iam create-open-id-connect-provider \
  --url https://token.actions.githubusercontent.com \
  --client-id-list sts.amazonaws.com \
  --thumbprint-list 6938fd4d98bab03faadb97b34396831e3780aea1
```

---

### Step 3 — Add the GitHub Actions secret

The deploy role ARN follows a predictable format, so you can add the GitHub secret now —
before the role itself exists.

- Compute the ARN for the role you'll create in the next step

```bash
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
echo "arn:aws:iam::${ACCOUNT_ID}:role/blackjackpy-trainer-github-deploy"
```

In your GitHub repository:

1. Go to **Settings → Secrets and variables → Actions**
2. Click **New repository secret**
3. Name: `AWS_DEPLOY_ROLE_ARN`
4. Value: the ARN printed above

---

### Step 4 — Create and configure the IAM deploy role

**IAM roles have two independent halves:**

- **Trust policy** — controls *who* can assume the role (Step 4a)
- **Permission policies** — control *what* the role can do once assumed (Step 4b)

A caller must satisfy *both* to use the role.

#### Step 4a — Create the role (trust policy)

The trust policy scopes assumption to GitHub Actions OIDC tokens from this specific repository
and branch. The `sub` condition prevents tokens from other repositories or branches from
assuming this role.

- Store your account ID, GitHub org, and repo name

```bash
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
GITHUB_ORG=jeffhoek
GITHUB_REPO=blackjackpy-trainer
```

- Write the trust policy and create the role

```bash
cat > /tmp/trust-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {
      "Federated": "arn:aws:iam::${ACCOUNT_ID}:oidc-provider/token.actions.githubusercontent.com"
    },
    "Action": "sts:AssumeRoleWithWebIdentity",
    "Condition": {
      "StringEquals": {
        "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
      },
      "StringLike": {
        "token.actions.githubusercontent.com:sub": "repo:${GITHUB_ORG}/${GITHUB_REPO}:ref:refs/heads/main"
      }
    }
  }]
}
EOF

aws iam create-role \
  --role-name blackjackpy-trainer-github-deploy \
  --assume-role-policy-document file:///tmp/trust-policy.json
```

- Verify the trust policy looks correct

```bash
aws iam get-role \
  --role-name blackjackpy-trainer-github-deploy \
  --query 'Role.AssumeRolePolicyDocument' \
  --output json
```

#### Step 4b — Attach permissions to the role

- Attach the AWS-managed ECR PowerUser policy to allow pushing and pulling images

```bash
aws iam attach-role-policy \
  --role-name blackjackpy-trainer-github-deploy \
  --policy-arn arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryPowerUser
```

- Attach an inline policy granting permission to describe EKS clusters (needed so the runner can call `aws eks update-kubeconfig`)

```bash
cat > /tmp/eks-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Action": [
      "eks:DescribeCluster",
      "eks:ListClusters"
    ],
    "Resource": "*"
  }]
}
EOF

aws iam put-role-policy \
  --role-name blackjackpy-trainer-github-deploy \
  --policy-name eks-describe \
  --policy-document file:///tmp/eks-policy.json
```

---

### Step 5 — Update deployment.yaml with your ECR account ID

The `deployment.yaml` contains a placeholder `ACCOUNT_ID` in the image URI. Replace it with
your actual account ID so the manifest references the correct ECR repository.

- Replace the placeholder in-place and confirm the result

```bash
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
sed -i '' "s|ACCOUNT_ID|${ACCOUNT_ID}|" deployment.yaml
grep "image:" deployment.yaml
# Expected: image: 123456789012.dkr.ecr.us-east-2.amazonaws.com/blackjackpy-trainer:latest
```

---

### Step 6 — Commit, push, and merge to main

- Stage the manifests and workflow file

```bash
git add k8s/ .github/workflows/deploy.yml
git commit -m "Add EKS deployment manifests and CI/CD workflow"
git push origin <your-branch>
# Open a PR and merge to main
```

The GitHub Actions workflow triggers on merge. It will succeed through the ECR image build and
push, then gracefully skip the `kubectl` steps because the cluster doesn't exist yet — that's
expected. Confirm the image landed in ECR:

```bash
aws ecr describe-images \
  --repository-name blackjackpy-trainer \
  --region us-east-2
```

---

## Phase 2 — After the cluster is provisioned

Everything below requires `eks-proto` to be running. The AWS Load Balancer Controller is
provisioned automatically by the cluster Terraform — no manual Helm installation needed.

### Step 7 — Connect kubectl to the cluster

- Fetch credentials and write them to your local kubeconfig

```bash
aws eks update-kubeconfig --name eks-proto --region us-east-2
kubectl get nodes
```

---

### Step 8 — Grant the deploy role kubectl access

**Why this step?** AWS IAM controls who can call the EKS API (Step 4), but Kubernetes RBAC
controls what an authenticated identity can do *inside* the cluster. This step maps the IAM
deploy role to a Kubernetes user in the `system:masters` group, giving the GitHub Actions runner
full cluster-admin access via `kubectl`.

- Map the IAM role to a Kubernetes user with `system:masters` via `eksctl`

```bash
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

eksctl create iamidentitymapping \
  --cluster eks-proto \
  --region us-east-2 \
  --arn arn:aws:iam::${ACCOUNT_ID}:role/blackjackpy-trainer-github-deploy \
  --username github-deploy \
  --group system:masters
```

> **Note:** `system:masters` is the simplest way to grant full cluster access for CI/CD.
> For tighter security, create a custom `ClusterRole` scoped to the `blackjack` namespace.

Without `eksctl`, edit the `aws-auth` ConfigMap directly — malformed YAML will break cluster
authentication for all users:

```bash
kubectl edit configmap aws-auth -n kube-system
# Add under mapRoles:
#   - rolearn: arn:aws:iam::<ACCOUNT_ID>:role/blackjackpy-trainer-github-deploy
#     username: github-deploy
#     groups:
#       - system:masters
```

---

### Step 9 — Trigger the full deploy

Push a commit to `main` or dispatch the workflow manually from the GitHub Actions UI.
The full pipeline — build → push → `kubectl apply` → rolling update — should now complete
without errors.

```
GitHub → Actions → "Deploy to EKS" → Run workflow → Run workflow
```

---

### Step 10 — Lock WebSocket origins

Once the ALB is provisioned (takes ~60s after first `kubectl apply`), restrict WebSocket
connections to the known ALB hostname to prevent cross-origin requests.

- Get the ALB hostname and set the allowed origins environment variable

```bash
ALB_HOST=$(kubectl get ingress blackjack-trainer -n blackjack \
  -o jsonpath='{.status.loadBalancer.ingress[0].hostname}')
echo "ALB hostname: $ALB_HOST"

kubectl set env deployment/blackjack-trainer -n blackjack \
  WS_ALLOWED_ORIGINS="http://${ALB_HOST}"
```

Then persist it in `deployment.yaml` by uncommenting and filling in the `WS_ALLOWED_ORIGINS`
env var so future `kubectl apply` runs don't revert it.

---

## Post-Deploy Verification

- Watch pod status until both replicas are `Running` and `Ready`

```bash
kubectl get pods -n blackjack -w
```

- Confirm the ingress has an ALB hostname in the `ADDRESS` column (takes ~60s after first apply)

```bash
kubectl get ingress -n blackjack
```

- Open the app in your browser — the xterm.js terminal should load and be playable

```bash
open http://$(kubectl get ingress blackjack-trainer -n blackjack \
  -o jsonpath='{.status.loadBalancer.ingress[0].hostname}')
```

- Confirm the WebSocket connection stays open: **DevTools → Network → WS tab → `/ws`**

---

## Rollback

- Roll back to the previous deployment revision

```bash
kubectl rollout undo deployment/blackjack-trainer -n blackjack
```

- To roll back to a specific revision, list available revisions first

```bash
kubectl rollout history deployment/blackjack-trainer -n blackjack
kubectl rollout undo deployment/blackjack-trainer -n blackjack --to-revision=<N>
```

---

## Troubleshooting

### GH Actions: `Not authorized to perform sts:AssumeRoleWithWebIdentity`

The runner can't assume the deploy role. Common causes:

- The IAM role doesn't exist yet
- The trust policy `sub` condition doesn't match the OIDC token (e.g. wrong repo slug or branch)
- The GitHub OIDC provider isn't registered in IAM

```bash
# Confirm the role exists and inspect the trust policy sub condition
aws iam get-role \
  --role-name blackjackpy-trainer-github-deploy \
  --query 'Role.AssumeRolePolicyDocument' \
  --output json
```

Add a debug step to the workflow to print the actual `sub` claim from the OIDC token if the
values don't match.

---

### GH Actions `kubectl` unauthorized

The deploy role assumed successfully but Kubernetes doesn't recognize it.
This means the `iamidentitymapping` from Step 8 is missing or was applied to the wrong cluster.

```bash
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

eksctl create iamidentitymapping \
  --cluster eks-proto \
  --region us-east-2 \
  --arn arn:aws:iam::${ACCOUNT_ID}:role/blackjackpy-trainer-github-deploy \
  --username github-deploy \
  --group system:masters
```

---

### Ingress stuck — no ADDRESS after 3+ minutes

The AWS Load Balancer Controller isn't running or can't create the ALB.

```bash
# Check controller pod status and stream logs
kubectl get pods -n kube-system \
  -l app.kubernetes.io/name=aws-load-balancer-controller

kubectl logs -n kube-system \
  -l app.kubernetes.io/name=aws-load-balancer-controller \
  --tail=30

# Verify Pod Identity association for the controller
aws eks list-pod-identity-associations --cluster-name eks-proto --region us-east-2
```

---

### WebSocket disconnects immediately

The `WS_ALLOWED_ORIGINS` env var doesn't match the actual ALB hostname. The value must include
the `http://` prefix and match exactly.

```bash
# Check the current value and compare with the actual ALB hostname
kubectl get deployment blackjack-trainer -n blackjack \
  -o jsonpath='{.spec.template.spec.containers[0].env}'

kubectl get ingress blackjack-trainer -n blackjack \
  -o jsonpath='{.status.loadBalancer.ingress[0].hostname}'
```

---

### Pods in `CrashLoopBackOff`

```bash
kubectl logs -n blackjack -l app=blackjack-trainer --previous
```

---

### ECR image pull error

Verify the image URI in `deployment.yaml` matches the ECR repository URI exactly. Node group
IAM has ECR read access by default via the EKS Terraform module.

```bash
kubectl describe pod -n blackjack -l app=blackjack-trainer | grep -A10 Events
```
