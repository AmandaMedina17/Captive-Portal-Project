import socket
import sqlite3
import hashlib
import threading
import subprocess
import os
import re
from urllib.parse import parse_qs

class HotspotServer:
    def __init__(self):
        self.host = '192.168.100.1'  # IP de la interfaz virtual
        self.port = 8000
        self.liberated_clients = set()
        self.init_db()
        self.scripts_dir = os.path.dirname(__file__)
    
    def init_db(self):
        conn = sqlite3.connect('usuarios.db')
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                ip_address TEXT,                   
                liberated INTEGER DEFAULT 0,         
                login_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP 
            )
        ''')
        cursor.execute("INSERT OR IGNORE INTO usuarios (username, password) VALUES (?, ?)", 
                      ('test', self.hash_password('test')))
        conn.commit()
        conn.close()
    
    def hash_password(self, password):
        return hashlib.sha256(password.encode()).hexdigest()

    def run_script(self, script_name, parameters=None):
        script_path = os.path.join(self.scripts_dir, script_name)
        
        try:
            if parameters:
                command = [script_path] + parameters
                result = subprocess.run(
                    command, 
                    check=True, 
                    capture_output=True, 
                    text=True
                )
            else:
                result = subprocess.run(
                    [script_path], 
                    check=True, 
                    capture_output=True, 
                    text=True
                )
            
            print(f"✅ {result.stdout.strip()}")
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"❌ Error ejecutando {script_name}: {e.stderr}")
            return False


    def unlock_client(self, client_ip):
        """Ejecuta el script para desbloquear la IP del cliente"""
        if client_ip in self.liberated_clients:
            print(f"✅ Cliente {client_ip} ya estaba liberado")
            return True
            
        print(f"🔓 Intentando liberar cliente: {client_ip}")
        success = self.run_script('unlock.sh', [client_ip])
        
        if success:
            self.liberated_clients.add(client_ip)
            # Guardar en base de datos que está liberado
            conn = sqlite3.connect('usuarios.db')
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE usuarios SET ip_address = ?, liberated = 1 WHERE username = ?",
                (client_ip, self.get_username_by_ip(client_ip))
            )
            conn.commit()
            conn.close()
            print(f"✅ Cliente {client_ip} liberado y guardado en BD")
        
        return success

    def verify_unlocked_client(self, client_ip):
        """Verifica si un cliente ya está liberado"""
        if client_ip in self.liberated_clients:
            return True
            
        # Verificar en base de datos
        try:
            conn = sqlite3.connect('usuarios.db')
            cursor = conn.cursor()
            cursor.execute(
                "SELECT liberated FROM usuarios WHERE ip_address = ? AND liberated = 1",
                (client_ip,)
            )
            resultado = cursor.fetchone()
            conn.close()
            
            if resultado:
                self.liberated_clients.add(client_ip)
                return True
        except:
            pass
            
        return False
    
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
    
    def serve_file(self, conn, filename, content_type):
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                content = f.read()
            response = f"HTTP/1.1 200 OK\r\nContent-Type: {content_type}\r\n\r\n{content}"
            conn.sendall(response.encode())
        except:
            response = "HTTP/1.1 404 Not Found\r\n\r\nArchivo no encontrado"
            conn.sendall(response.encode())
    
    def process_request(self, method, path, data, client_ip):
        if method == 'GET':
            if path == '/register':
                return self.serve_html('register.html')
            elif path == '/success':
                return self.success_page(client_ip)
            else:
                if self.verify_unlocked_client(client_ip):
                    print("esta autenticado y no lo voy a mandar a hacer nada")
                    
                else:
                    return self.serve_html('portal.html')
        
        elif method == 'POST':
            body = data.split('\r\n\r\n')[1] if '\r\n\r\n' in data else ''
            params = parse_qs(body)
            
            username = params.get('username', [''])[0]
            password = params.get('password', [''])[0]
            
            if path == '/register':
                if self.register_user(username, password):
                    html = self.serve_html('portal.html')
                    # Insertar mensaje de éxito en el contenedor de registro
                    html = self.inject_message(html, 
                        '<div class="alert success">¡Registro exitoso!</div>',
                        'register')
                    return html
                else:
                    html = self.serve_html('portal.html')
                    # Insertar mensaje de error en el contenedor de registro
                    html = self.inject_message(html,
                        '<div class="alert error">Usuario ya existe o error en el registro.</div>',
                        'register')
                    return html
            else:  # login
                if self.verify_login(username, password):
                    print(f" Login exitoso: {username} desde {client_ip}")
                    
                    # Liberar al cliente
                    liberation_success = self.unlock_client(client_ip)
                    
                    if liberation_success:
                        return self.success_page(client_ip)
                    else:
                        html = self.serve_html('portal.html')
                        html = self.inject_message(html,
                            '<div class="alert error">✅ Login exitoso, pero error al liberar acceso. Contacta al administrador.</div>',
                            'login')
                        return html
                else:
                    print(f"❌ Login fallido: {username} desde {client_ip}")
                    html = self.serve_html('portal.html')
                    html = self.inject_message(html,
                        '<div class="alert error">Credenciales incorrectas. Inténtalo de nuevo.</div>',
                            'login')
                    return html        
        return self.serve_html('portal.html')
    
    def inject_message(self, html, message, target):

        if target == 'login':
            # Reemplazar el contenido de login-messages
            pattern = r'<div id="login-messages" class="messages-container">.*?</div>'
            replacement = f'<div id="login-messages" class="messages-container">{message}</div>'
            return re.sub(pattern, replacement, html, flags=re.DOTALL)
        elif target == 'register':
            # Reemplazar el contenido de register-messages
            pattern = r'<div id="register-messages" class="messages-container">.*?</div>'
            replacement = f'<div id="register-messages" class="messages-container">{message}</div>'
            html = re.sub(pattern, replacement, html, flags=re.DOTALL)
            # También necesitamos cambiar a la pestaña de registro
            html = self.inject_script(html, "openTab('register');")
            return html
        return html
    

    def inject_script(self, html, script_code):
        script = f"""
        <script>
            document.addEventListener('DOMContentLoaded', function() {{
                {script_code}
            }});
        </script>
        """
        return html.replace('</body>', script + '</body>')
    
    
    def get_username_by_ip(self, ip):
        """Obtiene el username por IP"""
        try:
            conn = sqlite3.connect('usuarios.db')
            cursor = conn.cursor()
            cursor.execute(
                "SELECT username FROM usuarios WHERE ip_address = ?",
                (ip,)
            )
            result = cursor.fetchone()
            conn.close()
            return result[0] if result else None
        except:
            return None
    
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
    
    def message_success(self, msg):
        return f'<div class="alert success">{msg}</div>'
    
    def message_error(self, msg):
        return f'<div class="alert error">{msg}</div>'
    
    def success_page(self, client_ip):
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Autenticación Exitosa</title>
            <link rel="stylesheet" href="/styles.css">
        </head>
        <body>
            <div class="container">
                <div class="success-card">
                    <div class="success-icon">✅</div>
                    
                    <h1 class="success-message">¡Autenticación Exitosa!</h1>
                    
                    <p>Ya puede conectarse a internet. Su acceso ha sido autorizado.</p>
                    
                    <div class="connection-details">
                        <div class="detail-item">
                            <span class="detail-label">Estado de conexión:</span>
                            <span class="detail-value">
                                <span class="status-indicator"></span>
                                Conectado
                            </span>
                        </div>
                        <div class="detail-item">
                            <span class="detail-label">IP del dispositivo:</span>
                            <span class="detail-value">{client_ip}</span>
                        </div>
                    </div>
                </div>
            </div>
        </body>
        </html>
        """
    
    def start(self):
        print("🚀 SERVIDOR HOTSPOT INICIADO")
        print("============================")
        print(f"📡 Hotspot: MiPortalCautivo")
        print(f"🔗 IP: {self.host}:{self.port}")
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
                    
        except Exception as e:
            print(f"❌ ERROR: {e}")

if __name__ == "__main__":
    server = HotspotServer()
    server.start()