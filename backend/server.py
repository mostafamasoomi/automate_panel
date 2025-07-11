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
    description: Optional[str] = None

class Task(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    command: str
    description: Optional[str] = None
    os_type: str = "linux"
    variables: Dict[str, Any] = {}
    created_at: datetime = Field(default_factory=datetime.utcnow)

class TaskCreate(BaseModel):
    name: str
    command: str
    description: Optional[str] = None
    os_type: str = "linux"
    variables: Dict[str, Any] = {}

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

class ExecutionRequest(BaseModel):
    server_ids: List[str]
    task_id: str
    timeout: int = 30

class TestConnectionRequest(BaseModel):
    hostname: str
    username: str
    password: Optional[str] = None
    private_key_path: Optional[str] = None
    port: int = 22

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

async def execute_task_on_server(server_id: str, task_id: str, timeout: int = 30) -> ExecutionResult:
    """Execute a task on a specific server"""
    loop = asyncio.get_event_loop()
    
    # Get server and task from database
    server_doc = await db.servers.find_one({"id": server_id})
    task_doc = await db.tasks.find_one({"id": task_id})
    
    if not server_doc or not task_doc:
        raise HTTPException(status_code=404, detail="Server or task not found")
    
    server = Server(**server_doc)
    task = Task(**task_doc)
    
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
            
            result = execute_command(ssh, task.command, timeout)
            ssh.close()
            
            return ExecutionResult(
                server_id=server_id,
                task_id=task_id,
                command=task.command,
                stdout=result['stdout'],
                stderr=result['stderr'],
                return_code=result['return_code'],
                execution_time=result['execution_time'],
                started_at=started_at,
                completed_at=datetime.utcnow(),
                status=result['status']
            )
        except Exception as e:
            return ExecutionResult(
                server_id=server_id,
                task_id=task_id,
                command=task.command,
                stdout='',
                stderr=str(e),
                return_code=-1,
                execution_time=time.time() - started_at.timestamp(),
                started_at=started_at,
                completed_at=datetime.utcnow(),
                status='error'
            )
    
    return await loop.run_in_executor(ssh_executor, _execute)

# API Routes
@api_router.get("/")
async def root():
    return {"message": "Server Fleet Automation API"}

# Server Management Routes
@api_router.post("/servers", response_model=Server)
async def create_server(server: ServerCreate):
    server_dict = server.dict()
    server_obj = Server(**server_dict)
    await db.servers.insert_one(server_obj.dict())
    return server_obj

@api_router.get("/servers", response_model=List[Server])
async def get_servers():
    servers = await db.servers.find().to_list(1000)
    return [Server(**server) for server in servers]

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
async def get_tasks():
    tasks = await db.tasks.find().to_list(1000)
    return [Task(**task) for task in tasks]

@api_router.get("/tasks/{task_id}", response_model=Task)
async def get_task(task_id: str):
    task = await db.tasks.find_one({"id": task_id})
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return Task(**task)

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
        task = execute_task_on_server(server_id, request.task_id, request.timeout)
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

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
    ssh_executor.shutdown(wait=True)