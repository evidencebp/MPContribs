#!/bin/bash

supervisorctl start api

echo "METADATA URI: ${METADATA_URI}"

if [ -z "${METADATA_URI}" ]; then
    # in docker-compose stack with one task
    supervisorctl start worker
    supervisorctl start scheduler
else
    # in AWS Fargate with potentially multiple tasks
    echo "PINGING ${METADATA_URI}"
    http ${METADATA_URI}
    supervisorctl start worker
    supervisorctl start scheduler
fi

