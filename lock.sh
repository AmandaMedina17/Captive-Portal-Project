#!/bin/bash

USER_IP=$1

if [ -z "$USER_IP" ]; then
    echo "Error: Se necesita la IP del usuario"
    exit 1
fi

    iptables -I FORWARD -s $USER_IP-j DROP
    iptables -I FORWARD -d $USER_IP -j DROP
    echo "✅ Usuario $USER_IP "