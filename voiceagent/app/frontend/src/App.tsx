import { useState, useEffect, useRef, FormEvent } from "react";
import { ZoomIn, Mic, MicOff, Search } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import StatusMessage from "@/components/ui/status-message";
import { Card, CardContent } from "@/components/ui/card";
import { SearchResults } from "@/components/ui/search-results";
import { JobDetails } from "@/components/ui/job-details";

import useRealTime from "@/hooks/useRealtime";
import useAudioRecorder from "@/hooks/useAudioRecorder";
import useAudioPlayer from "@/hooks/useAudioPlayer";
import { Job } from "@/types";

declare global {
    interface Window {
        selectJob: (jobId: string) => void;
    }
}

function App() {
    const [isRecording, setIsRecording] = useState(false);
    const [uiState, setUiState] = useState<{
        search: {
            query: string | null;
            country: string | null;
            results: any[] | null;
            total_count: number;
        };
        current_job: Job | null;
        view_mode: 'search' | 'detail';
    } | null>(null);
    const stateWebSocketRef = useRef<WebSocket | null>(null);

    const { startSession, addUserAudio, inputAudioBufferClear } = useRealTime({
        onWebSocketOpen: () => console.log("WebSocket connection opened"),
        onWebSocketClose: () => console.log("WebSocket connection closed"),
        onWebSocketError: event => console.error("WebSocket error:", event),
        onReceivedError: message => console.error("error", message),
        onReceivedResponseAudioDelta: message => {
            isRecording && playAudio(message.delta);
        },
        onReceivedInputAudioBufferSpeechStarted: () => {
            stopAudioPlayer();
        },
    });

    const { reset: resetAudioPlayer, play: playAudio, stop: stopAudioPlayer } = useAudioPlayer();
    const { 
        start: startAudioRecording, 
        stop: stopAudioRecording,
        toggleMute: toggleMicMute,
        isMuted: isMicMuted 
    } = useAudioRecorder({ onAudioRecorded: addUserAudio });

    const onToggleListening = async () => {
        if (!isRecording) {
            // Reset UI state when starting a new session
            if (stateWebSocketRef.current && stateWebSocketRef.current.readyState === WebSocket.OPEN) {
                stateWebSocketRef.current.send(JSON.stringify({
                    type: 'reset_state'
                }));
            }
            
            startSession();
            await startAudioRecording();
            resetAudioPlayer();
            setIsRecording(true);
        } else {
            await stopAudioRecording();
            stopAudioPlayer();
            inputAudioBufferClear();
            setIsRecording(false);
        }
    };

    // Connect to state WebSocket - no more initial fetch
    useEffect(() => {
        // Connect to WebSocket for state updates
        const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${wsProtocol}//${window.location.host}/api/state/ws`;
        const ws = new WebSocket(wsUrl);
        
        ws.onopen = () => {
            console.log("State WebSocket connected");
        };
        
        ws.onmessage = (event) => {
            const message = JSON.parse(event.data);
            if (message.type === 'state_update') {
                setUiState(message.data);
            }
        };
        
        ws.onerror = (error) => {
            console.error("State WebSocket error:", error);
        };
        
        ws.onclose = () => {
            console.log("State WebSocket disconnected");
            // Optional: attempt to reconnect after a delay
            setTimeout(() => {
                console.log("Attempting to reconnect to state WebSocket...");
                if (stateWebSocketRef.current === ws) { // Only reconnect if this is still the current websocket
                    const newWs = new WebSocket(wsUrl);
                    // Set up the same event handlers
                    // This would be cleaner with a separate function
                    // but for brevity, leaving it here
                    newWs.onopen = ws.onopen;
                    newWs.onmessage = ws.onmessage;
                    newWs.onerror = ws.onerror;
                    newWs.onclose = ws.onclose;
                    stateWebSocketRef.current = newWs;
                }
            }, 3000);
        };
        
        stateWebSocketRef.current = ws;
        
        return () => {
            ws.close();
        };
    }, []);

    // Expose job selection function to window for HTML button clicks
    useEffect(() => {
        window.selectJob = (jobId: string) => {
            console.log("Selected job:", jobId);
            // The assistant will handle this via its tools
        };
    }, []);

    const [searchQuery, setSearchQuery] = useState('');
    const [searchCountry, setSearchCountry] = useState('');
    
    // Handle manual search form submission
    const handleManualSearch = async (e: FormEvent<HTMLFormElement>) => {
        e.preventDefault();
        
        if (!searchQuery.trim()) return;
        
        if (stateWebSocketRef.current && stateWebSocketRef.current.readyState === WebSocket.OPEN) {
            stateWebSocketRef.current.send(JSON.stringify({
                type: 'manual_search',
                data: {
                    query: searchQuery.trim(),
                    country: searchCountry.trim() || null
                }
            }));
        }
    };
    
    // Handle job selection via UI
    const handleJobSelection = (jobId: string) => {
        if (stateWebSocketRef.current && stateWebSocketRef.current.readyState === WebSocket.OPEN) {
            stateWebSocketRef.current.send(JSON.stringify({
                type: 'select_job',
                data: {
                    job_id: jobId
                }
            }));
        }
    };
    
    // Expose job selection function to window for HTML button clicks
    useEffect(() => {
        window.selectJob = handleJobSelection;
    }, []);

    return (
        <div className="flex min-h-screen flex-col bg-background p-4">
            
            
            <div className="computer-container flex-grow rounded-lg p-6">
                <header className="mb-8 flex items-center justify-between border-b border-primary/50 pb-4">
                    <div className="flex items-center space-x-4">
                        <ZoomIn className="h-8 w-8 text-primary animate-pulse" />
                        <h1 className="text-3xl font-semibold tracking-tight text-foreground">
                            Job Search Agent
                        </h1>
                    </div>
                </header>

                <main className="grid grid-cols-1 gap-6">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                        {/* Voice Interface Card */}
                        <Card className="computer-container bg-card/50">
                            <CardContent className="p-4">
                                <h2 className="text-lg font-semibold tracking-tight mb-4">Voice Interface</h2>
                                <div className="flex flex-col items-center space-y-4">
                                    <Button
                                        onClick={onToggleListening}
                                        className={`h-16 w-full ${
                                            isRecording 
                                                ? "bg-destructive hover:bg-destructive/90" 
                                                : "bg-primary hover:bg-primary/90"
                                        }`}
                                    >
                                        {isRecording ? "STOP LISTENING" : "START TALKING TO ASSISTANT"}
                                    </Button>
                                    <Button
                                        onClick={toggleMicMute}
                                        variant="outline"
                                        className="w-full flex items-center justify-center gap-2"
                                    >
                                        {isMicMuted ? (
                                            <>
                                                <MicOff className="h-4 w-4" />
                                                UNMUTE MICROPHONE
                                            </>
                                        ) : (
                                            <>
                                                <Mic className="h-4 w-4" />
                                                MUTE MICROPHONE
                                            </>
                                        )}
                                    </Button>
                                    <StatusMessage isRecording={isRecording} />
                                </div>
                            </CardContent>
                        </Card>

                        {/* Search Status Card */}
                        <Card className="computer-container bg-card/50">
                            <CardContent className="p-4">
                                <h2 className="text-lg font-semibold tracking-tight mb-4">Search Status</h2>
                                
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
                                            />
                                            <Button type="submit" variant="outline" size="icon">
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
                                        />
                                    </div>
                                </form>
                                
                                <div className="space-y-4">
                                    <div className="flex flex-col space-y-2">
                                        <span className="text-sm text-muted-foreground">CURRENT QUERY:</span>
                                        <span className="computer-text">{uiState?.search.query || "no active search"}</span>
                                    </div>
                                    <div className="flex flex-col space-y-2">
                                        <span className="text-sm text-muted-foreground">LOCATION:</span>
                                        <span className="computer-text">{uiState?.search.country || "not specified"}</span>
                                    </div>
                                    {uiState?.current_job && (
                                        <div className="flex flex-col space-y-2">
                                            <span className="text-sm text-muted-foreground">CURRENT JOB:</span>
                                            <span className="computer-text">{uiState.current_job.title}</span>
                                            <span className="text-sm text-muted-foreground">ID: {uiState.current_job.jobId}</span>
                                        </div>
                                    )}
                                </div>
                            </CardContent>
                        </Card>
                    </div>

                    {/* Content Area */}
                    <Card className="computer-container bg-card/50">
                        <CardContent className="p-4">
                            {uiState?.view_mode === 'search' && uiState.search.results && (
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
                                        if (stateWebSocketRef.current) {
                                            stateWebSocketRef.current.send(JSON.stringify({
                                                type: 'view_search_results'
                                            }));
                                        }
                                    }}
                                />
                            )}
                        </CardContent>
                    </Card>
                </main>
            </div>

            <footer className="mt-4 text-center text-sm text-primary/60">
                JOB SEARCH v1.0
            </footer>
        </div>
    );
}

export default App;
