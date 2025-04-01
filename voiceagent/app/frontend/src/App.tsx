import { useState, useEffect, FormEvent, useCallback, useRef } from "react";
import { ZoomIn, Mic, MicOff, Search, AlertCircle, RefreshCw } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import StatusMessage from "@/components/ui/status-message";
import { Card, CardContent } from "@/components/ui/card";
import { SearchResults } from "@/components/ui/search-results";
import { JobDetails } from "@/components/ui/job-details";
import { SessionBadge } from "@/components/ui/session-badge";
import { SessionSwitcher } from "@/components/ui/session-switcher";

import useRealTime from "@/hooks/useRealtime";
import useAudioRecorder from "@/hooks/useAudioRecorder";
import useAudioPlayer from "@/hooks/useAudioPlayer";
import useWebSocket from "@/hooks/useWebSocket";
import { fetchSessionId } from "@/utils/websocket";
import { UIState } from "@/types/state";
import { getMostRecentSession, saveSession, touchSession } from "@/utils/sessions";

// Define retry config outside the component for stable reference
const webSocketRetryConfig = {
    maxAttempts: 5,
    initialDelay: 1000,
    maxDelay: 15000
};

declare global {
    interface Window {
        selectJob: (jobId: string) => void;
    }
}

function App() {
    const [isRecording, setIsRecording] = useState(false);
    const [sessionId, setSessionId] = useState<string | undefined>(undefined);
    const [uiState, setUiState] = useState<UIState | null>(null);
    const [isInitializing, setIsInitializing] = useState(true);
    
    // Initialize session management
    useEffect(() => {
        const initSession = async () => {
            setIsInitializing(true);
            try {
                // Check for recent session first
                const recentSession = getMostRecentSession();
                
                if (recentSession) {
                    // Use the most recent session
                    setSessionId(recentSession.id);
                    touchSession(recentSession.id); // Update last used timestamp
                    console.log("Using existing session:", recentSession.id);
                } else {
                    // Create a new session
                    const newSessionId = await fetchSessionId();
                    setSessionId(newSessionId);
                    saveSession(newSessionId);
                    console.log("Created new session:", newSessionId);
                }
            } catch (error) {
                console.error("Failed to initialize session:", error);
            } finally {
                setIsInitializing(false);
            }
        };
        
        initSession();
    }, []);

    // --- Define stable WebSocket callbacks (excluding onMessage for now) --- 
    const handleWebSocketStateUpdate = useCallback((state: UIState) => {
        setUiState(state);
    }, []); // Dependency: setUiState is stable

    const handleWebSocketError = useCallback((error: Event | Error) => {
        console.error('WebSocket error:', error);
    }, []);

    const handleWebSocketOpen = useCallback(() => {
        console.log('WebSocket connection opened');
    }, []);

    const handleWebSocketClose = useCallback((event?: CloseEvent) => {
        console.log('WebSocket connection closed', event?.code);
        if (event && (event.code === 1011 || event.code === 1013 || event.code === 1001)) {
            console.warn('Connection closed due to server issue. Code:', event.code);
        }
    }, []);
    // --- End WebSocket Callbacks ---

    // --- Ref for the WebSocket message handler --- 
    const webSocketMessageHandlerRef = useRef<((message: any) => void) | null>(null);

    // --- Initialize WebSocket Connection --- 
    // Pass the ref for the message handler and stable retry config
    const { 
        isConnected: isStateWsConnected, 
        sendMessage: sendStateWsMessage, 
        connectionError,
        reconnect: reconnectWebSocket
    } = useWebSocket({
        onMessageRef: webSocketMessageHandlerRef, 
        onStateUpdate: handleWebSocketStateUpdate, 
        sessionId: sessionId || null, 
        onError: handleWebSocketError, 
        onOpen: handleWebSocketOpen, 
        onClose: handleWebSocketClose, 
        retry: webSocketRetryConfig // Use the stable config object
    });
    // --- End WebSocket Connection ---

    // --- Initialize Realtime Hook --- 
    // Depends on sendStateWsMessage from useWebSocket
    const { 
        startSession, 
        addUserAudio, 
        inputAudioBufferClear, 
        handleIncomingMessage // Get the message handler
    } = useRealTime({
        sessionId,
        // Pass the actual sendMessage function from useWebSocket
        sendMessage: sendStateWsMessage, 
        onReceivedError: message => console.error("Realtime error:", message),
        onReceivedResponseAudioDelta: message => {
            isRecording && playAudio(message.delta);
        },
        onReceivedInputAudioBufferSpeechStarted: () => {
            stopAudioPlayer();
        },
        // Add other necessary callbacks from useRealTime here
    });
    // --- End Realtime Hook ---

    // --- Define stable WebSocket Message Handler --- 
    // This depends on handleIncomingMessage from useRealTime
    const handleWebSocketMessage = useCallback((message: any) => {
        // Route non-UI messages to the useRealTime hook
        handleIncomingMessage(message);
    }, [handleIncomingMessage]); // Dependency: handleIncomingMessage

    // --- Update the ref with the stable handler --- 
    // This effect runs whenever the stable handleWebSocketMessage function changes
    useEffect(() => {
        webSocketMessageHandlerRef.current = handleWebSocketMessage;
    }, [handleWebSocketMessage]);

    // Initialize audio player and recorder
    const { reset: resetAudioPlayer, play: playAudio, stop: stopAudioPlayer } = useAudioPlayer();
    const { 
        start: startAudioRecording, 
        stop: stopAudioRecording,
        toggleMute: toggleMicMute,
        isMuted: isMicMuted 
    } = useAudioRecorder({ onAudioRecorded: addUserAudio });

    // Toggle listening state
    const onToggleListening = async () => {
        if (!isRecording) {
            // Start the audio session without resetting state
            startSession(); // This now uses the passed sendMessage
            await startAudioRecording();
            resetAudioPlayer();
            setIsRecording(true);
        } else {
            await stopAudioRecording();
            stopAudioPlayer();
            inputAudioBufferClear(); // This now uses the passed sendMessage
            setIsRecording(false);
        }
    };
    
    // Function to explicitly reset the conversation state
    const resetConversation = () => {
        if (isStateWsConnected) {
            sendStateWsMessage({
                type: 'reset_state'
            });
        }
    };

    const [searchQuery, setSearchQuery] = useState('');
    const [searchCountry, setSearchCountry] = useState('');
    
    // Switch to a different session
    const handleSelectSession = (newSessionId: string) => {
        if (isRecording) {
            // Stop current recording before switching
            stopAudioRecording();
            stopAudioPlayer();
            inputAudioBufferClear();
            setIsRecording(false);
        }
        
        setSessionId(newSessionId);
        setUiState(null);
        touchSession(newSessionId);
    };
    
    // Create a new session
    const handleCreateNewSession = async () => {
        if (isRecording) {
            // Stop current recording before creating new session
            stopAudioRecording();
            stopAudioPlayer();
            inputAudioBufferClear();
            setIsRecording(false);
        }
        
        try {
            const newSessionId = await fetchSessionId();
            setSessionId(newSessionId);
            setUiState(null);
            saveSession(newSessionId);
        } catch (error) {
            console.error("Failed to create new session:", error);
        }
    };
    
    // Handle manual search form submission
    const handleManualSearch = async (e: FormEvent<HTMLFormElement>) => {
        e.preventDefault();
        
        if (!searchQuery.trim()) return;
        
        if (isStateWsConnected) {
            sendStateWsMessage({
                type: 'manual_search',
                data: {
                    query: searchQuery.trim(),
                    country: searchCountry.trim() || null
                }
            });
        }
    };
    
    // Handle job selection via UI
    const handleJobSelection = (jobId: string) => {
        if (isStateWsConnected) {
            sendStateWsMessage({
                type: 'select_job',
                data: {
                    job_id: jobId
                }
            });
        }
    };
    
    // Expose job selection function to window for HTML button clicks
    useEffect(() => {
        window.selectJob = handleJobSelection;
    }, []);

    return (
        <div className="flex min-h-screen flex-col bg-background p-4">
            <div className="computer-container flex-grow rounded-lg p-6">
                <header className="mb-8 flex flex-col md:flex-row md:items-center md:justify-between border-b border-primary/50 pb-4 gap-4">
                    <div className="flex items-center space-x-4">
                        <ZoomIn className="h-8 w-8 text-primary animate-pulse" />
                        <h1 className="text-3xl font-semibold tracking-tight text-foreground">
                            Job Search Agent
                        </h1>
                    </div>
                    
                    <div className="w-full md:w-[260px]">
                        <SessionSwitcher 
                            currentSessionId={sessionId}
                            onSelectSession={handleSelectSession}
                            onCreateNewSession={handleCreateNewSession}
                        />
                    </div>
                </header>

                <main className="grid grid-cols-1 gap-6">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                        {/* Voice Interface Card */}
                        <Card className="computer-container bg-card/50">
                            <CardContent className="p-4">
                                <div className="flex items-center justify-between mb-4">
                                    <h2 className="text-lg font-semibold tracking-tight">Voice Interface</h2>
                                    {sessionId && <SessionBadge sessionId={sessionId} compact />}
                                </div>
                                <div className="flex flex-col items-center space-y-4">
                                    <Button
                                        onClick={onToggleListening}
                                        className={`h-16 w-full ${
                                            isRecording 
                                                ? "bg-destructive hover:bg-destructive/90" 
                                                : "bg-primary hover:bg-primary/90"
                                        }`}
                                        disabled={!sessionId || isInitializing || !isStateWsConnected}
                                    >
                                        {isRecording ? "STOP LISTENING" : "START TALKING TO ASSISTANT"}
                                    </Button>
                                    <div className="flex w-full gap-2">
                                        <Button
                                            onClick={toggleMicMute}
                                            variant="outline"
                                            className="flex-1 flex items-center justify-center gap-2"
                                            disabled={!isRecording}
                                        >
                                            {isMicMuted ? (
                                                <>
                                                    <MicOff className="h-4 w-4" />
                                                    UNMUTE MIC
                                                </>
                                            ) : (
                                                <>
                                                    <Mic className="h-4 w-4" />
                                                    MUTE MIC
                                                </>
                                            )}
                                        </Button>
                                        <Button
                                            onClick={resetConversation}
                                            variant="outline"
                                            className="flex-1"
                                            disabled={!isStateWsConnected}
                                        >
                                            RESET CONVERSATION
                                        </Button>
                                    </div>
                                    <StatusMessage isRecording={isRecording} />
                                    
                                    {/* Connection status and errors */}
                                    {isInitializing && (
                                        <div className="text-sm text-amber-600">
                                            Initializing session...
                                        </div>
                                    )}
                                    
                                    {!isInitializing && !isStateWsConnected && !connectionError && (
                                        <div className="text-sm text-amber-600 flex items-center gap-2">
                                            <AlertCircle className="h-4 w-4" />
                                            <span>Connecting to server...</span>
                                        </div>
                                    )}
                                    
                                    {connectionError && (
                                        <div className="text-sm text-destructive border border-destructive/30 bg-destructive/10 p-3 rounded-md flex flex-col gap-2 w-full">
                                            <div className="flex items-center gap-2">
                                                <AlertCircle className="h-4 w-4 shrink-0" />
                                                <span>Connection error: {connectionError.message}</span>
                                            </div>
                                            <Button 
                                                variant="outline" 
                                                size="sm" 
                                                className="flex items-center gap-2 self-end"
                                                onClick={() => reconnectWebSocket()}
                                            >
                                                <RefreshCw className="h-3 w-3" />
                                                Reconnect
                                            </Button>
                                        </div>
                                    )}
                                </div>
                            </CardContent>
                        </Card>

                        {/* Search Status Card */}
                        <Card className="computer-container bg-card/50">
                            <CardContent className="p-4">
                                <div className="flex items-center justify-between mb-4">
                                    <h2 className="text-lg font-semibold tracking-tight">Search Status</h2>
                                    {sessionId && <SessionBadge sessionId={sessionId} compact />}
                                </div>
                                
                                {/* Add manual search form */}
                                <form onSubmit={handleManualSearch} className="mb-4 space-y-3">
                                    <div className="space-y-2">
                                        <label className="text-sm text-muted-foreground">JOB QUERY:</label>
                                        <div className="flex gap-2">
                                            <Input 
                                                value={searchQuery}
                                                onChange={(e: React.ChangeEvent<HTMLInputElement>) => setSearchQuery(e.target.value)}
                                                placeholder="Enter job title or skills"
                                                className="flex-1"
                                                disabled={!sessionId || isInitializing || !isStateWsConnected}
                                            />
                                            <Button 
                                                type="submit" 
                                                variant="outline" 
                                                size="icon" 
                                                disabled={!sessionId || isInitializing || !isStateWsConnected}
                                            >
                                                <Search className="h-4 w-4" />
                                            </Button>
                                        </div>
                                    </div>
                                    
                                    <div className="space-y-2">
                                        <label className="text-sm text-muted-foreground">COUNTRY (OPTIONAL):</label>
                                        <Input 
                                            value={searchCountry}
                                            onChange={(e: React.ChangeEvent<HTMLInputElement>) => setSearchCountry(e.target.value)}
                                            placeholder="e.g., United States"
                                            disabled={!sessionId || isInitializing || !isStateWsConnected}
                                        />
                                    </div>
                                </form>
                                
                                <div className="space-y-4">
                                    <div className="flex flex-col space-y-2">
                                        <span className="text-sm text-muted-foreground">CURRENT QUERY:</span>
                                        <span className="computer-text">{uiState?.search?.query || "no active search"}</span>
                                    </div>
                                    <div className="flex flex-col space-y-2">
                                        <span className="text-sm text-muted-foreground">LOCATION:</span>
                                        <span className="computer-text">{uiState?.search?.country || "not specified"}</span>
                                    </div>
                                    {uiState?.current_job && (
                                        <div className="flex flex-col space-y-2">
                                            <span className="text-sm text-muted-foreground">CURRENT JOB:</span>
                                            <span className="computer-text">{uiState.current_job.title}</span>
                                            <span className="text-sm text-muted-foreground">ID: {uiState.current_job.jobId}</span>
                                        </div>
                                    )}
                                    
                                    {/* Connection status indicator */}
                                    <div className="flex items-center justify-between pt-2 border-t border-primary/20">
                                        <span className="text-xs text-muted-foreground">Connection:</span>
                                        <div className={`flex items-center gap-2 ${isStateWsConnected ? 'text-green-500' : 'text-amber-500'}`}>
                                            <div className={`w-2 h-2 rounded-full ${isStateWsConnected ? 'bg-green-500' : 'bg-amber-500'}`}></div>
                                            <span className="text-xs">{isStateWsConnected ? 'Online' : 'Offline'}</span>
                                        </div>
                                    </div>
                                </div>
                            </CardContent>
                        </Card>
                    </div>

                    {/* Content Area */}
                    <Card className="computer-container bg-card/50">
                        <CardContent className="p-4">
                            <div className="flex items-center justify-between mb-4">
                                <h2 className="text-lg font-semibold tracking-tight">
                                    {uiState?.view_mode === 'detail' ? 'Job Details' : 'Search Results'}
                                </h2>
                                {sessionId && <SessionBadge sessionId={sessionId} compact />}
                            </div>
                            
                            {uiState?.view_mode === 'search' && uiState.search?.results && (
                                <SearchResults 
                                    results={uiState.search.results}
                                    totalCount={uiState.search.total_count}
                                    onSelectJob={handleJobSelection}
                                />
                            )}
                            {uiState?.view_mode === 'detail' && uiState.current_job && (
                                <JobDetails 
                                    job={uiState.current_job} 
                                    onBackToResults={() => {
                                        if (isStateWsConnected) {
                                            sendStateWsMessage({
                                                type: 'view_search_results'
                                            });
                                        }
                                    }}
                                />
                            )}
                            {(isInitializing || !sessionId) && (
                                <div className="flex items-center justify-center h-40 text-muted-foreground">
                                    <div className="text-center">
                                        <div className="text-lg">Initializing Session</div>
                                        <div className="mt-2 text-sm">Please wait...</div>
                                    </div>
                                </div>
                            )}
                            
                            {/* Show better connection error message */}
                            {!isInitializing && !isStateWsConnected && (
                                <div className="flex items-center justify-center h-40">
                                    <div className="text-center max-w-md">
                                        <div className="text-lg text-amber-600 mb-2">Connection Unavailable</div>
                                        <div className="text-sm text-muted-foreground mb-4">
                                            {connectionError 
                                                ? `Unable to connect: ${connectionError.message}` 
                                                : "The service is currently unavailable. Please check your connection."}
                                        </div>
                                        <Button 
                                            onClick={() => reconnectWebSocket()}
                                            className="flex items-center gap-2"
                                            variant="outline"
                                        >
                                            <RefreshCw className="h-4 w-4" />
                                            Try Again
                                        </Button>
                                    </div>
                                </div>
                            )}
                        </CardContent>
                    </Card>
                </main>
            </div>

            <footer className="mt-4 text-center text-sm text-primary/60">
                JOB SEARCH v1.0 {sessionId && (
                    <span className="ml-2">| <SessionBadge sessionId={sessionId} inline /></span>
                )}
            </footer>
        </div>
    );
}

export default App;
