"""
Advanced Network Backup System - Unimus-like functionality for MikroTik devices
"""

import hashlib
import asyncio
import json
import re
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from pathlib import Path
import difflib
from dataclasses import dataclass
from enum import Enum
import paramiko
import logging

logger = logging.getLogger(__name__)

class BackupStatus(Enum):
    SUCCESS = "success"
    FAILED = "failed"
    RUNNING = "running"
    SCHEDULED = "scheduled"

class ChangeType(Enum):
    ADDED = "added"
    REMOVED = "removed"
    MODIFIED = "modified"
    CRITICAL = "critical"  # NAT/Firewall changes

@dataclass
class ConfigChange:
    line_number: int
    change_type: ChangeType
    old_content: Optional[str]
    new_content: Optional[str]
    section: str  # e.g., "firewall", "nat", "interface"
    is_security_sensitive: bool = False

@dataclass
class BackupMetadata:
    server_id: str
    timestamp: datetime
    file_size: int
    md5_checksum: str
    config_version: str
    changes_detected: int
    security_changes: int
    backup_duration: float
    status: BackupStatus

class NetworkBackupManager:
    def __init__(self, backup_storage_path: str = "/app/backups"):
        self.backup_path = Path(backup_storage_path)
        self.backup_path.mkdir(exist_ok=True)
        self.retention_count = 10
        
        # Security-sensitive configuration sections
        self.security_sections = {
            'firewall', 'nat', 'ip firewall', 'ip route', 'interface bridge',
            'user', 'ip service', 'ip hotspot', 'tool mac-server'
        }
        
        # Critical configuration patterns
        self.critical_patterns = [
            r'/ip firewall',
            r'/ip route',
            r'/ip nat',
            r'/interface bridge',
            r'/user',
            r'/ip service',
            r'password=',
            r'secret='
        ]

    def generate_filename(self, server_name: str, timestamp: datetime) -> str:
        """Generate standardized backup filename"""
        formatted_time = timestamp.strftime("%Y%m%d_%H%M%S")
        return f"{server_name}_{formatted_time}.rsc"

    def calculate_md5(self, content: str) -> str:
        """Calculate MD5 checksum of backup content"""
        return hashlib.md5(content.encode('utf-8')).hexdigest()

    async def create_mikrotik_backup(self, server_id: str, server_data: Dict) -> BackupMetadata:
        """Create comprehensive MikroTik backup with sensitive data"""
        start_time = datetime.utcnow()
        
        try:
            # Execute sensitive export command
            backup_content = await self._execute_mikrotik_export(server_data)
            
            if not backup_content:
                return BackupMetadata(
                    server_id=server_id,
                    timestamp=start_time,
                    file_size=0,
                    md5_checksum="",
                    config_version="",
                    changes_detected=0,
                    security_changes=0,
                    backup_duration=0,
                    status=BackupStatus.FAILED
                )

            # Calculate metadata
            file_size = len(backup_content.encode('utf-8'))
            md5_checksum = self.calculate_md5(backup_content)
            config_version = self._extract_config_version(backup_content)
            
            # Save backup file
            server_name = server_data.get('name', server_id)
            filename = self.generate_filename(server_name, start_time)
            backup_file_path = self.backup_path / server_name / filename
            backup_file_path.parent.mkdir(exist_ok=True)
            
            with open(backup_file_path, 'w', encoding='utf-8') as f:
                f.write(backup_content)

            # Analyze changes if previous backup exists
            changes_detected, security_changes = await self._analyze_config_changes(
                server_id, server_name, backup_content
            )

            # Clean up old backups (retain only last N versions)
            await self._cleanup_old_backups(server_name)

            execution_time = (datetime.utcnow() - start_time).total_seconds()

            return BackupMetadata(
                server_id=server_id,
                timestamp=start_time,
                file_size=file_size,
                md5_checksum=md5_checksum,
                config_version=config_version,
                changes_detected=changes_detected,
                security_changes=security_changes,
                backup_duration=execution_time,
                status=BackupStatus.SUCCESS
            )

        except Exception as e:
            logger.error(f"Backup failed for server {server_id}: {str(e)}")
            execution_time = (datetime.utcnow() - start_time).total_seconds()
            
            return BackupMetadata(
                server_id=server_id,
                timestamp=start_time,
                file_size=0,
                md5_checksum="",
                config_version="",
                changes_detected=0,
                security_changes=0,
                backup_duration=execution_time,
                status=BackupStatus.FAILED
            )

    async def _execute_mikrotik_export(self, server_data: Dict) -> str:
        """Execute MikroTik export command with sensitive data"""
        loop = asyncio.get_event_loop()
        
        def _ssh_export():
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            try:
                ssh.connect(
                    hostname=server_data['hostname'],
                    port=server_data.get('port', 22),
                    username=server_data['username'],
                    password=server_data.get('password'),
                    timeout=30
                )
                
                # Execute comprehensive export with sensitive data
                stdin, stdout, stderr = ssh.exec_command(
                    '/export compact show-sensitive=yes',
                    timeout=60
                )
                
                output = stdout.read().decode('utf-8')
                error = stderr.read().decode('utf-8')
                
                if error:
                    logger.warning(f"MikroTik export warning: {error}")
                
                return output.strip()
                
            finally:
                ssh.close()
        
        return await loop.run_in_executor(None, _ssh_export)

    def _extract_config_version(self, config_content: str) -> str:
        """Extract RouterOS version from config"""
        version_pattern = r'# software id = (.+)'
        match = re.search(version_pattern, config_content)
        return match.group(1) if match else "unknown"

    async def _analyze_config_changes(self, server_id: str, server_name: str, 
                                    current_config: str) -> Tuple[int, int]:
        """Analyze configuration changes compared to previous backup"""
        try:
            # Get previous backup
            previous_config = await self._get_previous_backup(server_name)
            if not previous_config:
                return 0, 0

            # Generate diff
            changes = self._generate_config_diff(previous_config, current_config)
            
            # Count changes and security-sensitive changes
            total_changes = len(changes)
            security_changes = sum(1 for change in changes if change.is_security_sensitive)
            
            # Store change analysis
            await self._store_change_analysis(server_id, changes)
            
            return total_changes, security_changes

        except Exception as e:
            logger.error(f"Change analysis failed for {server_name}: {str(e)}")
            return 0, 0

    async def _get_previous_backup(self, server_name: str) -> Optional[str]:
        """Get the most recent backup content for comparison"""
        server_backup_dir = self.backup_path / server_name
        
        if not server_backup_dir.exists():
            return None
        
        backup_files = sorted(server_backup_dir.glob("*.rsc"), reverse=True)
        
        if len(backup_files) < 2:  # Need at least 2 backups to compare
            return None
        
        # Get second most recent (previous backup)
        previous_backup = backup_files[1]
        
        with open(previous_backup, 'r', encoding='utf-8') as f:
            return f.read()

    def _generate_config_diff(self, old_config: str, new_config: str) -> List[ConfigChange]:
        """Generate detailed configuration diff with security analysis"""
        changes = []
        
        old_lines = old_config.splitlines()
        new_lines = new_config.splitlines()
        
        # Generate unified diff
        diff = list(difflib.unified_diff(
            old_lines, new_lines,
            fromfile='previous',
            tofile='current',
            lineterm=''
        ))
        
        current_section = "unknown"
        line_number = 0
        
        for line in diff:
            if line.startswith('@@'):
                # Extract line number info
                match = re.search(r'\+(\d+)', line)
                if match:
                    line_number = int(match.group(1))
                continue
            
            if line.startswith('---') or line.startswith('+++'):
                continue
            
            # Detect configuration section
            if line.startswith('/'):
                current_section = line.strip('+-').strip()
            
            if line.startswith('-'):
                # Removed line
                content = line[1:].strip()
                is_security = self._is_security_sensitive(content, current_section)
                
                changes.append(ConfigChange(
                    line_number=line_number,
                    change_type=ChangeType.CRITICAL if is_security else ChangeType.REMOVED,
                    old_content=content,
                    new_content=None,
                    section=current_section,
                    is_security_sensitive=is_security
                ))
                
            elif line.startswith('+'):
                # Added line
                content = line[1:].strip()
                is_security = self._is_security_sensitive(content, current_section)
                
                changes.append(ConfigChange(
                    line_number=line_number,
                    change_type=ChangeType.CRITICAL if is_security else ChangeType.ADDED,
                    old_content=None,
                    new_content=content,
                    section=current_section,
                    is_security_sensitive=is_security
                ))
                line_number += 1
                
            elif not line.startswith(' '):
                line_number += 1

        return changes

    def _is_security_sensitive(self, line: str, section: str) -> bool:
        """Determine if a configuration line is security-sensitive"""
        # Check if section is security-sensitive
        if any(sec in section.lower() for sec in self.security_sections):
            return True
        
        # Check for critical patterns
        for pattern in self.critical_patterns:
            if re.search(pattern, line, re.IGNORECASE):
                return True
        
        return False

    async def _store_change_analysis(self, server_id: str, changes: List[ConfigChange]):
        """Store change analysis for reporting and alerting"""
        # This would integrate with your database to store change records
        # For now, we'll log the security-sensitive changes
        security_changes = [c for c in changes if c.is_security_sensitive]
        
        if security_changes:
            logger.warning(f"Security-sensitive changes detected for server {server_id}: "
                         f"{len(security_changes)} changes")
            
            for change in security_changes:
                logger.warning(f"  {change.change_type.value}: {change.section} - "
                             f"{change.new_content or change.old_content}")

    async def _cleanup_old_backups(self, server_name: str):
        """Remove old backups, keeping only the most recent N versions"""
        server_backup_dir = self.backup_path / server_name
        
        if not server_backup_dir.exists():
            return
        
        backup_files = sorted(server_backup_dir.glob("*.rsc"), reverse=True)
        
        # Remove files beyond retention count
        for old_backup in backup_files[self.retention_count:]:
            try:
                old_backup.unlink()
                logger.info(f"Removed old backup: {old_backup}")
            except Exception as e:
                logger.error(f"Failed to remove old backup {old_backup}: {e}")

    def generate_diff_html(self, old_config: str, new_config: str) -> str:
        """Generate HTML diff view for web interface"""
        old_lines = old_config.splitlines()
        new_lines = new_config.splitlines()
        
        diff_html = difflib.HtmlDiff(wrapcolumn=80)
        html_diff = diff_html.make_file(
            old_lines, new_lines,
            fromdesc='Previous Configuration',
            todesc='Current Configuration',
            context=True,
            numlines=3
        )
        
        # Add custom CSS for better security highlighting
        security_css = """
        <style>
        .security-change { background-color: #ffebee !important; border-left: 4px solid #f44336; }
        .critical-section { font-weight: bold; color: #d32f2f; }
        .diff_header { background-color: #e3f2fd; }
        </style>
        """
        
        # Inject security CSS
        html_diff = html_diff.replace('<style', security_css + '<style')
        
        return html_diff

    async def get_backup_statistics(self, time_range: timedelta = timedelta(days=30)) -> Dict:
        """Generate backup statistics for dashboard"""
        # This would query your database for backup statistics
        # For now, return mock data structure
        cutoff_date = datetime.utcnow() - time_range
        
        return {
            "total_backups": 0,
            "successful_backups": 0,
            "failed_backups": 0,
            "security_changes_detected": 0,
            "servers_with_changes": [],
            "average_backup_size": 0,
            "last_backup_time": None,
            "backup_frequency": {},
            "critical_alerts": []
        }

    async def search_configurations(self, query: str, 
                                  server_filter: Optional[str] = None,
                                  date_range: Optional[Tuple[datetime, datetime]] = None) -> List[Dict]:
        """Search across all backup configurations"""
        results = []
        
        # Iterate through all server backup directories
        for server_dir in self.backup_path.iterdir():
            if not server_dir.is_dir():
                continue
                
            if server_filter and server_filter.lower() not in server_dir.name.lower():
                continue
            
            # Search through backup files
            for backup_file in sorted(server_dir.glob("*.rsc"), reverse=True):
                # Check date range
                if date_range:
                    file_timestamp = self._extract_timestamp_from_filename(backup_file.name)
                    if not (date_range[0] <= file_timestamp <= date_range[1]):
                        continue
                
                # Search file content
                try:
                    with open(backup_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                        
                    if query.lower() in content.lower():
                        # Find matching lines
                        matches = []
                        for line_num, line in enumerate(content.splitlines(), 1):
                            if query.lower() in line.lower():
                                matches.append({
                                    "line_number": line_num,
                                    "content": line.strip(),
                                    "context": self._get_line_context(content, line_num)
                                })
                        
                        results.append({
                            "server_name": server_dir.name,
                            "backup_file": backup_file.name,
                            "timestamp": self._extract_timestamp_from_filename(backup_file.name),
                            "matches": matches[:10]  # Limit matches per file
                        })
                        
                except Exception as e:
                    logger.error(f"Error searching {backup_file}: {e}")
        
        return results

    def _extract_timestamp_from_filename(self, filename: str) -> datetime:
        """Extract timestamp from backup filename"""
        # Expected format: servername_YYYYMMDD_HHMMSS.rsc
        try:
            timestamp_part = filename.split('_')[-2] + '_' + filename.split('_')[-1].replace('.rsc', '')
            return datetime.strptime(timestamp_part, "%Y%m%d_%H%M%S")
        except:
            return datetime.min

    def _get_line_context(self, content: str, line_number: int, context_lines: int = 2) -> List[str]:
        """Get context lines around a specific line number"""
        lines = content.splitlines()
        start = max(0, line_number - context_lines - 1)
        end = min(len(lines), line_number + context_lines)
        
        return lines[start:end]

# MTU/MSS Management Utilities
class TunnelOptimizer:
    """Centralized MTU/MSS management for tunnel interfaces"""
    
    OPTIMAL_MTUS = {
        'gre': 1396,
        'gre6': 1356,
        'wireguard': 1420,
        'l2tp': 1460,
        'pptp': 1500,
        'ipsec': 1436
    }
    
    @classmethod
    def get_optimal_mtu(cls, tunnel_type: str, overhead: int = 0) -> int:
        """Get optimal MTU for tunnel type"""
        base_mtu = cls.OPTIMAL_MTUS.get(tunnel_type.lower(), 1500)
        return max(1280, base_mtu - overhead)  # IPv6 minimum MTU
    
    @classmethod
    def generate_mtu_fix_script(cls, interface: str, tunnel_type: str) -> str:
        """Generate MikroTik script to fix MTU/MSS issues"""
        optimal_mtu = cls.get_optimal_mtu(tunnel_type)
        mss_clamp = optimal_mtu - 40  # TCP header overhead
        
        return f"""
# MTU/MSS optimization for {interface} ({tunnel_type})
/interface set {interface} mtu={optimal_mtu}
/ip firewall mangle add chain=forward protocol=tcp tcp-flags=syn tcp-mss=!0-{mss_clamp} action=change-mss new-mss={mss_clamp} comment="MSS clamp for {interface}"
"""

# Credential Security Manager
class SecureCredentialManager:
    """AES-256 encrypted credential storage with JWT-based access"""
    
    def __init__(self, encryption_key: bytes):
        from cryptography.fernet import Fernet
        self.cipher = Fernet(encryption_key)
    
    def encrypt_credentials(self, credentials: Dict) -> str:
        """Encrypt credentials using AES-256"""
        credential_json = json.dumps(credentials)
        encrypted_data = self.cipher.encrypt(credential_json.encode())
        return encrypted_data.decode()
    
    def decrypt_credentials(self, encrypted_data: str) -> Dict:
        """Decrypt credentials"""
        decrypted_data = self.cipher.decrypt(encrypted_data.encode())
        return json.loads(decrypted_data.decode())
    
    def generate_temporal_token(self, server_id: str, expiry_hours: int = 24) -> str:
        """Generate JWT token with temporal access"""
        import jwt
        from datetime import datetime, timedelta
        
        payload = {
            'server_id': server_id,
            'exp': datetime.utcnow() + timedelta(hours=expiry_hours),
            'iat': datetime.utcnow()
        }
        
        # In production, use a proper JWT secret from environment
        return jwt.encode(payload, 'your-jwt-secret', algorithm='HS256')