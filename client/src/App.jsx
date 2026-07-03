import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { 
  Folder, 
  FileText, 
  Video, 
  Image as ImageIcon, 
  Music, 
  Archive, 
  File as FileIcon, 
  Search, 
  Grid, 
  List, 
  ChevronRight, 
  MoreVertical, 
  Trash2, 
  Edit3, 
  Play, 
  Shield, 
  Activity, 
  Move, 
  Check, 
  X, 
  User as UserIcon, 
  Lock, 
  Unlock, 
  RotateCcw,
  RefreshCw,
  Plus,
  ArrowUp,
  FileSpreadsheet,
  Info,
  Clipboard,
  Copy,
  ArrowUpDown
} from 'lucide-react';

const API_BASE = import.meta.env.VITE_API_URL || '';

// Compact Toast System
const Toast = ({ message, type, onClose }) => {
  useEffect(() => {
    const timer = setTimeout(onClose, 3000);
    return () => clearTimeout(timer);
  }, [onClose]);

  const bg = type === 'error' ? 'var(--danger-color, #ef4444)' : 'var(--accent-color, #22c55e)';

  return (
    <div style={{
      position: 'fixed',
      bottom: '80px',
      left: '50%',
      transform: 'translateX(-50%)',
      background: bg,
      color: '#fff',
      padding: '8px 16px',
      borderRadius: '8px',
      fontSize: '0.8rem',
      fontWeight: '600',
      boxShadow: '0 4px 12px rgba(0,0,0,0.3)',
      zIndex: 10000,
      display: 'flex',
      alignItems: 'center',
      gap: '6px'
    }}>
      {message}
    </div>
  );
};

export default function App() {
  const [currentFolderId, setCurrentFolderId] = useState('root');
  const [folderName, setFolderName] = useState('Root');
  const [folders, setFolders] = useState([]);
  const [files, setFiles] = useState([]);
  const [breadcrumbs, setBreadcrumbs] = useState([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [viewMode, setViewMode] = useState('list'); // Default ZArchiver is list
  const [sortBy, setSortBy] = useState('name'); // 'name' | 'size' | 'date' | 'type'
  const [sortOrder, setSortOrder] = useState('asc'); // 'asc' | 'desc'
  const [isSortOpen, setIsSortOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  
  // Selection states
  const [selectedItems, setSelectedItems] = useState(new Set());
  const [clipboard, setClipboard] = useState(null); // { action: 'copy' | 'move', item: { id, name, type }, sourceFolderId }

  // Active overlays
  const [toast, setToast] = useState(null);
  const [activeItem, setActiveItem] = useState(null); // Tapped item for options bottom sheet
  const [isCreateFolderOpen, setIsCreateFolderOpen] = useState(false);
  const [newFolderName, setNewFolderName] = useState('');
  const [isRenameOpen, setIsRenameOpen] = useState(false);
  const [renameValue, setRenameValue] = useState('');
  const [isPropertiesOpen, setIsPropertiesOpen] = useState(false);
  const [propertiesData, setPropertiesData] = useState(null);
  
  // Admin & Diagnostics
  const [isAdminOpen, setIsAdminOpen] = useState(false);
  const [adminTab, setAdminTab] = useState('access'); // 'access' | 'stats' | 'health'
  const [usersList, setUsersList] = useState([]);
  const [healthStatus, setHealthStatus] = useState(null);
  const [healthLoading, setHealthLoading] = useState(false);
  const [statsData, setStatsData] = useState(null);
  const [statsLoading, setStatsLoading] = useState(false);
  const [searchUserQuery, setSearchUserQuery] = useState('');
  const [allFolders, setAllFolders] = useState([]);
  const [exceptionEditorUser, setExceptionEditorUser] = useState(null); // stores user_doc_id
  const [selectedFolderForException, setSelectedFolderForException] = useState('');
  const [exceptionRuleType, setExceptionRuleType] = useState('allow'); // 'allow' | 'block'

  // Admin Settings
  const [settingsData, setSettingsData] = useState(null);
  const [settingsLoading, setSettingsLoading] = useState(false);
  const [settingsSaving, setSettingsSaving] = useState(false);
  const [botNameInput, setBotNameInput] = useState('');
  const [itemsPerPageInput, setItemsPerPageInput] = useState(15);
  const [autoDeleteHoursInput, setAutoDeleteHoursInput] = useState(1.0);
  const [protectContentInput, setProtectContentInput] = useState(true);

  // Authentication states
  const [isReady, setIsReady] = useState(false);
  const [initData, setInitData] = useState('');
  const [currentUser, setCurrentUser] = useState(null);
  const [isMockMode, setIsMockMode] = useState(false);
  const [mockRole, setMockRole] = useState('owner'); // owner | approved | guest (lowercase matches backend)

  // Haptic feedback helpers
  const triggerHaptic = useCallback((type = 'light') => {
    const tg = window.Telegram?.WebApp;
    if (tg?.HapticFeedback) {
      if (type === 'light') tg.HapticFeedback.impactOccurred('light');
      if (type === 'medium') tg.HapticFeedback.impactOccurred('medium');
      if (type === 'success') tg.HapticFeedback.notificationOccurred('success');
      if (type === 'error') tg.HapticFeedback.notificationOccurred('error');
    }
  }, []);

  const showToast = useCallback((message, type = 'info') => {
    setToast({ message, type });
    if (type === 'error') triggerHaptic('error');
    else if (type === 'success') triggerHaptic('success');
  }, [triggerHaptic]);

  // Load Telegram SDK
  useEffect(() => {
    const tg = window.Telegram?.WebApp;
    if (tg) {
      tg.ready();
      tg.expand();
      const rawInit = tg.initData || '';
      setInitData(rawInit);
      setIsMockMode(!rawInit);
    } else {
      setIsMockMode(true);
    }
    setIsReady(true);
  }, []);

  // Fetch current user role
  const fetchMe = useCallback(async () => {
    if (!isReady) return;
    try {
      const headers = {};
      if (initData) {
        headers['X-Telegram-Init-Data'] = initData;
      } else if (isMockMode) {
        setCurrentUser({
          telegram_id: 123456789,
          display_name: "Owner Account",
          role: mockRole,
          allowed_folders: [],
          blocked_folders: []
        });
        return;
      }

      const res = await fetch(`${API_BASE}/api/user/me`, { headers });
      if (!res.ok) {
        if (res.status === 403) throw new Error("Access Denied.");
        throw new Error("Failed to load user profiles.");
      }
      const data = await res.json();
      setCurrentUser({
        ...data,
        role: data.role.toLowerCase()
      });
    } catch (err) {
      setError(err.message);
      showToast(err.message, 'error');
    }
  }, [isReady, initData, isMockMode, mockRole, showToast]);

  useEffect(() => {
    fetchMe();
  }, [fetchMe]);

  // Load directory items
  const loadDirectory = useCallback(async (folderId) => {
    if (!isReady) return;
    setLoading(true);
    setError(null);
    try {
      const headers = {};
      if (initData) {
        headers['X-Telegram-Init-Data'] = initData;
      }
      
      if (isMockMode) {
        await new Promise(r => setTimeout(r, 200));
        if (folderId === 'root') {
          setFolderName('Root');
          setBreadcrumbs([]);
           setFolders([
            { id: 'f1', name: '🎥 Movies & Shows', created_at: new Date().toISOString(), created_by: 123456789, size: 2140000000 },
            { id: 'f2', name: '📚 Textbooks & E-books', created_at: new Date().toISOString(), created_by: 123456789, size: 4560000 },
            { id: 'f3', name: '🎵 Audio & Music Album', created_at: new Date().toISOString(), created_by: 123456789, size: 0 },
            { id: 'f4', name: '🛡️ Restricted Documents (Admin)', created_at: new Date().toISOString(), created_by: 123456789, size: 0 }
          ]);
          setFiles([
            { id: 'doc1', name: 'Setup_Deployment_Guide.pdf', file_type: 'document', file_size: 4560000, uploaded_at: new Date().toISOString(), mime_type: 'application/pdf' },
            { id: 'vid1', name: 'Premium_CDN_Upload_Tutorial.mp4', file_type: 'video', file_size: 2140000000, uploaded_at: new Date().toISOString(), mime_type: 'video/mp4' }
          ]);
        } else if (folderId === 'f1') {
          setFolderName('Movies & Shows');
          setBreadcrumbs([{ id: 'f1', name: '🎥 Movies & Shows' }]);
          setFolders([
            { id: 'f1_sub1', name: 'Marvel Cinematic Universe', created_at: new Date().toISOString(), size: 154000000 }
          ]);
          setFiles([
            { id: 'vid2', name: 'IronMan_4K_Trailer.mp4', file_type: 'video', file_size: 154000000, uploaded_at: new Date().toISOString() }
          ]);
        } else {
          setFolderName('Sub Folder');
          setBreadcrumbs([
            { id: 'f1', name: '🎥 Movies & Shows' },
            { id: folderId, name: 'Sub Folder' }
          ]);
          setFolders([]);
          setFiles([]);
        }
        setLoading(false);
        return;
      }

      const url = folderId && folderId !== 'root' ? `${API_BASE}/api/folders?folder_id=${folderId}` : `${API_BASE}/api/folders`;
      const res = await fetch(url, { headers });
      if (!res.ok) {
        if (res.status === 403) throw new Error("Access Denied to this directory.");
        throw new Error("Failed to load directory.");
      }
      const data = await res.json();
      setFolderName(data.folder_name);
      setBreadcrumbs(data.breadcrumbs || []);
      setFolders(data.folders || []);
      setFiles(data.files || []);
    } catch (err) {
      setError(err.message);
      showToast(err.message, 'error');
    } finally {
      setLoading(false);
    }
  }, [isReady, initData, isMockMode, showToast]);

  useEffect(() => {
    loadDirectory(currentFolderId);
  }, [currentFolderId, loadDirectory]);

  // Back button setup
  useEffect(() => {
    const tg = window.Telegram?.WebApp;
    const isBackButtonSupported = tg && tg.isVersionAtLeast && tg.isVersionAtLeast('6.1');
    if (isBackButtonSupported && tg.BackButton) {
      if (currentFolderId && currentFolderId !== 'root') {
        tg.BackButton.show();
        const handleBack = () => {
          triggerHaptic('light');
          handleNavigateUp();
        };
        tg.BackButton.onClick(handleBack);
        return () => {
          tg.BackButton.offClick(handleBack);
        };
      } else {
        tg.BackButton.hide();
      }
    }
  }, [currentFolderId, breadcrumbs, triggerHaptic]);

  // Up folder navigation
  const handleNavigateUp = () => {
    if (breadcrumbs.length > 0) {
      const parent = breadcrumbs[breadcrumbs.length - 2];
      setCurrentFolderId(parent ? parent.id : 'root');
    } else {
      setCurrentFolderId('root');
    }
  };

  // Search filtering and sorting
  const filteredFolders = useMemo(() => {
    const matched = folders.filter(f => f.name.toLowerCase().includes(searchQuery.toLowerCase()));
    return [...matched].sort((a, b) => {
      let comparison = 0;
      if (sortBy === 'name') {
        comparison = a.name.localeCompare(b.name);
      } else if (sortBy === 'size') {
        comparison = (a.size || 0) - (b.size || 0);
      } else if (sortBy === 'date') {
        comparison = new Date(a.created_at || 0) - new Date(b.created_at || 0);
      } else {
        comparison = a.name.localeCompare(b.name);
      }
      return sortOrder === 'asc' ? comparison : -comparison;
    });
  }, [folders, searchQuery, sortBy, sortOrder]);

  const filteredFiles = useMemo(() => {
    const matched = files.filter(f => f.name.toLowerCase().includes(searchQuery.toLowerCase()));
    return [...matched].sort((a, b) => {
      let comparison = 0;
      if (sortBy === 'name') {
        comparison = a.name.localeCompare(b.name);
      } else if (sortBy === 'size') {
        comparison = (a.file_size || 0) - (b.file_size || 0);
      } else if (sortBy === 'date') {
        const dateA = new Date(a.uploaded_at || a.created_at || 0);
        const dateB = new Date(b.uploaded_at || b.created_at || 0);
        comparison = dateA - dateB;
      } else if (sortBy === 'type') {
        const extA = (a.name || '').split('.').pop() || '';
        const extB = (b.name || '').split('.').pop() || '';
        comparison = extA.localeCompare(extB);
      }
      return sortOrder === 'asc' ? comparison : -comparison;
    });
  }, [files, searchQuery, sortBy, sortOrder]);

  // Folder Click Actions
  const handleFolderClick = (folder) => {
    triggerHaptic('light');
    setCurrentFolderId(folder.id);
  };

  const handleFileClick = (file) => {
    triggerHaptic('medium');
    setActiveItem({ ...file, type: 'file' });
  };

  // Deliver File API
  const handlePlayFile = async (fileId) => {
    showToast("Processing Telegram CDN delivery...", "info");
    try {
      if (isMockMode) {
        await new Promise(r => setTimeout(r, 450));
        showToast("Sent! Check your Telegram chat.", "success");
        return;
      }

      const headers = { 'Content-Type': 'application/json' };
      if (initData) headers['X-Telegram-Init-Data'] = initData;

      const res = await fetch(`${API_BASE}/api/files/play`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ file_id: fileId })
      });

      if (!res.ok) throw new Error("Delivery failed.");
      showToast("Sent to Telegram successfully!", "success");
    } catch (err) {
      showToast(err.message, 'error');
    }
  };

  // Operations CRUD
  const handleCreateFolder = async () => {
    if (!newFolderName.trim()) return;
    try {
      if (isMockMode) {
        setFolders(prev => [...prev, {
          id: `f_mock_${Date.now()}`,
          name: newFolderName.trim(),
          created_at: new Date().toISOString()
        }]);
        setIsCreateFolderOpen(false);
        setNewFolderName('');
        showToast("Folder created (Demo)", "success");
        return;
      }

      const headers = { 'Content-Type': 'application/json' };
      if (initData) headers['X-Telegram-Init-Data'] = initData;

      const res = await fetch(`${API_BASE}/api/folders/create`, {
        method: 'POST',
        headers,
        body: JSON.stringify({
          name: newFolderName.trim(),
          parent_id: currentFolderId === 'root' ? null : currentFolderId
        })
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || "Error creating folder");
      }

      setIsCreateFolderOpen(false);
      setNewFolderName('');
      showToast("Folder created successfully!", "success");
      loadDirectory(currentFolderId);
    } catch (err) {
      showToast(err.message, 'error');
    }
  };

  const handleRename = async () => {
    if (!renameValue.trim() || !activeItem) return;
    const isFolder = activeItem.type === 'folder';
    const endpoint = isFolder ? '/api/folders/rename' : '/api/files/rename';
    const body = isFolder 
      ? { folder_id: activeItem.id, new_name: renameValue.trim() }
      : { file_id: activeItem.id, new_name: renameValue.trim() };

    try {
      if (isMockMode) {
        if (isFolder) {
          setFolders(prev => prev.map(f => f.id === activeItem.id ? { ...f, name: renameValue.trim() } : f));
        } else {
          setFiles(prev => prev.map(f => f.id === activeItem.id ? { ...f, name: renameValue.trim() } : f));
        }
        setIsRenameOpen(false);
        setActiveItem(null);
        showToast("Renamed (Demo)", "success");
        return;
      }

      const headers = { 'Content-Type': 'application/json' };
      if (initData) headers['X-Telegram-Init-Data'] = initData;

      const res = await fetch(`${API_BASE}${endpoint}`, {
        method: 'POST',
        headers,
        body: JSON.stringify(body)
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || "Error renaming");
      }

      setIsRenameOpen(false);
      setActiveItem(null);
      showToast("Renamed successfully!", "success");
      loadDirectory(currentFolderId);
    } catch (err) {
      showToast(err.message, 'error');
    }
  };

  const handleDelete = async (item = activeItem) => {
    if (!item) return;
    const isFolder = item.type === 'folder';
    const endpoint = isFolder ? '/api/folders/delete' : '/api/files/delete';
    const body = isFolder ? { folder_id: item.id } : { file_id: item.id };

    if (!confirm(`Are you sure you want to delete "${item.name}"?`)) return;

    try {
      if (isMockMode) {
        if (isFolder) {
          setFolders(prev => prev.filter(f => f.id !== item.id));
        } else {
          setFiles(prev => prev.filter(f => f.id !== item.id));
        }
        setActiveItem(null);
        showToast("Deleted (Demo)", "success");
        return;
      }

      const headers = { 'Content-Type': 'application/json' };
      if (initData) headers['X-Telegram-Init-Data'] = initData;

      const res = await fetch(`${API_BASE}${endpoint}`, {
        method: 'POST',
        headers,
        body: JSON.stringify(body)
      });

      if (!res.ok) throw new Error("Delete failed.");

      setActiveItem(null);
      showToast("Deleted successfully", "success");
      loadDirectory(currentFolderId);
    } catch (err) {
      showToast(err.message, 'error');
    }
  };

  // Clipboard and Paste Operations
  const startCopyFlow = () => {
    if (!activeItem) return;
    setClipboard({
      action: 'copy',
      item: { id: activeItem.id, name: activeItem.name, type: activeItem.type },
      sourceFolderId: currentFolderId
    });
    setActiveItem(null);
    triggerHaptic('medium');
    showToast("Copied to clipboard. Navigate to destination and paste.", "info");
  };

  const startMoveFlow = () => {
    if (!activeItem) return;
    setClipboard({
      action: 'move',
      item: { id: activeItem.id, name: activeItem.name, type: activeItem.type },
      sourceFolderId: currentFolderId
    });
    setActiveItem(null);
    triggerHaptic('medium');
    showToast("Item ready to move. Navigate to destination and paste.", "info");
  };

  const executePaste = async () => {
    if (!clipboard) return;
    const targetFolderId = currentFolderId;
    const sourceFolderId = clipboard.sourceFolderId;

    if (targetFolderId === sourceFolderId) {
      showToast("Cannot paste in the same directory.", "error");
      return;
    }

    if (clipboard.item.type === 'folder') {
      if (targetFolderId === clipboard.item.id || breadcrumbs.some(c => c.id === clipboard.item.id)) {
        showToast("Cannot paste a folder inside itself or its subfolders.", "error");
        return;
      }
    }

    showToast(clipboard.action === 'move' ? "Moving item..." : "Copying item...", "info");

    try {
      if (isMockMode) {
        await new Promise(r => setTimeout(r, 450));
        if (clipboard.action === 'move') {
          if (clipboard.item.type === 'folder') {
            setFolders(prev => prev.filter(f => f.id !== clipboard.item.id));
          } else {
            setFiles(prev => prev.filter(f => f.id !== clipboard.item.id));
          }
          showToast("Moved successfully (Demo)!", "success");
        } else {
          showToast("Copied successfully (Demo)!", "success");
        }
        setClipboard(null);
        loadDirectory(currentFolderId);
        return;
      }

      const headers = { 'Content-Type': 'application/json' };
      if (initData) headers['X-Telegram-Init-Data'] = initData;

      let endpoint = "";
      let body = {};

      if (clipboard.item.type === 'folder') {
        endpoint = clipboard.action === 'move' ? '/api/folders/move' : '/api/folders/copy';
        body = {
          folder_id: clipboard.item.id,
          target_parent_id: targetFolderId === 'root' ? null : targetFolderId
        };
      } else {
        endpoint = clipboard.action === 'move' ? '/api/files/move' : '/api/files/copy';
        body = {
          file_id: clipboard.item.id,
          target_folder_id: targetFolderId === 'root' ? null : targetFolderId
        };
      }

      const res = await fetch(`${API_BASE}${endpoint}`, {
        method: 'POST',
        headers,
        body: JSON.stringify(body)
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || "Operation failed.");
      }

      showToast(clipboard.action === 'move' ? "Moved successfully!" : "Copied successfully!", "success");
      setClipboard(null);
      loadDirectory(currentFolderId);
    } catch (err) {
      showToast(err.message, 'error');
    }
  };

  const isPasteDisabled = useMemo(() => {
    if (!clipboard) return false;
    if (currentFolderId === clipboard.sourceFolderId) return true;
    if (clipboard.item.type === 'folder') {
      if (currentFolderId === clipboard.item.id) return true;
      if (breadcrumbs.some(c => c.id === clipboard.item.id)) return true;
    }
    return false;
  }, [clipboard, currentFolderId, breadcrumbs]);

  const handleShowProperties = async (item) => {
    if (!item) return;
    triggerHaptic('light');
    setActiveItem(null);

    if (item.type === 'folder') {
      try {
        if (isMockMode) {
          setPropertiesData({
            name: item.name,
            type: 'Folder',
            id: item.id,
            size: 1557118976, // 1.45 GB
            files_count: 12,
            folders_count: 3
          });
          setIsPropertiesOpen(true);
          return;
        }

        showToast("Calculating folder size...", "info");
        const headers = {};
        if (initData) headers['X-Telegram-Init-Data'] = initData;

        const res = await fetch(`${API_BASE}/api/folders/size?folder_id=${item.id}`, { headers });
        if (!res.ok) throw new Error("Failed to fetch folder properties.");
        const stats = await res.json();
        
        setToast(null);
        setPropertiesData({
          name: item.name,
          type: 'Folder',
          id: item.id,
          size: stats.size,
          files_count: stats.files_count,
          folders_count: stats.folders_count
        });
        setIsPropertiesOpen(true);
      } catch (err) {
        setToast(null);
        showToast(err.message, 'error');
      }
    } else {
      setPropertiesData({
        name: item.name,
        type: `File (${item.file_type || 'generic'})`,
        id: item.id,
        size: item.file_size,
        uploaded_at: item.uploaded_at || item.created_at,
        mime_type: item.mime_type
      });
      setIsPropertiesOpen(true);
    }
  };

  // Dynamic Drive stats
  const loadStats = async () => {
    setStatsLoading(true);
    try {
      if (isMockMode) {
        await new Promise(r => setTimeout(r, 400));
        setStatsData({
          folders_count: 8,
          files_count: 42,
          total_size: 2684354560, // 2.5 GB
          file_types: {
            video: { count: 32, size: 2469605888 },
            document: { count: 8, size: 214748364 },
            photo: { count: 2, size: 3000308 }
          },
          users: {
            total: 15,
            approved: 10,
            guest: 4,
            owner: 1
          }
        });
        return;
      }

      const headers = {};
      if (initData) headers['X-Telegram-Init-Data'] = initData;

      const res = await fetch(`${API_BASE}/api/admin/stats`, { headers });
      if (!res.ok) throw new Error("Failed to load statistics.");
      const data = await res.json();
      setStatsData(data);
    } catch (err) {
      showToast(err.message, 'error');
    } finally {
      setStatsLoading(false);
    }
  };

  useEffect(() => {
    if (isAdminOpen && adminTab === 'stats') {
      loadStats();
    }
  }, [isAdminOpen, adminTab]);

  // Admin whitelist controls
  const loadAdminUsers = async () => {
    try {
      const headers = {};
      if (initData) headers['X-Telegram-Init-Data'] = initData;

      if (isMockMode) {
        setUsersList([
          { user_doc_id: 'u1', display_name: "John Doe", username: "johndoe", role: "approved", allowed_folders: [], blocked_folders: [] }
        ]);
        return;
      }

      const res = await fetch(`${API_BASE}/api/admin/users`, { headers });
      if (!res.ok) throw new Error("Failed to load user directory.");
      const data = await res.json();
      setUsersList(data);
    } catch (err) {
      showToast(err.message, 'error');
    }
  };

  const runHealthCheck = async () => {
    setHealthLoading(true);
    setHealthStatus(null);
    try {
      if (isMockMode) {
        await new Promise(r => setTimeout(r, 800));
        setHealthStatus({
          total: 50,
          active: 46,
          legacy: 1,
          broken: [
            { id: 'b_mock_1', name: 'Premium_CDN_Tutorial_Corrupt.mp4', folder_path: '🎥 Movies & Shows' },
            { id: 'b_mock_2', name: 'Whitelisted_Leak_Document.pdf', folder_path: '🛡️ Restricted Documents (Admin)' }
          ]
        });
        showToast("Diagnostics complete (Demo)", "success");
        return;
      }

      const headers = {};
      if (initData) headers['X-Telegram-Init-Data'] = initData;

      const res = await fetch(`${API_BASE}/api/admin/health-check`, {
        method: 'POST',
        headers
      });

      if (!res.ok) throw new Error("Health check failed.");
      const data = await res.json();
      setHealthStatus(data);
      showToast("Health Check completed!", "success");
    } catch (err) {
      showToast(err.message, 'error');
    } finally {
      setHealthLoading(false);
    }
  };

  const handleToggleException = async (userDocId, folderId, type) => {
    const endpoint = type === 'allow' 
      ? '/api/admin/users/exceptions/allow' 
      : type === 'block' 
        ? '/api/admin/users/exceptions/block' 
        : '/api/admin/users/exceptions/reset';
        
    const body = type === 'reset' ? { user_doc_id: userDocId } : { user_doc_id: userDocId, folder_id: folderId };

    try {
      if (isMockMode) {
        setUsersList(prev => prev.map(u => {
          if (u.user_doc_id !== userDocId) return u;
          let allowed = [...u.allowed_folders];
          let blocked = [...u.blocked_folders];
          if (type === 'allow') {
            allowed.push({ id: folderId || 'f1', name: "Allowed Exception" });
            blocked = blocked.filter(f => f.id !== folderId);
          } else if (type === 'block') {
            blocked.push({ id: folderId || 'f1', name: "Blocked Exception" });
            allowed = allowed.filter(f => f.id !== folderId);
          } else {
            allowed = [];
            blocked = [];
          }
          return { ...u, allowed_folders: allowed, blocked_folders: blocked };
        }));
        showToast("Rules updated!", "success");
        return;
      }

      const headers = { 'Content-Type': 'application/json' };
      if (initData) headers['X-Telegram-Init-Data'] = initData;

      const res = await fetch(`${API_BASE}${endpoint}`, {
        method: 'POST',
        headers,
        body: JSON.stringify(body)
      });

      if (!res.ok) throw new Error("Exception update failed.");
      showToast("Exception configured successfully!", "success");
      loadAdminUsers();
    } catch (err) {
      showToast(err.message, 'error');
    }
  };

  const loadAllFolders = async () => {
    try {
      const headers = {};
      if (initData) headers['X-Telegram-Init-Data'] = initData;

      if (isMockMode) {
        setAllFolders([
          { id: 'f1', name: '🎥 Movies & Shows' },
          { id: 'f2', name: '📚 Textbooks & E-books' },
          { id: 'f3', name: '🎵 Audio & Music Album' },
          { id: 'f4', name: '🛡️ Restricted Documents (Admin)' }
        ]);
        return;
      }

      const res = await fetch(`${API_BASE}/api/admin/folders/all`, { headers });
      if (!res.ok) throw new Error("Failed to load folder indexes.");
      const data = await res.json();
      setAllFolders(data);
    } catch (err) {
      showToast(err.message, 'error');
    }
  };

  const handleRemoveException = async (userDocId, folderId) => {
    try {
      if (isMockMode) {
        setUsersList(prev => prev.map(u => {
          if (u.user_doc_id !== userDocId) return u;
          return {
            ...u,
            allowed_folders: u.allowed_folders.filter(f => f.id !== folderId),
            blocked_folders: u.blocked_folders.filter(f => f.id !== folderId)
          };
        }));
        showToast("Exception removed (Demo)", "success");
        return;
      }

      const headers = { 'Content-Type': 'application/json' };
      if (initData) headers['X-Telegram-Init-Data'] = initData;

      const res = await fetch(`${API_BASE}/api/admin/users/exceptions/remove`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ user_doc_id: userDocId, folder_id: folderId })
      });

      if (!res.ok) throw new Error("Failed to remove exception rule.");
      showToast("Exception rule removed", "success");
      loadAdminUsers();
    } catch (err) {
      showToast(err.message, 'error');
    }
  };

  const handleAddException = async () => {
    if (!exceptionEditorUser || !selectedFolderForException) return;
    const userDocId = exceptionEditorUser;
    const folderId = selectedFolderForException;
    const type = exceptionRuleType;

    const endpoint = type === 'allow' 
      ? '/api/admin/users/exceptions/allow' 
      : '/api/admin/users/exceptions/block';

    try {
      if (isMockMode) {
        const folderObj = allFolders.find(f => f.id === folderId) || { id: folderId, name: "Folder Exception" };
        setUsersList(prev => prev.map(u => {
          if (u.user_doc_id !== userDocId) return u;
          let allowed = [...u.allowed_folders];
          let blocked = [...u.blocked_folders];
          if (type === 'allow') {
            if (!allowed.some(f => f.id === folderId)) allowed.push(folderObj);
            blocked = blocked.filter(f => f.id !== folderId);
          } else {
            if (!blocked.some(f => f.id === folderId)) blocked.push(folderObj);
            allowed = allowed.filter(f => f.id !== folderId);
          }
          return { ...u, allowed_folders: allowed, blocked_folders: blocked };
        }));
        setExceptionEditorUser(null);
        setSelectedFolderForException('');
        showToast("Exception added (Demo)", "success");
        return;
      }

      const headers = { 'Content-Type': 'application/json' };
      if (initData) headers['X-Telegram-Init-Data'] = initData;

      const res = await fetch(`${API_BASE}${endpoint}`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ user_doc_id: userDocId, folder_id: folderId })
      });

      if (!res.ok) throw new Error("Failed to add folder exception.");
      setExceptionEditorUser(null);
      setSelectedFolderForException('');
      showToast("Exception rule added successfully!", "success");
      loadAdminUsers();
    } catch (err) {
      showToast(err.message, 'error');
    }
  };

  const handleApproveUser = async (userDocId) => {
    try {
      if (isMockMode) {
        setUsersList(prev => prev.map(u => u.user_doc_id === userDocId ? { ...u, role: 'approved' } : u));
        showToast("User approved (Demo)", "success");
        return;
      }

      const headers = { 'Content-Type': 'application/json' };
      if (initData) headers['X-Telegram-Init-Data'] = initData;

      const res = await fetch(`${API_BASE}/api/admin/users/approve`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ user_doc_id: userDocId })
      });

      if (!res.ok) throw new Error("Approval failed.");
      showToast("User approved successfully!", "success");
      loadAdminUsers();
    } catch (err) {
      showToast(err.message, 'error');
    }
  };

  const handleRevokeUser = async (userDocId) => {
    try {
      if (isMockMode) {
        setUsersList(prev => prev.map(u => u.user_doc_id === userDocId ? { ...u, role: 'guest' } : u));
        showToast("Access revoked (Demo)", "success");
        return;
      }

      const headers = { 'Content-Type': 'application/json' };
      if (initData) headers['X-Telegram-Init-Data'] = initData;

      const res = await fetch(`${API_BASE}/api/admin/users/revoke`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ user_doc_id: userDocId })
      });

      if (!res.ok) throw new Error("Revocation failed.");
      showToast("Access revoked successfully", "success");
      loadAdminUsers();
    } catch (err) {
      showToast(err.message, 'error');
    }
  };

  const handleTogglePermission = async (userDocId, permName, value) => {
    try {
      triggerHaptic('light');
      const u = usersList.find(x => x.user_doc_id === userDocId);
      if (!u) return;

      const payload = {
        user_doc_id: userDocId,
        can_upload: u.can_upload ?? false,
        can_create_folder: u.can_create_folder ?? false,
        can_rename: u.can_rename ?? false,
        can_delete: u.can_delete ?? false,
        can_move_copy: u.can_move_copy ?? false,
      };
      
      payload[permName] = value;

      if (isMockMode) {
        setUsersList(prev => prev.map(item => {
          if (item.user_doc_id === userDocId) {
            return { ...item, [permName]: value };
          }
          return item;
        }));
        showToast('Permissions updated (Demo).', 'success');
        return;
      }

      const headers = { 'Content-Type': 'application/json' };
      if (initData) headers['X-Telegram-Init-Data'] = initData;

      const res = await fetch(`${API_BASE}/api/admin/users/permissions`, {
        method: 'POST',
        headers,
        body: JSON.stringify(payload)
      });
      
      if (!res.ok) {
        throw new Error('Failed to update permissions');
      }
      
      setUsersList(prev => prev.map(item => {
        if (item.user_doc_id === userDocId) {
          return { ...item, [permName]: value };
        }
        return item;
      }));
      showToast('Permissions updated.', 'success');
    } catch (err) {
      console.error(err);
      showToast(err.message, 'error');
    }
  };

  const handlePurgeBroken = async (fileIds) => {
    if (!fileIds || fileIds.length === 0) return;
    try {
      if (isMockMode) {
        setHealthStatus(prev => {
          if (!prev) return null;
          const newBroken = prev.broken.filter(f => !fileIds.includes(f.id));
          return {
            ...prev,
            total: prev.total - fileIds.length,
            broken: newBroken
          };
        });
        showToast("Broken references purged (Demo)", "success");
        return;
      }

      const headers = { 'Content-Type': 'application/json' };
      if (initData) headers['X-Telegram-Init-Data'] = initData;

      const res = await fetch(`${API_BASE}/api/admin/purge-broken`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ file_ids: fileIds })
      });

      showToast(`Purged ${data.purged_count} broken reference(s)!`, "success");
      runHealthCheck();
    } catch (err) {
      showToast(err.message, 'error');
    }
  };

  const loadSettings = async () => {
    setSettingsLoading(true);
    try {
      if (isMockMode) {
        await new Promise(r => setTimeout(r, 400));
        const mockData = {
          settings: {
            protect_content: true,
            items_per_page: 15,
            bot_name: "Cloud Bot (Mock)",
            auto_delete_hours: 1.0
          },
          defaults: {
            protect_content: true,
            items_per_page: 15,
            bot_name: "",
            auto_delete_hours: 1.0
          },
          overrides: {
            protect_content: false,
            items_per_page: false,
            bot_name: true,
            auto_delete_hours: false
          }
        };
        setSettingsData(mockData);
        setBotNameInput(mockData.settings.bot_name || '');
        setItemsPerPageInput(mockData.settings.items_per_page);
        setAutoDeleteHoursInput(mockData.settings.auto_delete_hours);
        setProtectContentInput(mockData.settings.protect_content);
        return;
      }

      const headers = {};
      if (initData) headers['X-Telegram-Init-Data'] = initData;

      const res = await fetch(`${API_BASE}/api/admin/settings`, { headers });
      if (!res.ok) throw new Error("Failed to load settings.");
      const data = await res.json();
      setSettingsData(data);
      setBotNameInput(data.settings.bot_name || '');
      setItemsPerPageInput(data.settings.items_per_page);
      setAutoDeleteHoursInput(data.settings.auto_delete_hours);
      setProtectContentInput(data.settings.protect_content);
    } catch (err) {
      showToast(err.message, 'error');
    } finally {
      setSettingsLoading(false);
    }
  };

  const handleSaveSettings = async (fieldToSave = null, valueToSave = null) => {
    triggerHaptic('medium');
    setSettingsSaving(true);
    try {
      let body = {};
      if (fieldToSave) {
        body[fieldToSave] = valueToSave;
      } else {
        const itemsVal = parseInt(itemsPerPageInput, 10);
        if (isNaN(itemsVal) || itemsVal < 1 || itemsVal > 100) {
          throw new Error("Items per page must be a number between 1 and 100");
        }
        const hoursVal = parseFloat(autoDeleteHoursInput);
        if (isNaN(hoursVal) || hoursVal < 0 || hoursVal > 720) {
          throw new Error("Auto delete hours must be a number between 0 and 720");
        }
        
        body = {
          bot_name: botNameInput.trim() || null,
          items_per_page: itemsVal,
          auto_delete_hours: hoursVal,
          protect_content: protectContentInput
        };
      }

      if (isMockMode) {
        await new Promise(r => setTimeout(r, 400));
        setSettingsData(prev => {
          if (!prev) return null;
          const newSettings = { ...prev.settings, ...body };
          const newOverrides = { ...prev.overrides };
          Object.keys(body).forEach(k => {
            newOverrides[k] = body[k] !== null;
          });
          return {
            ...prev,
            settings: newSettings,
            overrides: newOverrides
          };
        });
        showToast("Settings saved successfully (Demo)", "success");
        return;
      }

      const headers = { 'Content-Type': 'application/json' };
      if (initData) headers['X-Telegram-Init-Data'] = initData;

      const res = await fetch(`${API_BASE}/api/admin/settings`, {
        method: 'POST',
        headers,
        body: JSON.stringify(body)
      });

      if (!res.ok) {
        const errorData = await res.json();
        throw new Error(errorData.detail || "Failed to update settings.");
      }
      
      const data = await res.json();
      setSettingsData(data);
      setBotNameInput(data.settings.bot_name || '');
      setItemsPerPageInput(data.settings.items_per_page);
      setAutoDeleteHoursInput(data.settings.auto_delete_hours);
      setProtectContentInput(data.settings.protect_content);
      
      showToast("Settings saved successfully!", "success");
    } catch (err) {
      showToast(err.message, 'error');
    } finally {
      setSettingsSaving(false);
    }
  };

  useEffect(() => {
    if (isAdminOpen && adminTab === 'settings') {
      loadSettings();
    }
  }, [isAdminOpen, adminTab]);

  const formatBytes = (bytes, decimals = 2) => {
    if (!bytes) return '0 Bytes';
    const k = 1024;
    const dm = decimals < 0 ? 0 : decimals;
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
  };

  // Get compact ZArchiver color icon based on type
  const getFileIcon = (file) => {
    const name = (file.name || '').toLowerCase();
    if (file.file_type === 'video' || name.endsWith('.mp4') || name.endsWith('.mkv')) {
      return <Video size={16} style={{ color: '#38bdf8' }} />;
    }
    if (name.endsWith('.pdf')) {
      return <FileText size={16} style={{ color: '#f87171' }} />;
    }
    if (name.endsWith('.xls') || name.endsWith('.xlsx')) {
      return <FileSpreadsheet size={16} style={{ color: '#34d399' }} />;
    }
    if (name.endsWith('.png') || name.endsWith('.jpg') || name.endsWith('.jpeg')) {
      return <ImageIcon size={16} style={{ color: '#fb7185' }} />;
    }
    if (name.endsWith('.zip') || name.endsWith('.rar') || name.endsWith('.7z')) {
      return <Archive size={16} style={{ color: '#fbbf24' }} />;
    }
    return <FileIcon size={16} style={{ color: '#9ca3af' }} />;
  };

  const isMockBypass = new URLSearchParams(window.location.search).get('mock') === 'true';

  if (!isReady) {
    return (
      <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', backgroundColor: 'var(--bg-color, #17212b)', color: 'var(--text-color, #f5f5f5)' }}>
        <RefreshCw className="animate-spin" size={24} style={{ color: 'var(--accent-color, #22c55e)' }} />
      </div>
    );
  }

  if (!initData && !isMockBypass) {
    return (
      <div style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: '#17212b',
        color: '#f5f5f5',
        padding: '24px',
        fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif'
      }}>
        <div style={{
          maxWidth: '380px',
          width: '100%',
          backgroundColor: '#202b36',
          border: '1px solid rgba(255,255,255,0.08)',
          borderRadius: '16px',
          padding: '32px 24px',
          textAlign: 'center',
          boxShadow: '0 8px 30px rgba(0,0,0,0.35)',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: '16px'
        }}>
          <div style={{
            width: '64px',
            height: '64px',
            borderRadius: '50%',
            backgroundColor: 'rgba(239, 68, 68, 0.1)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#ef4444',
            marginBottom: '8px'
          }}>
            <Lock size={32} />
          </div>
          
          <h2 style={{ fontSize: '1.3rem', fontWeight: '800', margin: 0 }}>403 Forbidden</h2>
          <h3 style={{ fontSize: '0.95rem', fontWeight: '600', color: '#ef4444', margin: 0 }}>Access Denied</h3>
          
          <p style={{ fontSize: '0.8rem', color: '#708499', lineHeight: '1.5', margin: '8px 0' }}>
            This application is cryptographically secured and can only be accessed from within the official Telegram Messenger client.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      {/* Toast notifications */}
      {toast && <Toast message={toast.message} type={toast.type} onClose={() => setToast(null)} />}

      {/* ── 1. ZArchiver Clean Header Bar ───────────────────────────────── */}
      <header className="z-header">
        <div className="z-header-left">
          {currentFolderId !== 'root' && (
            <button 
              style={{ background: 'none', border: 'none', color: 'var(--text-color)', cursor: 'pointer', padding: '4px' }}
              onClick={handleNavigateUp}
              aria-label="Navigate up"
              title="Navigate up"
            >
              <ArrowUp size={20} />
            </button>
          )}
          <span className="z-title">
            {currentFolderId === 'root' ? 'Root' : folderName}
          </span>
        </div>

        <div className="z-header-right">
          <button 
            style={{ background: 'none', border: 'none', color: 'var(--text-color)', cursor: 'pointer', padding: '6px' }}
            onClick={() => { triggerHaptic('light'); setIsSortOpen(true); }}
            aria-label="Sort options"
            title="Sort options"
          >
            <ArrowUpDown size={18} />
          </button>
          <button 
            style={{ background: 'none', border: 'none', color: 'var(--text-color)', cursor: 'pointer', padding: '6px' }}
            onClick={() => setViewMode(viewMode === 'grid' ? 'list' : 'grid')}
            aria-label={viewMode === 'grid' ? "Switch to list view" : "Switch to grid view"}
            title={viewMode === 'grid' ? "List view" : "Grid view"}
          >
            {viewMode === 'grid' ? <List size={18} /> : <Grid size={18} />}
          </button>
          {currentUser?.role?.toLowerCase() === 'owner' && (
            <button 
              style={{ background: 'none', border: 'none', color: 'var(--text-color)', cursor: 'pointer', padding: '6px' }}
              onClick={() => { triggerHaptic('light'); setIsAdminOpen(!isAdminOpen); if(!isAdminOpen) { loadAdminUsers(); loadAllFolders(); } }}
              aria-label="Admin dashboard"
              title="Admin dashboard"
            >
              <Shield size={18} />
            </button>
          )}
        </div>
      </header>

      {/* Mock Role Switcher for local browser testing */}
      {isMockMode && (
        <div style={{ display: 'flex', gap: '8px', padding: '6px 12px', background: 'var(--secondary-bg-color)', borderBottom: '1px solid var(--border-color)', fontSize: '0.75rem' }}>
          <span style={{ color: 'var(--warning-color)', fontWeight: 600 }}>Mock Role:</span>
          <span className="z-path-item" style={{ textDecoration: 'underline' }} onClick={() => { setMockRole('owner'); fetchMe(); }}>Owner</span> | 
          <span className="z-path-item" style={{ textDecoration: 'underline' }} onClick={() => { setMockRole('approved'); fetchMe(); }}>Approved</span> | 
          <span className="z-path-item" style={{ textDecoration: 'underline' }} onClick={() => { setMockRole('guest'); fetchMe(); }}>Guest</span>
        </div>
      )}

      {/* ── 2. Clickable Pathchain (Breadcrumbs) ───────────────────────── */}
      <div className="z-path-bar">
        <span className={`z-path-item ${currentFolderId === 'root' ? 'active' : ''}`} onClick={() => setCurrentFolderId('root')}>Root</span>
        {breadcrumbs.map((c, idx) => (
          <React.Fragment key={c.id}>
            <ChevronRight size={10} style={{ opacity: 0.5 }} />
            <span className={`z-path-item ${idx === breadcrumbs.length - 1 ? 'active' : ''}`} onClick={() => setCurrentFolderId(c.id)}>
              {c.name}
            </span>
          </React.Fragment>
        ))}
      </div>

      {/* ── 3. Search Bar ─────────────────────────────────────────────── */}
      <div className="z-search-container">
        <div className="z-search-box">
          <Search size={14} style={{ color: 'var(--hint-color)' }} />
          <input 
            type="text" 
            placeholder="Search folders and files..."
            className="z-search-input"
            aria-label="Search folders and files"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
          {searchQuery && (
            <button
              style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--hint-color)' }}
              onClick={() => setSearchQuery('')}
              aria-label="Clear search"
              title="Clear search"
            >
              <X size={14} />
            </button>
          )}
        </div>
      </div>

      {/* ── 4. Folders and Files Explorer List ───────────────────────── */}
      <div className={`z-list ${viewMode === 'grid' ? 'z-grid-view' : 'z-list-view'}`}>
        {loading ? (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '200px', gap: '8px' }}>
            <RefreshCw className="animate-spin" size={24} style={{ color: 'var(--accent-color)' }} />
            <span style={{ fontSize: '0.75rem', color: 'var(--hint-color)' }}>Loading paths...</span>
          </div>
        ) : filteredFolders.length === 0 && filteredFiles.length === 0 ? (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '200px', opacity: 0.5 }}>
            <Folder size={36} style={{ strokeWidth: 1.5, color: 'var(--hint-color)' }} />
            <span style={{ fontSize: '0.8rem', marginTop: '8px' }}>This folder is empty</span>
          </div>
        ) : (
          <>
            {/* Directories Row */}
            {filteredFolders.map(folder => (
              <div 
                key={folder.id} 
                className="z-item"
                onClick={() => handleFolderClick(folder)}
              >
                <div className="z-item-left">
                  <div className="z-icon-container" style={{ color: '#fbbf24' }}>
                    <Folder size={18} fill="#fbbf24" />
                  </div>
                  <div className="z-item-meta">
                    <span className="z-item-name">{folder.name}</span>
                    <span className="z-item-desc">
                      {folder.item_count !== undefined ? (folder.item_count === 0 ? 'Empty \u2022 ' : `${folder.item_count} item${folder.item_count !== 1 ? 's' : ''} \u2022 `) : ''}{formatBytes(folder.size || 0)} &bull; {new Date(folder.created_at).toLocaleDateString()}
                    </span>
                  </div>
                </div>
                
                <div className="z-item-actions" onClick={(e) => e.stopPropagation()}>
                  <button 
                    className="z-action-btn"
                    onClick={() => { triggerHaptic('light'); setActiveItem({ ...folder, type: 'folder' }); }}
                    aria-label={`Options for folder ${folder.name}`}
                    title="Folder options"
                  >
                    <MoreVertical size={16} />
                  </button>
                </div>
              </div>
            ))}

            {/* Files Row */}
            {filteredFiles.map(file => (
              <div 
                key={file.id} 
                className="z-item"
                onClick={() => handleFileClick(file)}
              >
                <div className="z-item-left">
                  <div className="z-icon-container">
                    {getFileIcon(file)}
                  </div>
                  <div className="z-item-meta">
                    <span className="z-item-name">{file.name}</span>
                    <span className="z-item-desc">
                      {formatBytes(file.file_size)} &bull; {new Date(file.uploaded_at || file.created_at).toLocaleDateString()}
                    </span>
                  </div>
                </div>

                <div className="z-item-actions has-play" onClick={(e) => e.stopPropagation()}>
                  <button 
                    className="z-action-btn play-btn"
                    onClick={() => handlePlayFile(file.id)}
                    aria-label={`Play file ${file.name}`}
                    title="Play file"
                  >
                    <Play size={14} fill="var(--success-color)" />
                  </button>
                  <button 
                    className="z-action-btn"
                    onClick={() => { triggerHaptic('light'); setActiveItem({ ...file, type: 'file' }); }}
                    aria-label={`Options for file ${file.name}`}
                    title="File options"
                  >
                    <MoreVertical size={16} />
                  </button>
                </div>
              </div>
            ))}
          </>
        )}
      </div>

      {/* ── 5. ZArchiver Round FAB Button with Paste Toggle ────────────────── */}
      {((currentUser?.role?.toLowerCase() === 'owner') || 
        (clipboard ? currentUser?.can_move_copy : currentUser?.can_create_folder)) && (
        <>
          {clipboard ? (
            <div style={{ position: 'fixed', bottom: '24px', right: '24px', display: 'flex', flexDirection: 'column', gap: '12px', alignItems: 'center', zIndex: 200 }}>
              {/* Cancel Button */}
              <button 
                className="z-fab" 
                style={{ 
                  position: 'static', 
                  backgroundColor: 'var(--danger-color, #ef4444)', 
                  width: '40px', 
                  height: '40px', 
                  boxShadow: '0 2px 8px rgba(0,0,0,0.3)' 
                }} 
                onClick={() => { triggerHaptic('light'); setClipboard(null); }}
                aria-label="Cancel paste operation"
                title="Cancel paste operation"
              >
                <X size={18} />
              </button>

              {/* Paste Button */}
              <button 
                className="z-fab" 
                style={{ 
                  position: 'static', 
                  backgroundColor: isPasteDisabled ? 'var(--hint-color, #708499)' : 'var(--accent-color, #22c55e)',
                  opacity: isPasteDisabled ? 0.6 : 1,
                  cursor: isPasteDisabled ? 'not-allowed' : 'pointer'
                }} 
                onClick={() => { 
                  if (isPasteDisabled) {
                    triggerHaptic('error');
                    showToast("Cannot paste in this location", "error");
                  } else {
                    triggerHaptic('medium');
                    executePaste(); 
                  }
                }}
                aria-label="Paste clipboard item"
                title={isPasteDisabled ? "Cannot paste here" : "Paste clipboard item"}
                aria-disabled={isPasteDisabled}
              >
                <Clipboard size={22} />
              </button>
            </div>
          ) : (
            <button
              className="z-fab"
              onClick={() => { triggerHaptic('medium'); setIsCreateFolderOpen(true); }}
              aria-label="Create new folder"
              title="Create new folder"
            >
              <Plus size={24} />
            </button>
          )}
        </>
      )}

      {/* ── Sorting bottom sheet dialog ─────────────────────────── */}
      {isSortOpen && (
        <div className="z-bottom-sheet-overlay" onClick={() => setIsSortOpen(false)}>
          <div className="z-bottom-sheet" onClick={(e) => e.stopPropagation()}>
            <div className="sheet-handle"></div>
            <div className="z-sheet-title" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span>Sorting</span>
              <button 
                style={{ background: 'none', border: 'none', color: 'var(--hint-color)', cursor: 'pointer', padding: '4px' }}
                onClick={() => setIsSortOpen(false)}
                aria-label="Close sort options"
                title="Close"
              >
                <X size={18} />
              </button>
            </div>
            
            <div style={{ padding: '0 8px 12px 8px' }}>
              <span style={{ fontSize: '0.7rem', color: 'var(--hint-color)', fontWeight: 'bold', display: 'block', marginBottom: '8px', letterSpacing: '0.05em' }}>SORT BY</span>
              <div className="menu-options" style={{ display: 'flex', flexDirection: 'column', gap: '4px', marginBottom: '16px' }}>
                <button 
                  className={`z-sheet-option ${sortBy === 'name' ? 'active' : ''}`} 
                  onClick={() => { triggerHaptic('light'); setSortBy('name'); }}
                  style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}
                >
                  <span>Name</span>
                  {sortBy === 'name' && <Check size={16} style={{ color: 'var(--accent-color)' }} />}
                </button>
                <button 
                  className={`z-sheet-option ${sortBy === 'size' ? 'active' : ''}`} 
                  onClick={() => { triggerHaptic('light'); setSortBy('size'); }}
                  style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}
                >
                  <span>Size</span>
                  {sortBy === 'size' && <Check size={16} style={{ color: 'var(--accent-color)' }} />}
                </button>
                <button 
                  className={`z-sheet-option ${sortBy === 'date' ? 'active' : ''}`} 
                  onClick={() => { triggerHaptic('light'); setSortBy('date'); }}
                  style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}
                >
                  <span>Date</span>
                  {sortBy === 'date' && <Check size={16} style={{ color: 'var(--accent-color)' }} />}
                </button>
                <button 
                  className={`z-sheet-option ${sortBy === 'type' ? 'active' : ''}`} 
                  onClick={() => { triggerHaptic('light'); setSortBy('type'); }}
                  style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}
                >
                  <span>File type</span>
                  {sortBy === 'type' && <Check size={16} style={{ color: 'var(--accent-color)' }} />}
                </button>
              </div>

              <span style={{ fontSize: '0.7rem', color: 'var(--hint-color)', fontWeight: 'bold', display: 'block', marginBottom: '8px', letterSpacing: '0.05em' }}>ORDER</span>
              <div className="menu-options" style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                <button 
                  className={`z-sheet-option ${sortOrder === 'asc' ? 'active' : ''}`} 
                  onClick={() => { triggerHaptic('light'); setSortOrder('asc'); }}
                  style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}
                >
                  <span>Ascending</span>
                  {sortOrder === 'asc' && <Check size={16} style={{ color: 'var(--accent-color)' }} />}
                </button>
                <button 
                  className={`z-sheet-option ${sortOrder === 'desc' ? 'active' : ''}`} 
                  onClick={() => { triggerHaptic('light'); setSortOrder('desc'); }}
                  style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}
                >
                  <span>Descending</span>
                  {sortOrder === 'desc' && <Check size={16} style={{ color: 'var(--accent-color)' }} />}
                </button>
              </div>
            </div>

            <button 
              className="z-sheet-option" 
              onClick={() => setIsSortOpen(false)} 
              style={{ marginTop: '8px', justifyContent: 'center', background: 'rgba(255,255,255,0.03)', fontWeight: '600' }}
            >
              Close
            </button>
          </div>
        </div>
      )}

      {/* ── 6. Bottom sheet Dialog Options ─────────────────────────── */}
      {activeItem && (
        <div className="z-bottom-sheet-overlay" onClick={() => setActiveItem(null)}>
          <div className="z-bottom-sheet" onClick={(e) => e.stopPropagation()}>
            <div className="sheet-handle"></div>
            <div className="z-sheet-title">{activeItem.name}</div>
            
            <div className="menu-options">
              {activeItem.type === 'file' && (
                <button className="z-sheet-option" onClick={() => { handlePlayFile(activeItem.id); setActiveItem(null); }}>
                  <Play size={16} style={{ color: 'var(--success-color)' }} />
                  <span>Send to Private Telegram Chat</span>
                </button>
              )}
              
              <button className="z-sheet-option" onClick={() => handleShowProperties(activeItem)}>
                <Info size={16} />
                <span>Properties</span>
              </button>

              {((currentUser?.role?.toLowerCase() === 'owner') || currentUser?.can_rename) && (
                <button className="z-sheet-option" onClick={() => { setIsRenameOpen(true); setRenameValue(activeItem.name); }}>
                  <Edit3 size={16} />
                  <span>Rename</span>
                </button>
              )}
              {((currentUser?.role?.toLowerCase() === 'owner') || currentUser?.can_move_copy) && (
                <>
                  <button className="z-sheet-option" onClick={startCopyFlow}>
                    <Copy size={16} />
                    <span>Copy</span>
                  </button>
                  <button className="z-sheet-option" onClick={startMoveFlow}>
                    <Move size={16} />
                    <span>Move</span>
                  </button>
                </>
              )}
              {((currentUser?.role?.toLowerCase() === 'owner') || currentUser?.can_delete) && (
                <button className="z-sheet-option danger" onClick={() => { handleDelete(activeItem); }}>
                  <Trash2 size={16} />
                  <span>Delete Permanently</span>
                </button>
              )}
              
              <button className="z-sheet-option" onClick={() => setActiveItem(null)} style={{ marginTop: '8px', justifyContent: 'center', background: 'rgba(255,255,255,0.03)' }}>
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── 7. Action Modals Overlay ───────────────────────────────── */}
      {isCreateFolderOpen && (
        <div className="z-modal-overlay" onClick={() => setIsCreateFolderOpen(false)}>
          <div className="z-modal" onClick={(e) => e.stopPropagation()}>
            <h3 className="z-modal-title">New folder</h3>
            <input 
              type="text" 
              className="z-modal-input" 
              placeholder="Folder name..." 
              value={newFolderName}
              onChange={(e) => setNewFolderName(e.target.value)}
              autoFocus
            />
            <div className="z-modal-actions">
              <button className="z-btn z-btn-text" onClick={() => setIsCreateFolderOpen(false)}>Cancel</button>
              <button className="z-btn z-btn-primary" onClick={handleCreateFolder}>OK</button>
            </div>
          </div>
        </div>
      )}

      {/* Rename Modal */}
      {isRenameOpen && (
        <div className="z-modal-overlay" onClick={() => setIsRenameOpen(false)}>
          <div className="z-modal" onClick={(e) => e.stopPropagation()}>
            <h3 className="z-modal-title">Rename</h3>
            <input 
              type="text" 
              className="z-modal-input" 
              placeholder="New name..." 
              value={renameValue}
              onChange={(e) => setRenameValue(e.target.value)}
              autoFocus
            />
            <div className="z-modal-actions">
              <button className="z-btn z-btn-text" onClick={() => setIsRenameOpen(false)}>Cancel</button>
              <button className="z-btn z-btn-primary" onClick={handleRename}>OK</button>
            </div>
          </div>
        </div>
      )}

      {/* Properties Modal */}
      {isPropertiesOpen && propertiesData && (
        <div className="z-modal-overlay" onClick={() => setIsPropertiesOpen(false)}>
          <div className="z-modal" onClick={(e) => e.stopPropagation()}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <h3 className="z-modal-title" style={{ margin: 0 }}>ℹ️ Properties</h3>
              <button style={{ background: 'none', border: 'none', color: 'var(--text-color)', cursor: 'pointer' }} onClick={() => setIsPropertiesOpen(false)}>
                <X size={18} />
              </button>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', fontSize: '0.8rem' }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '2px', borderBottom: '1px solid var(--border-color)', paddingBottom: '8px' }}>
                <span style={{ color: 'var(--hint-color)', fontSize: '0.65rem', fontWeight: 'bold' }}>NAME</span>
                <span style={{ fontWeight: 600, wordBreak: 'break-all' }}>{propertiesData.name}</span>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '2px', borderBottom: '1px solid var(--border-color)', paddingBottom: '8px' }}>
                <span style={{ color: 'var(--hint-color)', fontSize: '0.65rem', fontWeight: 'bold' }}>TYPE</span>
                <span>{propertiesData.type}</span>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '2px', borderBottom: '1px solid var(--border-color)', paddingBottom: '8px' }}>
                <span style={{ color: 'var(--hint-color)', fontSize: '0.65rem', fontWeight: 'bold' }}>OBJECT ID</span>
                <span style={{ fontFamily: 'monospace', fontSize: '0.7rem' }}>{propertiesData.id}</span>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '2px', borderBottom: '1px solid var(--border-color)', paddingBottom: '8px' }}>
                <span style={{ color: 'var(--hint-color)', fontSize: '0.65rem', fontWeight: 'bold' }}>SIZE</span>
                <span style={{ fontWeight: '600', color: 'var(--accent-color)' }}>{formatBytes(propertiesData.size)}</span>
              </div>

              {propertiesData.type === 'Folder' ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                  <span style={{ color: 'var(--hint-color)', fontSize: '0.65rem', fontWeight: 'bold' }}>CONTAINS</span>
                  <span>{propertiesData.files_count} files, {propertiesData.folders_count} subfolders</span>
                </div>
              ) : (
                <>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '2px', borderBottom: '1px solid var(--border-color)', paddingBottom: '8px' }}>
                    <span style={{ color: 'var(--hint-color)', fontSize: '0.65rem', fontWeight: 'bold' }}>MIME TYPE</span>
                    <span>{propertiesData.mime_type || 'unknown'}</span>
                  </div>
                  {propertiesData.uploaded_at && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                      <span style={{ color: 'var(--hint-color)', fontSize: '0.65rem', fontWeight: 'bold' }}>UPLOADED AT</span>
                      <span>{new Date(propertiesData.uploaded_at).toLocaleString()}</span>
                    </div>
                  )}
                </>
              )}
            </div>

            <div className="z-modal-actions" style={{ marginTop: '20px' }}>
              <button className="z-btn z-btn-primary" onClick={() => setIsPropertiesOpen(false)}>Close</button>
            </div>
          </div>
        </div>
      )}

      {/* Admin Whitelist/Exceptions, Stats and Audit overlay */}
      {isAdminOpen && (
        <div className="z-modal-overlay" onClick={() => setIsAdminOpen(false)}>
          <div className="z-modal" style={{ maxWidth: '440px', width: '90%', maxHeight: '85vh', overflowY: 'auto' }} onClick={(e) => e.stopPropagation()}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <h3 className="z-modal-title" style={{ margin: 0 }}>🛡️ Access Controls</h3>
              <button style={{ background: 'none', border: 'none', color: 'var(--text-color)', cursor: 'pointer' }} onClick={() => setIsAdminOpen(false)}>
                <X size={18} />
              </button>
            </div>

            {/* Admin Tabs Bar */}
            <div style={{ display: 'flex', borderBottom: '1px solid var(--border-color)', marginBottom: '16px' }}>
              <button 
                style={{ 
                  flex: 1, 
                  background: 'none', 
                  border: 'none', 
                  color: adminTab === 'access' ? 'var(--accent-color)' : 'var(--hint-color)', 
                  borderBottom: adminTab === 'access' ? '2px solid var(--accent-color)' : 'none',
                  padding: '10px 0', 
                  fontSize: '0.8rem', 
                  fontWeight: '600',
                  cursor: 'pointer'
                }} 
                onClick={() => setAdminTab('access')}
              >
                Access
              </button>
              <button 
                style={{ 
                  flex: 1, 
                  background: 'none', 
                  border: 'none', 
                  color: adminTab === 'stats' ? 'var(--accent-color)' : 'var(--hint-color)', 
                  borderBottom: adminTab === 'stats' ? '2px solid var(--accent-color)' : 'none',
                  padding: '10px 0', 
                  fontSize: '0.8rem', 
                  fontWeight: '600',
                  cursor: 'pointer'
                }} 
                onClick={() => setAdminTab('stats')}
              >
                Stats
              </button>
              <button 
                style={{ 
                  flex: 1, 
                  background: 'none', 
                  border: 'none', 
                  color: adminTab === 'health' ? 'var(--accent-color)' : 'var(--hint-color)', 
                  borderBottom: adminTab === 'health' ? '2px solid var(--accent-color)' : 'none',
                  padding: '10px 0', 
                  fontSize: '0.8rem', 
                  fontWeight: '600',
                  cursor: 'pointer'
                }} 
                onClick={() => setAdminTab('health')}
              >
                Audit
              </button>
              <button 
                style={{ 
                  flex: 1, 
                  background: 'none', 
                  border: 'none', 
                  color: adminTab === 'settings' ? 'var(--accent-color)' : 'var(--hint-color)', 
                  borderBottom: adminTab === 'settings' ? '2px solid var(--accent-color)' : 'none',
                  padding: '10px 0', 
                  fontSize: '0.8rem', 
                  fontWeight: '600',
                  cursor: 'pointer'
                }} 
                onClick={() => setAdminTab('settings')}
              >
                Settings
              </button>
            </div>

            {/* TAB CONTENT: Access & Exceptions */}
            {adminTab === 'access' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                {/* Search Registered Users Box */}
                <div style={{ position: 'relative', display: 'flex', alignItems: 'center', marginBottom: '4px' }}>
                  <Search size={14} style={{ position: 'absolute', left: '10px', color: 'var(--hint-color)' }} />
                  <input 
                    type="text" 
                    placeholder="Search registered users by name..."
                    style={{ 
                      width: '100%', 
                      backgroundColor: 'rgba(0,0,0,0.15)', 
                      border: '1px solid var(--border-color)', 
                      borderRadius: '8px', 
                      padding: '8px 12px 8px 30px', 
                      color: 'var(--text-color)', 
                      fontSize: '0.8rem',
                      outline: 'none'
                    }}
                    value={searchUserQuery}
                    onChange={(e) => setSearchUserQuery(e.target.value)}
                  />
                  {searchUserQuery && (
                    <button 
                      style={{ position: 'absolute', right: '10px', background: 'none', border: 'none', color: 'var(--hint-color)', cursor: 'pointer', display: 'flex', alignItems: 'center' }}
                      onClick={() => setSearchUserQuery('')}
                    >
                      <X size={14} />
                    </button>
                  )}
                </div>

                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontSize: '0.8rem', fontWeight: 600 }}>All Registered Users:</span>
                  <span style={{ fontSize: '0.7rem', color: 'var(--hint-color)' }}>
                    Showing {usersList.filter(u => {
                      const term = searchUserQuery.toLowerCase();
                      return (u.display_name || '').toLowerCase().includes(term) || (u.username || '').toLowerCase().includes(term);
                    }).length} of {usersList.length}
                  </span>
                </div>

                {usersList.length === 0 ? (
                  <span style={{ fontSize: '0.75rem', color: 'var(--hint-color)', textAlign: 'center', padding: '20px' }}>No users registered.</span>
                ) : usersList.filter(u => {
                  const term = searchUserQuery.toLowerCase();
                  return (u.display_name || '').toLowerCase().includes(term) || (u.username || '').toLowerCase().includes(term);
                }).length === 0 ? (
                  <span style={{ fontSize: '0.75rem', color: 'var(--hint-color)', textAlign: 'center', padding: '20px' }}>No users match search criteria.</span>
                ) : (
                  usersList.filter(u => {
                    const term = searchUserQuery.toLowerCase();
                    return (u.display_name || '').toLowerCase().includes(term) || (u.username || '').toLowerCase().includes(term);
                  }).map(u => {
                    const uRole = u.role || 'guest';
                    return (
                      <div key={u.user_doc_id} style={{ padding: '12px 0', borderBottom: '1px solid var(--border-color)' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.8rem' }}>
                          <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                            <span style={{ fontWeight: 600, fontSize: '0.85rem' }}>{u.display_name}</span>
                            <span style={{ fontSize: '0.7rem', color: 'var(--hint-color)', display: 'flex', flexWrap: 'wrap', gap: '4px', alignItems: 'center' }}>
                              <span>@{u.username || 'no_username'}</span> &bull; 
                              <span style={{ fontFamily: 'monospace' }}>ID: {u.telegram_id}</span> &bull;
                              <span>Role: <span style={{ color: uRole === 'approved' ? 'var(--success-color)' : 'var(--danger-color)', fontWeight: 600 }}>{uRole.toUpperCase()}</span></span>
                            </span>
                          </div>
                          <div style={{ display: 'flex', gap: '6px' }}>
                            {uRole === 'guest' ? (
                              <button 
                                className="z-btn z-btn-primary" 
                                style={{ padding: '4px 8px', fontSize: '0.7rem', backgroundColor: 'var(--success-color)' }}
                                onClick={() => handleApproveUser(u.user_doc_id)}
                              >
                                Approve
                              </button>
                            ) : (
                              <button 
                                className="z-btn z-btn-text" 
                                style={{ padding: '4px 8px', fontSize: '0.7rem', border: '1px solid var(--danger-color)', color: 'var(--danger-color)' }}
                                onClick={() => handleRevokeUser(u.user_doc_id)}
                              >
                                Revoke
                              </button>
                            )}
                          </div>
                        </div>
                        
                        {uRole === 'approved' && (
                          <div style={{ marginTop: '10px', paddingLeft: '4px', borderLeft: '2px solid rgba(255,255,255,0.03)' }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                              <span style={{ fontSize: '0.7rem', color: 'var(--hint-color)', fontWeight: 500 }}>Folder Exceptions:</span>
                              <div style={{ display: 'flex', gap: '4px' }}>
                                <button className="z-btn z-btn-primary" style={{ padding: '2px 6px', fontSize: '0.65rem' }} onClick={() => handleToggleException(u.user_doc_id, currentFolderId, 'allow')}>Allow Current</button>
                                <button className="z-btn z-btn-primary" style={{ padding: '2px 6px', fontSize: '0.65rem', backgroundColor: 'var(--danger-color, #ef4444)' }} onClick={() => handleToggleException(u.user_doc_id, currentFolderId, 'block')}>Block Current</button>
                                <button className="z-btn z-btn-primary" style={{ padding: '2px 6px', fontSize: '0.65rem', backgroundColor: 'var(--button-color)' }} onClick={() => { triggerHaptic('light'); setExceptionEditorUser(u.user_doc_id); setSelectedFolderForException(''); setExceptionRuleType('allow'); }}>+ Custom</button>
                                {(u.allowed_folders?.length > 0 || u.blocked_folders?.length > 0) && (
                                  <button className="z-btn z-btn-text" style={{ padding: '2px 6px', fontSize: '0.65rem', color: 'var(--danger-color)' }} onClick={() => handleToggleException(u.user_doc_id, currentFolderId, 'reset')}>Reset</button>
                                )}
                              </div>
                            </div>

                            {/* Exception Editor Inline Form */}
                            {exceptionEditorUser === u.user_doc_id && (
                              <div style={{ marginTop: '10px', padding: '10px', background: 'rgba(255,255,255,0.02)', border: '1px solid var(--border-color)', borderRadius: '8px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                                <span style={{ fontSize: '0.65rem', fontWeight: 'bold', color: 'var(--hint-color)', letterSpacing: '0.05em' }}>ADD CUSTOM FOLDER EXCEPTION</span>
                                <div>
                                  <select
                                    value={selectedFolderForException}
                                    onChange={(e) => setSelectedFolderForException(e.target.value)}
                                    style={{ width: '100%', padding: '6px', borderRadius: '4px', backgroundColor: 'var(--secondary-bg-color)', color: 'var(--text-color)', border: '1px solid var(--border-color)', fontSize: '0.75rem', outline: 'none' }}
                                  >
                                    <option value="">-- Select Folder --</option>
                                    {allFolders.map(f => (
                                      <option key={f.id} value={f.id}>{f.name}</option>
                                    ))}
                                  </select>
                                </div>
                                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                  <div style={{ display: 'flex', gap: '12px' }}>
                                    <label style={{ fontSize: '0.7rem', display: 'flex', alignItems: 'center', gap: '4px', cursor: 'pointer' }}>
                                      <input type="radio" name={`rule-type-${u.user_doc_id}`} checked={exceptionRuleType === 'allow'} onChange={() => setExceptionRuleType('allow')} />
                                      Allow Access
                                    </label>
                                    <label style={{ fontSize: '0.7rem', display: 'flex', alignItems: 'center', gap: '4px', cursor: 'pointer' }}>
                                      <input type="radio" name={`rule-type-${u.user_doc_id}`} checked={exceptionRuleType === 'block'} onChange={() => setExceptionRuleType('block')} />
                                      Block Access
                                    </label>
                                  </div>
                                  <div style={{ display: 'flex', gap: '6px' }}>
                                    <button className="z-btn z-btn-text" style={{ padding: '4px 8px', fontSize: '0.65rem' }} onClick={() => setExceptionEditorUser(null)}>Cancel</button>
                                    <button className="z-btn z-btn-primary" style={{ padding: '4px 10px', fontSize: '0.65rem' }} onClick={handleAddException}>Save</button>
                                  </div>
                                </div>
                              </div>
                            )}

                            {/* Exception Badges List */}
                            <div className="pill-container" style={{ marginTop: '8px', display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                              {u.allowed_folders?.map(f => (
                                <span key={f.id} className="z-badge allow" style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', paddingRight: '2px' }}>
                                  Allow: {f.name}
                                  <button 
                                    style={{ background: 'none', border: 'none', color: '#4ade80', cursor: 'pointer', padding: '0 4px', fontSize: '0.65rem', display: 'flex', alignItems: 'center' }}
                                    onClick={() => { triggerHaptic('medium'); handleRemoveException(u.user_doc_id, f.id); }}
                                    title="Remove Exception"
                                  >
                                    ✕
                                  </button>
                                </span>
                              ))}
                              {u.blocked_folders?.map(f => (
                                <span key={f.id} className="z-badge block" style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', paddingRight: '2px' }}>
                                  Block: {f.name}
                                  <button 
                                    style={{ background: 'none', border: 'none', color: '#f87171', cursor: 'pointer', padding: '0 4px', fontSize: '0.65rem', display: 'flex', alignItems: 'center' }}
                                    onClick={() => { triggerHaptic('medium'); handleRemoveException(u.user_doc_id, f.id); }}
                                    title="Remove Exception"
                                  >
                                    ✕
                                  </button>
                                </span>
                              ))}
                            </div>

                            <div style={{ marginTop: '12px', display: 'flex', flexDirection: 'column', gap: '6px', borderTop: '1px solid rgba(255,255,255,0.03)', paddingTop: '8px' }}>
                              <span style={{ fontSize: '0.7rem', color: 'var(--hint-color)', fontWeight: 500 }}>Delegated Management Permissions:</span>
                              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px 14px', marginTop: '2px' }}>
                                <label style={{ fontSize: '0.7rem', display: 'flex', alignItems: 'center', gap: '4px', cursor: 'pointer', userSelect: 'none' }}>
                                  <input type="checkbox" checked={u.can_upload || false} onChange={(e) => handleTogglePermission(u.user_doc_id, 'can_upload', e.target.checked)} style={{ accentColor: 'var(--accent-color)' }} />
                                  Upload Files
                                </label>
                                <label style={{ fontSize: '0.7rem', display: 'flex', alignItems: 'center', gap: '4px', cursor: 'pointer', userSelect: 'none' }}>
                                  <input type="checkbox" checked={u.can_create_folder || false} onChange={(e) => handleTogglePermission(u.user_doc_id, 'can_create_folder', e.target.checked)} style={{ accentColor: 'var(--accent-color)' }} />
                                  Create Folders
                                </label>
                                <label style={{ fontSize: '0.7rem', display: 'flex', alignItems: 'center', gap: '4px', cursor: 'pointer', userSelect: 'none' }}>
                                  <input type="checkbox" checked={u.can_rename || false} onChange={(e) => handleTogglePermission(u.user_doc_id, 'can_rename', e.target.checked)} style={{ accentColor: 'var(--accent-color)' }} />
                                  Rename Items
                                </label>
                                <label style={{ fontSize: '0.7rem', display: 'flex', alignItems: 'center', gap: '4px', cursor: 'pointer', userSelect: 'none' }}>
                                  <input type="checkbox" checked={u.can_delete || false} onChange={(e) => handleTogglePermission(u.user_doc_id, 'can_delete', e.target.checked)} style={{ accentColor: 'var(--accent-color)' }} />
                                  Delete Items
                                </label>
                                <label style={{ fontSize: '0.7rem', display: 'flex', alignItems: 'center', gap: '4px', cursor: 'pointer', userSelect: 'none' }}>
                                  <input type="checkbox" checked={u.can_move_copy || false} onChange={(e) => handleTogglePermission(u.user_doc_id, 'can_move_copy', e.target.checked)} style={{ accentColor: 'var(--accent-color)' }} />
                                  Move / Copy
                                </label>
                              </div>
                            </div>
                          </div>
                        )}
                      </div>
                    );
                  })
                )}
              </div>
            )}

            {/* TAB CONTENT: Drive Metrics */}
            {adminTab === 'stats' && (
              <div>
                {statsLoading ? (
                  <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '40px', gap: '8px' }}>
                    <RefreshCw className="animate-spin" size={20} style={{ color: 'var(--accent-color)' }} />
                    <span style={{ fontSize: '0.75rem', color: 'var(--hint-color)' }}>Loading metrics...</span>
                  </div>
                ) : statsData ? (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                    {/* Total Storage Panel */}
                    <div className="glass-panel" style={{ padding: '16px', borderRadius: '10px', background: 'rgba(255,255,255,0.02)', border: '1px solid var(--border-color)', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                      <span style={{ fontSize: '0.75rem', color: 'var(--hint-color)' }}>TOTAL STORAGE USE</span>
                      <span style={{ fontSize: '1.6rem', fontWeight: '800', color: 'var(--accent-color)', margin: '4px 0' }}>
                        {formatBytes(statsData.total_size)}
                      </span>
                      <span style={{ fontSize: '0.7rem', color: 'var(--hint-color)' }}>
                        Across {statsData.files_count} files and {statsData.folders_count} directories
                      </span>
                    </div>

                    {/* Media Split Breakdown */}
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                      <span style={{ fontSize: '0.8rem', fontWeight: 600 }}>Media Type Split:</span>
                      {Object.entries(statsData.file_types || {}).map(([type, stats]) => {
                        const sizeVal = stats?.size || 0;
                        const countVal = stats?.count || 0;
                        const pct = statsData.total_size > 0 ? (sizeVal / statsData.total_size) * 100 : 0;
                        return (
                          <div key={type} style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem' }}>
                              <span style={{ textTransform: 'capitalize', fontWeight: '500' }}>{type}s ({countVal})</span>
                              <span style={{ color: 'var(--hint-color)' }}>{formatBytes(sizeVal)} ({pct.toFixed(1)}%)</span>
                            </div>
                            <div style={{ width: '100%', height: '6px', backgroundColor: 'rgba(255,255,255,0.05)', borderRadius: '3px', overflow: 'hidden' }}>
                              <div style={{ width: `${pct}%`, height: '100%', backgroundColor: type === 'video' ? '#38bdf8' : type === 'photo' ? '#fb7185' : '#fbbf24', borderRadius: '3px' }} />
                            </div>
                          </div>
                        );
                      })}
                    </div>

                    {/* Users Statistics */}
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', borderTop: '1px solid var(--border-color)', paddingTop: '16px' }}>
                      <span style={{ fontSize: '0.8rem', fontWeight: 600 }}>Users Breakdown:</span>
                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '8px', textAlign: 'center' }}>
                        <div style={{ background: 'rgba(255,255,255,0.02)', padding: '10px', borderRadius: '8px', border: '1px solid var(--border-color)' }}>
                          <div style={{ fontSize: '1.1rem', fontWeight: '700' }}>{statsData.users?.total}</div>
                          <div style={{ fontSize: '0.65rem', color: 'var(--hint-color)' }}>Total</div>
                        </div>
                        <div style={{ background: 'rgba(34,197,94,0.04)', padding: '10px', borderRadius: '8px', border: '1px solid rgba(34,197,94,0.1)' }}>
                          <div style={{ fontSize: '1.1rem', fontWeight: '700', color: 'var(--success-color)' }}>{statsData.users?.approved}</div>
                          <div style={{ fontSize: '0.65rem', color: 'var(--success-color)' }}>Approved</div>
                        </div>
                        <div style={{ background: 'rgba(239,68,68,0.04)', padding: '10px', borderRadius: '8px', border: '1px solid rgba(239,68,68,0.1)' }}>
                          <div style={{ fontSize: '1.1rem', fontWeight: '700', color: 'var(--danger-color)' }}>{statsData.users?.guest}</div>
                          <div style={{ fontSize: '0.65rem', color: 'var(--danger-color)' }}>Guests</div>
                        </div>
                      </div>
                    </div>
                  </div>
                ) : (
                  <span style={{ fontSize: '0.75rem', color: 'var(--hint-color)' }}>Failed to load metrics.</span>
                )}
              </div>
            )}

            {/* TAB CONTENT: Audit */}
            {adminTab === 'health' && (
              <div>
                {/* Audit Controls & Execution Status */}
                <div className="glass-panel" style={{ padding: '12px', marginBottom: '12px', borderRadius: '8px', background: 'rgba(255,255,255,0.02)', border: '1px solid var(--border-color)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                    <span style={{ fontSize: '0.8rem', fontWeight: 600 }}>Diagnostic Audit</span>
                    <span style={{ fontSize: '0.65rem', color: 'var(--hint-color)' }}>Verify database reference integrity against Telegram CDN</span>
                  </div>
                  <button className="z-btn z-btn-primary" style={{ padding: '6px 12px', fontSize: '0.75rem' }} onClick={runHealthCheck} disabled={healthLoading}>
                    {healthLoading ? "Scanning..." : "Start scan"}
                  </button>
                </div>

                {healthLoading && (
                  <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '40px', gap: '8px' }}>
                    <RefreshCw className="animate-spin" size={24} style={{ color: 'var(--accent-color)' }} />
                    <span style={{ fontSize: '0.75rem', color: 'var(--hint-color)' }}>Verifying Telegram file records...</span>
                  </div>
                )}

                {/* Audit Results Visualization */}
                {!healthLoading && healthStatus && (
                  <div>
                    {/* Integrity Score Card */}
                    {(() => {
                      const integrityPercent = healthStatus.total > 0 ? Math.round((healthStatus.active / healthStatus.total) * 100) : 100;
                      return (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', padding: '16px', background: 'rgba(255,255,255,0.02)', border: '1px solid var(--border-color)', borderRadius: '10px', marginBottom: '16px' }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <span style={{ fontSize: '0.75rem', color: 'var(--hint-color)', fontWeight: 'bold' }}>SYSTEM INTEGRITY</span>
                            <span style={{ fontSize: '1.1rem', fontWeight: '800', color: integrityPercent === 100 ? 'var(--success-color)' : 'var(--warning-color)' }}>
                              {integrityPercent}% Healthy
                            </span>
                          </div>
                          {/* Progress Bar */}
                          <div style={{ width: '100%', height: '8px', backgroundColor: 'rgba(255,255,255,0.05)', borderRadius: '4px', overflow: 'hidden' }}>
                            <div 
                              style={{ 
                                width: `${integrityPercent}%`, 
                                height: '100%', 
                                background: integrityPercent === 100 ? 'var(--success-color)' : 'linear-gradient(90deg, var(--warning-color) 0%, var(--danger-color) 100%)',
                                borderRadius: '4px',
                                transition: 'width 0.5s ease-out'
                              }} 
                            />
                          </div>
                          
                          {/* Stats Grid */}
                          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '6px', marginTop: '8px', textAlign: 'center' }}>
                            <div style={{ padding: '6px', background: 'rgba(255,255,255,0.01)', borderRadius: '6px', border: '1px solid var(--border-color)' }}>
                              <div style={{ fontSize: '0.85rem', fontWeight: '700' }}>{healthStatus.total}</div>
                              <div style={{ fontSize: '0.55rem', color: 'var(--hint-color)' }}>Total</div>
                            </div>
                            <div style={{ padding: '6px', background: 'rgba(34,197,94,0.02)', borderRadius: '6px', border: '1px solid rgba(34,197,94,0.08)' }}>
                              <div style={{ fontSize: '0.85rem', fontWeight: '700', color: 'var(--success-color)' }}>{healthStatus.active}</div>
                              <div style={{ fontSize: '0.55rem', color: 'var(--success-color)' }}>Active</div>
                            </div>
                            <div style={{ padding: '6px', background: 'rgba(239,68,68,0.02)', borderRadius: '6px', border: '1px solid rgba(239,68,68,0.08)' }}>
                              <div style={{ fontSize: '0.85rem', fontWeight: '700', color: 'var(--danger-color)' }}>{healthStatus.broken?.length || 0}</div>
                              <div style={{ fontSize: '0.55rem', color: 'var(--danger-color)' }}>Broken</div>
                            </div>
                            <div style={{ padding: '6px', background: 'rgba(255,255,255,0.01)', borderRadius: '6px', border: '1px solid var(--border-color)' }}>
                              <div style={{ fontSize: '0.85rem', fontWeight: '700', color: 'var(--hint-color)' }}>{healthStatus.legacy || 0}</div>
                              <div style={{ fontSize: '0.55rem', color: 'var(--hint-color)' }}>Legacy</div>
                            </div>
                          </div>
                        </div>
                      );
                    })()}

                    {/* Detailed Broken Files List */}
                    {healthStatus.broken && healthStatus.broken.length > 0 ? (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <span style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--danger-color)' }}>Broken References List:</span>
                          <button 
                            className="z-btn z-btn-primary" 
                            style={{ padding: '4px 8px', fontSize: '0.65rem', backgroundColor: 'var(--danger-color)' }}
                            onClick={() => {
                              if (confirm("Are you sure you want to purge all broken references from the database? This cannot be undone.")) {
                                handlePurgeBroken(healthStatus.broken.map(b => b.id));
                              }
                            }}
                          >
                            Purge All
                          </button>
                        </div>

                        <div style={{ maxHeight: '180px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '6px', border: '1px solid var(--border-color)', borderRadius: '8px', padding: '6px', background: 'rgba(0,0,0,0.1)' }}>
                          {healthStatus.broken.map(b => (
                            <div key={b.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '6px 8px', background: 'rgba(255,255,255,0.01)', border: '1px solid var(--border-color)', borderRadius: '6px', fontSize: '0.75rem' }}>
                              <div style={{ display: 'flex', flexDirection: 'column', gap: '1px', overflow: 'hidden', flex: 1, paddingRight: '8px', textAlign: 'left' }}>
                                <span style={{ fontWeight: 600, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{b.name}</span>
                                <span style={{ fontSize: '0.65rem', color: 'var(--hint-color)' }}>Path: {b.folder_path}</span>
                              </div>
                              <button 
                                style={{ background: 'none', border: 'none', color: 'var(--danger-color)', cursor: 'pointer', padding: '4px', display: 'flex', alignItems: 'center' }}
                                onClick={() => {
                                  if (confirm(`Remove this broken reference "${b.name}"?`)) {
                                    handlePurgeBroken([b.id]);
                                  }
                                }}
                                title="Delete Reference"
                              >
                                <Trash2 size={14} />
                              </button>
                            </div>
                          ))}
                        </div>
                      </div>
                    ) : (
                      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '32px 0 16px 0', opacity: 0.7, gap: '8px' }}>
                        <Check size={28} style={{ color: 'var(--success-color)' }} />
                        <span style={{ fontSize: '0.75rem', fontWeight: 600 }}>All file references verified healthy!</span>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}

            {adminTab === 'settings' && (
              <div>
                {settingsLoading ? (
                  <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '40px', gap: '8px' }}>
                    <RefreshCw className="animate-spin" size={20} style={{ color: 'var(--accent-color)' }} />
                    <span style={{ fontSize: '0.75rem', color: 'var(--hint-color)' }}>Loading settings...</span>
                  </div>
                ) : settingsData ? (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                    {/* Bot Name Setting Card */}
                    <div className="glass-panel" style={{ padding: '14px', borderRadius: '10px', background: 'rgba(255,255,255,0.02)', border: '1px solid var(--border-color)', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <span style={{ fontSize: '0.8rem', fontWeight: 'bold' }}>Bot Name / Personalization</span>
                        {settingsData.overrides.bot_name && (
                          <button 
                            style={{ background: 'none', border: 'none', color: 'var(--danger-color)', fontSize: '0.65rem', cursor: 'pointer', textDecoration: 'underline' }}
                            onClick={() => handleSaveSettings('bot_name', null)}
                          >
                            Use Default
                          </button>
                        )}
                      </div>
                      <input 
                        type="text" 
                        placeholder={settingsData.defaults.bot_name || "Telegram Cloud Manager"}
                        style={{ 
                          width: '100%', 
                          backgroundColor: 'rgba(0,0,0,0.15)', 
                          border: '1px solid var(--border-color)', 
                          borderRadius: '6px', 
                          padding: '8px 10px', 
                          color: 'var(--text-color)', 
                          fontSize: '0.8rem',
                          outline: 'none'
                        }}
                        value={botNameInput}
                        onChange={(e) => setBotNameInput(e.target.value)}
                      />
                      <span style={{ fontSize: '0.65rem', color: 'var(--hint-color)' }}>
                        Default: <code>{settingsData.defaults.bot_name || "None (uses generic names)"}</code>. Changing this updates welcome messages.
                      </span>
                    </div>

                    {/* Items Per Page Card */}
                    <div className="glass-panel" style={{ padding: '14px', borderRadius: '10px', background: 'rgba(255,255,255,0.02)', border: '1px solid var(--border-color)', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <span style={{ fontSize: '0.8rem', fontWeight: 'bold' }}>Items Per Page</span>
                        {settingsData.overrides.items_per_page && (
                          <button 
                            style={{ background: 'none', border: 'none', color: 'var(--danger-color)', fontSize: '0.65rem', cursor: 'pointer', textDecoration: 'underline' }}
                            onClick={() => handleSaveSettings('items_per_page', null)}
                          >
                            Use Default
                          </button>
                        )}
                      </div>
                      <input 
                        type="number" 
                        min="1"
                        max="100"
                        style={{ 
                          width: '100%', 
                          backgroundColor: 'rgba(0,0,0,0.15)', 
                          border: '1px solid var(--border-color)', 
                          borderRadius: '6px', 
                          padding: '8px 10px', 
                          color: 'var(--text-color)', 
                          fontSize: '0.8rem',
                          outline: 'none'
                        }}
                        value={itemsPerPageInput}
                        onChange={(e) => setItemsPerPageInput(e.target.value)}
                      />
                      <span style={{ fontSize: '0.65rem', color: 'var(--hint-color)' }}>
                        Default: <code>{settingsData.defaults.items_per_page}</code>. Virtual folders will page at this limit.
                      </span>
                    </div>

                    {/* Auto Delete Hours Card */}
                    <div className="glass-panel" style={{ padding: '14px', borderRadius: '10px', background: 'rgba(255,255,255,0.02)', border: '1px solid var(--border-color)', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <span style={{ fontSize: '0.8rem', fontWeight: 'bold' }}>Auto Delete Delay (Hours)</span>
                        {settingsData.overrides.auto_delete_hours && (
                          <button 
                            style={{ background: 'none', border: 'none', color: 'var(--danger-color)', fontSize: '0.65rem', cursor: 'pointer', textDecoration: 'underline' }}
                            onClick={() => handleSaveSettings('auto_delete_hours', null)}
                          >
                            Use Default
                          </button>
                        )}
                      </div>
                      <input 
                        type="number" 
                        min="0"
                        max="720"
                        step="0.1"
                        style={{ 
                          width: '100%', 
                          backgroundColor: 'rgba(0,0,0,0.15)', 
                          border: '1px solid var(--border-color)', 
                          borderRadius: '6px', 
                          padding: '8px 10px', 
                          color: 'var(--text-color)', 
                          fontSize: '0.8rem',
                          outline: 'none'
                        }}
                        value={autoDeleteHoursInput}
                        onChange={(e) => setAutoDeleteHoursInput(e.target.value)}
                      />
                      <span style={{ fontSize: '0.65rem', color: 'var(--hint-color)' }}>
                        Default: <code>{settingsData.defaults.auto_delete_hours} hours</code>. Use <code>0</code> to disable auto-delete.
                      </span>
                    </div>

                    {/* Protect Content Card */}
                    <div className="glass-panel" style={{ padding: '14px', borderRadius: '10px', background: 'rgba(255,255,255,0.02)', border: '1px solid var(--border-color)', display: 'flex', flexDirection: 'column', gap: '10px' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <span style={{ fontSize: '0.8rem', fontWeight: 'bold' }}>Content Protection (Anti-Forward/Save)</span>
                        {settingsData.overrides.protect_content && (
                          <button 
                            style={{ background: 'none', border: 'none', color: 'var(--danger-color)', fontSize: '0.65rem', cursor: 'pointer', textDecoration: 'underline' }}
                            onClick={() => handleSaveSettings('protect_content', null)}
                          >
                            Use Default
                          </button>
                        )}
                      </div>
                      <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer', fontSize: '0.8rem' }}>
                        <input 
                          type="checkbox" 
                          checked={protectContentInput}
                          onChange={(e) => setProtectContentInput(e.target.checked)}
                          style={{ cursor: 'pointer', width: '16px', height: '16px' }}
                        />
                        <span>Protect delivered Telegram messages from save/forward</span>
                      </label>
                      <span style={{ fontSize: '0.65rem', color: 'var(--hint-color)' }}>
                        Default: <code>{settingsData.defaults.protect_content ? "Enabled" : "Disabled"}</code>. Disallows forwarding or saving media.
                      </span>
                    </div>

                    {/* Action buttons */}
                    <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '4px' }}>
                      <button 
                        className="z-btn z-btn-text" 
                        style={{ padding: '8px 16px', fontSize: '0.75rem' }} 
                        onClick={loadSettings}
                        disabled={settingsSaving}
                      >
                        Reset Form
                      </button>
                      <button 
                        className="z-btn z-btn-primary" 
                        style={{ padding: '8px 20px', fontSize: '0.75rem' }} 
                        onClick={() => handleSaveSettings(null, null)}
                        disabled={settingsSaving}
                      >
                        {settingsSaving ? "Saving..." : "Save Settings"}
                      </button>
                    </div>
                  </div>
                ) : (
                  <span style={{ fontSize: '0.75rem', color: 'var(--hint-color)' }}>Failed to load settings.</span>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
