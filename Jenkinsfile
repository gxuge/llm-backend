pipeline {
  agent any

  environment {
    IMAGE_NAME = 'your-registry/fastapi-langgraph'
    IMAGE_TAG  = "${env.GIT_COMMIT}"
    DEPLOY_HOST = 'your.server.ip'
    DEPLOY_USER = 'your_user'
    DEPLOY_PATH = '/opt/fastapi-langgraph'
    COMPOSE_FILE = 'docker-compose.prod.yml'
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

    stage('Push Image') {
      steps {
        withCredentials([usernamePassword(credentialsId: 'docker-registry', usernameVariable: 'REG_USER', passwordVariable: 'REG_PASS')]) {
          sh 'echo $REG_PASS | docker login -u $REG_USER --password-stdin'
          sh 'docker push $IMAGE_NAME:$IMAGE_TAG'
        }
      }
    }

    stage('Deploy') {
      steps {
        sshagent(credentials: ['deploy-ssh']) {
          sh '''
            ssh -o StrictHostKeyChecking=no $DEPLOY_USER@$DEPLOY_HOST \
              "cd $DEPLOY_PATH && \
               export IMAGE_NAME=$IMAGE_NAME IMAGE_TAG=$IMAGE_TAG && \
               docker compose -f $COMPOSE_FILE pull && \
               docker compose -f $COMPOSE_FILE up -d"
          '''
        }
      }
    }
  }
}
