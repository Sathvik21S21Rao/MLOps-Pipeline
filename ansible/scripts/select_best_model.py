#!/usr/bin/env python3
import sys
import json
import requests

"""
Select the best model based on training metrics stored in Elasticsearch (Logstash index).
Usage: select_best_model.py <elasticsearch_url> <comma_separated_models>
Returns the best model name on stdout; exits 1 if none found.
"""

ES_QUERY = {
    "size": 0,
    "query": {
        "bool": {
            "must": [
                {"term": {"log_type.keyword": "training_metrics"}}
            ]
        }
    },
    "aggs": {
        "by_model": {
            "terms": {"field": "model_name.keyword", "size": 50},
            "aggs": {
                "latest": {
                    "top_hits": {
                        "sort": [{"timestamp": {"order": "desc"}}],
                        "size": 1
                    }
                },
                "max_f1": {"max": {"field": "metrics.f1"}},
                "max_accuracy": {"max": {"field": "metrics.accuracy"}}
            }
        }
    }
}


def pick_best_model(es_url: str, allowed_models):
    resp = requests.post(f"{es_url}/logstash-*/_search", json=ES_QUERY, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    buckets = data.get("aggregations", {}).get("by_model", {}).get("buckets", [])

    best = None
    for b in buckets:
        name = b.get("key")
        if allowed_models and name not in allowed_models:
            continue
        f1 = b.get("max_f1", {}).get("value")
        acc = b.get("max_accuracy", {}).get("value")
        score = (f1 or 0, acc or 0)
        if best is None or score > best[1]:
            best = (name, score)

    if best:
        return best[0]
    return None


def main():
    if len(sys.argv) < 2:
        print("Usage: select_best_model.py <elasticsearch_url> [comma_separated_models]", file=sys.stderr)
        sys.exit(1)
    es_url = sys.argv[1].rstrip('/')
    allowed = sys.argv[2].split(',') if len(sys.argv) > 2 and sys.argv[2] else []

    try:
        best = pick_best_model(es_url, allowed)
        if not best:
            print("", end="")
            sys.exit(1)
        print(best, end="")
    except Exception as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
