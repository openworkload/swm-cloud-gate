function make_pem_data() {
    local cert=$1
    local key=$2
    local joined_content

    IFS= read -r -d '' content1 < "$key"
    content2=$(sed -n '/-----BEGIN CERTIFICATE-----/,/-----END CERTIFICATE-----/p' $cert)

    joined_content="$content1$content2"
    joined_content=$(echo "$joined_content" | jq -sRr @json)

    printf "%s" "$joined_content"
}
