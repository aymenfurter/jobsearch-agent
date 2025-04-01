/**
 * Gets the WebSocket URL with proper protocol and session ID
 * 
 * @param endpoint - The API endpoint (e.g., '/api/state/ws' or '/realtime')
 * @param sessionId - User's session identifier
 * @returns Fully qualified WebSocket URL with session ID
 */
export const getWebSocketUrl = (endpoint: string, sessionId?: string): string => {
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const baseUrl = `${wsProtocol}//${window.location.host}${endpoint}`;
    
    // Append session ID as query parameter if provided
    if (sessionId) {
        return `${baseUrl}?sid=${encodeURIComponent(sessionId)}`;
    }
    
    return baseUrl;
};

/**
 * Fetches a new session ID from the server
 * 
 * @returns Promise resolving to a session ID string
 */
export const fetchSessionId = async (): Promise<string> => {
    try {
        const response = await fetch('/api/session/init');
        if (!response.ok) {
            throw new Error(`Failed to initialize session: ${response.status}`);
        }
        const data = await response.json();
        return data.session_id;
    } catch (error) {
        console.error('Error fetching session ID:', error);
        // Fallback to client-side generated ID in case of failure
        return `fallback-${Math.random().toString(36).substring(2, 15)}`;
    }
};
