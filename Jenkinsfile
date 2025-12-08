pipeline {
  agent any

  environment {
    DOCKER_CLI_EXPERIMENTAL = "enabled"
    REGISTRY = "shreyankgopal403"
    NAMESPACE = "default"

    VENV_PATH = "/Users/SGBHAT/.jenkins/workspace/MLOps-Pipeline/.venv"

    DOCKER_CREDENTIALS_ID = "dockerhub-credentials"
    ANSIBLE_VAULT_CRED_ID = "ansible-vault-pass"

    ANSIBLE_PYTHON_INTERPRETER = "/Users/SGBHAT/.jenkins/workspace/MLOps-Pipeline/.venv/bin/python"
  }

  stages {

    stage('Checkout Code') {
      when { expression { return false } }  // Disable SCM checkout (you want local directory)
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
    withCredentials([string(credentialsId: env.ANSIBLE_VAULT_CRED_ID, variable: 'VAULT_PASS')]) {
      sh '''
        set -e

        cd "$WORKSPACE"

        echo "==> Creating local vault file"
        VAULT_FILE="$HOME/.ansible_vault_pass.txt"
        printf "%s" "$VAULT_PASS" > "$VAULT_FILE"
        chmod 600 "$VAULT_FILE"

        echo "==> Checking if venv exists"
        if [ ! -d "$WORKSPACE/.venv" ]; then
          echo "==> Creating virtual environment"
          python3 -m venv "$WORKSPACE/.venv"
        fi

        echo "==> Activating virtual environment"
        . "$WORKSPACE/.venv/bin/activate"

        echo "==> Installing required Python packages"
        pip install --upgrade pip
        pip install ansible kubernetes openshift pyyaml requests

        echo "==> Running Ansible Playbook"
        ansible-playbook ansible/playbooks/deploy_pipeline.yml \
          -i ansible/inventory.ini \
          --extra-vars "k8s_namespace=${NAMESPACE}" \
          --vault-password-file "$VAULT_FILE" \
          -e "ansible_python_interpreter=$WORKSPACE/.venv/bin/python"

        echo "==> Cleaning up vault file"
        shred -u -z "$VAULT_FILE" || rm -f "$VAULT_FILE"
      '''
    }
  }
}

  post {
    success { echo "🚀 Pipeline executed successfully!" }
    failure { echo "❌ Pipeline failed. Check logs." }
  }
}
