#!/bin/bash

if [ "$EUID" -ne 0 ]
    then echo "Please run script as root."
    exit
fi

if [ -z "$1" ]; then
  echo "Please provide full path of fortiadc_agent as an argument."
  exit 1
fi

if [ -e "$1" ]; then
  echo " "
else
  echo "The file '$1' does not exist."
  exit 1
fi


cp fortiadc-agent.service.template fortiadc-agent.service
sed -i "s|%agent_path%|$1|g" fortiadc-agent.service
mv -f fortiadc-agent.service /etc/systemd/system/

systemctl enable fortiadc-agent.service
systemctl start fortiadc-agent.service

echo "Service installation complete."
