pipeline {
  agent any

  environment {
    DOCKER_CLI_EXPERIMENTAL = "enabled"
    REGISTRY = "shreyankgopal403"
    NAMESPACE = "default"
    VENV_PATH = "/Users/SGBHAT/Library/CloudStorage/OneDrive-iiit-b/IIIT-B/sem-7/SPE/MajorProject/MLOps-Pipeline/.venv"
    DOCKER_CREDENTIALS_ID = "	dockerhub-credentials"
    ANSIBLE_VAULT_CRED_ID = "ansible-vault-pass"
    ANSIBLE_PYTHON_INTERPRETER = "/Users/SGBHAT/Library/CloudStorage/OneDrive-iiit-b/IIIT-B/sem-7/SPE/MajorProject/MLOps-Pipeline/.venv/bin/python"
  }

  stages {

    stage('Checkout Code') {
      steps {
        checkout scm
      }
    }

    stage("Setup buildx & Docker login") {
      steps {
        withCredentials([usernamePassword(credentialsId: env.DOCKER_CREDENTIALS_ID,
                                          usernameVariable: 'DOCKER_USER',
                                          passwordVariable: 'DOCKER_PASS')]) {
          sh '''
            set -e

            echo "==> Clearing any existing docker login (safe)"
            docker logout || true

            echo "==> Logging into Docker Hub as $DOCKER_USER"
            echo "$DOCKER_PASS" | docker login -u "$DOCKER_USER" --password-stdin

            echo "==> Ensuring buildx builder uses docker-container driver"
            docker buildx create --name mybuilder --driver docker-container --use || true
            docker buildx inspect --bootstrap
            docker buildx version
          '''
        }
      }
    }

    stage('Build & Push DataLoader Image') {
      steps {
        withCredentials([usernamePassword(credentialsId: env.DOCKER_CREDENTIALS_ID,
                                          usernameVariable: 'DOCKER_USER',
                                          passwordVariable: 'DOCKER_PASS')]) {
          sh '''
            set -e
            echo "==> (DataLoader) Ensure login"
            docker logout || true
            echo "$DOCKER_PASS" | docker login -u "$DOCKER_USER" --password-stdin

            docker buildx build \
              --platform linux/amd64,linux/arm64 \
              -t $REGISTRY/dataloader:latest \
              --push \
              ./DataLoading
          '''
        }
      }
    }

    stage('Build & Push ModelTrainer Image') {
      steps {
        withCredentials([usernamePassword(credentialsId: env.DOCKER_CREDENTIALS_ID,
                                          usernameVariable: 'DOCKER_USER',
                                          passwordVariable: 'DOCKER_PASS')]) {
          sh '''
            set -e
            echo "==> (ModelTrainer) Ensure login"
            docker logout || true
            echo "$DOCKER_PASS" | docker login -u "$DOCKER_USER" --password-stdin

            docker buildx build \
              --platform linux/amd64,linux/arm64 \
              -t $REGISTRY/modeltrainer:latest \
              --push \
              ./ModelTraining
          '''
        }
      }
    }

    stage('Build & Push ModelInference Image') {
      steps {
        withCredentials([usernamePassword(credentialsId: env.DOCKER_CREDENTIALS_ID,
                                          usernameVariable: 'DOCKER_USER',
                                          passwordVariable: 'DOCKER_PASS')]) {
          sh '''
            set -e
            echo "==> (ModelInference) Ensure login"
            docker logout || true
            echo "$DOCKER_PASS" | docker login -u "$DOCKER_USER" --password-stdin

            docker buildx build \
              --platform linux/amd64,linux/arm64 \
              -t $REGISTRY/model-inference:latest \
              --push \
              ./ModelInference
          '''
        }
      }
    }

    stage('Build & Push DriftMonitor Image') {
      steps {
        withCredentials([usernamePassword(credentialsId: env.DOCKER_CREDENTIALS_ID,
                                          usernameVariable: 'DOCKER_USER',
                                          passwordVariable: 'DOCKER_PASS')]) {
          sh '''
            set -e
            echo "==> (DriftMonitor) Ensure login"
            docker logout || true
            echo "$DOCKER_PASS" | docker login -u "$DOCKER_USER" --password-stdin

            docker buildx build \
              --platform linux/amd64,linux/arm64 \
              -t $REGISTRY/drift-monitor:latest \
              --push \
              ./DriftMonitor
          '''
        }
      }
    }

    stage('Deploy to Kubernetes using Ansible') {
      steps {
        withCredentials([string(credentialsId: env.ANSIBLE_VAULT_CRED_ID, variable: 'VAULT_PASS')]) {
          sh '''
            set -e

            # create temporary vault file in HOME and make it private to the jenkins user
            VAULT_FILE="$HOME/.ansible_vault_pass.txt"
            printf "%s" "$VAULT_PASS" > "$VAULT_FILE"
            chmod 600 "$VAULT_FILE"

            # prefer venv python if it exists; otherwise fall back to system python3
            if [ -x "$VENV_PATH/bin/activate" ]; then
              echo "Activating venv at $VENV_PATH"
              # shellcheck disable=SC1090
              . "$VENV_PATH/bin/activate"
              ANSIBLE_PY="$VENV_PATH/bin/python"
            else
              echo "No venv found at $VENV_PATH; falling back to system python3"
              ANSIBLE_PY="$(command -v python3 || command -v python || echo /usr/bin/python3)"
            fi

            echo "Using Ansible python interpreter: $ANSIBLE_PY"

            # ensure required controller libs are present (idempotent)
            # only install into venv (if active)
            if [ -n "$VIRTUAL_ENV" ]; then
              pip install --quiet --upgrade pip
              pip install --quiet ansible kubernetes openshift pyyaml requests || true
            fi

            ansible-playbook ansible/playbooks/deploy_pipeline.yml \
              -i ansible/inventory.ini \
              --extra-vars "k8s_namespace=${NAMESPACE}" \
              --vault-password-file "$VAULT_FILE" \
              -e "ansible_python_interpreter=$ANSIBLE_PY"

            # secure cleanup of vault file
            shred -u -z "$VAULT_FILE" || rm -f "$VAULT_FILE"
          '''
        }
      }
    }
  }

  post {
    success {
      echo "🚀 Pipeline executed successfully!"
    }
    failure {
      echo "❌ Pipeline failed. Check logs."
    }
  }
}
