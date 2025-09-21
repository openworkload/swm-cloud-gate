#!/bin/bash

source $(dirname "$0")/helpers.sh

CERT=/opt/swm/spool/secure/node/cert.pem
KEY=/opt/swm/spool/secure/node/key.pem
CA=/opt/swm/spool/secure/cluster/ca-chain-cert.pem
PEM_DATA=$(make_pem_data $CERT $KEY)

PORT=8444
HOST=$(hostname -f)

REQUEST=GET
HEADER1="Accept: application/json"
HEADER2="extra: location=eastus2"
URL="https://${HOST}:${PORT}/azure/images"
BODY='{"pem_data": '${PEM_DATA}'}'

json=$(curl --request ${REQUEST}\
     --cacert ${CA}\
     --cert ${CERT}\
     --key ${KEY}\
     --header "${HEADER1}"\
     --header "${HEADER2}"\
     --data-raw "${BODY}" \
     ${URL} 2>/dev/null)

echo $json
