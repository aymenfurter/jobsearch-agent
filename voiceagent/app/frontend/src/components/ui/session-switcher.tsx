import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Check, ChevronDown, Edit2, Plus, Trash2, UserCircle } from 'lucide-react';
import { Button } from './button';
import { StoredSession, getSavedSessions, removeSession, updateSession } from '@/utils/sessions';
import { cn } from '@/lib/utils';

interface SessionSwitcherProps {
  currentSessionId: string | undefined;
  onSelectSession: (sessionId: string) => void;
  onCreateNewSession: () => void;
  className?: string;
}

export function SessionSwitcher({ 
  currentSessionId, 
  onSelectSession, 
  onCreateNewSession,
  className 
}: SessionSwitcherProps): JSX.Element {
  const [isOpen, setIsOpen] = useState(false);
  const [sessions, setSessions] = useState<StoredSession[]>([]);
  const [editingSession, setEditingSession] = useState<string | null>(null);
  const [sessionName, setSessionName] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const editInputRef = useRef<HTMLInputElement>(null);
  
  // Load sessions from localStorage and Redis when needed
  const refreshSessions = useCallback(async () => {
    setIsLoading(true);
    try {
      const savedSessions = await getSavedSessions();
      // Sort by last used timestamp (most recent first)
      savedSessions.sort((a: StoredSession, b: StoredSession) => b.lastUsed - a.lastUsed);
      setSessions(savedSessions);
    } catch (error) {
      console.error("Error loading sessions:", error);
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Refresh when dropdown opens or current session changes
  useEffect(() => {
    if (isOpen || currentSessionId) {
      refreshSessions();
    }
  }, [isOpen, currentSessionId, refreshSessions]);
  
  // Also refresh on mount
  useEffect(() => {
    refreshSessions();
  }, [refreshSessions]);
  
  // Handle clicks outside the dropdown to close it
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    
    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, []);
  
  // Focus the edit input when starting to edit
  useEffect(() => {
    if (editingSession && editInputRef.current) {
      editInputRef.current.focus();
    }
  }, [editingSession]);
  
  // Get current session details
  const currentSession = sessions.find(s => s.id === currentSessionId);
  
  // Format date for display
  const formatDate = (timestamp: number) => {
    return new Date(timestamp).toLocaleString(undefined, { 
      month: 'short', 
      day: 'numeric',
      hour: '2-digit', 
      minute: '2-digit'
    });
  };
  
  // Handle session rename
  const handleRenameSession = (e: React.FormEvent, sessionId: string) => {
    e.preventDefault();
    if (sessionName.trim()) {
      const updatedSession = updateSession(sessionId, { name: sessionName.trim() });
      if (updatedSession) {
        refreshSessions();
        setEditingSession(null);
      }
    }
  };
  
  // Handle session deletion
  const handleDeleteSession = (sessionId: string) => {
    removeSession(sessionId);
    refreshSessions();
    
    // If we're deleting the current session, create a new one
    if (sessionId === currentSessionId) {
      onCreateNewSession();
    }
  };
  
  // Start editing a session name
  const startEditing = (session: StoredSession) => {
    setSessionName(session.name);
    setEditingSession(session.id);
  };
  
  // Create a new session
  const handleCreateSession = async () => {
    setIsOpen(false);
    onCreateNewSession();
    // Will refresh via currentSessionId change
  };

  return (
    <div className={cn("relative", className)} ref={dropdownRef}>
      <Button
        variant="outline"
        className="w-full justify-between"
        onClick={() => setIsOpen(!isOpen)}
      >
        <div className="flex items-center gap-2 truncate">
          <UserCircle className="h-4 w-4 shrink-0" />
          <span className="truncate">
            {currentSession?.name || "No session selected"}
          </span>
        </div>
        <ChevronDown className="h-4 w-4 shrink-0 opacity-50" />
      </Button>

      {isOpen && (
        <div className="absolute top-full left-0 z-10 mt-1 w-full rounded-md border bg-background shadow-md">
          <div className="max-h-[300px] overflow-auto p-1">
            {isLoading ? (
              <div className="py-4 text-center text-sm text-muted-foreground">
                Loading sessions...
              </div>
            ) : sessions.length > 0 ? (
              <div className="space-y-1">
                {sessions.map((session) => (
                  <div
                    key={session.id}
                    className={cn(
                      "flex items-center justify-between rounded-md px-2 py-1.5 hover:bg-muted",
                      session.id === currentSessionId && "bg-muted"
                    )}
                  >
                    {editingSession === session.id ? (
                      <form 
                        className="flex-1 flex items-center" 
                        onSubmit={(e) => handleRenameSession(e, session.id)}
                      >
                        <input
                          ref={editInputRef}
                          type="text"
                          value={sessionName}
                          onChange={(e) => setSessionName(e.target.value)}
                          className="flex-1 bg-transparent border-b border-primary px-1 py-0.5 text-sm focus:outline-none"
                          onBlur={() => setEditingSession(null)}
                          onKeyDown={(e) => e.key === 'Escape' && setEditingSession(null)}
                        />
                        <Button 
                          type="submit" 
                          variant="ghost" 
                          size="sm" 
                          className="h-7 w-7 p-0"
                        >
                          <Check className="h-3.5 w-3.5" />
                        </Button>
                      </form>
                    ) : (
                      <>
                        <div 
                          className="flex-1 cursor-pointer"
                          onClick={() => {
                            if (session.id !== currentSessionId) {
                              onSelectSession(session.id);
                              setIsOpen(false);
                            }
                          }}
                        >
                          <div className="flex items-center gap-2">
                            {session.id === currentSessionId && (
                              <Check className="h-3.5 w-3.5 text-primary" />
                            )}
                            <span className="font-medium text-sm">
                              {session.name}
                            </span>
                          </div>
                          <div className="text-xs text-muted-foreground">
                            Last used: {formatDate(session.lastUsed)}
                          </div>
                        </div>
                        
                        <div className="flex items-center">
                          <Button 
                            variant="ghost" 
                            size="sm" 
                            className="h-7 w-7 p-0"
                            onClick={() => startEditing(session)}
                          >
                            <Edit2 className="h-3.5 w-3.5" />
                          </Button>
                          <Button 
                            variant="ghost" 
                            size="sm" 
                            className="h-7 w-7 p-0 text-destructive hover:text-destructive/90"
                            onClick={() => handleDeleteSession(session.id)}
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </Button>
                        </div>
                      </>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <div className="py-4 text-center text-sm text-muted-foreground">
                No saved sessions
              </div>
            )}
          </div>
          
          <div className="border-t p-2">
            <Button
              variant="outline"
              size="sm"
              className="w-full justify-center"
              onClick={handleCreateSession}
            >
              <Plus className="mr-2 h-4 w-4" />
              New Session
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}