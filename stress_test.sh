#stress_test.sh
SERVICE_NAME=model-inference-service
NAMESPACE=default
ROUTE="/predict"   # your FastAPI endpoint
DATA='{"email_text": "This is a sample email for testing autoscaling"}'
REQUESTS=100000       # total number of requests
CONCURRENCY=100       # how many parallel clients
# -----------------------------

echo "Fetching ClusterIP for $SERVICE_NAME ..."
SERVICE_IP=$(kubectl get svc $SERVICE_NAME -n $NAMESPACE -o jsonpath='{.spec.clusterIP}')
echo "Service IP: $SERVICE_IP"

echo "Starting port-forward (background)..."
kubectl port-forward svc/$SERVICE_NAME 8000:80 -n $NAMESPACE >/dev/null 2>&1 &
PF_PID=$!

sleep 2

echo "Running load test..."
echo "Sending $REQUESTS requests with concurrency $CONCURRENCY"

# SEND LOT OF PARALLEL REQUESTS
seq $REQUESTS | xargs -n1 -P"$CONCURRENCY" bash -c "curl -s -X POST http://127.0.0.1:8000$ROUTE -H 'Content-Type: application/json' -d '$DATA' >/dev/null"

echo "✔ Load test complete."

# STOP PORT FORWARD
kill $PF_PID

echo "Checking HPA scaling:"
kubectl get hpa -n $NAMESPACE

echo "Checking deployment replicas:"
kubectl get deployment -n $NAMESPACE