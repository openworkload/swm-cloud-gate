#!/bin/bash

source $(dirname "$0")/helpers.sh

CREDS=$(read_credentials azure)
CERT=/opt/swm/spool/secure/node/cert.pem
KEY=/opt/swm/spool/secure/node/key.pem
CA=/opt/swm/spool/secure/cluster/ca-chain-cert.pem
PEM_DATA=$(make_pem_data $CERT $KEY)

PUBLISHER=microsoft-dsvm
OFFER=ubuntu-hpc
#SKUS=2204

PORT=8444
HOST=$(hostname -s)

REQUEST=GET
HEADER1="Accept: application/json"
HEADER2="subscriptionid: $(echo $CREDS | jq -r '.subscriptionid')"
HEADER3="tenantid: $(echo $CREDS | jq -r '.tenantid')"
HEADER4="appid: $(echo $CREDS | jq -r '.appid')"
HEADER5="extra: location=eastus;publisher=${PUBLISHER};offer=${OFFER};skus=${SKUS}"
URL="https://${HOST}:${PORT}/azure/images"
BODY='{"pem_data": '${PEM_DATA}'}'

json=$(curl --request ${REQUEST}\
     --cacert ${CA}\
     --cert ${CERT}\
     --key ${KEY}\
     --header "${HEADER1}"\
     --header "${HEADER2}"\
     --header "${HEADER3}"\
     --header "${HEADER4}"\
     --header "${HEADER5}"\
     --data-raw "${BODY}" \
     ${URL} 2>/dev/null)

echo $json
