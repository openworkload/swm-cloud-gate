#!/bin/bash

source ~/.swm/azure.env
source $(dirname "$0")/helpers.sh

CERT=~/.swm/cert.pem
KEY=~/.swm/key.pem
CA=/opt/swm/spool/secure/cluster/ca-chain-cert.pem
PEM_DATA=$(make_pem_data $CERT $KEY)

PORT=8444
HOST=$(hostname -s)

REQUEST=POST
HEADER1="Accept: application/json"
HEADER2="subscriptionid: ${SUBSCRIPTION_ID}"
HEADER3="tenantid: ${TENANT_ID}"
HEADER4="appid: ${APP_ID}"
HEADER5="vmimage: /Subscriptions/${SUBSCRIPTION_ID}/Providers/Microsoft.Compute/Locations/eastus/Publishers/Canonical/ArtifactTypes/VMImage/Offers/0001-com-ubuntu-server-jammy/Skus/22_04-lts/Versions/22.04.202407160"
HEADER6="containerimage: swmregistry.azurecr.io/jupyter/datascience-notebook:hub-3.1.1"
HEADER7="flavorname: Standard_B2s"
HEADER8="username: taras"
HEADER9="count: 0"
HEADER10="jobid: 3579a076-9924-11ee-ba53-a3132f7ae2fb"
HEADER11="runtime: swm_source=ssh, ssh_pub_key=ssh-rsa AAAAB3NzaC1yc2EAAAABIwAAAQEA7GA+EAxXl5e7P1FEQOxRwwGroxj4x9G0GKHipGcjaM3PFZ3mONNO7GI3rfK97gB3aRiopePZGYpOfzifq5nfLWvl7gq77UkQd+fZffxrkCprtaA8/VELMZLuvfeJS2PFiF/XugeMjgm+KYVVhL2nYhSuSVO7XCPOd4TmKIBdjvtlIfpMWkaDwZjz+uq4qsDfHBIC+iDXPajXG38Q3aXxQJ3wUhYiTC65gRYmP0a47cCyikudu8AgoCvsiBd6i9oBUucf9c3DzaU3TqakRlNbypMFBftiNIj1VTWVZ5524U8Dug/huESE03C1fdTzXjym2OtadhYaCPfYfLkU/WGUIQ== taras@iclouds.net"
HEADER12="ports: 10001,10022"

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
     --data-raw "${BODY}" \
     ${URL}
echo
