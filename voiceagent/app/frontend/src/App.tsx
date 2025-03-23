import { useState, useEffect } from "react";
import { Power, Mic, MicOff } from "lucide-react";

import { Button } from "@/components/ui/button";
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
    const [systemStatus] = useState("STANDBY");
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
    const [statusMessage, setStatusMessage] = useState<{text: string, remaining_seconds: number} | null>(null);

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

    // Poll the state from /api/state periodically
    useEffect(() => {
        const fetchState = () => {
            fetch("/api/state")
                .then(res => res.json())
                .then(state => {
                    setUiState(state.ui);
                    setStatusMessage(state.status_message);
                });
        };
        const intervalId = setInterval(fetchState, 1000);
        return () => clearInterval(intervalId);
    }, []);

    // Expose job selection function to window for HTML button clicks
    useEffect(() => {
        window.selectJob = (jobId: string) => {
            console.log("Selected job:", jobId);
            // The assistant will handle this via its tools
        };
    }, []);

    const renderMessageContent = (text: string) => {
        return <div className="message-content" dangerouslySetInnerHTML={{ __html: text }} />;
    };

    const [progress, setProgress] = useState(100);

    useEffect(() => {
        if (statusMessage) {
            setProgress(100);
            const interval = setInterval(() => {
                setProgress((prev) => Math.max(0, prev - (100 / statusMessage.remaining_seconds)));
            }, 1000);
            return () => clearInterval(interval);
        }
    }, [statusMessage]);

    const formatTime = (seconds: number) => {
        return Math.ceil(seconds);
    };

    return (
        <div className="flex min-h-screen flex-col bg-background p-4">
            {statusMessage && (
                <div className="fixed top-4 left-1/2 transform -translate-x-1/2 z-50 w-full max-w-4xl px-4">
                    <div className="system-message rounded-lg shadow-lg border border-primary/30">
                        <div className="system-message-header">
                            <div className="system-message-header-icon" />
                            <div className="message-duration">
                                {formatTime(statusMessage.remaining_seconds)}s
                            </div>
                        </div>
                        <div className="system-message-content">
                            {renderMessageContent(statusMessage.text)}
                            <div className="message-progress">
                                <div 
                                    className="message-progress-bar" 
                                    style={{ width: `${progress}%` }} 
                                />
                            </div>
                        </div>
                    </div>
                </div>
            )}
            
            <div className="computer-container flex-grow rounded-lg p-6">
                <header className="mb-8 flex items-center justify-between border-b border-primary/50 pb-4">
                    <div className="flex items-center space-x-4">
                        <Power className="h-8 w-8 text-primary animate-pulse" />
                        <h1 className="computer-text text-3xl font-bold tracking-wider">MICROSOFT JOB SEARCH ASSISTANT</h1>
                    </div>
                    <div className="flex items-center space-x-2">
                        <span className="text-sm">STATUS:</span>
                        <span className={`text-sm ${systemStatus === "ACTIVE" ? "text-green-400" : "text-primary"}`}>
                            {systemStatus}
                        </span>
                    </div>
                </header>

                <main className="grid grid-cols-1 gap-6">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                        {/* Voice Interface Card */}
                        <Card className="computer-container bg-card/50">
                            <CardContent className="p-4">
                                <h2 className="computer-text mb-4 text-xl">VOICE INTERFACE</h2>
                                <div className="flex flex-col items-center space-y-4">
                                    <Button
                                        onClick={onToggleListening}
                                        className={`h-16 w-full ${
                                            isRecording 
                                                ? "bg-destructive hover:bg-destructive/90" 
                                                : "bg-primary hover:bg-primary/90"
                                        }`}
                                    >
                                        {isRecording ? "TERMINATE INPUT" : "INITIATE VOICE COMMAND"}
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
                                <h2 className="computer-text mb-4 text-xl">SEARCH STATUS</h2>
                                <div className="space-y-4">
                                    <div className="flex flex-col space-y-2">
                                        <span className="text-sm text-muted-foreground">QUERY:</span>
                                        <span className="computer-text">{uiState?.search.query || "NO ACTIVE SEARCH"}</span>
                                    </div>
                                    <div className="flex flex-col space-y-2">
                                        <span className="text-sm text-muted-foreground">LOCATION:</span>
                                        <span className="computer-text">{uiState?.search.country || "NOT SPECIFIED"}</span>
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
                                />
                            )}
                            {uiState?.view_mode === 'detail' && uiState.current_job && (
                                <JobDetails job={uiState.current_job} />
                            )}
                        </CardContent>
                    </Card>
                </main>
            </div>

            <footer className="mt-4 text-center text-sm text-primary/60">
                MICROSOFT JOB SEARCH v1.0
            </footer>
        </div>
    );
}

export default App;
