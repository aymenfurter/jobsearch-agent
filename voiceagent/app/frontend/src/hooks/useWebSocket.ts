import { useRef, useEffect } from 'react';
import { UIState } from '@/types/state';
import { getWebSocketUrl } from '@/utils/websocket';

interface UseWebSocketProps {
    onStateUpdate: (state: UIState) => void;
}

export function useWebSocket({ onStateUpdate }: UseWebSocketProps) {
    const wsRef = useRef<WebSocket | null>(null);

    const setupWebSocket = () => {
        const ws = new WebSocket(getWebSocketUrl());
        
        ws.onopen = () => console.log("State WebSocket connected");
        ws.onmessage = (event) => {
            const message = JSON.parse(event.data);
            if (message.type === 'state_update') {
                onStateUpdate(message.data);
            }
        };
        ws.onerror = (error) => console.error("State WebSocket error:", error);
        ws.onclose = () => handleWebSocketClose(ws);
        
        return ws;
    };

    const handleWebSocketClose = (ws: WebSocket) => {
        console.log("State WebSocket disconnected");
        setTimeout(() => {
            if (wsRef.current === ws) {
                wsRef.current = setupWebSocket();
            }
        }, 3000);
    };

    useEffect(() => {
        wsRef.current = setupWebSocket();
        return () => wsRef.current?.close();
    }, []);

    return wsRef;
}
