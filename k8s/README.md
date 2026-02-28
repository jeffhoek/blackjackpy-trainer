# blackjackpy-trainer — EKS Deployment Runbook

Deploys the blackjackpy-trainer FastAPI + WebSocket app to the `eks-proto` cluster
in `us-east-2` using Amazon ECR for images and an AWS Application Load Balancer for
ingress. WebSocket sticky sessions are enabled on the ALB so each browser stays on
the same pod.

## Files in this directory

| File | Purpose |
|---|---|
| `namespace.yaml` | `blackjack` namespace |
| `deployment.yaml` | 2-replica Deployment |
| `service.yaml` | ClusterIP, port 80 → 8080 |
| `ingress.yaml` | ALB ingress, sticky sessions, 600s idle timeout |

CI/CD workflow: `../.github/workflows/deploy.yml` (triggers on push to `main`, also manually dispatchable)

---

> **Note on OIDC:**
> **GitHub OIDC** (`token.actions.githubusercontent.com`) lets GitHub Actions runners assume AWS IAM
> roles without long-lived keys. This is the only OIDC provider you need to manage manually.
> The AWS Load Balancer Controller uses **EKS Pod Identity** (not IRSA) — provisioned automatically
> by the cluster Terraform (`eks-proto`).

---

## Phase 1 — Before provisioning the cluster

Everything in this phase can be completed with only the AWS CLI, Docker, and git.
No active EKS cluster is required.

### 1. Verify prerequisites

```bash
aws sts get-caller-identity   # AWS CLI configured and credentialed
docker version                # Docker running locally
```

### 2. Create ECR repository

```bash
aws ecr create-repository \
  --repository-name blackjackpy-trainer \
  --region us-east-2 \
  --image-scanning-configuration scanOnPush=true
# Note the repositoryUri in the output — you'll need it in step 4
# e.g. 123456789012.dkr.ecr.us-east-2.amazonaws.com/blackjackpy-trainer
```

Verify it exists any time:
```bash
aws ecr describe-repositories --repository-names blackjackpy-trainer --region us-east-2
```

### 3. Set up GitHub Actions OIDC in AWS IAM

This lets the GitHub Actions runner assume an AWS role without long-lived access keys.

#### 3a. Register the GitHub OIDC provider (one-time per AWS account)

Check first — it only needs to exist once regardless of how many repos use it:
```bash
aws iam list-open-id-connect-providers | grep token.actions.githubusercontent.com
```

If nothing is returned, create it:
```bash
aws iam create-open-id-connect-provider \
  --url https://token.actions.githubusercontent.com \
  --client-id-list sts.amazonaws.com \
  --thumbprint-list 6938fd4d98bab03faadb97b34396831e3780aea1
```

#### 3b. Create the deploy IAM role

```bash
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
```
```
cat > gh-deploy-trust-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {
      "Federated": "arn:aws:iam::${AWS_ACCOUNT_ID}:oidc-provider/token.actions.githubusercontent.com"
    },
    "Action": "sts:AssumeRoleWithWebIdentity",
    "Condition": {
      "StringEquals": { "token.actions.githubusercontent.com:aud": "sts.amazonaws.com" },
      "StringLike": {
        "token.actions.githubusercontent.com:sub": "repo:jeffhoek/blackjackpy-trainer:ref:refs/heads/main"
      }
    }
  }]
}
EOF
```

```
aws iam create-role \
  --role-name blackjackpy-trainer-github-deploy \
  --assume-role-policy-document file://gh-deploy-trust-policy.json
```

```
# ECR push access
aws iam attach-role-policy \
  --role-name blackjackpy-trainer-github-deploy \
  --policy-arn arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryPowerUser
```

```
# EKS describe (needed so the runner can call aws eks update-kubeconfig)
aws iam put-role-policy \
  --role-name blackjackpy-trainer-github-deploy \
  --policy-name eks-access \
  --policy-document '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Action":["eks:DescribeCluster"],"Resource":"*"}]}'
```

Verify the role and its trust policy:
```bash
aws iam get-role --role-name blackjackpy-trainer-github-deploy \
  --query 'Role.AssumeRolePolicyDocument' --output json
```

#### 3c. Add the GitHub secret

In your repo: **Settings → Secrets and variables → Actions → New repository secret**

| Secret name | Value |
|---|---|
| `AWS_DEPLOY_ROLE_ARN` | `arn:aws:iam::<ACCOUNT_ID>:role/blackjackpy-trainer-github-deploy` |

### 4. Update deployment.yaml with your ECR account ID

```bash
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
sed -i '' "s|ACCOUNT_ID|${AWS_ACCOUNT_ID}|" deployment.yaml
```

```
# Confirm the placeholder is gone
grep "image:" deployment.yaml
# Expected: image: 123456789012.dkr.ecr.us-east-2.amazonaws.com/blackjackpy-trainer:latest
```

### 5. Commit, push, and merge to main

```bash
git add ../k8s/ ../.github/workflows/deploy.yml
git commit -m "Add EKS deployment manifests and CI/CD workflow"
git push origin <your-branch>
# Open a PR and merge to main
```

The GitHub Actions workflow will trigger on merge. It will **succeed** through the
ECR image build and push, then **skip** the kubectl steps because the cluster doesn't
exist yet — that's expected. Confirm the image landed in ECR:

```bash
aws ecr describe-images --repository-name blackjackpy-trainer --region us-east-2
```

---

## Phase 2 — After the cluster is provisioned

Everything below requires `eks-proto` to be running. The AWS Load Balancer Controller
is provisioned automatically by the cluster Terraform (`lbc.tf` in `eks-proto`) —
no manual Helm installation needed.

### 6. Connect kubectl to the cluster

```bash
aws eks update-kubeconfig --name eks-proto --region us-east-2
kubectl get nodes   # should list cluster nodes
```

### 7. Verify the AWS Load Balancer Controller is healthy

```bash
kubectl get deployment -n kube-system aws-load-balancer-controller
# Expected: READY 2/2
```

If not ready, check logs before proceeding — the ingress won't get an ALB until it is:
```bash
kubectl logs -n kube-system \
  -l app.kubernetes.io/name=aws-load-balancer-controller --tail=20
```

### 8. Grant the GitHub Actions role kubectl access

This allows the GitHub Actions runner to run `kubectl` commands against the cluster.

With `eksctl` (recommended):
```bash
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
eksctl create iamidentitymapping \
  --cluster eks-proto \
  --region us-east-2 \
  --arn arn:aws:iam::${AWS_ACCOUNT_ID}:role/blackjackpy-trainer-github-deploy \
  --username github-deploy \
  --group system:masters
```

Without `eksctl`, edit the aws-auth ConfigMap directly (careful — malformed YAML breaks cluster auth):
```bash
kubectl edit configmap aws-auth -n kube-system
# Add under mapRoles:
#   - rolearn: arn:aws:iam::<ACCOUNT_ID>:role/blackjackpy-trainer-github-deploy
#     username: github-deploy
#     groups:
#       - system:masters
```

### 9. Trigger the full deploy

Push a commit to `main` or dispatch the workflow manually from the GitHub Actions UI.
The full pipeline — build → push → `kubectl apply` → rolling update — should now
complete without errors.

### 10. Lock WebSocket origins

Once the ALB is provisioned (takes ~60s after first `kubectl apply`), restrict
WebSocket connections to the known hostname:

```bash
ALB_HOST=$(kubectl get ingress blackjack-trainer -n blackjack \
  -o jsonpath='{.status.loadBalancer.ingress[0].hostname}')
echo "ALB hostname: $ALB_HOST"

kubectl set env deployment/blackjack-trainer -n blackjack \
  WS_ALLOWED_ORIGINS="http://${ALB_HOST}"
```

Then persist it in `deployment.yaml` by uncommenting and filling in the
`WS_ALLOWED_ORIGINS` env var so future `kubectl apply` runs don't revert it.

---

## Verification

```bash
# Pods running
kubectl get pods -n blackjack

# ALB hostname assigned (ADDRESS column — takes ~60s to populate)
kubectl get ingress -n blackjack

# Get the URL and open it
kubectl get ingress blackjack-trainer -n blackjack \
  -o jsonpath='{.status.loadBalancer.ingress[0].hostname}'
# Open http://<hostname> — the xterm.js terminal should load and be playable

# WebSocket: DevTools → Network → WS tab → /ws connection stays open
```

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| GH Actions: `Not authorized to perform sts:AssumeRoleWithWebIdentity` | Role missing, trust policy sub mismatch, or GitHub OIDC provider not registered | Check role exists: `aws iam get-role --role-name blackjackpy-trainer-github-deploy`. Verify trust policy `sub` matches the OIDC token (add the debug step from the workflow to print it) |
| Ingress stuck, no ADDRESS after 3+ min | LBC not running or its Pod Identity association misconfigured | `kubectl get pods -n kube-system -l app.kubernetes.io/name=aws-load-balancer-controller` then check logs; verify Pod Identity association with `aws eks list-pod-identity-associations --cluster-name eks-proto` |
| GH Actions `kubectl` unauthorized | Deploy role not added to aws-auth / access entries | Re-run `eksctl create iamidentitymapping` from step 8 |
| WebSocket disconnects immediately | `WS_ALLOWED_ORIGINS` mismatch | Verify the env var matches the exact ALB hostname including `http://` prefix |
| Pods in `CrashLoopBackOff` | App startup failure | `kubectl logs -n blackjack <pod-name>` |
| ECR image pull error | Wrong image URI | Check image field in `deployment.yaml`; node group IAM has ECR read access by default via the EKS module |
