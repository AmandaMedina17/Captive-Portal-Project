import socket
import threading
import subprocess
import os
import re
from urllib.parse import parse_qs

# Importar los managers
from auth_manager import AuthManager
from session_manager import NetworkSessionManager
from firewall_manager import FirewallManager

class HotspotServer:
    def __init__(self):
        self.host = '192.168.100.1'  # IP de la interfaz virtual
        self.port = 8000
        self.scripts_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Inicializar managers
        self.auth_manager = AuthManager()
        self.firewall_manager = FirewallManager(self.scripts_dir)
        self.session_manager = NetworkSessionManager(self.auth_manager,firewall_manager=self.firewall_manager)
        
    
    def unlock_client(self, client_ip, username):
        """Libera un cliente usando el session manager"""
        print(f"🔓 HotspotServer: Intentando liberar cliente: {client_ip}")
        
        # Verificar integridad MAC
        if not self.session_manager.verify_mac_integrity(client_ip, username):
            print(f"❌ HotspotServer: Bloqueado por posible suplantación: {client_ip}")
            return False
        
        # Ejecutar script de desbloqueo a traves de firewall manager
        success = self.firewall_manager.unlock_client(client_ip)
        
        if success:
            # Obtener MAC del cliente
            mac = self.session_manager.get_client_mac(client_ip)
            
            # Crear sesión
            session_created = self.session_manager.create_session(client_ip, username, mac)
            
            if session_created:
                print(f"✅ HotspotServer: Cliente {client_ip} liberado exitosamente")
                return True
            else:
                print(f"❌ HotspotServer: Error creando sesión para {client_ip}")
                return False
        else:
            print(f"❌ HotspotServer: Error ejecutando unlock.sh para {client_ip}")
            return False
    
    def block_client(self, client_ip, reason="timeout"):
        """Bloquea un cliente"""
        print(f"⏰ HotspotServer: Bloqueando cliente {client_ip} - Razón: {reason}")
        
        success = self.firewall_manager.block_client(client_ip)
        
        if success:
            self.session_manager.end_session(client_ip, reason)
            print(f"✅ HotspotServer: Cliente {client_ip} bloqueado")
            return True
        else:
            print(f"❌ HotspotServer: Error bloqueando cliente {client_ip}")
            return False
    
    def handle_request(self, conn, addr):
        """Maneja solicitudes HTTP"""
        try:
            data = conn.recv(4096).decode('utf-8', errors='ignore')
            if not data:
                return
            
            lines = data.split('\n')
            first_line = lines[0] if lines else ''
            parts = first_line.split(' ')
            
            if len(parts) < 2:
                return
            
            method = parts[0]
            path = parts[1]
            client_ip = addr[0]
            
            # Servir archivos estáticos
            if path == '/styles.css':
                self.serve_file(conn, 'styles.css', 'text/css')
                return
            
            response_body = self.process_request(method, path, data, client_ip)
            
            http_response = f"""HTTP/1.1 200 OK
Content-Type: text/html; charset=utf-8
Content-Length: {len(response_body)}

{response_body}"""
            
            conn.sendall(http_response.encode())
            
        except Exception as e:
            print(f"❌ HotspotServer Error en handle_request: {e}")
        finally:
            conn.close()
    
    def serve_file(self, conn, filename, content_type):
        """Sirve archivos estáticos"""
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                content = f.read()
            response = f"HTTP/1.1 200 OK\r\nContent-Type: {content_type}\r\n\r\n{content}"
            conn.sendall(response.encode())
        except:
            response = "HTTP/1.1 404 Not Found\r\n\r\nArchivo no encontrado"
            conn.sendall(response.encode())
    
    def process_request(self, method, path, data, client_ip):
        """Procesa solicitudes HTTP"""
        # Verificar sesión activa
        if self.session_manager.verify_active_session(client_ip):
            if path == '/logout':
                self.block_client(client_ip, reason="logout")
                return self.message_success("✅ Sesión cerrada exitosamente") + self.serve_html('portal.html')
            elif path == '/status':
                return self.success_page(client_ip)
            else:
                return self.success_page(client_ip)
        
        # Si no tiene sesión activa, mostrar portal
        if method == 'GET':
            if path == '/register':
                return self.serve_html('portal.html')
            elif path == '/logout':
                return self.message_success("✅ Ya has cerrado sesión") + self.serve_html('portal.html')
            else:
                return self.serve_html('portal.html')
        
        elif method == 'POST':
            body = data.split('\r\n\r\n')[1] if '\r\n\r\n' in data else ''
            params = parse_qs(body)
            
            username = params.get('username', [''])[0]
            password = params.get('password', [''])[0]
            
            if path == '/register':
                if self.auth_manager.register_user(username, password):
                    html = self.serve_html('portal.html')
                    success_msg = '<div class="alert success">✅ ¡Registro exitoso! Ahora puedes iniciar sesión.</div>'
                    return html.replace('<div id="login" class="tab-content active">', 
                                       success_msg + '<div id="login" class="tab-content active">')
                else:
                    html = self.serve_html('portal.html')
                    error_msg = '<div class="alert error">❌ Usuario ya existe</div>'
                    return html.replace('<div id="register" class="tab-content">', 
                                       error_msg + '<div id="register" class="tab-content">')
            else:  # login
                if self.auth_manager.verify_login(username, password):
                    print(f"👤 HotspotServer: Login exitoso: {username} desde {client_ip}")
                    
                    # Liberar al cliente
                    liberation_success = self.unlock_client(client_ip, username)
                    
                    if liberation_success:
                        return self.success_page(client_ip)
                    else:
                        html = self.serve_html('portal.html')
                        error_msg = '<div class="alert error">✅ Login exitoso, pero error al liberar acceso. Contacta al administrador.</div>'
                        return error_msg + html
                else:
                    print(f"❌ HotspotServer: Login fallido: {username} desde {client_ip}")
                    html = self.serve_html('portal.html')
                    error_msg = '<div class="alert error">❌ Credenciales incorrectas</div>'
                    return error_msg + html
        
        return self.serve_html('portal.html')
    
    def serve_html(self, filename):
        """Sirve archivos HTML"""
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                return f.read()
        except:
            return """
            <!DOCTYPE html>
            <html>
            <head><title>Error</title></head>
            <body>
                <h1>Portal de Acceso Hotspot</h1>
                <p>Error cargando la página</p>
            </body>
            </html>
            """
    
    def message_success(self, msg):
        return f'<div class="alert success">{msg}</div>'
    
    def message_error(self, msg):
        return f'<div class="alert error">{msg}</div>'
    
    def success_page(self, client_ip):
        """Genera página de éxito"""
        session_info = self.session_manager.get_session_info(client_ip)
        
        if session_info:
            remaining = session_info['remaining']
            minutes = int(remaining // 60)
            seconds = int(remaining % 60)
            time_remaining = f"{minutes}:{seconds:02d} minutos"
        else:
            time_remaining = "30 minutos"
        
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Acceso Concedido</title>
            <link rel="stylesheet" href="/styles.css">
            <meta http-equiv="refresh" content="300;url=/status">
        </head>
        <body>
            <div class="container">
                <div class="alert success">
                    ✅ ¡Acceso concedido!
                </div>
                <div class="dashboard">
                    <h2>Bienvenido a MiPortalCaptivo</h2>
                    <p>Dispositivo: {client_ip}</p>
                    <p>Tiempo restante de sesión: {time_remaining}</p>
                    <p>Ahora tienes acceso completo a internet.</p>
                    <div style="margin-top: 20px;">
                        <a href="http://google.com" class="btn" style="margin-bottom: 10px;">Continuar navegando</a>
                        <a href="/logout" class="btn" style="background: linear-gradient(135deg, #dc3545 0%, #c82333 100%);">Cerrar sesión</a>
                    </div>
                </div>
            </div>
        </body>
        </html>
        """
    
    def start(self):
        """Inicia el servidor"""
        print("🚀 SERVIDOR HOTSPOT INICIADO")
        print("============================")
        print(f"📡 Hotspot: MiPortalCautivo")
        print(f"🔗 IP: {self.host}:{self.port}")
        print(f"⏰ Timeout de sesión: {self.session_manager.session_timeout // 60} minutos")
        print(f"🔒 Detección de suplantación: ACTIVADA")
        print("👂 Esperando conexiones...")
        
        # Limpiar sesiones expiradas al inicio
        self.auth_manager.clean_expired_sessions()
        
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind((self.host, self.port))
                s.listen(5)
                
                while True:
                    conn, addr = s.accept()
                    thread = threading.Thread(target=self.handle_request, args=(conn, addr))
                    thread.daemon = True
                    thread.start()
                    
        except Exception as e:
            print(f"❌ ERROR: {e}")

if __name__ == "__main__":
    server = HotspotServer()
    server.start()