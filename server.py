import socket
import sqlite3
import hashlib
import threading
from urllib.parse import parse_qs

class HotspotServer:
    def __init__(self):
        self.host = '192.168.4.1'  # IP del hotspot
        self.port = 8000
        self.init_db()
    
    def init_db(self):
        conn = sqlite3.connect('usuarios.db')
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL
            )
        ''')
        cursor.execute("INSERT OR IGNORE INTO usuarios (username, password) VALUES (?, ?)", 
                      ('test', self.hash_password('test')))
        conn.commit()
        conn.close()
    
    def hash_password(self, password):
        return hashlib.sha256(password.encode()).hexdigest()
    
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
                return self.serve_html('portal.html')
        
        elif method == 'POST':
            body = data.split('\r\n\r\n')[1] if '\r\n\r\n' in data else ''
            params = parse_qs(body)
            
            username = params.get('username', [''])[0]
            password = params.get('password', [''])[0]
            
            if path == '/register':
                if self.registrar_usuario(username, password):
                    # Mensaje de éxito debajo del formulario
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
                if self.verificar_login(username, password):
                    return self.success_page(client_ip)
                else:
                    return self.message_error("❌ Credenciales incorrectas") + self.serve_html('portal.html')
        
        return self.serve_html('portal.html')
    
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
    
    def registrar_usuario(self, username, password):
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
    
    def verificar_login(self, username, password):
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
            <title>Acceso Concedido</title>
            <link rel="stylesheet" href="/styles.css">
        </head>
        <body>
            <div class="container">
                <div class="alert success">
                    ✅ ¡Acceso concedido!
                </div>
                <div class="dashboard">
                    <h2>Bienvenido a MiPortalCaptivo</h2>
                    <p>Dispositivo: {client_ip}</p>
                    <p>Ahora tienes acceso completo a internet.</p>
                    <a href="http://google.com" class="btn">Continuar navegando</a>
                </div>
            </div>
        </body>
        </html>
        """
    
    def iniciar(self):
        print("🚀 SERVIDOR HOTSPOT INICIADO")
        print("============================")
        print(f"📡 Hotspot: MiPortalCaptivo")
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
    server.iniciar()