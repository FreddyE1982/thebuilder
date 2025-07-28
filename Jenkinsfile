pipeline {
    agent any
    stages {
        stage('Install') {
            steps {
                sh 'pip install -r requirements.txt'
                sh 'pip install pytest'
            }
        }
        stage('Test') {
            steps {
                sh 'pytest --maxfail=1'
            }
        }
    }
}
