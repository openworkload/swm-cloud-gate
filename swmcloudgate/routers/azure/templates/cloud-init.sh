#!/bin/bash
# Invoked as `bash /tmp/swm-init.sh` from cloud-init (shebang flags are ignored).
set -ex

HOST_NAME="{{ host_name }}"
SWM_ROOT="/opt/swm"
PRIMARY_INTERFACE=""
PRIVATE_IP_CIDR=""
PRIVATE_SUBNET_CIDR=""
IS_MAIN={{ is_main }}
MAIN_INSTANCE_HOSTNAME="{{ main_instance_hostname }}"
MAIN_INSTANCE_PRIVATE_IP="{{ main_instance_private_ip }}"

detect_vm_context() {
    PRIMARY_INTERFACE=$(ip -4 route list 0/0 | awk 'NR==1 { print $5 }')
    PRIVATE_IP_CIDR=$(ip -4 -o addr show "$PRIMARY_INTERFACE" | awk 'NR==1 { print $4 }')
    # Prefer prefix-length form (10.0.0.0/24) for /etc/exports.
    PRIVATE_SUBNET_CIDR=$(python3 - "$PRIVATE_IP_CIDR" <<'PY'
import ipaddress
import sys

network = ipaddress.ip_interface(sys.argv[1]).network
print(network.with_prefixlen)
PY
)
    if [[ -z "$PRIVATE_SUBNET_CIDR" ]]; then
        echo "$(date): could not determine private subnet CIDR" >&2
        return 1
    fi

    if [[ -z "$MAIN_INSTANCE_HOSTNAME" || -z "$MAIN_INSTANCE_PRIVATE_IP" ]]; then
        echo "$(date): could not determine main instance details" >&2
        return 1
    fi
}

wait_for_dpkg_lock() {
    # cloud-init `packages:` and Ubuntu unattended-upgrades often still hold
    # the frontend lock when runcmd starts; dpkg -i does not wait by itself.
    local locks=(
        /var/lib/dpkg/lock-frontend
        /var/lib/dpkg/lock
        /var/cache/apt/archives/lock
        /var/lib/apt/lists/lock
    )
    local waited=0
    local max_wait=600
    while true; do
        local busy=0
        local lock
        for lock in "${locks[@]}"; do
            if fuser "$lock" >/dev/null 2>&1; then
                busy=1
                break
            fi
        done
        if [[ $busy -eq 0 ]]; then
            if [[ $waited -gt 0 ]]; then
                echo "$(date): dpkg/apt locks are free after ${waited}s"
            fi
            return 0
        fi
        if [[ $waited -ge $max_wait ]]; then
            echo "$(date): timed out after ${max_wait}s waiting for dpkg/apt locks" >&2
            fuser -v "${locks[@]}" 2>&1 || true
            return 1
        fi
        if [[ $((waited % 30)) -eq 0 ]]; then
            echo "$(date): waiting for dpkg/apt lock (held; waited ${waited}s)..."
            fuser -v /var/lib/dpkg/lock-frontend 2>&1 || true
        fi
        sleep 5
        waited=$((waited + 5))
    done
}

install_blobfuse2() {
    export DEBIAN_FRONTEND=noninteractive
    export NEEDRESTART_MODE=a
    # Let apt wait if another apt grabs the lock between our check and invoke.
    local apt_lock_opts=(-o DPkg::Lock::Timeout=600)

    if command -v blobfuse2 >/dev/null 2>&1; then
        echo "$(date): blobfuse2 already installed: $(command -v blobfuse2)"
        return 0
    fi

    local ubuntu_ver
    ubuntu_ver=$(lsb_release -rs)
    echo "$(date): install blobfuse2 for Ubuntu ${ubuntu_ver}"

    # Pause background apt so it does not race dpkg -i (see cloud-init-output.log).
    systemctl stop apt-daily.service apt-daily-upgrade.service unattended-upgrades.service 2>/dev/null || true
    systemctl kill --kill-who=all apt-daily.service apt-daily-upgrade.service unattended-upgrades.service 2>/dev/null || true

    wait_for_dpkg_lock

    pushd /tmp
    # Azure marketplace images often already have packages.microsoft.com configured.
    if [[ ! -f /etc/apt/sources.list.d/microsoft-prod.list ]] \
        && ! grep -Rqs 'packages.microsoft.com/ubuntu' /etc/apt/sources.list /etc/apt/sources.list.d 2>/dev/null; then
        wget -q "https://packages.microsoft.com/config/ubuntu/${ubuntu_ver}/packages-microsoft-prod.deb" \
            -O packages-microsoft-prod.deb
        wait_for_dpkg_lock
        dpkg -i packages-microsoft-prod.deb
    else
        echo "$(date): Microsoft apt repo already present; skip packages-microsoft-prod.deb"
    fi
    wait_for_dpkg_lock
    apt-get "${apt_lock_opts[@]}" update
    wait_for_dpkg_lock
    apt-get "${apt_lock_opts[@]}" install -y fuse3 blobfuse2
    popd

    if ! command -v blobfuse2 >/dev/null 2>&1; then
        echo "$(date): blobfuse2 is not on PATH after apt install" >&2
        dpkg -l 'blobfuse2' 'fuse3' || true
        return 1
    fi
    echo "$(date): blobfuse2 installed: $(command -v blobfuse2) ($(blobfuse2 --version 2>/dev/null || true))"
}

mount_azure_storage() {
    echo Mount Azure storage

    install_blobfuse2

    local azure_storage_account={{ storage_account | shellquote }}
    local azure_storage_container={{ storage_container | shellquote }}
    local azure_storage_key_b64
    local azure_storage_key
    local config_file=/etc/blobfuse2.yaml
    local cache_dir=/tmp/blobfuse2.cache
    local mount_dir=/mnt/blob

    mkdir -p "$cache_dir"
    mkdir -p "$mount_dir"

    # Avoid leaking the storage key via `set -x` / cloud-init-output.log.
    set +x
    azure_storage_key_b64="{{ storage_key_b64 }}"
    azure_storage_key=$(printf '%s' "$azure_storage_key_b64" | base64 -d)
    cat << EOF > "$config_file"
allow-other: true
logging:
  type: syslog
  level: log_debug
  components:
    - libfuse
    - file_cache
    - attr_cache
    - azstorage
libfuse:
  attribute-expiration-sec: 120
  entry-expiration-sec: 120
  negative-entry-expiration-sec: 240
file_cache:
  path: $cache_dir
  timeout-sec: 120
  max-size-mb: 4096
attr_cache:
  timeout-sec: 7200
azstorage:
  type: block
  account-name: $azure_storage_account
  account-key: $azure_storage_key
  endpoint: https://$azure_storage_account.blob.core.windows.net
  mode: key
  container: $azure_storage_container
EOF
    unset azure_storage_key azure_storage_key_b64
    set -x
    chmod 600 "$config_file"
    echo "$(date): wrote blobfuse2 config to $config_file (account=$azure_storage_account container=$azure_storage_container; key redacted)"

    echo "$(date): mount $mount_dir"
    blobfuse2 mount "$mount_dir" --config-file="$config_file" --read-only
    if ! mountpoint -q "$mount_dir"; then
        echo "$(date): blobfuse2 mount of $mount_dir failed" >&2
        return 1
    fi
    echo "$(date): mounted $mount_dir"
}

wait_for_main_nfs() {
    local attempt=0
    local max_attempts=60

    until timeout 2 bash -c "</dev/tcp/${MAIN_INSTANCE_PRIVATE_IP}/2049" >/dev/null 2>&1; do
        (( attempt += 1 ))
        if (( attempt >= max_attempts )); then
            echo "$(date): NFS on ${MAIN_INSTANCE_PRIVATE_IP}:2049 did not become ready after ${max_attempts} attempts" >&2
            return 1
        fi
        echo "$(date): waiting for NFS on ${MAIN_INSTANCE_PRIVATE_IP}:2049 (${attempt}/${max_attempts})"
        sleep 5
    done
}

create_directories() {
    if [[ {{ swm_source | shellquote }} == "ssh" ]]; then
        echo $(date) ": create directory $SWM_ROOT"
        mkdir -p "$SWM_ROOT"
    fi
}

setup_swm_worker() {
    echo $(date) ": ensure swm worker is installed, SWM_SOURCE={{ swm_source | shellquote }}"

    if [[ {{ swm_source | shellquote }} == "ssh" ]]; then
        echo {{ ssh_pub_key | shellquote }} >> /root/.ssh/authorized_keys
        echo $(date) ": ensure swm worker is installed via ssh"

        local check_interval=15
        local file_path="$SWM_ROOT/swm-worker.tar.gz"

        while true; do
            if [[ -f "$file_path" ]]; then
                echo "$(date): file $file_path found"
                sleep 10
                tar -xzf "$file_path" -C "$SWM_ROOT"
                if [ $? -eq 0 ]; then
                    echo "$(date): worker archive has been unpacked successfully"
                    break
                else
                    echo "$(date): worker archive is not ready yet => will repeat in a while"
                fi
            else
              echo "$(date): file not found, checking again in $check_interval seconds..."
                sleep $check_interval
            fi
        done

        mkdir -p /opt/swm/spool
        source /opt/swm/*/scripts/swm.env

        ${SWM_ROOT}/${SWM_VERSION}/scripts/setup-swm-core.py -v ${SWM_VERSION} -p ${SWM_ROOT} -c ${SWM_ROOT}/${SWM_VERSION}/priv/setup/setup.config

    elif [[ {{ swm_source | shellquote }} == "http://*.tar.gz" ]]; then
        TMP_DIR=$(mktemp -d -t swm-worker-XXXXX)
        pushd $TMP_DIR
        wget {{ swm_source | shellquote }} --output-document=swm-worker.tar.gz
        mkdir -p /opt/swm
        tar zfx ./swm-worker.tar.gz --directory /opt/swm/
        popd
    fi

    echo SWM_SNAME=$HOST_NAME > /etc/swm.conf
    echo $(date) ": /etc/swm.conf:"
    cat /etc/swm.conf
    echo

    JOB_DIR=/opt/swm/spool/job/{{ job_id }}
    echo $(date) ": create job directory: $JOB_DIR"
    mkdir -p $JOB_DIR

    systemctl enable swm
    systemctl start swm

    local waited=0
    local max_wait=120
    until systemctl is-active --quiet swm; do
        if [[ $waited -ge $max_wait ]]; then
            echo "$(date): swm.service did not become active within ${max_wait}s" >&2
            systemctl status swm --no-pager -l || true
            journalctl -u swm -n 100 --no-pager || true
            return 1
        fi
        echo "$(date): waiting for swm.service to become active (${waited}/${max_wait}s)"
        sleep 5
        waited=$((waited + 5))
    done
    echo "$(date): swm.service is active"
    systemctl status swm --no-pager -l || true
    ps aux | grep '[s]wm' || true
}

setup_network() {
    detect_vm_context || exit 1
    VM_PRIVATE_IP="${PRIVATE_IP_CIDR%%/*}"
    echo $(date) ": start VM initialization (HOST: $HOST_NAME, IP=$VM_PRIVATE_IP, master: ${IS_MAIN})"
    echo $VM_PRIVATE_IP $HOST_NAME.openworkload.org $HOST_NAME >> /etc/hosts
    echo $(date) ": /etc/hosts:"
    cat /etc/hosts
    echo
}

setup_mounts() {
    if [ $IS_MAIN == "true" ];
    then
        echo "/home $PRIVATE_SUBNET_CIDR(rw,async,no_root_squash,no_subtree_check)" >> /etc/exports
        echo $(date) ": /etc/exports:"
        cat /etc/exports
        echo

        exportfs -ra
        systemctl enable nfs-kernel-server
        systemctl restart nfs-kernel-server
        echo $(date) ": systemctl | grep nfs:"
        systemctl | grep nfs

    else
        echo "$MAIN_INSTANCE_PRIVATE_IP:/home /home nfs rsize=32768,wsize=32768,hard,intr,async 0 0" >> /etc/fstab
        echo $(date) ": /etc/fstab:"
        cat /etc/fstab
        echo

        wait_for_main_nfs

        local count=0
        local max_mount_attempts=60
        echo $(date) ": waiting for mount ..."
        until mount -a; do
            (( count += 1 ))
            if (( count >= max_mount_attempts )); then
                echo "$(date): failed to mount shared /home after ${max_mount_attempts} attempts" >&2
                return 1
            fi
            echo "$(date): mount attempt ${count}/${max_mount_attempts} failed, retrying in 5 seconds"
            sleep 5
        done
        echo $(date) ": mounted."
    fi
    echo

    mount_azure_storage
}

setup_docker() {
    echo $(date) ": setup docker"

    # Prefer preinstalled Moby on Azure HPC/GPU images. Only fall back to docker.io
    # if neither docker nor dockerd is present (do not replace moby in cloud-init packages).
    if ! command -v docker >/dev/null 2>&1; then
        export DEBIAN_FRONTEND=noninteractive
        export NEEDRESTART_MODE=a
        local apt_lock_opts=(-o DPkg::Lock::Timeout=600)
        echo "$(date): docker not found; installing docker.io"
        systemctl stop apt-daily.service apt-daily-upgrade.service unattended-upgrades.service 2>/dev/null || true
        wait_for_dpkg_lock
        apt-get "${apt_lock_opts[@]}" update
        wait_for_dpkg_lock
        apt-get "${apt_lock_opts[@]}" install -y docker.io
    fi
    echo "$(date): using docker: $(command -v docker) ($(docker --version 2>/dev/null || true))"

    # swm connects to docker via tcp => enable this port listening in the docker daemon:
    sed -i "/^ExecStart/s/$/ -H tcp:\/\/127.0.0.1:6000 --insecure-registry 172.28.128.2:6006/" /lib/systemd/system/docker.service
    systemctl daemon-reload

    # Fix docker connections failures
    # https://github.com/systemd/systemd/issues/3374
    sed -i s/MACAddressPolicy=persistent/MACAddressPolicy=none/g /lib/systemd/network/99-default.link
    echo $(date) ": 99-default.link:"
    cat /lib/systemd/network/99-default.link
    echo

    systemctl enable docker
    systemctl restart docker
    if ! systemctl is-active --quiet docker; then
        echo "$(date): docker.service failed to start" >&2
        systemctl status docker --no-pager -l || true
        return 1
    fi
    echo "$(date): docker.service is active"
}

pull_container_image() {
    local container_registry={{ container_registry | shellquote }}
    local container_registry_username={{ container_registry_username | shellquote }}
    local container_image={{ container_image | shellquote }}
    local container_registry_password

    set +x
    container_registry_password={{ container_registry_password | shellquote }}
    if [ -n "$container_registry_password" ]; then
        printf '%s\n' "$(date): login to the registry: $container_registry"
        printf '%s' "$container_registry_password" \
            | docker login "$container_registry" \
                --username "$container_registry_username" \
                --password-stdin
    fi
    unset container_registry_password
    set -x

    echo $(date) ": pull job container image from container registry: $container_image"
    docker pull "$container_image"

    echo $(date) ": all local docker images after the pulling:"
    docker images
}

create_directories
setup_network
setup_mounts
setup_docker
pull_container_image
setup_swm_worker

echo
echo $(date) ": the initialization has finished successfully."

exit 0
