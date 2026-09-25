#!/bin/bash -ex

function download_swm_worker() {
    echo $(date) ": ensure swm worker is installed, SWM_SOURCE={{ swm_source }}"

    if [[ "{{ swm_source }}" == "ssh" ]]; then
        echo "{{ ssh_pub_key }}" >> /root/.ssh/authorized_keys
        echo $(date) ": ensure swm worker is installed via ssh"

        local check_interval=15
        local target_directory="/opt/swm"
        local file_path="$target_directory/swm-worker.tar.gz"

        mkdir -p "$target_directory"

        while true; do
            if [[ -f "$file_path" ]]; then
                echo "$(date): file '$file_path' found"
                sleep 10
                tar -xzf "$file_path" -C "$target_directory"
                break
            else
              echo "$(date): file not found, checking again in $check_interval seconds..."
                sleep $check_interval
            fi
        done

        source /opt/swm/0.2.0/scripts/swm.env

        ${SWM_ROOT}/${SWM_VERSION}/scripts/setup.linux -p ${SWM_ROOT} -c ${SWM_ROOT}/${SWM_VERSION}/priv/setup/setup-config.linux

    elif [[ "{{ swm_source }}" == "http://*.tar.gz" ]]; then
        TMP_DIR=$(mktemp -d -t swm-worker-XXXXX)
        pushd $TMP_DIR
        wget {{ swm_source }} --output-document=swm-worker.tar.gz
        mkdir -p /opt/swm
        tar zfx ./swm-worker.tar.gz --directory /opt/swm/
        popd
    fi

    echo SWM_SNAME=$HOST_NAME > /etc/swm.conf
    echo SWM_CONTAINER_PODMAN_SOCK=/run/podman/podman.sock >> /etc/swm.conf
    echo $(date) ": /etc/swm.conf:"
    cat /etc/swm.conf
    echo

    # Runs on every job node. Expose spool paths under /var/log.
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

    systemctl enable swm
    systemctl start swm

    echo $(date) ": systemctl | grep swm:"
    systemctl | grep swm

    echo $(date) ": ps aux | grep swm:"
    ps aux | grep swm
}

function setup_network() {
    GATEWAY_IP=$(ip -4 addr show $(ip -4 route list 0/0 | awk -F' ' '{ print $5 }') | grep -oP "(?<=inet\\s)\\d+(\\.\\d+){3}")
    IS_MAIN=true
    echo $(date) ": start VM initialization (HOST: $HOST_NAME, IP=$GATEWAY_IP, master: ${IS_MAIN})"

    hostname $HOST_NAME.openworkload.org
    echo $HOST_NAME.openworkload.org > /etc/hostname
    echo $(date) ": hostname=$(hostname)"

    echo $GATEWAY_IP $HOST_NAME.openworkload.org $HOST_NAME >> /etc/hosts
    echo $(date) ": /etc/hosts:"
    cat /etc/hosts
    echo

    # FIXME: re-configure openstack to get rid of this domain
    sed -i -n "/openstacklocal/!p" /etc/resolv.conf
    echo $(date) ": /etc/resolv.conf:"
    cat /etc/resolv.conf
    echo
}

function setup_mounts() {
    if [ $IS_MAIN == "true" ];
    then
        echo "/home $PRIVATE_SUBNET_CIDR(rw,async,no_root_squash)" | sed "s/\\/25/\\/255.255.255.0/g" >> /etc/exports
        echo $(date) ": /etc/exports:"
        cat /etc/exports
        echo

        # Temporary disable for debug purposes
        #systemctl enable nfs-kernel-server
        #systemctl restart nfs-kernel-server
        #echo $(date) ": systemctl | grep nfs:"
        #systemctl | grep nfs

    else
        echo "$MAIN_INSTANCE_PRIVATE_IP:/home /home nfs rsize=32768,wsize=32768,hard,intr,async 0 0" >> /etc/fstab
        echo $(date) ": /etc/fstab:"
        cat /etc/fstab
        echo

        echo $(date) ": waiting for mount ..."
        until mount -a || (( count++ >= 20 )); do sleep 5; done
        echo $(date) ": mounted."
    fi
    echo
}

function install_packages() {
    echo $(date) ": install packages"

    apt-get --yes update
    apt-get --yes install podman crun uidmap slirp4netns fuse-overlayfs
    apt-get --yes install cgroupfs-mount
    apt-get --yes install net-tools
}

function setup_podman() {
    echo $(date) ": setup rootful Podman + crun"

    mkdir -p /etc/containers /etc/containers/containers.conf.d
    cat > /etc/containers/containers.conf.d/50-swm-crun.conf <<'EOF'
[engine]
runtime = "crun"
EOF

    # https://github.com/systemd/systemd/issues/3374
    sed -i s/MACAddressPolicy=persistent/MACAddressPolicy=none/g /lib/systemd/network/99-default.link
    echo $(date) ": 99-default.link:"
    cat /lib/systemd/network/99-default.link
    echo

    systemctl enable --now podman.socket
    if [[ ! -S /run/podman/podman.sock ]]; then
        echo "$(date): podman.socket did not create /run/podman/podman.sock" >&2
        systemctl status podman.socket --no-pager -l || true
        return 1
    fi

    local runtime
    # Keep Podman go-template braces out of Jinja via raw block.
    runtime=$(podman info --format '{% raw %}{{.Host.OCIRuntime.Name}}{% endraw %}' 2>/dev/null || true)
    echo "$(date): OCI runtime=$runtime"
    if [[ "$runtime" != "crun" ]]; then
        echo "$(date): expected OCI runtime crun, got: ${runtime:-unknown}" >&2
        return 1
    fi
}

function pull_container_image() {
    echo $(date) ": pull job container image: '{{ container_image }}'"
    podman pull {{ container_image }}

    echo $(date) ": local podman images after pull:"
    podman images
}

setup_network
setup_mounts
install_packages
setup_podman
pull_container_image
download_swm_worker

echo
echo $(date) ": the initialization has finished successfully."

exit 0
