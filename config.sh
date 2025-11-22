#!/bin/bash

echo "📡 CONFIGURANDO HOTSPOT FUNCIONAL + CAPTIVE PORTAL"
echo "=================================================="

# Configuración
INTERFACE="wlp2s0"
SSID="MiPortal"
PASSWORD="portal123"
GATEWAY_IP="192.168.4.1"
SERVER_PORT="8000"

# Función de limpieza
cleanup() {
    echo ""
    echo "🧹 Limpiando configuración..."
    sudo pkill hostapd 2>/dev/null
    sudo pkill dnsmasq 2>/dev/null
    sudo pkill -f "python3 server_hotspot.py" 2>/dev/null
    sudo systemctl restart NetworkManager 2>/dev/null
    sudo systemctl restart systemd-resolved 2>/dev/null

    sudo iptables -t nat -F 2>/dev/null
    sudo iptables -F 2>/dev/null
    sudo pkill dnsmasq
    sudo pkill hostapd
    sudo rm -f /tmp/dnsmasq.log
    sudo rm -f /tmp/dhcp.leases

    sudo touch /tmp/dnsmasq.log
    sudo chmod 666 /tmp/dnsmasq.log
    sudo touch /tmp/dhcp.leases
    sudo chmod 666 /tmp/dhcp.leases

    sudo ip addr flush dev $INTERFACE 2>/dev/null
    sudo ip link set $INTERFACE down 2>/dev/null
    sudo ip link set $INTERFACE up 2>/dev/null

    echo "✅ Configuración limpiada"
}

# Verificar que la interfaz soporta modo AP
check_ap_support() {
    echo "🔍 Verificando soporte de modo AP..."
    if iw list | grep -A 10 "Supported interface modes" | grep -q "AP"; then
        echo "✅ La interfaz $INTERFACE soporta modo AP"
    else
        echo "❌ La interfaz $INTERFACE NO soporta modo AP"
        echo "   No puedes crear un hotspot con esta interfaz"
        exit 1
    fi
}

# Configurar interfaz de red para hotspot
setup_network_hotspot() {
    echo "🔧 Configurando interfaz para hotspot..."
    
    # Detener NetworkManager
    sudo systemctl stop NetworkManager 2>/dev/null
    sleep 2
    
    # Limpiar configuración anterior
    sudo ip addr flush dev $INTERFACE 2>/dev/null
    sudo ip link set $INTERFACE down
    
    # Configurar IP estática para el hotspot
    sudo ip addr add $GATEWAY_IP/24 dev $INTERFACE
    sudo ip link set $INTERFACE up
    
    echo "✅ Interfaz configurada con IP: $GATEWAY_IP"
}

# Configurar DNSMasq para DHCP y DNS
setup_dnsmasq_hotspot() {
    echo "🌐 Configurando DNSMasq (DHCP + DNS)..."
    
    # Crear configuración de dnsmasq
    cat > /tmp/dnsmasq_hotspot.conf << EOF
# Configuración para Hotspot
interface=$INTERFACE
bind-interfaces

# Servidor DHCP
dhcp-range=192.168.4.10,192.168.4.100,255.255.255.0,24h
dhcp-option=3,$GATEWAY_IP  # Gateway
dhcp-option=6,$GATEWAY_IP  # DNS

# Redirección DNS para captive portal
address=/#/$GATEWAY_IP

# Logs detallados
log-dhcp
log-queries
log-facility=/tmp/dnsmasq.log

# Opciones adicionales para mejor funcionamiento
dhcp-authoritative
dhcp-leasefile=/tmp/dhcp.leases
EOF

    # Detener cualquier dnsmasq previo
    sudo pkill dnsmasq 2>/dev/null
    sleep 2
    
    # Iniciar dnsmasq
    sudo dnsmasq -C /tmp/dnsmasq_hotspot.conf --no-daemon &
    DNSMASQ_PID=$!
    
    # Esperar a que dnsmasq inicie
    sleep 3
    if ps -p $DNSMASQ_PID > /dev/null; then
        echo "✅ DNSMasq iniciado correctamente (PID: $DNSMASQ_PID)"
        echo "   - Rango DHCP: 192.168.4.10 - 192.168.4.100"
        echo "   - Gateway: $GATEWAY_IP"
        echo "   - DNS: $GATEWAY_IP"
    else
        echo "❌ Error: DNSMasq no se pudo iniciar"
        echo "   Revisa los logs en /tmp/dnsmasq.log"
        exit 1
    fi
}

# Configurar HostAPd para el punto de acceso
setup_hostapd() {
    echo "📡 Configurando punto de acceso WiFi..."
    
    # Crear configuración de hostapd
    sudo tee /etc/hostapd/hostapd.conf > /dev/null <<EOF
# Configuración básica del punto de acceso
interface=$INTERFACE
driver=nl80211
ssid=$SSID
hw_mode=g
channel=6
wmm_enabled=0
macaddr_acl=0
auth_algs=1
ignore_broadcast_ssid=0

# Configuración de seguridad WPA2
wpa=2
wpa_passphrase=$PASSWORD
wpa_key_mgmt=WPA-PSK
wpa_pairwise=TKIP
rsn_pairwise=CCMP

# Mejoras de rendimiento y compatibilidad
max_num_sta=10
logger_syslog=-1
logger_syslog_level=2
logger_stdout=-1
logger_stdout_level=2
EOF

    # Detener hostapd previo
    sudo pkill hostapd 2>/dev/null
    sleep 2
    
    # Iniciar hostapd en segundo plano con logs
    sudo hostapd -B /etc/hostapd/hostapd.conf -f /tmp/hostapd.log
    
    # Esperar a que hostapd inicie
    sleep 5
    if pgrep hostapd > /dev/null; then
        echo "✅ HostAPd iniciado correctamente"
        echo "   - SSID: $SSID"
        echo "   - Canal: 6"
        echo "   - Seguridad: WPA2"
    else
        echo "❌ Error: HostAPd no se pudo iniciar"
        echo "   Revisa los logs en /tmp/hostapd.log"
        exit 1
    fi
}

# Configurar iptables para NAT y redirección
setup_iptables_hotspot() {
    echo "🔀 Configurando reglas de redirección y NAT..."
    
    # Limpiar reglas anteriores
    sudo iptables -F
    sudo iptables -t nat -F
    sudo iptables -X
    sudo iptables -t nat -X
    
    # Politicas por defecto
    sudo iptables -P INPUT ACCEPT
    sudo iptables -P FORWARD ACCEPT
    sudo iptables -P OUTPUT ACCEPT
    
    # 1. NAT para el hotspot (MASQUERADE)
    sudo iptables -t nat -A POSTROUTING -o $INTERFACE -j MASQUERADE
    
    # 2. Redirigir HTTP (80) al servidor del captive portal
    sudo iptables -t nat -A PREROUTING -i $INTERFACE -p tcp --dport 80 -j DNAT --to-destination $GATEWAY_IP:$SERVER_PORT
    
    # 3. Redirigir HTTPS (443) al servidor del captive portal
    sudo iptables -t nat -A PREROUTING -i $INTERFACE -p tcp --dport 443 -j DNAT --to-destination $GATEWAY_IP:$SERVER_PORT
    
    # 4. Redirigir DNS (53) al servidor DNS local
    sudo iptables -t nat -A PREROUTING -i $INTERFACE -p udp --dport 53 -j DNAT --to-destination $GATEWAY_IP:53
    
    # 5. Permitir forward entre interfaces
    sudo iptables -A FORWARD -i $INTERFACE -o $INTERFACE -j ACCEPT
    
    echo "✅ Reglas de iptables configuradas:"
    echo "   - NAT activado"
    echo "   - Redirección HTTP/HTTPS/DNS"
    echo "   - Forwarding permitido"
}

# Verificar configuración completa
verify_setup() {
    echo ""
    echo "🔍 VERIFICANDO CONFIGURACIÓN COMPLETA"
    echo "====================================="
    
    # Verificar procesos
    echo "📊 Procesos activos:"
    if pgrep hostapd > /dev/null; then
        echo "   ✅ HostAPd: ACTIVO"
    else
        echo "   ❌ HostAPd: INACTIVO"
    fi
    
    if pgrep dnsmasq > /dev/null; then
        echo "   ✅ DNSMasq: ACTIVO"
    else
        echo "   ❌ DNSMasq: INACTIVO"
    fi
    
    # Verificar IP de la interfaz
    echo "🌐 Configuración de red:"
    if ip addr show $INTERFACE | grep -q "192.168.4.1"; then
        echo "   ✅ IP $GATEWAY_IP configurada en $INTERFACE"
    else
        echo "   ❌ IP NO configurada correctamente"
    fi
    
    # Verificar reglas iptables
    echo "🔀 Reglas de redirección:"
    sudo iptables -t nat -L PREROUTING 2>/dev/null | grep -E "(80|443|53)" && \
        echo "   ✅ Reglas de redirección activas" || \
        echo "   ❌ Reglas de redirección faltantes"
    
    # Verificar que el servidor esté listo
    echo "🐍 Servidor Python:"
    if netstat -tulpn 2>/dev/null | grep ":8000" > /dev/null; then
        echo "   ✅ Servidor escuchando en puerto 8000"
    else
        echo "   ⚠️  Servidor no escuchando (se iniciará después)"
    fi
    
    echo "====================================="
}

# Información para el usuario
show_instructions() {
    echo ""
    echo "🎯 HOTSPOT CAPTIVE PORTAL LISTO"
    echo "==============================="
    echo "📡 RED WIFI CREADA:"
    echo "   - Nombre (SSID): $SSID"
    echo "   - Contraseña: $PASSWORD"
    echo "   - Seguridad: WPA2"
    echo ""
    echo "🌐 CONFIGURACIÓN DE RED:"
    echo "   - Gateway: $GATEWAY_IP"
    echo "   - Rango DHCP: 192.168.4.10 - 192.168.4.100"
    echo "   - DNS: $GATEWAY_IP"
    echo ""
    echo "📱 PARA CONECTARSE:"
    echo "1. Busca la red '$SSID' en tu teléfono"
    echo "2. Conéctate con la contraseña '$PASSWORD'"
    echo "3. Espera a que obtenga IP (debería ser 192.168.4.x)"
    echo "4. Abre cualquier navegador y ve a cualquier página"
    echo "5. Serás redirigido automáticamente al portal de login"
    echo ""
    echo "🔧 CREDENCIALES DE PRUEBA:"
    echo "   Usuario: test"
    echo "   Contraseña: test"
    echo ""
    echo "🚀 INICIANDO SERVIDOR CAPTIVE PORTAL..."
    echo "Presiona Ctrl+C para detener todos los servicios"
    echo "==============================="
}

# Manejar Ctrl+C para limpiar
trap cleanup EXIT

# Ejecutar configuración paso a paso
echo "🚀 INICIANDO CONFIGURACIÓN..."
check_ap_support
setup_network_hotspot
setup_dnsmasq_hotspot
setup_hostapd
setup_iptables_hotspot
sleep 3
verify_setup
show_instructions

# Iniciar servidor captive portal
python3 server.py