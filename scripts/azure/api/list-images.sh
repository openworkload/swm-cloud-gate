#!/bin/bash

source $(dirname "$0")/helpers.sh

CREDS=$(read_credentials azure)
CERT=~/.swm/cert.pem
KEY=~/.swm/key.pem
CA=/opt/swm/spool/secure/cluster/ca-chain-cert.pem
PEM_DATA=$(make_pem_data $CERT $KEY)

PUBLISHER=Canonical
OFFER=0001-com-ubuntu-server-jammy
#SKUS=22_04-lts

PORT=8444
HOST=$(hostname -s)

REQUEST=GET
HEADER1="Accept: application/json"
HEADER2="subscriptionid: $(echo $CREDS | jq -r '.subscription_id')"
HEADER3="tenantid: $(echo $CREDS | jq -r '.tenant_id')"
HEADER4="appid: $(echo $CREDS | jq -r '.app_id')"
HEADER5="location: $(echo $CREDS | jq -r '.location')"
HEADER6="publisher: ${PUBLISHER}"
HEADER7="offer: ${OFFER}"
HEADER8="skus: ${SKUS}"
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
     --header "${HEADER6}"\
     --header "${HEADER7}"\
     --header "${HEADER8}"\
     --data-raw "${BODY}" \
     ${URL} 2>/dev/null)

echo $json
