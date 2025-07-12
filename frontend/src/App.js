import React, { useState, useEffect } from 'react';
import axios from 'axios';
import './App.css';

const API_BASE_URL = process.env.REACT_APP_BACKEND_URL;

const App = () => {
  const [activeTab, setActiveTab] = useState('servers');
  const [servers, setServers] = useState([]);
  const [tasks, setTasks] = useState([]);
  const [executions, setExecutions] = useState([]);
  const [backups, setBackups] = useState([]);
  const [backupStats, setBackupStats] = useState({ total: 0, successful: 0, failed: 0, running: 0 });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [searchTerm, setSearchTerm] = useState('');
  const [searchResults, setSearchResults] = useState(null);

  // Filters
  const [taskCategoryFilter, setTaskCategoryFilter] = useState('');
  const [taskOsFilter, setTaskOsFilter] = useState('');
  const [serverGroupFilter, setServerGroupFilter] = useState('');
  const [categories, setCategories] = useState([]);
  const [groups, setGroups] = useState([]);

  // Server form state
  const [serverForm, setServerForm] = useState({
    name: '',
    hostname: '',
    username: '',
    password: '',
    port: 22,
    os_type: 'linux',
    groups: [],
    tags: [],
    description: ''
  });

  // Task form state
  const [taskForm, setTaskForm] = useState({
    name: '',
    command: '',
    description: '',
    category: 'custom',
    os_type: 'linux',
    parameters: [],
    tags: []
  });

  // Edit task state
  const [editingTask, setEditingTask] = useState(null);
  const [editTaskForm, setEditTaskForm] = useState({});

  // Execution state
  const [selectedServers, setSelectedServers] = useState([]);
  const [selectedTask, setSelectedTask] = useState('');
  const [taskParameters, setTaskParameters] = useState({});
  const [quickCommand, setQuickCommand] = useState('');
  const [quickCommandServer, setQuickCommandServer] = useState('');

  useEffect(() => {
    fetchData();
    initializeTemplates();
  }, []);

  const fetchData = async () => {
    try {
      const [serversRes, tasksRes, executionsRes, backupsRes, backupStatsRes, categoriesRes, groupsRes] = await Promise.all([
        axios.get(`${API_BASE_URL}/api/servers`),
        axios.get(`${API_BASE_URL}/api/tasks`),
        axios.get(`${API_BASE_URL}/api/executions?limit=50`),
        axios.get(`${API_BASE_URL}/api/backups?limit=50`),
        axios.get(`${API_BASE_URL}/api/backups/stats`),
        axios.get(`${API_BASE_URL}/api/tasks/categories`),
        axios.get(`${API_BASE_URL}/api/servers/groups`)
      ]);
      
      setServers(serversRes.data);
      setTasks(tasksRes.data);
      setExecutions(executionsRes.data);
      setBackups(backupsRes.data);
      setBackupStats(backupStatsRes.data);
      setCategories(categoriesRes.data);
      setGroups(groupsRes.data);
    } catch (err) {
      setError('Failed to fetch data');
    }
  };

  const initializeTemplates = async () => {
    try {
      await axios.post(`${API_BASE_URL}/api/initialize-templates`);
    } catch (err) {
      console.log('Templates initialization:', err.message);
    }
  };

  const showMessage = (message, type = 'success') => {
    if (type === 'success') {
      setSuccess(message);
      setError('');
    } else {
      setError(message);
      setSuccess('');
    }
    setTimeout(() => {
      setSuccess('');
      setError('');
    }, 3000);
  };

  // Global search
  const handleGlobalSearch = async (query) => {
    if (!query.trim()) {
      setSearchResults(null);
      return;
    }

    try {
      const response = await axios.get(`${API_BASE_URL}/api/search?q=${encodeURIComponent(query)}`);
      setSearchResults(response.data);
    } catch (err) {
      setError('Search failed');
    }
  };

  // Server operations
  const handleServerSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      const formData = {
        ...serverForm,
        groups: serverForm.groups.filter(g => g.trim()),
        tags: serverForm.tags.filter(t => t.trim())
      };
      await axios.post(`${API_BASE_URL}/api/servers`, formData);
      showMessage('Server added successfully');
      setServerForm({
        name: '',
        hostname: '',
        username: '',
        password: '',
        port: 22,
        os_type: 'linux',
        groups: [],
        tags: [],
        description: ''
      });
      fetchData();
    } catch (err) {
      showMessage('Failed to add server', 'error');
    }
    setLoading(false);
  };

  // Task operations
  const handleTaskSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      const formData = {
        ...taskForm,
        tags: taskForm.tags.filter(t => t.trim())
      };
      await axios.post(`${API_BASE_URL}/api/tasks`, formData);
      showMessage('Task added successfully');
      setTaskForm({
        name: '',
        command: '',
        description: '',
        category: 'custom',
        os_type: 'linux',
        parameters: [],
        tags: []
      });
      fetchData();
    } catch (err) {
      showMessage('Failed to add task', 'error');
    }
    setLoading(false);
  };

  const handleEditTask = (task) => {
    setEditingTask(task.id);
    setEditTaskForm({
      name: task.name,
      command: task.command,
      description: task.description || '',
      category: task.category,
      os_type: task.os_type,
      tags: task.tags || []
    });
  };

  const handleUpdateTask = async (taskId) => {
    setLoading(true);
    try {
      await axios.put(`${API_BASE_URL}/api/tasks/${taskId}`, editTaskForm);
      showMessage('Task updated successfully');
      setEditingTask(null);
      setEditTaskForm({});
      fetchData();
    } catch (err) {
      showMessage('Failed to update task', 'error');
    }
    setLoading(false);
  };

  const testConnection = async (server) => {
    setLoading(true);
    try {
      const response = await axios.post(`${API_BASE_URL}/api/servers/test-connection`, {
        hostname: server.hostname,
        username: server.username,
        password: server.password,
        port: server.port
      });
      
      if (response.data.success) {
        showMessage(`Connection successful: ${response.data.message}`);
      } else {
        showMessage(`Connection failed: ${response.data.message}`, 'error');
      }
    } catch (err) {
      showMessage('Connection test failed', 'error');
    }
    setLoading(false);
  };

  const executeTask = async () => {
    if (!selectedTask || selectedServers.length === 0) {
      showMessage('Please select a task and at least one server', 'error');
      return;
    }

    setLoading(true);
    try {
      const response = await axios.post(`${API_BASE_URL}/api/execute`, {
        server_ids: selectedServers,
        task_id: selectedTask,
        timeout: 30,
        parameters: taskParameters
      });
      
      showMessage(`Task executed on ${response.data.length} servers`);
      setTaskParameters({});
      fetchData();
    } catch (err) {
      showMessage('Failed to execute task', 'error');
    }
    setLoading(false);
  };

  const executeQuickCommand = async () => {
    if (!quickCommand || !quickCommandServer) {
      showMessage('Please enter a command and select a server', 'error');
      return;
    }

    setLoading(true);
    try {
      const response = await axios.post(`${API_BASE_URL}/api/quick-execute`, null, {
        params: {
          server_id: quickCommandServer,
          command: quickCommand,
          timeout: 30
        }
      });
      
      showMessage(`Command executed. Status: ${response.data.status}`);
      setQuickCommand('');
    } catch (err) {
      showMessage('Failed to execute command', 'error');
    }
    setLoading(false);
  };

  const createBackup = async (serverId) => {
    setLoading(true);
    try {
      await axios.post(`${API_BASE_URL}/api/backups/${serverId}`);
      showMessage('Backup created successfully');
      fetchData();
    } catch (err) {
      showMessage('Failed to create backup', 'error');
    }
    setLoading(false);
  };

  const deleteServer = async (serverId) => {
    if (!window.confirm('Are you sure you want to delete this server?')) return;
    
    setLoading(true);
    try {
      await axios.delete(`${API_BASE_URL}/api/servers/${serverId}`);
      showMessage('Server deleted successfully');
      fetchData();
    } catch (err) {
      showMessage('Failed to delete server', 'error');
    }
    setLoading(false);
  };

  const deleteTask = async (taskId) => {
    if (!window.confirm('Are you sure you want to delete this task?')) return;
    
    setLoading(true);
    try {
      await axios.delete(`${API_BASE_URL}/api/tasks/${taskId}`);
      showMessage('Task deleted successfully');
      fetchData();
    } catch (err) {
      showMessage('Failed to delete task', 'error');
    }
    setLoading(false);
  };

  // Filter functions
  const getFilteredTasks = () => {
    return tasks.filter(task => {
      const matchesSearch = !searchTerm || 
        task.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
        task.description?.toLowerCase().includes(searchTerm.toLowerCase()) ||
        task.command.toLowerCase().includes(searchTerm.toLowerCase());
      
      const matchesCategory = !taskCategoryFilter || task.category === taskCategoryFilter;
      const matchesOs = !taskOsFilter || task.os_type === taskOsFilter;
      
      return matchesSearch && matchesCategory && matchesOs;
    });
  };

  const getFilteredServers = () => {
    return servers.filter(server => {
      const matchesSearch = !searchTerm || 
        server.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
        server.hostname.toLowerCase().includes(searchTerm.toLowerCase()) ||
        server.description?.toLowerCase().includes(searchTerm.toLowerCase());
      
      const matchesGroup = !serverGroupFilter || server.groups.includes(serverGroupFilter);
      
      return matchesSearch && matchesGroup;
    });
  };

  // Get task for execution to show parameters
  const getSelectedTaskObj = () => {
    return tasks.find(t => t.id === selectedTask);
  };

  const TabButton = ({ tab, label, isActive, badge }) => (
    <button
      onClick={() => setActiveTab(tab)}
      className={`px-6 py-3 font-medium rounded-lg transition-all relative ${
        isActive
          ? 'bg-blue-600 text-white shadow-lg'
          : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
      }`}
    >
      {label}
      {badge && (
        <span className="absolute -top-2 -right-2 bg-red-500 text-white text-xs rounded-full h-6 w-6 flex items-center justify-center">
          {badge}
        </span>
      )}
    </button>
  );

  const formatTimestamp = (timestamp) => {
    return new Date(timestamp).toLocaleString();
  };

  const formatFileSize = (bytes) => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <div className="flex items-center">
              <div className="flex-shrink-0">
                <h1 className="text-2xl font-bold text-gray-900">
                  🚀 Fleet Automation Pro
                </h1>
              </div>
            </div>
            <div className="flex items-center space-x-4">
              {/* Global Search */}
              <div className="relative">
                <input
                  type="text"
                  placeholder="Global search..."
                  value={searchTerm}
                  onChange={(e) => {
                    setSearchTerm(e.target.value);
                    handleGlobalSearch(e.target.value);
                  }}
                  className="w-64 px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
                <div className="absolute right-3 top-2.5">
                  🔍
                </div>
              </div>
              <div className="flex items-center space-x-2">
                <span className="text-sm text-gray-600">
                  {servers.length} Servers
                </span>
                <span className="text-sm text-gray-600">•</span>
                <span className="text-sm text-gray-600">
                  {tasks.length} Tasks
                </span>
                <span className="text-sm text-gray-600">•</span>
                <span className="text-sm text-gray-600">
                  {backupStats.total} Backups
                </span>
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* Navigation */}
      <nav className="bg-white shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex space-x-8 py-4">
            <TabButton tab="servers" label="Servers" isActive={activeTab === 'servers'} />
            <TabButton tab="tasks" label="Tasks" isActive={activeTab === 'tasks'} />
            <TabButton tab="execute" label="Execute" isActive={activeTab === 'execute'} />
            <TabButton tab="quick" label="Quick Command" isActive={activeTab === 'quick'} />
            <TabButton tab="backups" label="Backups" isActive={activeTab === 'backups'} badge={backupStats.failed > 0 ? backupStats.failed : null} />
            <TabButton tab="history" label="History" isActive={activeTab === 'history'} />
          </div>
        </div>
      </nav>

      {/* Global Search Results */}
      {searchResults && (
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="bg-white rounded-lg shadow p-4">
            <h3 className="text-lg font-semibold mb-3">Search Results for "{searchTerm}"</h3>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {searchResults.servers.length > 0 && (
                <div>
                  <h4 className="font-medium text-gray-700 mb-2">Servers ({searchResults.servers.length})</h4>
                  {searchResults.servers.map(server => (
                    <div key={server.id} className="text-sm text-gray-600 mb-1">
                      {server.name} ({server.hostname})
                    </div>
                  ))}
                </div>
              )}
              {searchResults.tasks.length > 0 && (
                <div>
                  <h4 className="font-medium text-gray-700 mb-2">Tasks ({searchResults.tasks.length})</h4>
                  {searchResults.tasks.map(task => (
                    <div key={task.id} className="text-sm text-gray-600 mb-1">
                      {task.name} ({task.category})
                    </div>
                  ))}
                </div>
              )}
              {searchResults.executions.length > 0 && (
                <div>
                  <h4 className="font-medium text-gray-700 mb-2">Executions ({searchResults.executions.length})</h4>
                  {searchResults.executions.map(execution => (
                    <div key={execution.id} className="text-sm text-gray-600 mb-1">
                      {execution.command.substring(0, 50)}...
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Messages */}
      {(error || success) && (
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          {error && (
            <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded">
              {error}
            </div>
          )}
          {success && (
            <div className="bg-green-100 border border-green-400 text-green-700 px-4 py-3 rounded">
              {success}
            </div>
          )}
        </div>
      )}

      {/* Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {activeTab === 'servers' && (
          <div className="space-y-8">
            <div className="bg-white rounded-lg shadow p-6">
              <h2 className="text-xl font-semibold mb-4">Add New Server</h2>
              <form onSubmit={handleServerSubmit} className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Server Name *
                  </label>
                  <input
                    type="text"
                    value={serverForm.name}
                    onChange={(e) => setServerForm({...serverForm, name: e.target.value})}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    required
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Hostname/IP *
                  </label>
                  <input
                    type="text"
                    value={serverForm.hostname}
                    onChange={(e) => setServerForm({...serverForm, hostname: e.target.value})}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    required
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Username *
                  </label>
                  <input
                    type="text"
                    value={serverForm.username}
                    onChange={(e) => setServerForm({...serverForm, username: e.target.value})}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    required
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Password
                  </label>
                  <input
                    type="password"
                    value={serverForm.password}
                    onChange={(e) => setServerForm({...serverForm, password: e.target.value})}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Port
                  </label>
                  <input
                    type="number"
                    value={serverForm.port}
                    onChange={(e) => setServerForm({...serverForm, port: parseInt(e.target.value)})}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    OS Type
                  </label>
                  <select
                    value={serverForm.os_type}
                    onChange={(e) => setServerForm({...serverForm, os_type: e.target.value})}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    <option value="linux">Linux</option>
                    <option value="mikrotik">MikroTik</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Groups (comma separated)
                  </label>
                  <input
                    type="text"
                    value={serverForm.groups.join(', ')}
                    onChange={(e) => setServerForm({...serverForm, groups: e.target.value.split(',').map(g => g.trim())})}
                    placeholder="production, web, database"
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Tags (comma separated)
                  </label>
                  <input
                    type="text"
                    value={serverForm.tags.join(', ')}
                    onChange={(e) => setServerForm({...serverForm, tags: e.target.value.split(',').map(t => t.trim())})}
                    placeholder="nginx, mysql, monitoring"
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
                <div className="md:col-span-2">
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Description
                  </label>
                  <textarea
                    value={serverForm.description}
                    onChange={(e) => setServerForm({...serverForm, description: e.target.value})}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    rows="2"
                  />
                </div>
                <div className="md:col-span-2">
                  <button
                    type="submit"
                    disabled={loading}
                    className="bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700 disabled:opacity-50"
                  >
                    {loading ? 'Adding...' : 'Add Server'}
                  </button>
                </div>
              </form>
            </div>

            {/* Server Filters */}
            <div className="bg-white rounded-lg shadow p-4">
              <div className="flex flex-wrap gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Filter by Group</label>
                  <select
                    value={serverGroupFilter}
                    onChange={(e) => setServerGroupFilter(e.target.value)}
                    className="px-3 py-2 border border-gray-300 rounded-md text-sm"
                  >
                    <option value="">All Groups</option>
                    {groups.map(group => (
                      <option key={group} value={group}>{group}</option>
                    ))}
                  </select>
                </div>
              </div>
            </div>

            <div className="bg-white rounded-lg shadow">
              <div className="p-6">
                <h2 className="text-xl font-semibold mb-4">Servers ({getFilteredServers().length})</h2>
                <div className="overflow-x-auto">
                  <table className="min-w-full divide-y divide-gray-200">
                    <thead className="bg-gray-50">
                      <tr>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                          Name
                        </th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                          Hostname
                        </th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                          OS Type
                        </th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                          Groups/Tags
                        </th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                          Actions
                        </th>
                      </tr>
                    </thead>
                    <tbody className="bg-white divide-y divide-gray-200">
                      {getFilteredServers().map((server) => (
                        <tr key={server.id}>
                          <td className="px-6 py-4 whitespace-nowrap">
                            <div className="text-sm font-medium text-gray-900">{server.name}</div>
                            <div className="text-sm text-gray-500">{server.description}</div>
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap">
                            <div className="text-sm text-gray-900">{server.hostname}:{server.port}</div>
                            <div className="text-sm text-gray-500">{server.username}</div>
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap">
                            <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${
                              server.os_type === 'linux' ? 'bg-green-100 text-green-800' : 'bg-blue-100 text-blue-800'
                            }`}>
                              {server.os_type}
                            </span>
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap">
                            <div className="flex flex-wrap gap-1">
                              {server.groups?.map(group => (
                                <span key={group} className="inline-flex px-2 py-1 text-xs font-semibold rounded-full bg-purple-100 text-purple-800">
                                  {group}
                                </span>
                              ))}
                              {server.tags?.map(tag => (
                                <span key={tag} className="inline-flex px-2 py-1 text-xs font-semibold rounded-full bg-yellow-100 text-yellow-800">
                                  #{tag}
                                </span>
                              ))}
                            </div>
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">
                            <button
                              onClick={() => testConnection(server)}
                              disabled={loading}
                              className="text-blue-600 hover:text-blue-900 mr-3"
                            >
                              Test
                            </button>
                            {server.os_type === 'mikrotik' && (
                              <button
                                onClick={() => createBackup(server.id)}
                                disabled={loading}
                                className="text-green-600 hover:text-green-900 mr-3"
                              >
                                Backup
                              </button>
                            )}
                            <button
                              onClick={() => deleteServer(server.id)}
                              disabled={loading}
                              className="text-red-600 hover:text-red-900"
                            >
                              Delete
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'tasks' && (
          <div className="space-y-8">
            <div className="bg-white rounded-lg shadow p-6">
              <h2 className="text-xl font-semibold mb-4">Add New Task</h2>
              <form onSubmit={handleTaskSubmit} className="space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Task Name *
                    </label>
                    <input
                      type="text"
                      value={taskForm.name}
                      onChange={(e) => setTaskForm({...taskForm, name: e.target.value})}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                      required
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Category
                    </label>
                    <select
                      value={taskForm.category}
                      onChange={(e) => setTaskForm({...taskForm, category: e.target.value})}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    >
                      <option value="custom">Custom</option>
                      <option value="monitoring">Monitoring</option>
                      <option value="updates">Updates</option>
                      <option value="security">Security</option>
                      <option value="backup">Backup</option>
                      <option value="networking">Networking</option>
                      <option value="services">Services</option>
                      <option value="docker">Docker</option>
                      <option value="web">Web</option>
                      <option value="database">Database</option>
                      <option value="performance">Performance</option>
                      <option value="logging">Logging</option>
                      <option value="maintenance">Maintenance</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      OS Type
                    </label>
                    <select
                      value={taskForm.os_type}
                      onChange={(e) => setTaskForm({...taskForm, os_type: e.target.value})}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    >
                      <option value="linux">Linux</option>
                      <option value="mikrotik">MikroTik</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Tags (comma separated)
                    </label>
                    <input
                      type="text"
                      value={taskForm.tags.join(', ')}
                      onChange={(e) => setTaskForm({...taskForm, tags: e.target.value.split(',').map(t => t.trim())})}
                      placeholder="nginx, backup, monitoring"
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                  </div>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Command *
                  </label>
                  <textarea
                    value={taskForm.command}
                    onChange={(e) => setTaskForm({...taskForm, command: e.target.value})}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    rows="3"
                    placeholder="echo 'Hello World'"
                    required
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Description
                  </label>
                  <textarea
                    value={taskForm.description}
                    onChange={(e) => setTaskForm({...taskForm, description: e.target.value})}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    rows="2"
                    placeholder="Describe what this task does..."
                  />
                </div>
                <button
                  type="submit"
                  disabled={loading}
                  className="bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700 disabled:opacity-50"
                >
                  {loading ? 'Adding...' : 'Add Task'}
                </button>
              </form>
            </div>

            {/* Task Filters */}
            <div className="bg-white rounded-lg shadow p-4">
              <div className="flex flex-wrap gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Filter by Category</label>
                  <select
                    value={taskCategoryFilter}
                    onChange={(e) => setTaskCategoryFilter(e.target.value)}
                    className="px-3 py-2 border border-gray-300 rounded-md text-sm"
                  >
                    <option value="">All Categories</option>
                    {categories.map(category => (
                      <option key={category} value={category}>{category}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Filter by OS</label>
                  <select
                    value={taskOsFilter}
                    onChange={(e) => setTaskOsFilter(e.target.value)}
                    className="px-3 py-2 border border-gray-300 rounded-md text-sm"
                  >
                    <option value="">All OS Types</option>
                    <option value="linux">Linux</option>
                    <option value="mikrotik">MikroTik</option>
                  </select>
                </div>
              </div>
            </div>

            <div className="bg-white rounded-lg shadow">
              <div className="p-6">
                <h2 className="text-xl font-semibold mb-4">Tasks ({getFilteredTasks().length})</h2>
                <div className="space-y-4">
                  {getFilteredTasks().map((task) => (
                    <div key={task.id} className="border rounded-lg p-4">
                      {editingTask === task.id ? (
                        <div className="space-y-4">
                          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            <input
                              type="text"
                              value={editTaskForm.name}
                              onChange={(e) => setEditTaskForm({...editTaskForm, name: e.target.value})}
                              className="px-3 py-2 border border-gray-300 rounded-md"
                              placeholder="Task name"
                            />
                            <select
                              value={editTaskForm.category}
                              onChange={(e) => setEditTaskForm({...editTaskForm, category: e.target.value})}
                              className="px-3 py-2 border border-gray-300 rounded-md"
                            >
                              <option value="custom">Custom</option>
                              <option value="monitoring">Monitoring</option>
                              <option value="updates">Updates</option>
                              <option value="security">Security</option>
                              <option value="backup">Backup</option>
                              <option value="networking">Networking</option>
                            </select>
                          </div>
                          <textarea
                            value={editTaskForm.command}
                            onChange={(e) => setEditTaskForm({...editTaskForm, command: e.target.value})}
                            className="w-full px-3 py-2 border border-gray-300 rounded-md"
                            rows="3"
                          />
                          <textarea
                            value={editTaskForm.description}
                            onChange={(e) => setEditTaskForm({...editTaskForm, description: e.target.value})}
                            className="w-full px-3 py-2 border border-gray-300 rounded-md"
                            rows="2"
                            placeholder="Description"
                          />
                          <div className="flex space-x-2">
                            <button
                              onClick={() => handleUpdateTask(task.id)}
                              disabled={loading}
                              className="bg-green-600 text-white px-4 py-2 rounded-md hover:bg-green-700"
                            >
                              Save
                            </button>
                            <button
                              onClick={() => setEditingTask(null)}
                              className="bg-gray-600 text-white px-4 py-2 rounded-md hover:bg-gray-700"
                            >
                              Cancel
                            </button>
                          </div>
                        </div>
                      ) : (
                        <div className="flex justify-between items-start">
                          <div className="flex-1">
                            <div className="flex items-center space-x-2 mb-2">
                              <h3 className="text-lg font-medium">{task.name}</h3>
                              <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${
                                task.os_type === 'linux' ? 'bg-green-100 text-green-800' : 'bg-blue-100 text-blue-800'
                              }`}>
                                {task.os_type}
                              </span>
                              <span className="inline-flex px-2 py-1 text-xs font-semibold rounded-full bg-purple-100 text-purple-800">
                                {task.category}
                              </span>
                              {task.is_template && (
                                <span className="inline-flex px-2 py-1 text-xs font-semibold rounded-full bg-yellow-100 text-yellow-800">
                                  Template
                                </span>
                              )}
                            </div>
                            {task.description && (
                              <p className="text-sm text-gray-600 mb-2">{task.description}</p>
                            )}
                            {task.tags && task.tags.length > 0 && (
                              <div className="flex flex-wrap gap-1 mb-2">
                                {task.tags.map(tag => (
                                  <span key={tag} className="inline-flex px-2 py-1 text-xs font-semibold rounded-full bg-gray-100 text-gray-800">
                                    #{tag}
                                  </span>
                                ))}
                              </div>
                            )}
                            <div className="mt-2 bg-gray-100 rounded p-2">
                              <code className="text-sm">{task.command}</code>
                            </div>
                          </div>
                          <div className="flex space-x-2 ml-4">
                            <button
                              onClick={() => handleEditTask(task)}
                              disabled={loading}
                              className="text-blue-600 hover:text-blue-900"
                            >
                              Edit
                            </button>
                            <button
                              onClick={() => deleteTask(task.id)}
                              disabled={loading}
                              className="text-red-600 hover:text-red-900"
                            >
                              Delete
                            </button>
                          </div>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'execute' && (
          <div className="space-y-8">
            <div className="bg-white rounded-lg shadow p-6">
              <h2 className="text-xl font-semibold mb-4">Execute Task</h2>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Select Task
                  </label>
                  <select
                    value={selectedTask}
                    onChange={(e) => {
                      setSelectedTask(e.target.value);
                      setTaskParameters({});
                    }}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    <option value="">Select a task...</option>
                    {tasks.map((task) => (
                      <option key={task.id} value={task.id}>
                        {task.name} ({task.os_type} - {task.category})
                      </option>
                    ))}
                  </select>
                </div>

                {/* Task Parameters */}
                {getSelectedTaskObj()?.parameters?.length > 0 && (
                  <div className="bg-gray-50 p-4 rounded-lg">
                    <h3 className="text-sm font-medium text-gray-700 mb-3">Task Parameters</h3>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      {getSelectedTaskObj().parameters.map((param) => (
                        <div key={param.name}>
                          <label className="block text-sm font-medium text-gray-700 mb-1">
                            {param.name} {param.required && '*'}
                          </label>
                          {param.type === 'select' ? (
                            <select
                              value={taskParameters[param.name] || ''}
                              onChange={(e) => setTaskParameters({...taskParameters, [param.name]: e.target.value})}
                              className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
                              required={param.required}
                            >
                              <option value="">Select {param.name}</option>
                              {param.options.map(option => (
                                <option key={option} value={option}>{option}</option>
                              ))}
                            </select>
                          ) : (
                            <input
                              type={param.type === 'number' ? 'number' : 'text'}
                              value={taskParameters[param.name] || ''}
                              onChange={(e) => setTaskParameters({...taskParameters, [param.name]: e.target.value})}
                              placeholder={param.description}
                              className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
                              required={param.required}
                            />
                          )}
                          <p className="text-xs text-gray-500 mt-1">{param.description}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Select Servers
                  </label>
                  <div className="border rounded-md p-3 max-h-48 overflow-y-auto">
                    {servers.map((server) => (
                      <div key={server.id} className="flex items-center space-x-2 mb-2">
                        <input
                          type="checkbox"
                          id={`server-${server.id}`}
                          checked={selectedServers.includes(server.id)}
                          onChange={(e) => {
                            if (e.target.checked) {
                              setSelectedServers([...selectedServers, server.id]);
                            } else {
                              setSelectedServers(selectedServers.filter(id => id !== server.id));
                            }
                          }}
                          className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                        />
                        <label htmlFor={`server-${server.id}`} className="text-sm flex-1">
                          <span className="font-medium">{server.name}</span>
                          <span className="text-gray-500"> ({server.hostname} - {server.os_type})</span>
                          {server.groups.length > 0 && (
                            <span className="text-purple-600"> [{server.groups.join(', ')}]</span>
                          )}
                        </label>
                      </div>
                    ))}
                  </div>
                </div>
                <button
                  onClick={executeTask}
                  disabled={loading || !selectedTask || selectedServers.length === 0}
                  className="bg-green-600 text-white px-4 py-2 rounded-md hover:bg-green-700 disabled:opacity-50"
                >
                  {loading ? 'Executing...' : 'Execute Task'}
                </button>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'quick' && (
          <div className="space-y-8">
            <div className="bg-white rounded-lg shadow p-6">
              <h2 className="text-xl font-semibold mb-4">Quick Command</h2>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Select Server
                  </label>
                  <select
                    value={quickCommandServer}
                    onChange={(e) => setQuickCommandServer(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    <option value="">Select a server...</option>
                    {servers.map((server) => (
                      <option key={server.id} value={server.id}>
                        {server.name} ({server.hostname} - {server.os_type})
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Command
                  </label>
                  <input
                    type="text"
                    value={quickCommand}
                    onChange={(e) => setQuickCommand(e.target.value)}
                    placeholder="e.g., uptime, df -h, ps aux"
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
                <button
                  onClick={executeQuickCommand}
                  disabled={loading || !quickCommand || !quickCommandServer}
                  className="bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700 disabled:opacity-50"
                >
                  {loading ? 'Executing...' : 'Execute Command'}
                </button>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'backups' && (
          <div className="space-y-8">
            {/* Backup Statistics */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
              <div className="bg-white rounded-lg shadow p-6">
                <div className="flex items-center">
                  <div className="flex-shrink-0">
                    <div className="w-8 h-8 bg-blue-100 rounded-full flex items-center justify-center">
                      📊
                    </div>
                  </div>
                  <div className="ml-4">
                    <div className="text-sm font-medium text-gray-500">Total Backups</div>
                    <div className="text-2xl font-bold text-gray-900">{backupStats.total}</div>
                  </div>
                </div>
              </div>
              
              <div className="bg-white rounded-lg shadow p-6">
                <div className="flex items-center">
                  <div className="flex-shrink-0">
                    <div className="w-8 h-8 bg-green-100 rounded-full flex items-center justify-center">
                      ✅
                    </div>
                  </div>
                  <div className="ml-4">
                    <div className="text-sm font-medium text-gray-500">Successful</div>
                    <div className="text-2xl font-bold text-green-600">{backupStats.successful}</div>
                  </div>
                </div>
              </div>
              
              <div className="bg-white rounded-lg shadow p-6">
                <div className="flex items-center">
                  <div className="flex-shrink-0">
                    <div className="w-8 h-8 bg-red-100 rounded-full flex items-center justify-center">
                      ❌
                    </div>
                  </div>
                  <div className="ml-4">
                    <div className="text-sm font-medium text-gray-500">Failed</div>
                    <div className="text-2xl font-bold text-red-600">{backupStats.failed}</div>
                  </div>
                </div>
              </div>
              
              <div className="bg-white rounded-lg shadow p-6">
                <div className="flex items-center">
                  <div className="flex-shrink-0">
                    <div className="w-8 h-8 bg-yellow-100 rounded-full flex items-center justify-center">
                      ⏳
                    </div>
                  </div>
                  <div className="ml-4">
                    <div className="text-sm font-medium text-gray-500">Running</div>
                    <div className="text-2xl font-bold text-yellow-600">{backupStats.running}</div>
                  </div>
                </div>
              </div>
            </div>

            {/* Backup Actions */}
            <div className="bg-white rounded-lg shadow p-6">
              <h2 className="text-xl font-semibold mb-4">Create Backup</h2>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {servers.filter(s => s.os_type === 'mikrotik').map(server => (
                  <div key={server.id} className="border rounded-lg p-4">
                    <div className="flex justify-between items-center">
                      <div>
                        <h3 className="font-medium">{server.name}</h3>
                        <p className="text-sm text-gray-500">{server.hostname}</p>
                      </div>
                      <button
                        onClick={() => createBackup(server.id)}
                        disabled={loading}
                        className="bg-green-600 text-white px-3 py-1 rounded text-sm hover:bg-green-700 disabled:opacity-50"
                      >
                        Backup
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Backup History */}
            <div className="bg-white rounded-lg shadow">
              <div className="p-6">
                <h2 className="text-xl font-semibold mb-4">Backup History</h2>
                <div className="overflow-x-auto">
                  <table className="min-w-full divide-y divide-gray-200">
                    <thead className="bg-gray-50">
                      <tr>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                          Server
                        </th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                          Timestamp
                        </th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                          Status
                        </th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                          Size
                        </th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                          Type
                        </th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                          Actions
                        </th>
                      </tr>
                    </thead>
                    <tbody className="bg-white divide-y divide-gray-200">
                      {backups.map((backup) => (
                        <tr key={backup.id}>
                          <td className="px-6 py-4 whitespace-nowrap">
                            <div className="text-sm font-medium text-gray-900">
                              {servers.find(s => s.id === backup.server_id)?.name || 'Unknown'}
                            </div>
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap">
                            <div className="text-sm text-gray-900">{formatTimestamp(backup.timestamp)}</div>
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap">
                            <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${
                              backup.status === 'success' ? 'bg-green-100 text-green-800' : 
                              backup.status === 'failed' ? 'bg-red-100 text-red-800' :
                              'bg-yellow-100 text-yellow-800'
                            }`}>
                              {backup.status}
                            </span>
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap">
                            <div className="text-sm text-gray-900">{formatFileSize(backup.size_bytes)}</div>
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap">
                            <div className="text-sm text-gray-900">{backup.backup_type}</div>
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">
                            {backup.status === 'success' && backup.content && (
                              <button
                                onClick={() => {
                                  const blob = new Blob([backup.content], { type: 'text/plain' });
                                  const url = window.URL.createObjectURL(blob);
                                  const a = document.createElement('a');
                                  a.href = url;
                                  a.download = `backup_${backup.server_id}_${backup.timestamp}.txt`;
                                  a.click();
                                  window.URL.revokeObjectURL(url);
                                }}
                                className="text-blue-600 hover:text-blue-900"
                              >
                                Download
                              </button>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'history' && (
          <div className="bg-white rounded-lg shadow">
            <div className="p-6">
              <h2 className="text-xl font-semibold mb-4">Execution History</h2>
              <div className="space-y-4">
                {executions.map((execution) => (
                  <div key={execution.id} className={`border rounded-lg p-4 ${
                    execution.status === 'success' ? 'execution-success' : 'execution-error'
                  }`}>
                    <div className="flex justify-between items-start mb-2">
                      <div>
                        <h3 className="font-medium">{execution.command}</h3>
                        <p className="text-sm text-gray-600">
                          Server: {servers.find(s => s.id === execution.server_id)?.name || 'Unknown'}
                        </p>
                        {execution.parameters && Object.keys(execution.parameters).length > 0 && (
                          <p className="text-sm text-gray-600">
                            Parameters: {JSON.stringify(execution.parameters)}
                          </p>
                        )}
                      </div>
                      <div className="text-right">
                        <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${
                          execution.status === 'success' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
                        }`}>
                          {execution.status}
                        </span>
                        <p className="text-xs text-gray-500 mt-1">
                          {formatTimestamp(execution.completed_at)}
                        </p>
                      </div>
                    </div>
                    
                    {execution.stdout && (
                      <div className="mt-2">
                        <h4 className="text-sm font-medium text-gray-700">Output:</h4>
                        <pre className="text-xs bg-gray-100 p-2 rounded overflow-x-auto">
                          {execution.stdout}
                        </pre>
                      </div>
                    )}
                    
                    {execution.stderr && (
                      <div className="mt-2">
                        <h4 className="text-sm font-medium text-red-700">Error:</h4>
                        <pre className="text-xs bg-red-50 p-2 rounded overflow-x-auto">
                          {execution.stderr}
                        </pre>
                      </div>
                    )}
                    
                    <div className="mt-2 text-xs text-gray-500">
                      Execution Time: {execution.execution_time?.toFixed(2)}s | 
                      Return Code: {execution.return_code}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
};

export default App;