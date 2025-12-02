#!/bin/bash

echo "🔒 Iniciando Portal Cautivo - Limpieza Mejorada"
echo "================================================"

# Verificar permisos root
if [ "$EUID" -ne 0 ]; then 
    echo "❌ Ejecutar con: sudo ./config.sh"
    exit 1
fi

# Configuración
INTERNET_INTERFACE="wlp58s0"
HOTSPOT_INTERFACE="wlp58s0_ap"
SSID="MiPortalCaptivo"
PASSWORD="portal123"
GATEWAY_IP="192.168.100.1"
SERVER_PORT="8000"

# Función de limpieza MEJORADA
cleanup() {
    echo ""
    echo "🧹 Limpiando configuración de forma agresiva..."
    
    # Matar procesos de forma más agresiva
    pkill -9 hostapd 2>/dev/null
    pkill -9 dnsmasq 2>/dev/null
    pkill -9 -f "python3 server.py" 2>/dev/null
    
    # Esperar a que los procesos terminen
    sleep 3
    
    # Limpiar reglas iptables
    iptables -t nat -F 2>/dev/null
    iptables -F 2>/dev/null
    iptables -X 2>/dev/null
    iptables -t nat -X 2>/dev/null

    # Limpiar procesos residuales
    sudo pkill -9 dnsmasq 2>/dev/null
    sudo pkill -9 hostapd 2>/dev/null
    
    # 🔥 LIMPIEZA AGREGADA: Eliminar archivos temporales
    sudo rm -f /tmp/dnsmasq.log
    sudo rm -f /tmp/dhcp.leases
    sudo rm -f /tmp/hostapd.log
    sudo rm -f /tmp/dnsmasq_ap.conf
    
    # Crear archivos limpios
    sudo touch /tmp/dnsmasq.log
    sudo chmod 666 /tmp/dnsmasq.log
    sudo touch /tmp/dhcp.leases
    sudo chmod 666 /tmp/dhcp.leases

    # 🔥 LIMPIEZA MEJORADA de interfaz virtual
    echo "🗑️  Eliminando interfaz virtual..."
    ip link set $HOTSPOT_INTERFACE down 2>/dev/null
    sleep 2
    iw dev $HOTSPOT_INTERFACE del 2>/dev/null
    sleep 2
    
    # Intentar múltiples veces si falla
    if iw dev | grep -q $HOTSPOT_INTERFACE; then
        echo "⚠️  Primera eliminación falló, intentando de nuevo..."
        ip link set $HOTSPOT_INTERFACE down 2>/dev/null
        iw dev $HOTSPOT_INTERFACE del 2>/dev/null
        sleep 2
    fi
    
    # Verificar eliminación
    if iw dev | grep -q $HOTSPOT_INTERFACE; then
        echo "❌ No se pudo eliminar la interfaz virtual"
    else
        echo "✅ Interfaz virtual eliminada"
    fi
    
    # Restaurar NetworkManager
    systemctl restart NetworkManager 2>/dev/null
    sleep 2
    
    echo "✅ Configuración limpiada completamente"
    exit 0
}

# 🔥 NUEVA FUNCIÓN: Limpieza inicial agresiva
aggressive_cleanup() {
    echo "[0/7] 🔥 Limpieza inicial agresiva..."
    
    # Matar todos los procesos relacionados
    pkill -9 hostapd 2>/dev/null
    pkill -9 dnsmasq 2>/dev/null
    pkill -9 -f "python3 server.py" 2>/dev/null
    
    # Limpiar iptables completamente
    iptables -t nat -F 2>/dev/null
    iptables -F 2>/dev/null
    iptables -X 2>/dev/null
    iptables -t nat -X 2>/dev/null
    
    # Eliminar interfaz virtual de forma forzada
    echo "🗑️  Eliminando interfaz virtual existente..."
    ip link set $HOTSPOT_INTERFACE down 2>/dev/null
    iw dev $HOTSPOT_INTERFACE del 2>/dev/null
    
    # Esperar y verificar
    sleep 3
    if iw dev | grep -q $HOTSPOT_INTERFACE; then
        echo "⚠️  Interfaz aún existe, forzando eliminación..."
        # Método alternativo
        iw dev $HOTSPOT_INTERFACE del 2>/dev/null
        sleep 2
    fi
    
    # Limpiar archivos temporales
    rm -f /tmp/dnsmasq.log /tmp/dhcp.leases /tmp/hostapd.log /tmp/dnsmasq_ap.conf
    
    echo "✅ Limpieza inicial completada"
}

# Configurar interfaz virtual MEJORADA
setup_virtual_interface() {
    echo "[1/7] Configurando interfaz virtual..."
    
    # 🔥 VERIFICAR SI LA INTERFAZ YA EXISTE
    if iw dev | grep -q $HOTSPOT_INTERFACE; then
        echo "⚠️  La interfaz virtual ya existe, eliminando..."
        ip link set $HOTSPOT_INTERFACE down 2>/dev/null
        iw dev $HOTSPOT_INTERFACE del 2>/dev/null
        sleep 3
    fi
    
    # Verificar que la interfaz principal esté activa
    if ! ip link show $INTERNET_INTERFACE | grep -q "state UP"; then
        echo "❌ La interfaz principal $INTERNET_INTERFACE no está activa"
        echo "🔧 Activando interfaz principal..."
        ip link set $INTERNET_INTERFACE up
        sleep 3
    fi
    
    # Crear interfaz virtual AP
    echo "📡 Creando interfaz virtual $HOTSPOT_INTERFACE..."
    if ! iw dev $INTERNET_INTERFACE interface add $HOTSPOT_INTERFACE type __ap; then
        echo "❌ Error creando interfaz virtual"
        echo "💡 Intentando método alternativo..."
        # Método alternativo
        iw phy `iw dev $INTERNET_INTERFACE info | grep wiphy | awk '{print $2}'` interface add $HOTSPOT_INTERFACE type __ap
        if [ $? -ne 0 ]; then
            echo "❌ Error crítico: No se puede crear la interfaz virtual"
            exit 1
        fi
    fi
    
    sleep 3
    
    # Activar interfaz
    echo "⚡ Activando interfaz virtual..."
    ip link set dev $HOTSPOT_INTERFACE up
    sleep 2
    
    # Verificar activación
    if ip link show $HOTSPOT_INTERFACE | grep -q "state UP"; then
        echo "✅ Interfaz virtual activada"
    else
        echo "⚠️  Interfaz virtual creada pero no se pudo activar completamente"
    fi
    
    # Asignar IP
    echo "🔢 Asignando IP $GATEWAY_IP/24..."
    ip addr flush dev $HOTSPOT_INTERFACE 2>/dev/null
    ip addr add $GATEWAY_IP/24 dev $HOTSPOT_INTERFACE
    sleep 2
    
    # Verificar IP
    if ip addr show $HOTSPOT_INTERFACE | grep -q "$GATEWAY_IP"; then
        echo "✅ Interfaz configurada: $GATEWAY_IP/24"
    else
        echo "❌ Error: No se asignó la IP correctamente"
        exit 1
    fi
}

# Configurar NetworkManager para ignorar la interfaz virtual
configure_network_manager() {
    echo "[2/7] Configurando NetworkManager..."
    
    # Hacer que NetworkManager ignore la interfaz virtual
    if command -v nmcli > /dev/null 2>&1; then
        nmcli dev set $HOTSPOT_INTERFACE managed no 2>/dev/null
        echo "✅ NetworkManager configurado para ignorar $HOTSPOT_INTERFACE"
    else
        echo "⚠️  nmcli no disponible, saltando configuración NetworkManager"
    fi
}

# Configurar NAT y redirección
setup_nat_redirect() {
    echo "[3/7] Configurando NAT y redirección..."
    
    # Habilitar forwarding
    echo 1 > /proc/sys/net/ipv4/ip_forward
    
    # # Limpiar reglas anteriores
    # iptables -t nat -F 2>/dev/null
    # iptables -F 2>/dev/null
    
    # # Configurar NAT
    # iptables -t nat -A POSTROUTING -o $INTERNET_INTERFACE -j MASQUERADE
    # iptables -A FORWARD -i $HOTSPOT_INTERFACE -o $INTERNET_INTERFACE -j ACCEPT
    # iptables -A FORWARD -i $INTERNET_INTERFACE -o $HOTSPOT_INTERFACE -m state --state RELATED,ESTABLISHED -j ACCEPT
    
    # # Redirección para captive portal
    # iptables -t nat -A PREROUTING -i $HOTSPOT_INTERFACE -p tcp --dport 80 -j REDIRECT --to-port $SERVER_PORT
    # iptables -t nat -A PREROUTING -i $HOTSPOT_INTERFACE -p tcp --dport 443 -j REDIRECT --to-port $SERVER_PORT
    
    # echo "✅ NAT y redirección configurados"
}

# Configurar DNSMasq
setup_dnsmasq() {
    echo "[4/7] Iniciando servidor DHCP y DNS..."
    
    cat > /tmp/dnsmasq_ap.conf << EOF
interface=$HOTSPOT_INTERFACE
bind-interfaces
dhcp-range=192.168.100.50,192.168.100.150,12h
dhcp-option=3,$GATEWAY_IP
dhcp-option=6,$GATEWAY_IP
server= 8.8.8.8
# address=/#/$GATEWAY_IP
log-dhcp
# log-queries
# log-facility=/tmp/dnsmasq.log
# dhcp-authoritative
# dhcp-leasefile=/tmp/dhcp.leases
EOF

    dnsmasq -C /tmp/dnsmasq_ap.conf
    sleep 2
    
    if pgrep dnsmasq > /dev/null; then
        echo "✅ Servidor DHCP y DNS activo"
    else
        echo "❌ Error iniciando DHCP/DNS"
        exit 1
    fi
}

# Configurar HostAPd
setup_hostapd() {
    echo "[5/7] Configurando Access Point..."
    
    mkdir -p /etc/hostapd
    cat > /etc/hostapd/hostapd.conf << EOF
interface=$HOTSPOT_INTERFACE
driver=nl80211
ssid=$SSID
hw_mode=g
channel=6
wmm_enabled=1 #0
macaddr_acl=0
auth_algs=1
ignore_broadcast_ssid=0
wpa=2
wpa_passphrase=$PASSWORD
wpa_key_mgmt=WPA-PSK
wpa_pairwise=TKIP
rsn_pairwise=CCMP
# max_num_sta=10
EOF

    hostapd /etc/hostapd/hostapd.conf > /tmp/hostapd.log 2>&1 &
    sleep 5
    
    if pgrep hostapd > /dev/null; then
        echo "✅ Access Point iniciado - SSID: $SSID"
    else
        echo "❌ Error iniciando AP"
        echo "🔍 Últimas líneas del log:"
        tail -10 /tmp/hostapd.log
        exit 1
    fi
}

# Verificar configuración
verify_setup() {
    echo "[6/7] Verificando configuración..."
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "🔍 ESTADO DEL SISTEMA"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    echo "📊 Procesos:"
    pgrep hostapd > /dev/null && echo "   ✅ HostAPd: ACTIVO" || echo "   ❌ HostAPd: INACTIVO"
    pgrep dnsmasq > /dev/null && echo "   ✅ DNSMasq: ACTIVO" || echo "   ❌ DNSMasq: INACTIVO"
    
    echo "🌐 Estado interfaz virtual:"
    if iw dev | grep -q $HOTSPOT_INTERFACE; then
        echo "   ✅ $HOTSPOT_INTERFACE: EXISTE"
        ip addr show $HOTSPOT_INTERFACE | grep "inet" | sed 's/^/      /' || echo "      ❌ Sin IP configurada"
    else
        echo "   ❌ $HOTSPOT_INTERFACE: NO EXISTE"
    fi
    
    echo "📡 WiFi: $SSID"
    echo "🔑 Password: $PASSWORD" 
    echo "🌐 Gateway: $GATEWAY_IP"
    echo "🖥️  Portal: http://$GATEWAY_IP:$SERVER_PORT"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
}

# Iniciar servidor web
start_webserver() {
    echo "[7/7] Iniciando servidor web..."
    
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    cd "$SCRIPT_DIR"
    
    if [ -f "server.py" ]; then
        echo "🚀 Ejecutando servidor..."
        python3 server.py
    else
        echo "❌ No se encuentra server.py"
        echo "Hotspot activo. Ejecuta manualmente: python3 server.py"
        trap cleanup INT
        while true; do sleep 60; done
    fi
}

# Bloquear la conexion para todos los cliente
block_all() {
    #Configura el portal cautivo para dispositivos conectados a la WiFi   
    INTERNET_IFACE="wlp58s0"
    LOCAL_IFACE="wlp58s0_ap"

    # Limpiar reglas existentes
    iptables -t nat -F

    # Políticas por defecto: bloquear todo forwarding
    iptables -P INPUT ACCEPT
    iptables -P OUTPUT ACCEPT
    iptables -P FORWARD DROP

    #Permitir resolver DNS
    iptables -A FORWARD -i "$LOCAL_IFACE" -o "$INTERNET_IFACE" -p udp --dport 53 -j ACCEPT
    iptables -A FORWARD -i "$LOCAL_IFACE" -o "$INTERNET_IFACE" -p tcp --dport 53 -j ACCEPT

    # NAT - permite que dispositivos compartan tu internet (después de autenticar)
    iptables -t nat -A POSTROUTING -o $INTERNET_IFACE -j MASQUERADE

    # PERMITIR acceso al servidor web del portal (puerto 8080)
    iptables -A FORWARD -i $LOCAL_IFACE -p tcp --dport 8000 -j ACCEPT

    #Hacer redireccionamiento
    iptables -t nat -A PREROUTING -i "$LOCAL_IFACE" -p tcp --dport 80 -j REDIRECT --to-port 8000
    iptables -t nat -A PREROUTING -i "$LOCAL_IFACE" -p tcp --dport 443 -j REDIRECT --to-port 8000

    echo "Firewall configurado"
}

# Manejar Ctrl+C
trap cleanup INT TERM EXIT

# 🔥 EJECUCIÓN PRINCIPAL MEJORADA
aggressive_cleanup
setup_virtual_interface
configure_network_manager
setup_nat_redirect
setup_dnsmasq
setup_hostapd
sleep 3
verify_setup

echo "🎯 PORTAL CAUTIVO CONFIGURADO"
echo "============================="
echo "📱 Para probar:"
echo "1. Conéctate a: $SSID"
echo "2. Abre cualquier navegador"
echo "3. Debe aparecer automáticamente el login"
echo "4. Usa: test / test"
echo ""
echo "🚀 INICIANDO SERVIDOR..."
echo "============================="

block_all
start_webserver