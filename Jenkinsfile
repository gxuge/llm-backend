pipeline {
  agent any


  stages {
    stage('Checkout') {
      steps {
        checkout scm
      }
    }

    stage('Prepare Env') {
      steps {
        sh '''
          if [ -f .env.example ]; then
            cp .env.example .env
          else
            echo ".env.example not found"
            exit 1
          fi
        '''
      }
    }

    stage('Build Image') {
      steps {
        sh 'docker compose build'
      }
    }

    stage('Deploy') {
      steps {
        sh '''
          docker compose up -d
        '''
      }
    }
  }
}
