#!/usr/bin/env python3
"""
Drift Monitor: Detects classification distribution skewness in model inference logs
and triggers Jenkins pipeline for retraining when drift exceeds threshold.
"""
import os
import sys
import time
import json
import logging
from datetime import datetime, timedelta
from collections import Counter
import requests
from requests.auth import HTTPBasicAuth

# Configuration
ELASTICSEARCH_HOST = os.environ.get("ELASTICSEARCH_HOST", "elasticsearch")
ELASTICSEARCH_PORT = int(os.environ.get("ELASTICSEARCH_PORT", "9200"))
ELASTICSEARCH_USER = os.environ.get("ELASTICSEARCH_USER", "elastic")
ELASTICSEARCH_PASSWORD = os.environ.get("ELASTICSEARCH_PASSWORD", "changeme")

JENKINS_URL = os.environ.get("JENKINS_URL", "http://jenkins:8080")
JENKINS_JOB = os.environ.get("JENKINS_JOB", "MLOps-Pipeline")
JENKINS_USER = os.environ.get("JENKINS_USER", "admin")
JENKINS_TOKEN = os.environ.get("JENKINS_TOKEN", "")

# Drift detection parameters
CHECK_INTERVAL_SECONDS = int(os.environ.get("CHECK_INTERVAL_SECONDS", "300"))  # 5 minutes
LOOKBACK_MINUTES = int(os.environ.get("LOOKBACK_MINUTES", "15"))
SKEWNESS_THRESHOLD = float(os.environ.get("SKEWNESS_THRESHOLD", "0.7"))  # If one class > 70%, trigger
MIN_SAMPLES = int(os.environ.get("MIN_SAMPLES", "50"))  # Minimum predictions to analyze

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DriftMonitor:
    def __init__(self):
        self.es_url = f"http://{ELASTICSEARCH_HOST}:{ELASTICSEARCH_PORT}"
        self.es_auth = HTTPBasicAuth(ELASTICSEARCH_USER, ELASTICSEARCH_PASSWORD)
        self.last_trigger_time = None
        self.cooldown_minutes = 30  # Prevent retriggering within 30 min
        
    def query_inference_logs(self):
        """Query Elasticsearch for recent inference predictions."""
        now = datetime.utcnow()
        start_time = now - timedelta(minutes=LOOKBACK_MINUTES)
        
        query = {
            "query": {
                "bool": {
                    "must": [
                        {"term": {"log_type.keyword": "inference_event"}},
                        {"term": {"event.keyword": "prediction"}},
                        {
                            "range": {
                                "@timestamp": {
                                    "gte": start_time.isoformat(),
                                    "lte": now.isoformat()
                                }
                            }
                        }
                    ]
                }
            },
            "size": 10000,
            "_source": ["predicted_label", "label", "timestamp", "model_name"]
        }
        
        try:
            response = requests.post(
                f"{self.es_url}/logstash-*/_search",
                json=query,
                auth=self.es_auth,
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            response.raise_for_status()
            data = response.json()
            
            hits = data.get("hits", {}).get("hits", [])
            logger.info(f"Retrieved {len(hits)} inference predictions from last {LOOKBACK_MINUTES} minutes")
            
            return [hit["_source"] for hit in hits]
        
        except Exception as e:
            logger.error(f"Failed to query Elasticsearch: {e}")
            return []
    
    def calculate_distribution(self, predictions):
        """Calculate class distribution from predictions."""
        if not predictions:
            return {}
        
        labels = [pred.get("predicted_label") for pred in predictions if "predicted_label" in pred]
        counter = Counter(labels)
        total = len(labels)
        
        if total == 0:
            return {}
        
        distribution = {label: count / total for label, count in counter.items()}
        return distribution
    
    def detect_skewness(self, distribution):
        """
        Detect if distribution is skewed beyond threshold.
        Returns (is_skewed, max_proportion, dominant_label).
        """
        if not distribution:
            return False, 0.0, None
        
        max_label = max(distribution, key=distribution.get)
        max_proportion = distribution[max_label]
        
        is_skewed = max_proportion >= SKEWNESS_THRESHOLD
        
        return is_skewed, max_proportion, max_label
    
    def trigger_jenkins_pipeline(self, reason):
        """Trigger Jenkins pipeline rebuild."""
        if not JENKINS_TOKEN:
            logger.warning("JENKINS_TOKEN not set; cannot trigger pipeline")
            return False
        
        # Check cooldown period
        if self.last_trigger_time:
            elapsed = (datetime.utcnow() - self.last_trigger_time).total_seconds() / 60
            if elapsed < self.cooldown_minutes:
                logger.info(f"Cooldown active: {self.cooldown_minutes - elapsed:.1f} minutes remaining")
                return False
        
        try:
            trigger_url = f"{JENKINS_URL}/job/{JENKINS_JOB}/build"
            params = {
                "token": JENKINS_TOKEN,
                "cause": f"Drift detected: {reason}"
            }
            
            response = requests.post(
                trigger_url,
                params=params,
                auth=HTTPBasicAuth(JENKINS_USER, JENKINS_TOKEN),
                timeout=10
            )
            
            if response.status_code in [200, 201]:
                logger.info(f"Jenkins pipeline triggered successfully: {reason}")
                self.last_trigger_time = datetime.utcnow()
                return True
            else:
                logger.error(f"Jenkins trigger failed: {response.status_code} - {response.text}")
                return False
        
        except Exception as e:
            logger.error(f"Failed to trigger Jenkins: {e}")
            return False
    
    def run_check(self):
        """Run a single drift check cycle."""
        logger.info("=" * 60)
        logger.info("Running drift detection check...")
        
        # Query recent predictions
        predictions = self.query_inference_logs()
        
        if len(predictions) < MIN_SAMPLES:
            logger.info(f"Insufficient samples: {len(predictions)} < {MIN_SAMPLES} (minimum required)")
            return
        
        # Calculate distribution
        distribution = self.calculate_distribution(predictions)
        logger.info(f"Class distribution: {distribution}")
        
        # Detect skewness
        is_skewed, max_prop, dominant_label = self.detect_skewness(distribution)
        
        if is_skewed:
            reason = f"Class {dominant_label} accounts for {max_prop*100:.1f}% of predictions (threshold: {SKEWNESS_THRESHOLD*100}%)"
            logger.warning(f"DRIFT DETECTED: {reason}")
            logger.info(f"Sample count: {len(predictions)}, Distribution: {distribution}")
            
            # Trigger pipeline
            self.trigger_jenkins_pipeline(reason)
        else:
            logger.info(f"No drift detected. Max class proportion: {max_prop*100:.1f}%")
    
    def run_forever(self):
        """Continuously monitor for drift."""
        logger.info("Drift Monitor started")
        logger.info(f"Configuration:")
        logger.info(f"  - Elasticsearch: {self.es_url}")
        logger.info(f"  - Jenkins: {JENKINS_URL}/job/{JENKINS_JOB}")
        logger.info(f"  - Check interval: {CHECK_INTERVAL_SECONDS}s")
        logger.info(f"  - Lookback window: {LOOKBACK_MINUTES} minutes")
        logger.info(f"  - Skewness threshold: {SKEWNESS_THRESHOLD*100}%")
        logger.info(f"  - Minimum samples: {MIN_SAMPLES}")
        logger.info(f"  - Cooldown period: {self.cooldown_minutes} minutes")
        
        while True:
            try:
                self.run_check()
            except Exception as e:
                logger.error(f"Error in check cycle: {e}", exc_info=True)
            
            logger.info(f"Sleeping for {CHECK_INTERVAL_SECONDS} seconds...")
            time.sleep(CHECK_INTERVAL_SECONDS)


if __name__ == "__main__":
    monitor = DriftMonitor()
    monitor.run_forever()
