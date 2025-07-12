#!/usr/bin/env python3
"""
Comprehensive Backend API Testing for Server Fleet Automation
Tests all API endpoints and functionality
"""

import requests
import json
import sys
from datetime import datetime
import time

class FleetAutomationAPITester:
    def __init__(self, base_url="https://027b19e8-52b2-4865-a82b-3d6187ee0495.preview.emergentagent.com"):
        self.base_url = base_url
        self.tests_run = 0
        self.tests_passed = 0
        self.created_servers = []
        self.created_tasks = []
        
    def log(self, message, level="INFO"):
        """Log test messages with timestamp"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {level}: {message}")

    def run_test(self, name, method, endpoint, expected_status, data=None, params=None):
        """Run a single API test"""
        url = f"{self.base_url}/{endpoint}"
        headers = {'Content-Type': 'application/json'}
        
        self.tests_run += 1
        self.log(f"🔍 Testing {name}...")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, params=params, timeout=30)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers, params=params, timeout=30)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=headers, timeout=30)
            elif method == 'DELETE':
                response = requests.delete(url, headers=headers, timeout=30)
            
            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                self.log(f"✅ {name} - Status: {response.status_code}")
                try:
                    return True, response.json()
                except:
                    return True, response.text
            else:
                self.log(f"❌ {name} - Expected {expected_status}, got {response.status_code}")
                self.log(f"   Response: {response.text[:200]}")
                return False, {}
                
        except Exception as e:
            self.log(f"❌ {name} - Error: {str(e)}")
            return False, {}

    def test_api_root(self):
        """Test API root endpoint"""
        success, response = self.run_test(
            "API Root",
            "GET", 
            "api/",
            200
        )
        return success

    def test_server_crud(self):
        """Test complete server CRUD operations with enhanced features"""
        self.log("🚀 Testing Enhanced Server CRUD Operations")
        
        # Test GET servers (empty initially)
        success, servers = self.run_test(
            "Get Servers (Initial)",
            "GET",
            "api/servers",
            200
        )
        if not success:
            return False
            
        initial_count = len(servers) if isinstance(servers, list) else 0
        self.log(f"   Initial server count: {initial_count}")
        
        # Test CREATE server with groups and tags
        test_server = {
            "name": f"test-server-{int(time.time())}",
            "hostname": "192.168.1.100",
            "username": "testuser",
            "password": "testpass",
            "port": 22,
            "os_type": "linux",
            "groups": ["test", "production"],
            "tags": ["web", "nginx"],
            "description": "Test server for API testing"
        }
        
        success, created_server = self.run_test(
            "Create Enhanced Server",
            "POST",
            "api/servers",
            200,
            data=test_server
        )
        if not success:
            return False
            
        server_id = created_server.get('id')
        if server_id:
            self.created_servers.append(server_id)
            self.log(f"   Created server ID: {server_id}")
        
        # Test MikroTik server creation
        mikrotik_server = {
            "name": f"mikrotik-test-{int(time.time())}",
            "hostname": "192.168.1.101",
            "username": "admin",
            "password": "testpass",
            "port": 22,
            "os_type": "mikrotik",
            "groups": ["network"],
            "tags": ["router"],
            "description": "Test MikroTik server"
        }
        
        success, created_mikrotik = self.run_test(
            "Create MikroTik Server",
            "POST",
            "api/servers",
            200,
            data=mikrotik_server
        )
        if success:
            mikrotik_id = created_mikrotik.get('id')
            if mikrotik_id:
                self.created_servers.append(mikrotik_id)
                self.log(f"   Created MikroTik server ID: {mikrotik_id}")
        
        # Test server filtering by group
        success, filtered_servers = self.run_test(
            "Filter Servers by Group",
            "GET",
            "api/servers",
            200,
            params={"group": "test"}
        )
        if success and isinstance(filtered_servers, list):
            self.log(f"   Servers in 'test' group: {len(filtered_servers)}")
        
        # Test server filtering by tag
        success, tagged_servers = self.run_test(
            "Filter Servers by Tag",
            "GET",
            "api/servers",
            200,
            params={"tag": "web"}
        )
        if success and isinstance(tagged_servers, list):
            self.log(f"   Servers with 'web' tag: {len(tagged_servers)}")
        
        # Test server search
        success, search_results = self.run_test(
            "Search Servers",
            "GET",
            "api/servers",
            200,
            params={"search": "test"}
        )
        if success and isinstance(search_results, list):
            self.log(f"   Server search results: {len(search_results)}")
        
        # Test get server groups
        success, groups = self.run_test(
            "Get Server Groups",
            "GET",
            "api/servers/groups",
            200
        )
        if success and isinstance(groups, list):
            self.log(f"   Available groups: {len(groups)}")
        
        # Test get server tags
        success, tags = self.run_test(
            "Get Server Tags",
            "GET",
            "api/servers/tags",
            200
        )
        if success and isinstance(tags, list):
            self.log(f"   Available tags: {len(tags)}")
        
        # Test GET single server
        success, server = self.run_test(
            "Get Single Server",
            "GET",
            f"api/servers/{server_id}",
            200
        )
        if not success:
            return False
            
        # Test UPDATE server
        updated_server = test_server.copy()
        updated_server["description"] = "Updated test server"
        updated_server["tags"] = ["web", "nginx", "updated"]
        
        success, updated = self.run_test(
            "Update Server",
            "PUT",
            f"api/servers/{server_id}",
            200,
            data=updated_server
        )
        if not success:
            return False
            
        return True

    def test_template_initialization(self):
        """Test template initialization endpoint"""
        self.log("🎯 Testing Template Initialization")
        
        success, response = self.run_test(
            "Initialize Templates",
            "POST",
            "api/initialize-templates",
            200
        )
        
        if success and isinstance(response, dict):
            self.log(f"   Template initialization: {response.get('message', 'Unknown')}")
        
        return success

    def test_task_crud(self):
        """Test complete task CRUD operations including enhanced features"""
        self.log("📋 Testing Enhanced Task CRUD Operations")
        
        # Test GET tasks (should have templates now)
        success, tasks = self.run_test(
            "Get Tasks (With Templates)",
            "GET",
            "api/tasks",
            200
        )
        if not success:
            return False
            
        initial_count = len(tasks) if isinstance(tasks, list) else 0
        self.log(f"   Task count with templates: {initial_count}")
        
        # Test task filtering by category
        success, filtered_tasks = self.run_test(
            "Filter Tasks by Category",
            "GET",
            "api/tasks",
            200,
            params={"category": "monitoring"}
        )
        if success and isinstance(filtered_tasks, list):
            self.log(f"   Monitoring tasks count: {len(filtered_tasks)}")
        
        # Test task filtering by OS type
        success, linux_tasks = self.run_test(
            "Filter Tasks by OS Type",
            "GET",
            "api/tasks",
            200,
            params={"os_type": "linux"}
        )
        if success and isinstance(linux_tasks, list):
            self.log(f"   Linux tasks count: {len(linux_tasks)}")
        
        # Test task search
        success, search_results = self.run_test(
            "Search Tasks",
            "GET",
            "api/tasks",
            200,
            params={"search": "system"}
        )
        if success and isinstance(search_results, list):
            self.log(f"   Search results count: {len(search_results)}")
        
        # Test get task categories
        success, categories = self.run_test(
            "Get Task Categories",
            "GET",
            "api/tasks/categories",
            200
        )
        if success and isinstance(categories, list):
            self.log(f"   Available categories: {len(categories)}")
        
        # Test CREATE task with enhanced features
        test_task = {
            "name": f"test-task-{int(time.time())}",
            "command": "echo 'Hello from test task'",
            "description": "Test task for API testing",
            "category": "custom",
            "os_type": "linux",
            "tags": ["test", "api"],
            "variables": {"test_var": "test_value"}
        }
        
        success, created_task = self.run_test(
            "Create Enhanced Task",
            "POST",
            "api/tasks",
            200,
            data=test_task
        )
        if not success:
            return False
            
        task_id = created_task.get('id')
        if task_id:
            self.created_tasks.append(task_id)
            self.log(f"   Created task ID: {task_id}")
        
        # Test task UPDATE (editing)
        update_data = {
            "name": "Updated Test Task",
            "description": "Updated description",
            "category": "monitoring"
        }
        
        success, updated_task = self.run_test(
            "Update Task (Edit)",
            "PUT",
            f"api/tasks/{task_id}",
            200,
            data=update_data
        )
        if not success:
            return False
        
        # Test GET single task
        success, task = self.run_test(
            "Get Single Task",
            "GET",
            f"api/tasks/{task_id}",
            200
        )
        if not success:
            return False
            
        return True

    def test_connection_testing(self):
        """Test SSH connection testing endpoint"""
        self.log("🔌 Testing Connection Testing")
        
        # Test with invalid connection (should fail gracefully)
        test_connection = {
            "hostname": "192.168.1.999",  # Invalid IP
            "username": "testuser",
            "password": "testpass",
            "port": 22
        }
        
        success, response = self.run_test(
            "Test Connection (Invalid)",
            "POST",
            "api/servers/test-connection",
            200,
            data=test_connection
        )
        
        if success and isinstance(response, dict):
            self.log(f"   Connection test result: {response.get('success', 'Unknown')}")
            self.log(f"   Message: {response.get('message', 'No message')}")
        
        return success

    def test_quick_execute(self):
        """Test quick command execution"""
        self.log("⚡ Testing Quick Execute")
        
        if not self.created_servers:
            self.log("   No servers available for quick execute test")
            return True
            
        server_id = self.created_servers[0]
        
        # Test quick execute (will fail due to invalid server, but should return proper error)
        success, response = self.run_test(
            "Quick Execute Command",
            "POST",
            "api/quick-execute",
            200,
            params={
                "server_id": server_id,
                "command": "echo 'Quick test'",
                "timeout": 10
            }
        )
        
        if success and isinstance(response, dict):
            self.log(f"   Quick execute status: {response.get('status', 'Unknown')}")
        
        return success

    def test_task_execution(self):
        """Test full task execution"""
        self.log("🎯 Testing Task Execution")
        
        if not self.created_servers or not self.created_tasks:
            self.log("   No servers or tasks available for execution test")
            return True
            
        execution_request = {
            "server_ids": [self.created_servers[0]],
            "task_id": self.created_tasks[0],
            "timeout": 10
        }
        
        success, response = self.run_test(
            "Execute Task",
            "POST",
            "api/execute",
            200,
            data=execution_request
        )
        
        if success and isinstance(response, list):
            self.log(f"   Execution results count: {len(response)}")
        
        return success

    def test_backup_functionality(self):
        """Test backup creation and management"""
        self.log("💾 Testing Backup Functionality")
        
        # Test backup stats
        success, stats = self.run_test(
            "Get Backup Stats",
            "GET",
            "api/backups/stats",
            200
        )
        if success and isinstance(stats, dict):
            self.log(f"   Backup stats: {stats}")
        
        # Test get backups
        success, backups = self.run_test(
            "Get Backup History",
            "GET",
            "api/backups",
            200,
            params={"limit": 10}
        )
        if success and isinstance(backups, list):
            self.log(f"   Backup history count: {len(backups)}")
        
        # Test backup creation (will fail for test server but should handle gracefully)
        mikrotik_servers = [s for s in self.created_servers if "mikrotik" in str(s)]
        if mikrotik_servers:
            server_id = mikrotik_servers[0]
            success, backup = self.run_test(
                "Create Backup",
                "POST",
                f"api/backups/{server_id}",
                200
            )
            if success:
                self.log(f"   Backup creation attempted for server: {server_id}")
        else:
            self.log("   No MikroTik servers available for backup test")
        
        return True

    def test_enhanced_backup_system(self):
        """Test the enhanced Unimus-like backup system"""
        self.log("🔧 Testing Enhanced Backup System (Unimus-like)")
        
        # Test enhanced backup statistics
        success, enhanced_stats = self.run_test(
            "Enhanced Backup Statistics",
            "GET",
            "api/enhanced-backups/statistics",
            200,
            params={"days": 30}
        )
        if success and isinstance(enhanced_stats, dict):
            self.log(f"   Enhanced backup stats: Total={enhanced_stats.get('total_backups', 0)}, "
                    f"Successful={enhanced_stats.get('successful_backups', 0)}, "
                    f"Security Changes={enhanced_stats.get('security_changes_detected', 0)}")
        
        # Test enhanced backup list
        success, enhanced_backups = self.run_test(
            "Enhanced Backup List",
            "GET",
            "api/enhanced-backups/list",
            200,
            params={"limit": 10}
        )
        if success and isinstance(enhanced_backups, list):
            self.log(f"   Enhanced backup history count: {len(enhanced_backups)}")
        
        # Test tunnel optimization - get supported tunnel types
        success, tunnel_types = self.run_test(
            "Get Tunnel Types",
            "GET",
            "api/enhanced-backups/tunnel-types",
            200
        )
        if success and isinstance(tunnel_types, dict):
            types_count = len(tunnel_types.get('tunnel_types', {}))
            self.log(f"   Supported tunnel types: {types_count}")
            if 'tunnel_types' in tunnel_types:
                for tunnel_type, mtu in tunnel_types['tunnel_types'].items():
                    self.log(f"     {tunnel_type}: MTU {mtu}")
        
        # Test tunnel optimization script generation
        tunnel_config = {
            "interface_name": "gre-tunnel1",
            "tunnel_type": "gre",
            "mtu_override": None
        }
        
        success, optimization_script = self.run_test(
            "Generate Tunnel Optimization Script",
            "POST",
            "api/enhanced-backups/tunnel-optimize",
            200,
            data=tunnel_config
        )
        if success and isinstance(optimization_script, dict):
            self.log(f"   Generated script for {optimization_script.get('interface', 'unknown')} "
                    f"({optimization_script.get('tunnel_type', 'unknown')})")
            self.log(f"   Optimal MTU: {optimization_script.get('optimal_mtu', 'unknown')}")
            self.log(f"   MSS Clamp: {optimization_script.get('mss_clamp', 'unknown')}")
        
        # Test WireGuard tunnel optimization
        wireguard_config = {
            "interface_name": "wg-tunnel1",
            "tunnel_type": "wireguard"
        }
        
        success, wg_script = self.run_test(
            "Generate WireGuard Optimization Script",
            "POST",
            "api/enhanced-backups/tunnel-optimize",
            200,
            data=wireguard_config
        )
        if success and isinstance(wg_script, dict):
            self.log(f"   WireGuard MTU: {wg_script.get('optimal_mtu', 'unknown')}")
        
        # Test security alerts
        success, security_alerts = self.run_test(
            "Get Security Alerts",
            "GET",
            "api/enhanced-backups/security-alerts",
            200,
            params={"limit": 10}
        )
        if success and isinstance(security_alerts, list):
            self.log(f"   Security alerts count: {len(security_alerts)}")
        
        # Test security alerts filtering
        success, critical_alerts = self.run_test(
            "Get Critical Security Alerts",
            "GET",
            "api/enhanced-backups/security-alerts",
            200,
            params={"severity": "critical", "limit": 5}
        )
        if success and isinstance(critical_alerts, list):
            self.log(f"   Critical alerts count: {len(critical_alerts)}")
        
        # Test enhanced backup creation (will fail for test server but should handle gracefully)
        mikrotik_servers = [s for s in self.created_servers if "mikrotik" in str(s)]
        if mikrotik_servers:
            server_id = mikrotik_servers[0]
            success, enhanced_backup = self.run_test(
                "Create Enhanced Backup",
                "POST",
                f"api/enhanced-backups/create/{server_id}",
                200
            )
            if success and isinstance(enhanced_backup, dict):
                self.log(f"   Enhanced backup created: ID={enhanced_backup.get('id', 'unknown')}")
                self.log(f"   Backup metadata: Size={enhanced_backup.get('size_bytes', 0)} bytes, "
                        f"Changes={enhanced_backup.get('changes_count', 0)}, "
                        f"Security Changes={enhanced_backup.get('security_changes', 0)}")
                self.log(f"   MD5 Checksum: {enhanced_backup.get('md5_checksum', 'none')[:16]}...")
                self.log(f"   Config Version: {enhanced_backup.get('config_version', 'unknown')}")
                self.log(f"   Backup Duration: {enhanced_backup.get('backup_duration', 0):.2f}s")
        else:
            self.log("   No MikroTik servers available for enhanced backup test")
        
        return True

    def test_global_search(self):
        """Test global search functionality"""
        self.log("🔍 Testing Global Search")
        
        # Test global search
        success, results = self.run_test(
            "Global Search",
            "GET",
            "api/search",
            200,
            params={"q": "test"}
        )
        
        if success and isinstance(results, dict):
            servers_count = len(results.get('servers', []))
            tasks_count = len(results.get('tasks', []))
            executions_count = len(results.get('executions', []))
            
            self.log(f"   Search results - Servers: {servers_count}, Tasks: {tasks_count}, Executions: {executions_count}")
        
        # Test search with different terms
        success, monitoring_results = self.run_test(
            "Search for Monitoring",
            "GET",
            "api/search",
            200,
            params={"q": "monitoring"}
        )
        
        if success and isinstance(monitoring_results, dict):
            tasks_count = len(monitoring_results.get('tasks', []))
            self.log(f"   Monitoring search results - Tasks: {tasks_count}")
        
        return success

    def test_error_handling(self):
        """Test error handling for invalid requests"""
        self.log("🚨 Testing Error Handling")
        
        # Test 404 for non-existent server
        success, _ = self.run_test(
            "Get Non-existent Server",
            "GET",
            "api/servers/non-existent-id",
            404
        )
        
        # Test 404 for non-existent task
        success2, _ = self.run_test(
            "Get Non-existent Task",
            "GET",
            "api/tasks/non-existent-id",
            404
        )
        
        # Test invalid data for server creation
        success3, _ = self.run_test(
            "Create Invalid Server",
            "POST",
            "api/servers",
            422,  # Validation error
            data={"name": ""}  # Missing required fields
        )
        
        return success and success2

    def cleanup(self):
        """Clean up created test data"""
        self.log("🧹 Cleaning up test data")
        
        # Delete created servers
        for server_id in self.created_servers:
            success, _ = self.run_test(
                f"Delete Server {server_id}",
                "DELETE",
                f"api/servers/{server_id}",
                200
            )
        
        # Delete created tasks
        for task_id in self.created_tasks:
            success, _ = self.run_test(
                f"Delete Task {task_id}",
                "DELETE",
                f"api/tasks/{task_id}",
                200
            )

    def run_all_tests(self):
        """Run all API tests"""
        self.log("🚀 Starting Fleet Automation API Tests")
        self.log(f"   Base URL: {self.base_url}")
        
        test_results = []
        
        # Run all test suites
        test_suites = [
            ("API Root", self.test_api_root),
            ("Template Initialization", self.test_template_initialization),
            ("Enhanced Server CRUD", self.test_server_crud),
            ("Enhanced Task CRUD", self.test_task_crud),
            ("Connection Testing", self.test_connection_testing),
            ("Quick Execute", self.test_quick_execute),
            ("Task Execution", self.test_task_execution),
            ("Backup Functionality", self.test_backup_functionality),
            ("Enhanced Backup System", self.test_enhanced_backup_system),
            ("Global Search", self.test_global_search),
            ("Error Handling", self.test_error_handling)
        ]
        
        for suite_name, test_func in test_suites:
            try:
                result = test_func()
                test_results.append((suite_name, result))
                if result:
                    self.log(f"✅ {suite_name} suite passed")
                else:
                    self.log(f"❌ {suite_name} suite failed")
            except Exception as e:
                self.log(f"❌ {suite_name} suite error: {str(e)}")
                test_results.append((suite_name, False))
        
        # Cleanup
        self.cleanup()
        
        # Print final results
        self.log("📊 Final Test Results")
        self.log(f"   Total API calls: {self.tests_run}")
        self.log(f"   Successful calls: {self.tests_passed}")
        self.log(f"   Success rate: {(self.tests_passed/self.tests_run*100):.1f}%")
        
        self.log("📋 Test Suite Results:")
        for suite_name, result in test_results:
            status = "✅ PASS" if result else "❌ FAIL"
            self.log(f"   {suite_name}: {status}")
        
        # Return overall success
        failed_suites = [name for name, result in test_results if not result]
        if failed_suites:
            self.log(f"❌ Failed suites: {', '.join(failed_suites)}")
            return False
        else:
            self.log("🎉 All test suites passed!")
            return True

def main():
    """Main test execution"""
    tester = FleetAutomationAPITester()
    success = tester.run_all_tests()
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())