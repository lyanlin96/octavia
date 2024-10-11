#!/bin/bash

if [ "$EUID" -ne 0 ]
    then echo "Please run script as root."
    exit
fi

SERVICE_NAME="fortiadc-agent.service"

systemctl stop $SERVICE_NAME 
systemctl disable $SERVICE_NAME 
rm /etc/systemd/system/$SERVICE_NAME

echo "Service uninstallation complete."
