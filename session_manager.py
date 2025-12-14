import threading
import time
from datetime import datetime, timedelta
import subprocess

class NetworkSessionManager:
    """Maneja sesiones de usuarios con control de tiempo y suplantación"""
    
    def __init__(self, auth_manager, firewall_manager = None, session_timeout=1800):
        self.auth_manager = auth_manager
        self.firewall_manager = firewall_manager
        self.session_timeout = session_timeout
        self.active_sessions = {}  # {ip: {'expiry': timestamp, 'mac': mac, 'username': username}}
        self.session_lock = threading.RLock()
    
    def _normalize_mac(self, mac: str) -> str:
        """Normaliza MAC a formato estándar"""
        if not mac:
            return "00:00:00:00:00:00"
        normalized = mac.strip().upper().replace('-', ':')
        return normalized if normalized else "00:00:00:00:00:00"
    
    def get_client_mac(self, client_ip):
        """Obtiene MAC del cliente"""
        try:
            result = subprocess.run(
                ['ip', 'neigh', 'show', client_ip], 
                capture_output=True, 
                text=True, 
                timeout=3
            )
            if result.returncode == 0 and result.stdout:
                line = result.stdout.strip()
                parts = line.split()
                if "lladdr" in parts:
                    idx = parts.index("lladdr")
                    return parts[idx + 1].upper()
        except Exception as e:
            print(f"⚠️ NetworkSessionManager Error obteniendo MAC: {e}")
        return "00:00:00:00:00:00"
    
    def check_session_expired(self, client_ip):
        """Verifica si una sesión ha expirado"""
        with self.session_lock:
            if client_ip in self.active_sessions:
                expiry_time = self.active_sessions[client_ip]['expiry']
                if time.time() > expiry_time:
                    print(f"⏰ NetworkSessionManager: Sesión expirada para {client_ip}")
                    return True
            return False
    
    def verify_mac_integrity(self, client_ip, username):
        """Verifica integridad de la dirección MAC"""
        try:
            current_mac = self.get_client_mac(client_ip)
            normalized_current_mac = self._normalize_mac(current_mac)
            
            with self.session_lock:
                if client_ip in self.active_sessions:
                    stored_mac = self.active_sessions[client_ip].get('mac', '00:00:00:00:00:00')
                    
                    if stored_mac == "00:00:00:00:00:00" and normalized_current_mac != "00:00:00:00:00:00":
                        self.active_sessions[client_ip]['mac'] = normalized_current_mac
                        self.auth_manager.update_mac_address(client_ip, normalized_current_mac)
                        return True
                    
                    if (stored_mac != "00:00:00:00:00:00" and 
                        normalized_current_mac != "00:00:00:00:00:00" and 
                        stored_mac != normalized_current_mac):
                        print(f"🚨 NetworkSessionManager: Posible suplantación en {client_ip}")
                        print(f"   Almacenada: {stored_mac}")
                        print(f"   Actual: {normalized_current_mac}")
                        self.end_session(client_ip,"suplantacion")
                        return False
                
                session_data = self.auth_manager.get_session_data(client_ip)
                if session_data:
                    db_mac = self._normalize_mac(session_data[2])
                    
                    if client_ip in self.active_sessions:
                        self.active_sessions[client_ip]['mac'] = db_mac
                    
                    if (db_mac != "00:00:00:00:00:00" and 
                        normalized_current_mac != "00:00:00:00:00:00" and 
                        db_mac != normalized_current_mac):
                        print(f"🚨 SessionManager: Suplantación en BD para {client_ip}")
                        return False
            
            return True
            
        except Exception as e:
            print(f"❌ SessionManager Error en verify_mac_integrity: {e}")
            return True
    
    def create_session(self, client_ip, username, mac=None):
        """Crea una nueva sesión para el usuario"""
        with self.session_lock:
            normalized_mac = self._normalize_mac(mac) if mac else "00:00:00:00:00:00"
            expiry_time = time.time() + self.session_timeout
            
            self.active_sessions[client_ip] = {
                'expiry': expiry_time,
                'mac': normalized_mac,
                'username': username
            }
            
            now = datetime.now()
            expire = now + timedelta(seconds=self.session_timeout)
            
            self.auth_manager.update_session_data(
                client_ip, username, normalized_mac,
                now.isoformat(), expire.isoformat(), 1
            )
            
            print(f"✅ NetworkSessionManager: Sesión creada para {username} ({client_ip})")
            print(f"   MAC: {normalized_mac}")
            print(f"   Expira: {expire.strftime('%H:%M:%S')}")
            
            # Programar expiración con bloqueo de firewall
            def _expire_and_block():
                self.end_session(client_ip, "timeout")
            
            timer = threading.Timer(self.session_timeout, _expire_and_block)
            timer.daemon = True
            timer.start()
            return True
    
    def end_session(self, client_ip, reason="timeout"):
        """Termina una sesión"""
        with self.session_lock:
            if client_ip in self.active_sessions:
                username = self.active_sessions[client_ip].get('username', 'Desconocido')
                print(f"⏰ NetworkSessionManager: Terminando sesión {username} ({client_ip}) - Razón: {reason}")
                
                # Bloquear en firewall si está disponible
                if self.firewall_manager:
                    success = self.firewall_manager.block_client(client_ip)
                    if not success:
                        print(f"❌ SessionManager: Error bloqueando en firewall para {client_ip}")

                self.auth_manager.set_liberated(client_ip, 0)
                del self.active_sessions[client_ip]
                
                print(f"✅ NetworkSessionManager: Sesión terminada para {client_ip}")
            else:
                print(f"⚠️  NetworkSessionManager: No hay sesión activa para {client_ip}")
    
    def verify_active_session(self, client_ip):
        """Verifica si hay una sesión activa válida"""
        with self.session_lock:
            if client_ip in self.active_sessions:
                if self.check_session_expired(client_ip):
                    return False
                
                username = self.active_sessions[client_ip].get('username', '')
                if not self.verify_mac_integrity(client_ip, username):
                    return False
                
                return True
            
            # Verificar en BD
            session_data = self.auth_manager.get_session_data(client_ip)
            if session_data:
                username, session_expire_str, mac = session_data
                
                try:
                    expire_time = datetime.fromisoformat(session_expire_str)
                    if expire_time > datetime.now():
                        # Restaurar desde BD
                        expiry_timestamp = time.mktime(expire_time.timetuple())
                        self.active_sessions[client_ip] = {
                            'expiry': expiry_timestamp,
                            'mac': self._normalize_mac(mac),
                            'username': username
                        }
                        
                        time_remaining = (expire_time - datetime.now()).total_seconds()
                        if time_remaining > 0:
                            threading.Timer(time_remaining, self.end_session, args=[client_ip, "timeout"]).start()
                        
                        print(f"🔄 NetworkSessionManager: Sesión restaurada para {client_ip}")
                        return True
                    else:
                        self.end_session(client_ip, "timeout")
                except (ValueError, TypeError) as e:
                    print(f"❌ NetworkSessionManager Error parseando fecha: {e}")
            
            return False
    
    def get_session_info(self, client_ip):
        """Obtiene información de una sesión"""
        with self.session_lock:
            if client_ip in self.active_sessions:
                session = self.active_sessions[client_ip]
                remaining = max(0, session['expiry'] - time.time())
                return {
                    'username': session['username'],
                    'mac': session['mac'],
                    'remaining': remaining,
                    'expiry': session['expiry']
                }
            return None