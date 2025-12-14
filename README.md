🔐 Portal Cautivo
📋 Descripción del Proyecto

Este proyecto implementa un portal cautivo completo que controla el acceso a una red mediante autenticación de usuarios. Cuando un dispositivo se conecta a la red, su comunicación está restringida hasta que el usuario inicie sesión a través de un portal web. Una vez autenticado, el usuario obtiene acceso completo a Internet.

El sistema actúa como gateway de la red y proporciona:

    Autenticación mediante usuario/contraseña

    Control de sesiones con timeout configurable

    Detección de suplantación de IP/MAC

    Firewall para bloqueo/desbloqueo dinámico

    Interfaz web responsiva

🎯 Características Principales
✅ Requisitos Mínimos Cumplidos:

    Endpoint HTTP de inicio de sesión - Portal web en http://192.168.100.1:8000

    Bloqueo de enrutamiento sin autenticación - Firewall bloquea todo tráfico excepto el portal

    Mecanismo de cuentas de usuario - Registro y autenticación con base de datos SQLite

    Manejo concurrente de usuarios - Servidor multihilo con sesiones independientes

⭐ Extras Implementados:

    Detección automática del portal - Redirección automática de tráfico HTTP al portal

    Control de suplantación - Verificación de integridad MAC/IP para prevenir suplantación

    Enmascaramiento IP (NAT) - Configuración NAT para compartir conexión a Internet

    Experiencia de usuario - Interfaz web moderna y responsiva

    Creatividad - Sistema completo con gestión de sesiones, timeout automático y logs detallados

🏗️ Arquitectura del Sistema
Componentes Principales:

    server.py - Servidor HTTP principal que maneja las conexiones

    auth_manager.py - Gestión de autenticación y base de datos de usuarios

    session_manager.py - Control de sesiones con timeout y detección de suplantación

    firewall_manager.py - Interfaz para bloquear/desbloquear IPs en el firewall

    config.sh - Script de configuración del hotspot y firewall

Archivos de Soporte:

    portal.html - Interfaz web del portal de autenticación

    styles.css - Estilos para la interfaz web

    block.sh / unlock.sh - Scripts para control del firewall

    usuarios.db - Base de datos SQLite de usuarios (generada automáticamente)

📡 Configuración de Red
Parámetros por Defecto:

    SSID: MiPortalCautivo

    Password: portal123

    Gateway IP: 192.168.100.1

    Rango DHCP: 192.168.100.50-150

    Puerto Servidor: 8000

Personalización:

Editar config.sh para modificar:
bash

INTERNET_INTERFACE="wlp58s0"        # Tu interfaz de Internet
HOTSPOT_INTERFACE="wlp58s0_ap"      # Interfaz virtual del hotspot
SSID="MiPortalCautivo"              # Nombre de la red WiFi
PASSWORD="portal123"                # Contraseña WiFi
GATEWAY_IP="192.168.100.1"          # IP del portal

🚀 Uso del Sistema
1. Configurar el hotspot:
bash

# Dar permisos de ejecución
chmod +x config.sh block.sh unlock.sh

2. Iniciar el Portal Cautivo:
bash

sudo ./config.sh

3. Conectar Dispositivos:

    Conectarse a la red WiFi MiPortalCautivo

    Abrir cualquier navegador web

    Será redirigido automáticamente al portal de autenticación

4. Cuentas de Prueba:

    Usuario: test

    Contraseña: test

5. Registrar Nuevos Usuarios:

Desde el portal web, usar la pestaña "Registrarse"

🔒 Características de Seguridad
Detección de Suplantación:

    Verificación de integridad MAC/IP

    Alerta ante cambios sospechosos de dirección MAC

    Terminación automática de sesiones comprometidas

Gestión de Sesiones:

    Timeout configurable (30 minutos por defecto)

    Renovación automática al verificar sesión

    Almacenamiento persistente en base de datos

    Limpieza automática de sesiones expiradas

Control de Firewall:

    Bloqueo total sin autenticación

    Desbloqueo específico por IP tras autenticación

    Reglas dinámicas basadas en estado de sesión

📝 Consideraciones Técnicas
Limitaciones:

    Requiere interfaz WiFi con soporte para modo AP

    Necesita permisos root para configuración de red

    Solo funciona en sistemas Linux

    No implementa HTTPS 

👥 Flujo de Trabajo

    Conexión del cliente → Bloqueo automático por firewall

    Redirección al portal → Captura de tráfico HTTP

    Autenticación → Verificación en base de datos

    Desbloqueo → Reglas específicas en firewall

    Sesión activa → Timeout y verificación periódica

    Cierre de sesión → Bloqueo y limpieza
