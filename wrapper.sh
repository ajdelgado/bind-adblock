#!/bin/bash
if [ -z "${HOME}" ]; then
    if [ "$(whoami)" == "root" ]; then
        HOME="/root"
    else
        HOME=$(grep "$(whoami)" /etc/passwd | awk 'BEGIN {FS=":"} {print($6)}')
    fi
fi

CONFIG_FILE="${HOME}/.config/update_zonefile.conf"
cd "__src_folder__" || exit 1
if [ -r "${CONFIG_FILE}" ]; then
    perms=$(stat -c %A "${CONFIG_FILE}")
    if [ "${perms:4:6}" != '------' ]; then
        echo "Permissions too open for config file '${CONFIG_FILE}' ($perms). Remove all permissions to group and others."
        exit 1
    fi
    config=(--config "${CONFIG_FILE}")
else
    config=()
fi
"__src_folder__/update_zonefile.sh" "${config[@]}" "${@}"
