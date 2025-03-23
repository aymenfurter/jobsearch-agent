from dataclasses import dataclass
import asyncio
import json
import logging
from enum import Enum, auto
from typing import Any, Callable, Dict, Optional, Set, Union

import aiohttp
from aiohttp import web
from azure.core.credentials import AzureKeyCredential
from azure.identity import DefaultAzureCredential, get_bearer_token_provider

# Configure logging
logger = logging.getLogger("voicerag")

# Message types
class MessageType(Enum):
    SESSION_CREATED = "session.created"
    SESSION_UPDATE = "session.update"
    RESPONSE_OUTPUT_ADDED = "response.output_item.added"
    CONVERSATION_ITEM_CREATED = "conversation.item.created"
    FUNCTION_CALL_ARGS_DELTA = "response.function_call_arguments.delta"
    FUNCTION_CALL_ARGS_DONE = "response.function_call_arguments.done"
    RESPONSE_OUTPUT_DONE = "response.output_item.done"
    RESPONSE_DONE = "response.done"

class ToolResultDirection(Enum):
    TO_SERVER = auto()
    TO_CLIENT = auto()

@dataclass
class RTMTConfig:
    """Configuration for RT Middle Tier."""
    endpoint: str
    deployment: str
    api_version: str = "2024-10-01-preview"
    model: Optional[str] = None
    system_message: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    disable_audio: Optional[bool] = None
    voice_choice: Optional[str] = None

@dataclass
class ToolResult:
    """Result from a tool execution."""
    text: str
    destination: ToolResultDirection

    def to_text(self) -> str:
        """Convert tool result to text format."""
        if self.text is None:
            return ""
        return self.text if isinstance(self.text, str) else json.dumps(self.text)

class Tool:
    """Tool definition and execution."""
    def __init__(self, target: Callable[..., ToolResult], schema: Any):
        self.target = target
        self.schema = schema

class RTToolCall:
    """Represents an ongoing tool call."""
    def __init__(self, tool_call_id: str, previous_id: str):
        self.tool_call_id = tool_call_id
        self.previous_id = previous_id

class WebSocketMessageHandler:
    """Handles WebSocket message processing."""
    @staticmethod
    async def process_client_message(message: Dict[str, Any], session: Dict[str, Any], tools: Dict[str, Tool]) -> Optional[str]:
        """Process messages from client to server."""
        if message["type"] == MessageType.SESSION_UPDATE.value:
            WebSocketMessageHandler._update_session_config(session, tools)
            return json.dumps({"type": MessageType.SESSION_UPDATE.value, "session": session})
        return None

    @staticmethod
    def _update_session_config(session: Dict[str, Any], tools: Dict[str, Tool]) -> None:
        """Update session configuration with tool settings."""
        session["tool_choice"] = "auto" if tools else "none"
        session["tools"] = [tool.schema for tool in tools.values()]

class RTMiddleTier:
    """Real-Time Middle Tier for handling WebSocket communications."""
    
    def __init__(self, endpoint: str, deployment: str, 
                 credentials: Union[AzureKeyCredential, DefaultAzureCredential], 
                 voice_choice: Optional[str] = None):
        self.config = RTMTConfig(endpoint=endpoint, deployment=deployment, voice_choice=voice_choice)
        self.tools: Dict[str, Tool] = {}
        self._tools_pending: Dict[str, RTToolCall] = {}
        self._connected_clients: Set[web.WebSocketResponse] = set()
        
        if isinstance(credentials, AzureKeyCredential):
            self.key = credentials.key
            self._token_provider = None
        else:
            self.key = None
            self._token_provider = get_bearer_token_provider(
                credentials, 
                "https://cognitiveservices.azure.com/.default"
            )
            self._token_provider()  # Warm up token cache

    async def _process_message_to_client(self, msg: str, client_ws: web.WebSocketResponse, server_ws: web.WebSocketResponse) -> Optional[str]:
        try:
            message = json.loads(msg.data)
            updated_message = msg.data
            if message is not None:
                match message["type"]:
                    case MessageType.SESSION_CREATED.value:
                        session = message["session"]
                        session["instructions"] = ""
                        session["tools"] = []
                        session["voice"] = self.config.voice_choice
                        session["tool_choice"] = "none"
                        session["max_response_output_tokens"] = None
                        updated_message = json.dumps(message)

                    case MessageType.RESPONSE_OUTPUT_ADDED.value:
                        if "item" in message and message["item"]["type"] == "function_call":
                            updated_message = None

                    case MessageType.CONVERSATION_ITEM_CREATED.value:
                        if "item" in message and message["item"]["type"] == "function_call":
                            item = message["item"]
                            if item["call_id"] not in self._tools_pending:
                                self._tools_pending[item["call_id"]] = RTToolCall(item["call_id"], message["previous_item_id"])
                            updated_message = None
                        elif "item" in message and message["item"]["type"] == "function_call_output":
                            updated_message = None

                    case MessageType.FUNCTION_CALL_ARGS_DELTA.value:
                        updated_message = None
                    
                    case MessageType.FUNCTION_CALL_ARGS_DONE.value:
                        updated_message = None

                    case MessageType.RESPONSE_OUTPUT_DONE.value:
                        if "item" in message and message["item"]["type"] == "function_call":
                            item = message["item"]
                            tool_call = self._tools_pending[message["item"]["call_id"]]
                            tool = self.tools[item["name"]]
                            args = item["arguments"]
                            result = await tool.target(json.loads(args))
                            await server_ws.send_json({
                                "type": "conversation.item.create",
                                "item": {
                                    "type": "function_call_output",
                                    "call_id": item["call_id"],
                                    "output": result.to_text() if result.destination == ToolResultDirection.TO_SERVER else ""
                                }
                            })
                            if result.destination == ToolResultDirection.TO_CLIENT:
                                await client_ws.send_json({
                                    "type": "extension.middle_tier_tool_response",
                                    "previous_item_id": tool_call.previous_id,
                                    "tool_name": item["name"],
                                    "tool_result": result.to_text()
                                })
                            updated_message = None

                    case MessageType.RESPONSE_DONE.value:
                        if len(self._tools_pending) > 0:
                            self._tools_pending.clear()
                            await server_ws.send_json({
                                "type": "response.create"
                            })
                        if "response" in message and "output" in message["response"]:
                            output = message["response"]["output"]
                            if isinstance(output, list):
                                # Remove function calls from output safely
                                new_output = [item for item in output if item.get("type") != "function_call"]
                                if len(new_output) != len(output):
                                    message["response"]["output"] = new_output
                                    updated_message = json.dumps(message)

            return updated_message
        except Exception as e:
            logger.error(f"Error processing message: {str(e)}")
            return msg.data 

    async def _process_message_to_server(self, msg: str, ws: web.WebSocketResponse) -> Optional[str]:
        message = json.loads(msg.data)
        updated_message = msg.data
        if message is not None:
            match message["type"]:
                case MessageType.SESSION_UPDATE.value:
                    session = message["session"]
                    if self.config.system_message is not None:
                        session["instructions"] = self.config.system_message
                    if self.config.temperature is not None:
                        session["temperature"] = self.config.temperature
                    if self.config.max_tokens is not None:
                        session["max_response_output_tokens"] = self.config.max_tokens
                    if self.config.disable_audio is not None:
                        session["disable_audio"] = self.config.disable_audio
                    if self.config.voice_choice is not None:
                        session["voice"] = self.config.voice_choice
                    session["tool_choice"] = "auto" if len(self.tools) > 0 else "none"
                    session["tools"] = [tool.schema for tool in self.tools.values()]
                    updated_message = json.dumps(message)

        return updated_message

    # Audio flow explanation:
    # 1. Frontend: Audio is captured in recorder.ts
    # 2. Frontend: Audio is chunked and base64-encoded by handleAudioData
    # 3. Frontend: Chunks are sent to server via addUserAudio using WebSocket messages
    #             (type "input_audio_buffer.append")
    # 4. Backend: This _forward_messages function in rtmt.py relays chunks to OpenAI realtime socket
    # 5. Backend: Audio responses come back from OpenAI (e.g., "response.audio.delta")
    # 6. Frontend: Audio responses are handled by useAudioPlayer component
    async def _forward_messages(self, ws: web.WebSocketResponse):
        async with aiohttp.ClientSession(base_url=self.config.endpoint) as session:
            params = { "api-version": self.config.api_version, "deployment": self.config.deployment}
            headers = {}
            if "x-ms-client-request-id" in ws.headers:
                headers["x-ms-client-request-id"] = ws.headers["x-ms-client-request-id"]
            if self.key is not None:
                headers = { "api-key": self.key }
            else:
                headers = { "Authorization": f"Bearer {self._token_provider()}" } # NOTE: no async version of token provider, maybe refresh token on a timer?
            async with session.ws_connect("/openai/realtime", headers=headers, params=params) as target_ws:
                async def from_client_to_server():
                    async for msg in ws:
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            new_msg = await self._process_message_to_server(msg, ws)
                            if new_msg is not None:
                                await target_ws.send_str(new_msg)
                        else:
                            print("Error: unexpected message type:", msg.type)
                    
                    # Means it is gracefully closed by the client then time to close the target_ws
                    if target_ws:
                        print("Closing OpenAI's realtime socket connection.")
                        await target_ws.close()
                        
                async def from_server_to_client():
                    async for msg in target_ws:
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            new_msg = await self._process_message_to_client(msg, ws, target_ws)
                            if new_msg is not None:
                                await ws.send_str(new_msg)
                        else:
                            print("Error: unexpected message type:", msg.type)

                try:
                    await asyncio.gather(from_client_to_server(), from_server_to_client())
                except ConnectionResetError:
                    # Ignore the errors resulting from the client disconnecting the socket
                    pass

    async def _websocket_handler(self, request: web.Request):
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        self._connected_clients.add(ws)
        try:
            await self._forward_messages(ws)
        finally:
            self._connected_clients.remove(ws)
        return ws
    
    async def broadcast_message(self, message_type: str, data: Any):
        """Broadcast a message to all connected clients"""
        if not self._connected_clients:
            return
            
        message = {
            "type": message_type,
            "data": data
        }
        
        disconnected = set()
        for ws in self._connected_clients:
            if ws.closed:
                disconnected.add(ws)
                continue
            try:
                await ws.send_json(message)
            except Exception as e:
                logger.error(f"Error sending broadcast: {str(e)}")
                disconnected.add(ws)
        
        # Clean up any disconnected clients
        self._connected_clients.difference_update(disconnected)
    
    def attach_to_app(self, app: web.Application, path: str) -> None:
        """Attach the WebSocket handler to the application."""
        app.router.add_get(path, self._websocket_handler)
