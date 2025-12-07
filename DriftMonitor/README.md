# Drift Monitor

Monitors model inference logs from Elasticsearch and triggers Jenkins pipeline retraining when classification distribution skewness is detected.

## How It Works

1. **Queries Elasticsearch** every 5 minutes (configurable) for recent inference predictions
2. **Calculates class distribution** from predicted labels
3. **Detects skewness** - triggers if one class exceeds 70% (configurable)
4. **Triggers Jenkins pipeline** to rebuild and retrain models
5. **Cooldown period** - prevents retriggering within 30 minutes

## Configuration

Edit `ansible/group_vars/all/vars.yml`:

```yaml
# Drift monitor settings
jenkins_url: "http://your-jenkins-url:8080"
jenkins_user: "admin"
drift_check_interval: "300"          # Check every 5 minutes
drift_lookback_minutes: "15"         # Analyze last 15 minutes of logs
drift_skewness_threshold: "0.7"      # Trigger if one class > 70%
drift_min_samples: "50"              # Minimum predictions needed
```

Add Jenkins API token to vault:
```bash
ansible-vault edit ansible/group_vars/all/vault.yml
```

Add:
```yaml
jenkins_token: "your-jenkins-api-token-here"
```

## Jenkins Setup

1. Generate Jenkins API token:
   - Jenkins → User → Configure → API Token → Add new Token
   
2. Configure Jenkins job to accept remote triggers:
   - Job → Configure → Build Triggers → "Trigger builds remotely"
   - Set authentication token (same as `jenkins_token` in vault)

3. Update `ansible/group_vars/all/vars.yml` with correct Jenkins URL

## Deployment

Deploy with the full pipeline:
```bash
ansible-playbook ansible/playbooks/deploy_pipeline.yml -i ansible/inventory.ini --vault-password-file ~/.vault_pass
```

Or deploy drift monitor separately:
```bash
ansible-playbook ansible/playbooks/deploy_pipeline.yml -i ansible/inventory.ini --vault-password-file ~/.vault_pass --tags driftmonitor
```

## Monitoring

Check drift monitor logs:
```bash
kubectl logs -f deployment/drift-monitor -n ml-pipeline
```

Example output:
```
2025-12-07 08:00:00 - Running drift detection check...
2025-12-07 08:00:01 - Retrieved 150 inference predictions from last 15 minutes
2025-12-07 08:00:01 - Class distribution: {1: 0.12, 2: 0.76, 3: 0.08, 4: 0.04}
2025-12-07 08:00:01 - DRIFT DETECTED: Class 2 accounts for 76.0% of predictions (threshold: 70%)
2025-12-07 08:00:02 - Jenkins pipeline triggered successfully
```

## Architecture

```
┌─────────────────┐
│  Model Inference│──┐
│   (FastAPI)     │  │
└─────────────────┘  │
                     │ Predictions logged
┌─────────────────┐  │ to Logstash
│  Logstash       │◄─┘
│  (TCP 5004)     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐     ┌─────────────────┐
│ Elasticsearch   │◄────│  Drift Monitor  │
│  (Port 9200)    │     │  (queries ES)   │
└─────────────────┘     └────────┬────────┘
                                 │
                                 │ Triggers on drift
                                 ▼
                        ┌─────────────────┐
                        │  Jenkins        │
                        │  (rebuilds)     │
                        └─────────────────┘
```

## Customization

### Adjust Sensitivity

More sensitive (trigger earlier):
```yaml
drift_skewness_threshold: "0.6"  # 60%
drift_min_samples: "30"
```

Less sensitive (trigger only on severe drift):
```yaml
drift_skewness_threshold: "0.85"  # 85%
drift_min_samples: "100"
```

### Change Check Frequency

More frequent:
```yaml
drift_check_interval: "120"  # 2 minutes
```

Less frequent:
```yaml
drift_check_interval: "600"  # 10 minutes
```

### Multiple Detection Strategies

The monitor currently uses **max class proportion**. You can extend `drift_monitor.py` to add:
- Chi-square test against expected distribution
- KL divergence from training distribution
- Consecutive drift detection (trigger only after N consecutive drifts)

## Troubleshooting

**Monitor not starting:**
```bash
kubectl describe pod -l app=drift-monitor -n ml-pipeline
```

**Can't connect to Elasticsearch:**
- Verify ES is running: `kubectl get pods -n ml-pipeline | grep elasticsearch`
- Check ES password in secret: `kubectl get secret drift-monitor-secret -n ml-pipeline -o yaml`

**Jenkins not triggering:**
- Verify Jenkins URL is accessible from cluster
- Check Jenkins token is correct
- Review Jenkins job configuration (remote trigger enabled)
- Check cooldown period hasn't prevented trigger

**No drift detected even with skewed data:**
- Lower `drift_skewness_threshold`
- Check if enough samples: `drift_min_samples`
- Verify predictions are reaching Elasticsearch (check Kibana)
