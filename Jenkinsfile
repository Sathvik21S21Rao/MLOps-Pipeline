pipeline {
    agent any

    environment {
        DOCKER_CLI_EXPERIMENTAL = "enabled"
        REGISTRY = "nikhilesh611"
        NAMESPACE = "default"
        PYTHON_INTERPRETER = "/usr/bin/python3"
    }

    stages {

        stage('Checkout Code') {
            steps {
                checkout scm
            }
        }

        stage("Check docker buildx version") {
            steps {
                sh '''
                    docker buildx create --name mybuilder --use || true
                    docker buildx inspect --bootstrap
                '''
            }
        }

        stage('Build & Push DataLoader Image') {
            steps {
                sh '''
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
