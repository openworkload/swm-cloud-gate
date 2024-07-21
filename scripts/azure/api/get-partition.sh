#!/bin/bash

PARTITION_ID=$1
#PARTITION_ID=/subscriptions/3f2fc2c5-8446-4cd5-af2f-a6af7f85ea75/resourceGroups/swm-02ccc5c0-resource-group

source ~/.swm/azure.env
source $(dirname "$0")/helpers.sh

CERT=~/.swm/cert.pem
KEY=~/.swm/key.pem
CA=/opt/swm/spool/secure/cluster/ca-chain-cert.pem
PEM_DATA=$(make_pem_data $CERT $KEY)

PORT=8444
HOST=$(hostname -s)

REQUEST=GET
HEADER1="Accept: application/json"
HEADER2="tenantid: ${TENANT_ID}"
HEADER3="appid: ${APP_ID}"
URL="https://${HOST}:${PORT}/azure/partitions/${PARTITION_ID}"
BODY='{"pem_data": '${PEM_DATA}'}'

curl --request ${REQUEST}\
     --cacert ${CA}\
     --cert ${CERT}\
     --key ${KEY}\
     --header "${HEADER1}"\
     --header "${HEADER2}"\
     --header "${HEADER3}"\
     --data-raw "${BODY}" \
     ${URL}
echo
