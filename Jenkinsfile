pipeline {
    agent any

    parameters {
        booleanParam(name: 'PUSH_IMAGE', defaultValue: false,
                     description: 'Push the image to Docker Hub (needs the dockerhub-creds credential)')
    }

    environment {
        IMAGE   = 'rahulkmishra2806/manthan-api'
        TAG     = "${env.GIT_COMMIT.take(7)}"
        CI_NAME = "manthan-ci-${env.BUILD_NUMBER}"
    }

    options {
        timestamps()
        disableConcurrentBuilds()
        timeout(time: 30, unit: 'MINUTES')
        buildDiscarder(logRotator(numToKeepStr: '10'))
    }

    stages {
        stage('Install') {
            steps {
                sh 'uv sync --dev --frozen'
            }
        }

        stage('Lint') {
            steps {
                sh 'uv run ruff check .'
                sh 'uv run python -m compileall -q app scripts'
            }
        }

        stage('Unit Tests') {
            steps {
                sh 'uv run pytest'
            }
        }

        stage('Build Image') {
            steps {
                sh 'docker build -f docker/api.Dockerfile -t $IMAGE:$TAG -t $IMAGE:latest .'
            }
        }

        stage('Smoke Test') {
            steps {
                sh '''
                  docker network create $CI_NAME
                  docker run -d --name $CI_NAME-db --network $CI_NAME \
                    -e POSTGRES_DB=manthan -e POSTGRES_USER=manthan -e POSTGRES_PASSWORD=ci \
                    postgres:17-alpine
                  until docker exec $CI_NAME-db pg_isready -U manthan -d manthan; do sleep 1; done

                  DB_URL=postgresql+psycopg://manthan:ci@$CI_NAME-db:5432/manthan

                  # Migrations must apply cleanly to an empty database
                  docker run --rm --network $CI_NAME -e DATABASE_URL=$DB_URL -e SECRET_KEY=ci-only \
                    $IMAGE:$TAG alembic upgrade head

                  docker run -d --name $CI_NAME-api --network $CI_NAME \
                    -e DATABASE_URL=$DB_URL -e SECRET_KEY=ci-only $IMAGE:$TAG

                  for path in /health/live /api/v1/health/ready; do
                    docker exec $CI_NAME-api python -c "
import sys, time, urllib.request
for _ in range(30):
    try:
        print(urllib.request.urlopen('http://localhost:8000$path').read().decode()); sys.exit(0)
    except Exception:
        time.sleep(1)
sys.exit('$path did not respond')"
                  done
                '''
            }
            post {
                failure { sh 'docker logs $CI_NAME-api || true' }
                always {
                    sh 'docker rm -f $CI_NAME-api $CI_NAME-db || true'
                    sh 'docker network rm $CI_NAME || true'
                }
            }
        }

        stage('Push Image') {
            when {
                allOf {
                    expression { params.PUSH_IMAGE }
                    expression { env.GIT_BRANCH == 'origin/main' }
                }
            }
            steps {
                withCredentials([usernamePassword(credentialsId: 'dockerhub-creds',
                                                  usernameVariable: 'U', passwordVariable: 'P')]) {
                    sh 'echo "$P" | docker login -u "$U" --password-stdin'
                    sh 'docker push $IMAGE:$TAG && docker push $IMAGE:latest'
                }
            }
            post {
                always { sh 'docker logout || true' }
            }
        }
    }

    post {
        success { echo "Built $IMAGE:$TAG" }
        always  { sh 'docker image prune -f || true' }
    }
}
