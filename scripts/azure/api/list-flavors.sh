#!/bin/bash

source ~/.swm/azure.env
source $(dirname "$0")/helpers.sh

CERT=~/.swm/cert.pem
KEY=~/.swm/key.pem
CA=/opt/swm/spool/secure/cluster/ca-chain-cert.pem
PEM_DATA=$(make_pem_data $CERT $KEY)

LOCATION="eastus"

PORT=8444
HOST=$(hostname -s)

REQUEST=GET
HEADER1="Accept: application/json"
HEADER2="subscriptionid: ${SUBSCRIPTION_ID}"
HEADER3="tenantid: ${TENANT_ID}"
HEADER4="appid: ${APP_ID}"
HEADER5="location: ${LOCATION}"
URL="https://${HOST}:${PORT}/azure/flavors"
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
     --data-raw "${BODY}" \
     ${URL} 2>/dev/null)

table=$(echo "$json" | jq -r '.flavors[] | [.id, .name, .cpus] | @tsv')

id_width=$(echo "$table" | awk -F'\t' '{print length($1)}' | sort -nr | head -1)
name_width=$(echo "$table" | awk -F'\t' '{print length($2)}' | sort -nr | head -1)
cpus_width=$(echo "$table" | awk -F'\t' '{print length($3)}' | sort -nr | head -1)

printf "%-${id_width}s  %-${name_width}s %-${cpus_width}s\n" "ID" "Name" "CPUs"
printf "%${id_width}s  %${name_width}s %${cpus_width}s\n" "$(printf '%*s' "$id_width" | tr ' ' '-')" "$(printf '%*s' "$name_width" | tr ' ' '-')" "$(printf '%*s' "$cpus_width" | tr ' ' '-')"
echo "$table" | while IFS=$'\t' read -r id name; do
    printf "%-${id_width}s  %-${name_width}s %-${cpus_width}s\n" "$id" "$name" "$cpus"
done
