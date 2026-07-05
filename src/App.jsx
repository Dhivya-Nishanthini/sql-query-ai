import React, { useEffect, useMemo, useState } from 'react';
import { motion } from 'framer-motion';
import ReactMarkdown from 'react-markdown';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { FaRobot, FaCopy, FaDownload, FaMoon, FaSun, FaDatabase, FaHistory, FaSave, FaSignInAlt, FaUserPlus, FaSearch, FaTable } from 'react-icons/fa';

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api';

function App() {
  const [token, setToken] = useState(localStorage.getItem('token') || '');
  const [authMode, setAuthMode] = useState('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [user, setUser] = useState(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [theme, setTheme] = useState('dark');
  const [dbConfig, setDbConfig] = useState({ db_type: 'sqlite', host: '', port: '', database_name: '', username: '', password: '' });
  const [testResult, setTestResult] = useState('');
  const [queryResult, setQueryResult] = useState(null);
  const [savedQueries, setSavedQueries] = useState([]);
  const [history, setHistory] = useState([]);
  const [queryTitle, setQueryTitle] = useState('Saved Query');
  const [searchTerm, setSearchTerm] = useState('');
  const [schemaResult, setSchemaResult] = useState(null);
  const [schemaLoading, setSchemaLoading] = useState(false);

  useEffect(() => {
    if (token) {
      fetchUser();
      loadHistory();
    }
  }, [token]);

  const fetchUser = async () => {
    const res = await fetch(`${API_BASE}/auth/me`, { headers: { Authorization: `Bearer ${token}` } });
    if (res.ok) {
      const data = await res.json();
      setUser(data);
    }
  };

  const loadHistory = async () => {
    const res = await fetch(`${API_BASE}/chat/history`, { headers: { Authorization: `Bearer ${token}` } });
    if (res.ok) {
      const data = await res.json();
      setHistory(data.sessions || []);
      setSavedQueries(data.saved_queries || []);
    }
  };

  const handleAuth = async (e) => {
    e.preventDefault();
    const endpoint = authMode === 'login' ? '/auth/login' : '/auth/signup';
    const payload = authMode === 'login' ? { email, password } : { email, password, full_name: fullName };
    const res = await fetch(`${API_BASE}${endpoint}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (res.ok) {
      localStorage.setItem('token', data.access_token);
      setToken(data.access_token);
      setUser(data.user);
    } else {
      alert(data.detail || 'Authentication failed');
    }
  };

  const sendMessage = async () => {
    if (!input.trim()) return;
    const prompt = input;
    const newMessages = [...messages, { role: 'user', content: prompt }];
    setMessages(newMessages);
    setInput('');
    setLoading(true);
    const res = await fetch(`${API_BASE}/chat/ask`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify({ message: prompt, mode: 'chat' })
    });
    const data = await res.json();
    setLoading(false);
    if (res.ok) {
      setMessages([...newMessages, { role: 'assistant', content: data.reply }]);
      loadHistory();
    }
  };

  const testConnection = async () => {
    const res = await fetch(`${API_BASE}/connections/test`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify(dbConfig)
    });
    const data = await res.json();
    setTestResult(data.detail || JSON.stringify(data));
  };

  const executeQuery = async () => {
    const res = await fetch(`${API_BASE}/connections/execute`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify({ ...dbConfig, query: input })
    });
    const data = await res.json();
    setQueryResult(data);
    if (data.detail) {
      setTestResult(data.detail);
    }
  };

  const saveQuery = async () => {
    if (!input.trim()) return;
    const res = await fetch(`${API_BASE}/queries/save`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify({ title: queryTitle || 'Saved Query', query: input, explanation: 'Saved from SQL Genius AI' })
    });
    if (res.ok) {
      loadHistory();
      setQueryTitle('Saved Query');
    }
  };

  const inspectSchema = async () => {
    setSchemaLoading(true);
    const res = await fetch(`${API_BASE}/connections/schema`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify(dbConfig)
    });
    const data = await res.json();
    setSchemaLoading(false);
    setSchemaResult(data);
  };

  const exportChat = () => {
    const contents = messages.map((msg) => `${msg.role.toUpperCase()}: ${msg.content}`).join('\n\n');
    const blob = new Blob([contents], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'sql-chat-export.txt';
    link.click();
    URL.revokeObjectURL(url);
  };

  const exportResults = () => {
    if (!queryResult?.columns) return;
    const rows = [queryResult.columns, ...queryResult.rows].map((row) => row.join(','));
    const blob = new Blob([rows.join('\n')], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'query-results.csv';
    link.click();
    URL.revokeObjectURL(url);
  };

  const copySql = async () => {
    if (!input.trim()) return;
    try {
      await navigator.clipboard.writeText(input);
    } catch {
      // ignore clipboard errors
    }
  };

  const logout = () => {
    localStorage.removeItem('token');
    setToken('');
    setUser(null);
  };

  const filteredHistory = useMemo(() => {
    const term = searchTerm.toLowerCase();
    return history.filter((item) => item.title.toLowerCase().includes(term));
  }, [history, searchTerm]);

  const filteredSavedQueries = useMemo(() => {
    const term = searchTerm.toLowerCase();
    return savedQueries.filter((item) => item.title.toLowerCase().includes(term) || item.query.toLowerCase().includes(term));
  }, [savedQueries, searchTerm]);

  const stats = useMemo(() => ({
    queries: history.length,
    saved: savedQueries.length,
    status: 'Connected'
  }), [history.length, savedQueries.length]);

  if (!token) {
    return (
      <div className={`min-h-screen ${theme === 'dark' ? 'bg-slate-950 text-slate-100' : 'bg-slate-50 text-slate-900'}`}>
        <div className="mx-auto flex min-h-screen max-w-6xl flex-col items-center justify-center px-6 py-12">
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="w-full max-w-4xl rounded-3xl border border-slate-800 bg-slate-900/80 p-8 shadow-2xl backdrop-blur">
            <div className="mb-8 flex items-center justify-between">
              <div>
                <p className="text-sm uppercase tracking-[0.3em] text-cyan-400">SQL Genius AI</p>
                <h1 className="text-4xl font-semibold">Your production-ready SQL copilot</h1>
              </div>
              <button onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')} className="rounded-full border border-slate-700 p-3">
                {theme === 'dark' ? <FaSun /> : <FaMoon />}
              </button>
            </div>
            <div className="grid gap-8 lg:grid-cols-[1.1fr_0.9fr]">
              <div className="space-y-4">
                <p className="text-lg text-slate-300">Generate SQL, explain joins, optimize queries, detect issues, connect to SQLite/MySQL/PostgreSQL, and execute queries from one intelligent workspace.</p>
                <div className="grid gap-3 sm:grid-cols-2">
                  {['Natural language to SQL', 'Query optimization', 'Database execution', 'JWT auth'].map((feature) => (
                    <div key={feature} className="rounded-2xl border border-slate-800 bg-slate-800/70 p-4">{feature}</div>
                  ))}
                </div>
                <div className="rounded-2xl border border-cyan-800/50 bg-cyan-500/10 p-4 text-sm text-cyan-200">Demo credentials: admin@example.com / admin123</div>
              </div>
              <form onSubmit={handleAuth} className="rounded-3xl border border-slate-800 bg-slate-950/70 p-6">
                <div className="mb-4 flex gap-3">
                  <button type="button" onClick={() => setAuthMode('login')} className={`flex-1 rounded-xl px-4 py-2 ${authMode === 'login' ? 'bg-cyan-600' : 'bg-slate-800'}`}><FaSignInAlt className="mr-2 inline" />Login</button>
                  <button type="button" onClick={() => setAuthMode('signup')} className={`flex-1 rounded-xl px-4 py-2 ${authMode === 'signup' ? 'bg-cyan-600' : 'bg-slate-800'}`}><FaUserPlus className="mr-2 inline" />Signup</button>
                </div>
                {authMode === 'signup' && <input value={fullName} onChange={(e) => setFullName(e.target.value)} className="mb-3 w-full rounded-xl border border-slate-700 bg-slate-900 p-3" placeholder="Full name" />}
                <input value={email} onChange={(e) => setEmail(e.target.value)} className="mb-3 w-full rounded-xl border border-slate-700 bg-slate-900 p-3" placeholder="Email" />
                <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} className="mb-4 w-full rounded-xl border border-slate-700 bg-slate-900 p-3" placeholder="Password" />
                <button type="submit" className="w-full rounded-xl bg-cyan-600 px-4 py-3 font-semibold hover:bg-cyan-500">{authMode === 'login' ? 'Log in' : 'Create account'}</button>
              </form>
            </div>
          </motion.div>
        </div>
      </div>
    );
  }

  return (
    <div className={`min-h-screen ${theme === 'dark' ? 'bg-slate-950 text-slate-100' : 'bg-slate-50 text-slate-900'}`}>
      <div className="mx-auto flex max-w-7xl flex-col gap-6 px-4 py-6 lg:flex-row">
        <aside className="w-full rounded-3xl border border-slate-800 bg-slate-900/80 p-6 lg:w-80">
          <div className="mb-6 flex items-center justify-between">
            <div>
              <p className="text-sm uppercase tracking-[0.3em] text-cyan-400">SQL Genius</p>
              <h2 className="text-2xl font-semibold">Workspace</h2>
            </div>
            <button onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')} className="rounded-full border border-slate-700 p-2">
              {theme === 'dark' ? <FaSun /> : <FaMoon />}
            </button>
          </div>
          <div className="mb-6 space-y-3">
            <div className="rounded-2xl bg-slate-800/70 p-4">
              <div className="flex items-center gap-2 text-cyan-400"><FaDatabase /> Database Status</div>
              <div className="mt-2 text-sm text-slate-300">{stats.status}</div>
            </div>
            <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-1">
              <div className="rounded-2xl bg-slate-800/70 p-4"><div className="text-sm text-slate-400">Recent Queries</div><div className="text-xl font-semibold">{stats.queries}</div></div>
              <div className="rounded-2xl bg-slate-800/70 p-4"><div className="text-sm text-slate-400">Saved Queries</div><div className="text-xl font-semibold">{stats.saved}</div></div>
            </div>
          </div>
          <div className="mb-4 flex items-center gap-2 text-slate-300"><FaSearch /> Search</div>
          <input value={searchTerm} onChange={(e) => setSearchTerm(e.target.value)} className="mb-4 w-full rounded-xl border border-slate-700 bg-slate-950 p-2 text-sm" placeholder="Find a query or chat" />
          <div className="space-y-3">
            <div className="flex items-center gap-2 text-slate-300"><FaHistory /> Recent history</div>
            {filteredHistory.slice(0, 5).map((item) => <div key={item.id} className="rounded-xl bg-slate-800/60 p-3 text-sm text-slate-300">{item.title}</div>)}
          </div>
          <div className="mt-6 space-y-3">
            <div className="flex items-center gap-2 text-slate-300"><FaSave /> Saved queries</div>
            {filteredSavedQueries.slice(0, 5).map((item) => (
              <button key={item.id} onClick={() => { setInput(item.query); setQueryTitle(item.title); }} className="w-full rounded-xl bg-slate-800/60 p-3 text-left text-sm text-slate-300">
                <div className="font-medium">{item.title}</div>
                <div className="mt-1 truncate text-xs text-slate-400">{item.query}</div>
              </button>
            ))}
          </div>
          <button onClick={logout} className="mt-6 w-full rounded-xl bg-slate-800 px-4 py-3">Logout</button>
        </aside>

        <main className="flex-1 space-y-6">
          <section className="rounded-3xl border border-slate-800 bg-slate-900/80 p-6">
            <div className="mb-4 flex items-center justify-between">
              <div>
                <p className="text-sm uppercase tracking-[0.3em] text-cyan-400">AI SQL Assistant</p>
                <h3 className="text-2xl font-semibold">ChatGPT-like SQL copilot</h3>
              </div>
              <div className="rounded-full border border-cyan-500/30 bg-cyan-500/10 px-4 py-2 text-sm text-cyan-300">Context aware • Streaming ready</div>
            </div>
            <div className="space-y-3 rounded-2xl bg-slate-950/80 p-4">
              {messages.length === 0 && <div className="text-slate-400">Ask anything like “Explain INNER JOIN” or “Generate a query for top customers.”</div>}
              {messages.map((msg, idx) => (
                <motion.div key={idx} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className={`rounded-2xl p-4 ${msg.role === 'assistant' ? 'bg-slate-800/80' : 'bg-cyan-600/20'}`}>
                  <div className="mb-2 flex items-center gap-2 text-sm font-semibold">{msg.role === 'assistant' ? <FaRobot /> : <FaUserPlus />}{msg.role === 'assistant' ? 'SQL Genius' : 'You'}</div>
                  <ReactMarkdown components={{ code({ inline, className, children }) { return inline ? <code className={className}>{children}</code> : <SyntaxHighlighter style={vscDarkPlus} language="sql">{String(children).replace(/\n$/, '')}</SyntaxHighlighter>; } }}>{msg.content}</ReactMarkdown>
                </motion.div>
              ))}
              {loading && <div className="text-slate-400">Thinking...</div>}
            </div>
            <div className="mt-4 flex flex-col gap-3 lg:flex-row">
              <textarea value={input} onChange={(e) => setInput(e.target.value)} className="min-h-[120px] flex-1 rounded-2xl border border-slate-700 bg-slate-950 p-3" placeholder="Ask for SQL help, generation, optimization, or debugging..." />
              <div className="flex flex-col gap-2">
                <button onClick={sendMessage} className="rounded-2xl bg-cyan-600 px-4 py-3 font-semibold hover:bg-cyan-500">Send</button>
                <button onClick={copySql} className="rounded-2xl border border-slate-700 px-4 py-3"><FaCopy className="mr-2 inline" />Copy SQL</button>
                <button onClick={saveQuery} className="rounded-2xl border border-slate-700 px-4 py-3"><FaSave className="mr-2 inline" />Save</button>
              </div>
            </div>
            <div className="mt-4 flex flex-wrap items-center gap-3">
              <input value={queryTitle} onChange={(e) => setQueryTitle(e.target.value)} className="rounded-xl border border-slate-700 bg-slate-950 p-2" placeholder="Query title" />
              <button onClick={exportChat} className="rounded-xl border border-slate-700 px-3 py-2"><FaDownload className="mr-2 inline" />Export Chat</button>
            </div>
          </section>

          <section className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
            <div className="rounded-3xl border border-slate-800 bg-slate-900/80 p-6">
              <h3 className="mb-4 text-xl font-semibold">Database Connection</h3>
              <div className="grid gap-3 md:grid-cols-2">
                <select value={dbConfig.db_type} onChange={(e) => setDbConfig({ ...dbConfig, db_type: e.target.value })} className="rounded-xl border border-slate-700 bg-slate-950 p-3">
                  <option value="sqlite">SQLite</option>
                  <option value="mysql">MySQL</option>
                  <option value="postgresql">PostgreSQL</option>
                </select>
                <input value={dbConfig.host} onChange={(e) => setDbConfig({ ...dbConfig, host: e.target.value })} className="rounded-xl border border-slate-700 bg-slate-950 p-3" placeholder="Host" />
                <input value={dbConfig.port} onChange={(e) => setDbConfig({ ...dbConfig, port: e.target.value })} className="rounded-xl border border-slate-700 bg-slate-950 p-3" placeholder="Port" />
                <input value={dbConfig.database_name} onChange={(e) => setDbConfig({ ...dbConfig, database_name: e.target.value })} className="rounded-xl border border-slate-700 bg-slate-950 p-3" placeholder="Database / File" />
                <input value={dbConfig.username} onChange={(e) => setDbConfig({ ...dbConfig, username: e.target.value })} className="rounded-xl border border-slate-700 bg-slate-950 p-3" placeholder="Username" />
                <input type="password" value={dbConfig.password} onChange={(e) => setDbConfig({ ...dbConfig, password: e.target.value })} className="rounded-xl border border-slate-700 bg-slate-950 p-3" placeholder="Password" />
              </div>
              <div className="mt-4 flex flex-wrap gap-3">
                <button onClick={testConnection} className="rounded-xl bg-cyan-600 px-4 py-3">Test Connection</button>
                <button onClick={executeQuery} className="rounded-xl border border-slate-700 px-4 py-3">Execute SQL</button>
                <button onClick={inspectSchema} className="rounded-xl border border-slate-700 px-4 py-3"><FaTable className="mr-2 inline" />Inspect Schema</button>
              </div>
              {testResult && <div className="mt-4 rounded-xl border border-slate-700 bg-slate-950/80 p-3 text-sm text-slate-300">{testResult}</div>}
              {schemaLoading && <div className="mt-4 text-sm text-slate-400">Inspecting database schema…</div>}
              {schemaResult?.tables && (
                <div className="mt-4 rounded-xl border border-slate-700 bg-slate-950/80 p-4 text-sm text-slate-300">
                  <div className="mb-2 font-semibold text-cyan-300">Schema explorer</div>
                  <div className="flex flex-wrap gap-2">
                    {schemaResult.tables.map((table) => <span key={table} className="rounded-full border border-slate-700 px-3 py-1">{table}</span>)}
                  </div>
                </div>
              )}
            </div>
            <div className="rounded-3xl border border-slate-800 bg-slate-900/80 p-6">
              <div className="mb-4 flex items-center justify-between">
                <h3 className="text-xl font-semibold">Results</h3>
                {queryResult?.columns && <button onClick={exportResults} className="rounded-xl border border-slate-700 px-3 py-2"><FaDownload className="mr-2 inline" />Export CSV</button>}
              </div>
              {queryResult ? (
                <div className="overflow-auto rounded-2xl border border-slate-700 bg-slate-950/80 p-3">
                  <table className="min-w-full text-sm">
                    <thead>
                      <tr className="border-b border-slate-700 text-left">
                        {queryResult.columns?.map((col) => <th key={col} className="p-2">{col}</th>)}
                      </tr>
                    </thead>
                    <tbody>
                      {queryResult.rows?.map((row, idx) => (
                        <tr key={idx} className="border-b border-slate-800">
                          {row.map((cell, cellIdx) => <td key={`${idx}-${cellIdx}`} className="p-2">{String(cell)}</td>)}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : <div className="text-slate-400">Run a query to see professional table results.</div>}
            </div>
          </section>
        </main>
      </div>
    </div>
  );
}

export default App;
