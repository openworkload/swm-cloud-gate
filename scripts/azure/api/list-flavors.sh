#!/bin/bash

source $(dirname "$0")/helpers.sh

CREDS=$(read_credentials azure)
CERT=$HOME/.swm/spool/secure/node/cert.pem
KEY=$HOME/.swm/spool/secure/node/key.pem
CA=$HOME/.swm/spool/secure/cluster/ca-chain-cert.pem
PEM_DATA=$(make_pem_data $CERT $KEY)

PORT=8444
HOST=$(hostname -s)

REQUEST=GET
HEADER1="Accept: application/json"
HEADER2="subscriptionid: $(echo $CREDS | jq -r '.subscriptionid')"
HEADER3="tenantid: $(echo $CREDS | jq -r '.tenantid')"
HEADER4="appid: $(echo $CREDS | jq -r '.appid')"
HEADER5="extra: location=eastus"
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

table=$(echo "$json" | jq -r '.flavors[] | [.id, .name, .cpus, .price] | @tsv')

id_width=$(echo "$table" | awk -F'\t' '{print length($1)}' | sort -nr | head -1)
name_width=$(echo "$table" | awk -F'\t' '{print length($2)}' | sort -nr | head -1)
cpus_width=$(echo "$table" | awk -F'\t' '{print length($3)}' | sort -nr | head -1)
price_width=$(echo "$table" | awk -F'\t' '{print length($4)}' | sort -nr | head -1)

printf "%-${id_width}s  %-${name_width}s %-${cpus_width}s %-${price_width}s\n" "ID" "Name" "CPUs" "Price"
printf "%${id_width}s  %${name_width}s %${cpus_width}s %${price_width}s\n" "$(printf '%*s' "$id_width" | tr ' ' '-')" "$(printf '%*s' "$name_width" | tr ' ' '-')" "$(printf '%*s' "$cpus_width" | tr ' ' '-')" "$(printf '%*s' "$price_width" | tr ' ' '-')"
echo "$table" | while IFS=$'\t' read -r id name cpus price; do
    printf "%-${id_width}s  %-${name_width}s %-${cpus_width}s %-${price_width}s\n" "$id" "$name" "$cpus" "$price"
done
