#!/bin/bash

IMAGE_ID=$1
#IMAGE_ID=/Subscriptions/3f2fc2c5-8446-4cd5-af2f-a6af7f85ea75/Providers/Microsoft.Compute/Locations/eastus/Publishers/Canonical/ArtifactTypes/VMImage/Offers/0001-com-ubuntu-server-jammy/Skus/22_04-lts/Versions/22.04.202407010

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
HEADER2="subscriptionid: $(echo $CREDS | jq -r '.subscription_id')"
HEADER3="tenantid: $(echo $CREDS | jq -r '.tenant_id')"
HEADER4="appid: $(echo $CREDS | jq -r '.app_id')"
URL="https://${HOST}:${PORT}/azure/images/${IMAGE_ID}"
BODY='{"pem_data": '${PEM_DATA}'}'

echo $URL
echo

echo $HEADER2
echo $HEADER3
echo $HEADER4

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
