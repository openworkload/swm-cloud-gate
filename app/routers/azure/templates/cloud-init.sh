#!/bin/bash -ex

function download_swm_worker() {
    if [[ {{ swm_source }} == "https://*.tar.gz" ]]; then
        swm_url={{ swm_source }}
        echo $(date) ": ensure swm worker is installed from ${swm_url}"
        target_directory="/opt/swm"
        mkdir -p "$target_directory"
        wget "$swm_url" -O "$target_directory/swm-worker.tar.gz"
        tar -xzf "$target_directory/swm-worker.tar.gz" -C "$target_directory"
        rm "$target_directory/swm-worker.tar.gz"
    else
        echo "ERROR: unsupported swm-worker source: {{ swm_source }}"
        exit 1
    fi
}

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

# Fix docker connections failures
# https://github.com/systemd/systemd/issues/3374
sed -i s/MACAddressPolicy=persistent/MACAddressPolicy=none/g /lib/systemd/network/99-default.link
echo $(date) ": 99-default.link:"
cat /lib/systemd/network/99-default.link
echo

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

download_swm_worker()

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

echo
echo $(date) ": the initialization has finished"

exit 0
