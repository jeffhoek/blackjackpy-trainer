# blackjackpy-trainer — EKS Deployment

Deploys the blackjackpy-trainer FastAPI + WebSocket app to the `eks-proto` cluster
in `us-east-2` using Amazon ECR for images and an AWS Application Load Balancer for ingress.
WebSocket sticky sessions are enabled on the ALB so each browser stays on the same pod.

## Files in this directory

| File | Purpose |
|---|---|
| `namespace.yaml` | `blackjack` namespace |
| `deployment.yaml` | 2-replica Deployment — update `ACCOUNT_ID` before first apply |
| `service.yaml` | ClusterIP, port 80 → 8080 |
| `ingress.yaml` | ALB ingress, sticky sessions, 600s idle timeout |

CI/CD workflow: `../.github/workflows/deploy.yml` (triggers on push to `main`)

---

## 1. Prerequisites Checklist

Work through each item and run its verification command before deploying.

**AWS CLI configured**
```bash
aws sts get-caller-identity   # should return your account ID
```

**kubectl pointed at eks-proto**
```bash
aws eks update-kubeconfig --name eks-proto --region us-east-2
kubectl get nodes             # should list cluster nodes
```

**helm ≥ 3.x installed**
```bash
helm version
```

**ECR repository exists** (see [Step 2](#2-create-ecr-repository))
```bash
aws ecr describe-repositories --repository-names blackjackpy-trainer --region us-east-2
```

**OIDC provider registered in IAM** (see [Step 3](#3-install-aws-load-balancer-controller))
```bash
OIDC_ID=$(aws eks describe-cluster --name eks-proto --region us-east-2 \
  --query "cluster.identity.oidc.issuer" --output text | cut -d'/' -f5)
aws iam list-open-id-connect-providers | grep $OIDC_ID
```

**AWS Load Balancer Controller installed** (see [Step 3](#3-install-aws-load-balancer-controller))
```bash
kubectl get pods -n kube-system -l app.kubernetes.io/name=aws-load-balancer-controller
# Expected: 2 pods in Running state
```

**`deployment.yaml` image updated** — replace `ACCOUNT_ID` with your real account ID:
```bash
grep "ACCOUNT_ID" deployment.yaml   # should return nothing if already updated
```

---

## 2. Create ECR Repository

One-time setup. Skip if the repository already exists.

```bash
aws ecr create-repository \
  --repository-name blackjackpy-trainer \
  --region us-east-2 \
  --image-scanning-configuration scanOnPush=true
# Note the repositoryUri in the output:
# e.g. 123456789012.dkr.ecr.us-east-2.amazonaws.com/blackjackpy-trainer
```

---

## 3. Install AWS Load Balancer Controller

### Check if already installed

```bash
kubectl get pods -n kube-system -l app.kubernetes.io/name=aws-load-balancer-controller
```
```
helm list -n kube-system | grep aws-load-balancer-controller
```

If either command shows a running pod or installed release → skip to [Step 4](#4-first-deploy).

### 3a. Register the cluster OIDC provider in IAM

The EKS cluster has an OIDC issuer URL, but it must also be registered as an IAM
Identity Provider before IAM Roles for Service Accounts (IRSA) work.

Check:
```bash
OIDC_ID=$(aws eks describe-cluster --name eks-proto --region us-east-2 \
  --query "cluster.identity.oidc.issuer" --output text | cut -d'/' -f5)
aws iam list-open-id-connect-providers | grep $OIDC_ID
```

If nothing is returned, register it. With `eksctl` (easiest):
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

### 3b. Create the LBC IAM policy

```bash
curl -O https://raw.githubusercontent.com/kubernetes-sigs/aws-load-balancer-controller/v2.8.2/docs/install/iam_policy.json
aws iam create-policy \
  --policy-name AWSLoadBalancerControllerIAMPolicy \
  --policy-document file://iam_policy.json
```

### 3c. Create the IRSA role

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

### 3d. Install via Helm

```bash
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

### 3e. Verify it's healthy

```bash
kubectl get deployment -n kube-system aws-load-balancer-controller
# Expected: READY 2/2

kubectl logs -n kube-system \
  -l app.kubernetes.io/name=aws-load-balancer-controller --tail=20
# Should show "Starting" with no errors
```

---

## 4. First Deploy

Update `deployment.yaml` with your real ECR account ID and push the initial image:

```bash
# Set your account ID
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_URI=${AWS_ACCOUNT_ID}.dkr.ecr.us-east-2.amazonaws.com/blackjackpy-trainer

# Authenticate Docker to ECR
aws ecr get-login-password --region us-east-2 \
  | docker login --username AWS --password-stdin ${ECR_URI}

# Build and push
docker build -t ${ECR_URI}:latest ..
docker push ${ECR_URI}:latest

# Patch the placeholder in deployment.yaml
sed -i "s|ACCOUNT_ID|${AWS_ACCOUNT_ID}|" deployment.yaml

# Apply all manifests
kubectl apply -f .
```

Watch the rollout:
```bash
kubectl rollout status deployment/blackjack-trainer -n blackjack
kubectl get pods -n blackjack
```

---

## 5. CI/CD Setup (GitHub Actions + OIDC)

The workflow in `.github/workflows/deploy.yml` uses GitHub's OIDC token to assume
an AWS role — no long-lived access keys needed.

### 5a. Register GitHub OIDC provider in IAM (one-time)

Check if it already exists:
```bash
aws iam list-open-id-connect-providers | grep token.actions.githubusercontent.com
```

If missing:
```bash
aws iam create-open-id-connect-provider \
  --url https://token.actions.githubusercontent.com \
  --client-id-list sts.amazonaws.com \
  --thumbprint-list 6938fd4d98bab03faadb97b34396831e3780aea1
```

### 5b. Create the deploy IAM role

```bash
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

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

aws iam create-role \
  --role-name blackjackpy-trainer-github-deploy \
  --assume-role-policy-document file://gh-deploy-trust-policy.json

# ECR push access
aws iam attach-role-policy \
  --role-name blackjackpy-trainer-github-deploy \
  --policy-arn arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryPowerUser

# EKS describe (needed for aws eks update-kubeconfig)
aws iam put-role-policy \
  --role-name blackjackpy-trainer-github-deploy \
  --policy-name eks-access \
  --policy-document '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Action":["eks:DescribeCluster"],"Resource":"*"}]}'
```

### 5c. Grant the role kubectl access

With `eksctl` (recommended — avoids editing aws-auth manually):
```bash
eksctl create iamidentitymapping \
  --cluster eks-proto \
  --region us-east-2 \
  --arn arn:aws:iam::${AWS_ACCOUNT_ID}:role/blackjackpy-trainer-github-deploy \
  --username github-deploy \
  --group system:masters
```

Without `eksctl`, patch the ConfigMap directly:
```bash
kubectl patch configmap/aws-auth -n kube-system --type merge \
  -p "{\"data\":{\"mapRoles\":\"$(kubectl get configmap aws-auth -n kube-system \
    -o jsonpath='{.data.mapRoles}')- rolearn: arn:aws:iam::${AWS_ACCOUNT_ID}:role/blackjackpy-trainer-github-deploy\n  username: github-deploy\n  groups:\n  - system:masters\n\"}}"
```
> Prefer `eksctl` — the manual patch is brittle if mapRoles already has content.

### 5d. Add GitHub secret

In your repo: **Settings → Secrets and variables → Actions → New repository secret**

| Secret name | Value |
|---|---|
| `AWS_DEPLOY_ROLE_ARN` | `arn:aws:iam::<ACCOUNT_ID>:role/blackjackpy-trainer-github-deploy` |

---

## 6. Post-Deploy: Lock WebSocket Origins

After the ALB is provisioned, restrict WebSocket connections to the known hostname:

```bash
ALB_HOST=$(kubectl get ingress blackjack-trainer -n blackjack \
  -o jsonpath='{.status.loadBalancer.ingress[0].hostname}')
echo "ALB: $ALB_HOST"

kubectl set env deployment/blackjack-trainer -n blackjack \
  WS_ALLOWED_ORIGINS="http://${ALB_HOST}"
```

Then update the `WS_ALLOWED_ORIGINS` env var in `deployment.yaml` to persist it
across future `kubectl apply` runs.

---

## 7. Verification

```bash
# 1. Pods healthy
kubectl get pods -n blackjack

# 2. ALB provisioned (ADDRESS column populated — takes ~60s)
kubectl get ingress -n blackjack

# 3. Smoke test — get the URL
kubectl get ingress blackjack-trainer -n blackjack \
  -o jsonpath='{.status.loadBalancer.ingress[0].hostname}'
# Open http://<hostname> in a browser — xterm.js terminal should load

# 4. WebSocket: open browser DevTools → Network → WS tab
#    The /ws connection should appear and stay open

# 5. CI/CD: push a commit to main → Actions tab in GitHub → deploy job passes
```

---

## 8. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Ingress stuck, no ADDRESS | LBC not running or IRSA role misconfigured | Check `kubectl get pods -n kube-system -l app.kubernetes.io/name=aws-load-balancer-controller` and review LBC logs |
| WebSocket disconnects at open | `WS_ALLOWED_ORIGINS` mismatch | Verify the env var matches the exact ALB hostname (including protocol) |
| Pods in `CrashLoopBackOff` | App startup failure | `kubectl logs -n blackjack <pod-name>` |
| ECR image pull error | Wrong image URI or missing ECR permissions | Verify the image field in deployment.yaml and that the node IAM role has ECR read access |
| GitHub Actions `kubectl` unauthorized | Role not in aws-auth / access entries | Re-run the `eksctl create iamidentitymapping` command in Step 5c |
