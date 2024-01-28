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
HEADER11="runtime: swm_source=ssh, ssh_pub_key=ssh-rsa AAAAB3NzaC1yc2EAAAABIwAAAQEA7GA+EAxXl5e7P1FEQOxRwwGroxj4x9G0GKHipGcjaM3PFZ3mONNO7GI3rfK97gB3aRiopePZGYpOfzifq5nfLWvl7gq77UkQd+fZffxrkCprtaA8/VELMZLuvfeJS2PFiF/XugeMjgm+KYVVhL2nYhSuSVO7XCPOd4TmKIBdjvtlIfpMWkaDwZjz+uq4qsDfHBIC+iDXPajXG38Q3aXxQJ3wUhYiTC65gRYmP0a47cCyikudu8AgoCvsiBd6i9oBUucf9c3DzaU3TqakRlNbypMFBftiNIj1VTWVZ5524U8Dug/huESE03C1fdTzXjym2OtadhYaCPfYfLkU/WGUIQ== taras@iclouds.net"
HEADER12="ports: 10001,10022"
HEADER13="containerimage: 172.28.128.2:6006/jupyter/datascience-notebook:hub-3.1.1"
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
     --header "${HEADER13}"\
     ${URL}
echo
