#!/bin/bash

CERT=~/.swm/cert.pem
KEY=~/.swm/key.pem
CA=/opt/swm/spool/secure/cluster/ca-chain-cert.pem

PORT=8444
HOST=$(hostname -s)

REQUEST=POST
HEADER1="Accept: application/json"
HEADER2="username: demo1"
HEADER3="password: demo1"
HEADER4="partname: part1"
HEADER5="tenantname: demo1"
HEADER6="imagename: cirros"
HEADER7="flavorname: m1.micro"
HEADER8="keyname: demo1"
HEADER9="count: 1"
URL="https://${HOST}:${PORT}/openstack/partitions"

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
     ${URL}
echo
