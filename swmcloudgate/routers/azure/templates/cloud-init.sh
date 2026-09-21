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

wait_for_shared_swm_root() {
    # Compute nodes use NFS-exported /opt/swm from main (no local worker unpack).
    local attempt=0
    local max_attempts=120

    until mountpoint -q "$SWM_ROOT" && [[ -d "$SWM_ROOT/spool" ]]; do
        (( attempt += 1 ))
        if (( attempt >= max_attempts )); then
            echo "$(date): timed out waiting for shared $SWM_ROOT (mounted=$(mountpoint -q "$SWM_ROOT" && echo yes || echo no), spool=$([[ -d $SWM_ROOT/spool ]] && echo yes || echo no))" >&2
            mount | grep -E "swm|nfs" || true
            ls -la "$SWM_ROOT" 2>/dev/null || true
            return 1
        fi
        echo "$(date): waiting for shared $SWM_ROOT mount and spool (${attempt}/${max_attempts})"
        sleep 5
    done
    echo "$(date): shared $SWM_ROOT is mounted and spool exists"
}

create_directories() {
    if [[ {{ swm_source | shellquote }} == "ssh" ]]; then
        echo $(date) ": create directory $SWM_ROOT"
        mkdir -p "$SWM_ROOT"
    fi
}

setup_log_symlinks() {
    # Runs on every job node (main and compute). SWM/job paths stay under spool;
    # expose convenient locations under /var/log.
    local domain="${HOST_NAME}.openworkload.org"
    local swm_log_dir="/opt/swm/spool/${HOST_NAME}@${domain}/log"
    local job_dir="/opt/swm/spool/job/{{ job_id }}"

    echo "$(date): ensure directories $swm_log_dir and $job_dir"
    mkdir -p "$swm_log_dir" "$job_dir"

    echo "$(date): link /var/log/swm -> $swm_log_dir"
    if [[ -e /var/log/swm || -L /var/log/swm ]]; then
        rm -rf /var/log/swm
    fi
    ln -s "$swm_log_dir" /var/log/swm

    echo "$(date): link /var/log/job -> $job_dir"
    if [[ -e /var/log/job || -L /var/log/job ]]; then
        rm -rf /var/log/job
    fi
    ln -s "$job_dir" /var/log/job

    ls -ld /var/log/swm /var/log/job "$swm_log_dir" "$job_dir"
}

setup_swm_worker() {
    echo $(date) ": ensure swm worker is installed, SWM_SOURCE={{ swm_source | shellquote }} IS_MAIN=$IS_MAIN"

    if [[ "$IS_MAIN" != "true" ]]; then
        echo "$(date): compute node uses NFS-shared $SWM_ROOT from main (skip worker archive unpack)"
        wait_for_shared_swm_root
        source /opt/swm/*/scripts/swm.env
        ${SWM_ROOT}/${SWM_VERSION}/scripts/setup-swm-core.py \
            -v ${SWM_VERSION} \
            -p ${SWM_ROOT} \
            -c ${SWM_ROOT}/${SWM_VERSION}/priv/setup/setup.config \
            --job-node compute \
            --parent-host "$MAIN_INSTANCE_HOSTNAME"
    elif [[ {{ swm_source | shellquote }} == "ssh" ]]; then
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

        ${SWM_ROOT}/${SWM_VERSION}/scripts/setup-swm-core.py \
            -v ${SWM_VERSION} \
            -p ${SWM_ROOT} \
            -c ${SWM_ROOT}/${SWM_VERSION}/priv/setup/setup.config \
            --job-node main

    elif [[ {{ swm_source | shellquote }} == "http://*.tar.gz" ]]; then
        TMP_DIR=$(mktemp -d -t swm-worker-XXXXX)
        pushd $TMP_DIR
        wget {{ swm_source | shellquote }} --output-document=swm-worker.tar.gz
        mkdir -p /opt/swm
        tar zfx ./swm-worker.tar.gz --directory /opt/swm/
        popd
        mkdir -p /opt/swm/spool
        source /opt/swm/*/scripts/swm.env
        ${SWM_ROOT}/${SWM_VERSION}/scripts/setup-swm-core.py \
            -v ${SWM_VERSION} \
            -p ${SWM_ROOT} \
            -c ${SWM_ROOT}/${SWM_VERSION}/priv/setup/setup.config \
            --job-node main
    fi

    # Runtime parent must be explicit: swm.env defaults to localhost:10002 when unset.
    if [[ "$IS_MAIN" == "true" ]]; then
        # Sky Port via local tunnel parent port.
        parent_host=localhost
        parent_port=10002
    else
        # Parent is the job main node API (not the skyport tunnel defaults).
        parent_host=$MAIN_INSTANCE_HOSTNAME
        parent_port=10001
    fi
    if [[ -z "$parent_host" ]]; then
        echo "$(date): SWM parent host is empty (IS_MAIN=$IS_MAIN)" >&2
        return 1
    fi

    cat > /etc/swm.conf <<EOF
SWM_SNAME=$HOST_NAME
SWM_PARENT_HOST=$parent_host
SWM_PARENT_PORT=$parent_port
EOF
    # Compute confdb must be local: entire /opt/swm (incl. spool) is NFS from main,
    # and Mnesia force_load on NFS hangs wm_conf:init forever.
    if [[ "$IS_MAIN" != "true" ]]; then
        local_mnesia="/var/lib/swm/${HOST_NAME}/confdb"
        mkdir -p "$local_mnesia"
        echo "SWM_MNESIA_DIR=$local_mnesia" >> /etc/swm.conf
    fi
    echo $(date) ": /etc/swm.conf:"
    cat /etc/swm.conf
    echo

    # Environment= overrides EnvironmentFile; survives a partial /etc/swm.conf rewrite.
    mkdir -p /etc/systemd/system/swm.service.d
    if [[ "$IS_MAIN" == "true" ]]; then
        cat > /etc/systemd/system/swm.service.d/parent.conf <<EOF
[Service]
Environment=SWM_PARENT_HOST=$parent_host
Environment=SWM_PARENT_PORT=$parent_port
EOF
    else
        cat > /etc/systemd/system/swm.service.d/parent.conf <<EOF
[Service]
Environment=SWM_PARENT_HOST=$parent_host
Environment=SWM_PARENT_PORT=$parent_port
Environment=SWM_MNESIA_DIR=/var/lib/swm/${HOST_NAME}/confdb
EOF
    fi
    echo $(date) ": /etc/systemd/system/swm.service.d/parent.conf:"
    cat /etc/systemd/system/swm.service.d/parent.conf
    echo

    setup_log_symlinks

    systemctl daemon-reload
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
    if [[ "$IS_MAIN" != "true" ]]; then
        # Resolve job main by hostname for SWM_PARENT_HOST (API on :10001).
        echo "$MAIN_INSTANCE_PRIVATE_IP $MAIN_INSTANCE_HOSTNAME.openworkload.org $MAIN_INSTANCE_HOSTNAME" >> /etc/hosts
    fi
    echo $(date) ": /etc/hosts:"
    cat /etc/hosts
    echo
}

setup_passwordless_root_ssh() {
    # Key-based root SSH with no password. Main publishes its root pubkey via
    # shared /home NFS; compute nodes install it after the mount.
    echo "$(date): configure passwordless root SSH (IS_MAIN=$IS_MAIN)"
    mkdir -p /root/.ssh
    chmod 700 /root/.ssh

    mkdir -p /etc/ssh/sshd_config.d
    cat > /etc/ssh/sshd_config.d/99-swm-root-key.conf <<'EOF'
PermitRootLogin prohibit-password
PubkeyAuthentication yes
PasswordAuthentication no
EOF
    if ! systemctl reload sshd 2>/dev/null; then
        systemctl reload ssh 2>/dev/null || true
    fi

    cat > /root/.ssh/config <<'EOF'
Host *
  StrictHostKeyChecking no
  UserKnownHostsFile /dev/null
EOF
    chmod 600 /root/.ssh/config

    ensure_root_authorized_key() {
        local key="$1"
        [[ -n "$key" ]] || return 0
        touch /root/.ssh/authorized_keys
        chmod 600 /root/.ssh/authorized_keys
        grep -qxF "$key" /root/.ssh/authorized_keys || echo "$key" >> /root/.ssh/authorized_keys
    }

    # Sky Port / user provisioning key (all nodes).
    ensure_root_authorized_key {{ ssh_pub_key | shellquote }}

    local cluster_pub=/home/.swm/cluster_root.pub
    if [[ "$IS_MAIN" == "true" ]]; then
        if [[ ! -f /root/.ssh/id_rsa ]]; then
            ssh-keygen -t rsa -b 4096 -N "" -f /root/.ssh/id_rsa -C "swm-cluster-root"
        fi
        mkdir -p /home/.swm
        cp -f /root/.ssh/id_rsa.pub "$cluster_pub"
        chmod 755 /home/.swm
        chmod 644 "$cluster_pub"
        ensure_root_authorized_key "$(cat /root/.ssh/id_rsa.pub)"
        echo "$(date): published cluster root pubkey to $cluster_pub"
    else
        local attempt=0
        local max_attempts=60
        while [[ ! -f "$cluster_pub" ]]; do
            (( attempt += 1 ))
            if (( attempt >= max_attempts )); then
                echo "$(date): timed out waiting for main root pubkey at $cluster_pub" >&2
                return 1
            fi
            echo "$(date): waiting for main root pubkey ($attempt/$max_attempts)"
            sleep 5
        done
        ensure_root_authorized_key "$(cat "$cluster_pub")"
        echo "$(date): installed main root pubkey into /root/.ssh/authorized_keys"
    fi

    chmod 600 /root/.ssh/authorized_keys
    ls -la /root/.ssh/
}

setup_mounts() {
    if [ $IS_MAIN == "true" ];
    then
        # Publish cluster root key before NFS export so compute nodes can fetch it.
        mkdir -p /root/.ssh /home/.swm "$SWM_ROOT"
        chmod 700 /root/.ssh
        if [[ ! -f /root/.ssh/id_rsa ]]; then
            ssh-keygen -t rsa -b 4096 -N "" -f /root/.ssh/id_rsa -C "swm-cluster-root"
        fi
        cp -f /root/.ssh/id_rsa.pub /home/.swm/cluster_root.pub
        chmod 755 /home/.swm
        chmod 644 /home/.swm/cluster_root.pub

        # Share /home and /opt/swm with compute nodes (worker is unpacked on main only).
        echo "/home $PRIVATE_SUBNET_CIDR(rw,async,no_root_squash,no_subtree_check)" >> /etc/exports
        echo "$SWM_ROOT $PRIVATE_SUBNET_CIDR(rw,async,no_root_squash,no_subtree_check)" >> /etc/exports
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
        echo "$MAIN_INSTANCE_PRIVATE_IP:$SWM_ROOT $SWM_ROOT nfs rsize=32768,wsize=32768,hard,intr,async 0 0" >> /etc/fstab
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
                echo "$(date): failed to mount shared /home and $SWM_ROOT after ${max_mount_attempts} attempts" >&2
                return 1
            fi
            echo "$(date): mount attempt ${count}/${max_mount_attempts} failed, retrying in 5 seconds"
            sleep 5
        done
        echo $(date) ": mounted."
        mountpoint -q /home && mountpoint -q "$SWM_ROOT"
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
setup_passwordless_root_ssh
setup_docker
pull_container_image
setup_swm_worker

echo
echo $(date) ": the initialization has finished successfully."

exit 0
