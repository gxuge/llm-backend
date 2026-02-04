pipeline {
  agent any

  environment {
    IMAGE_NAME = 'fastapi-langgraph'
    IMAGE_TAG  = "${env.GIT_COMMIT}"
    DEPLOY_HOST = '117.72.149.125'
    DEPLOY_USER = 'root'
    DEPLOY_PATH = '/www/fastapi-langgraph-jenkins'
    COMPOSE_FILE = 'docker-compose.yml'
  }

  stages {
    stage('Checkout') {
      steps {
        checkout scm
      }
    }

    stage('Build Image') {
      steps {
        sh 'docker build -t $IMAGE_NAME:$IMAGE_TAG .'
      }
    }

    stage('Deploy') {
      steps {
        sshagent(credentials: ['deploy-ssh']) {
          sh '''
            ssh -o StrictHostKeyChecking=no $DEPLOY_USER@$DEPLOY_HOST \
              "mkdir -p $DEPLOY_PATH && \
               cd $DEPLOY_PATH && \
               export IMAGE_NAME=$IMAGE_NAME IMAGE_TAG=$IMAGE_TAG && \
               docker compose -f $COMPOSE_FILE pull && \
               docker compose -f $COMPOSE_FILE up -d"
          '''
        }
      }
    }
  }
}
