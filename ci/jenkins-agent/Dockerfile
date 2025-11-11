FROM jenkins/inbound-agent:jdk17

# Use root for setup
USER root

# Set shell options for security
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# -----------------------------
# 1. Base system dependencies
# -----------------------------
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        gnupg \
        lsb-release \
        unzip \
        git \
        python3 \
        python3-pip \
        python3-dev \
        build-essential \
        libffi-dev \
        libssl-dev \
        apt-transport-https \
        bc && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# -----------------------------
# 2. Python packages (safe upgrade)
# -----------------------------
RUN python3 -m pip install --no-cache-dir --break-system-packages --upgrade --ignore-installed pip==24.3.1 setuptools==80.9.0 wheel==0.45.1 && \
    pip3 install --no-cache-dir --break-system-packages \
        pytest==8.4.2 \
        pylint==3.3.6 \
        flask==3.1.1 \
        requests==2.32.4 \
        flask-scss==0.5

# -----------------------------
# 2.5. Security tools for DevSecOps exercises
# -----------------------------
RUN pip3 install --no-cache-dir --break-system-packages \
        safety==2.3.5 \
        bandit==1.8.6 \
        --ignore-installed packaging

# Install Cosign and Hadolint binaries
RUN curl -O -L "https://github.com/sigstore/cosign/releases/latest/download/cosign-linux-amd64" && \
    mv cosign-linux-amd64 /usr/local/bin/cosign && \
    chmod +x /usr/local/bin/cosign && \
    curl -sL https://github.com/hadolint/hadolint/releases/latest/download/hadolint-Linux-x86_64 -o /usr/local/bin/hadolint && \
    chmod +x /usr/local/bin/hadolint

# -----------------------------
# 3. Install BuildKit client
# -----------------------------
RUN curl -L https://github.com/moby/buildkit/releases/download/v0.12.0/buildkit-v0.12.0.linux-amd64.tar.gz \
    | tar -xzC /tmp && \
    cp /tmp/bin/buildctl /usr/local/bin/ && \
    chmod +x /usr/local/bin/buildctl && \
    rm -rf /tmp/bin /tmp/buildkit-v0.12.0.linux-amd64.tar.gz

# -----------------------------
# 4. Install AWS CLI v2
# -----------------------------
RUN curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip" && \
    unzip awscliv2.zip && \
    ./aws/install && \
    rm -rf aws awscliv2.zip

# -----------------------------
# 5. Install kubectl CLI
# -----------------------------
RUN curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl" && \
    install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl && \
    rm kubectl

# -----------------------------
# 6. Install Helm CLI (direct binary)
# -----------------------------
RUN curl -fsSL -o get_helm.sh https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 && \
    chmod 700 get_helm.sh && \
    ./get_helm.sh && \
    rm get_helm.sh

# -----------------------------
# 7. Install Docker CLI (for cosign authentication)
# -----------------------------
RUN curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg && \
    echo "deb [arch=amd64 signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/debian bullseye stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null && \
    apt-get update && \
    apt-get install -y --no-install-recommends docker-ce-cli && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# -----------------------------
# 8. Environment setup
# -----------------------------
ENV PATH="/usr/local/bin:${PATH}"

# Ensure jenkins home exists and permissions are correct
RUN mkdir -p /home/jenkins && chown -R jenkins:jenkins /home/jenkins

# Verify installed tools as Jenkins user
RUN chown jenkins:jenkins /usr/local/bin/buildctl && \
    su - jenkins -c "buildctl --version" && \
    su - jenkins -c "aws --version" && \
    su - jenkins -c "kubectl version --client" && \
    su - jenkins -c "helm version --client" && \
    su - jenkins -c "git --version"

# -----------------------------
# 8. Final setup
# -----------------------------
USER 1000
WORKDIR /home/jenkins

# Start Jenkins agent (inherited from base image)
ENTRYPOINT ["/usr/local/bin/jenkins-agent"]