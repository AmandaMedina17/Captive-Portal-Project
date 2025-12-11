# firewall_manager.py
import os
import subprocess
import re

class FirewallManager:
    def __init__(self):
        self.scripts_dir = os.path.dirname(__file__)
    
    def unlock_user(self, ip, mac=None):
        """Desbloquea un usuario en el firewall por IP y opcionalmente por MAC"""
        try:
            print("estoy en unlock user")
            # Ejecutar el script unlock.sh con la IP
            # subprocess.run(['./unlock.sh', ip], check=True, capture_output=True, text=True)
            

            script_path = os.path.join(self.scripts_dir, 'unlock.sh')
            command = [script_path] + [ip]
            result = subprocess.run(
            command, 
            check=True, 
            capture_output=True, 
            text=True
            )
            print("termine unlock")
            if mac and mac != "00:00:00:00:00:00":
                # Permitir solo tráfico desde esta IP con esta MAC específica
                subprocess.run([
                    'iptables', '-I', 'FORWARD', '-s', ip,
                    '-m', 'mac', '--mac-source', mac, '-j', 'ACCEPT'
                ], check=True)
                
                # Bloquear tráfico desde esta IP con otras MACs (prevención suplantación)
                subprocess.run([
                    'iptables', '-I', 'FORWARD', '-s', ip, '-j', 'DROP'
                ], check=True)
                
                print(f"✅ Reglas MAC aplicadas para {ip} ({mac})")
            
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"❌ Error desbloqueando usuario: {e.stderr}")
            return False
    
    def lock_user(self, ip, mac=None):
        """Bloquea un usuario en el firewall por IP y opcionalmente por MAC"""
        try:
            # Si se especifica MAC, bloquear específicamente esa MAC
            if mac and mac != "00:00:00:00:00:00":
                subprocess.run([
                    'iptables', '-I', 'FORWARD', '-m', 'mac',
                    '--mac-source', mac, '-j', 'DROP'
                ], check=True)
                print(f"🔒 Bloqueada MAC: {mac}")
            
            # Ejecutar el script lock.sh con la IP
            subprocess.run(['./lock.sh', ip], check=True, capture_output=True, text=True)
            
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"❌ Error bloqueando usuario: {e.stderr}")
            return False
    
    def verify_mac_binding(self, ip, expected_mac):
        """Verifica si la MAC actual de una IP coincide con la esperada"""
        try:
            # Obtener MAC actual desde la tabla ARP
            result = subprocess.run(['ip', 'neigh', 'show', ip], 
                                  capture_output=True, text=True, timeout=3)
            
            if result.returncode == 0 and result.stdout:
                for line in result.stdout.strip().split('\n'):
                    if ip in line and 'REACHABLE' in line:
                        parts = line.split()
                        if len(parts) >= 5:
                            current_mac = parts[4].upper()
                            return current_mac == expected_mac.upper()
            
            return True  # Si no podemos verificar, asumimos que es válido
            
        except Exception as e:
            print(f"⚠️ Error verificando MAC: {e}")
            return True