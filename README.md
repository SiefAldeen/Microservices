# Microservices Deployment Guide

This guide documents the complete process of deploying a Flask microservice application to Azure Kubernetes Service (AKS) with CI/CD automation and comprehensive monitoring using Prometheus and Grafana.

## Project Overview

This project demonstrates a complete DevOps workflow including:
- Containerization of a Python Flask application
- Infrastructure as Code using Terraform
- Kubernetes orchestration on Azure (AKS)
- Automated CI/CD pipeline with GitHub Actions
- Monitoring stack with Prometheus and Grafana
- Auto-scaling and health checks

## Architecture Overview

The deployment architecture consists of:
- **Application Layer**: Flask microservice containerized with Docker
- **Container Registry**: Azure Container Registry (ACR) for image storage
- **Orchestration**: Azure Kubernetes Service (AKS) for container orchestration
- **CI/CD**: GitHub Actions for automated build and deployment
- **Monitoring**: Prometheus for metrics collection and Grafana for visualization
- **Networking**: LoadBalancer service for external access

## Prerequisites

Before starting, ensure you have the following installed and configured:

- **Azure CLI** - For Azure resource management
- **Docker** - For containerization
- **kubectl** - For Kubernetes cluster interaction
- **Terraform** - For infrastructure provisioning
- **Helm** - For Kubernetes package management
- **Git** - For version control
- **GitHub Account** - With repository access and Actions enabled

## Table of Contents
- [Initial Setup](#initial-setup)
- [Docker Configuration](#docker-configuration)
- [Azure Container Registry Setup](#azure-container-registry-setup)
- [Kubernetes Deployment](#kubernetes-deployment)
- [Monitoring Setup](#monitoring-setup)
- [CI/CD Pipeline Implementation](#cicd-pipeline-implementation)
- [Access Information](#access-information)

---

## Initial Setup

### 1. Clone the Repository
```bash
git clone https://github.com/sameh-Tawfiq/Microservices
cd Microservices
```

---

## Docker Configuration

### 2. Application Modifications

Made the following changes to ensure proper Docker deployment:

- **Updated `requirements.txt`**: Upgraded Flask to version 2.3.3 to resolve compatibility issues with Werkzeug
  ```
  Flask==2.3.3
  ```

- **Modified `run.py`**: Changed host configuration to allow external connections (not just localhost 127.0.0.1)
  ```python
  app.run(host='0.0.0.0', port=5000)
  ```

- **Added status endpoint** in `__init__.py`: Created `/status` endpoint for health monitoring and liveness/readiness probes
  ```python
    @app.get("/status")
    def status():
        return jsonify(status="ok"), 200
  ```

### 3. Create Docker Files

Created the following files:
- `Dockerfile` - Container image definition with multi-stage build
- `.dockerignore` - Files to exclude from Docker build context (e.g., `.git`)

### 4. Build and Test Docker Image

```bash
# Build the Docker image
docker build -t microservice .

# Run the container locally for testing
docker run -d -p 5000:5000 microservice

# Test the application
curl http://localhost:5000
curl http://localhost:5000/status

# Stop the container
docker stop $(docker ps -q --filter ancestor=microservice)
```

---

## Azure Container Registry Setup

### 5. Install Azure CLI

```bash
curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash
```

### 6. Login to Azure

```bash
az login --use-device-code
```

Follow the prompts to authenticate with your Azure account.

### 7. Create and Push to ACR

Created Azure Container Registry named `pwctask`:

```bash
# Build and tag the image
docker build -t microservice:v1 .
docker tag microservice:v1 pwctask.azurecr.io/microservice:v1

# Login to ACR
az acr login --name pwctask

# Push to ACR
docker push pwctask.azurecr.io/microservice:v1

# Verify the image was pushed successfully
az acr repository list --name pwctask
az acr repository show-tags --name pwctask --repository microservice
```

---

## Kubernetes Deployment

### 8. Install Terraform

```bash
wget -O - https://apt.releases.hashicorp.com/gpg | sudo gpg --dearmor -o /usr/share/keyrings/hashicorp-archive-keyring.gpg

echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] https://apt.releases.hashicorp.com $(grep -oP '(?<=UBUNTU_CODENAME=).*' /etc/os-release || lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/hashicorp.list

sudo apt update && sudo apt install terraform

# Verify installation
terraform -v
```

### 9. Provision AKS Cluster

Created `main.tf` to define the AKS cluster infrastructure with the following specifications:
- Resource Group: `Microservices`
- Cluster Name: `pwctask-aks`
- Node Count: 2
- VM Size: Standard_DS2_v2
- Region: UAE North 

```bash
# Initialize Terraform
terraform init

# Validate configuration
terraform validate

# Preview changes
terraform plan

# Apply configuration
terraform apply

# Confirm with 'yes' when prompted
```

This creates an AKS cluster named `pwctask-aks` in the `Microservices` resource group.

### 10. Connect to AKS Cluster

```bash
# Get cluster credentials
az aks get-credentials --resource-group Microservices --name pwctask-aks

# Verify connection
kubectl get nodes
kubectl cluster-info

# View cluster details
kubectl get all --all-namespaces
```

### 11. Deploy Application

```bash
# Deploy the service first (LoadBalancer type for external access)
kubectl apply -f service.yaml

# Deploy the application with replicas
kubectl apply -f deployment.yaml

# Verify deployment
kubectl get deployments
kubectl get pods
kubectl get services

# Wait for LoadBalancer external IP
kubectl get service microservice-service --watch
```

---

## Monitoring Setup

### 12. Install Helm

```bash
curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash

# Verify installation
helm version
```

### 13. Install Prometheus and Grafana

```bash
# Add Helm repositories
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo add grafana https://grafana.github.io/helm-charts
helm repo update

# Install Prometheus stack with Grafana (includes both tools)
helm install prometheus prometheus-community/kube-prometheus-stack \
  --namespace monitoring \
  --create-namespace \
  --set prometheus.service.type=LoadBalancer \
  --set grafana.service.type=LoadBalancer

# Verify installation
kubectl get pods -n monitoring
kubectl get svc -n monitoring
```

### 14. Retrieve Grafana Admin Password

```bash
kubectl --namespace monitoring get secrets prometheus-grafana -o jsonpath="{.data.admin-password}" | base64 -d ; echo
```

> **Important**: Save this password for Grafana login (username: `admin`)

### 15. Configure Blackbox Exporter

Install Blackbox Exporter for HTTP endpoint monitoring:

```bash
helm upgrade --install blackbox-exporter prometheus-community/prometheus-blackbox-exporter \
  --namespace monitoring \
  --set serviceMonitor.enabled=true

# Verify installation
kubectl get pods -n monitoring | grep blackbox
```

### 16. Configure Prometheus Scraping

Create `prometheus-fix.yaml` to configure endpoint monitoring for your application:

```yaml
prometheus:
  prometheusSpec:
    additionalScrapeConfigs:
      - job_name: 'endpoint-status'
        metrics_path: /probe
        params:
          module: [http_2xx]
        static_configs:
          - targets:
              - http://40.120.114.118/status  # Replace with your service IP
        relabel_configs:
          - source_labels: [__address__]
            target_label: __param_target
          - source_labels: [__param_target]
            target_label: instance
          - target_label: __address__
            replacement: blackbox-exporter-prometheus-blackbox-exporter.monitoring.svc.cluster.local:9115
```

Update Prometheus configuration:

```bash
helm upgrade prometheus prometheus-community/kube-prometheus-stack \
  --namespace monitoring \
  -f prometheus-fix.yaml

# Restart Prometheus pods to apply changes
kubectl rollout restart statefulset prometheus-prometheus-kube-prometheus-prometheus -n monitoring
```

### 17. Configure Grafana Dashboard

Created a custom dashboard in Grafana to monitor the application using the following metrics:

**Key Metrics:**
- `probe_success{instance="http://40.120.114.118/status"}` - Endpoint availability (1=up, 0.5=down)
- `probe_http_status_code{instance="http://40.120.114.118/status"}` - HTTP response codes
- `probe_duration_seconds{instance="http://40.120.114.118/status"}` - Response time in seconds

---

## CI/CD Pipeline Implementation

### Overview
Implemented a GitHub Actions CI/CD pipeline that automates the build, push, and deployment process for containerized applications to Azure Kubernetes Service (AKS). The pipeline includes automatic image versioning with incremental tagging (v1, v2, v3, etc.).

### 18. Enable ACR Admin Access

First, enable admin access on the Azure Container Registry to allow authentication:

```bash
az acr update -n pwctask --admin-enabled true
```

### 19. Retrieve ACR Credentials

Query the admin username:
```bash
az acr credential show --name pwctask --query username --output tsv
```

Query the admin password:
```bash
az acr credential show --name pwctask --query passwords[0].value --output tsv
```

Verify admin user is enabled:
```bash
az acr show --name pwctask --query adminUserEnabled
```

### 20. Set Environment Variables

Get your Azure subscription ID:
```bash
SUBSCRIPTION_ID=$(az account show --query id -o tsv)
echo $SUBSCRIPTION_ID
```

Set your resource group name:
```bash
RESOURCE_GROUP="Microservices"
```

Set your AKS cluster name:
```bash
AKS_CLUSTER="pwctask-aks"
```

### 21. Create Service Principal for GitHub Actions

Create a service principal with contributor role for CI/CD operations:

```bash
az ad sp create-for-rbac \
  --name "github-actions-cicd" \
  --role contributor \
  --scopes /subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP \
  --sdk-auth
```

> **Important**: Save the complete JSON output - you'll need it for GitHub secrets configuration. The output will look like:
```json
{
  "clientId": "xxx",
  "clientSecret": "xxx",
  "subscriptionId": "xxx",
  "tenantId": "xxx",
  ...
}
```

### 22. Configure ACR Permissions

Retrieve the Service Principal Client ID from the previous output and set it:
```bash
SP_CLIENT_ID="<your-service-principal-client-id>"
```

Get the ACR resource ID:
```bash
ACR_ID=$(az acr show --name pwctask --resource-group Microservices --query id -o tsv)
echo $ACR_ID
```

Assign ACR Pull role to the service principal:
```bash
az role assignment create \
  --assignee $SP_CLIENT_ID \
  --role AcrPull \
  --scope $ACR_ID
```

Assign ACR Push role to the service principal:
```bash
az role assignment create \
  --assignee $SP_CLIENT_ID \
  --role AcrPush \
  --scope $ACR_ID
```

Verify role assignments:
```bash
az role assignment list --assignee $SP_CLIENT_ID --output table
```

### 23. Configure AKS Permissions

Assign Kubernetes cluster user role for deployment operations:

```bash
az role assignment create \
  --assignee $SP_CLIENT_ID \
  --role "Azure Kubernetes Service Cluster User Role" \
  --scope /subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP/providers/Microsoft.ContainerService/managedClusters/$AKS_CLUSTER
```

### 24. Configure GitHub Secrets and Variables

Navigate to your GitHub repository settings and add the following:

**Secrets** (Settings → Secrets and variables → Actions → New repository secret):
- `AZURE_CREDENTIALS`: The complete JSON output from the service principal creation
- `ACR_PASSWORD`: The ACR admin password retrieved earlier
- `ACR_USERNAME`: The ACR admin username

**Variables** (Settings → Secrets and variables → Actions → New repository variable):
- `ACR_NAME`: `pwctask`
- `ACR_LOGIN_SERVER`: `pwctask.azurecr.io`
- `RESOURCE_GROUP`: `Microservices`
- `AKS_CLUSTER`: `pwctask-aks`
- `NAMESPACE`: `default`
- `IMAGE_NAME`: `microservice`
- `DEPLOYMENT_NAME`: `microservice`

### 25. Create GitHub Actions Workflow

Create `.github/workflows/main.yml` with the CI/CD pipeline configuration.

The pipeline includes:

**Auto-Incrementing Version Tags:**
- Automatically generates version tags (v1, v2, v3, etc.)
- Retrieves the latest tag from ACR
- Increments version number for each build
- Tags images consistently across all deployments

**Build and Push Process:**
- Builds Docker images from source code
- Pushes images to Azure Container Registry
- Tags images with incremental version numbers
- Maintains image history in ACR

**Automated Deployment:**
- Updates Kubernetes deployment manifests with new image tags
- Applies changes to the AKS cluster
- Performs basic deployment verification
- Confirms pods are running successfully

### 26. Pipeline Triggers

The pipeline triggers on:
- Push to `main` branch
- Pull requests to `main` branch

### Pipeline Development Process

The pipeline was developed and tested through multiple iterations to ensure:
- Proper authentication with Azure services
- Correct image tagging and versioning
- Successful deployment to AKS
- Reliable verification steps
- Error handling and rollback capabilities

---

---

## Access Information

### Application Access
- **Application Main URL**: `http://40.120.114.118`
- **Health Check Endpoint**: `http://40.120.114.118/status`
- **Expected Response**: JSON with status information


### Monitoring Access

**Grafana Dashboard:**
- **URL**: `http://20.174.216.100:380`
