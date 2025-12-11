# import socket
# import sqlite3
# import hashlib
# import threading
# import subprocess
# import os
# from urllib.parse import parse_qs

# class HotspotServer:
#     def __init__(self):
#         self.host = '192.168.100.1'  # IP de la interfaz virtual
#         self.port = 8000
#         self.liberated_clients = set()
#         self.init_db()
#         self.scripts_dir = os.path.dirname(__file__)
    
#     def init_db(self):
#         conn = sqlite3.connect('usuarios.db')
#         cursor = conn.cursor()
#         cursor.execute('''
#             CREATE TABLE IF NOT EXISTS usuarios (
#                 id INTEGER PRIMARY KEY AUTOINCREMENT,
#                 username TEXT UNIQUE NOT NULL,
#                 password TEXT NOT NULL,
#                 ip_address TEXT,                   
#                 liberated INTEGER DEFAULT 0,         
#                 login_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP 
#             )
#         ''')
#         cursor.execute("INSERT OR IGNORE INTO usuarios (username, password) VALUES (?, ?)", 
#                       ('test', self.hash_password('test')))
#         conn.commit()
#         conn.close()
    
#     def hash_password(self, password):
#         return hashlib.sha256(password.encode()).hexdigest()

#     def run_script(self, script_name, parameters=None):
#         script_path = os.path.join(self.scripts_dir, script_name)
        
#         try:
#             if parameters:
#                 command = [script_path] + parameters
#                 result = subprocess.run(
#                     command, 
#                     check=True, 
#                     capture_output=True, 
#                     text=True
#                 )
#             else:
#                 result = subprocess.run(
#                     [script_path], 
#                     check=True, 
#                     capture_output=True, 
#                     text=True
#                 )
            
#             print(f"✅ {result.stdout.strip()}")
#             return True
            
#         except subprocess.CalledProcessError as e:
#             print(f"❌ Error ejecutando {script_name}: {e.stderr}")
#             return False


#     def unlock_client(self, client_ip):
#         """Ejecuta el script para desbloquear la IP del cliente"""
#         if client_ip in self.liberated_clients:
#             print(f"✅ Cliente {client_ip} ya estaba liberado")
#             return True
            
#         print(f"🔓 Intentando liberar cliente: {client_ip}")
#         success = self.run_script('unlock.sh', [client_ip])
        
#         if success:
#             self.liberated_clients.add(client_ip)
#             # Guardar en base de datos que está liberado
#             conn = sqlite3.connect('usuarios.db')
#             cursor = conn.cursor()
#             cursor.execute(
#                 "UPDATE usuarios SET ip_address = ?, liberated = 1 WHERE username = ?",
#                 (client_ip, self.get_username_by_ip(client_ip))
#             )
#             conn.commit()
#             conn.close()
#             print(f"✅ Cliente {client_ip} liberado y guardado en BD")
        
#         return success

#     def verify_unlocked_client(self, client_ip):
#         """Verifica si un cliente ya está liberado"""
#         if client_ip in self.liberated_clients:
#             return True
            
#         # Verificar en base de datos
#         try:
#             conn = sqlite3.connect('usuarios.db')
#             cursor = conn.cursor()
#             cursor.execute(
#                 "SELECT liberated FROM usuarios WHERE ip_address = ? AND liberated = 1",
#                 (client_ip,)
#             )
#             resultado = cursor.fetchone()
#             conn.close()
            
#             if resultado:
#                 self.liberated_clients.add(client_ip)
#                 return True
#         except:
#             pass
            
#         return False
    
#     def handle_request(self, conn, addr):
#         try:
#             data = conn.recv(4096).decode('utf-8', errors='ignore')
#             if not data:
#                 return
            
#             lines = data.split('\n')
#             first_line = lines[0] if lines else ''
#             parts = first_line.split(' ')
            
#             if len(parts) < 2:
#                 return
            
#             method = parts[0]
#             path = parts[1]
#             client_ip = addr[0]
            
#             if path == '/styles.css':
#                 self.serve_file(conn, 'styles.css', 'text/css')
#                 return
            
#             response_body = self.process_request(method, path, data, client_ip)
            
#             http_response = f"""HTTP/1.1 200 OK
# Content-Type: text/html; charset=utf-8
# Content-Length: {len(response_body)}

# {response_body}"""
            
#             conn.sendall(http_response.encode())
            
#         except Exception as e:
#             print(f"❌ Error: {e}")
#         finally:
#             conn.close()
    
#     def serve_file(self, conn, filename, content_type):
#         try:
#             with open(filename, 'r', encoding='utf-8') as f:
#                 content = f.read()
#             response = f"HTTP/1.1 200 OK\r\nContent-Type: {content_type}\r\n\r\n{content}"
#             conn.sendall(response.encode())
#         except:
#             response = "HTTP/1.1 404 Not Found\r\n\r\nArchivo no encontrado"
#             conn.sendall(response.encode())
    
#     def process_request(self, method, path, data, client_ip):
#         if method == 'GET':
#             if path == '/register':
#                 return self.serve_html('register.html')
#             elif path == '/success':
#                 return self.success_page(client_ip)
#             else:
#                 if self.verify_unlocked_client(client_ip):
#                     print("esta autenticado y no lo voy a mandar a hacer nada")
                    
#                 else:
#                     return self.serve_html('portal.html')
        
#         elif method == 'POST':
#             body = data.split('\r\n\r\n')[1] if '\r\n\r\n' in data else ''
#             params = parse_qs(body)
            
#             username = params.get('username', [''])[0]
#             password = params.get('password', [''])[0]
            
#             if path == '/register':
#                 if self.register_user(username, password):
#                     return self.serve_html('portal.html').replace(
#                         '<!-- MESSAGES -->', 
#                         '<div class="alert success">✅ ¡Registro exitoso! Ahora puedes iniciar sesión.</div>'
#                     )
#                 else:
#                     return self.serve_html('portal.html').replace(
#                         '<!-- MESSAGES -->', 
#                         '<div class="alert error">❌ Usuario ya existe</div>'
#                     )
#             else:  # login
#                 if self.verify_login(username, password):
#                     print(f"👤 Login exitoso: {username} desde {client_ip}")
                    
#                     # Liberar al cliente
#                     liberation_success = self.unlock_client(client_ip)
                    
#                     if liberation_success:
#                         return self.success_page(client_ip)
#                     else:
#                         return self.message_error("✅ Login exitoso, pero error al liberar acceso. Contacta al administrador.") + self.serve_html('portal.html')
#                 else:
#                     print(f"❌ Login fallido: {username} desde {client_ip}")
#                     return self.message_error("❌ Credenciales incorrectas") + self.serve_html('portal.html')
        
#         return self.serve_html('portal.html')
    
#     def get_username_by_ip(self, ip):
#         """Obtiene el username por IP"""
#         try:
#             conn = sqlite3.connect('usuarios.db')
#             cursor = conn.cursor()
#             cursor.execute(
#                 "SELECT username FROM usuarios WHERE ip_address = ?",
#                 (ip,)
#             )
#             result = cursor.fetchone()
#             conn.close()
#             return result[0] if result else None
#         except:
#             return None
    
    # def serve_html(self, filename):
    #     try:
    #         with open(filename, 'r', encoding='utf-8') as f:
    #             return f.read()
    #     except:
    #         return """
    #         <html>
    #         <body>
    #             <h1>Portal de Acceso Hotspot</h1>
    #             <p>Error cargando la página</p>
    #         </body>
    #         </html>
    #         """
    
#     def register_user(self, username, password):
#         try:
#             conn = sqlite3.connect('usuarios.db')
#             cursor = conn.cursor()
#             cursor.execute(
#                 "INSERT INTO usuarios (username, password) VALUES (?, ?)",
#                 (username, self.hash_password(password))
#             )
#             conn.commit()
#             conn.close()
#             return True
#         except:
#             return False
    
#     def verify_login(self, username, password):
#         try:
#             conn = sqlite3.connect('usuarios.db')
#             cursor = conn.cursor()
#             cursor.execute(
#                 "SELECT password FROM usuarios WHERE username = ?", 
#                 (username,)
#             )
#             resultado = cursor.fetchone()
#             conn.close()
#             return resultado and resultado[0] == self.hash_password(password)
#         except:
#             return False
    
#     def message_success(self, msg):
#         return f'<div class="alert success">{msg}</div>'
    
#     def message_error(self, msg):
#         return f'<div class="alert error">{msg}</div>'
    
#     def success_page(self, client_ip):
#         return f"""
#         <!DOCTYPE html>
#         <html>
#         <head>
#             <title>Acceso Concedido</title>
#             <link rel="stylesheet" href="/styles.css">
#         </head>
#         <body>
#             <div class="container">
#                 <div class="alert success">
#                     ✅ ¡Acceso concedido!
#                 </div>
#                 <div class="dashboard">
#                     <h2>Bienvenido a MiPortalCaptivo</h2>
#                     <p>Dispositivo: {client_ip}</p>
#                     <p>Ahora tienes acceso completo a internet.</p>
#                     <a href="http://google.com" class="btn">Continuar navegando</a>
#                 </div>
#             </div>
#         </body>
#         </html>
#         """
    
#     def start(self):
#         print("🚀 SERVIDOR HOTSPOT INICIADO")
#         print("============================")
#         print(f"📡 Hotspot: MiPortalCautivo")
#         print(f"🔗 IP: {self.host}:{self.port}")
#         print("👂 Esperando conexiones...")
        
#         try:
#             with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
#                 s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
#                 s.bind((self.host, self.port))
#                 s.listen(5)
                
#                 while True:
#                     conn, addr = s.accept()
#                     thread = threading.Thread(target=self.handle_request, args=(conn, addr))
#                     thread.daemon = True
#                     thread.start()
                    
#         except Exception as e:
#             print(f"❌ ERROR: {e}")

# if __name__ == "__main__":
#     server = HotspotServer()
#     server.start()

# server.py (actualizado)
import socket
import sqlite3
import hashlib
import threading
import subprocess
import os
from urllib.parse import parse_qs
from firewall_manager import FirewallManager
from session_manager import SessionTerminationReason, NetworkSessionManager

class HotspotServer:
    def __init__(self):
        self.host = '192.168.100.1'
        self.port = 8000
        self.liberated_clients = set()
        self.init_db()
        self.scripts_dir = os.path.dirname(__file__)
        
        # Inicializar gestores
        self.firewall_manager = FirewallManager()
        self.session_manager = NetworkSessionManager(
            firewall_manager=self.firewall_manager,
            timeout=1800,  # 30 minutos
            cleanup_interval=300  # 5 minutos
        )
    
    def init_db(self):
        conn = sqlite3.connect('usuarios.db')
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                ip_address TEXT,
                mac_address TEXT,
                liberated INTEGER DEFAULT 0,
                login_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Crear índice para búsquedas más rápidas
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_ip ON usuarios(ip_address)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_mac ON usuarios(mac_address)')
        
        cursor.execute("INSERT OR IGNORE INTO usuarios (username, password) VALUES (?, ?)", 
                      ('test', self.hash_password('test')))
        conn.commit()
        conn.close()
    
    def hash_password(self, password):
        return hashlib.sha256(password.encode()).hexdigest()
    
    def unlock_client(self, client_ip):
        """Desbloquea cliente - ahora manejado por SessionManager"""
        # Esta función se mantiene por compatibilidad, pero ahora usa el SessionManager
        print(f"⚠️  unlock_client obsoleto, usar SessionManager.create_session en su lugar")
        return True
    
    def verify_unlocked_client(self, client_ip):
        """Verifica si un cliente ya está autenticado"""
        valid, message = self.session_manager.verify_session(client_ip)
        
        if not valid:
            print(f"❌ Sesión inválida para {client_ip}: {message}")
        
        return valid
    
    def handle_request(self, conn, addr):
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
            print(f"❌ Error: {e}")
        finally:
            conn.close()

    def process_request(self, method, path, data, client_ip):
        if method == 'GET':
            if path == '/register':
                return self.serve_html('register.html')
            elif path == '/success':
                return self.success_page(client_ip)
            elif path == '/logout':
                # Cerrar sesión
                self.session_manager.terminate_session(client_ip, SessionTerminationReason.USER_LOGOUT)
                return self.logout_page()
            elif path == '/status':
                # Página de estado de sesión
                return self.status_page(client_ip)
            else:
                # Verificar si ya está autenticado
                if self.verify_unlocked_client(client_ip):
                    # Mostrar dashboard en lugar de redirigir
                    session_info = self.session_manager.get_session_info(client_ip)
                    if session_info:
                        return self.dashboard_page(client_ip, session_info)
                    else:
                        return self.success_page(client_ip)
                else:
                    # Mostrar portal de autenticación
                    return self.serve_html('portal.html')
        
        elif method == 'POST':
            body = data.split('\r\n\r\n')[1] if '\r\n\r\n' in data else ''
            params = parse_qs(body)
            
            username = params.get('username', [''])[0]
            password = params.get('password', [''])[0]
            
            if path == '/register':
                if self.register_user(username, password):
                    return self.serve_html('portal.html').replace(
                        '<!-- MESSAGES -->', 
                        '<div class="alert success">✅ ¡Registro exitoso! Ahora puedes iniciar sesión.</div>'
                    )
                else:
                    return self.serve_html('portal.html').replace(
                        '<!-- MESSAGES -->', 
                        '<div class="alert error">❌ Usuario ya existe</div>'
                    )
            else:  # login
                if self.verify_login(username, password):
                    print(f"👤 Login exitoso: {username} desde {client_ip}")
                    
                    # Obtener MAC del cliente
                    mac = self.get_client_mac(client_ip)
                    print(f"📱 MAC detectada: {mac}")
                    
                    # Crear sesión con gestión de MAC
                    session_created = self.session_manager.create_session(client_ip, username, mac)
                    
                    if session_created:
                        # Actualizar base de datos con IP y MAC
                        self.update_user_session(username, client_ip, mac)
                        
                        # Mostrar página de éxito con información de sesión
                        return self.success_page(client_ip)
                    else:
                        return self.message_error("✅ Login exitoso, pero error al crear sesión. Contacta al administrador.") + self.serve_html('portal.html')
                else:
                    print(f"❌ Login fallido: {username} desde {client_ip}")
                    return self.message_error("❌ Credenciales incorrectas") + self.serve_html('portal.html')
        
        return self.serve_html('portal.html')
    
    def verify_login(self, username, password):
        try:
            conn = sqlite3.connect('usuarios.db')
            cursor = conn.cursor()
            cursor.execute(
                "SELECT password FROM usuarios WHERE username = ?", 
                (username,)
            )
            resultado = cursor.fetchone()
            conn.close()
            return resultado and resultado[0] == self.hash_password(password)
        except:
            return False
    def serve_file(self, conn, filename, content_type):
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                content = f.read()
            response = f"HTTP/1.1 200 OK\r\nContent-Type: {content_type}\r\n\r\n{content}"
            conn.sendall(response.encode())
        except:
            response = "HTTP/1.1 404 Not Found\r\n\r\nArchivo no encontrado"
            conn.sendall(response.encode())
    
    def register_user(self, username, password):
        try:
            conn = sqlite3.connect('usuarios.db')
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO usuarios (username, password) VALUES (?, ?)",
                (username, self.hash_password(password))
            )
            conn.commit()
            conn.close()
            return True
        except:
            return False
    
    def serve_html(self, filename):
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                return f.read()
        except:
            return """
            <html>
            <body>
                <h1>Portal de Acceso Hotspot</h1>
                <p>Error cargando la página</p>
            </body>
            </html>
            """
    
    def get_client_mac(self, ip):
        """Obtiene la MAC de un cliente desde la tabla ARP"""
        try:
            result = subprocess.run(['ip', 'neigh', 'show', ip], 
                                  capture_output=True, text=True, timeout=2)
            
            if result.returncode == 0 and result.stdout:
                for line in result.stdout.strip().split('\n'):
                    if ip in line and ('REACHABLE' in line or 'STALE' in line):
                        parts = line.split()
                        if len(parts) >= 5:
                            return parts[4].upper().replace('-', ':')
            
        except Exception as e:
            print(f"⚠️ Error obteniendo MAC: {e}")
        
        return "00:00:00:00:00:00"
    
    def update_user_session(self, username, ip, mac):
        """Actualiza la información de sesión en la base de datos"""
        try:
            conn = sqlite3.connect('usuarios.db')
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE usuarios 
                SET ip_address = ?, mac_address = ?, liberated = 1, last_activity = CURRENT_TIMESTAMP
                WHERE username = ?
            ''', (ip, mac, username))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"❌ Error actualizando sesión en BD: {e}")
            return False
    
    def dashboard_page(self, client_ip, session_info):
        """Página de dashboard con información de sesión"""
        elapsed = self.session_manager._format_time(session_info['elapsed'])
        remaining = self.session_manager._format_time(session_info['remaining'])
        
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Dashboard - MiPortalCaptivo</title>
            <link rel="stylesheet" href="/styles.css">
        </head>
        <body>
            <div class="container">
                <div class="alert success">
                    ✅ ¡Sesión Activa!
                </div>
                <div class="dashboard">
                    <h2>Panel de Control</h2>
                    <div class="session-info">
                        <p><strong>Usuario:</strong> {session_info['username']}</p>
                        <p><strong>IP:</strong> {client_ip}</p>
                        <p><strong>MAC:</strong> {session_info.get('mac', 'No registrada')}</p>
                        <p><strong>Tiempo conectado:</strong> {elapsed}</p>
                        <p><strong>Tiempo restante:</strong> {remaining}</p>
                        <p><strong>Login:</strong> {session_info.get('login_timestamp', 'N/A')}</p>
                    </div>
                    <div class="actions">
                        <a href="http://google.com" class="btn">🌐 Navegar en Internet</a>
                        <a href="/status" class="btn" style="background: #17a2b8;">📊 Ver Estado</a>
                        <a href="/logout" class="btn" style="background: #dc3545;">🚪 Cerrar Sesión</a>
                    </div>
                </div>
            </div>
        </body>
        </html>
        """
    
    def status_page(self, client_ip):
        """Página de estado del sistema"""
        sessions = self.session_manager.get_all_sessions()
        session_count = len(sessions)
        
        sessions_html = ""
        for ip, session in sessions.items():
            elapsed = self.session_manager._format_time(session['elapsed'])
            remaining = self.session_manager._format_time(session['remaining'])
            
            sessions_html += f"""
            <div class="session-card">
                <h3>{session['username']}</h3>
                <p><strong>IP:</strong> {ip}</p>
                <p><strong>MAC:</strong> {session.get('mac', 'No registrada')}</p>
                <p><strong>Conectado:</strong> {elapsed}</p>
                <p><strong>Restante:</strong> {remaining}</p>
            </div>
            """
        
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Estado del Sistema</title>
            <link rel="stylesheet" href="/styles.css">
            <style>
                .session-card {{
                    background: #f8f9fa;
                    border: 1px solid #dee2e6;
                    border-radius: 10px;
                    padding: 15px;
                    margin: 10px 0;
                }}
                .stats {{
                    background: linear-gradient(135deg, #6a11cb 0%, #2575fc 100%);
                    color: white;
                    padding: 20px;
                    border-radius: 10px;
                    margin: 20px 0;
                    text-align: center;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>📊 Estado del Sistema</h1>
                
                <div class="stats">
                    <h2>Sesiones Activas: {session_count}</h2>
                    <p>Servidor: {self.host}:{self.port}</p>
                </div>
                
                <div class="sessions-list">
                    <h3>Sesiones Activas</h3>
                    {sessions_html if sessions_html else '<p class="alert info">No hay sesiones activas</p>'}
                </div>
                
                <div class="actions">
                    <a href="/success" class="btn">🏠 Volver al Dashboard</a>
                    <a href="/logout" class="btn" style="background: #dc3545;">🚪 Cerrar Sesión</a>
                </div>
            </div>
        </body>
        </html>
        """
    
    def logout_page(self):
        """Página de confirmación de cierre de sesión"""
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Sesión Cerrada</title>
            <link rel="stylesheet" href="/styles.css">
        </head>
        <body>
            <div class="container">
                <div class="alert info">
                    👋 Sesión Cerrada
                </div>
                <div class="dashboard">
                    <h2>¡Hasta pronto!</h2>
                    <p>Tu sesión ha sido cerrada exitosamente.</p>
                    <p>Tu acceso a internet ha sido revocado.</p>
                    <div class="actions">
                        <a href="/" class="btn">🔐 Iniciar Sesión Nuevamente</a>
                    </div>
                </div>
            </div>
        </body>
        </html>
        """
    
    def message_success(self, msg):
        return f'<div class="alert success">{msg}</div>'
    
    def message_error(self, msg):
        return f'<div class="alert error">{msg}</div>'
    
    def success_page(self, client_ip):
        # Mantener compatibilidad con código existente
        return self.dashboard_page(client_ip, {
            'username': 'Usuario',
            'elapsed': 0,
            'remaining': 1800,
            'mac': 'No disponible',
            'login_timestamp': 'Ahora'
        })
    
    def start(self):
        print("🚀 SERVIDOR HOTSPOT INICIADO")
        print("============================")
        print(f"📡 Hotspot: MiPortalCautivo")
        print(f"🔗 IP: {self.host}:{self.port}")
        print(f"⏰ Timeout de sesión: {self.session_manager.session_timeout}s")
        print("👂 Esperando conexiones...")
        
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
                    
        except KeyboardInterrupt:
            print("\n🛑 Deteniendo servidor...")
            self.session_manager.stop_cleanup()
            print("✅ Servidor detenido")
        except Exception as e:
            print(f"❌ ERROR: {e}")
            self.session_manager.stop_cleanup()

if __name__ == "__main__":
    server = HotspotServer()
    server.start()