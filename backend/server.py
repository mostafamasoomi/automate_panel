from fastapi import FastAPI, APIRouter, HTTPException, BackgroundTasks
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime
import paramiko
import asyncio
import time
from concurrent.futures import ThreadPoolExecutor
import yaml
import json
import re
from backup_manager import NetworkBackupManager, TunnelOptimizer, SecureCredentialManager, BackupStatus
from cryptography.fernet import Fernet

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create the main app without a prefix
app = FastAPI()

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Thread pool for SSH operations
ssh_executor = ThreadPoolExecutor(max_workers=10)

# Define Models
class Server(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    hostname: str
    username: str
    password: Optional[str] = None
    private_key_path: Optional[str] = None
    port: int = 22
    os_type: str = "linux"  # linux, mikrotik
    groups: List[str] = []
    tags: List[str] = []
    description: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_connected: Optional[datetime] = None
    status: str = "unknown"  # unknown, online, offline, error

class ServerCreate(BaseModel):
    name: str
    hostname: str
    username: str
    password: Optional[str] = None
    private_key_path: Optional[str] = None
    port: int = 22
    os_type: str = "linux"
    groups: List[str] = []
    tags: List[str] = []
    description: Optional[str] = None

class TaskParameter(BaseModel):
    name: str
    type: str = "string"  # string, number, boolean, select
    description: str
    required: bool = True
    default_value: Optional[str] = None
    options: List[str] = []  # For select type

class Task(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    command: str
    description: Optional[str] = None
    category: str = "custom"
    os_type: str = "linux"
    parameters: List[TaskParameter] = []
    variables: Dict[str, Any] = {}
    created_at: datetime = Field(default_factory=datetime.utcnow)
    is_template: bool = False
    tags: List[str] = []

class TaskCreate(BaseModel):
    name: str
    command: str
    description: Optional[str] = None
    category: str = "custom"
    os_type: str = "linux"
    parameters: List[TaskParameter] = []
    variables: Dict[str, Any] = {}
    tags: List[str] = []

class TaskUpdate(BaseModel):
    name: Optional[str] = None
    command: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    os_type: Optional[str] = None
    parameters: Optional[List[TaskParameter]] = None
    variables: Optional[Dict[str, Any]] = None
    tags: Optional[List[str]] = None

class ExecutionResult(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    server_id: str
    task_id: str
    command: str
    stdout: str
    stderr: str
    return_code: int
    execution_time: float
    started_at: datetime
    completed_at: datetime
    status: str  # success, error, timeout
    parameters: Dict[str, Any] = {}

class ExecutionRequest(BaseModel):
    server_ids: List[str]
    task_id: str
    timeout: int = 30
    parameters: Dict[str, Any] = {}

class TestConnectionRequest(BaseModel):
    hostname: str
    username: str
    password: Optional[str] = None
    private_key_path: Optional[str] = None
    port: int = 22

class Backup(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    server_id: str
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    status: str = "success"  # success, failed, running
    backup_type: str = "config"  # config, full, incremental
    file_path: Optional[str] = None
    size_bytes: int = 0
    changes_count: int = 0

# Pre-loaded task templates
TASK_TEMPLATES = [
    # System Monitoring
    {
        "name": "System Resource Check",
        "command": "echo '=== CPU Usage ==='; top -bn1 | grep 'Cpu(s)'; echo '=== Memory Usage ==='; free -h; echo '=== Disk Usage ==='; df -h; echo '=== Load Average ==='; uptime",
        "description": "Check CPU, memory, disk usage and system load",
        "category": "monitoring",
        "os_type": "linux",
        "tags": ["system", "monitoring", "resources"]
    },
    {
        "name": "Network Interface Status",
        "command": "ip addr show && echo '=== Network Stats ===' && cat /proc/net/dev",
        "description": "Display network interfaces and statistics",
        "category": "networking",
        "os_type": "linux",
        "tags": ["network", "interfaces", "monitoring"]
    },
    {
        "name": "Process Monitor",
        "command": "ps aux --sort=-%cpu | head -20",
        "description": "Show top 20 processes by CPU usage",
        "category": "monitoring",
        "os_type": "linux",
        "tags": ["processes", "cpu", "monitoring"]
    },
    
    # System Updates
    {
        "name": "Ubuntu/Debian Update",
        "command": "sudo apt update && sudo apt list --upgradable",
        "description": "Update package lists and show available upgrades",
        "category": "updates",
        "os_type": "linux",
        "tags": ["ubuntu", "debian", "updates", "packages"]
    },
    {
        "name": "CentOS/RHEL Update Check",
        "command": "sudo yum check-update || sudo dnf check-update",
        "description": "Check for available updates on CentOS/RHEL systems",
        "category": "updates",
        "os_type": "linux",
        "tags": ["centos", "rhel", "updates", "packages"]
    },
    {
        "name": "Full System Upgrade",
        "command": "sudo apt update && sudo apt upgrade -y && sudo apt autoremove -y",
        "description": "Perform full system upgrade and cleanup",
        "category": "updates",
        "os_type": "linux",
        "tags": ["upgrade", "maintenance", "cleanup"]
    },
    
    # Security
    {
        "name": "Security Audit",
        "command": "echo '=== Failed Login Attempts ==='; sudo grep 'Failed password' /var/log/auth.log | tail -10; echo '=== Active Sessions ==='; who; echo '=== Listening Ports ==='; sudo netstat -tulpn",
        "description": "Basic security audit showing failed logins, sessions, and open ports",
        "category": "security",
        "os_type": "linux",
        "tags": ["security", "audit", "monitoring"]
    },
    {
        "name": "Firewall Status",
        "command": "sudo ufw status verbose || sudo iptables -L -n",
        "description": "Check firewall status and rules",
        "category": "security",
        "os_type": "linux",
        "tags": ["firewall", "security", "iptables"]
    },
    {
        "name": "SSH Key Management",
        "command": "echo '=== Authorized Keys ==='; cat ~/.ssh/authorized_keys; echo '=== SSH Config ==='; sudo grep -E '^(Port|PermitRootLogin|PasswordAuthentication)' /etc/ssh/sshd_config",
        "description": "Display SSH keys and security configuration",
        "category": "security",
        "os_type": "linux",
        "tags": ["ssh", "keys", "security"]
    },
    
    # Backup Operations
    {
        "name": "Database Backup MySQL",
        "command": "mysqldump --all-databases --single-transaction --routines --triggers > /backup/mysql_backup_$(date +%Y%m%d_%H%M%S).sql",
        "description": "Create MySQL database backup",
        "category": "backup",
        "os_type": "linux",
        "tags": ["mysql", "database", "backup"]
    },
    {
        "name": "Config Files Backup",
        "command": "tar -czf /backup/config_backup_$(date +%Y%m%d_%H%M%S).tar.gz /etc /opt/*/config /usr/local/etc",
        "description": "Backup important configuration files",
        "category": "backup",
        "os_type": "linux",
        "tags": ["config", "backup", "files"]
    },
    
    # Docker Management
    {
        "name": "Docker Status",
        "command": "docker --version && echo '=== Running Containers ===' && docker ps && echo '=== Images ===' && docker images && echo '=== System Usage ===' && docker system df",
        "description": "Show Docker version, containers, images, and disk usage",
        "category": "docker",
        "os_type": "linux",
        "tags": ["docker", "containers", "monitoring"]
    },
    {
        "name": "Docker Cleanup",
        "command": "docker system prune -f && docker image prune -f",
        "description": "Clean up unused Docker containers and images",
        "category": "docker",
        "os_type": "linux",
        "tags": ["docker", "cleanup", "maintenance"]
    },
    
    # Service Management
    {
        "name": "Service Status Check",
        "command": "systemctl list-units --failed",
        "description": "Show failed systemd services",
        "category": "services",
        "os_type": "linux",
        "tags": ["systemd", "services", "monitoring"]
    },
    {
        "name": "Restart Web Server",
        "command": "sudo systemctl restart nginx || sudo systemctl restart apache2",
        "description": "Restart web server (nginx or apache)",
        "category": "services",
        "os_type": "linux",
        "tags": ["web", "nginx", "apache", "restart"]
    },
    
    # MikroTik Operations
    {
        "name": "MikroTik Export Config",
        "command": "/export compact",
        "description": "Export complete MikroTik configuration",
        "category": "backup",
        "os_type": "mikrotik",
        "tags": ["mikrotik", "config", "export"]
    },
    {
        "name": "MikroTik Interface Status",
        "command": "/interface print",
        "description": "Show all network interfaces status",
        "category": "networking",
        "os_type": "mikrotik",
        "tags": ["mikrotik", "interfaces", "network"]
    },
    {
        "name": "MikroTik DHCP Leases",
        "command": "/ip dhcp-server lease print",
        "description": "Show DHCP lease information",
        "category": "networking",
        "os_type": "mikrotik",
        "tags": ["mikrotik", "dhcp", "network"]
    },
    {
        "name": "MikroTik System Resources",
        "command": "/system resource print",
        "description": "Show system resources and performance",
        "category": "monitoring",
        "os_type": "mikrotik",
        "tags": ["mikrotik", "resources", "monitoring"]
    },
    
    # Web Server Management
    {
        "name": "Nginx Access Logs",
        "command": "sudo tail -n 50 /var/log/nginx/access.log",
        "description": "Show recent nginx access log entries",
        "category": "web",
        "os_type": "linux",
        "tags": ["nginx", "logs", "web"]
    },
    {
        "name": "Apache Error Logs",
        "command": "sudo tail -n 50 /var/log/apache2/error.log",
        "description": "Show recent Apache error log entries",
        "category": "web",
        "os_type": "linux",
        "tags": ["apache", "logs", "web", "errors"]
    },
    
    # Database Management
    {
        "name": "PostgreSQL Status",
        "command": "sudo systemctl status postgresql && sudo -u postgres psql -c 'SELECT version();'",
        "description": "Check PostgreSQL service status and version",
        "category": "database",
        "os_type": "linux",
        "tags": ["postgresql", "database", "status"]
    },
    {
        "name": "MySQL Status",
        "command": "sudo systemctl status mysql && mysql --version",
        "description": "Check MySQL service status and version",
        "category": "database",
        "os_type": "linux",
        "tags": ["mysql", "database", "status"]
    },
    
    # Performance Tuning
    {
        "name": "I/O Performance Test",
        "command": "dd if=/dev/zero of=/tmp/testfile bs=1G count=1 oflag=direct && rm /tmp/testfile",
        "description": "Test disk I/O performance",
        "category": "performance",
        "os_type": "linux",
        "tags": ["io", "performance", "disk"]
    },
    {
        "name": "Network Latency Test",
        "command": "ping -c 10 8.8.8.8 && ping -c 10 1.1.1.1",
        "description": "Test network latency to public DNS servers",
        "category": "networking",
        "os_type": "linux",
        "tags": ["ping", "latency", "network"]
    },
    
    # Log Management
    {
        "name": "System Log Summary",
        "command": "sudo journalctl --since '1 hour ago' --no-pager | tail -50",
        "description": "Show recent system log entries from the last hour",
        "category": "logging",
        "os_type": "linux",
        "tags": ["logs", "journalctl", "system"]
    },
    {
        "name": "Clear Old Logs",
        "command": "sudo journalctl --vacuum-time=7d && sudo find /var/log -name '*.log' -mtime +30 -delete",
        "description": "Clean up old log files older than 7 days",
        "category": "maintenance",
        "os_type": "linux",
        "tags": ["logs", "cleanup", "maintenance"]
    }
]

# SSH Connection Functions
def create_ssh_connection(hostname: str, username: str, password: str = None, 
                         private_key_path: str = None, port: int = 22) -> paramiko.SSHClient:
    """Create SSH connection to a server"""
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        if private_key_path:
            key = paramiko.RSAKey.from_private_key_file(private_key_path)
            ssh.connect(hostname, port=port, username=username, pkey=key, timeout=10)
        else:
            ssh.connect(hostname, port=port, username=username, password=password, timeout=10)
        return ssh
    except Exception as e:
        ssh.close()
        raise e

def execute_command(ssh: paramiko.SSHClient, command: str, timeout: int = 30) -> dict:
    """Execute command on SSH connection"""
    start_time = time.time()
    try:
        stdin, stdout, stderr = ssh.exec_command(command, timeout=timeout)
        
        # Get outputs
        stdout_output = stdout.read().decode('utf-8')
        stderr_output = stderr.read().decode('utf-8')
        return_code = stdout.channel.recv_exit_status()
        
        execution_time = time.time() - start_time
        
        return {
            'stdout': stdout_output,
            'stderr': stderr_output,
            'return_code': return_code,
            'execution_time': execution_time,
            'status': 'success' if return_code == 0 else 'error'
        }
    except Exception as e:
        execution_time = time.time() - start_time
        return {
            'stdout': '',
            'stderr': str(e),
            'return_code': -1,
            'execution_time': execution_time,
            'status': 'error'
        }

def substitute_parameters(command: str, parameters: Dict[str, Any]) -> str:
    """Substitute parameters in command template"""
    for key, value in parameters.items():
        placeholder = f"{{{key}}}"
        command = command.replace(placeholder, str(value))
    return command

async def test_server_connection(server_data: dict) -> dict:
    """Test SSH connection to server"""
    loop = asyncio.get_event_loop()
    
    def _test_connection():
        try:
            ssh = create_ssh_connection(
                hostname=server_data['hostname'],
                username=server_data['username'],
                password=server_data.get('password'),
                private_key_path=server_data.get('private_key_path'),
                port=server_data.get('port', 22)
            )
            
            # Test with simple command
            result = execute_command(ssh, 'echo "Connection successful"')
            ssh.close()
            
            return {
                'success': True,
                'message': 'Connection successful',
                'output': result['stdout'].strip()
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'Connection failed: {str(e)}',
                'output': ''
            }
    
    return await loop.run_in_executor(ssh_executor, _test_connection)

async def execute_task_on_server(server_id: str, task_id: str, timeout: int = 30, parameters: Dict[str, Any] = {}) -> ExecutionResult:
    """Execute a task on a specific server"""
    loop = asyncio.get_event_loop()
    
    # Get server and task from database
    server_doc = await db.servers.find_one({"id": server_id})
    task_doc = await db.tasks.find_one({"id": task_id})
    
    if not server_doc or not task_doc:
        raise HTTPException(status_code=404, detail="Server or task not found")
    
    server = Server(**server_doc)
    task = Task(**task_doc)
    
    # Substitute parameters in command
    final_command = substitute_parameters(task.command, parameters)
    
    def _execute():
        started_at = datetime.utcnow()
        try:
            ssh = create_ssh_connection(
                hostname=server.hostname,
                username=server.username,
                password=server.password,
                private_key_path=server.private_key_path,
                port=server.port
            )
            
            result = execute_command(ssh, final_command, timeout)
            ssh.close()
            
            return ExecutionResult(
                server_id=server_id,
                task_id=task_id,
                command=final_command,
                stdout=result['stdout'],
                stderr=result['stderr'],
                return_code=result['return_code'],
                execution_time=result['execution_time'],
                started_at=started_at,
                completed_at=datetime.utcnow(),
                status=result['status'],
                parameters=parameters
            )
        except Exception as e:
            return ExecutionResult(
                server_id=server_id,
                task_id=task_id,
                command=final_command,
                stdout='',
                stderr=str(e),
                return_code=-1,
                execution_time=time.time() - started_at.timestamp(),
                started_at=started_at,
                completed_at=datetime.utcnow(),
                status='error',
                parameters=parameters
            )
    
    return await loop.run_in_executor(ssh_executor, _execute)

async def create_mikrotik_backup(server_id: str) -> Backup:
    """Create backup for MikroTik server"""
    server_doc = await db.servers.find_one({"id": server_id})
    if not server_doc:
        raise HTTPException(status_code=404, detail="Server not found")
    
    server = Server(**server_doc)
    
    if server.os_type != "mikrotik":
        raise HTTPException(status_code=400, detail="Server is not a MikroTik device")
    
    loop = asyncio.get_event_loop()
    
    def _backup():
        try:
            ssh = create_ssh_connection(
                hostname=server.hostname,
                username=server.username,
                password=server.password,
                port=server.port
            )
            
            result = execute_command(ssh, "/export compact", timeout=60)
            ssh.close()
            
            if result['status'] == 'success':
                return Backup(
                    server_id=server_id,
                    content=result['stdout'],
                    status='success',
                    backup_type='config',
                    size_bytes=len(result['stdout'].encode('utf-8'))
                )
            else:
                return Backup(
                    server_id=server_id,
                    content='',
                    status='failed',
                    backup_type='config',
                    size_bytes=0
                )
        except Exception as e:
            return Backup(
                server_id=server_id,
                content='',
                status='failed',
                backup_type='config',
                size_bytes=0
            )
    
    backup = await loop.run_in_executor(ssh_executor, _backup)
    await db.backups.insert_one(backup.dict())
    return backup

# API Routes
@api_router.get("/")
async def root():
    return {"message": "Server Fleet Automation API"}

# Initialize template tasks
@api_router.post("/initialize-templates")
async def initialize_templates():
    """Initialize pre-loaded task templates"""
    existing_templates = await db.tasks.count_documents({"is_template": True})
    if existing_templates > 0:
        return {"message": f"Templates already initialized ({existing_templates} templates)"}
    
    created_count = 0
    for template_data in TASK_TEMPLATES:
        template_data['is_template'] = True
        task = Task(**template_data)
        await db.tasks.insert_one(task.dict())
        created_count += 1
    
    return {"message": f"Initialized {created_count} task templates"}

# Server Management Routes
@api_router.post("/servers", response_model=Server)
async def create_server(server: ServerCreate):
    server_dict = server.dict()
    server_obj = Server(**server_dict)
    await db.servers.insert_one(server_obj.dict())
    return server_obj

@api_router.get("/servers", response_model=List[Server])
async def get_servers(search: Optional[str] = None, group: Optional[str] = None, tag: Optional[str] = None):
    query = {}
    if search:
        query["$or"] = [
            {"name": {"$regex": search, "$options": "i"}},
            {"hostname": {"$regex": search, "$options": "i"}},
            {"description": {"$regex": search, "$options": "i"}}
        ]
    if group:
        query["groups"] = group
    if tag:
        query["tags"] = tag
    
    servers = await db.servers.find(query).to_list(1000)
    return [Server(**server) for server in servers]

@api_router.get("/servers/groups")
async def get_server_groups():
    """Get all unique server groups"""
    pipeline = [
        {"$unwind": "$groups"},
        {"$group": {"_id": "$groups"}},
        {"$sort": {"_id": 1}}
    ]
    result = await db.servers.aggregate(pipeline).to_list(None)
    return [item["_id"] for item in result]

@api_router.get("/servers/tags")
async def get_server_tags():
    """Get all unique server tags"""
    pipeline = [
        {"$unwind": "$tags"},
        {"$group": {"_id": "$tags"}},
        {"$sort": {"_id": 1}}
    ]
    result = await db.servers.aggregate(pipeline).to_list(None)
    return [item["_id"] for item in result]

@api_router.get("/servers/{server_id}", response_model=Server)
async def get_server(server_id: str):
    server = await db.servers.find_one({"id": server_id})
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    return Server(**server)

@api_router.put("/servers/{server_id}", response_model=Server)
async def update_server(server_id: str, server_update: ServerCreate):
    existing_server = await db.servers.find_one({"id": server_id})
    if not existing_server:
        raise HTTPException(status_code=404, detail="Server not found")
    
    update_dict = server_update.dict()
    update_dict['id'] = server_id
    server_obj = Server(**update_dict)
    
    await db.servers.replace_one({"id": server_id}, server_obj.dict())
    return server_obj

@api_router.delete("/servers/{server_id}")
async def delete_server(server_id: str):
    result = await db.servers.delete_one({"id": server_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Server not found")
    return {"message": "Server deleted successfully"}

@api_router.post("/servers/test-connection")
async def test_connection(request: TestConnectionRequest):
    """Test SSH connection to a server"""
    result = await test_server_connection(request.dict())
    return result

# Task Management Routes
@api_router.post("/tasks", response_model=Task)
async def create_task(task: TaskCreate):
    task_dict = task.dict()
    task_obj = Task(**task_dict)
    await db.tasks.insert_one(task_obj.dict())
    return task_obj

@api_router.get("/tasks", response_model=List[Task])
async def get_tasks(search: Optional[str] = None, category: Optional[str] = None, os_type: Optional[str] = None):
    query = {}
    if search:
        query["$or"] = [
            {"name": {"$regex": search, "$options": "i"}},
            {"description": {"$regex": search, "$options": "i"}},
            {"command": {"$regex": search, "$options": "i"}}
        ]
    if category:
        query["category"] = category
    if os_type:
        query["os_type"] = os_type
    
    tasks = await db.tasks.find(query).to_list(1000)
    return [Task(**task) for task in tasks]

@api_router.get("/tasks/categories")
async def get_task_categories():
    """Get all unique task categories"""
    pipeline = [
        {"$group": {"_id": "$category"}},
        {"$sort": {"_id": 1}}
    ]
    result = await db.tasks.aggregate(pipeline).to_list(None)
    return [item["_id"] for item in result]

@api_router.get("/tasks/{task_id}", response_model=Task)
async def get_task(task_id: str):
    task = await db.tasks.find_one({"id": task_id})
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return Task(**task)

@api_router.put("/tasks/{task_id}", response_model=Task)
async def update_task(task_id: str, task_update: TaskUpdate):
    existing_task = await db.tasks.find_one({"id": task_id})
    if not existing_task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Update only provided fields
    update_data = {k: v for k, v in task_update.dict().items() if v is not None}
    existing_task.update(update_data)
    
    task_obj = Task(**existing_task)
    await db.tasks.replace_one({"id": task_id}, task_obj.dict())
    return task_obj

@api_router.delete("/tasks/{task_id}")
async def delete_task(task_id: str):
    result = await db.tasks.delete_one({"id": task_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"message": "Task deleted successfully"}

# Execution Routes
@api_router.post("/execute", response_model=List[ExecutionResult])
async def execute_task(request: ExecutionRequest):
    """Execute a task on multiple servers"""
    results = []
    
    # Execute tasks in parallel
    tasks = []
    for server_id in request.server_ids:
        task = execute_task_on_server(server_id, request.task_id, request.timeout, request.parameters)
        tasks.append(task)
    
    # Wait for all tasks to complete
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Store results in database
    for result in results:
        if isinstance(result, ExecutionResult):
            await db.executions.insert_one(result.dict())
    
    # Filter out exceptions and return results
    valid_results = [r for r in results if isinstance(r, ExecutionResult)]
    return valid_results

@api_router.get("/executions", response_model=List[ExecutionResult])
async def get_executions(limit: int = 100):
    """Get recent execution results"""
    executions = await db.executions.find().sort("started_at", -1).limit(limit).to_list(limit)
    return [ExecutionResult(**execution) for execution in executions]

@api_router.get("/executions/{execution_id}", response_model=ExecutionResult)
async def get_execution(execution_id: str):
    execution = await db.executions.find_one({"id": execution_id})
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")
    return ExecutionResult(**execution)

# Quick command execution
@api_router.post("/quick-execute")
async def quick_execute(server_id: str, command: str, timeout: int = 30):
    """Execute a quick command on a server without saving as task"""
    server_doc = await db.servers.find_one({"id": server_id})
    if not server_doc:
        raise HTTPException(status_code=404, detail="Server not found")
    
    server = Server(**server_doc)
    
    loop = asyncio.get_event_loop()
    
    def _execute():
        try:
            ssh = create_ssh_connection(
                hostname=server.hostname,
                username=server.username,
                password=server.password,
                private_key_path=server.private_key_path,
                port=server.port
            )
            
            result = execute_command(ssh, command, timeout)
            ssh.close()
            return result
        except Exception as e:
            return {
                'stdout': '',
                'stderr': str(e),
                'return_code': -1,
                'execution_time': 0,
                'status': 'error'
            }
    
    result = await loop.run_in_executor(ssh_executor, _execute)
    return result

# Backup Management Routes
@api_router.post("/backups/{server_id}", response_model=Backup)
async def create_backup(server_id: str):
    """Create backup for a server"""
    backup = await create_mikrotik_backup(server_id)
    return backup

@api_router.get("/backups", response_model=List[Backup])
async def get_backups(server_id: Optional[str] = None, limit: int = 100):
    """Get backup history"""
    query = {}
    if server_id:
        query["server_id"] = server_id
    
    backups = await db.backups.find(query).sort("timestamp", -1).limit(limit).to_list(limit)
    return [Backup(**backup) for backup in backups]

@api_router.get("/backups/stats")
async def get_backup_stats():
    """Get backup statistics"""
    total_backups = await db.backups.count_documents({})
    successful_backups = await db.backups.count_documents({"status": "success"})
    failed_backups = await db.backups.count_documents({"status": "failed"})
    running_backups = await db.backups.count_documents({"status": "running"})
    
    return {
        "total": total_backups,
        "successful": successful_backups,
        "failed": failed_backups,
        "running": running_backups
    }

# Global Search
@api_router.get("/search")
async def global_search(q: str):
    """Global search across servers, tasks, and executions"""
    results = {
        "servers": [],
        "tasks": [],
        "executions": []
    }
    
    # Search servers
    server_query = {
        "$or": [
            {"name": {"$regex": q, "$options": "i"}},
            {"hostname": {"$regex": q, "$options": "i"}},
            {"description": {"$regex": q, "$options": "i"}}
        ]
    }
    servers = await db.servers.find(server_query).limit(10).to_list(10)
    results["servers"] = [Server(**server) for server in servers]
    
    # Search tasks
    task_query = {
        "$or": [
            {"name": {"$regex": q, "$options": "i"}},
            {"description": {"$regex": q, "$options": "i"}},
            {"command": {"$regex": q, "$options": "i"}}
        ]
    }
    tasks = await db.tasks.find(task_query).limit(10).to_list(10)
    results["tasks"] = [Task(**task) for task in tasks]
    
    # Search executions
    execution_query = {
        "$or": [
            {"command": {"$regex": q, "$options": "i"}},
            {"stdout": {"$regex": q, "$options": "i"}}
        ]
    }
    executions = await db.executions.find(execution_query).limit(10).to_list(10)
    results["executions"] = [ExecutionResult(**execution) for execution in executions]
    
    return results

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("startup")
async def startup_event():
    """Initialize templates on startup"""
    try:
        await initialize_templates()
    except Exception as e:
        logger.error(f"Failed to initialize templates: {e}")

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
    ssh_executor.shutdown(wait=True)