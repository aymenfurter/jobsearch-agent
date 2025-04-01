/**
 * Utility functions for managing session IDs in local storage
 */

// Storage key for sessions in localStorage
const STORAGE_KEY = "job_search_sessions";

export interface StoredSession {
  id: string;
  name: string;
  createdAt: number; // timestamp
  lastUsed: number; // timestamp
}

/**
 * Retrieves all stored sessions from localStorage
 * 
 * @returns Array of stored session objects
 */
export const getSavedSessions = (): StoredSession[] => {
  try {
    const sessionsJson = localStorage.getItem(STORAGE_KEY);
    if (!sessionsJson) return [];
    
    const sessions = JSON.parse(sessionsJson);
    return Array.isArray(sessions) ? sessions : [];
  } catch (error) {
    console.error("Error reading sessions from localStorage:", error);
    return [];
  }
};

/**
 * Saves a session to localStorage
 * 
 * @param sessionId - The session ID to save
 * @param name - Optional friendly name for the session
 * @returns The stored session object
 */
export const saveSession = (sessionId: string, name?: string): StoredSession => {
  const sessions = getSavedSessions();
  
  // Check if session already exists
  const existingIndex = sessions.findIndex(s => s.id === sessionId);
  const timestamp = Date.now();
  
  const sessionObj: StoredSession = {
    id: sessionId,
    name: name || `Session ${sessions.length + 1}`,
    createdAt: existingIndex >= 0 ? sessions[existingIndex].createdAt : timestamp,
    lastUsed: timestamp
  };
  
  if (existingIndex >= 0) {
    // Update existing session
    sessions[existingIndex] = sessionObj;
  } else {
    // Add new session
    sessions.push(sessionObj);
  }
  
  localStorage.setItem(STORAGE_KEY, JSON.stringify(sessions));
  return sessionObj;
};

/**
 * Updates a session's metadata
 * 
 * @param sessionId - The session ID to update
 * @param updates - Fields to update
 * @returns The updated session or null if not found
 */
export const updateSession = (
  sessionId: string, 
  updates: Partial<Pick<StoredSession, "name" | "lastUsed">>
): StoredSession | null => {
  const sessions = getSavedSessions();
  const sessionIndex = sessions.findIndex(s => s.id === sessionId);
  
  if (sessionIndex < 0) return null;
  
  sessions[sessionIndex] = {
    ...sessions[sessionIndex],
    ...updates
  };
  
  localStorage.setItem(STORAGE_KEY, JSON.stringify(sessions));
  return sessions[sessionIndex];
};

/**
 * Removes a session from localStorage
 * 
 * @param sessionId - The session ID to remove
 */
export const removeSession = (sessionId: string): void => {
  const sessions = getSavedSessions();
  const filteredSessions = sessions.filter(s => s.id !== sessionId);
  localStorage.setItem(STORAGE_KEY, JSON.stringify(filteredSessions));
};

/**
 * Updates the lastUsed timestamp for a session
 * 
 * @param sessionId - The session ID to touch
 */
export const touchSession = (sessionId: string): void => {
  updateSession(sessionId, { lastUsed: Date.now() });
};

/**
 * Gets the most recently used session
 * 
 * @returns The most recent session or undefined if none exist
 */
export const getMostRecentSession = (): StoredSession | undefined => {
  const sessions = getSavedSessions();
  if (sessions.length === 0) return undefined;
  
  return sessions.sort((a, b) => b.lastUsed - a.lastUsed)[0];
};