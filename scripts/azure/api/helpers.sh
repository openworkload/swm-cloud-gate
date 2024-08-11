make_pem_data() {
    local cert=$1
    local key=$2
    local joined_content

    IFS= read -r -d '' content1 < "$key"
    content2=$(sed -n '/-----BEGIN CERTIFICATE-----/,/-----END CERTIFICATE-----/p' $cert)

    joined_content="$content1$content2"
    joined_content=$(echo "$joined_content" | jq -sRr @json)

    printf "%s" "$joined_content"
}

read_credentials() {
    local provider="$1"
    local credentials_file="$HOME/.swm/credentials.json"

    if [[ ! -f "$credentials_file" ]]; then
        echo "Credentials file not found: $credentials_file" >&2
        return 1
    fi

    local credentials=$(jq -r ".$provider" "$credentials_file")
    if [[ -z "$credentials" ]]; then
        echo "Provider '$provider' not found in credentials file" >&2
        return 1
    fi

    echo "$credentials"
}
