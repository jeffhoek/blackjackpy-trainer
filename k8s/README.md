# blackjackpy-trainer — EKS Deployment Runbook

Deploys the blackjackpy-trainer FastAPI + WebSocket app to the `eks-proto` cluster
in `us-east-2` using Amazon ECR for images and an AWS Application Load Balancer for
ingress. WebSocket sticky sessions are enabled on the ALB so each browser stays on
the same pod.

## Files in this directory

| File | Purpose |
|---|---|
| `namespace.yaml` | `blackjack` namespace |
| `deployment.yaml` | 2-replica Deployment — update `ACCOUNT_ID` before first apply |
| `service.yaml` | ClusterIP, port 80 → 8080 |
| `ingress.yaml` | ALB ingress, sticky sessions, 600s idle timeout |

CI/CD workflow: `../.github/workflows/deploy.yml` (triggers on push to `main`, also manually dispatchable)

---

> **Two OIDC providers, two purposes — don't confuse them:**
> - **GitHub OIDC** (`token.actions.githubusercontent.com`) — lets GitHub Actions runners assume AWS IAM roles. Set up once per AWS account.
> - **EKS OIDC** (per-cluster URL) — lets Kubernetes pods assume AWS IAM roles via IRSA. Requires a live cluster.

---

## Phase 1 — Before provisioning the cluster

Everything in this phase can be completed with only the AWS CLI, Docker, and git.
No active EKS cluster is required.

### 1. Verify prerequisites

```bash
aws sts get-caller-identity   # AWS CLI configured and credentialed
docker version                # Docker running locally
helm version                  # helm ≥ 3.x
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
ECR image build and push, then **fail** at the `aws eks update-kubeconfig` step
because the cluster doesn't exist yet — that's expected. Confirm the image landed
in ECR:

```bash
aws ecr describe-images --repository-name blackjackpy-trainer --region us-east-2
```

---

## Phase 2 — After the cluster is provisioned

Everything below requires `eks-proto` to be running.

### 6. Connect kubectl to the cluster

```bash
aws eks update-kubeconfig --name eks-proto --region us-east-2
kubectl get nodes   # should list cluster nodes
```

### 7. Install the AWS Load Balancer Controller

The ALB Ingress controller watches for `Ingress` resources and provisions AWS
Application Load Balancers. It uses IRSA (IAM Roles for Service Accounts), which
requires the **EKS cluster's own OIDC provider** registered in IAM — separate from
the GitHub one in step 3a.

#### Check if already installed

```bash
kubectl get pods -n kube-system -l app.kubernetes.io/name=aws-load-balancer-controller
helm list -n kube-system | grep aws-load-balancer-controller
```

If either shows a running pod or installed release → skip to [Step 8](#8-grant-the-github-actions-role-kubectl-access).

#### 7a. Register the EKS cluster OIDC provider in IAM

Check first (each cluster has a unique OIDC ID):
```bash
OIDC_ID=$(aws eks describe-cluster --name eks-proto --region us-east-2 \
  --query "cluster.identity.oidc.issuer" --output text | cut -d'/' -f5)
aws iam list-open-id-connect-providers | grep $OIDC_ID
```

If missing, register it. With `eksctl` (easiest):
```bash
eksctl utils associate-iam-oidc-provider \
  --cluster eks-proto --region us-east-2 --approve
```

Without `eksctl`:
```bash
OIDC_URL=$(aws eks describe-cluster --name eks-proto --region us-east-2 \
  --query "cluster.identity.oidc.issuer" --output text)
THUMBPRINT=$(openssl s_client -connect oidc.eks.us-east-2.amazonaws.com:443 \
  -showcerts </dev/null 2>/dev/null \
  | openssl x509 -fingerprint -sha1 -noout \
  | sed 's/://g' | cut -d= -f2 | tr '[:upper:]' '[:lower:]')
aws iam create-open-id-connect-provider \
  --url $OIDC_URL \
  --client-id-list sts.amazonaws.com \
  --thumbprint-list $THUMBPRINT
```

#### 7b. Create the LBC IAM policy

```bash
curl -O https://raw.githubusercontent.com/kubernetes-sigs/aws-load-balancer-controller/v2.8.2/docs/install/iam_policy.json
aws iam create-policy \
  --policy-name AWSLoadBalancerControllerIAMPolicy \
  --policy-document file://iam_policy.json
```

#### 7c. Create the LBC IRSA role

```bash
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
OIDC_ISSUER=$(aws eks describe-cluster --name eks-proto --region us-east-2 \
  --query "cluster.identity.oidc.issuer" --output text | sed 's|https://||')

cat > lbc-trust-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": { "Federated": "arn:aws:iam::${AWS_ACCOUNT_ID}:oidc-provider/${OIDC_ISSUER}" },
    "Action": "sts:AssumeRoleWithWebIdentity",
    "Condition": {
      "StringEquals": {
        "${OIDC_ISSUER}:sub": "system:serviceaccount:kube-system:aws-load-balancer-controller",
        "${OIDC_ISSUER}:aud": "sts.amazonaws.com"
      }
    }
  }]
}
EOF

aws iam create-role \
  --role-name eks-proto-aws-load-balancer-controller \
  --assume-role-policy-document file://lbc-trust-policy.json

aws iam attach-role-policy \
  --role-name eks-proto-aws-load-balancer-controller \
  --policy-arn arn:aws:iam::${AWS_ACCOUNT_ID}:policy/AWSLoadBalancerControllerIAMPolicy
```

#### 7d. Install via Helm

```bash
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
VPC_ID=$(aws eks describe-cluster --name eks-proto --region us-east-2 \
  --query "cluster.resourcesVpcConfig.vpcId" --output text)

helm repo add eks https://aws.github.io/eks-charts && helm repo update

helm install aws-load-balancer-controller eks/aws-load-balancer-controller \
  -n kube-system \
  --set clusterName=eks-proto \
  --set serviceAccount.create=true \
  --set "serviceAccount.annotations.eks\.amazonaws\.com/role-arn=arn:aws:iam::${AWS_ACCOUNT_ID}:role/eks-proto-aws-load-balancer-controller" \
  --set region=us-east-2 \
  --set vpcId=${VPC_ID}
```

#### 7e. Verify it's healthy

```bash
kubectl get deployment -n kube-system aws-load-balancer-controller
# Expected: READY 2/2

kubectl logs -n kube-system \
  -l app.kubernetes.io/name=aws-load-balancer-controller --tail=20
# Should show no errors
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
| Ingress stuck, no ADDRESS after 3+ min | LBC not running or its IRSA role misconfigured | `kubectl get pods -n kube-system -l app.kubernetes.io/name=aws-load-balancer-controller` then check logs |
| GH Actions `kubectl` unauthorized | Deploy role not added to aws-auth / access entries | Re-run `eksctl create iamidentitymapping` from step 8 |
| WebSocket disconnects immediately | `WS_ALLOWED_ORIGINS` mismatch | Verify the env var matches the exact ALB hostname including `http://` prefix |
| Pods in `CrashLoopBackOff` | App startup failure | `kubectl logs -n blackjack <pod-name>` |
| ECR image pull error | Wrong image URI or node role lacks ECR read access | Check image field in `deployment.yaml`; verify node group IAM role has `AmazonEC2ContainerRegistryReadOnly` |
