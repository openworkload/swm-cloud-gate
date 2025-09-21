#!/bin/bash

source $(dirname "$0")/helpers.sh

CERT=/opt/swm/spool/secure/node/cert.pem
KEY=/opt/swm/spool/secure/node/key.pem
CA=/opt/swm/spool/secure/cluster/ca-chain-cert.pem
PEM_DATA=$(make_pem_data $CERT $KEY)

PORT=8444
HOST=$(hostname -f)
REQUEST=POST

HEADER1="Accept: application/json"
HEADER2="osversion: ubuntu-hpc/2204"
HEADER3="containerimage: swmregistry.azurecr.io/jupyter/pytorch-notebook:cuda12-hub-5.2.1"
HEADER4="flavorname: Standard_NC24ads_A100_v4"
HEADER5="username: taras"
HEADER6="count: 0"
HEADER7="jobid: 3579a076-9924-11ee-ba53-a3132f7ae2fb"
HEADER8="partname: swm-3579a076"
HEADER9="runtime: swm_source=ssh"
HEADER10="location: eastus2"
HEADER11="ports: 10001,10022"

URL="https://${HOST}:${PORT}/azure/partitions"
BODY='{"pem_data": '${PEM_DATA}'}'

curl --request ${REQUEST}\
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
     --header "${HEADER9}"\
     --header "${HEADER10}"\
     --header "${HEADER11}"\
     --data-raw "${BODY}" \
     ${URL}
echo
