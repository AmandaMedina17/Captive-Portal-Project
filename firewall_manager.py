# firewall_manager.py
import os
import subprocess
import re

class FirewallManager:
    """Maneja operaciones de firewall (bloquear/desbloquear IPs)"""

    def __init__(self, scripts_dir='.'):
        self.scripts_dir = scripts_dir

    def unlock_client(self, client_ip):
        """Desbloquea un cliente en el firewall"""
        print(f"FirewallManager: Desbloqueando {client_ip}")
        return self.run_script('unlock.sh', [client_ip])
        
    
    def block_client(self, client_ip):
        """Bloquea un cliente en el firewall"""
        print(f"FirewallManager: Bloqueando {client_ip}")
        return self.run_script('block.sh', [client_ip])
    
    def run_script(self, script_name, parameters=None):
        """Ejecuta scripts externos"""
        script_path = os.path.join(self.scripts_dir, script_name)
        
        try:
            if parameters:
                command = ['sudo', script_path] + parameters
                result = subprocess.run(
                    command, 
                    check=True, 
                    capture_output=True, 
                    text=True
                )
            else:
                result = subprocess.run(
                    ['sudo', script_path], 
                    check=True, 
                    capture_output=True, 
                    text=True
                )
            
            print(f"✅ {result.stdout.strip()}")
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"❌ Error ejecutando {script_name}: {e.stderr}")
            return False
 