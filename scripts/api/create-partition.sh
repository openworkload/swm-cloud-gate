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
HEADER9="count: 0"
HEADER10="jobid: 3579a076-9924-11ee-ba53-a3132f7ae2fb"
HEADER11="runtime: swm_source=http://10.0.2.15/swm-worker.tar.gz"
HEADER12="ports: 10001,10022"
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
     --header "${HEADER10}"\
     --header "${HEADER11}"\
     --header "${HEADER12}"\
     ${URL}
echo
