# garage_bootstrap

Garage is currently being evaluated to serve as a MinIO replacement following MinIO's decision to pivot towards a paid model

# Pros of Garage
- Garage is more latency resistent than MinIO due to it's write now, reconcile later style
- Free
- Much less maintenance/maangement complexity than Rook-based ObjectStore provisioning

# Cons of Garage
- Default docker container build is VERY low footprint: no /bin/bash, grep, cat, ls, anything to be able to interact with a pod in it's target environment
- Helm chart does not have a 'bootstrapping' function where pre-made buckets and accounts can be created declaritively which massively inhibits it's capability to be used within GitOps