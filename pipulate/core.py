import inspect
import importlib
from pathlib import Path
import functools
import json
import re
import asyncio
import aiohttp
from datetime import datetime
from fasthtml.common import *
from fastlite import Database  # CORRECTED: Use the Database class
from loguru import logger
import imports.server_logging as slog
import config as CFG
from config import COLOR_MAP
from imports import botify_code_generation
from imports.stream_orchestrator import stream_orchestrator
from typing import AsyncGenerator, Optional
import imports.server_logging as slog

log = slog.LogManager(logger)

import getpass
from google.api_core import exceptions as google_exceptions
try:
    import google.generativeai as genai
    GOOGLE_AI_AVAILABLE = True
except ImportError:
    GOOGLE_AI_AVAILABLE = False


def title_name(word: str) -> str:
    """Format a string into a title case form."""
    if not word:
        return ''
    formatted = word.replace('.', ' ').replace('-', ' ')
    words = []
    for part in formatted.split('_'):
        words.extend(part.split())
    processed_words = []
    for word in words:
        if word.isdigit():
            processed_words.append(word.lstrip('0') or '0')
        else:
            processed_words.append(word.capitalize())
    return ' '.join(processed_words)


def pipeline_operation(func):

    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        url = args[0] if args else None
        if not url:
            return func(self, *args, **kwargs)
        old_state = self._get_clean_state(url)
        result = func(self, *args, **kwargs)
        new_state = self._get_clean_state(url)
        if old_state != new_state:
            changes = {k: new_state[k] for k in new_state if k not in old_state or old_state[k] != new_state[k]}
            if changes:
                operation = func.__name__
                step_changes = [k for k in changes if not k.startswith('_')]
                if step_changes:
                    log.pipeline(f"Operation '{operation}' updated state", details=f"Steps: {', '.join(step_changes)}", pipeline_id=url)
                # Use Rich JSON display for pipeline changes
                formatted_changes = slog.rich_json_display(changes, console_output=False, log_output=True)
                log.debug('pipeline', f"Pipeline '{url}' detailed changes", formatted_changes)
        return result
    return wrapper


def db_operation(func):

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            result = func(*args, **kwargs)
            if func.__name__ == '__setitem__':
                key, value = (args[1], args[2])
                if not key.startswith('_') and (not key.endswith('_temp')):
                    if key in ('last_app_choice', 'last_profile_id', 'last_visited_url', 'pipeline_id'):
                        log.data(f'State updated: {key}', value)
                    else:
                        log.debug('database', f'DB {func.__name__}: {key}', f'value: {str(value)[:30]}...' if len(str(value)) > 30 else f'value: {value}')
            return result
        except Exception as e:
            # Don't log KeyError as ERROR for __getitem__ - it's expected behavior
            if func.__name__ == '__getitem__' and isinstance(e, KeyError):
                logger.debug(f'Key not found in database: {e}')
            else:
                log.error(f'Database operation {func.__name__} failed', e)
            raise
    return wrapper


class DictLikeDB:

    def __init__(self, store, Store):
        self.store = store
        logger.debug('DictLikeDB initialized.')

    @db_operation
    def __getitem__(self, key):
        try:
            value = self.store[key].value
            logger.debug(f'Retrieved from DB: {key} = {value}')
            return value
        except NotFoundError:
            # Don't log as error - this is expected behavior when checking for keys
            logger.debug(f'Key not found: {key}')
            raise KeyError(key)

    @db_operation
    def __setitem__(self, key, value):
        try:
            self.store.update({'key': key, 'value': value})
            logger.debug(f'Updated persistence store: {key} = {value}')
        except NotFoundError:
            self.store.insert({'key': key, 'value': value})
            logger.debug(f'Inserted new item in persistence store: {key} = {value}')

    @db_operation
    def __delitem__(self, key):
        try:
            self.store.delete(key)
            if key != 'temp_message':
                logger.warning(f'Deleted key from persistence store: {key}')
        except NotFoundError:
            logger.error(f'Attempted to delete non-existent key: {key}')
            raise KeyError(key)

    @db_operation
    def __contains__(self, key):
        exists = key in self.store
        logger.debug(f"Key '<{COLOR_MAP['key']}>{key}</{COLOR_MAP['key']}>' exists: <{COLOR_MAP['value']}>{exists}</{COLOR_MAP['value']}>")
        return exists

    @db_operation
    def __iter__(self):
        for record in self.store():
            yield record.key

    @db_operation
    def items(self):
        for record in self.store():
            yield (record.key, record.value)

    @db_operation
    def keys(self):
        return list(self)

    @db_operation
    def values(self):
        for record in self.store():
            yield record.value

    @db_operation
    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            logger.debug(f"Key '<{COLOR_MAP['key']}>{key}</{COLOR_MAP['key']}>' not found. Returning default: <{COLOR_MAP['value']}>{default}</{COLOR_MAP['value']}>")
            return default

    @db_operation
    def set(self, key, value):
        self[key] = value
        return value


class Pipulate:
    """Central coordinator for pipelines and chat functionality.

    This class serves as the main interface for plugins to access
    shared functionality without relying on globals.

    As Pipulate evolves toward its "Digital Workshop" vision, this coordinator
    will support:
    - Sub-plugin architecture (steps expanding to full-screen apps)
    - Content curation systems (archive surfing, variant creation)
    - Progressive distillation workflows (search, sort, sieve, story)
    - Local-first creative exploration with privacy preservation

    The centralized coordination pattern enables sophisticated interaction
    monitoring and behavioral pattern analysis while maintaining the
    "vibrating edge" of creative freedom that powers genuine innovation.
    """
    PRESERVE_REFILL = True
    UNLOCK_BUTTON_LABEL = '🔓 Unlock'

    # START: pipulate_init
    def __init__(self, pipeline_table=None, db=None, friendly_names=None, append_func=None, get_profile_id_func=None, get_profile_name_func=None, model=None, chat_instance=None, db_path=None):
        self.chat = chat_instance
        self.friendly_names = friendly_names
        self.append_to_conversation = append_func
        self.get_current_profile_id = get_profile_id_func
        self.get_profile_name = get_profile_name_func
        self.model = model
        self.message_queue = self.OrderedMessageQueue()
        self.is_notebook_context = bool(db_path) # Flag for notebook context
    
        if db_path:
            # Standalone/Notebook Context: Create our "Parallel Universe" DB using fastlite directly
            from fastlite import Database
            from loguru import logger
            logger.info(f"Pipulate initializing in standalone mode with db: {db_path}")
    
            # 1. Create a database connection using fastlite.Database
            db_conn = Database(db_path)
    
            # 2. Access the table handles via the .t property
            l_store = db_conn.t.store
            l_pipeline = db_conn.t.pipeline
            # Note: We don't need to explicitly create tables; fastlite handles it.
    
            self.pipeline_table = l_pipeline
            # The second argument `Store` from fast_app isn't needed by DictLikeDB.
            self.db = DictLikeDB(l_store, None)
    
            # In standalone mode, some features that rely on the server are stubbed out
            if self.append_to_conversation is None: self.append_to_conversation = lambda msg, role: print(f"[{role}] {msg}")
            if self.get_current_profile_id is None: self.get_current_profile_id = lambda: 'standalone'
            if self.get_profile_name is None: self.get_profile_name = lambda: 'standalone'
    
        else:
            # Server Context: Use the objects passed in from server.py
            from loguru import logger
            logger.info("Pipulate initializing in server mode.")
            self.pipeline_table = pipeline_table
            self.db = db
    # END: pipulate_init

    def get_home_menu_item(self) -> str:
        """Returns the appropriate home menu item text based on the HOME_APP setting."""
        home_app_name = getattr(CFG, 'HOME_APP', '030_roles') # Default to '030_roles'
        return self.friendly_names.get(home_app_name, title_name(home_app_name))

    def endpoint_name(self, endpoint: str) -> str:
        if not endpoint:
            return self.get_home_menu_item()
        if endpoint in self.friendly_names:
            return self.friendly_names[endpoint]
        return title_name(endpoint)

    def append_to_conversation_from_instance(self, message: str, role: str = 'user'):
        """Instance method wrapper for the global self.append_to_conversation function."""
        return self.append_to_conversation(message, role=role)

    def append_to_history(self, message: str, role: str = 'system') -> None:
        """Add a message to the LLM conversation history without triggering a response.

        This is the preferred way for workflows to update the LLM's context about:
        - UI state changes
        - Form submissions
        - Validation results
        - Explanatory text shown to users
        - Step completion status

        Args:
            message: The message to add to history
            role: The role of the message sender ("system", "user", "assistant")
        """
        self.append_to_conversation(message, role=role)

    class OrderedMessageQueue:
        """A lightweight queue to ensure messages are delivered in order.

        This class creates a simple message queue that ensures messages are delivered
        in the exact order they are added, without requiring explicit delays between
        messages. It's used to fix the message streaming order issues.

        As part of the Digital Workshop evolution, this queue will support:
        - Interaction pattern recognition for adaptive workflows
        - State transition tracking for sub-plugin applications
        - Creative session analysis for distillation workflows
        - Privacy-preserving behavioral insights for local optimization

        The workflow state tracking enables sophisticated user interaction
        analysis while keeping all data local for maximum creative freedom.
        """

        def __init__(self):
            self.queue = []
            self._processing = False
            self._current_step = None
            self._step_started = False
            self._step_complete = False
            self._workflow_context = None

        async def add(self, pipulate, message, **kwargs):
            """Add a message to the queue and process if not already processing.

            This method no longer handles conversation history - that's now managed by pipulate.stream.
            """
            logger.info(f'[🔄 QUEUEING] {message[:100]}...')
            self.queue.append((pipulate, message, kwargs))
            if not self._processing:
                await self._process_queue()

        async def _process_queue(self):
            """Process messages in the queue.

            This method now focuses solely on queue processing and streaming,
            leaving conversation history management to pipulate.stream.
            """
            if self._processing:
                return

            self._processing = True
            try:
                while self.queue:
                    pipulate, message, kwargs = self.queue.pop(0)
                    await pipulate.stream(message, **kwargs)
            finally:
                self._processing = False

        def mark_step_complete(self, step_num):
            """Mark a step as completed."""
            self._current_step = step_num
            self._step_complete = True

        def mark_step_started(self, step_num):
            """Mark a step as started but not completed."""
            self._current_step = step_num
            self._step_started = True

    def speak(self, text: str):
        """
        Synthesizes text to speech using the global ChipVoiceSystem if available.
        Fails gracefully to simple printing if the audio backend is unavailable.
        """
        print(f"🤖 {text}")
        try:
            # We import here to avoid circular dependencies and unnecessary 
            # loading if the user never calls pip.speak()
            from imports.voice_synthesis import chip_voice_system
            if chip_voice_system and chip_voice_system.voice_ready:
                 chip_voice_system.speak_text(text)
        except Exception as e:
            # We fail silently because the print() statement above acts as our fallback
            pass

    def make_singular(self, word):
        """Convert a potentially plural word to its singular form using simple rules.

        This uses basic suffix replacement rules to handle common English plurals.
        It's designed for the 80/20 rule - handling common cases without complexity.

        Args:
            word (str): The potentially plural word to convert

        Returns:
            str: The singular form of the word
        """
        word = word.strip()
        if not word:
            return word
        if word.lower() in ('data', 'media', 'series', 'species', 'news'):
            return word
        irregulars = {'children': 'child', 'people': 'person', 'men': 'man', 'women': 'woman', 'teeth': 'tooth', 'feet': 'foot', 'geese': 'goose', 'mice': 'mouse', 'criteria': 'criterion'}
        if word.lower() in irregulars:
            return irregulars[word.lower()]
        if word.lower().endswith('ies'):
            return word[:-3] + 'y'
        if word.lower().endswith('ves'):
            return word[:-3] + 'f'
        if word.lower().endswith('xes') or word.lower().endswith('sses') or word.lower().endswith('shes') or word.lower().endswith('ches'):
            return word[:-2]
        if word.lower().endswith('s') and (not word.lower().endswith('ss')):
            return word[:-1]
        return word


    def set_chat(self, chat_instance):
            """Set the chat instance after initialization."""
            self.chat = chat_instance


    def get_message_queue(self):
        """Return the message queue instance for ordered message delivery."""
        return self.message_queue

    def step_button(self, visual_step_number: str, preserve: bool = False, revert_label: str = None) -> str:
        """
        Formats the revert button text.
        Uses visual_step_number for "Step X" numbering if revert_label is not provided.

        Args:
            visual_step_number: The visual step number (e.g., "1", "2", "3") based on position in workflow
            preserve: Whether to use the preserve symbol (⟲) instead of revert symbol (↶)
            revert_label: Custom label to use instead of "Step X" format
        """
        symbol = '⟲' if preserve else '↶'
        if revert_label:
            button_text = f'{symbol}\xa0{revert_label}'
        else:
            button_text = f'{symbol}\xa0Step\xa0{visual_step_number}'
        return button_text

    def get_ui_constants(self):
        """Access centralized UI constants through dependency injection."""
        return CFG.UI_CONSTANTS

    def get_config(self):
        """Access centralized configuration through dependency injection."""
        return CFG

    def get_button_border_radius(self):
        """Get the global button border radius setting."""
        return CFG.UI_CONSTANTS['BUTTON_STYLES']['BORDER_RADIUS']

    def register_workflow_routes(self, plugin_instance):
        """
        Register standard and step-specific routes for a workflow plugin.

        This helper extracts the common route registration boilerplate from workflow __init__ methods,
        while maintaining the WET principle - each workflow still explicitly calls this method.

        Args:
            plugin_instance: The workflow plugin instance with app, APP_NAME, and steps attributes
        """
        app_name = plugin_instance.APP_NAME
        steps = plugin_instance.steps

        # Standard workflow lifecycle routes
        routes = [
            (f'/{app_name}/init', plugin_instance.init, ['POST']),
            (f'/{app_name}/revert', plugin_instance.handle_revert, ['POST']),
            (f'/{app_name}/unfinalize', plugin_instance.unfinalize, ['POST'])
        ]

        # Dynamically create routes for each step from the plugin's steps list
        for step_obj in steps:
            step_id = step_obj.id
            handler_method = getattr(plugin_instance, step_id, None)
            if handler_method:
                current_methods = ['GET']
                if step_id == 'finalize':
                    current_methods.append('POST')
                routes.append((f'/{app_name}/{step_id}', handler_method, current_methods))

            # Only data steps (not 'finalize') have explicit _submit handlers
            if step_id != 'finalize':
                submit_handler_method = getattr(plugin_instance, f'{step_id}_submit', None)
                if submit_handler_method:
                    routes.append((f'/{app_name}/{step_id}_submit', submit_handler_method, ['POST']))

        # Register all routes with the FastHTML app
        for path, handler, *methods_list_arg in routes:
            current_methods = methods_list_arg[0] if methods_list_arg else ['GET']
            plugin_instance.app.route(path, methods=current_methods)(handler)

    async def log_api_call_details(self, pipeline_id: str, step_id: str, call_description: str, http_method: str, url: str, headers: dict, payload: Optional[dict] = None, response_status: Optional[int] = None, response_preview: Optional[str] = None, response_data: Optional[dict] = None, curl_command: Optional[str] = None, python_command: Optional[str] = None, estimated_rows: Optional[int] = None, actual_rows: Optional[int] = None, file_path: Optional[str] = None, file_size: Optional[str] = None, notes: Optional[str] = None):
        """Log complete API call details for extreme observability and Jupyter reproduction.

        This provides the same level of transparency for API calls as is used in BQL query logging,
        including copy-paste ready Python code for Jupyter notebook reproduction.
        """
        log_entry_parts = []
        log_entry_parts.append(f'  [API Call] {call_description or "API Request"}')
        log_entry_parts.append(f'  Pipeline ID: {pipeline_id}')
        log_entry_parts.append(f'  Step ID: {step_id}')
        log_entry_parts.append(f'  Method: {http_method}')
        log_entry_parts.append(f'  URL: {url}')
        if headers:
            headers_preview = {k: v for k, v in headers.items() if k.lower() not in ['authorization', 'cookie', 'x-api-key']}
            if len(headers_preview) != len(headers):
                headers_preview['<REDACTED_AUTH_HEADERS>'] = f'{len(headers) - len(headers_preview)} hidden'
            # Use Rich JSON display for headers
            pretty_headers = slog.rich_json_display(headers_preview, title="API Headers", console_output=True, log_output=True)
            log_entry_parts.append(f'  Headers: {pretty_headers}')
        if payload:
            try:
                # Use Rich JSON display for payload
                pretty_payload = slog.rich_json_display(payload, title="API Payload", console_output=True, log_output=True)
                log_entry_parts.append(f'  Payload:\n{pretty_payload}')
            except Exception:
                log_entry_parts.append(f'  Payload: {payload}')
        if curl_command:
            log_entry_parts.append(f'  cURL Command:\n{curl_command}')
        if python_command:
            # Use centralized emoji configuration for console messages
            python_emoji = CFG.UI_CONSTANTS['EMOJIS']['PYTHON_CODE']
            snippet_emoji = CFG.UI_CONSTANTS['EMOJIS']['CODE_SNIPPET']
            comment_divider = CFG.UI_CONSTANTS['CODE_FORMATTING']['COMMENT_DIVIDER']
            snippet_intro = CFG.UI_CONSTANTS['CONSOLE_MESSAGES']['PYTHON_SNIPPET_INTRO'].format(
                python_emoji=python_emoji,
                snippet_emoji=snippet_emoji
            )
            snippet_end = CFG.UI_CONSTANTS['CONSOLE_MESSAGES']['PYTHON_SNIPPET_END'].format(
                python_emoji=python_emoji,
                snippet_emoji=snippet_emoji
            )
            # Add Python snippet with complete BEGIN/END block
            log_entry_parts.append(f'{snippet_intro}\n{python_command}')
            log_entry_parts.append('# Note: The API token should be loaded from a secure file location.')
            log_entry_parts.append(f'{comment_divider}')
            log_entry_parts.append(f'{snippet_end}')
        if estimated_rows is not None:
            log_entry_parts.append(f'  Estimated Rows (from pre-check): {estimated_rows:,}')
        if actual_rows is not None:
            log_entry_parts.append(f'  Actual Rows Downloaded: {actual_rows:,}')
        if response_status is not None:
            log_entry_parts.append(f'  Response Status: {response_status}')
        if response_preview:
            try:
                parsed = json.loads(response_preview)
                # Use Rich JSON display for response preview
                pretty_preview = slog.rich_json_display(parsed, title="API Response Preview", console_output=True, log_output=True)
                log_entry_parts.append(f'  Response Preview:\n{pretty_preview}')
            except Exception:
                log_entry_parts.append(f'  Response Preview:\n{response_preview}')

        # Enhanced transparency for discovery endpoints - log full response data
        is_discovery_endpoint = self._is_discovery_endpoint(url)
        if response_data and is_discovery_endpoint:
            try:
                # Use Rich JSON display for discovery response
                pretty_response = slog.rich_json_display(response_data, title=f"🔍 Discovery Response: {call_description}", console_output=True, log_output=True)
                log_entry_parts.append(f'  🔍 FULL RESPONSE DATA (Discovery Endpoint):\n{pretty_response}')

            except Exception as e:
                log_entry_parts.append(f'  🔍 FULL RESPONSE DATA (Discovery Endpoint): [Error formatting JSON: {e}]\n{response_data}')

                # Still display in console even if JSON formatting fails
                slog.console.print(f"❌ Discovery Response Error: {e}", style="red")
                slog.console.print(f"Raw data: {str(response_data)}", style="dim")

        if file_path:
            log_entry_parts.append(f'  Associated File Path: {file_path}')
        if file_size:
            log_entry_parts.append(f'  Associated File Size: {file_size}')
        if notes:
            log_entry_parts.append(f'  Notes: {notes}')

        full_log_message = '\n'.join(log_entry_parts)
        logger.info(f'\n🚀 === API CALL TRANSPARENCY ===\n{full_log_message}\n🚀 === END API TRANSPARENCY ===')
        is_bql = 'bql' in (call_description or '').lower() or 'botify query language' in (call_description or '').lower()

    def _is_discovery_endpoint(self, url: str) -> bool:
        """Detect if this is a key discovery endpoint that should have full response logging.

        Args:
            url: The API endpoint URL

        Returns:
            bool: True if this is a discovery endpoint that should log full response data
        """
        discovery_patterns = [
            '/analyses/',  # Covers both /analyses/{username}/{project}/light and regular analyses
            '/advanced_export',  # Field discovery endpoint
        ]

        return any(pattern in url for pattern in discovery_patterns)

    async def log_mcp_call_details(self, operation_id: str, tool_name: str, operation_type: str, mcp_block: str = None, request_payload: Optional[dict] = None, response_data: Optional[dict] = None, response_status: Optional[int] = None, external_api_url: Optional[str] = None, external_api_method: str = 'GET', external_api_headers: Optional[dict] = None, external_api_payload: Optional[dict] = None, external_api_response: Optional[dict] = None, external_api_status: Optional[int] = None, execution_time_ms: Optional[float] = None, notes: Optional[str] = None):
        """Log complete MCP operation details for extreme observability and Jupyter reproduction.

        This provides the same level of transparency for MCP operations as the BQL query logging,
        including copy-paste ready Python code for external API reproduction.

        Args:
            operation_id: Unique identifier for this MCP operation
            tool_name: Name of the MCP tool being executed
            operation_type: Type of operation (tool_execution, api_call, etc.)
            mcp_block: Raw MCP block that triggered the operation
            request_payload: Payload sent to MCP tool executor
            response_data: Response from MCP tool executor
            response_status: HTTP status from MCP tool executor
            external_api_url: URL of external API called (if any)
            external_api_method: HTTP method for external API
            external_api_headers: Headers sent to external API
            external_api_payload: Payload sent to external API
            external_api_response: Response from external API
            external_api_status: HTTP status from external API
            execution_time_ms: Total execution time in milliseconds
            notes: Additional context or notes
        """
        log_entry_parts = []
        log_entry_parts.append(f'  [MCP Operation] {operation_type.title()} - {tool_name}')
        log_entry_parts.append(f'  Operation ID: {operation_id}')
        log_entry_parts.append(f'  Tool Name: {tool_name}')
        log_entry_parts.append(f'  Operation Type: {operation_type}')
        log_entry_parts.append(f'  Timestamp: {self.get_timestamp()}')

        if execution_time_ms is not None:
            log_entry_parts.append(f'  Execution Time: {execution_time_ms:.2f}ms')

        # MCP Block Details
        if mcp_block:
            log_entry_parts.append(f'  MCP Block:')
            # Indent each line of the MCP block for better readability
            indented_block = '\n'.join(f'    {line}' for line in mcp_block.strip().split('\n'))
            log_entry_parts.append(indented_block)

        # Internal MCP Tool Executor Request
        if request_payload:
            log_entry_parts.append('')  # Extra space for visual separation
            log_entry_parts.append(f'  MCP Tool Executor Request:')
            log_entry_parts.append(f'    URL: http://127.0.0.1:5001/mcp-tool-executor')
            log_entry_parts.append(f'    Method: POST')
            try:
                # Use Rich JSON display for MCP request payload
                pretty_payload = slog.rich_json_display(request_payload, title="MCP Tool Executor Request", console_output=True, log_output=True)
                # Indent the JSON for consistency
                indented_payload = '\n'.join(f'    {line}' for line in pretty_payload.split('\n'))
                log_entry_parts.append(f'    Payload:\n{indented_payload}')
            except Exception:
                log_entry_parts.append(f'    Payload: {request_payload}')

        # Internal MCP Tool Executor Response
        if response_data or response_status:
            log_entry_parts.append('')  # Extra space for visual separation
            log_entry_parts.append(f'  MCP Tool Executor Response:')
            if response_status:
                log_entry_parts.append(f'    Status: {response_status}')
            if response_data:
                try:
                    # Use Rich JSON display for MCP response data
                    pretty_response = slog.rich_json_display(response_data, title="MCP Tool Executor Response", console_output=True, log_output=True)
                    # Indent the JSON for consistency
                    indented_response = '\n'.join(f'    {line}' for line in pretty_response.split('\n'))
                    log_entry_parts.append(f'    Response:\n{indented_response}')
                except Exception:
                    log_entry_parts.append(f'    Response: {response_data}')

        # External API Call Details (the actual external service)
        if external_api_url:
            log_entry_parts.append('')  # Extra space for visual separation
            log_entry_parts.append(f'  External API Call:')
            log_entry_parts.append(f'    URL: {external_api_url}')
            log_entry_parts.append(f'    Method: {external_api_method}')

            if external_api_headers:
                # Redact sensitive headers
                headers_preview = {k: v for k, v in external_api_headers.items() if k.lower() not in ['authorization', 'cookie', 'x-api-key']}
                if len(headers_preview) != len(external_api_headers):
                    headers_preview['<REDACTED_AUTH_HEADERS>'] = f'{len(external_api_headers) - len(headers_preview)} hidden'
                # Use Rich JSON display for external API headers
                pretty_headers = slog.rich_json_display(headers_preview, title="External API Headers", console_output=True, log_output=True)
                log_entry_parts.append(f'    Headers: {pretty_headers}')

            if external_api_payload:
                try:
                    # Use Rich JSON display for external API payload
                    pretty_payload = slog.rich_json_display(external_api_payload, title="External API Payload", console_output=True, log_output=True)
                    indented_payload = '\n'.join(f'    {line}' for line in pretty_payload.split('\n'))
                    log_entry_parts.append(f'    Payload:\n{indented_payload}')
                except Exception:
                    log_entry_parts.append(f'    Payload: {external_api_payload}')

            if external_api_status:
                log_entry_parts.append(f'    Response Status: {external_api_status}')

            if external_api_response:
                try:
                    # Use Rich JSON display for external API response
                    pretty_response = slog.rich_json_display(external_api_response, title="External API Response", console_output=True, log_output=True)
                    indented_response = '\n'.join(f'    {line}' for line in pretty_response.split('\n'))
                    log_entry_parts.append(f'    Response:\n{indented_response}')
                except Exception:
                    log_entry_parts.append(f'    Response: {external_api_response}')

        # Generate copy-paste ready Python code for Jupyter reproduction
        if external_api_url:
            python_code = self._generate_mcp_python_code(
                tool_name=tool_name,
                external_api_url=external_api_url,
                external_api_method=external_api_method,
                external_api_headers=external_api_headers,
                external_api_payload=external_api_payload,
                operation_id=operation_id
            )

            # Use centralized emoji configuration for console messages
            python_emoji = CFG.UI_CONSTANTS['EMOJIS']['PYTHON_CODE']
            snippet_emoji = CFG.UI_CONSTANTS['EMOJIS']['CODE_SNIPPET']
            comment_divider = CFG.UI_CONSTANTS['CODE_FORMATTING']['COMMENT_DIVIDER']
            snippet_intro = CFG.UI_CONSTANTS['CONSOLE_MESSAGES']['PYTHON_SNIPPET_INTRO'].format(
                python_emoji=python_emoji,
                snippet_emoji=snippet_emoji
            )
            snippet_end = CFG.UI_CONSTANTS['CONSOLE_MESSAGES']['PYTHON_SNIPPET_END'].format(
                python_emoji=python_emoji,
                snippet_emoji=snippet_emoji
            )

            # Add Python snippet with complete BEGIN/END block and visual separation
            log_entry_parts.append('')  # Extra space before Python code
            log_entry_parts.append(f'{snippet_intro}')
            log_entry_parts.append(f'{comment_divider}')
            log_entry_parts.append(f'{python_code}')
            log_entry_parts.append('# Note: This code reproduces the external API call made by the MCP tool.')
            log_entry_parts.append(f'{comment_divider}')
            log_entry_parts.append(f'{snippet_end}')
            log_entry_parts.append('')  # Extra space after Python code

        if notes:
            log_entry_parts.append(f'  Notes: {notes}')

        full_log_message = '\n'.join(log_entry_parts)
        logger.info(f'\n🚀 === MCP OPERATION TRANSPARENCY ===\n{full_log_message}\n🚀 === END MCP TRANSPARENCY ===')

    def _generate_mcp_python_code(self, tool_name: str, external_api_url: str, external_api_method: str = 'GET', external_api_headers: Optional[dict] = None, external_api_payload: Optional[dict] = None, operation_id: str = None) -> str:
        """Generate copy-paste ready Python code for reproducing MCP external API calls in Jupyter.

        This mirrors the pattern used in BQL query logging but for MCP operations.
        """
        lines = []
        lines.append(f'# MCP Tool Reproduction: {tool_name}')
        if operation_id:
            lines.append(f'# Operation ID: {operation_id}')
        lines.append(f'# Generated at: {self.get_timestamp()}')
        lines.append('')
        lines.append('import aiohttp')
        lines.append('import asyncio')
        lines.append('import json')
        lines.append('from pprint import pprint')
        lines.append('')
        lines.append('async def reproduce_mcp_call():')
        lines.append('    """Reproduce the external API call made by the MCP tool."""')
        lines.append('    ')
        lines.append(f'    url = "{external_api_url}"')
        lines.append(f'    method = "{external_api_method.upper()}"')
        lines.append('    ')

        # Headers
        if external_api_headers:
            lines.append('    headers = {')
            for key, value in external_api_headers.items():
                if key.lower() in ['authorization', 'cookie', 'x-api-key']:
                    lines.append(f'        "{key}": "REDACTED_FOR_SECURITY",')
                else:
                    lines.append(f'        "{key}": "{value}",')
            lines.append('    }')
        else:
            lines.append('    headers = {}')
        lines.append('    ')

        # Payload
        if external_api_payload and external_api_method.upper() in ['POST', 'PUT', 'PATCH']:
            lines.append('    payload = {')
            try:
                for key, value in external_api_payload.items():
                    if isinstance(value, str):
                        lines.append(f'        "{key}": "{value}",')
                    else:
                        lines.append(f'        "{key}": {json.dumps(value)},')
            except Exception:
                lines.append(f'        # Payload: {external_api_payload}')
            lines.append('    }')
        else:
            lines.append('    payload = None')
        lines.append('    ')

        # Async session and request
        lines.append('    async with aiohttp.ClientSession() as session:')
        if external_api_method.upper() == 'GET':
            lines.append('        async with session.get(url, headers=headers) as response:')
        elif external_api_method.upper() == 'POST':
            lines.append('        async with session.post(url, headers=headers, json=payload) as response:')
        elif external_api_method.upper() == 'PUT':
            lines.append('        async with session.put(url, headers=headers, json=payload) as response:')
        elif external_api_method.upper() == 'DELETE':
            lines.append('        async with session.delete(url, headers=headers) as response:')
        else:
            lines.append(f'        async with session.request("{external_api_method.upper()}", url, headers=headers, json=payload) as response:')

        lines.append('            print(f"Status: {response.status}")')
        lines.append('            print(f"Headers: {dict(response.headers)}")')
        lines.append('            ')
        lines.append('            if response.content_type == "application/json":')
        lines.append('                data = await response.json()')
        lines.append('                print("JSON Response:")')
        lines.append('                pprint(data)')
        lines.append('                return data')
        lines.append('            else:')
        lines.append('                text = await response.text()')
        lines.append('                print("Text Response:")')
        lines.append('                print(text)')
        lines.append('                return text')
        lines.append('')
        divider = CFG.UI_CONSTANTS['CODE_FORMATTING']['COMMENT_DIVIDER']
        lines.append(divider)
        lines.append('# EXECUTION: Choose your environment')
        lines.append(divider)
        lines.append('')
        lines.append('# For Jupyter Notebooks (recommended):')
        lines.append('result = await reproduce_mcp_call()')
        lines.append('print("\\nFinal result:")')
        lines.append('pprint(result)')
        lines.append('')
        lines.append('# For Python scripts (uncomment if needed):')
        lines.append('# if __name__ == "__main__":')
        lines.append('#     result = asyncio.run(reproduce_mcp_call())')
        lines.append('#     print("\\nFinal result:")')
        lines.append('#     pprint(result)')

        return '\n'.join(lines)

    # ========================================
    # REUSABLE BOTIFY PYTHON CODE GENERATION
    # ========================================

    def generate_botify_code_header(self, display_name: str, step_name: str, username: str, project_name: str,
                                    template_info: dict = None, qualifier_config: dict = None) -> list:
        """Generate standardized header for Botify Python debugging code.

        Delegates to external botify_code_generation module to reduce server.py size.
        """
        return botify_code_generation.generate_botify_code_header(
            display_name=display_name,
            step_name=step_name,
            username=username,
            project_name=project_name,
            template_info=template_info,
            qualifier_config=qualifier_config
        )

    def generate_botify_token_loader(self) -> str:
        """Generate the standard Botify token loading function.

        Delegates to external botify_code_generation module to reduce server.py size.
        """
        return botify_code_generation.generate_botify_token_loader()

    def generate_botify_http_client(self, client_name: str, description: str) -> str:
        """Generate the standard HTTP client function for Botify APIs.

        Delegates to external botify_code_generation module to reduce server.py size.
        """
        return botify_code_generation.generate_botify_http_client(client_name, description)

    def generate_botify_main_executor(self, client_function_name: str, api_description: str) -> str:
        """Generate the main execution function for Botify APIs.

        Delegates to external botify_code_generation module to reduce server.py size.
        """
        return botify_code_generation.generate_botify_main_executor(client_function_name, api_description)

    def create_folder_button(self, folder_path: str, icon: str = "📁", text: str = "Open Folder",
                             title_prefix: str = "Open folder") -> object:
        """Generate a standardized folder opening button.

        Centralizes the folder button pattern used across many plugins.
        """
        import urllib.parse

        from fasthtml.common import A

        quoted_path = urllib.parse.quote(str(folder_path))
        title = f"{title_prefix}: {folder_path}"

        return A(
            f"{icon} {text}",
            hx_get=f"/open-folder?path={quoted_path}",
            hx_swap="none",
            title=title,
            cls="button-link"
        )

    # ========================================
    # ADVANCED BOTIFY CODE GENERATION UTILITIES
    # ========================================

    def generate_botify_bqlv2_python_code(self, query_payload, username, project_name, page_size, jobs_payload, display_name, get_step_name_from_payload_func, get_configured_template_func=None, query_templates=None):
        """
        🚀 REUSABLE UTILITY: Generate complete Python code for BQLv2 queries (crawl, GSC)

        Delegates to external botify_code_generation module to reduce server.py size.
        """
        return botify_code_generation.generate_botify_bqlv2_python_code(
            query_payload=query_payload,
            username=username,
            project_name=project_name,
            page_size=page_size,
            jobs_payload=jobs_payload,
            display_name=display_name,
            get_step_name_from_payload_func=get_step_name_from_payload_func,
            get_configured_template_func=get_configured_template_func,
            query_templates=query_templates
        )

    def generate_botify_bqlv1_python_code(self, query_payload, username, project_name, jobs_payload, display_name, get_step_name_from_payload_func):
        """
        🚀 REUSABLE UTILITY: Generate complete Python code for BQLv1 queries (web logs)

        Delegates to external botify_code_generation module to reduce server.py size.
        """
        return botify_code_generation.generate_botify_bqlv1_python_code(
            query_payload=query_payload,
            username=username,
            project_name=project_name,
            jobs_payload=jobs_payload,
            display_name=display_name,
            get_step_name_from_payload_func=get_step_name_from_payload_func
        )

    def get_botify_analysis_path(self, app_name, username, project_name, analysis_slug, filename=None):
        """
        🚀 REUSABLE UTILITY: Construct standardized Botify analysis file paths

        Delegates to external botify_code_generation module to reduce server.py size.
        """
        return botify_code_generation.get_botify_analysis_path(app_name, username, project_name, analysis_slug, filename)

    def fmt(self, endpoint: str) -> str:
        """Format an endpoint string into a human-readable form."""
        if endpoint in self.friendly_names:
            return self.friendly_names[endpoint]
        return title_name(endpoint)

    def _get_clean_state(self, pkey):
        try:
            record = self.pipeline_table[pkey]
            state = json.loads(record.data)
            state.pop('created', None)
            state.pop('updated', None)
            return state
        except (NotFoundError, json.JSONDecodeError):
            return {}

    def get_timestamp(self) -> str:
        return datetime.now().isoformat()

    def get_plugin_context(self, plugin_instance=None):
        """
        Returns the context information about the current plugin and profile.

        Args:
            plugin_instance: Optional plugin instance to extract name from

        Returns:
            dict: Contains plugin_name, profile_id, and profile_name
        """
        profile_id = self.get_current_profile_id()
        profile_name = self.get_profile_name()
        plugin_name = None
        display_name = None
        if plugin_instance:
            if hasattr(plugin_instance, 'DISPLAY_NAME'):
                display_name = plugin_instance.DISPLAY_NAME
            if hasattr(plugin_instance, 'name'):
                plugin_name = plugin_instance.name
            elif hasattr(plugin_instance, '__class__'):
                plugin_name = plugin_instance.__class__.__name__
            if plugin_name and (not display_name):
                if plugin_name in self.friendly_names:
                    display_name = self.friendly_names[plugin_name]
                else:
                    display_name = title_name(plugin_name)
        return {'plugin_name': display_name or plugin_name, 'internal_name': plugin_name, 'profile_id': profile_id, 'profile_name': profile_name}

    @pipeline_operation
    def initialize_if_missing(self, pkey: str, initial_step_data: dict = None) -> tuple[Optional[dict], Optional[Card]]:
        try:
            state = self.read_state(pkey)
            if state:
                return (state, None)
            now = self.get_timestamp()
            state = {'created': now, 'updated': now}
            if initial_step_data:
                app_name = None
                if 'app_name' in initial_step_data:
                    app_name = initial_step_data.pop('app_name')
                state.update(initial_step_data)
            self.pipeline_table.insert({'pkey': pkey, 'app_name': app_name if app_name else None, 'data': json.dumps(state), 'created': now, 'updated': now})
            return (state, None)
        except:
            error_card = Card(H3('ID Already In Use'), P(f"The ID '{pkey}' is already being used by another workflow. Please try a different ID."), style=self.id_conflict_style())
            return (None, error_card)

    def read_state(self, pkey: str) -> dict:
        logger.debug(f'Reading state for pipeline: {pkey}')
        try:
            record = self.pipeline_table[pkey]

            # 🎯 UNIFIED FIX: Handle both dicts (from notebook) and objects (from server).
            if record:
                if isinstance(record, dict) and 'data' in record:
                    # Handle dictionary from notebook context
                    state = json.loads(record['data'])
                    return state
                elif hasattr(record, 'data'):
                    # Handle object from server context
                    state = json.loads(record.data)
                    return state

            return {}
        except NotFoundError:
            # This is the expected exception when a record doesn't exist.
            logger.debug(f'No record found for pkey: {pkey}')
            return {}
        except Exception as e:
            logger.debug(f'Error reading state for pkey {pkey}: {str(e)}')
            return {}

    def write_state(self, pkey: str, state: dict) -> None:
        state['updated'] = datetime.now().isoformat()
        payload = {'pkey': pkey, 'data': json.dumps(state), 'updated': state['updated']}
        # Use Rich JSON display for debug payload
        formatted_payload = slog.rich_json_display(payload, console_output=False, log_output=True)
        logger.debug(f'Update payload:\n{formatted_payload}')
        self.pipeline_table.update(payload)
        verification = self.read_state(pkey)
        # Use Rich JSON display for verification
        formatted_verification = slog.rich_json_display(verification, console_output=False, log_output=True)
        logger.debug(f'Verification read:\n{formatted_verification}')

    def format_links_in_text(self, text):
        """
        Convert plain URLs in text to clickable HTML links.
        Safe for logging but renders as HTML in the UI.
        """
        url_pattern = 'https?://(?:[-\\w.]|(?:%[\\da-fA-F]{2}))+'

        def replace_url(match):
            url = match.group(0)
            return f'<a href="{url}" target="_blank">{url}</a>'
        return re.sub(url_pattern, replace_url, text)

    async def stream(self, message, **kwargs):
        """Wrapper that delegates to the external stream orchestrator."""
        from imports.stream_orchestrator import stream_orchestrator # Import just-in-time
        # Correctly pass self (pipulate_instance), self.chat (chat_instance), and message
        return await stream_orchestrator(self, self.chat, message, **kwargs)

    async def _handle_llm_stream(self):
        """Handles the logic for an interruptible LLM stream."""
        try:
            await self.chat.broadcast('%%STREAM_START%%')
            conversation_history = self.append_to_conversation()
            response_text = ''
    
            logger.info("ORCHESTRATOR: Entering LLM stream loop.")
            async for chunk in self.process_llm_interaction(self.model, conversation_history):
                await self.chat.broadcast(chunk)
                response_text += chunk
            logger.info(f"ORCHESTRATOR: Exited LLM stream loop. Full response_text: '{response_text}'")
        except asyncio.CancelledError:
            logger.info("LLM stream was cancelled by user.")
        except Exception as e:
            logger.error(f'Error in LLM stream: {e}', exc_info=True)
            raise
        finally:
            await self.chat.broadcast('%%STREAM_END%%')
            logger.debug("LLM stream finished or cancelled, sent %%STREAM_END%%")

    def display_revert_header(self, step_id: str, app_name: str, steps: list, message: str = None, target_id: str = None, revert_label: str = None, remove_padding: bool = False, show_when_finalized: bool = False):
        """Create a UI control for reverting to a previous workflow step.

        The button label uses the visual sequence number of the step.

        Args:
            step_id: The ID of the step to revert to
            app_name: The workflow app name
            steps: List of Step namedtuples defining the workflow
            message: Optional message to display (defaults to step_id)
            target_id: Optional target for HTMX updates (defaults to app container)
            revert_label: Optional custom label for the revert button
            remove_padding: Whether to remove padding from the article (for advanced layout)
            show_when_finalized: Whether to show content when workflow is finalized (default: False for backward compatibility)

        Returns:
            Card: A FastHTML Card component with revert functionality, or None if finalized and show_when_finalized=False
        """
        pipeline_id = self.db.get('pipeline_id', '')
        finalize_step = steps[-1] if steps and steps[-1].id == 'finalize' else None
        if pipeline_id and finalize_step and not show_when_finalized:
            final_data = self.get_step_data(pipeline_id, finalize_step.id, {})
            if finalize_step.done in final_data:
                return None
        step = next((s for s in steps if s.id == step_id), None)
        if not step:
            logger.error(f"Step with id '{step_id}' not found in steps list for display_revert_header.")
            return Div(f'Error: Step {step_id} not found.')
        data_collection_steps = [s for s in steps if s.id != 'finalize']
        visual_step_number = 'N/A'
        try:
            step_index = data_collection_steps.index(step)
            visual_step_number = str(step_index + 1)
        except ValueError:
            logger.warning(f"Step id '{step_id}' (show: '{step.show}') not found in data_collection_steps. Revert button will show 'Step N/A'.")
        refill = getattr(step, 'refill', False)
        target_id = target_id or f'{app_name}-container'
        form = Form(Input(type='hidden', name='step_id', value=step_id), Button(self.step_button(visual_step_number, refill, revert_label), type='submit', cls='button-revert', aria_label=f'Revert to step {visual_step_number}: {step.show}', title=f'Go back to modify {step.show}'), hx_post=f'/{app_name}/revert', hx_target=f'#{target_id}', hx_swap='outerHTML', role='form', aria_label=f'Revert to {step.show} form')
        if not message:
            return form
        article_style = 'display: flex; align-items: center; justify-content: space-between; background-color: var(--pico-card-background-color);'
        if remove_padding:
            article_style += ' padding: 0;'
        return Card(Div(message, style='flex: 1', role='status', aria_label=f'Step result: {message}'), Div(form, style='flex: 0'), style=article_style, role='region', aria_label=f'Step {visual_step_number} controls')

    def display_revert_widget(self, step_id: str, app_name: str, steps: list, message: str = None, widget=None, target_id: str = None, revert_label: str = None, widget_style=None, finalized_content=None, next_step_id: str = None):
        """Create a standardized container for widgets and visualizations.

        Core pattern for displaying rich content below workflow steps with consistent
        styling and DOM targeting for dynamic updates.

        Features:
        - Consistent padding/spacing with revert controls
        - Unique DOM addressing for targeted updates
        - Support for function-based widgets and AnyWidget components
        - Standard styling with override capability
        - Automatic finalized state handling with chain reaction preservation

        Args:
            step_id: ID of the step this widget belongs to
            app_name: Workflow app name
            steps: List of Step namedtuples defining the workflow
            message: Optional message for revert control
            widget: Widget/visualization to display
            target_id: Optional HTMX update target
            revert_label: Optional custom revert button label
            widget_style: Optional custom widget container style
            finalized_content: Content to show when workflow is finalized (if None, uses message with 🔒)
            next_step_id: Next step ID for chain reaction when finalized

        Returns:
            Div: FastHTML container with revert control and widget content, or locked Card when finalized
        """
        # Check if workflow is finalized
        pipeline_id = self.db.get('pipeline_id', '')
        finalize_step = steps[-1] if steps and steps[-1].id == 'finalize' else None
        is_finalized = False
        if pipeline_id and finalize_step:
            final_data = self.get_step_data(pipeline_id, finalize_step.id, {})
            is_finalized = finalize_step.done in final_data

        if is_finalized:
            # Create locked view for finalized workflow
            step = next((s for s in steps if s.id == step_id), None)
            step_title = step.show if step else step_id

            if finalized_content is None:
                finalized_content = P(f"Step completed: {message or step_title}")

            locked_card = Card(
                H3(f"🔒 {step_title}", role='heading', aria_level='3'),
                Div(finalized_content, cls='custom-card-padding-bg', role='status', aria_label=f'Finalized content for {step_title}'),
                role='region',
                aria_label=f'Finalized step: {step_title}'
            )

            # Add next step trigger if provided
            if next_step_id:
                return Div(
                    locked_card,
                    Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load'),
                    id=step_id
                )
            else:
                return Div(locked_card, id=step_id)

        # Normal revert widget behavior for non-finalized workflows
        revert_row = self.display_revert_header(step_id=step_id, app_name=app_name, steps=steps, message=message, target_id=target_id, revert_label=revert_label, remove_padding=True)
        if widget is None or revert_row is None:
            return revert_row

        # Use CSS class for widget content styling, allow custom widget_style override
        widget_container_attrs = {
            'id': f'{step_id}-widget-{hash(str(widget))}',
            'role': 'region',
            'aria_label': f'Widget content for {step_id}'
        }
        if widget_style:
            widget_container_attrs['style'] = widget_style
        else:
            widget_container_attrs['cls'] = 'widget-content'

        return Div(revert_row, Div(widget, **widget_container_attrs), id=f'{step_id}-content', cls='card-container', role='article', aria_label=f'Step content: {step_id}')

    def tree_display(self, content):
        """Create a styled display for file paths in tree or box format.

        Example widget function demonstrating reusable, styled components
        with consistent spacing in workflow displays.

        Args:
            content: Content to display (tree-formatted or plain path)

        Returns:
            Pre: Styled Pre component
        """
        is_tree = '\n' in content and ('└─' in content or '├─' in content)
        if is_tree:
            return Pre(content, cls='tree-display-tree')
        else:
            return Pre(content, cls='tree-display-path')

    def finalized_content(self, message: str, content=None, heading_tag=H4, content_style=None):
        """Create a finalized step display with optional content.

        Companion to display_revert_widget_advanced for finalized workflows,
        providing consistent styling for both states.

        Args:
            message: Message to display (typically with 🔒 lock icon)
            content: FastHTML component to display below message
            heading_tag: Tag to use for message (default: H4)
            content_style: Optional custom content container style

        Returns:
            Card: FastHTML Card component for finalized state
        """
        if content is None:
            return Card(message)

        # Use CSS class for finalized content styling, allow custom content_style override
        content_container_attrs = {}
        if content_style:
            content_container_attrs['style'] = content_style
        else:
            content_container_attrs['cls'] = 'finalized-content'

        return Card(heading_tag(message), Div(content, **content_container_attrs), cls='card-container')

    # START: wrap_with_inline_button
    def wrap_with_inline_button(self, input_element: Input, button_label: str = 'Next ▸', button_class: str = 'primary', show_new_key_button: bool = False, app_name: str = None, **kwargs) -> Div:
        """Wrap an input element with an inline button in a flex container.
    
        Args:
            input_element: The input element to wrap
            button_label: Text to display on the button (default: 'Next ▸')
            button_class: CSS class for the button (default: 'primary')
            show_new_key_button: Whether to show the 🆕 new key button (default: False)
            app_name: App name for new key generation (required if show_new_key_button=True)
            **kwargs: Additional attributes for the button, prefixed with 'button_' (e.g., button_data_testid='my-id')
    
        Returns:
            Div: A flex container with the input and button(s)
        """
        # Styles are now externalized to CSS classes for maintainability
    
        # Generate unique IDs for input-button association
        input_id = input_element.attrs.get('id') or f'input-{hash(str(input_element))}'
        button_id = f'btn-{input_id}'
    
        # Enhance input element with semantic attributes if not already present
        if 'aria_describedby' not in input_element.attrs:
            input_element.attrs['aria_describedby'] = button_id
        if 'id' not in input_element.attrs:
            input_element.attrs['id'] = input_id
    
        # Prepare button attributes with defaults
        button_attrs = {
            'type': 'submit',
            'cls': f'{button_class} inline-button-submit',
            'id': button_id,
            'aria_label': f'Submit {input_element.attrs.get("placeholder", "input")}',
            'title': f'Submit form ({button_label})'
        }
    
        # Process and merge kwargs, allowing overrides
        for key, value in kwargs.items():
            if key.startswith('button_'):
                # Convert button_data_testid to data-testid
                attr_name = key.replace('button_', '', 1).replace('_', '-')
                button_attrs[attr_name] = value
    
        # Create enhanced button with semantic attributes and pass through extra kwargs
        enhanced_button = Button(button_label, **button_attrs)
    
        # Prepare elements for container
        elements = [input_element, enhanced_button]
    
        # Add new key button if requested
        if show_new_key_button and app_name:
            ui_constants = CFG.UI_CONSTANTS
            # 🆕 New Key button styled via CSS class for maintainability
            new_key_button = Button(
                ui_constants['BUTTON_LABELS']['NEW_KEY'],
                type='button',  # Not a submit button
                cls='new-key-button',  # Externalized styling in styles.css
                id=f'new-key-{input_id}',
                hx_get=f'/generate-new-key/{app_name}',
                hx_target=f'#{input_id}',
                hx_swap='outerHTML',
                aria_label='Generate new pipeline key',
                title='Generate a new auto-incremented pipeline key'
            )
            elements.append(new_key_button)
    
        return Div(
            *elements,
            cls='inline-button-container',
            role='group',
            aria_label='Input with submit button' + (' and new key generator' if show_new_key_button else '')
        )
    # END: wrap_with_inline_button

    def create_standard_landing_page(self, plugin_instance):
        """
        Creates a standardized landing page for workflows using centralized UI constants.

        This helper reduces boilerplate while maintaining WET workflow explicitness.
        Each workflow still explicitly calls this method and can customize the result.

        Args:
            plugin_instance: The workflow plugin instance

        Returns:
            Container: Standard landing page structure
        """
        # Standard display name derivation
        try:
            module_file = inspect.getfile(plugin_instance.__class__)
            blank_placeholder_module = importlib.import_module('plugins.910_blank_placeholder')
            derive_public_endpoint_from_filename = blank_placeholder_module.derive_public_endpoint_from_filename
            public_app_name_for_display = derive_public_endpoint_from_filename(Path(module_file).name)
        except (TypeError, AttributeError, ImportError):
            public_app_name_for_display = plugin_instance.APP_NAME

        title = plugin_instance.DISPLAY_NAME or public_app_name_for_display.replace("_", " ").title()

        # Standard pipeline key generation and matching records
        full_key, prefix, _ = self.generate_pipeline_key(plugin_instance)
        self.pipeline_table.xtra(app_name=plugin_instance.APP_NAME)
        matching_records = [record.pkey for record in self.pipeline_table() if record.pkey.startswith(prefix)]

        # Standard form with centralized constants
        ui_constants = CFG.UI_CONSTANTS
        landing_constants = CFG.UI_CONSTANTS['LANDING_PAGE']

        return Container(
            Card(
                H2(title, role='heading', aria_level='2'),
                P(plugin_instance.ENDPOINT_MESSAGE, cls='text-secondary', role='doc-subtitle'),
                Form(
                    self.wrap_with_inline_button(
                        Input(
                            placeholder=landing_constants['INPUT_PLACEHOLDER'],
                            name='pipeline_id',
                            list='pipeline-ids',
                            type='search',
                            required=False,
                            autofocus=True,
                            value=full_key,
                            _onfocus='this.setSelectionRange(this.value.length, this.value.length)',
                            cls='contrast',
                            aria_label='Pipeline ID input',
                            aria_describedby='pipeline-help'
                        ),
                        button_label=ui_constants['BUTTON_LABELS']['ENTER_KEY'],
                        button_class=ui_constants['BUTTON_STYLES']['SECONDARY'],
                        show_new_key_button=True,
                        app_name=plugin_instance.APP_NAME
                    ),
                    self.update_datalist('pipeline-ids', options=matching_records, should_clear=not matching_records),
                    Small('Enter a new ID or select from existing pipelines', id='pipeline-help', cls='text-muted'),
                    hx_post=f'/{plugin_instance.APP_NAME}/init',
                    hx_target=f'#{plugin_instance.APP_NAME}-container',
                    role='form',
                    aria_label=f'Initialize {title} workflow'
                ),
                role='main',
                aria_label=f'{title} workflow landing page'
            ),
            Div(id=f'{plugin_instance.APP_NAME}-container', role='region', aria_label=f'{title} workflow content')
        )

    async def get_state_message(self, pkey: str, steps: list, messages: dict) -> str:
        state = self.read_state(pkey)
        logger.debug(f'\nDEBUG [{pkey}] State Check:')
        # Use Rich JSON display for state debug
        formatted_state = slog.rich_json_display(state, console_output=False, log_output=True)
        logger.debug(formatted_state)
        for step in reversed(steps):
            if step.id not in state:
                continue
            if step.done == 'finalized':
                if step.done in state[step.id]:
                    return self._log_message('finalized', messages['finalize']['complete'])
                return self._log_message('ready to finalize', messages['finalize']['ready'])
            step_data = state[step.id]
            step_value = step_data.get(step.done)
            if step_value:
                msg = messages[step.id]['complete']
                msg = msg.format(step_value) if '{}' in msg else msg
                return self._log_message(f'{step.id} complete ({step_value})', msg)
        return self._log_message('new pipeline', messages['new'])

    def _log_message(self, state_desc: str, message: str) -> str:
        safe_state = state_desc.replace('<', '\\<').replace('>', '\\>')
        safe_message = message.replace('<', '\\<').replace('>', '\\>')
        logger.debug(f'State: {safe_state}, Message: {safe_message}')
        self.append_to_conversation(message, role='system')
        return message

    @pipeline_operation
    def get_step_data(self, pkey: str, step_id: str, default=None) -> dict:
        state = self.read_state(pkey)
        return state.get(step_id, default or {})

    async def clear_steps_from(self, pipeline_id: str, step_id: str, steps: list) -> dict:
        state = self.read_state(pipeline_id)
        start_idx = next((i for i, step in enumerate(steps) if step.id == step_id), -1)
        if start_idx == -1:
            logger.error(f'[clear_steps_from] Step {step_id} not found in steps list')
            return state
        for step in steps[start_idx + 1:]:
            if (not self.PRESERVE_REFILL or not step.refill) and step.id in state:
                logger.debug(f'[clear_steps_from] Removing step {step.id}')
                del state[step.id]
        self.write_state(pipeline_id, state)
        return state

    def id_conflict_style(self):
        """Return style for ID conflict error messages"""
        return 'background-color: #ffdddd; color: #990000; padding: 10px; border-left: 5px solid #990000;'

    def generate_pipeline_key(self, plugin_instance, user_input=None):
        """Generate a standardized pipeline key using the current profile and plugin.

        Creates a composite key in the format: profile_name-plugin_name-user_id
        If user_input is numeric and less than 100, it will be formatted with leading zeros.

        Args:
            plugin_instance: The plugin instance requesting the key
            user_input: Optional user-provided ID part (defaults to auto-incrementing number)

        Returns:
            tuple: (full_key, prefix, user_part) where:
                full_key: The complete pipeline key
                prefix: The profile-plugin prefix
                user_part: The user-specific part of the key
        """
        context = self.get_plugin_context(plugin_instance)
        app_name = getattr(plugin_instance, 'APP_NAME', None)
        plugin_name = app_name or context['plugin_name'] or getattr(plugin_instance, 'DISPLAY_NAME', None) or getattr(plugin_instance, 'app_name', 'unknown')
        profile_name = context['profile_name'] or 'default'
        profile_part = profile_name.replace(' ', '_')
        plugin_part = plugin_name.replace(' ', '_')
        prefix = f'{profile_part}-{plugin_part}-'
        if user_input is None:
            self.pipeline_table.xtra()
            self.pipeline_table.xtra(app_name=app_name)
            app_records = list(self.pipeline_table())
            matching_records = [record.pkey for record in app_records if record.pkey.startswith(prefix)]
            numeric_suffixes = []
            for record_key in matching_records:
                rec_user_part = record_key.replace(prefix, '')
                if rec_user_part.isdigit():
                    numeric_suffixes.append(int(rec_user_part))
            next_number = 1
            if numeric_suffixes:
                next_number = max(numeric_suffixes) + 1
            if next_number < 100:
                user_part = f'{next_number:02d}'
            else:
                user_part = str(next_number)
        elif isinstance(user_input, int) or (isinstance(user_input, str) and user_input.isdigit()):
            number = int(user_input)
            if number < 100:
                user_part = f'{number:02d}'
            else:
                user_part = str(number)
        else:
            user_part = str(user_input)
        full_key = f'{prefix}{user_part}'
        return (full_key, prefix, user_part)

    def parse_pipeline_key(self, pipeline_key):
        """Parse a pipeline key into its component parts.

        Args:
            pipeline_key: The full pipeline key to parse

        Returns:
            dict: Contains profile_part, plugin_part, and user_part components
        """
        parts = pipeline_key.split('-', 2)
        if len(parts) < 3:
            return {'profile_part': parts[0] if len(parts) > 0 else '', 'plugin_part': parts[1] if len(parts) > 1 else '', 'user_part': ''}
        return {'profile_part': parts[0], 'plugin_part': parts[1], 'user_part': parts[2]}

    def update_datalist(self, datalist_id, options=None, should_clear=False):
        """Create a datalist with out-of-band swap for updating dropdown options.

        This helper method allows easy updates to datalist options using HTMX's
        out-of-band swap feature. It can either update with new options or clear all options.

        Args:
            datalist_id: The ID of the datalist to update
            options: List of option values to include, or None to clear
            should_clear: If True, force clear all options regardless of options parameter

        Returns:
            Datalist: A FastHTML Datalist object with out-of-band swap attribute
        """
        if should_clear or options is None:
            return Datalist(id=datalist_id, _hx_swap_oob='true')
        else:
            return Datalist(*[Option(value=opt) for opt in options], id=datalist_id, _hx_swap_oob='true')

    def run_all_cells(self, app_name, steps):
        """
        Rebuild the entire workflow UI from scratch.

        This is used after state changes that require the entire workflow to be regenerated,
        such as reverting to a previous step or jumping to a specific step. It's a core
        helper method commonly used in workflow methods like finalize, unfinalize, and
        handle_revert.

        The method creates a fresh container with all step placeholders, allowing
        the workflow to reload from the current state.

        Args:
            app_name: The name of the workflow app
            steps: List of Step namedtuples defining the workflow

        Returns:
            Div: Container with all steps ready to be displayed
        """
        placeholders = []
        for i, step in enumerate(steps):
            trigger = 'load' if i == 0 else None
            placeholders.append(Div(id=step.id, hx_get=f'/{app_name}/{step.id}', hx_trigger=trigger))
        return Div(*placeholders, id=f'{app_name}-container')

    def validate_step_input(self, value, step_show, custom_validator=None):
        """
        Validate step input with default and optional custom validation.

        This helper ensures consistent validation across all workflow steps:
        1. Basic validation: Ensures the input is not empty
        2. Custom validation: Applies workflow-specific validation logic if provided

        When validation fails, it returns an error component ready for direct
        display in the UI, helping maintain consistent error handling.

        Args:
            value: The user input value to validate
            step_show: Display name of the step (for error messages)
            custom_validator: Optional function(value) -> (is_valid, error_msg)

        Returns:
            tuple: (is_valid, error_message, P_component_or_None)
        """
        is_valid = True
        error_msg = ''
        if not value.strip():
            is_valid = False
            error_msg = f'{step_show} cannot be empty'
        if is_valid and custom_validator:
            custom_valid, custom_error = custom_validator(value)
            if not custom_valid:
                is_valid = False
                error_msg = custom_error
        if not is_valid:
            return (False, error_msg, P(error_msg, cls='text-invalid'))
        return (True, '', None)

    async def set_step_data(self, pipeline_id, step_id, step_value, steps, clear_previous=True):
        """
        Update the state for a step and handle reverting.

        This core helper manages workflow state updates, ensuring consistent state 
        management across all workflows. It handles several important tasks:

        1. Clearing subsequent steps when a step is updated (optional)
        2. Storing the new step value in the correct format
        3. Removing any revert target flags that are no longer needed
        4. Persisting the updated state to storage

        Used by workflow step_xx_submit methods to maintain state after form submissions.

        Args:
            pipeline_id: The pipeline key
            step_id: The current step ID
            step_value: The value to store for this step
            steps: The steps list
            clear_previous: Whether to clear steps after this one

        Returns:
            str: The processed step value (for confirmation messages)
        """
        if clear_previous:
            await self.clear_steps_from(pipeline_id, step_id, steps)
        state = self.read_state(pipeline_id)
        step = next((s for s in steps if s.id == step_id), None)
        if step:
            state[step_id] = {step.done: step_value}
            if '_revert_target' in state:
                del state['_revert_target']
            self.write_state(pipeline_id, state)
        return step_value

    def check_finalize_needed(self, step_index, steps):
        """
        Check if we're on the final step before finalization.

        This helper determines if the workflow is ready for finalization by checking
        if the next step in the sequence is the "finalize" step. Workflows use this
        to decide whether to prompt the user to finalize after completing a step.

        Used in step_xx_submit methods to show appropriate finalization prompts
        after the user completes the last regular step in the workflow.

        Args:
            step_index: Index of current step in steps list
            steps: The steps list

        Returns:
            bool: True if the next step is the finalize step
        """
        next_step_id = steps[step_index + 1].id if step_index < len(steps) - 1 else None
        return next_step_id == 'finalize'

    def chain_reverter(self, step_id, step_index, steps, app_name, processed_val):
        """
        Create the standard navigation controls after a step submission.
        This helper generates a consistent UI pattern for step navigation that includes:
        1. A revert control showing the current step's value
        2. An HTMX-enabled div that EXPLICITLY triggers loading the next step using
           hx_trigger="load" (preferred over relying on HTMX event bubbling)
        Now also triggers a client-side event to scroll the main content panel.
        Args:
            step_id: The current step ID
            step_index: Index of current step in steps list
            steps: The steps list
            app_name: The workflow app name
            processed_val: The processed value to display
        Returns:
            HTMLResponse: A FastHTML Div component with revert control and next step trigger,
                          wrapped in an HTMLResponse to include HX-Trigger header.
        """
        step = steps[step_index]
        next_step_id = steps[step_index + 1].id if step_index < len(steps) - 1 else None
        header_component = self.display_revert_header(step_id=step_id, app_name=app_name, message=f'{step.show}: {processed_val}', steps=steps)
        next_step_trigger_div = Div(id=next_step_id, hx_get=f'/{app_name}/{next_step_id}', hx_trigger='load') if next_step_id else Div()
        content_to_swap = Div(header_component, next_step_trigger_div, id=step_id)
        response = HTMLResponse(to_xml(content_to_swap))
        return response

    async def handle_finalized_step(self, pipeline_id, step_id, steps, app_name, plugin_instance=None):
        """
        Handle the case when a step is submitted in finalized state.

        Args:
            pipeline_id: The pipeline key
            step_id: The current step ID
            steps: The steps list
            app_name: The workflow app name
            plugin_instance: Optional plugin instance (for accessing step_messages)

        Returns:
            Div: The rebuilt workflow UI
        """
        state = self.read_state(pipeline_id)
        state[step_id] = {'finalized': True}
        self.write_state(pipeline_id, state)
        step_messages = {}
        if plugin_instance and hasattr(plugin_instance, 'step_messages'):
            step_messages = plugin_instance.step_messages
        message = await self.get_state_message(pipeline_id, steps, step_messages)
        await self.stream(message, verbatim=True)
        return self.run_all_cells(app_name, steps)

    async def finalize_workflow(self, pipeline_id, state_update=None):
        """
        Finalize a workflow by marking it as complete and updating its state.

        Args:
            pipeline_id: The pipeline key
            state_update: Optional additional state to update (beyond finalized flag)

        Returns:
            dict: The updated state
        """
        state = self.read_state(pipeline_id)
        if 'finalize' not in state:
            state['finalize'] = {}
        state['finalize']['finalized'] = True
        state['updated'] = datetime.now().isoformat()
        if state_update:
            state.update(state_update)
        self.write_state(pipeline_id, state)
        return state

    async def unfinalize_workflow(self, pipeline_id):
        """
        Unfinalize a workflow by removing the finalized flag.

        Args:
            pipeline_id: The pipeline key

        Returns:
            dict: The updated state
        """
        state = self.read_state(pipeline_id)
        if 'finalize' in state:
            del state['finalize']
        state['updated'] = datetime.now().isoformat()
        self.write_state(pipeline_id, state)
        return state


    async def process_llm_interaction(self, MODEL: str, messages: list, base_app=None) -> AsyncGenerator[str, None]:
        from rich.table import Table
        # Import the formal MCP orchestrator for passive listening
        from imports.mcp_orchestrator import parse_mcp_request
        
        url = 'http://localhost:11434/api/chat'
        payload = {'MODEL': MODEL, 'messages': messages, 'stream': True}
        accumulated_response = []
        full_content_buffer = ""
        word_buffer = ""  # Buffer for word-boundary detection
        mcp_detected = False
        chunk_count = 0

        # 🎯 GOLDEN PATH EXECUTION MATRIX - ORCHESTRATOR STATUS:
        # ✅ WORKING: XML syntax <tool><params><url>value</url></params></tool>
        # ✅ WORKING: JSON syntax <tool><params>{"url": "value"}</params></tool>
        # 🟡 INTEGRATING: [cmd arg] bracket notation syntax (parser exists, integrating now)
        # 🔴 NOT YET: python -c "..." inline code execution
        # 🔴 NOT YET: python cli.py call forwarding from message stream
        #
        # 🎓 PROGRESSIVE REVEAL DESIGN FOR LLMs (simplest first):
        # Level 1: [mcp-discover] - Ultra-simple for small models
        # Level 2: .venv/bin/python cli.py mcp-discover - Terminal proficiency
        # Level 3: python -c "from imports.ai_tool_discovery_simple_parser import execute_simple_command..."
        # Level 4: <tool name="ai_self_discovery_assistant"><params>{"discovery_type":"capabilities"}</params></tool>
        # Level 5: <tool name="ai_self_discovery_assistant"><params><discovery_type>capabilities</discovery_type></params></tool>
        # Level 6: Formal MCP Protocol - Full conversation loop with automatic tool execution
        #
        # This orchestrator monitors LLM response streams for MCP tool calls.
        # When found, tools are executed asynchronously and results injected back.

        # Match XML/JSON tool tags AND bracket notation commands
        mcp_pattern = re.compile(r'(<mcp-request>.*?</mcp-request>|<tool\s+[^>]*/>|<tool\s+[^>]*>.*?</tool>|\[[^\]]+\])', re.DOTALL)

        logger.debug("🔍 DEBUG: === STARTING process_llm_interaction ===")
        logger.debug(f"🔍 DEBUG: MODEL='{MODEL}', messages_count={len(messages)}")

        # 🚨 TRANSPARENCY: Show COMPLETE conversation history being sent to LLM
        logger.info("🔍 TRANSPARENCY: === COMPLETE CONVERSATION HISTORY ===")
        for i, msg in enumerate(messages):
            role = msg.get('role', 'unknown')
            content = msg.get('content', '')
            logger.info(f"🔍 TRANSPARENCY: Message {i}: [{role}] {content}")
        logger.info("🔍 TRANSPARENCY: === END CONVERSATION HISTORY ===")

        table = Table(title='User Input')
        table.add_column('Role', style='cyan')
        table.add_column('Content', style='orange3')
        if messages:
            # Show the current user input (last message should be the current user's message)
            current_message = messages[-1]
            role = current_message.get('role', 'unknown')
            content = current_message.get('content', '')
            if isinstance(content, dict):
                # Use Rich JSON display for LLM content formatting
                content = slog.rich_json_display(content, console_output=False, log_output=True)
            table.add_row(role, content)
            logger.debug(f"🔍 DEBUG: Current user input - role: {role}, content: '{content[:100]}...'")
        slog.print_and_log_table(table, "LLM DEBUG - ")

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        error_msg = f'Ollama server error: {error_text}'
                        logger.error(f"🔍 DEBUG: HTTP Error {response.status}: {error_text}")
                        yield error_msg
                        return

                    yield '\n'  # Start with a newline for better formatting in UI

                    async for line in response.content:
                        if not line:
                            continue
                        try:
                            chunk = json.loads(line)
                            chunk_count += 1

                            if chunk.get('done', False):
                                logger.debug(f"🔍 DEBUG: Stream complete (done=True)")
                                break

                            if (content := chunk.get('message', {}).get('content', '')):
                                # If we've already found and handled a tool call, ignore the rest of the stream.
                                if mcp_detected:
                                    continue

                                full_content_buffer += content

                                # STAGE 3: Active MCP execution - detect and execute formal MCP requests
                                formal_mcp_result = parse_mcp_request(full_content_buffer)
                                if formal_mcp_result:
                                    tool_name, inner_content = formal_mcp_result
                                    mcp_detected = True  # Stop streaming the LLM response
                                    
                                    logger.info(f"🎯 MCP ACTIVATED: Found formal MCP tool call for '{tool_name}'")
                                    logger.debug(f"🎯 MCP CONTENT: {inner_content}")
                                    
                                    # Execute the formal MCP tool call
                                    asyncio.create_task(
                                        execute_formal_mcp_tool_call(messages, tool_name, inner_content)
                                    )
                                    continue  # Skip the rest of the stream processing

                                # Use regex to find a complete MCP block
                                match = mcp_pattern.search(full_content_buffer)
                                if match:
                                    mcp_block = match.group(1)
                                    mcp_detected = True  # Flag that we've found our tool call

                                    logger.info(f"🔧 MCP CLIENT: Complete MCP tool call extracted.")
                                    logger.debug(f"🔧 MCP BLOCK:\n{mcp_block}")

                                    # Offload the tool execution to a background task
                                    asyncio.create_task(
                                        execute_and_respond_to_tool_call(messages, mcp_block)
                                    )
                                    # Now that we have the tool call, we ignore all subsequent content from this stream
                                    continue

                                # If no MCP block is detected yet, stream the content normally.
                                # This handles regular, non-tool-call conversations.
                                word_buffer += content

                                # Check if word_buffer contains start of potential MCP/tool tag or markdown code block
                                if '<tool' in word_buffer or '<mcp-request' in word_buffer or '```xml' in word_buffer:
                                    # Hold off on yielding if we might be building a tool call
                                    continue

                                parts = re.split(r'(\s+)', word_buffer)
                                if len(parts) > 1:
                                    complete_parts = parts[:-1]
                                    word_buffer = parts[-1]
                                    for part in complete_parts:
                                        accumulated_response.append(part)
                                        yield part

                        except json.JSONDecodeError:
                            logger.warning(f"🔍 DEBUG: JSON decode error on chunk #{chunk_count}")
                            continue

                    # After the loop, if there's remaining content in the buffer and no tool was called, flush it.
                    if word_buffer and not mcp_detected:
                        accumulated_response.append(word_buffer)
                        yield word_buffer

                    # Final logging table for LLM responses (including tool calls)
                    if accumulated_response:
                        final_response = ''.join(accumulated_response)
                        table = Table(title='Chat Response')
                        table.add_column('Accumulated Response')
                        table.add_row(final_response, style='green')
                        slog.print_and_log_table(table, "LLM RESPONSE - ")

        except aiohttp.ClientConnectorError as e:
            error_msg = 'Unable to connect to Ollama server. Please ensure Ollama is running.'
            logger.error(f"🔍 DEBUG: Connection error: {e}")
            yield error_msg
        except Exception as e:
            error_msg = f'Error: {str(e)}'
            logger.error(f"🔍 DEBUG: Unexpected error in process_llm_interaction: {e}")
            yield error_msg

    def read(self, job: str) -> dict:
        """Reads the entire state dictionary for a given job (pipeline_id)."""
        state = self.read_state(job)
        state.pop('created', None)
        state.pop('updated', None)
        return state
    
    def write(self, job: str, state: dict):
        """Writes an entire state dictionary for a given job (pipeline_id)."""
        existing_state = self.read_state(job)
        if 'created' in existing_state:
            state['created'] = existing_state['created']
        self.write_state(job, state)
    
    def set(self, job: str, step: str, value: any):
        """Sets a key-value pair within a job's state for notebook usage."""
        state = self.read_state(job)
        if not state:
            state = {'created': self.get_timestamp()}
    
        state[step] = value
        state['updated'] = self.get_timestamp()
    
        payload = {
            'pkey': job,
            'app_name': 'notebook',
            'data': json.dumps(state),
            'created': state.get('created', state['updated']),
            'updated': state['updated']
        }
        self.pipeline_table.upsert(payload, pk='pkey')
    
    def get(self, job: str, step: str, default: any = None) -> any:
        """Gets a value for a key within a job's state."""
        state = self.read_state(job)
        return state.get(step, default)

    async def scrape(self, 
                     url: str, 
                     take_screenshot: bool = False, 
                     mode: str = 'selenium', 
                     headless: bool = True, 
                     verbose: bool = True, 
                     persistent: bool = False, 
                     profile_name: str = "default", 
                     delay_range: tuple = None, **kwargs):
        """
        Gives AI "eyes" by performing browser automation or HTTP requests to scrape a URL.

        This method is the primary entrypoint for scraping and supports multiple modes.
        The default mode is 'selenium' which uses a full browser.

        Args:
            url (str): The URL to scrape.
            take_screenshot (bool): Whether to capture a screenshot (selenium mode only). Defaults to False.
            mode (str): The scraping mode to use ('selenium', 'requests', etc.). Defaults to 'selenium'.
            headless (bool): Whether to run the browser in headless mode (selenium mode only). Defaults to True.
            persistent (bool): Whether to use a persistent browser profile. Defaults to False.
            profile_name (str): The name of the persistent profile to use. Defaults to "default".
            delay_range (tuple): A tuple (min, max) for random delay in seconds between requests.
            **kwargs: Additional parameters to pass to the underlying automation tool.

        Returns:
            dict: The result from the scraper tool, including paths to captured artifacts.
        """
        from tools.scraper_tools import selenium_automation
        from urllib.parse import urlparse, quote
        from datetime import datetime

        logger.info(f"👁️‍🗨️ Initiating scrape for: {url} (Mode: {mode}, Headless: {headless}, Persistent: {persistent})")

        # --- New Directory Logic ---
        parsed_url = urlparse(url)
        domain = parsed_url.netloc
        path = parsed_url.path or '/'
        # Use quote with an empty safe string to encode everything, including slashes
        url_path_slug = quote(path, safe='')

        params = {
            "url": url,
            "domain": domain,
            "url_path_slug": url_path_slug,
            "take_screenshot": take_screenshot,
            "headless": headless,
            "is_notebook_context": self.is_notebook_context, # Pass the context flag
            "verbose": verbose,
            "persistent": persistent,
            "profile_name": profile_name,
            "delay_range": delay_range,
            **kwargs # Pass through any other params
        }

        if mode == 'selenium':
            try:
                result = await selenium_automation(params)
                return result
            except Exception as e:
                logger.error(f"❌ Advanced scrape failed for {url}: {e}")
                return {"success": False, "error": str(e)}
        else:
            logger.warning(f"Scrape mode '{mode}' is not yet implemented.")
            return {"success": False, "error": f"Mode '{mode}' not implemented."}

    def _find_project_root(self, start_path):
        """Walks up from a starting path to find the project root (marked by 'flake.nix')."""
        current_path = Path(start_path).resolve()
        while current_path != current_path.parent:
            if (current_path / 'flake.nix').exists():
                return current_path
            current_path = current_path.parent
        return None

    def nbup(self, notebook_filename: str, modules: tuple = None):
        """
        Cleans and syncs a notebook and optionally its associated Python modules
        from the working 'Notebooks/' directory back to the version-controlled
        'assets/nbs/' template directory.
        """
        # Import necessary libraries inside the function
        import nbformat
        from pathlib import Path
        import os
        import shutil
        import ast
        import astunparse # Our new dependency
        import re # Need to import 're' for the regex part

        ### INPUT PROCESSING START ###
        # Ensure the notebook filename has the .ipynb extension
        if not notebook_filename.endswith(".ipynb"):
            notebook_filename = f"{notebook_filename}.ipynb"
        ### INPUT PROCESSING END ###

        ### NEW LOGIC STARTS HERE ###
        class SecretScrubber(ast.NodeTransformer):
            """An AST transformer to replace string literals in assignments with None."""
            def visit_Assign(self, node):
                # Check if the value being assigned is a string constant
                if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                    # Replace the string value with None
                    node.value = ast.Constant(value=None)
                return node
        ### NEW LOGIC ENDS HERE ###

        # --- Define Sample Data for Scrubbing ---
        SAMPLE_FILTERS_SOURCE = [
            "# --- Define Custom Excel Tab Filters --- \n",
            "# (This list is scrubbed by pip.nbup() and returned to this default)\n",
            "\n",
            "targeted_filters = [\n",
            "    (\"Gifts\", ['gift', 'gifts', 'idea', 'ideas', 'present', 'presents', 'give', 'giving', 'black friday', 'cyber monday', 'cyber week', 'bfcm', 'bf', 'cm', 'holiday', 'deals', 'sales', 'offer', 'discount', 'shopping']),\n",
            "    (\"Broad Questions\", '''am are can could did do does for from had has have how i is may might must shall should was were what when where which who whom whose why will with would'''.split()),\n",
            "    (\"Narrow Questions\", '''who whom whose what which where when why how'''.split()),\n",
            "    (\"Popular Modifiers\", ['how to', 'best', 'review', 'reviews']),\n",
            "    (\"Near Me\", ['near me', 'for sale', 'nearby', 'closest', 'near you', 'local'])\n",
            "]\n",
            "\n",
            "pip.set(job, 'targeted_filters', targeted_filters)\n",
            "print(f\"✅ Stored {len(targeted_filters)} custom filter sets in pip state.\")"
        ]
        SAMPLE_PROMPT_SOURCE_FAQ = [
            "**Your Role (AI Content Strategist):**\n",
            "\n",
            "You are an AI Content Strategist. \n",
            "Make 5 Frequently Asked Questions for each page.\n",
            "For each question, produce the following so it fits the data structure:\n",
            "\n",
            "1. priority: integer (1-5, 1 is highest)\n",
            "2. question: string (The generated question)\n",
            "3. target_intent: string (What is the user's goal in asking this?)\n",
            "4. justification: string (Why is this a valuable question to answer? e.g., sales, seasonal, etc.)"
        ]

        SAMPLE_PROMPT_SOURCE_URLI = [
            "**Your Role (SEO URL Auditor):**\n",
            "\n",
            "Based on the input data for a single webpage (URL, title, h1s, h2s, status code, and markdown body), provide the following:\n",
            "\n",
            "1.  **ai_selected_keyword**: The single best keyword phrase (2-5 words) the page appears to be targeting. Prioritize the \`title\` and \`h1_tags\` for this selection.\n",
            "2.  **ai_score**: On a scale of 1-5 (5 is best), how well-aligned the page's content (\`title\`, \`h1s\`, \`h2s\`, \`markdown\`) is to this single keyword. A 5 means the keyword is used effectively and naturally in key places. A 1 means it's barely present.\n",
            "3.  **keyword_rationale**: A brief (1-sentence) rationale for the score, including the user's most likely search intent (Informational, Commercial, Navigational, or Transactional)."
        ]

        PROMPT_MAP = {
            "FAQuilizer": SAMPLE_PROMPT_SOURCE_FAQ,
            "URLinspector": SAMPLE_PROMPT_SOURCE_URLI,
        }

        SAMPLE_URL_LIST_SOURCE = [
            "# Enter one URL per line\n",
            "https://nixos.org/     # Linux\n",
            "https://jupyter.org/   # Python\n",
            "https://neovim.io/     # vim\n",
            "https://git-scm.com/   # git\n",
            "https://www.fastht.ml/ # FastHTML\n"
            'https://pipulate.com/  # AIE (Pronounced "Ayyy")'
        ]

        # 1. Find the project root in a portable way
        project_root = self._find_project_root(os.getcwd())
        if not project_root:
            print("❌ Error: Could not find project root (flake.nix). Cannot sync.")
            return

        # --- Notebook Sync Logic ---
        print(f"🔄 Syncing notebook '{notebook_filename}'...")
        notebook_source_path = project_root / "Notebooks" / notebook_filename
        notebook_dest_path = project_root / "assets" / "nbs" / notebook_filename

        if not notebook_source_path.exists():
            print(f"❌ Error: Source notebook not found at '{notebook_source_path}'")
        else:
            try:
                with open(notebook_source_path, 'r', encoding='utf-8') as f:
                    nb = nbformat.read(f, as_version=4)

                # --- Scrub proprietary data ---
                notebook_base_name = Path(notebook_filename).stem
                prompt_source_to_use = PROMPT_MAP.get(notebook_base_name, SAMPLE_PROMPT_SOURCE_FAQ)

                for cell in nb.cells:
                    tags = cell.metadata.get("tags", [])
                    if "prompt-input" in tags:
                        cell.source = prompt_source_to_use
                        print(f"    ✓ Scrubbed and replaced 'prompt-input' cell using prompt for '{notebook_base_name}'.")
                    elif "url-list-input" in tags:
                        cell.source = SAMPLE_URL_LIST_SOURCE
                        print("    ✓ Scrubbed and replaced 'url-list-input' cell.")
                    elif "custom-filters-input" in tags:
                        cell.source = SAMPLE_FILTERS_SOURCE
                        print("    ✓ Scrubbed and replaced 'custom-filters-input' cell.")

                    ### NEW LOGIC STARTS HERE ###
                    elif "secrets" in tags and cell.cell_type == 'code':
                        try:
                            # First, do the robust AST-based scrubbing for variable assignments
                            tree = ast.parse(cell.source)
                            scrubber = SecretScrubber()
                            transformed_tree = scrubber.visit(tree)
                            scrubbed_source = astunparse.unparse(transformed_tree)
                            # Then, run the existing regex for pip.api_key for backward compatibility
                            cell.source = re.sub(
                                r'(key\s*=\s*)["\'].*?["\']',
                                r'\1None',
                                scrubbed_source
                            )
                            print("    ✓ Scrubbed variable assignments in 'secrets' cell.")
                        except SyntaxError:
                            print("    ⚠️ Could not parse 'secrets' cell, falling back to regex only.")
                            # Fallback to just the regex if AST fails
                            cell.source = re.sub(r'(key\s*=\s*)["\'].*?["\']', r'\1None', cell.source)
                    ### NEW LOGIC ENDS HERE ###

                # --- Existing Cleaning Logic ---
                original_cell_count = len(nb.cells)
                pruned_cells = [
                    cell for cell in nb.cells if 'pip.nbup' not in cell.source
                ]
                if len(pruned_cells) < original_cell_count:
                    print("    ✓ Auto-pruned the 'pip.nbup()' command cell from the template.")
                nb.cells = pruned_cells

                for cell in nb.cells:
                    if cell.cell_type == 'code':
                        # Normalize cell source to string if it's a list
                        source_text = cell.source
                        if isinstance(source_text, list):
                            source_text = "".join(source_text)
                        
                        # This regex is still needed for calls not in a 'secrets' cell
                        if "secrets" not in cell.metadata.get("tags", []):
                            cell.source = re.sub(r'(key\s*=\s*)["\'].*?["\']', r'\1None', source_text)

                        # Clear outputs and execution counts
                        cell.outputs.clear()
                        cell.execution_count = None
                        if 'metadata' in cell and 'execution' in cell.metadata:
                            del cell.metadata['execution']

                with open(notebook_dest_path, 'w', encoding='utf-8') as f:
                    nbformat.write(nb, f)
                print(f"✅ Success! Notebook '{notebook_filename}' has been cleaned and synced.")

            except Exception as e:
                print(f"❌ An error occurred during the notebook sync process: {e}")

        # --- Module Sync Logic (remains unchanged) ---
        if modules:
            print("\n--- Syncing Associated Modules ---")
            if isinstance(modules, str): modules = (modules,)
            for module_name in modules:
                module_filename = f"{module_name}.py"
                module_source_path = project_root / "Notebooks" / "imports" / module_filename # Look inside imports/
                module_dest_path = project_root / "assets" / "nbs" / "imports" / module_filename # Sync back to imports/
                if module_source_path.exists():
                    try:
                        shutil.copy2(module_source_path, module_dest_path)
                        print(f"    🧬 Synced module: '{module_filename}'")
                    except Exception as e:
                        print(f"    ❌ Error syncing module '{module_filename}': {e}")
                else:
                    print(f"    ⚠️ Warning: Module file not found, skipping sync: '{module_source_path}'")


    def api_key(self, job: str, service: str = 'google', key: str = None):
        """
        Handles getting, storing, and configuring a Google API key for a given service,
        and includes validation before saving.

        - If `key` is provided, it attempts a one-shot validation.
        - If `key` is None, it checks for a stored key, validates it, and if invalid,
          enters an interactive prompt loop until a valid key is entered or the
          user cancels (by pressing Enter).
        """
        if service.lower() != 'google':
            print(f"⚠️ Service '{service}' not yet supported. Only 'google' is currently configured.")
            return False

        if not GOOGLE_AI_AVAILABLE:
            print("❌ Error: The 'google-generativeai' package is not installed.")
            print("   Please run: pip install google-generativeai")
            return False

        api_key_step = "google_api_key"

        def validate_key(api_key_to_validate):
            try:
                genai.configure(api_key=api_key_to_validate)
                model = genai.GenerativeModel('gemini-2.5-flash')
                model.generate_content("test", generation_config=genai.types.GenerationConfig(max_output_tokens=1))
                return True
            except (google_exceptions.PermissionDenied, google_exceptions.Unauthenticated) as e:
                print(f"❌ API Key Validation Failed. Please try again or press Enter to cancel.")
                print(f"   Error: {e}\n")
                return False
            except Exception as e:
                print(f"❌ An unexpected error occurred: {e}. Please try again or press Enter to cancel.\n")
                return False

        # --- Scenario 1: Key is provided directly (non-interactive "one-shot" attempt) ---
        if key is not None:
            print("Checking API key provided via parameter...")
            if not key: # Check for empty string ""
                 print("❌ API Key provided is empty.")
                 return False

            if validate_key(key):
                self.set(job, api_key_step, key)
                print("✅ Google AI configured and key validated successfully.")
                return True
            else:
                return False

        # --- Scenario 2: No key provided (interactive mode) ---
        # First, check if a non-empty key is already stored and valid.
        stored_key = self.get(job, api_key_step)
        # Explicitly check if stored_key exists AND is not just whitespace
        if stored_key and stored_key.strip():
            print("Validating stored API key...")
            if validate_key(stored_key):
                print("✅ Stored Google AI key is valid and configured.")
                return True
            else:
                print(f"⚠️ Stored API key failed validation. Please re-enter your key.")
                # Clear the invalid stored key so we prompt correctly
                self.set(job, api_key_step, None) 

        # No valid key stored or provided. Enter the prompt loop.
        print("\n💡 To cancel API key setup, just press Enter without typing a key.")
        print("   (Note: If the kernel seems 'stuck' after entry, it might be an invalid key. Press Esc, 0, 0 to interrupt.)")

        while True:
            try:
                prompt_message = "Enter your Google AI API Key (or press Enter to cancel): "
                api_key_input = getpass.getpass(prompt_message)
            except Exception as e:
                print(f"❌ Could not prompt for API key in this environment: {e}")
                return False # Exit if prompting fails

            # Check for cancel condition (empty string entered by user)
            if not api_key_input.strip():
                print("🚫 API Key setup cancelled by user.")
                return False # Exit function if user cancels

            # A non-empty key was entered, now validate it.
            print("Validating new key...")
            if validate_key(api_key_input):
                self.set(job, api_key_step, api_key_input)
                print("✅ Google AI configured and key validated successfully.")
                return True # Exit loop and function with success

    def prompt(self, prompt_text: str, model_name: str = 'gemini-2.5-flash'):
        """
        Sends a simple, one-shot prompt to the configured AI model and returns the response.
        This is a bare-minimum implementation for demonstration, not a chat system.
        """
        if not GOOGLE_AI_AVAILABLE:
            error_msg = "❌ Error: The 'google-generativeai' package is not installed."
            print(error_msg)
            return error_msg

        print(f"🤖 Sending prompt to {model_name}...")

        try:
            # Instantiate the model for this specific call
            model = genai.GenerativeModel(model_name)
            
            # Send the prompt and get the response
            response = model.generate_content(prompt_text)
            
            # Extract and return the text
            response_text = response.text.strip()
            print("✅ AI response received.")
            return response_text

        except Exception as e:
            # Catch common errors like authentication failure or model not found
            error_msg = f"❌ AI prompt failed: {e}"
            print(error_msg)
            print("   Did you remember to run pip.api_key(job) in a previous cell?")
            return error_msg
