"""
Enhanced Backup API Endpoints - Enterprise-grade backup management
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
import uuid
import asyncio
from backup_manager import NetworkBackupManager, TunnelOptimizer, BackupStatus, ConfigChange
import logging

logger = logging.getLogger(__name__)

# Enhanced Models
class EnhancedBackup(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    server_id: str
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    status: str = "success"  # success, failed, running
    backup_type: str = "config"  # config, full, incremental
    file_path: Optional[str] = None
    size_bytes: int = 0
    changes_count: int = 0
    md5_checksum: str = ""
    config_version: str = ""
    security_changes: int = 0
    backup_duration: float = 0.0

class BackupDiff(BaseModel):
    server_id: str
    old_backup_id: str
    new_backup_id: str
    changes: List[Dict] = []
    security_changes: List[Dict] = []
    html_diff: str = ""

class ConfigSearchRequest(BaseModel):
    query: str
    server_filter: Optional[str] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None

class ConfigSearchResult(BaseModel):
    server_name: str
    backup_file: str
    timestamp: datetime
    matches: List[Dict] = []

class TunnelConfig(BaseModel):
    interface_name: str
    tunnel_type: str
    mtu_override: Optional[int] = None

class TunnelOptimizationScript(BaseModel):
    interface: str
    tunnel_type: str
    script_content: str
    optimal_mtu: int
    mss_clamp: int

class BackupStatistics(BaseModel):
    total_backups: int
    successful_backups: int
    failed_backups: int
    security_changes_detected: int
    servers_with_changes: List[str]
    average_backup_size: int
    last_backup_time: Optional[datetime]
    backup_frequency: Dict[str, int]
    critical_alerts: List[Dict]

class SecurityAlert(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    server_id: str
    alert_type: str
    severity: str  # low, medium, high, critical
    message: str
    details: Dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    acknowledged: bool = False

# Router for enhanced backup functionality
backup_router = APIRouter(prefix="/api/enhanced-backups", tags=["Enhanced Backups"])

# Global backup manager instance
backup_manager = NetworkBackupManager()
tunnel_optimizer = TunnelOptimizer()

@backup_router.post("/create/{server_id}", response_model=EnhancedBackup)
async def create_enhanced_backup(server_id: str, background_tasks: BackgroundTasks):
    """Create comprehensive MikroTik backup with change detection"""
    from motor.motor_asyncio import AsyncIOMotorClient
    import os
    
    # Get database connection
    mongo_url = os.environ['MONGO_URL']
    client = AsyncIOMotorClient(mongo_url)
    db = client[os.environ['DB_NAME']]
    
    try:
        # Get server data
        server_doc = await db.servers.find_one({"id": server_id})
        if not server_doc:
            raise HTTPException(status_code=404, detail="Server not found")
        
        if server_doc.get('os_type') != 'mikrotik':
            raise HTTPException(status_code=400, detail="Server is not a MikroTik device")
        
        # Create backup using enhanced backup manager
        backup_metadata = await backup_manager.create_mikrotik_backup(server_id, server_doc)
        
        # Convert to EnhancedBackup model
        enhanced_backup = EnhancedBackup(
            server_id=server_id,
            content="",  # Content stored in file system
            timestamp=backup_metadata.timestamp,
            status=backup_metadata.status.value,
            backup_type="config",
            size_bytes=backup_metadata.file_size,
            changes_count=backup_metadata.changes_detected,
            md5_checksum=backup_metadata.md5_checksum,
            config_version=backup_metadata.config_version,
            security_changes=backup_metadata.security_changes,
            backup_duration=backup_metadata.backup_duration
        )
        
        # Store backup metadata in database
        await db.enhanced_backups.insert_one(enhanced_backup.dict())
        
        # Schedule security alerts if needed
        if backup_metadata.security_changes > 0:
            background_tasks.add_task(
                generate_security_alert,
                server_id,
                backup_metadata.security_changes,
                db
            )
        
        return enhanced_backup
        
    except Exception as e:
        logger.error(f"Enhanced backup creation failed for server {server_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Backup creation failed: {str(e)}")

@backup_router.get("/list", response_model=List[EnhancedBackup])
async def get_enhanced_backups(
    server_id: Optional[str] = None,
    limit: int = 100,
    include_content: bool = False
):
    """Get enhanced backup history with metadata"""
    from motor.motor_asyncio import AsyncIOMotorClient
    import os
    
    mongo_url = os.environ['MONGO_URL']
    client = AsyncIOMotorClient(mongo_url)
    db = client[os.environ['DB_NAME']]
    
    query = {}
    if server_id:
        query["server_id"] = server_id
    
    backups = await db.enhanced_backups.find(query).sort("timestamp", -1).limit(limit).to_list(limit)
    
    # Optionally include backup content from file system
    if include_content:
        for backup in backups:
            try:
                # Load content from file system if needed
                backup_content = await load_backup_content(backup["server_id"], backup["timestamp"])
                backup["content"] = backup_content or ""
            except Exception as e:
                logger.warning(f"Could not load backup content: {e}")
                backup["content"] = ""
    
    return [EnhancedBackup(**backup) for backup in backups]

@backup_router.get("/statistics", response_model=BackupStatistics)
async def get_backup_statistics(days: int = 30):
    """Get comprehensive backup statistics for dashboard"""
    from motor.motor_asyncio import AsyncIOMotorClient
    import os
    
    mongo_url = os.environ['MONGO_URL']
    client = AsyncIOMotorClient(mongo_url)
    db = client[os.environ['DB_NAME']]
    
    try:
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        # Aggregate backup statistics
        pipeline = [
            {"$match": {"timestamp": {"$gte": cutoff_date}}},
            {"$group": {
                "_id": None,
                "total_backups": {"$sum": 1},
                "successful_backups": {"$sum": {"$cond": [{"$eq": ["$status", "success"]}, 1, 0]}},
                "failed_backups": {"$sum": {"$cond": [{"$eq": ["$status", "failed"]}, 1, 0]}},
                "total_security_changes": {"$sum": "$security_changes"},
                "total_size": {"$sum": "$size_bytes"},
                "last_backup": {"$max": "$timestamp"}
            }}
        ]
        
        stats = await db.enhanced_backups.aggregate(pipeline).to_list(1)
        
        if not stats:
            return BackupStatistics(
                total_backups=0,
                successful_backups=0,
                failed_backups=0,
                security_changes_detected=0,
                servers_with_changes=[],
                average_backup_size=0,
                last_backup_time=None,
                backup_frequency={},
                critical_alerts=[]
            )
        
        stat = stats[0]
        
        # Get servers with recent changes
        servers_with_changes = await db.enhanced_backups.distinct(
            "server_id",
            {"security_changes": {"$gt": 0}, "timestamp": {"$gte": cutoff_date}}
        )
        
        # Get backup frequency by day
        frequency_pipeline = [
            {"$match": {"timestamp": {"$gte": cutoff_date}}},
            {"$group": {
                "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$timestamp"}},
                "count": {"$sum": 1}
            }},
            {"$sort": {"_id": 1}}
        ]
        
        frequency_data = await db.enhanced_backups.aggregate(frequency_pipeline).to_list(None)
        backup_frequency = {item["_id"]: item["count"] for item in frequency_data}
        
        # Get recent critical alerts
        critical_alerts = await db.security_alerts.find(
            {"severity": "critical", "timestamp": {"$gte": cutoff_date}}
        ).sort("timestamp", -1).limit(10).to_list(10)
        
        return BackupStatistics(
            total_backups=stat["total_backups"],
            successful_backups=stat["successful_backups"],
            failed_backups=stat["failed_backups"],
            security_changes_detected=stat["total_security_changes"],
            servers_with_changes=servers_with_changes,
            average_backup_size=stat["total_size"] // max(stat["total_backups"], 1),
            last_backup_time=stat["last_backup"],
            backup_frequency=backup_frequency,
            critical_alerts=[
                {
                    "id": alert["id"],
                    "server_id": alert["server_id"],
                    "message": alert["message"],
                    "timestamp": alert["timestamp"]
                }
                for alert in critical_alerts
            ]
        )
        
    except Exception as e:
        logger.error(f"Statistics generation failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Statistics generation failed: {str(e)}")

@backup_router.post("/tunnel-optimize", response_model=TunnelOptimizationScript)
async def optimize_tunnel_mtu(tunnel_config: TunnelConfig):
    """Generate MTU optimization script for tunnel interfaces"""
    optimal_mtu = tunnel_config.mtu_override or tunnel_optimizer.get_optimal_mtu(tunnel_config.tunnel_type)
    script_content = tunnel_optimizer.generate_mtu_fix_script(
        tunnel_config.interface_name,
        tunnel_config.tunnel_type
    )
    
    return TunnelOptimizationScript(
        interface=tunnel_config.interface_name,
        tunnel_type=tunnel_config.tunnel_type,
        script_content=script_content,
        optimal_mtu=optimal_mtu,
        mss_clamp=optimal_mtu - 40
    )

@backup_router.get("/tunnel-types")
async def get_supported_tunnel_types():
    """Get list of supported tunnel types and their optimal MTUs"""
    return {
        "tunnel_types": tunnel_optimizer.OPTIMAL_MTUS,
        "recommendations": {
            "gre": "Recommended for site-to-site connections",
            "wireguard": "Modern, secure VPN protocol",
            "l2tp": "Layer 2 tunneling protocol",
            "ipsec": "Enterprise-grade security"
        }
    }

@backup_router.get("/security-alerts", response_model=List[SecurityAlert])
async def get_security_alerts(
    severity: Optional[str] = None,
    server_id: Optional[str] = None,
    acknowledged: Optional[bool] = None,
    limit: int = 50
):
    """Get security alerts from backup analysis"""
    from motor.motor_asyncio import AsyncIOMotorClient
    import os
    
    mongo_url = os.environ['MONGO_URL']
    client = AsyncIOMotorClient(mongo_url)
    db = client[os.environ['DB_NAME']]
    
    query = {}
    if severity:
        query["severity"] = severity
    if server_id:
        query["server_id"] = server_id
    if acknowledged is not None:
        query["acknowledged"] = acknowledged
    
    alerts = await db.security_alerts.find(query).sort("timestamp", -1).limit(limit).to_list(limit)
    return [SecurityAlert(**alert) for alert in alerts]

# Helper functions
async def load_backup_content(server_id: str, timestamp: datetime) -> Optional[str]:
    """Load backup content from file system"""
    try:
        # This would implement the actual file loading logic
        # For now, return None to indicate file system integration needed
        return None
    except Exception as e:
        logger.error(f"Failed to load backup content: {e}")
        return None

async def generate_security_alert(server_id: str, security_changes: int, db):
    """Generate security alert for configuration changes"""
    try:
        alert = SecurityAlert(
            server_id=server_id,
            alert_type="configuration_change",
            severity="high" if security_changes > 5 else "medium",
            message=f"Security-sensitive configuration changes detected: {security_changes} changes",
            details={"changes_count": security_changes, "categories": ["firewall", "nat"]}
        )
        
        await db.security_alerts.insert_one(alert.dict())
        
        # Here you could integrate with Telegram bot for notifications
        logger.info(f"Security alert generated for server {server_id}: {security_changes} changes")
        
    except Exception as e:
        logger.error(f"Failed to generate security alert: {e}")