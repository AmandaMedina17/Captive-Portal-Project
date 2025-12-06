#!/bin/bash
# Desbloquea una IP específica 

USER_IP=$1

if [ -z "$USER_IP" ]; then
    echo "Error: Se necesita la IP del usuario"
    exit 1
fi

# Permitir tráfico completo para esta IP
iptables -I FORWARD -s $USER_IP -j ACCEPT 
iptables -I FORWARD -d $USER_IP -j ACCEPT 

# Agregar excepción para que no sea redirigido
iptables -t nat -I PREROUTING -s $USER_IP -p tcp --dport 80 -j ACCEPT

echo "✅ Usuario $USER_IP desbloqueado - Tiene internet completo"
echo "las reglas son"
iptables -L FORWARD -n | grep $USER_IP