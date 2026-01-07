# Goal
Create a helper helm chart and service with an accompanying Dockerfile to allow for the declaritive bootstrapping of a garage cluster. I am including the garage source code as a submodule for reference. 

## Output
The helm chart should:
1. Allow for declarative bucket creation with accompanying accounts and acces keys

The service should:
1. Connect to the cluster using port 3901 for rpc-based admin access
2. Include common utilities including curl, /bin/bash, python (to test connection)
3. Do the actual bootstrapping including creating a layout and buckets/users/keys
4. Include python scripts (pytest) where I can test connectivity by passing a bucket, username (access key), password (secret key), and optionally region. I would like seprate scripts based on the following python libraries:
    - Minio
    - S3
    - Azure Blob store
5. Include a data loader/data exporter function so I can back up all objects in the object store at the application level rather than relying on PVCs
6. Include a test that can see if all actions expected can be done using all 3 of the previously stated libraries (pytest)
7. Include a multistage test to allow for testing data persistence between garage pods being restarted


## Format
Include all of the service code under a garage_bootstrap/ dir and the helm chart under a chart/ dir. Update the README.md and include any other documentation needed that you would find relevant.