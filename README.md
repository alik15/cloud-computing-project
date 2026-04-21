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
### Go
cd connector && go test -v ./...

### Django
cd frontend && python manage.py test app --verbosity=2
