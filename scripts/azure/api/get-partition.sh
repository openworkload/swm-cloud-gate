#!/bin/bash

PARTITION_ID=$1
#PARTITION_ID=/subscriptions/3f2fc2c5-8446-4cd5-af2f-a6af7f85ea75/resourceGroups/swm-02ccc5c0-resource-group

source $(dirname "$0")/helpers.sh

CREDS=$(read_credentials azure)
CERT=~/.swm/cert.pem
KEY=~/.swm/key.pem
CA=/opt/swm/spool/secure/cluster/ca-chain-cert.pem
PEM_DATA=$(make_pem_data $CERT $KEY)

PORT=8444
HOST=$(hostname -s)

REQUEST=GET
HEADER1="Accept: application/json"
HEADER2="tenantid: $(echo $CREDS | jq -r '.tenant_id')"
HEADER3="appid: $(echo $CREDS | jq -r '.app_id')"
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
