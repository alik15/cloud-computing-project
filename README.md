# Reel Keeper

A 3-pod Kubernetes application stack:
- **PostgreSQL** — database
- **Go Connector** — REST API / DB middleware
- **Django Frontend** — HTML UI


## To Do List
- [x] Input sanitization for forms
- [x] User accounts
- [x] Scaling 
- [x] Enable logging on application
- [x] Define Limits and requests of each pod considering the size of the cluster
- [x] Local Tests
- [x] GitHub Automatic CI/CD

## Structure

```
k8s-app/
├── k8s/
│   ├── postgres/
│   │   ├── configmap.yaml
│   │   ├── secret.yaml
│   │   ├── pvc.yaml
│   │   └── deployment.yaml
│   ├── connector/
│   │   ├── configmap.yaml
│   │   └── deployment.yaml
│   └── frontend/
│       ├── configmap.yaml
│       └── deployment.yaml
├── connector/          # Go source
│   ├── main.go
│   ├── go.mod
│   └── Dockerfile
└── frontend/           # Django source
    ├── manage.py
    ├── requirements.txt
    ├── Dockerfile
    ├── app/
    └── templates/
```

## Quick Start (Local k3s)

### 1. Build & Push Images

```bash
# Go connector
cd connector
docker build -t YOUR_DOCKERHUB/connector:v1 .
docker push YOUR_DOCKERHUB/connector:v1

# Django frontend
cd ../frontend
docker build -t YOUR_DOCKERHUB/frontend:v1 .
docker push YOUR_DOCKERHUB/frontend:v1
```

### 2. Edit image names in k8s manifests

In `k8s/connector/deployment.yaml` and `k8s/frontend/deployment.yaml`,
replace `YOUR_DOCKERHUB` with your Docker Hub username.

### 3. Deploy 

```bash
# Namespace
kubectl apply -f k8s/namespace.yaml

# PostgreSQL
kubectl apply -f k8s/postgres/

# Wait for postgres to be ready
kubectl wait --for=condition=ready pod -l app=postgres -n appns --timeout=60s

# Connector
kubectl apply -f k8s/connector/

# Frontend
kubectl apply -f k8s/frontend/
```

### 4. Access the app

```bash
kubectl get svc -n appns
# The frontend NodePort will be on port 30080
# Open http://<your-k3s-node-ip>:30080
```

### Tear Down

```bash
kubectl delete namespace appns
```

## Services (internal DNS)

| Service     | DNS name                    | Port |
|-------------|-----------------------------|------|
| PostgreSQL  | postgres-svc.appns.svc.cluster.local | 5432 |
| Go Connector| connector-svc.appns.svc.cluster.local | 8080 |
| Django      | frontend-svc.appns.svc.cluster.local  | 8000 |



## Tests
```
Go
cd connector && go test -v ./...

Django
cd frontend && python manage.py test app --verbosity=2
```

## Steps for Deployment on Gcloud
```
1. Set project
gcloud config set project cloud-computing-project-ali

2. Create clusters
gcloud container clusters create dev-cluster \
  --zone=us-central1-a \
  --num-nodes=2 \
  --machine-type=e2-small \
  --disk-size=20

gcloud container clusters create prod-cluster \
  --zone=us-central1-a \
  --num-nodes=2 \
  --machine-type=e2-small \
  --disk-size=20

3. Create Artifact Registry
gcloud artifacts repositories create gke-repo \
  --repository-format=docker \
  --location=us-central1

4. Grant Cloud Build permissions
PROJECT_NUMBER=$(gcloud projects describe cloud-computing-project-ali --format='value(projectNumber)')

gcloud projects add-iam-policy-binding cloud-computing-project-ali \
  --member="serviceAccount:$PROJECT_NUMBER@cloudbuild.gserviceaccount.com" \
  --role="roles/clouddeploy.operator"

gcloud projects add-iam-policy-binding cloud-computing-project-ali \
  --member="serviceAccount:$PROJECT_NUMBER@cloudbuild.gserviceaccount.com" \
  --role="roles/container.developer"

gcloud projects add-iam-policy-binding cloud-computing-project-ali \
  --member="serviceAccount:$PROJECT_NUMBER@cloudbuild.gserviceaccount.com" \
  --role="roles/iam.serviceAccountUser"

gcloud projects add-iam-policy-binding cloud-computing-project-ali \
  --member="serviceAccount:$PROJECT_NUMBER@cloudbuild.gserviceaccount.com" \
  --role="roles/artifactregistry.writer"

5. Push to trigger pipeline
git add .
git commit -m "redeploy"
git push origin main

6. Watch build logs
gcloud builds log $(gcloud builds list --limit=1 --format='value(id)') --stream

7. Point kubectl at dev cluster
gcloud container clusters get-credentials dev-cluster \
  --zone=us-central1-a \
  --project=cloud-computing-project-ali

8. Watch pods come up
kubectl get pods -n appns -w

9. Patch frontend to LoadBalancer
kubectl patch svc frontend-svc -n appns \
  -p '{"spec": {"type": "LoadBalancer"}}'

10. Get external IP
kubectl get svc frontend-svc -n appns -w
```
