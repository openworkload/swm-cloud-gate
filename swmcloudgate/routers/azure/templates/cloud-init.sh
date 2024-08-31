#!/bin/bash -ex

HOST_NAME=$(hostname)
SWM_ROOT="/opt/swm"

create_directories() {
    if [[ "{{ swm_source }}" == "ssh" ]]; then
        echo $(date) ": create directory $SWM_ROOT"
        mkdir -p "$SWM_ROOT"
    fi
}

setup_swm_worker() {
    echo $(date) ": ensure swm worker is installed, SWM_SOURCE={{ swm_source }}"

    if [[ "{{ swm_source }}" == "ssh" ]]; then
        echo "{{ ssh_pub_key }}" >> /root/.ssh/authorized_keys
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

        source /opt/swm/*/scripts/swm.env

        ${SWM_ROOT}/${SWM_VERSION}/scripts/setup-swm-core.py -p ${SWM_ROOT} -c ${SWM_ROOT}/${SWM_VERSION}/priv/setup/setup.config

    elif [[ "{{ swm_source }}" == "http://*.tar.gz" ]]; then
        TMP_DIR=$(mktemp -d -t swm-worker-XXXXX)
        pushd $TMP_DIR
        wget {{ swm_source }} --output-document=swm-worker.tar.gz
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

    echo $(date) ": systemctl | grep swm:"
    systemctl | grep swm

    echo $(date) ": ps aux | grep swm:"
    ps aux | grep swm
}

setup_network() {
    GATEWAY_IP=$(ip -4 addr show $(ip -4 route list 0/0 | awk -F" " "{ print \$5 }") | grep -oP "(?<=inet\\s)\\d+(\\.\\d+){3}")
    IS_MAIN=true
    echo $(date) ": start VM initialization (HOST: $HOST_NAME, IP=$GATEWAY_IP, master: ${IS_MAIN})"
    echo $GATEWAY_IP $HOST_NAME.openworkload.org $HOST_NAME >> /etc/hosts
    echo $(date) ": /etc/hosts:"
    cat /etc/hosts
    echo
}

setup_mounts() {
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

        systemctl restart docker # fix rare "connection closed" issues
    fi
    echo
}

setup_docker() {
    echo $(date) ": setup docker"

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
}

pull_container_image() {
    if [ "{{ container_registry_password }}" != "" ]; then
        echo $(date) ": login to the registry: {{ container_registry }}"
        docker login {{ container_registry }} --username {{ container_registry_username }} --password {{ container_registry_password }}
    fi

    echo $(date) ": pull job container image from container registry: {{ container_image }}"
    docker pull {{ container_image }}

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

