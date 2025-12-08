pipeline {
  agent any

  environment {
    DOCKER_CLI_EXPERIMENTAL = "enabled"
    REGISTRY = "shreyankgopal403"
    NAMESPACE = "default"

    VENV_PATH = "venv-path"

    DOCKER_CREDENTIALS_ID = "dockerhub-credentials"
    ANSIBLE_VAULT_CRED_ID = "ansible-vault-pass"

    ANSIBLE_PYTHON_INTERPRETER = "ansible-python"
  }



  stages {

    stage('Checkout Code') {
      when { expression { return false } }
      steps {
        echo "Skipping SCM checkout — using local workspace"
      }
    }

    stage("Setup buildx & Docker login") {
      steps {
        withCredentials([
          usernamePassword(
            credentialsId: env.DOCKER_CREDENTIALS_ID,
            usernameVariable: 'DOCKER_USER',
            passwordVariable: 'DOCKER_PASS'
          )
        ]) {
          sh '''
            set -e
            docker logout || true
            echo "$DOCKER_PASS" | docker login -u "$DOCKER_USER" --password-stdin
            docker buildx create --name mybuilder --driver docker-container --use || true
            docker buildx inspect --bootstrap
          '''
        }
      }
    }

    stage('Build & Push DataLoader Image') {
      steps {
        withCredentials([
          usernamePassword(
            credentialsId: env.DOCKER_CREDENTIALS_ID,
            usernameVariable: 'DOCKER_USER',
            passwordVariable: 'DOCKER_PASS'
          )
        ]) {
          sh '''
            set -e

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
        withCredentials([
          usernamePassword(
            credentialsId: env.DOCKER_CREDENTIALS_ID,
            usernameVariable: 'DOCKER_USER',
            passwordVariable: 'DOCKER_PASS'
          )
        ]) {
          sh '''
            set -e

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
        withCredentials([
          usernamePassword(
            credentialsId: env.DOCKER_CREDENTIALS_ID,
            usernameVariable: 'DOCKER_USER',
            passwordVariable: 'DOCKER_PASS'
          )
        ]) {
          sh '''
            set -e

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
        withCredentials([
          usernamePassword(
            credentialsId: env.DOCKER_CREDENTIALS_ID,
            usernameVariable: 'DOCKER_USER',
            passwordVariable: 'DOCKER_PASS'
          )
        ]) {
          sh '''
            set -e

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
        withCredentials([
          string(credentialsId: env.ANSIBLE_VAULT_CRED_ID, variable: 'VAULT_PASS'),
          string(credentialsId: env.VENV_PATH, variable: 'VENV_PATH'),
          string(credentialsId: env.ANSIBLE_PYTHON_INTERPRETER, variable: 'ANSIBLE_PYTHON_INTERPRETER')
        ]) {
          sh '''
            set -e

            # --- FIX: ensure proper kubeconfig is used ---
            export KUBECONFIG=$HOME/.kube/config
            echo "==> Ensuring Minikube is running"
            minikube status || minikube start --driver=docker

            echo "==> Updating kube context"
            minikube update-context

            # vault setup
            VAULT_FILE="$HOME/.ansible_vault_pass.txt"
            printf "%s" "$VAULT_PASS" > "$VAULT_FILE"
            chmod 600 "$VAULT_FILE"

            # activate venv
            . "$VENV_PATH/bin/activate"
            ANSIBLE_PY="${ANSIBLE_PYTHON_INTERPRETER}"

            pip install --quiet ansible kubernetes openshift requests pyyaml

            ansible-playbook ansible/playbooks/deploy_pipeline.yml \
              -i ansible/inventory.ini \
              --extra-vars "k8s_namespace=${NAMESPACE}" \
              --vault-password-file "$VAULT_FILE" \
              -e "ansible_python_interpreter=$ANSIBLE_PY"

            shred -u -z "$VAULT_FILE" || rm -f "$VAULT_FILE"
          '''
        }
      }
    }
  }

  post {
    success { echo "🚀 Pipeline executed successfully!" }
    failure { echo "❌ Pipeline failed. Check logs." }
  }
}