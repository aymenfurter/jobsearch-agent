import { useCallback } from "react";

import {
    InputAudioBufferAppendCommand,
    InputAudioBufferClearCommand,
    Message,
    ResponseAudioDelta,
    ResponseAudioTranscriptDelta,
    ResponseDone,
    SessionUpdateCommand,
    ExtensionMiddleTierToolResponse,
    ResponseInputAudioTranscriptionCompleted
} from "@/types";

interface MessageCallbacks {
    onReceivedResponseAudioDelta?: (message: ResponseAudioDelta) => void;
    onReceivedInputAudioBufferSpeechStarted?: (message: Message) => void;
    onReceivedResponseDone?: (message: ResponseDone) => void;
    onReceivedExtensionMiddleTierToolResponse?: (message: ExtensionMiddleTierToolResponse) => void;
    onReceivedResponseAudioTranscriptDelta?: (message: ResponseAudioTranscriptDelta) => void;
    onReceivedInputAudioTranscriptionCompleted?: (message: ResponseInputAudioTranscriptionCompleted) => void;
    onReceivedError?: (message: Message) => void;
}

interface ConfigParameters {
    enableInputAudioTranscription?: boolean;
    sessionId?: string;  // Keep session ID if needed for logic
    sendMessage: (message: any) => boolean; // Accept sendMessage function
}

type Parameters = ConfigParameters & MessageCallbacks;

interface RealtimeHook {
    startSession: () => void;
    addUserAudio: (base64Audio: string) => void;
    inputAudioBufferClear: () => void;
    // Add a function to handle incoming messages
    handleIncomingMessage: (message: any) => void; 
}

export default function useRealTime(params: Parameters): RealtimeHook {
    const {
        enableInputAudioTranscription,
        sendMessage, // Use provided sendMessage
        onReceivedResponseDone,
        onReceivedResponseAudioDelta,
        onReceivedResponseAudioTranscriptDelta,
        onReceivedInputAudioBufferSpeechStarted,
        onReceivedExtensionMiddleTierToolResponse,
        onReceivedInputAudioTranscriptionCompleted,
        onReceivedError
    } = params;

    const startSession = useCallback(() => {
        const command: SessionUpdateCommand = {
            type: "session.update",
            session: {
                turn_detection: {
                    type: "server_vad"
                }
            }
        };

        if (enableInputAudioTranscription) {
            command.session.input_audio_transcription = {
                model: "whisper-1"
            };
        }

        sendMessage(command);
    }, [sendMessage, enableInputAudioTranscription]);

    const addUserAudio = useCallback((base64Audio: string) => {
        const command: InputAudioBufferAppendCommand = {
            type: "input_audio_buffer.append",
            audio: base64Audio
        };

        sendMessage(command);
    }, [sendMessage]);

    const inputAudioBufferClear = useCallback(() => {
        const command: InputAudioBufferClearCommand = {
            type: "input_audio_buffer.clear"
        };

        sendMessage(command);
    }, [sendMessage]);

    const handleIncomingMessage = useCallback((message: any) => {
        // No need to parse again, assume message is already parsed JSON from useWebSocket
        switch (message.type) {
            case "response.done":
                onReceivedResponseDone?.(message as ResponseDone);
                break;
            case "response.audio.delta":
                onReceivedResponseAudioDelta?.(message as ResponseAudioDelta);
                break;
            case "response.audio_transcript.delta":
                onReceivedResponseAudioTranscriptDelta?.(message as ResponseAudioTranscriptDelta);
                break;
            case "input_audio_buffer.speech_started":
                onReceivedInputAudioBufferSpeechStarted?.(message);
                break;
            case "conversation.item.input_audio_transcription.completed":
                onReceivedInputAudioTranscriptionCompleted?.(message as ResponseInputAudioTranscriptionCompleted);
                break;
            case "extension.middle_tier_tool.response":
                // Note: This might be redundant if UI updates are handled by UIState
                onReceivedExtensionMiddleTierToolResponse?.(message as ExtensionMiddleTierToolResponse);
                break;
            case "error":
                onReceivedError?.(message);
                break;
            // Add default case or logging for unhandled message types if needed
            default:
                // console.log('useRealTime received unhandled message type:', message.type);
                break;
        }
    }, [
        onReceivedResponseDone,
        onReceivedResponseAudioDelta,
        onReceivedResponseAudioTranscriptDelta,
        onReceivedInputAudioBufferSpeechStarted,
        onReceivedExtensionMiddleTierToolResponse,
        onReceivedInputAudioTranscriptionCompleted,
        onReceivedError
    ]);

    return { startSession, addUserAudio, inputAudioBufferClear, handleIncomingMessage };
}
