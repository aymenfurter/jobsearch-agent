from dataclasses import dataclass
import asyncio
import json
import logging
from enum import Enum
from typing import Any, Callable, Dict, Optional, Set, Union, TYPE_CHECKING

import aiohttp
from aiohttp import web
from azure.core.credentials import AzureKeyCredential
from azure.identity import DefaultAzureCredential, get_bearer_token_provider

# Local imports - import tool-related classes from job_tools
from job_tools import ToolDefinition, ToolResult, ToolResultDirection

if TYPE_CHECKING:
    from app import SessionState # Avoid circular import

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
    INPUT_AUDIO_BUFFER_APPEND = "input_audio_buffer.append"
    INPUT_AUDIO_BUFFER_CLEAR = "input_audio_buffer.clear"
    RESPONSE_CREATE = "response.create"
    EXTENSION_MIDDLE_TIER_TOOL_RESPONSE = "extension.middle_tier_tool.response"
    CONVERSATION_ITEM_CREATE = "conversation.item.create"
    FUNCTION_CALL_OUTPUT = "function_call_output"
    FUNCTION_CALL = "function_call"
    # Add UI message types (can be strings directly too)
    UI_RESET_STATE = "reset_state"
    UI_MANUAL_SEARCH = "manual_search"
    UI_SELECT_JOB = "select_job"
    UI_VIEW_SEARCH_RESULTS = "view_search_results"

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

class RTToolCall:
    """Represents an ongoing tool call within a session."""
    def __init__(self, tool_call_id: str, previous_id: str):
        self.tool_call_id = tool_call_id
        self.previous_id = previous_id

class RTMiddleTier:
    """Real-Time Middle Tier for handling WebSocket communications per session."""
    
    def __init__(self, endpoint: str, deployment: str, 
                 credentials: Union[AzureKeyCredential, DefaultAzureCredential],
                 tool_definitions: Dict[str, ToolDefinition],
                 session_provider: Callable[[str], 'SessionState'],
                 voice_choice: Optional[str] = None):
        self.config = RTMTConfig(endpoint=endpoint, deployment=deployment, voice_choice=voice_choice)
        self.tool_definitions = tool_definitions
        self.session_provider = session_provider
        
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

    async def _process_message_to_client(self, msg_data: str, session_id: str, client_ws: web.WebSocketResponse, server_ws: web.WebSocketResponse) -> Optional[str]:
        """Process messages from OpenAI server to the client, handling tool calls within the session."""
        try:
            message = json.loads(msg_data)
            session_state = self.session_provider(session_id)
            updated_message = msg_data

            if message is not None:
                msg_type = message.get("type")
                
                if msg_type == MessageType.SESSION_CREATED.value:
                    session = message["session"]
                    session["instructions"] = self.config.system_message or ""
                    session["tools"] = [td.schema for td in self.tool_definitions.values()]
                    session["voice"] = self.config.voice_choice
                    session["tool_choice"] = "auto" if self.tool_definitions else "none"
                    session["max_response_output_tokens"] = self.config.max_tokens
                    updated_message = json.dumps(message)

                elif msg_type == MessageType.RESPONSE_OUTPUT_ADDED.value:
                    if message.get("item", {}).get("type") == MessageType.FUNCTION_CALL.value:
                        updated_message = None # Don't forward raw function call to client

                elif msg_type == MessageType.CONVERSATION_ITEM_CREATED.value:
                    item = message.get("item", {})
                    item_type = item.get("type")
                    if item_type == MessageType.FUNCTION_CALL.value:
                        call_id = item.get("call_id")
                        if call_id and call_id not in session_state.pending_tools:
                            session_state.pending_tools[call_id] = RTToolCall(call_id, message.get("previous_item_id"))
                        updated_message = None # Don't forward raw function call to client
                    elif item_type == MessageType.FUNCTION_CALL_OUTPUT.value:
                        updated_message = None # Don't forward function call output to client

                elif msg_type == MessageType.FUNCTION_CALL_ARGS_DELTA.value:
                    updated_message = None # Don't forward argument deltas
                
                elif msg_type == MessageType.FUNCTION_CALL_ARGS_DONE.value:
                    updated_message = None # Don't forward argument done messages

                elif msg_type == MessageType.RESPONSE_OUTPUT_DONE.value:
                    item = message.get("item", {})
                    if item.get("type") == MessageType.FUNCTION_CALL.value:
                        call_id = item.get("call_id")
                        tool_name = item.get("name")
                        args_str = item.get("arguments")
                        
                        if call_id and tool_name and args_str and call_id in session_state.pending_tools:
                            tool_call = session_state.pending_tools.pop(call_id)
                            tool_def = self.tool_definitions.get(tool_name)
                            
                            if tool_def:
                                try:
                                    args = json.loads(args_str)
                                    # Pass the session-specific job_search instance
                                    result = await tool_def.handler(session_state.job_search, args)
                                    
                                    # Send result to server (LLM)
                                    await server_ws.send_json({
                                        "type": MessageType.CONVERSATION_ITEM_CREATE.value,
                                        "item": {
                                            "type": MessageType.FUNCTION_CALL_OUTPUT.value,
                                            "call_id": call_id,
                                            "output": result.to_text() # Always send text result to server
                                        }
                                    })
                                    
                                    # UI updates are now handled via UIState listeners, no need to send EXTENSION_MIDDLE_TIER_TOOL_RESPONSE
                                    # if result.destination == ToolResultDirection.TO_CLIENT:
                                    #     await client_ws.send_json({
                                    #         "type": MessageType.EXTENSION_MIDDLE_TIER_TOOL_RESPONSE.value,
                                    #         "previous_item_id": tool_call.previous_id,
                                    #         "tool_name": tool_name,
                                    #         "tool_result": result.to_text()
                                    #     })
                                except json.JSONDecodeError:
                                    logger.error(f"Session {session_id}: Failed to decode tool arguments: {args_str}")
                                except Exception as tool_error:
                                    logger.error(f"Session {session_id}: Error executing tool {tool_name}: {tool_error}")
                                    # Optionally send an error back to the LLM
                                    await server_ws.send_json({
                                        "type": MessageType.CONVERSATION_ITEM_CREATE.value,
                                        "item": {
                                            "type": MessageType.FUNCTION_CALL_OUTPUT.value,
                                            "call_id": call_id,
                                            "output": json.dumps({"error": f"Tool execution failed: {tool_error}"})
                                        }
                                    })
                            else:
                                logger.warning(f"Session {session_id}: Received call for unknown tool: {tool_name}")
                        
                        updated_message = None # Don't forward the original message

                elif msg_type == MessageType.RESPONSE_DONE.value:
                    if session_state.pending_tools:
                        logger.warning(f"Session {session_id}: Response done, but {len(session_state.pending_tools)} tools still pending. Clearing.")
                        session_state.pending_tools.clear()
                        # Request a new response turn from the LLM as the previous one was likely interrupted by tool calls
                        await server_ws.send_json({"type": MessageType.RESPONSE_CREATE.value})
                        
                    # Clean up function calls from the final response output if necessary
                    response_data = message.get("response", {})
                    output_list = response_data.get("output")
                    if isinstance(output_list, list):
                        original_len = len(output_list)
                        cleaned_output = [item for item in output_list if item.get("type") != MessageType.FUNCTION_CALL.value]
                        if len(cleaned_output) < original_len:
                            message["response"]["output"] = cleaned_output
                            updated_message = json.dumps(message)

            return updated_message
        except json.JSONDecodeError:
            logger.error(f"Session {session_id}: Failed to decode server message: {msg_data}")
            return msg_data # Forward undecodable message as is
        except Exception as e:
            logger.error(f"Session {session_id}: Error processing message to client: {str(e)}")
            return msg_data # Forward original message on error

    async def _process_message_to_server(self, msg_data: str, session_id: str) -> Optional[str]:
        """Process messages from the client to the OpenAI server for a specific session."""
        try:
            message = json.loads(msg_data)
            updated_message = msg_data
            session_state = self.session_provider(session_id)
            
            if message is not None:
                msg_type = message.get("type")

                # Check if it's a UI-specific message
                ui_message_types = {
                    MessageType.UI_RESET_STATE.value,
                    MessageType.UI_MANUAL_SEARCH.value,
                    MessageType.UI_SELECT_JOB.value,
                    MessageType.UI_VIEW_SEARCH_RESULTS.value
                }
                if msg_type in ui_message_types:
                    logger.info(f"Session {session_id}: Handling UI message type: {msg_type}")
                    await session_state.handle_ui_message(message)
                    return None # Don't forward UI messages to OpenAI

                elif msg_type == MessageType.SESSION_UPDATE.value:
                    session = message.get("session", {})
                    # Apply RTMT configurations
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
                    
                    # Apply tool configurations
                    session["tool_choice"] = "auto" if self.tool_definitions else "none"
                    session["tools"] = [td.schema for td in self.tool_definitions.values()]
                    
                    message["session"] = session
                    updated_message = json.dumps(message)
                
                # Other message types (like input_audio_buffer.append) are forwarded directly

            return updated_message
        except json.JSONDecodeError:
            logger.error(f"Session {session_id}: Failed to decode client message: {msg_data}")
            return msg_data # Forward undecodable message
        except Exception as e:
            logger.error(f"Session {session_id}: Error processing message to server: {str(e)}")
            return msg_data # Forward original message on error

    async def _forward_messages(self, client_ws: web.WebSocketResponse, session_id: str):
        """Forward messages between a client WebSocket and the OpenAI server for a given session."""
        logger.info(f"Starting message forwarding for session: {session_id}")
        async with aiohttp.ClientSession(base_url=self.config.endpoint) as http_session:
            params = { "api-version": self.config.api_version, "deployment": self.config.deployment}
            headers = {}
            if "x-ms-client-request-id" in client_ws.headers:
                headers["x-ms-client-request-id"] = client_ws.headers["x-ms-client-request-id"]
            
            if self.key is not None:
                headers["api-key"] = self.key
            elif self._token_provider:
                try:
                    # Refresh token if needed
                    token = self._token_provider() 
                    headers["Authorization"] = f"Bearer {token}"
                except Exception as token_error:
                    logger.error(f"Session {session_id}: Failed to get authorization token: {token_error}")
                    await client_ws.close(code=aiohttp.WSCloseCode.INTERNAL_ERROR, message=b'Authorization failed')
                    return
            else:
                 logger.error(f"Session {session_id}: No credentials configured.")
                 await client_ws.close(code=aiohttp.WSCloseCode.INTERNAL_ERROR, message=b'Server misconfiguration')
                 return

            try:
                async with http_session.ws_connect("/openai/realtime", headers=headers, params=params) as server_ws:
                    logger.info(f"Session {session_id}: Connected to OpenAI Realtime API.")
                    
                    async def from_client_to_server():
                        async for msg in client_ws:
                            if msg.type == aiohttp.WSMsgType.TEXT:
                                processed_msg = await self._process_message_to_server(msg.data, session_id)
                                if processed_msg is not None and not server_ws.closed:
                                    await server_ws.send_str(processed_msg)
                            elif msg.type == aiohttp.WSMsgType.ERROR:
                                logger.error(f"Session {session_id}: Client WS error: {client_ws.exception()}")
                                break
                            elif msg.type == aiohttp.WSMsgType.CLOSED:
                                logger.info(f"Session {session_id}: Client WS closed gracefully.")
                                break
                        # Client closed, close server connection
                        if not server_ws.closed:
                            await server_ws.close()
                            logger.info(f"Session {session_id}: Closed OpenAI connection due to client disconnect.")
                            
                    async def from_server_to_client():
                        async for msg in server_ws:
                            if msg.type == aiohttp.WSMsgType.TEXT:
                                processed_msg = await self._process_message_to_client(msg.data, session_id, client_ws, server_ws)
                                if processed_msg is not None and not client_ws.closed:
                                    await client_ws.send_str(processed_msg)
                            elif msg.type == aiohttp.WSMsgType.ERROR:
                                logger.error(f"Session {session_id}: Server WS error: {server_ws.exception()}")
                                break
                            elif msg.type == aiohttp.WSMsgType.CLOSED:
                                logger.info(f"Session {session_id}: Server WS closed gracefully.")
                                break
                        # Server closed, close client connection
                        if not client_ws.closed:
                            await client_ws.close()
                            logger.info(f"Session {session_id}: Closed client connection due to server disconnect.")

                    # Run both forwarders concurrently
                    await asyncio.gather(from_client_to_server(), from_server_to_client())

            except aiohttp.ClientConnectorError as e:
                logger.error(f"Session {session_id}: Failed to connect to OpenAI Realtime API: {e}")
                await client_ws.close(code=aiohttp.WSCloseCode.TRY_AGAIN_LATER, message=b'Cannot reach backend service')
            except aiohttp.WSServerHandshakeError as e:
                 logger.error(f"Session {session_id}: WebSocket handshake with OpenAI failed: {e.status} {e.message}")
                 await client_ws.close(code=aiohttp.WSCloseCode.INTERNAL_ERROR, message=b'Backend connection error')
            except Exception as e:
                logger.error(f"Session {session_id}: Unexpected error during message forwarding: {e}", exc_info=True)
                if not client_ws.closed:
                    await client_ws.close(code=aiohttp.WSCloseCode.INTERNAL_ERROR, message=b'Internal server error')
        
        logger.info(f"Stopped message forwarding for session: {session_id}")

    async def _websocket_handler(self, request: web.Request):
        """Handle incoming WebSocket connections, extract session ID, and start forwarding."""
        session_id = request.query.get('sid')
        if not session_id:
            logger.warning("WebSocket connection attempt without session ID.")
            return web.HTTPBadRequest(text="Session ID (sid) query parameter is required")
            
        try:
            session_state = self.session_provider(session_id) # Get or create session
        except KeyError:
             logger.warning(f"WebSocket connection attempt with invalid session ID: {session_id}")
             return web.HTTPBadRequest(text="Invalid session ID")

        ws = web.WebSocketResponse()
        await ws.prepare(request)
        logger.info(f"WebSocket connection established for session: {session_id}")
        
        # Store the client WebSocket in the session state
        session_state.client_ws = ws
        
        # Save session state to Redis if available
        if hasattr(session_state, 'save_to_redis'):
            session_state.save_to_redis()

        # Define the UI state update callback
        async def send_ui_update(state: Dict[str, Any]):
            if not ws.closed:
                try:
                    await ws.send_json({"type": "ui_state_update", "data": state})
                except ConnectionResetError:
                    logger.warning(f"Session {session_id}: Client connection closed while sending UI update.")
                except Exception as e:
                    logger.error(f"Session {session_id}: Error sending UI update: {e}")

        # Add the callback as a listener
        session_state.ui_state.add_update_listener(send_ui_update)

        # Send initial UI state
        await send_ui_update(session_state.ui_state.get_state())

        try:
            await self._forward_messages(ws, session_id)
        except Exception as e:
            logger.error(f"Session {session_id}: Error in WebSocket handler: {e}", exc_info=True)
        finally:
            logger.info(f"WebSocket connection closed for session: {session_id}")
            # Mark client_ws as None for this session
            session_state.client_ws = None
            # Save the final state to Redis
            if hasattr(session_state, 'save_to_redis'):
                session_state.save_to_redis()
        
        return ws
    
    def attach_to_app(self, app: web.Application, path: str) -> None:
        """Attach the WebSocket handler to the application."""
        # Ensure the path passed from app.py is used
        app.router.add_get(path, self._websocket_handler)
