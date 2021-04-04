#!/bin/bash

PARTIOTION_ID=$1

CERT=~/.swm/cert.pem
KEY=~/.swm/key.pem
CA=/opt/swm/spool/secure/cluster/ca-chain-cert.pem

PORT=8444
HOST=$(hostname -s)

REQUEST=DELETE
HEADER1="Accept: application/json"
HEADER2="username: demo1"
HEADER3="password: demo1"
URL="https://${HOST}:${PORT}/openstack/partitions/$PARTIOTION_ID"

curl --request ${REQUEST}\
     --cacert ${CA}\
     --cert ${CERT}\
     --key ${KEY}\
     --header "${HEADER1}"\
     --header "${HEADER2}"\
     --header "${HEADER3}"\
     ${URL}
echo
