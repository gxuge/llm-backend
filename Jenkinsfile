// ??????????????????
def runCmd(String cmd) {
  if (isUnix()) {
    sh cmd
  } else {
    bat cmd
  }
}

def copyEnvFile(String src) {
  if (isUnix()) {
    sh "cp \"${src}\" .env"
  } else {
    bat "copy /Y \"${src}\" .env"
  }
}

pipeline {
  agent any
  environment {
    APP_NAME = "llm-backend"
  }
  stages {
    stage("Prep") {
      steps {
        script {
          if (env.ENV_FILE?.trim()) {
            copyEnvFile(env.ENV_FILE)
          }
          if (!fileExists(".env")) {
            error("Missing .env. Provide ENV_FILE (Jenkins file credential) or create .env on the agent.")
          }
        }
      }
    }
    stage("Build Image") {
      steps {
        script {
          runCmd("docker build -t ${env.APP_NAME}:${env.GIT_COMMIT} .")
        }
      }
    }
    stage("Deploy") {
      steps {
        script {
          runCmd("docker compose down")
          runCmd("docker compose up -d --build")
        }
      }
    }
  }
  post {
    always {
      script {
        runCmd("docker compose ps")
      }
    }
  }
}
