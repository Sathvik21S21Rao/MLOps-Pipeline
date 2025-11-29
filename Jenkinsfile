pipeline {
  agent any

  environment {
    DOCKER_CLI_EXPERIMENTAL = "enabled"
    REGISTRY = "nikhilesh611"
    NAMESPACE = "default"
    PYTHON_INTERPRETER = "/usr/bin/python3"
    DOCKER_CREDENTIALS_ID = "dockerhub-creds"
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
            set -euo pipefail

            echo "==> Clearing any existing docker login (safe)"
            docker logout || true

            echo "==> Logging into Docker Hub as $DOCKER_USER"
            echo "$DOCKER_PASS" | docker login -u "$DOCKER_USER" --password-stdin

            echo "==> Checking docker login keys (non-sensitive)"
            if [ -f "$HOME/.docker/config.json" ]; then
              grep -Eo '"(index|https://registry-1.docker.io|https://index.docker.io/v1/)":' "$HOME/.docker/config.json" || true
            fi

            echo "==> Ensuring buildx builder uses docker-container driver"
            # create a docker-container driver builder and select it for this job
            docker buildx create --name mybuilder --driver docker-container --use || true
            docker buildx inspect --bootstrap
            docker buildx version
          '''
        }
      }
    }

    stage('Build & Push DataLoader Image') {
      steps {
        sh '''
          set -euo pipefail
          echo "==> Building & pushing dataloader"
          # Ensure login in this stage in case the agent changed between stages
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

    stage('Build & Push ModelTrainer Image') {
      steps {
        sh '''
          set -euo pipefail
          echo "==> Building & pushing modeltrainer"
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

    stage('Build & Push ModelInference Image') {
      steps {
        sh '''
          set -euo pipefail
          echo "==> Building & pushing model-inference"
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

    stage('Deploy to Kubernetes using Ansible') {
      steps {
        sh '''
          set -euo pipefail
          PYTHON_INTERPRETER="$(command -v python3 || command -v python || echo /usr/bin/python3)"
          echo "Using Ansible python interpreter: $PYTHON_INTERPRETER"

          ansible-playbook ansible/playbooks/deploy_pipeline.yml \
            -i ansible/inventory.ini \
            --extra-vars "k8s_namespace=${NAMESPACE}" \
            --vault-password-file ~/.vault_pass.txt \
            -e "ansible_python_interpreter=${PYTHON_INTERPRETER}"
        '''
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
