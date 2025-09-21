#!/bin/bash

source $(dirname "$0")/helpers.sh

CERT=$HOME/.swm/spool/secure/node/cert.pem
KEY=$HOME/.swm/spool/secure/node/key.pem
CA=$HOME/.swm/spool/secure/cluster/ca-chain-cert.pem
PEM_DATA=$(make_pem_data $CERT $KEY)

PORT=8444
HOST=$(hostname -f)

REQUEST=GET
HEADER1="Accept: application/json"
HEADER2="extra: location=eastus2"
URL="https://${HOST}:${PORT}/azure/flavors"
BODY='{"pem_data": '${PEM_DATA}'}'

json=$(curl --request ${REQUEST}\
     --cacert ${CA}\
     --cert ${CERT}\
     --key ${KEY}\
     --header "${HEADER1}"\
     --header "${HEADER2}"\
     --data-raw "${BODY}" \
     ${URL} 2>/dev/null)

table=$(echo "$json" | jq -r '.flavors[] | [.id, .name, .cpus, .gpus, .price] | @tsv')

id_width=$(echo "$table" | awk -F'\t' '{print length($1)}' | sort -nr | head -1)
name_width=$(echo "$table" | awk -F'\t' '{print length($2)}' | sort -nr | head -1)
cpus_width=$(echo "$table" | awk -F'\t' '{print length($3)}' | sort -nr | head -1)
gpus_width=$(echo "$table" | awk -F'\t' '{print length($4)}' | sort -nr | head -1)
price_width=$(echo "$table" | awk -F'\t' '{print length($5)}' | sort -nr | head -1)

if [ "$cpus_width" -lt 5 ]; then
    cpus_width=5
fi
if [ "$gpus_width" -lt 5 ]; then
    gpus_width=5
fi
if [ "$price_width" -lt 6 ]; then
    price_width=6
fi

printf "%-${id_width}s  %-${name_width}s %-${cpus_width}s %-${gpus_width}s %-${price_width}s\n" "ID" "Name" "CPUs" "GPUs" "Price"
printf "%${id_width}s  %${name_width}s %${cpus_width}s %${gpus_width}s %${price_width}s\n" "$(printf '%*s' "$id_width" | tr ' ' '-')" "$(printf '%*s' "$name_width" | tr ' ' '-')" "$(printf '%*s' "$cpus_width" | tr ' ' '-')" "$(printf '%*s' "$gpus_width" | tr ' ' '-')" "$(printf '%*s' "$price_width" | tr ' ' '-')"
echo "$table" | while IFS=$'\t' read -r id name cpus gpus price; do
    printf "%-${id_width}s  %-${name_width}s %-${cpus_width}s %-${gpus_width}s %-${price_width}s\n" "$id" "$name" "$cpus" "$gpus" "$price"
done
