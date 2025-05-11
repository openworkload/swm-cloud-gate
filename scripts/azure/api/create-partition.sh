#!/bin/bash

source $(dirname "$0")/helpers.sh

CREDS=$(read_credentials azure)
CERT=/opt/swm/spool/secure/node/cert.pem
KEY=/opt/swm/spool/secure/node/key.pem
CA=/opt/swm/spool/secure/cluster/ca-chain-cert.pem
PEM_DATA=$(make_pem_data $CERT $KEY)

PORT=8444
HOST=$(hostname -f)
REQUEST=POST

# Azure related headers:
HEADER1="Accept: application/json"
HEADER2="subscriptionid: $(echo $CREDS | jq -r '.subscriptionid')"
HEADER3="tenantid: $(echo $CREDS | jq -r '.tenantid')"
HEADER4="appid: $(echo $CREDS | jq -r '.appid')"
HEADER5="containerregistryuser: $(echo $CREDS | jq -r '.containerregistryuser')"
HEADER6="containerregistrypass: $(echo $CREDS | jq -r '.containerregistrypass')"
HEADER7="storage_account: $(echo $CREDS | jq -r '.storage_account')"
HEADER8="storage_key: $(echo $CREDS | jq -r '.storage_key')"
HEADER9="storage_container: $(echo $CREDS | jq -r '.storage_container')"

# Partition related headers:
HEADER10="osversion: ubuntu-hpc/2204"
HEADER11="containerimage: swmregistry.azurecr.io/jupyter/pytorch-notebook:cuda12-hub-5.2.1"
HEADER12="flavorname: Standard_NC24ads_A100_v4"
HEADER13="username: taras"
HEADER14="count: 0"
HEADER15="jobid: 3579a076-9924-11ee-ba53-a3132f7ae2fb"
HEADER16="partname: swm-3579a076"
HEADER17="runtime: swm_source=ssh, ssh_pub_key=ssh-rsa AAAAB3NzaC1yc2EAAAABIwAAAQEA7GA+EAxXl5e7P1FEQOxRwwGroxj4x9G0GKHipGcjaM3PFZ3mONNO7GI3rfK97gB3aRiopePZGYpOfzifq5nfLWvl7gq77UkQd+fZffxrkCprtaA8/VELMZLuvfeJS2PFiF/XugeMjgm+KYVVhL2nYhSuSVO7XCPOd4TmKIBdjvtlIfpMWkaDwZjz+uq4qsDfHBIC+iDXPajXG38Q3aXxQJ3wUhYiTC65gRYmP0a47cCyikudu8AgoCvsiBd6i9oBUucf9c3DzaU3TqakRlNbypMFBftiNIj1VTWVZ5524U8Dug/huESE03C1fdTzXjym2OtadhYaCPfYfLkU/WGUIQ== taras@iclouds.net"
HEADER18="location: eastus2"
HEADER19="ports: 10001,10022"

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
     --header "${HEADER12}"\
     --header "${HEADER13}"\
     --header "${HEADER14}"\
     --header "${HEADER15}"\
     --header "${HEADER16}"\
     --header "${HEADER17}"\
     --header "${HEADER18}"\
     --header "${HEADER19}"\
     --data-raw "${BODY}" \
     ${URL}
echo
