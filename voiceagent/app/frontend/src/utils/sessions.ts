/**
 * Utility functions for managing session IDs in local storage and Redis
 */

// Storage key for sessions in localStorage
const STORAGE_KEY = "job_search_sessions";

export interface StoredSession {
  id: string;
  name: string;
  createdAt: number; // timestamp
  lastUsed: number; // timestamp
}

export interface RedisSession {
  id: string;
  created_at: number;
  last_activity: number;
  search_query: string | null;
}

/**
 * Retrieves all sessions from localStorage
 * 
 * @returns Array of stored session objects
 */
export const getLocalSessions = (): StoredSession[] => {
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
 * Fetches all active sessions from Redis via API
 * 
 * @returns Promise resolving to array of Redis session objects
 */
export const fetchRedisSessions = async (): Promise<RedisSession[]> => {
  try {
    const response = await fetch('/api/sessions');
    if (!response.ok) {
      throw new Error(`Failed to fetch Redis sessions: ${response.status}`);
    }
    const data = await response.json();
    return data.sessions || [];
  } catch (error) {
    console.error("Error fetching Redis sessions:", error);
    return [];
  }
};

/**
 * Merges sessions from Redis and localStorage with appropriate names
 * 
 * @returns Promise resolving to combined array of session objects
 */
export const getSavedSessions = async (): Promise<StoredSession[]> => {
  // Get sessions from both sources
  const localSessions = getLocalSessions();
  const redisSessions = await fetchRedisSessions();
  
  // Create a map of local sessions for easy lookup
  const localSessionMap = new Map<string, StoredSession>();
  localSessions.forEach(session => {
    localSessionMap.set(session.id, session);
  });
  
  // Merge the sessions, preferring local data for names but using Redis for existence
  const mergedSessions: StoredSession[] = [];
  
  // First add all Redis sessions (as they are the source of truth)
  for (const redisSession of redisSessions) {
    // If the session exists locally, use that data
    if (localSessionMap.has(redisSession.id)) {
      mergedSessions.push(localSessionMap.get(redisSession.id)!);
      // Remove from map so we don't duplicate
      localSessionMap.delete(redisSession.id);
    } else {
      // Create a new entry with default name
      const name = redisSession.search_query 
        ? `Search for: ${redisSession.search_query}` 
        : `Session ${mergedSessions.length + 1}`;
      
      mergedSessions.push({
        id: redisSession.id,
        name: name,
        createdAt: redisSession.created_at,
        lastUsed: redisSession.last_activity
      });
      
      // Also save this to localStorage for future use
      saveSession(redisSession.id, name);
    }
  }
  
  // Then add any remaining local sessions (these might be from previous runs)
  localSessionMap.forEach(session => {
    mergedSessions.push(session);
  });
  
  return mergedSessions;
};

/**
 * Saves a session to localStorage
 * 
 * @param sessionId - The session ID to save
 * @param name - Optional friendly name for the session
 * @returns The stored session object
 */
export const saveSession = (sessionId: string, name?: string): StoredSession => {
  const localSessions = getLocalSessions();
  
  // Check if session already exists
  const existingIndex = localSessions.findIndex(s => s.id === sessionId);
  const timestamp = Date.now();
  
  const sessionObj: StoredSession = {
    id: sessionId,
    name: name || `Session ${localSessions.length + 1}`,
    createdAt: existingIndex >= 0 ? localSessions[existingIndex].createdAt : timestamp,
    lastUsed: timestamp
  };
  
  if (existingIndex >= 0) {
    // Update existing session
    localSessions[existingIndex] = sessionObj;
  } else {
    // Add new session
    localSessions.push(sessionObj);
  }
  
  localStorage.setItem(STORAGE_KEY, JSON.stringify(localSessions));
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
  const localSessions = getLocalSessions();
  const sessionIndex = localSessions.findIndex(s => s.id === sessionId);
  
  if (sessionIndex < 0) return null;
  
  localSessions[sessionIndex] = {
    ...localSessions[sessionIndex],
    ...updates
  };
  
  localStorage.setItem(STORAGE_KEY, JSON.stringify(localSessions));
  return localSessions[sessionIndex];
};

/**
 * Removes a session from localStorage (Note: does not delete from Redis)
 * 
 * @param sessionId - The session ID to remove
 */
export const removeSession = (sessionId: string): void => {
  const localSessions = getLocalSessions();
  const filteredSessions = localSessions.filter(s => s.id !== sessionId);
  localStorage.setItem(STORAGE_KEY, JSON.stringify(filteredSessions));
  
  // Note: This only removes from localStorage, not from Redis
  // To fully delete, the backend would need to provide an endpoint
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
  const sessions = getLocalSessions();
  if (sessions.length === 0) return undefined;
  
  return sessions.sort((a, b) => b.lastUsed - a.lastUsed)[0];
};