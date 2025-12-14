import sqlite3
import hashlib

class AuthManager:
    """Maneja autenticación y registro de usuarios"""
    
    def __init__(self, db_path='usuarios.db'):
        self.db_path = db_path
        self.init_db()
    
    def init_db(self):
        """Inicializa la base de datos con estructura necesaria"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                ip_address TEXT,
                mac_address TEXT DEFAULT '00:00:00:00:00:00',
                session_start TIMESTAMP DEFAULT NULL,
                session_expire TIMESTAMP DEFAULT NULL,
                liberated INTEGER DEFAULT 0,
                login_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Asegurar que la columna mac_address existe
        try:
            cursor.execute("ALTER TABLE usuarios ADD COLUMN mac_address TEXT DEFAULT '00:00:00:00:00:00'")
        except sqlite3.OperationalError:
            pass
        
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_ip ON usuarios(ip_address)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_mac ON usuarios(mac_address)')
        
        cursor.execute(
            "INSERT OR IGNORE INTO usuarios (username, password) VALUES (?, ?)",
            ('test', self.hash_password('test'))
        )
        
        conn.commit()
        conn.close()
        print("✅ AuthManager: Base de datos inicializada")
    
    def hash_password(self, password):
        """Hashea una contraseña usando SHA256"""
        return hashlib.sha256(password.encode()).hexdigest()
    
    def register_user(self, username, password):
        """Registra un nuevo usuario"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO usuarios (username, password) VALUES (?, ?)",
                (username, self.hash_password(password))
            )
            conn.commit()
            conn.close()
            return True
        except sqlite3.IntegrityError:
            return False  # Usuario ya existe
        except Exception as e:
            print(f"❌ AuthManager Error registrando usuario: {e}")
            return False
    
    def verify_login(self, username, password):
        """Verifica credenciales de login"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT password FROM usuarios WHERE username = ?", 
                (username,)
            )
            resultado = cursor.fetchone()
            conn.close()
            return resultado and resultado[0] == self.hash_password(password)
        except Exception as e:
            print(f"❌ AuthManager Error en verify_login: {e}")
            return False
    
    def get_username_by_ip(self, ip):
        """Obtiene username por IP"""
        try:
            conn = sqlite3.connect(self.db_path)
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
    
    def update_session_data(self, client_ip, username, mac, session_start, session_expire, liberated=1):
        """Actualiza datos de sesión en la BD"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                """UPDATE usuarios SET 
                   ip_address = ?, 
                   mac_address = ?,
                   session_start = ?, 
                   session_expire = ?, 
                   liberated = ? 
                   WHERE username = ?""",
                (client_ip, mac, session_start, session_expire, liberated, username)
            )
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"❌ AuthManager Error actualizando sesión: {e}")
            return False
    
    def update_mac_address(self, client_ip, mac):
        """Actualiza la dirección MAC en la BD"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE usuarios SET mac_address = ? WHERE ip_address = ?",
                (mac, client_ip)
            )
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"❌ AuthManager Error actualizando MAC: {e}")
            return False
    
    def get_session_data(self, client_ip):
        """Obtiene datos de sesión por IP"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT username, session_expire, mac_address FROM usuarios WHERE ip_address = ? AND liberated = 1",
                (client_ip,)
            )
            result = cursor.fetchone()
            conn.close()
            return result
        except Exception as e:
            print(f"❌ AuthManager Error obteniendo sesión: {e}")
            return None
    
    def set_liberated(self, client_ip, liberated):
        """Actualiza estado de liberación"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE usuarios SET liberated = ? WHERE ip_address = ?",
                (liberated, client_ip)
            )
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"❌ AuthManager Error actualizando estado: {e}")
            return False
    
    def clean_expired_sessions(self):
        """Limpia sesiones expiradas"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("PRAGMA table_info(usuarios)")
            columns = [col[1] for col in cursor.fetchall()]
            
            if 'session_expire' in columns:
                cursor.execute(
                    "UPDATE usuarios SET liberated = 0 WHERE session_expire < datetime('now')"
                )
                count = cursor.rowcount
            else:
                cursor.execute("UPDATE usuarios SET liberated = 0")
                count = cursor.rowcount
                
            conn.commit()
            conn.close()
            print(f"🧹 AuthManager: Limpiadas {count} sesiones expiradas")
        except Exception as e:
            print(f"❌ AuthManager Error limpiando sesiones: {e}")