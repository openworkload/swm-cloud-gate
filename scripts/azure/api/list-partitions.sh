#!/bin/bash

PARTIOTION_ID=$1
#PARTITION_ID=/subscriptions/3f2fc2c5-8446-4cd5-af2f-a6af7f85ea75/resourceGroups/swm-02ccc5c0-resource-group

source $(dirname "$0")/helpers.sh

CERT=/opt/swm/spool/secure/node/cert.pem
KEY=/opt/swm/spool/secure/node/key.pem
CA=/opt/swm/spool/secure/cluster/ca-chain-cert.pem
PEM_DATA=$(make_pem_data $CERT $KEY)

PORT=8444
HOST=$(hostname -f)

REQUEST=GET
HEADER1="Accept: application/json"
URL="https://${HOST}:${PORT}/azure/partitions"
BODY='{"pem_data": '${PEM_DATA}'}'

curl --request ${REQUEST}\
     --cacert ${CA}\
     --cert ${CERT}\
     --key ${KEY}\
     --header "${HEADER1}"\
     --data-raw "${BODY}" \
     ${URL}
echo
