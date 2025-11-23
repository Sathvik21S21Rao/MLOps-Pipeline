Quick guide: ELK + Ansible + Kubernetes for trainer metrics

Overview
- The trainer now emits JSON lines (one per metrics payload) to stdout. These JSON lines include `log_type: training_metrics` so Logstash can filter them.
- This repo includes a `logstash.conf` and a Kubernetes `ConfigMap` + `Deployment` to run Logstash in-cluster.
- An Ansible playbook (`ansible/playbooks/deploy_models.yml`) will render per-model env files under `./deploy/envs/*.env` from `ansible/templates/env.j2`.

Run locally with Docker Logstash (quick)

1. Start Logstash (bind logstash.conf into container):

docker run --rm -p 5000:5000 -v ${PWD}/logstash.conf:/usr/share/logstash/pipeline/logstash.conf docker.elastic.co/logstash/logstash:8.10.0

2. Build trainer image (if you use Docker):

docker build -t my-trainer:latest .

3. Run trainer container and point to Logstash container name/host (if docker network) or localhost:5000:

docker run --rm --env-file ./deploy/envs/modelA.env -e LOGSTASH_HOST=host.docker.internal -e LOGSTASH_PORT=5000 my-trainer:latest

Generate env files with Ansible

ansible-playbook -i ansible/inventory.ini ansible/playbooks/deploy_models.yml

Kubernetes
- Apply the `k8s/logstash-configmap.yaml` and `k8s/logstash-deployment.yaml`:

kubectl apply -f k8s/logstash-configmap.yaml
kubectl apply -f k8s/logstash-deployment.yaml

- For each model, render `k8s/trainer-deployment-template.yaml` (replace placeholders) and `kubectl apply -f` the result.

Notes & next steps
- You can adapt the Ansible playbook to also generate Kubernetes `ConfigMap` objects (using the `k8s` module) or to call `kubectl` automatically.
- If you want Logstash to receive logs directly from Docker container stdout, you can use `filebeat`/`docker log` forwarding, or configure your container runtime to send logs to Logstash TCP.

Ansible Vault & Kubernetes automation

- Store your Hugging Face token in an Ansible Vault variable file at `ansible/group_vars/all/vault.yml`:

```yaml
# ansible/group_vars/all/vault.yml
hf_api_token: "REPLACE_WITH_HF_TOKEN"
```

- Encrypt the file locally before running playbooks:

```powershell
ansible-vault encrypt ansible/group_vars/all/vault.yml
```

- The updated `deploy_models.yml` playbook will:
	- render per-model env files (as before),
	- create a Kubernetes `Secret` named `hf-token` from the vaulted `hf_api_token`,
	- create per-model `ConfigMap` objects with `PROCESSED_DATA_PATH`, `MODEL_CHECKPOINT`, and `MODEL_OUTPUT_DIR`,
	- render a trainer deployment manifest per-model and apply it with the `k8s` module.

Prerequisites for Ansible → Kubernetes automation
- You need `kubectl` configured and reachable from where you run Ansible, or set `K8S_AUTH_*` env vars for Ansible's k8s module.
- Install required Python deps for the `k8s` module on the Ansible controller:

```powershell
pip install openshift kubernetes
```

Run the playbook (if vault is encrypted, supply the vault password):

```powershell
ansible-playbook -i ansible/inventory.ini ansible/playbooks/deploy_models.yml --ask-vault-pass
```

This will create the ConfigMaps, Secret and trainer Deployments/Services in the `default` namespace. You can change namespace by editing the playbook.
