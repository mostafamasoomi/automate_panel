import React, { useState, useEffect } from 'react';
import axios from 'axios';
import './App.css';

const API_BASE_URL = process.env.REACT_APP_BACKEND_URL;

const App = () => {
  const [activeTab, setActiveTab] = useState('servers');
  const [servers, setServers] = useState([]);
  const [tasks, setTasks] = useState([]);
  const [executions, setExecutions] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  // Server form state
  const [serverForm, setServerForm] = useState({
    name: '',
    hostname: '',
    username: '',
    password: '',
    port: 22,
    os_type: 'linux',
    groups: [],
    description: ''
  });

  // Task form state
  const [taskForm, setTaskForm] = useState({
    name: '',
    command: '',
    description: '',
    os_type: 'linux'
  });

  // Execution state
  const [selectedServers, setSelectedServers] = useState([]);
  const [selectedTask, setSelectedTask] = useState('');
  const [quickCommand, setQuickCommand] = useState('');
  const [quickCommandServer, setQuickCommandServer] = useState('');

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const [serversRes, tasksRes, executionsRes] = await Promise.all([
        axios.get(`${API_BASE_URL}/api/servers`),
        axios.get(`${API_BASE_URL}/api/tasks`),
        axios.get(`${API_BASE_URL}/api/executions?limit=50`)
      ]);
      
      setServers(serversRes.data);
      setTasks(tasksRes.data);
      setExecutions(executionsRes.data);
    } catch (err) {
      setError('Failed to fetch data');
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

  const handleServerSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      await axios.post(`${API_BASE_URL}/api/servers`, serverForm);
      showMessage('Server added successfully');
      setServerForm({
        name: '',
        hostname: '',
        username: '',
        password: '',
        port: 22,
        os_type: 'linux',
        groups: [],
        description: ''
      });
      fetchData();
    } catch (err) {
      showMessage('Failed to add server', 'error');
    }
    setLoading(false);
  };

  const handleTaskSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      await axios.post(`${API_BASE_URL}/api/tasks`, taskForm);
      showMessage('Task added successfully');
      setTaskForm({
        name: '',
        command: '',
        description: '',
        os_type: 'linux'
      });
      fetchData();
    } catch (err) {
      showMessage('Failed to add task', 'error');
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
        timeout: 30
      });
      
      showMessage(`Task executed on ${response.data.length} servers`);
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

  const TabButton = ({ tab, label, isActive }) => (
    <button
      onClick={() => setActiveTab(tab)}
      className={`px-6 py-3 font-medium rounded-lg transition-all ${
        isActive
          ? 'bg-blue-600 text-white shadow-lg'
          : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
      }`}
    >
      {label}
    </button>
  );

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <div className="flex items-center">
              <div className="flex-shrink-0">
                <h1 className="text-2xl font-bold text-gray-900">
                  🚀 Fleet Automation
                </h1>
              </div>
            </div>
            <div className="flex items-center space-x-4">
              <div className="flex items-center space-x-2">
                <span className="text-sm text-gray-600">
                  {servers.length} Servers
                </span>
                <span className="text-sm text-gray-600">•</span>
                <span className="text-sm text-gray-600">
                  {tasks.length} Tasks
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
            <TabButton tab="history" label="History" isActive={activeTab === 'history'} />
          </div>
        </div>
      </nav>

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
                    Server Name
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
                    Hostname/IP
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
                    Username
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

            <div className="bg-white rounded-lg shadow">
              <div className="p-6">
                <h2 className="text-xl font-semibold mb-4">Servers ({servers.length})</h2>
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
                          Status
                        </th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                          Actions
                        </th>
                      </tr>
                    </thead>
                    <tbody className="bg-white divide-y divide-gray-200">
                      {servers.map((server) => (
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
                            <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${
                              server.status === 'online' ? 'bg-green-100 text-green-800' : 
                              server.status === 'offline' ? 'bg-red-100 text-red-800' : 'bg-gray-100 text-gray-800'
                            }`}>
                              {server.status}
                            </span>
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">
                            <button
                              onClick={() => testConnection(server)}
                              disabled={loading}
                              className="text-blue-600 hover:text-blue-900 mr-3"
                            >
                              Test
                            </button>
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
                      Task Name
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
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Command
                  </label>
                  <textarea
                    value={taskForm.command}
                    onChange={(e) => setTaskForm({...taskForm, command: e.target.value})}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    rows="3"
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

            <div className="bg-white rounded-lg shadow">
              <div className="p-6">
                <h2 className="text-xl font-semibold mb-4">Tasks ({tasks.length})</h2>
                <div className="space-y-4">
                  {tasks.map((task) => (
                    <div key={task.id} className="border rounded-lg p-4">
                      <div className="flex justify-between items-start">
                        <div className="flex-1">
                          <div className="flex items-center space-x-2">
                            <h3 className="text-lg font-medium">{task.name}</h3>
                            <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${
                              task.os_type === 'linux' ? 'bg-green-100 text-green-800' : 'bg-blue-100 text-blue-800'
                            }`}>
                              {task.os_type}
                            </span>
                          </div>
                          {task.description && (
                            <p className="text-sm text-gray-600 mt-1">{task.description}</p>
                          )}
                          <div className="mt-2 bg-gray-100 rounded p-2">
                            <code className="text-sm">{task.command}</code>
                          </div>
                        </div>
                        <button
                          onClick={() => deleteTask(task.id)}
                          disabled={loading}
                          className="text-red-600 hover:text-red-900 ml-4"
                        >
                          Delete
                        </button>
                      </div>
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
                    onChange={(e) => setSelectedTask(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    <option value="">Select a task...</option>
                    {tasks.map((task) => (
                      <option key={task.id} value={task.id}>
                        {task.name} ({task.os_type})
                      </option>
                    ))}
                  </select>
                </div>
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
                        <label htmlFor={`server-${server.id}`} className="text-sm">
                          {server.name} ({server.hostname})
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
                        {server.name} ({server.hostname})
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

        {activeTab === 'history' && (
          <div className="bg-white rounded-lg shadow">
            <div className="p-6">
              <h2 className="text-xl font-semibold mb-4">Execution History</h2>
              <div className="space-y-4">
                {executions.map((execution) => (
                  <div key={execution.id} className="border rounded-lg p-4">
                    <div className="flex justify-between items-start mb-2">
                      <div>
                        <h3 className="font-medium">{execution.command}</h3>
                        <p className="text-sm text-gray-600">
                          Server: {servers.find(s => s.id === execution.server_id)?.name || 'Unknown'}
                        </p>
                      </div>
                      <div className="text-right">
                        <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${
                          execution.status === 'success' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
                        }`}>
                          {execution.status}
                        </span>
                        <p className="text-xs text-gray-500 mt-1">
                          {new Date(execution.completed_at).toLocaleString()}
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