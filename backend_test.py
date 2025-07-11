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
        """Test complete server CRUD operations"""
        self.log("🚀 Testing Server CRUD Operations")
        
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
        
        # Test CREATE server
        test_server = {
            "name": f"test-server-{int(time.time())}",
            "hostname": "192.168.1.100",
            "username": "testuser",
            "password": "testpass",
            "port": 22,
            "os_type": "linux",
            "groups": ["test"],
            "description": "Test server for API testing"
        }
        
        success, created_server = self.run_test(
            "Create Server",
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
        
        success, updated = self.run_test(
            "Update Server",
            "PUT",
            f"api/servers/{server_id}",
            200,
            data=updated_server
        )
        if not success:
            return False
            
        # Test GET servers (should have one more)
        success, servers = self.run_test(
            "Get Servers (After Create)",
            "GET",
            "api/servers",
            200
        )
        if success and isinstance(servers, list):
            self.log(f"   Server count after create: {len(servers)}")
            
        return True

    def test_task_crud(self):
        """Test complete task CRUD operations"""
        self.log("📋 Testing Task CRUD Operations")
        
        # Test GET tasks (empty initially)
        success, tasks = self.run_test(
            "Get Tasks (Initial)",
            "GET",
            "api/tasks",
            200
        )
        if not success:
            return False
            
        initial_count = len(tasks) if isinstance(tasks, list) else 0
        self.log(f"   Initial task count: {initial_count}")
        
        # Test CREATE task
        test_task = {
            "name": f"test-task-{int(time.time())}",
            "command": "echo 'Hello from test task'",
            "description": "Test task for API testing",
            "os_type": "linux",
            "variables": {"test_var": "test_value"}
        }
        
        success, created_task = self.run_test(
            "Create Task",
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
        
        # Test GET single task
        success, task = self.run_test(
            "Get Single Task",
            "GET",
            f"api/tasks/{task_id}",
            200
        )
        if not success:
            return False
            
        # Test GET tasks (should have one more)
        success, tasks = self.run_test(
            "Get Tasks (After Create)",
            "GET",
            "api/tasks",
            200
        )
        if success and isinstance(tasks, list):
            self.log(f"   Task count after create: {len(tasks)}")
            
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

    def test_execution_history(self):
        """Test execution history retrieval"""
        self.log("📊 Testing Execution History")
        
        success, executions = self.run_test(
            "Get Execution History",
            "GET",
            "api/executions",
            200,
            params={"limit": 10}
        )
        
        if success and isinstance(executions, list):
            self.log(f"   Execution history count: {len(executions)}")
        
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
            ("Server CRUD", self.test_server_crud),
            ("Task CRUD", self.test_task_crud),
            ("Connection Testing", self.test_connection_testing),
            ("Quick Execute", self.test_quick_execute),
            ("Task Execution", self.test_task_execution),
            ("Execution History", self.test_execution_history),
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