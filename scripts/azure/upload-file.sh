#!/bin/bash -e

ENV_FILE=$HOME/.swm/azure.env
PROG_NAME=$0

if [ ! -f "$ENV_FILE" ]; then
    echo "The environment file does no exists: ${ENV_FILE}"
fi

source $HOME/.swm/azure.env

container_name_flag=0
blob_name_flag=0
file_flag=0

while getopts ':c:b:f:' option; do
    case "$option" in
        c) CONTAINER_NAME="$OPTARG"
            container_name_flag=1 ;;
        b) BLOB_NAME="$OPTARG"
            blob_name_flag=1 ;;
        f) FILE="$OPTARG"
            file_flag=1 ;;
        \?) echo "Invalid option: -$OPTARG" >&2
            exit 1
            ;;
        :) echo "Option -$OPTARG requires an argument." >&2
            exit 1
            ;;
    esac
done

function help() {
    echo "USAGE: $PROG_NAME -c <CONTAINER NAME> -b <BLOB NAME> -f <FILE PATH>
}

if [ "$container_name_flag" -eq 0 ] || [ "$blob_name_flag" -eq 0 ] || [ "$file_flag" -eq 0 ]; then
    echo "ERROR: all arguments -c, -b, and -f are mandatory."
    echo
    usage
    exit 1
fi

az storage blob upload\
    --container-name "$CONTAINER_NAME"\
    --name "$BLOB_NAME"\
    --file "$FILE"\
    --auth-mode $AUTH_MODE\
    --account-name $ACCOUNT_NAME\
    --account-key $ACCOUNT_KEY

exit 0
