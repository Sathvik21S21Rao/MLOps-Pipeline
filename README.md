# MLOps Email Classification Pipeline

End-to-end MLOps pipeline for training, deploying, and monitoring email classification models on Kubernetes with automated drift detection and retraining.

## Project Overview

This project implements a complete MLOps workflow for email classification with:
- **Automated data loading** from HuggingFace datasets
- **Multi-model training** (SGD, Logistic Regression, Random Forest)
- **Intelligent model selection** - automatically deploys the best-performing model based on F1/accuracy metrics stored in Elasticsearch
- **FastAPI inference service** with autoscaling (HPA)
- **ELK stack** (Elasticsearch, Logstash, Kibana) for centralized logging and metrics
- **Drift monitoring** - detects classification skewness and triggers Jenkins pipeline for retraining
- **CI/CD** with Jenkins and Ansible

##  Architecture

```
┌─────────────────┐     ┌─────────────────┐
│  DataLoader     │────►│  Elasticsearch  │◄────┐
│  (Job)          │     │  + Logstash     │     │
└─────────────────┘     │  + Kibana       │     │
                        └─────────────────┘     │
                                                 │
┌─────────────────┐                              │ Training
│  ModelTrainer   │──────────────────────────────┤ Metrics
│  (Deployment)   │                              │
│  - sgd          │                              │
│  - log          │                              │
└─────────────────┘                              │
                                                 │
┌─────────────────┐     ┌─────────────────┐    │
│  Model          │────►│  Drift Monitor  │────┤
│  Inference      │     │  (watches logs) │    │
│  (FastAPI+HPA)  │     └─────────────────┘    │
└─────────────────┘              │              │
                                 │              │
                                 ▼              │
                        ┌─────────────────┐    │
                        │  Jenkins        │────┘
                        │  (rebuilds)     │
                        └─────────────────┘
```

## Prerequisites

- **Kubernetes cluster** (Minikube, Kind, or cloud K8s)
- **Docker** for building images
- **Ansible** >= 2.10 with `kubernetes` Python module
- **Python** 3.9+ (for local dev/testing)
- **kubectl** configured to access your cluster
- **Jenkins** (optional, for CI/CD and drift retraining)

## Quick Start

### 1. Clone and Setup

```bash
git clone https://github.com/Sathvik21S21Rao/MLOps-Pipeline.git
cd MLOps-Pipeline

python -m venv .venv
source .venv/bin/activate  


# Install Ansible dependencies
pip install ansible kubernetes openshift pyyaml requests
```

### 2. Configure Secrets

```bash
ansible-vault edit ansible/group_vars/all/vault.yml

# Add:
hf_api_token: "hf_your_token_here"
jenkins_token: "your_jenkins_api_token"  # Optional, for drift monitor
```

### 3. Configure Variables

Edit `ansible/group_vars/all/vars.yml`:

```yaml
k8s_namespace: default  # or ml-pipeline
models:
  - sgd
  - log
elasticsearch_url: "http://elasticsearch:9200"
```

### 4. Start Kubernetes Cluster

```bash
# Using Minikube
minikube start --driver=docker --memory=4096 --cpus=2

# Verify
kubectl get nodes
```

### 5. Deploy Pipeline

```bash
cd ansible

# Deploy full pipeline (ELK, DataLoader, ModelTrainer, Inference, DriftMonitor)
ansible-playbook playbooks/deploy_pipeline.yml \
  -i inventory.ini \
  --vault-password-file ~/.vault_pass \
  -e "k8s_namespace=default"
```

### 6. Monitor Deployment

```bash
# Watch pods starting
kubectl get pods -n default -w

# Check logs
kubectl logs -f job/dataloader -n default
kubectl logs -f deployment/modeltrainer-sgd -n default
kubectl logs -f deployment/inference-deployment-sgd -n default
```

## Usage

### Access Inference Service

```bash
kubectl port-forward svc/model-inference-service 8000:80 -n default

# Test prediction
curl -X POST http://127.0.0.1:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"email_text":"FLASH SALE: 50% OFF Everything! Shop now!"}'

# Response:
# {
#   "predicted_label": 2,
#   "input_length": 45,
#   "model_used": "log",
#   "label": "Promotions"
# }
```

### Access Kibana Dashboard

```bash
# Port-forward Kibana
kubectl port-forward svc/kibana 5601:5601 -n default

# Open browser
http://localhost:5601

# Create index pattern: logstash-*
# View training_metrics and inference_event logs
```

### View Training Metrics

```bash
# Query Elasticsearch directly
kubectl port-forward svc/elasticsearch 9200:9200 -n default

curl http://localhost:9200/logstash-*/_search?pretty \
  -H "Content-Type: application/json" \
  -d '{
    "query": {"term": {"log_type.keyword": "training_metrics"}},
    "size": 5,
    "sort": [{"timestamp": "desc"}]
  }'
```

## Model Selection

The inference service automatically selects the **best model** at startup:

1. Queries Elasticsearch for `training_metrics` logs
2. Compares models by F1 score (primary), then accuracy
3. Loads the winning model from shared storage
4. Falls back to `MODEL_NAME` env var if no metrics found

**Environment variables for inference:**
- `ELASTICSEARCH_URL`: http://elasticsearch:9200
- `ELASTICSEARCH_USER`: (optional, if auth enabled)
- `ELASTICSEARCH_PASSWORD`: (optional)
- `MODEL_NAME`: Default model name (fallback)

## Drift Monitoring

The drift monitor watches inference predictions and triggers retraining when class distribution is skewed:

```bash
# Check drift monitor logs
kubectl logs -f deployment/drift-monitor -n default

# Example output:
# Retrieved 150 predictions from last 15 minutes
# Class distribution: {1: 0.12, 2: 0.76, 3: 0.08, 4: 0.04}
#  DRIFT DETECTED: Class 2 accounts for 76.0% (threshold: 70%)
# Jenkins pipeline triggered successfully
```

**Configuration** (`ansible/group_vars/all/vars.yml`):
- `drift_check_interval`: "300" (5 minutes)
- `drift_lookback_minutes`: "15"
- `drift_skewness_threshold`: "0.7" (70%)
- `drift_min_samples`: "50"

## CI/CD with Jenkins

### Setup Jenkins Pipeline

1. Install Jenkins plugins: Docker, Ansible, Git
2. Create pipeline job pointing to `Jenkinsfile`
3. Add credentials:
   - `dockerhub-creds` (Docker Hub username/password)
   - `ansible-vault-pass` (Ansible vault password)


### Jenkinsfile Stages

1. Checkout code
2. Build & push Docker images (DataLoader, ModelTrainer, ModelInference, DriftMonitor)
3. Deploy to Kubernetes via Ansible

## Project Structure

```
MLOps-Pipeline/
├── ansible/
│   ├── inventory.ini
│   ├── group_vars/all/
│   │   ├── vars.yml           # Configuration
│   │   └── vault.yml          # Encrypted secrets
│   ├── playbooks/
│   │   └── deploy_pipeline.yml
│   ├── roles/
│   │   ├── elk/               # Elasticsearch, Logstash, Kibana
│   │   ├── dataloader/        # Data loading job
│   │   ├── modeltrainer/      # Training deployments
│   │   ├── modelinference/    # Inference + HPA
│   │   └── driftmonitor/      # Drift detection
│   └── scripts/
│       └── select_best_model.py  # (legacy, now in inference)
├── DataLoading/
│   ├── data_loading.py
│   ├── Dockerfile
│   └── requirements.txt
├── ModelTraining/
│   ├── model_training.py      # TF-IDF + SGD/Logistic/RandomForest
│   ├── Dockerfile
│   └── requirements.txt
├── ModelInference/
│   ├── model_inference.py     # FastAPI service with ES model selection
│   ├── Dockerfile
│   └── requirements.txt
├── DriftMonitor/
│   ├── drift_monitor.py
│   ├── Dockerfile
│   └── requirements.txt
└── Jenkinsfile
```

## Label Categories

| ID | Category     | Description                          |
|----|--------------|--------------------------------------|
| 1  | Social Media | Notifications from social platforms  |
| 2  | Promotions   | Marketing and sales emails           |
| 3  | Forum        | Discussion forums and threads        |
| 4  | Spam         | Unwanted or suspicious emails        |
| 5  | Verify Code  | Authentication codes and OTPs        |
| 6  | Updates      | Order updates and notifications      |


## Troubleshooting

### Pods not starting

```bash
kubectl describe pod <pod-name> -n default
kubectl logs <pod-name> -n default
```

### Model not found

- Check modeltrainer completed: `kubectl logs deployment/modeltrainer-sgd -n default`
- Verify PVC mounted: `kubectl get pvc -n default`
- Check model saved: `kubectl exec deployment/modeltrainer-sgd -- ls /model`

### Elasticsearch connection failed

```bash
# Port-forward and test
kubectl port-forward svc/elasticsearch 9200:9200 -n default
curl http://localhost:9200/_cluster/health
```

### Inference always uses default model

- Check `ELASTICSEARCH_URL` env in inference pod
- Verify training metrics indexed: query Kibana or ES directly
- Check inference logs for ES query errors

### Drift monitor not triggering

- Verify Jenkins URL/token in `vars.yml`
- Check monitor logs: `kubectl logs deployment/drift-monitor -n default`
- Test manual trigger: `curl -X POST http://jenkins:8080/job/MLOps-Pipeline/build --user admin:token`

## Monitoring & Observability

**Kibana Dashboards:**
1. Create index pattern: `logstash-*`
2. Visualize:
   - Training metrics (accuracy, F1) per model over time
   - Inference predictions per label
   - Drift detection events
   - Error rates

**Prometheus/Grafana (optional):**
- HPA metrics (CPU, memory)
- Inference latency
- Request rates

## Updating the Pipeline

### Add a new model

1. Edit `ansible/group_vars/all/vars.yml`:
   ```yaml
   models:
     - sgd
     - log
     - rf  # Add new
   ```

2. Update `ModelTraining/model_training.py` classifier selection if needed

3. Redeploy:
   ```bash
   ansible-playbook playbooks/deploy_pipeline.yml -i inventory.ini --vault-password-file ~/.vault_pass
   ```

### Update Docker images

```bash
# Build and push
cd ModelInference
docker build -t yourusername/model-inference:latest .
docker push yourusername/model-inference:latest

# Update vars.yml
modelinference_image: "yourusername/model-inference:latest"

# Redeploy
kubectl rollout restart deployment/inference-deployment-sgd -n default
```