pipeline {
    agent {
        kubernetes {
            cloud 'quiz-app-eks'
            yaml '''
                apiVersion: v1
                kind: Pod
                metadata:
                  name: agent-1
                  labels:
                    jenkins/label: agent-1
                spec:
                  containers:
                    - name: jnlp
                      image: liavvv/jenkins-agent:1.7
                      imagePullPolicy: Always
                      volumeMounts:
                        - name: workspace-volume
                          mountPath: /home/jenkins/agent
                        - name: docker-config
                          mountPath: /home/jenkins/.docker
                          readOnly: true
                  volumes:
                    - name: workspace-volume
                      emptyDir: {}
                    - name: docker-config
                      secret:
                        secretName: docker-config
                        items:
                        - key: config.json
                          path: config.json
            '''
        }
    }

    environment {
        PIPELINE_STATUS       = "SUCCESS"
        BUILD_TAG             = "${BUILD_TIMESTAMP}"
        
        // Generates DOCKERHUB_CREDENTIALS_USR, DOCKERHUB_CREDENTIALS_PSW
        DOCKERHUB_CREDENTIALS = credentials('dockerhub-credentials')
        
        // Used for GitHub repository access (clone, push to GitOps repo)
        // Generates GITHUB_CREDENTIALS_USR, GITHUB_CREDENTIALS_PSW
        GITHUB_CREDENTIALS    = credentials('github-credentials')
        
        // Used for GitHub API calls (commit status updates)
        // This is a GitHub Personal Access Token with repo scope
        GITHUB_TOKEN          = credentials('github-token')
        
        // GitOps Configuration
        // GitHub repository for this application
        GITHUB_REPO           = "liav-hasson/Leumi-project"
        GITHUB_REPO_URL       = "https://github.com/${GITHUB_REPO}.git"
        
        // Git configuration for commits
        GIT_USER_NAME         = "Jenkins Pipeline"
        GIT_USER_EMAIL        = "jenkins@weatherlabs.org"
    }

    stages {
        stage('Prepare image version') {
            steps {
                script {
                    echo '--------- Preparing image version ---------'
                    checkout scm

                    // Default: use existing date-based BUILD_TAG
                    env.IMAGE_TAG = env.BUILD_TAG

                    // Compute semantic version and set env for the rest of pipeline
                    def semver = sh(returnStdout: true, script: './quiz-app/src/scripts/compute_next_version.sh ./quiz-app auto').trim()
                    if (semver) {
                        echo "Computed semantic version: ${semver}"
                        env.IMAGE_TAG = semver
                    } else {
                        echo "No semantic version computed; falling back to date-based tag: ${env.IMAGE_TAG}"
                    }
                }
            }
            post {
                failure {
                    script {
                        env.PIPELINE_STATUS = "FAILURE"
                    }
                }
            }
        }

        stage('Testing stage') {
            steps {
                echo '--------- Starting checkout and testing ---------'

                echo '--------- Running pylint test ---------'
                sh 'pylint quiz-app/src/python/main.py --score=yes --fail-under=5.0'
                sh 'pylint quiz-app/src/python/quiz_utils.py --score=yes --fail-under=5.0'
                sh 'pylint quiz-app/src/python/ai_utils.py --score=yes --fail-under=5.0'
                echo 'Pylint checks passed!'

                echo '--------- Skipping unit tests (no tests directory) ---------'
                echo 'Unit tests stage skipped - add tests in future'

                echo '--------- Running dependency vulnerability scan ---------'
                sh '''
                    # Run safety check on production dependencies only
                    # Focus on src/requirements.txt (production dependencies)
                    # Exit code 64 means vulnerabilities found, 0 means clean
                    safety check --json --file quiz-app/src/requirements.txt || {
                        if [ $? -eq 64 ]; then
                            echo "CRITICAL: Vulnerabilities found in production dependencies!"
                            echo "Pipeline failed due to security vulnerabilities in quiz-app/src/requirements.txt"
                            safety check --file quiz-app/src/requirements.txt --output text
                            exit 1
                        else
                            echo "Safety check failed with unexpected error"
                            exit 1
                        fi
                    }
                '''
                echo 'Dependency vulnerability scan passed!'
            }
            post {
                failure {
                    script {
                        env.PIPELINE_STATUS = "FAILURE"
                    }
                }
            }
        }

        stage('Python Static Security Analysis') {
            steps {
                echo '--------- Running Python static security analysis ---------'
                sh '''
                    # Run Bandit security analysis on Python source code
                    echo "Scanning Python code with Bandit..."
                    bandit -r quiz-app/src/python/ -f json -o bandit-report.json -ll || BANDIT_EXIT_CODE=$?
                    
                    # Display results in human-readable format  
                    echo "Bandit scan results:"
                    bandit -r quiz-app/src/python/ -f txt || true
                    
                    # Check if high/medium severity issues found (exit codes 1-2)
                    if [ "${BANDIT_EXIT_CODE:-0}" -eq 1 ] || [ "${BANDIT_EXIT_CODE:-0}" -eq 2 ]; then
                        echo "CRITICAL: High/Medium severity security issues found in Python code!"
                        echo "Pipeline failed due to Python security vulnerabilities"
                        echo "Fix the security issues above and retry the build"
                        exit 1
                    fi
                '''
                echo 'Python static security analysis passed!'
            }
            post {
                failure {
                    script {
                        env.PIPELINE_STATUS = "FAILURE"
                    }
                }
                always {
                    // Archive the Bandit report for review
                    archiveArtifacts artifacts: 'bandit-report.json', allowEmptyArchive: true
                }
            }
        }

        stage('Dockerfile Security Scan') {
            steps {
                echo '--------- Running Dockerfile security scan ---------'
                sh '''
                    # Run Hadolint security scan on Dockerfile
                    # Check for security issues, best practices, and compliance
                    echo "Scanning Dockerfile with Hadolint..."
                    hadolint --format json quiz-app/Dockerfile > hadolint-report.json || HADOLINT_EXIT_CODE=$?
                    
                    # Display results in human-readable format
                    echo "Hadolint scan results:"
                    hadolint quiz-app/Dockerfile || true
                    
                    # Check if critical/error level issues found
                    if [ "${HADOLINT_EXIT_CODE:-0}" -ne 0 ]; then
                        echo "CRITICAL: Dockerfile security issues found!"
                        echo "Pipeline failed due to Dockerfile security violations"
                        echo "Fix the issues above and retry the build"
                        exit 1
                    fi
                '''
                echo 'Dockerfile security scan passed!'
            }
            post {
                failure {
                    script {
                        env.PIPELINE_STATUS = "FAILURE"
                    }
                }
                always {
                    // Archive the Hadolint report for review
                    archiveArtifacts artifacts: 'hadolint-report.json', allowEmptyArchive: true
                }
            }
        }

        stage('Build Docker Image') {
            steps {
                script {
                    sh '''
                        echo "Connecting to BuildKit DaemonSet..."
                        export BUILDKIT_HOST=tcp://buildkitd.jenkins.svc.cluster.local:1234

                        echo "Building quiz-app image with buildctl..."
                        buildctl --addr ${BUILDKIT_HOST} build \
                            --frontend dockerfile.v0 \
                            --local context=quiz-app \
                            --local dockerfile=quiz-app \
                            --output type=image,name=${DOCKERHUB_CREDENTIALS_USR}/quiz-app:${IMAGE_TAG},push=true
                        
                        echo "Image ${DOCKERHUB_CREDENTIALS_USR}/quiz-app:${IMAGE_TAG} built and pushed"
                    '''
                }
            }
            post {
                failure {
                    script {
                        env.PIPELINE_STATUS = "FAILURE"
                    }
                }
            }
        }


        stage('Update GitOps Repository') {
            steps {
                echo '--------- Updating GitOps Repository ---------'
                script {
                    // Configure git credentials securely using credential helper
                    withCredentials([usernamePassword(credentialsId: 'github-credentials', 
                                                      usernameVariable: 'GIT_USERNAME', 
                                                      passwordVariable: 'GIT_PASSWORD')]) {
                        sh '''
                            # Configure git credential helper for this session
                            git config --global credential.helper store
                            echo "https://${GIT_USERNAME}:${GIT_PASSWORD}@github.com" > ~/.git-credentials
                            
                            ./quiz-app/src/scripts/update-gitops.sh \
                                "${DOCKERHUB_CREDENTIALS_USR}" \
                                "${IMAGE_TAG}" \
                                "${BUILD_NUMBER}" \
                                "${GITHUB_REPO_URL}" \
                                "${GIT_USER_NAME}" \
                                "${GIT_USER_EMAIL}"
                            
                            # Clean up credentials
                            rm -f ~/.git-credentials
                            git config --global --unset credential.helper
                        '''
                    }
                }
            }
            post {
                success {
                    echo "✅ GitOps repository updated successfully"
                    echo "ArgoCD will detect changes and deploy automatically"
                }
                failure {
                    script {
                        env.PIPELINE_STATUS = "FAILURE"
                    }
                    echo "❌ Failed to update GitOps repository"
                }
            }
        }
    }

    post {
        always {
            script {
                def statusIcon = env.PIPELINE_STATUS == "SUCCESS" ? "✅" : "❌"
                def color = env.PIPELINE_STATUS == "SUCCESS" ? "good" : "danger"
                def slackMessage = env.PIPELINE_STATUS == "SUCCESS" ? 
                    "✅ GitOps update completed! Sync ArgoCD to deploy!" : 
                    "❌ Pipeline failed - check logs for details"
                def finalMessage = [
                    "${statusIcon} GitOps Pipeline *${env.JOB_NAME}* #${env.BUILD_NUMBER} ${env.PIPELINE_STATUS}",
                    "",
                    "*Docker Image:* ${env.DOCKERHUB_CREDENTIALS_USR}/quiz-app:${env.IMAGE_TAG}",
                    "*GitOps Repo:* GitHub repository updated",
                    "*Deployment:* ArgoCD will sync automatically", 
                    "${slackMessage}"
                ].join('\n')

                slackSend(
                    channel: '#jenkins',
                    color: color,
                    message: finalMessage
                )
            }

            // Report status back to GitHub using Commit Status API
            script {
                def status = env.PIPELINE_STATUS == "SUCCESS" ? "success" : "failure"
                def description = env.PIPELINE_STATUS == "SUCCESS" ? 
                    "Jenkins build passed" : 
                    "Jenkins build failed"
                    
                sh """
                    curl -X POST \
                        -H "Authorization: token \${GITHUB_TOKEN}" \
                        -H "Accept: application/vnd.github.v3+json" \
                        -H "Content-Type: application/json" \
                        -d '{"state":"${status}","target_url":"${BUILD_URL}","description":"${description}","context":"continuous-integration/jenkins"}' \
                        "https://api.github.com/repos/${GITHUB_REPO}/statuses/${env.GIT_COMMIT}"
                """
            }
        }
    }
}