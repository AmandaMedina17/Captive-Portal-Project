# session_manager.py
import re
import time
import threading
from datetime import datetime
from enum import Enum
import subprocess

class SessionTerminationReason(Enum):
    USER_LOGOUT = "usuario cerró sesión"
    SESSION_TIMEOUT = "tiempo sesion agotado, sesión expirada"
    IP_SPOOFING_DETECTED = "suplantacion_ip"
    MAC_MISMATCH = "cambio_mac"
    UNKNOWN = "desconocida"
    SYSTEM_ERROR = "error_sistema"

class NetworkSessionManager:
    def __init__(self, firewall_manager, timeout=2*60, cleanup_interval=5*60):
        self.session_timeout = timeout
        self.active_sessions = {}
        self.firewall = firewall_manager
        self.cleanup_interval = cleanup_interval
        self._stop_cleanup = threading.Event()
        self._session_lock = threading.RLock()
        
        # Iniciar el hilo de limpieza
        self.cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        self.cleanup_thread.start()
        
        print(f"✅ SessionManager iniciado - Timeout: {timeout}s - Cleanup cada {self.cleanup_interval}s")
    
    def _normalize_mac(self, mac: str) -> str:
        """Normaliza MAC a MAYÚSCULAS con dos puntos"""
        if not mac:
            return "00:00:00:00:00:00"
        
        # Limpiar y normalizar formato
        mac = mac.strip().upper()
        mac = mac.replace('-', ':')
        
        # Asegurar formato XX:XX:XX:XX:XX:XX
        if len(mac) == 12 and ':' not in mac:
            mac = ':'.join([mac[i:i+2] for i in range(0, 12, 2)])
        
        return mac if re.match(r'^([0-9A-F]{2}:){5}[0-9A-F]{2}$', mac) else "00:00:00:00:00:00"
    
    def _cleanup_loop(self):
        """Bucle de limpieza automática"""
        while not self._stop_cleanup.is_set():
            time.sleep(self.cleanup_interval)
            self._check_and_cleanup_expired()
    
    def _check_and_cleanup_expired(self):
        """Verifica y limpia sesiones expiradas"""
        try:
            current_time = time.time()
            expired_count = 0
            
            with self._session_lock:
                expired_ips = []
                
                for ip, session in self.active_sessions.items():
                    elapsed = current_time - session.get('login_time', 0)
                    if elapsed > self.session_timeout:
                        expired_ips.append(ip)
            
            for ip in expired_ips:
                if self.terminate_session(ip, SessionTerminationReason.SESSION_TIMEOUT):
                    expired_count += 1
            
            if expired_count > 0:
                print(f"⏰ [{datetime.now().strftime('%H:%M:%S')}] Limpieza automática: {expired_count} sesiones expiradas")
            
            self._display_active_sessions_summary()
            
        except Exception as e:
            print(f"❌ Error en limpieza automática: {e}")
    
    def _get_client_mac(self, client_ip):
        """Obtiene la MAC del cliente desde la tabla ARP"""
        try:
            result = subprocess.run(['ip', 'neigh', 'show', client_ip], 
                                  capture_output=True, text=True, timeout=3)
            
            if result.returncode == 0 and result.stdout:
                for line in result.stdout.strip().split('\n'):
                    if client_ip in line and ('REACHABLE' in line or 'STALE' in line or 'DELAY' in line):
                        parts = line.split()
                        if 'lladdr' in line:
                            idx = line.index('lladdr')
                            mac = line[idx:].split()[1]
                            return self._normalize_mac(mac)
                        elif len(parts) >= 5:
                            return self._normalize_mac(parts[4])
            
            # Intentar con arp como fallback
            result = subprocess.run(['arp', '-n', client_ip], 
                                  capture_output=True, text=True, timeout=3)
            if result.returncode == 0 and result.stdout:
                lines = result.stdout.strip().split('\n')
                if len(lines) > 1:
                    parts = lines[1].split()
                    if len(parts) >= 3:
                        return self._normalize_mac(parts[2])
            
        except Exception as e:
            print(f"⚠️ Error obteniendo MAC para {client_ip}: {e}")
        
        return "00:00:00:00:00:00"
    
    def _format_time(self, seconds: float) -> str:
        """Formatear tiempo en segundos a string legible"""
        if seconds <= 0:
            return "0 segundos"
        
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        
        parts = []
        if hours > 0:
            parts.append(f"{hours}h")
        if minutes > 0:
            parts.append(f"{minutes}m")
        if secs > 0 and hours == 0:
            parts.append(f"{secs}s")
        
        return " ".join(parts)
    
    def _display_active_sessions_summary(self):
        """Muestra un resumen de las sesiones activas"""
        with self._session_lock:
            active_count = len(self.active_sessions)
            
            if active_count == 0:
                print(f"📊 Sesiones activas: 0")
                return
            
            print(f"\n📊 RESUMEN DE SESIONES ACTIVAS")
            print(f"   Total: {active_count} sesión(es)")
            print(f"   {'─' * 40}")
            
            for ip, session in self.active_sessions.items():
                username = session.get('username', 'Desconocido')
                login_time = session.get('login_time', 0)
                elapsed = time.time() - login_time
                remaining = max(0, self.session_timeout - elapsed)
                mac = session.get('mac', 'No registrada')
                
                elapsed_str = self._format_time(elapsed)
                remaining_str = self._format_time(remaining)
                
                print(f"   • {username:20} {ip:15} MAC: {mac}")
                print(f"     Tiempo conectado: {elapsed_str}")
                print(f"     Tiempo restante:  {remaining_str}")
                print(f"     Login: {datetime.fromtimestamp(login_time).strftime('%H:%M:%S')}")
    
    def create_session(self, ip, username, force_mac=None):
        """
        Crear nueva sesión para usuario autenticado
        
        Args:
            ip: Dirección IP del cliente
            username: Nombre de usuario
            force_mac: MAC específica (opcional, si no se proporciona, se detecta automáticamente)
        
        Returns:
            bool: True si la sesión se creó exitosamente
        """
        try:
            if not ip or ip == "0.0.0.0":
                print(f"❌ IP inválida: {ip}")
                return False
            
            # Obtener MAC del cliente
            if force_mac:
                mac = self._normalize_mac(force_mac)
            else:
                mac = self._get_client_mac(ip)
            
            print(f"📱 Detectada MAC para {ip}: {mac}")
            
            with self._session_lock:
                # Verificar si ya existe sesión para esta IP
                if ip in self.active_sessions:
                    existing_session = self.active_sessions[ip]
                    existing_mac = existing_session.get('mac', "00:00:00:00:00:00")
                    
                    # Verificar si la MAC coincide
                    if existing_mac != "00:00:00:00:00:00" and mac != "00:00:00:00:00:00" and existing_mac != mac:
                        print(f"🚨 Suplantación detectada en sesión existente para {username}")
                        print(f"   MAC esperada: {existing_mac}")
                        print(f"   MAC actual:   {mac}")
                        
                        # Terminar sesión existente por suplantación
                        self.terminate_session(ip, SessionTerminationReason.IP_SPOOFING_DETECTED)
                    
                    else:
                        print(f"🔄 Renovando sesión existente para {username}")
                    
                    # Actualizar sesión existente
                    existing_session['login_time'] = time.time()
                    if existing_mac == "00:00:00:00:00:00" and mac != "00:00:00:00:00:00":
                        existing_session['mac'] = mac
                    
                    # Actualizar reglas de firewall
                    self.firewall.unlock_user(ip, mac)
                    return True
                
                else:
                    # Crear nueva sesión
                    print(f"🔓 Creando nueva sesión para {username} ({ip}) - MAC: {mac}")
                    
                    # Desbloquear en firewall con binding MAC
                    success = self.firewall.unlock_user(ip, mac)
                    
                    if success:
                        self.active_sessions[ip] = {
                            'mac': mac,
                            'username': username,
                            'login_time': time.time(),
                            'login_timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        }
                        print(f"✅ Sesión creada exitosamente para {username}")
                        return True
                    else:
                        print(f"❌ Error al crear sesión: fallo en firewall")
                        return False
                
        except Exception as e:
            print(f"❌ Error en create_session: {e}")
            return False
    
    def terminate_session(self, ip, reason: SessionTerminationReason = SessionTerminationReason.UNKNOWN):
        """
        Terminar sesión y bloquear usuario
        
        Returns:
            bool: True si la sesión se terminó exitosamente
        """
        try:
            with self._session_lock:
                if ip not in self.active_sessions:
                    print(f"⚠️  No se encontró sesión para IP {ip}")
                    return False
                
                session = self.active_sessions[ip]
                username = session.get('username', 'Desconocido')
                mac = session.get('mac', "00:00:00:00:00:00")
                
                print(f"🔒 Terminando sesión: {username} ({ip}) - Razón: {reason.value}")
                print(f"   MAC registrada: {mac}")
                
                # Bloquear en firewall (IP y MAC si está disponible)
                self.firewall.lock_user(ip, mac)
                
                # Eliminar del registro de sesiones
                del self.active_sessions[ip]
                
                print(f"✅ Sesión terminada exitosamente: {username} ({ip})")
                return True
            
        except Exception as e:
            print(f"❌ Error terminando sesión: {e}")
            return False
    
    def verify_session(self, ip):
        """
        Verifica si una sesión es válida y no ha sido suplantada
        
        Returns:
            bool: True si la sesión es válida
            str: Mensaje de error si no es válida
        """
        with self._session_lock:
            # Verificar si existe la sesión
            if ip not in self.active_sessions:
                return False, "Sesión no encontrada"
            
            session = self.active_sessions[ip]
            
            # Verificar timeout
            elapsed = time.time() - session.get('login_time', 0)
            if elapsed > self.session_timeout:
                self.terminate_session(ip, SessionTerminationReason.SESSION_TIMEOUT)
                return False, "Sesión expirada"
            
            # Verificar suplantación por MAC (si tenemos MAC registrada)
            mac = session.get('mac', "00:00:00:00:00:00")
            if mac != "00:00:00:00:00:00":
                current_mac = self._get_client_mac(ip)
                
                if current_mac != "00:00:00:00:00:00" and current_mac != mac:
                    print(f"🚨 SUPLANTACIÓN DETECTADA!")
                    print(f"   IP: {ip}")
                    print(f"   Usuario: {session.get('username', 'Desconocido')}")
                    print(f"   MAC esperada: {mac}")
                    print(f"   MAC actual:   {current_mac}")
                    
                    # Terminar sesión por suplantación
                    self.terminate_session(ip, SessionTerminationReason.MAC_MISMATCH)
                    return False, "Suplantación de dispositivo detectada"
            
            return True, "Sesión válida"
    
    def get_session_info(self, ip):
        """Obtiene información de una sesión específica"""
        with self._session_lock:
            if ip in self.active_sessions:
                session = self.active_sessions[ip].copy()
                session['elapsed'] = time.time() - session['login_time']
                session['remaining'] = max(0, self.session_timeout - session['elapsed'])
                return session
            return None
    
    def get_all_sessions(self):
        """Obtiene todas las sesiones activas"""
        with self._session_lock:
            sessions = {}
            for ip, session in self.active_sessions.items():
                session_copy = session.copy()
                session_copy['elapsed'] = time.time() - session['login_time']
                session_copy['remaining'] = max(0, self.session_timeout - session_copy['elapsed'])
                sessions[ip] = session_copy
            return sessions
    
    def stop_cleanup(self):
        """Detener el hilo de limpieza"""
        self._stop_cleanup.set()
        if self.cleanup_thread.is_alive():
            self.cleanup_thread.join(timeout=2)