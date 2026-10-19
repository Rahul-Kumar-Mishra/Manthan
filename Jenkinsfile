pipeline {
    agent any
    stages {
        stage('Test') {
            steps {
                sh 'uv sync --dev'
                sh 'uv run ruff check .'
                sh 'uv run pytest'
            }
        }
    }
}