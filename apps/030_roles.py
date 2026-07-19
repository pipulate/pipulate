# Rename file to create a generic list plugin (e.g. tasks.py, competitors.py)

import importlib.util
import inspect
import os
import re
import sys
import fastlite
from fasthtml.common import *
from loguru import logger
from server import get_db_filename, title_name
from imports.crud import BaseCrud

# ROLES constant is now used for discovery, not for defining the roles themselves.
ROLES = ["Core"]

# Plugin visibility is now determined by actual ROLES declarations in plugin files

class PluginIdentityManager:
    EMOJI = '👥'

    def __init__(self, filename=None):
        if not filename:
            filename = os.path.basename(__file__)
        self.original_name = filename.replace('.py', '')
        self.name = re.sub(r'^\d+_', '', self.original_name)
        self.ENDPOINT_PREFIX = f"/{self.name}"
        self.LIST_ID = f"{self.name}-list"
        self.ITEM_CLASS = f"{self.name}-item"
        self.FORM_FIELD_NAME = f"{self.name}-text"
        self.INPUT_ID = f"{self.name}-input"
        self.CONTAINER_ID = f"{self.name}-container"

    @property

    def DISPLAY_NAME(self):
        name = title_name(self.name)
        if self.EMOJI:
            return f"{self.EMOJI} {name}"
        return name

    @property

    def DB_TABLE_NAME(self):
        return self.name

    @property
    def TRAINING_PROMPT(self):
        """Load the roles skill from Notebooks/.agents/skills/roles/SKILL.md (graceful fallback)."""
        skill_path = os.path.join(os.path.dirname(__file__), '..', 'Notebooks', '.agents', 'skills', 'roles', 'SKILL.md')
        try:
            with open(skill_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception:
            return (
                '# Pipulate Roles System\n\n'
                'SKILL.md not found at Notebooks/.agents/skills/roles/SKILL.md. '
                'The Roles app is the homepage and APP-menu control center: checkboxes toggle roles, '
                'drag reorders the APP menu, Core is always on. Secret word: ORCHESTRATOR.'
            )


class CrudCustomizer(BaseCrud):
    def __init__(self, table, plugin):
        self.plugin = plugin
        self.pipulate_instance = getattr(plugin, 'pipulate', None)
        super().__init__(
            name=plugin.name, table=table, toggle_field='done',
            sort_field='priority', pipulate_instance=self.pipulate_instance
        )
        self.item_name_field = 'text'

    def render_item(self, item):
        return render_item(item, self)

    def prepare_insert_data(self, form):
        text = form.get(self.plugin.FORM_FIELD_NAME, '').strip()
        if not text:
            return None

        roles_config = getattr(self.plugin.config, 'ROLES_CONFIG', {})
        if text in roles_config:
            priority = roles_config[text].get('priority', 99)
        else:
            all_items = self.table()
            max_priority = max((i.priority or 0 for i in all_items), default=len(roles_config)) + 1
            priority = int(form.get(f"{self.plugin.name}_priority", max_priority))

        default_active = getattr(self.plugin.config, 'DEFAULT_ACTIVE_ROLES', set())
        insert_data = { "text": text, "done": text in default_active, "priority": priority }
        return insert_data

    def prepare_update_data(self, form):
        text = form.get(self.plugin.FORM_FIELD_NAME, '').strip()
        if not text:
            return None
        return {"text": text}

    async def sort_items(self, request):
        """Override sort_items to include Default button update."""
        try:
            # Call the parent sort method
            result = await super().sort_items(request)
            
            # Add out-of-band update for the Default button
            from fasthtml.common import HTMLResponse, to_xml
            import json
            
            # Get the updated button
            updated_button = await self.plugin.update_default_button(request)
            
            # Add hx-swap-oob attribute correctly
            if hasattr(updated_button, 'attrs'):
                updated_button.attrs['hx-swap-oob'] = 'true'
            else:
                # If attrs doesn't exist, create it
                updated_button.attrs = {'hx-swap-oob': 'true'}
            
            # Create response with the button update
            button_html = to_xml(updated_button)
            response = HTMLResponse(str(button_html))
            response.headers['HX-Trigger'] = json.dumps({'refreshAppMenu': {}})
            return response
            
        except Exception as e:
            logger.error(f"Error in sort_items: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            # Return empty response on error
            from fasthtml.common import HTMLResponse
            return HTMLResponse('')

    async def toggle_role(self, request):
        """Custom toggle method that includes Default button update and messaging."""
        try:
            # 1. Extract item_id from the request path
            path_parts = request.url.path.split('/')
            item_id = int(path_parts[-1])
            
            # 2. Update Database State
            item = self.table[item_id]
            if item.text != "Core":
                item.done = not item.done
                self.table.update(item)
                
                # Send narrative feedback to the chat
                status_text = 'enabled' if item.done else 'disabled'
                action_details = f"The role '{item.text}' is now {status_text}."
                self.safe_send_message(action_details, verbatim=True)
            
            # 3. Prepare the Multi-Part UI Response
            # Part A: The updated Role Item (the checkbox row)
            updated_item_html = self.render_item(item)
            
            # Part B: The updated Default Button (calculates if it should be disabled)
            updated_button = await self.plugin.update_default_button(request)

            # CRITICAL: Tell HTMX to swap the button "Out of Band" (wherever its ID is)
            # instead of inside the target row.
            updated_button.attrs['hx-swap-oob'] = 'true'
            
            # Return both components wrapped in a Group
            return Group(updated_item_html, updated_button)
            
        except Exception as e:
            logger.error(f"Error in toggle_role: {e}")
            return HTMLResponse('Error toggling role', status_code=500)


class CrudUI(PluginIdentityManager):
    DEFAULT_BUTTON_TEXT = "Restore Default Selections"
    DEFAULT_BUTTON_TOOLTIP = "Restore default role selections and order"

    @property
    def H3_HEADER(self):
        return f"Customize the APP menu to your AI SEO needs."

    @property
    def ENDPOINT_MESSAGE(self):
        return f"Configure {self.get_app_name()} how you like. Check to add Roles to APP menu. Drag-to-reorder. Click any role to expand and see which APPs it affects - each APP link navigates directly to that feature. You can also Search Plugins in the nav menu above."

    def __init__(self, app, pipulate, pipeline, db_dictlike, config):
        """Initialize the Roles Plugin with injected configuration."""
        super().__init__()
        self.app = app
        self.pipulate = pipulate
        self.pipeline_table = pipeline
        self.db_dictlike = db_dictlike
        self.config = config  # Store the passed-in config from server.py

        # Use the passed-in config for UI constants
        self.UI_CONSTANTS = {
            'TYPOGRAPHY': {
                'SMALL_TEXT': '0.75rem',
                'TINY_TEXT': '0.8rem',
                'DESCRIPTION_TEXT': '0.9rem',
                'LINE_HEIGHT_COMPACT': '1.2',
                'LINE_HEIGHT_NORMAL': '1.3',
            },
            'SPACING': {
                'PLUGIN_ITEM_MARGIN': '0.1rem',
                'SECTION_MARGIN': '0.25rem',
                'CARD_MARGIN': '0.5rem',
                'CONTAINER_PADDING': '0.5rem',
                'DESCRIPTION_PADDING': '0.75rem',
                'LARGE_MARGIN': '1rem',
                'BORDER_RADIUS': '0.25rem',
                'BORDER_WIDTH': '3px',
            },
            'ROLE_COLORS': getattr(self.config, 'ROLE_COLORS', {}),
            'FALLBACK_COLORS': {
                'border': 'var(--pico-color-azure-500)',
                'background': 'var(--pico-card-background-color)'
            }
        }

        logger.debug(f"{self.DISPLAY_NAME} Plugin initializing...")

        db_path = os.path.join(os.path.dirname(__file__), "..", get_db_filename())  # 🚨 CRITICAL FIX: Use dynamic database resolution
        logger.debug(f"Using database path: {db_path}")

        self.plugin_db = fastlite.database(db_path)

        schema = {
            "id": int,
            "text": str,
            "done": bool,
            "priority": int,
            "pk": "id"
        }
        schema_fields = {k: v for k, v in schema.items() if k != 'pk'}
        primary_key = schema.get('pk')

        if not primary_key:
            logger.error("Primary key 'pk' must be defined in the schema dictionary!")
            raise ValueError("Schema dictionary must contain a 'pk' entry.")

        try:
            table_handle = self.plugin_db.t[self.DB_TABLE_NAME]
            logger.debug(f"Got potential table handle via .t accessor: {table_handle}")

            self.table = table_handle.create(
                **schema_fields,
                pk=primary_key,
                if_not_exists=True
            )
            logger.info(f"Fastlite '{self.DB_TABLE_NAME}' table created or accessed via handle: {self.table}")

            self.table.dataclass()
            logger.info(f"Called .dataclass() on table handle to enable dataclass returns.")

        except Exception as e:
            logger.error(f"Error creating/accessing '{self.DB_TABLE_NAME}' table: {e}")
            raise

        self.app_instance = CrudCustomizer(table=self.table, plugin=self)
        logger.debug(f"{self.DISPLAY_NAME}App instance created.")

        self.register_plugin_routes()
        logger.debug(f"{self.DISPLAY_NAME} Plugin initialized successfully.")

        # CRITICAL: Roles are global - initialize once for all profiles
        self.ensure_roles_initialized()

    def get_app_name(self):
        """Get the app name from whitelabel.txt file."""
        try:
            app_name_path = os.path.join(os.path.dirname(__file__), "..", "whitelabel.txt")
            with open(app_name_path, 'r', encoding='utf-8') as f:
                return f.read().strip()
        except Exception:
            return "Pipulate"  # Fallback to default name

    async def check_ollama_availability(self):
        """Check if Ollama is running and has models available - uses centralized check."""
        from imports.crud import check_ollama_availability
        return await check_ollama_availability()

    def ensure_roles_initialized(self):
        """Ensure all roles from config are initialized in the database."""
        try:
            existing_roles = {role.text: role for role in self.table()}
            roles_config = getattr(self.config, 'ROLES_CONFIG', {})
            default_active = getattr(self.config, 'DEFAULT_ACTIVE_ROLES', set())

            logger.debug(f"ROLES: Found {len(existing_roles)} existing roles in database.")
            logger.debug(f"ROLES: Found {len(roles_config)} roles in configuration.")

            for role_name, config_data in roles_config.items():
                if role_name not in existing_roles:
                    logger.info(f"ROLES: Creating missing role '{role_name}' with priority {config_data['priority']}")
                    self.table.insert(
                        text=role_name,
                        done=(role_name in default_active),
                        priority=config_data['priority']
                    )
                else:
                    logger.debug(f"ROLES: Role '{role_name}' already exists in database.")

            logger.info(f"ROLES: Role initialization complete.")

        except Exception as e:
            logger.error(f"ROLES: Error during role initialization: {e}")

    def initialize_roles(self):
        """Legacy method name for backward compatibility."""
        return self.ensure_roles_initialized()

    def register_plugin_routes(self):
        """Register the routes for the roles plugin."""
        prefix = self.ENDPOINT_PREFIX
        routes = [
            (f'{prefix}/toggle/{{item_id:int}}', self.app_instance.toggle_role, ['POST']),
            (f"{prefix}_sort", self.app_instance.sort_items, ['POST']),
            (f"{prefix}/select_default", self.select_default_roles, ['POST']),
            (f"{prefix}/update_default_button", self.update_default_button, ['POST']),
        ]
        for path, handler, methods in routes:
            self.app.route(path, methods=methods)(handler)

    async def landing(self, request=None):
        """Render the main roles management interface."""
        items_query = self.table()
        items = sorted(items_query, key=lambda item: item.priority if item.priority is not None else 99)

        return Div(
            Card(
                H3(self.H3_HEADER),
                Div(
                    Button(Img(src='/assets/feather/rewind.svg', 
                              alt='Reset', 
                              style='width: 14px; height: 14px; margin-right: 0.25rem; filter: brightness(0) invert(1);'),
                           self.DEFAULT_BUTTON_TEXT, 
                           hx_post=f"{self.ENDPOINT_PREFIX}/select_default",
                           cls="secondary",
                           style=f"font-size: 0.8rem; padding: 0.25rem 0.5rem; display: flex; align-items: center; opacity: {'0.4' if self.is_in_default_state() else '1.0'};",
                           disabled=self.is_in_default_state(),
                           title=self.DEFAULT_BUTTON_TOOLTIP + (" (already at default)" if self.is_in_default_state() else ""),
                           id="default-button"),
                    style="margin-bottom: 0.5rem; display: flex; gap: 0.25rem; flex-wrap: wrap; justify-content: center;"
                ),
                Ol(
                    *[self.app_instance.render_item(item) for item in items],
                    id=self.LIST_ID, cls="sortable pl-lg",
                    hx_post=f"{self.ENDPOINT_PREFIX}_sort", hx_swap="none",
                    data_plugin_name=self.name
                )
            ),
            id=self.CONTAINER_ID,
        )

    async def render(self, render_items=None):
        """Render method for compatibility."""
        return await self.landing()



    async def select_default_roles(self, request):
        """Reset roles to DEFAULT_ACTIVE_ROLES configuration and original sort order."""

        try:
            # 1. Get the defaults from the injected config
            default_active = getattr(self.config, 'DEFAULT_ACTIVE_ROLES', set())
            roles_config = getattr(self.config, 'ROLES_CONFIG', {})
            
            all_roles = self.table()
    
            logger.info(f"DEFAULT: Found {len(all_roles)} roles in database")
            
            changes_made = []
            for role in all_roles:
                # Reset selection state
                should_be_active = role.text in default_active
                role_changed = role.done != should_be_active
                if role_changed:
                    role.done = should_be_active
                    status = 'enabled' if should_be_active else 'disabled'
                    changes_made.append(f"{role.text} {status}")
                
                # Reset priority to config ROLES_CONFIG (the same source as initialization)
                original_priority = roles_config.get(role.text, {}).get('priority', 99)
                priority_changed = role.priority != original_priority
                
                logger.info(f"DEFAULT: Role '{role.text}' - current priority: {role.priority}, target priority: {original_priority}, needs change: {priority_changed}")
                
                if priority_changed:
                    role.priority = original_priority
                
                # Update if anything changed
                if role_changed or priority_changed:
                    logger.info(f"DEFAULT: UPDATING role '{role.text}' - done: {role.done}, priority: {role.priority}")
                    self.table.update(role)
                    logger.info(f"DEFAULT: UPDATE COMPLETE for role '{role.text}'")
                else:
                    logger.info(f"DEFAULT: No changes needed for role '{role.text}'")
            
            # Send message via temp_message system (survives page refresh)
            if changes_made:
                changes_list = ', '.join(changes_made)
                action_details = f"Reset to default roles: {changes_list}"
                self.db_dictlike['temp_message'] = action_details
            else:
                action_details = "Roles were already at default settings."
                self.db_dictlike['temp_message'] = action_details
            
            # Return HX-Refresh header to trigger full page reload
            from fasthtml.common import HTMLResponse
            response = HTMLResponse('')
            response.headers['HX-Refresh'] = 'true'
            return response
        except Exception as e:
            logger.error(f"Error in select_default_roles: {e}")
            # Even on error, trigger page refresh to show current state
            from fasthtml.common import HTMLResponse
            response = HTMLResponse('')
            response.headers['HX-Refresh'] = 'true'
            return response

    async def render_roles_list(self):
        """Render just the roles list for HTMX updates."""
        items_query = self.table()
        roles_config = getattr(self.config, 'ROLES_CONFIG', {})
        items = sorted(items_query, key=lambda item: item.priority if item.priority is not None else 99)
        
        return Ol(
            *[self.app_instance.render_item(item) for item in items],
            id=self.LIST_ID, cls="sortable pl-lg",
            hx_post=f"{self.ENDPOINT_PREFIX}_sort", hx_swap="none",
            data_plugin_name=self.name
        )

    def is_in_default_state(self):
        """Check if current roles state matches the default configuration."""
        try:
            default_active = getattr(self.config, 'DEFAULT_ACTIVE_ROLES', set())
            roles_config = getattr(self.config, 'ROLES_CONFIG', {})
            
            all_roles = self.table()
            
            for role in all_roles:
                # Check if selection state matches default
                should_be_active = role.text in default_active
                
                if role.done != should_be_active:
                    return False
                
                # Check if priority matches default
                expected_priority = roles_config.get(role.text, {}).get('priority', 99)
                if role.priority != expected_priority:
                    return False
            
            return True
        except Exception as e:
            logger.error(f"Error checking default state: {e}")
            return False

    async def update_default_button(self, request):
        """Return the updated state of the Default button."""
        is_default = self.is_in_default_state()
        
        button = Button(Img(src='/assets/feather/rewind.svg', 
                         alt='Reset', 
                         style='width: 14px; height: 14px; margin-right: 0.25rem; filter: brightness(0) invert(1);'),
                      self.DEFAULT_BUTTON_TEXT, 
                      hx_post=f"{self.ENDPOINT_PREFIX}/select_default",
                      cls="secondary",
                      style=f"font-size: 0.8rem; padding: 0.25rem 0.5rem; display: flex; align-items: center; opacity: {'0.4' if is_default else '1.0'};",
                      disabled=is_default,
                      title=self.DEFAULT_BUTTON_TOOLTIP + (" (already at default)" if is_default else ""),
                      id="default-button")
        
        return button

def get_role_css_class(role_name):
    """Generate CSS class name for a role."""
    return f"menu-role-{role_name.lower().replace(' ', '-')}"

def render_item(item, app_instance):
    """Render a single role item with clean, discrete presentation."""
    item_id = f'{app_instance.name}-{item.id}'
    toggle_url = f"{app_instance.plugin.ENDPOINT_PREFIX}/toggle/{item.id}"

    # Get role configuration from the injected config
    roles_config = getattr(app_instance.plugin.config, 'ROLES_CONFIG', {})
    role_info = roles_config.get(item.text, {})
    description = role_info.get('description', 'No description available.')

    # Core role is always enabled and cannot be toggled
    is_core = item.text == "Core"

    # THE FIX: Derive boolean state and ensure Core is always True
    is_checked = True if is_core else bool(item.done)

    # Use a single Input definition with the correct HTMX headers
    checkbox = Input(
        type="checkbox",
        name="done", 
        checked=is_checked, # Omits attribute if False
        disabled=is_core,
        cls="flex-shrink-0",
        style=f"margin-left: {app_instance.plugin.UI_CONSTANTS['SPACING']['SECTION_MARGIN']};",
        hx_post=None if is_core else toggle_url,
        hx_swap="outerHTML",
        hx_target=f"#{item_id}"
    )

    # HTMX wiring lives on the checkbox Input above; the old htmx_attrs dict was dead.
    
    # Get plugin count for this role
    plugin_list = get_plugin_list()
    affected_plugins = [plugin for plugin in plugin_list if item.text in plugin['roles']]
    plugin_count = len(affected_plugins)
    
    # Bold title with count in parentheses, followed by colon and description
    title_and_description = Div(
        Span(item.text, cls="role-title"),
        " ",
        Span(f"({plugin_count})", cls="role-title", style="color: var(--pico-muted-color); font-weight: normal;"),
        ": ",
        Span(description, cls="role-description"),
        cls="flex-1"
    )

    # Create discrete expandable plugin list with real emojis
    plugin_info = create_plugin_visibility_table(item.text, app_instance.plugin.UI_CONSTANTS)

    return Li(
        # Main role item with checkbox and title:description - clickable to expand/collapse
        Div(
            checkbox,
            title_and_description,
            cls="flex-center-items",
            onmousedown="this.parentElement._mouseDownPos = {x: event.clientX, y: event.clientY};",
            onclick=f"""
                // Only handle click if it wasn't a drag operation and wasn't on checkbox
                if (this.parentElement._mouseDownPos && event.target.type !== 'checkbox') {{
                    const dragThreshold = 5; // pixels
                    const dragDistance = Math.sqrt(
                        Math.pow(event.clientX - this.parentElement._mouseDownPos.x, 2) +
                        Math.pow(event.clientY - this.parentElement._mouseDownPos.y, 2)
                    );

                    // Only process as click if user didn't drag beyond threshold
                    if (dragDistance < dragThreshold) {{
                        const pluginList = this.parentElement.querySelector('.plugin-expandable');
                        if (pluginList) {{
                            pluginList.style.display = pluginList.style.display === 'none' ? 'block' : 'none';
                        }}
                    }}
                    this.parentElement._mouseDownPos = null;
                }}
            """
        ),
        # Discrete expandable plugin list - hidden by default
        plugin_info,
        id=item_id,
        cls=f"card-container card-list-item {get_role_css_class(item.text)}",
        onmousedown="this._mouseDownPos = {x: event.clientX, y: event.clientY};",
        onclick=f"""
            // Only handle click if it wasn't a drag operation
            if (this._mouseDownPos) {{
                const dragThreshold = 5; // pixels
                const dragDistance = Math.sqrt(
                    Math.pow(event.clientX - this._mouseDownPos.x, 2) +
                    Math.pow(event.clientY - this._mouseDownPos.y, 2)
                );

                // Only process as click if user didn't drag beyond threshold
                if (dragDistance < dragThreshold && event.target.type !== 'checkbox' && !event.target.closest('a')) {{
                    const pluginList = this.querySelector('.plugin-expandable');
                    if (pluginList) {{
                        pluginList.style.display = pluginList.style.display === 'none' ? 'block' : 'none';
                    }}
                }}
                this._mouseDownPos = null;
            }}
        """,
        data_id=item.id,
        data_priority=item.priority or 0,
        data_plugin_item='true',
        data_list_target=app_instance.plugin.LIST_ID,
        data_endpoint_prefix=app_instance.plugin.ENDPOINT_PREFIX
    )

# Supporting functions for plugin discovery and visibility
def get_plugin_list():
    """Get list of all available plugins with their roles."""
    plugins = []
    
    # Import plugin_instances from server to use actual loaded instances
    try:
        from server import plugin_instances
        logger.debug(f"get_plugin_list: Found {len(plugin_instances)} plugin instances")
        
        for plugin_key, plugin_instance in plugin_instances.items():
            # Skip the special plugins that don't belong in role lists
            if plugin_key in ['profiles', 'roles']:
                logger.debug(f"get_plugin_list: Skipping special plugin {plugin_key}")
                continue
                
            try:
                # Get the plugin module to access ROLES
                plugin_module = sys.modules.get(plugin_instance.__module__)
                plugin_roles = getattr(plugin_module, 'ROLES', []) if plugin_module else []
                
                # Get display name from the actual instance
                display_name = getattr(plugin_instance, 'DISPLAY_NAME', plugin_key.replace('_', ' ').title())
                
                # Convert plugin_key back to filename format for consistency
                # Most plugins have numeric prefixes, so we need to find the actual filename
                plugin_filename = None
                plugin_dir = Path(__file__).parent
                
                # Try different patterns to match the plugin key to a filename
                possible_patterns = [
                    f"*_{plugin_key}.py",  # e.g., 060_tasks.py
                    f"{plugin_key}.py",   # e.g., tasks.py
                    f"*{plugin_key}.py"   # e.g., 060tasks.py (less likely)
                ]
                
                for pattern in possible_patterns:
                    matches = list(plugin_dir.glob(pattern))
                    if matches:
                        plugin_filename = matches[0].name  # Take the first match
                        break
                
                if not plugin_filename:
                    # Final fallback: assume it follows the simple pattern
                    plugin_filename = f"{plugin_key}.py"
                
                logger.debug(f"get_plugin_list: Mapped {plugin_key} to filename {plugin_filename}")
                
                logger.debug(f"get_plugin_list: Plugin {plugin_key} -> {display_name} -> roles: {plugin_roles}")
                
                plugins.append({
                    'filename': plugin_filename,
                    'module_name': plugin_key,
                    'display_name': display_name,
                    'roles': plugin_roles
                })
                
            except Exception as e:
                logger.debug(f"Could not process plugin {plugin_key}: {e}")
                continue
                
    except ImportError as e:
        logger.error(f"Could not import plugin_instances from server: {e}")
        # Fallback to the old file-based discovery method
        return get_plugin_list_fallback()
    
    logger.debug(f"get_plugin_list: Returning {len(plugins)} plugins")
    core_plugins = [p for p in plugins if 'Core' in p['roles']]
    logger.debug(f"get_plugin_list: Found {len(core_plugins)} Core plugins: {[p['display_name'] for p in core_plugins]}")
    
    return sorted(plugins, key=lambda x: x['filename'])


def get_plugin_list_fallback():
    """Fallback plugin discovery method using file system scanning."""
    plugin_dir = Path(__file__).parent
    plugins = []

    for file_path in plugin_dir.glob('*.py'):
        if file_path.name.startswith('__') or file_path.name.startswith('xx_'):
            continue

        try:
            spec = importlib.util.spec_from_file_location(file_path.stem, file_path)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                plugin_roles = getattr(module, 'ROLES', [])
                
                # Look for DISPLAY_NAME in classes first (more common pattern)
                display_name = None
                for name, obj in inspect.getmembers(module):
                    if inspect.isclass(obj) and hasattr(obj, 'DISPLAY_NAME'):
                        display_name_attr = getattr(obj, 'DISPLAY_NAME', None)
                        # Handle both properties and direct attributes
                        if isinstance(display_name_attr, property):
                            # For CRUD apps with property-based DISPLAY_NAME, replicate the logic
                            try:
                                # Check if it's a PluginIdentityManager subclass
                                if hasattr(obj, 'EMOJI'):
                                    # Replicate the PluginIdentityManager.DISPLAY_NAME property logic
                                    # Get the module filename and process it like PluginIdentityManager does
                                    filename = file_path.name.replace('.py', '')
                                    name = re.sub(r'^\d+_', '', filename)  # Remove numeric prefix
                                    display_name = title_name(name)  # Use the same title_name function
                                    
                                    emoji = getattr(obj, 'EMOJI', '')
                                    if emoji:
                                        # Put emoji at the right for consistency with workflows
                                        display_name = f"{display_name} {emoji}"
                                    break
                            except:
                                continue
                        elif display_name_attr and isinstance(display_name_attr, str):
                            display_name = display_name_attr
                            break
                
                # Fallback to module-level DISPLAY_NAME or filename-based name
                if not display_name:
                    display_name = getattr(module, 'DISPLAY_NAME', file_path.stem.replace('_', ' ').title())

                plugins.append({
                    'filename': file_path.name,
                    'module_name': file_path.stem,
                    'display_name': display_name,
                    'roles': plugin_roles
                })
        except Exception as e:
            logger.debug(f"Could not inspect plugin {file_path.name}: {e}")
            continue

    return sorted(plugins, key=lambda x: x['filename'])

def create_plugin_visibility_table(role_name, ui_constants=None):
    """Create a discrete expandable list showing plugins with real emojis."""
    plugin_list = get_plugin_list()
    affected_plugins = [plugin for plugin in plugin_list if role_name in plugin['roles']]
    
    logger.debug(f"create_plugin_visibility_table: Role '{role_name}' has {len(affected_plugins)} plugins")
    for plugin in affected_plugins:
        logger.debug(f"  - {plugin['display_name']} (from {plugin['filename']})")

    if not affected_plugins:
        return Div(
            P("No plugins assigned to this role.", style="font-style: italic; color: var(--pico-muted-color); margin: 0.5rem 0;"),
            cls="plugin-expandable role-plugin-details",
            style="display: none;"
        )

    # Create discrete plugin links using display names as-is
    plugin_items = []
    for plugin in affected_plugins:
        module_name = plugin['module_name']
        display_name = plugin['display_name']

        # Create navigation link - strip numeric prefix for URL
        import re
        clean_module_name = re.sub(r'^\d+_', '', module_name)
        plugin_url = f"/redirect/{clean_module_name}"

        # Use display name as-is without adding extra emojis
        plugin_items.append(
                            Li(
                    A(
                        display_name,
                        href=plugin_url,
                        cls="plugin-link",
                        onclick="event.stopPropagation();"
                    ),
                    cls="plugin-list-item",
                    title=f"Navigate to {display_name}"
                )
        )

    return Div(
        Ol(*plugin_items, cls="role-plugin-ordered-list role-plugin-list"),
        cls="plugin-expandable role-plugin-details",
        style="display: none;"
    )
