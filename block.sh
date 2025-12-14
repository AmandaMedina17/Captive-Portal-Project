# #!/bin/bash

# USER_IP=$1

# if [ -z "$USER_IP" ]; then
#     echo "Error: Se necesita la IP del usuario"
#     exit 1
# fi

#     iptables -I FORWARD -s $USER_IP-j DROP
#     iptables -I FORWARD -d $USER_IP -j DROP
#     echo "✅ Usuario $USER_IP "


USER_IP=$1

if [ -z "$USER_IP" ]; then
    echo "Error: Se necesita la IP del usuario"
    exit 1
fi

# Eliminar reglas de ACCEPT para esta IP
iptables -D FORWARD -s $USER_IP -j ACCEPT 2>/dev/null
iptables -D FORWARD -d $USER_IP -j ACCEPT 2>/dev/null
iptables -t nat -D PREROUTING -s $USER_IP -p tcp --dport 80 -j ACCEPT 2>/dev/null

# Agregar redirección al portal cautivo
iptables -t nat -I PREROUTING -s $USER_IP -p tcp --dport 80 -j REDIRECT --to-port 8000

echo "⏳ Usuario $USER_IP bloqueado"
echo "Reglas actuales para $USER_IP:"
iptables -L FORWARD -n | grep $USER_IP || echo "No hay reglas específicas"