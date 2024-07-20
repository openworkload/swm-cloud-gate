#!/bin/bash

IMAGE_ID=$1
#IMAGE_ID=/Subscriptions/3f2fc2c5-8446-4cd5-af2f-a6af7f85ea75/Providers/Microsoft.Compute/Locations/eastus/Publishers/Canonical/ArtifactTypes/VMImage/Offers/0001-com-ubuntu-server-jammy/Skus/22_04-lts/Versions/22.04.202407010

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
HEADER2="subscriptionid: ${SUBSCRIPTION_ID}"
HEADER3="tenantid: ${TENANT_ID}"
HEADER4="appid: ${APP_ID}"
URL="https://${HOST}:${PORT}/azure/images${IMAGE_ID}"
BODY='{"pem_data": '${PEM_DATA}'}'

echo $URL
echo

json=$(curl --request ${REQUEST}\
     --cacert ${CA}\
     --cert ${CERT}\
     --key ${KEY}\
     --header "${HEADER1}"\
     --header "${HEADER2}"\
     --header "${HEADER3}"\
     --header "${HEADER4}"\
     --data-raw "${BODY}" \
     ${URL} 2>/dev/null)

echo $json
