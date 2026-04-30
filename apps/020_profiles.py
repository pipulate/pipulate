import json
import os
import re
import sys
from typing import Any, Dict, List, Optional

import fastlite
from fasthtml.common import (H2, H3, H4, A, Button, Card, Container, Details,
                             Div, Form, Grid, Group, Hr, HTMLResponse,
                             HTTPException, Input, Label, Li, Link, Meta,
                             Option, P, Script, Select, Span, Summary,
                             Textarea, Title, Ul, to_xml)
from server import get_db_filename
from imports.crud import BaseCrud
from server import db as server_db

# Lazy imports to avoid circular dependencies - imported when needed
def get_server_functions():
    """Get server functions when needed to avoid circular imports."""
    from server import get_current_profile_id, get_profile_name, logger, plugin_instances, rt, title_name
    return get_current_profile_id, get_profile_name, logger, plugin_instances, rt, title_name

# Get logger immediately since it's used everywhere
try:
    from server import logger
except ImportError:
    # Fallback if server isn't fully loaded yet
    import logging
    logger = logging.getLogger(__name__)

ROLES = ['Core']

PLACEHOLDER_ADDRESS = 'www.site.com'
PLACEHOLDER_CODE = 'CCode (us, uk, de, etc)'


class ProfilesPluginIdentity:
    # Override this in subclasses to customize the emoji
    EMOJI = '👤'

    APP_NAME = 'profiles'

    @property
    def DISPLAY_NAME(self):
        # Use lazy import to avoid circular dependency
        _, _, _, _, _, title_name = get_server_functions()
        name = title_name('profiles')
        if self.EMOJI:
            return f"{self.EMOJI} {name}"
        return name

    ENDPOINT_MESSAGE = 'Manage user profiles (clients, customers, etc.). Each Profile is a separate workspace.'


class ProfileCrudOperations(BaseCrud):

    def __init__(self, main_plugin_instance, table, pipulate_instance):
        self.main_plugin = main_plugin_instance
        self.pipulate_instance = pipulate_instance
        super().__init__(name=main_plugin_instance.name, table=table, toggle_field='active', sort_field='priority', pipulate_instance=self.pipulate_instance)
        self.item_name_field = 'name'
        # Use static name during init to avoid circular import
        display_name_for_init = f"{main_plugin_instance.EMOJI} Profiles"
        logger.debug(f"ProfileCrudOperations initialized for {display_name_for_init} with table: {(table.name if table else 'None')}")

    def render_item(self, profile_record):
        logger.debug(f"ProfileCrudOperations.render_item called for: {(profile_record.name if profile_record else 'None')}")
        return render_profile(profile_record, self.main_plugin)

    def prepare_insert_data(self, form_data_dict):
        profile_name = form_data_dict.get('profile_name', '').strip()
        if not profile_name:
            logger.warning('Profile name cannot be empty for insert.')
            return {'name': ''}
        all_profiles = list(self.table())
        max_priority = max((p.priority or 0 for p in all_profiles), default=-1) + 1
        data = {'name': profile_name, 'real_name': form_data_dict.get('profile_real_name', '').strip(), 'address': form_data_dict.get('profile_address', '').strip(), 'code': form_data_dict.get('profile_code', '').strip(), 'active': True, 'priority': max_priority}
        logger.debug(f'Prepared insert data for profile: {data}')
        return data

    def prepare_update_data(self, form_data_dict):
        profile_name = form_data_dict.get('profile_name', '').strip()
        if not profile_name:
            logger.warning('Profile name cannot be empty for update.')
            return {'name': ''}
        data = {'name': profile_name, 'real_name': form_data_dict.get('profile_real_name', '').strip(), 'address': form_data_dict.get('profile_address', '').strip(), 'code': form_data_dict.get('profile_code', '').strip()}
        logger.debug(f'Prepared update data for profile: {data}')
        return data


class ProfilesPlugin(ProfilesPluginIdentity):

    def __init__(self, app, pipulate_instance, pipeline_table, db_key_value_store, profiles_table_from_server):
        self.app = app
        self.pipulate = pipulate_instance
        self.db_dictlike = db_key_value_store
        self.table = profiles_table_from_server
        self.name = 'profiles'
        
        # Use static display name during init to avoid circular import
        display_name_for_init = f"{self.EMOJI} Profiles"
        
        if not self.table or not hasattr(self.table, 'name') or self.table.name != 'profile':
            logger.error(f"FATAL: {display_name_for_init} initialized with invalid 'profiles_table_from_server'. Expected MiniDataAPI for 'profile', got: {type(self.table)} with name {getattr(self.table, 'name', 'UNKNOWN')}")
            raise ValueError("ProfilesPlugin requires a valid 'profiles' table object from server.py.")
        else:
            logger.info(f"{display_name_for_init} Plugin SUCCESS: Initialized with 'profiles' table object: {self.table.name}")
        self.crud_handler = ProfileCrudOperations(main_plugin_instance=self, table=self.table, pipulate_instance=self.pipulate)
        
    def count_unchecked_tasks_for_profile(self, profile_id):
        """Count unchecked tasks for a specific profile."""
        try:
            # Use direct SQL query to count unchecked tasks (done=0)
            db = fastlite.database(get_db_filename())  # 🚨 CRITICAL FIX: Use dynamic database resolution
            result = db.execute('SELECT COUNT(*) FROM tasks WHERE profile_id = ? AND done = 0', (profile_id,)).fetchone()
            return result[0] if result else 0
        except Exception as e:
            logger.warning(f"Error counting tasks for profile {profile_id}: {e}")
            return 0
        logger.debug(f'{display_name_for_init} ProfileCrudOperations instance created.')

    def register_routes(self, rt_decorator):
        self.crud_handler.register_routes(rt_decorator)
        
        # Add route for switching to tasks for a specific profile
        @rt_decorator(f'/{self.name}/switch_to_tasks/{{profile_id:int}}')
        async def switch_to_tasks(profile_id: int):
            """Set the current profile ID and redirect to tasks."""
            try:
                # Validate profile exists
                profile = self.table.get(profile_id)
                if not profile:
                    logger.warning(f"Attempted to switch to non-existent profile {profile_id}")
                    raise HTTPException(status_code=404, detail=f"Profile {profile_id} not found")
                
                # Set the current profile ID in the key-value store
                self.db_dictlike['last_profile_id'] = profile_id
                logger.info(f"Switched to profile {profile_id} ({profile.name}) for tasks")
                
                # Redirect to tasks page
                from starlette.responses import RedirectResponse
                return RedirectResponse(url='/tasks', status_code=302)
                
            except Exception as e:
                logger.error(f"Error switching to tasks for profile {profile_id}: {e}")
                raise HTTPException(status_code=500, detail="Failed to switch profile")
        
        # Add route for lock-to-profile shortcut
        @rt_decorator(f'/{self.name}/lock_to_profile/{{profile_id:int}}')
        async def lock_to_profile(profile_id: int):
            """Set profile as current AND enable lock mode - meeting prep shortcut."""
            try:
                # Validate profile exists
                profile = self.table.get(profile_id)
                if not profile:
                    logger.warning(f"Attempted to lock to non-existent profile {profile_id}")
                    raise HTTPException(status_code=404, detail=f"Profile {profile_id} not found")
                
                # Set the current profile ID in the key-value store
                self.db_dictlike['last_profile_id'] = profile_id
                
                # Enable profile lock mode - FIX: Use same key/format as dropdown toggle
                self.db_dictlike['profile_locked'] = '1'
                
                logger.info(f"🔒 Locked to profile {profile_id} ({profile.name}) - meeting prep mode activated")
                
                # Return full page refresh to sync all UI elements (dropdown toggles, etc.)
                from starlette.responses import Response
                response = Response('')
                response.headers['HX-Refresh'] = 'true'
                return response
                
            except Exception as e:
                logger.error(f"Error locking to profile {profile_id}: {e}")
                raise HTTPException(status_code=500, detail="Failed to lock profile")
        
        # Use static name to avoid potential circular import during route registration
        display_name_for_routes = f"{self.EMOJI} Profiles"
        logger.info(f"CRUD routes for {display_name_for_routes} (prefix '/{self.name}') registered by ProfileCrudOperations.")

    async def landing(self, request=None):
        # Get all profiles first
        profiles = list(self.table())
        
        # Check if profile lock is enabled - FIX: Use same key as dropdown toggle
        profile_lock_enabled = self.db_dictlike.get('profile_locked', '0') == '1'
        
        if profile_lock_enabled:
            # If locked, only show the current profile
            get_current_profile_id, _, _, _, _, _ = get_server_functions()
            current_profile_id = get_current_profile_id()
            
            if current_profile_id:
                try:
                    current_id_int = int(current_profile_id)
                    # Filter to only show the current profile
                    profiles = [p for p in profiles if int(p.id) == current_id_int]
                    logger.debug(f"Profile lock enabled - showing only profile {current_profile_id}")
                except (ValueError, TypeError):
                    logger.warning(f"Error filtering profiles for lock mode: invalid current_profile_id {current_profile_id}")
                    # If there's an error, show all profiles as fallback
            else:
                logger.warning("Profile lock enabled but no current profile ID found")
                # If no current profile, show all profiles as fallback
        
        ordered_profiles = sorted(profiles, key=lambda x: getattr(x, 'priority', 0))
        profile_list = Ul(*[render_profile(p, self) for p in ordered_profiles], id='profile-list-ul', cls='sortable list-unstyled', data_sortable_group=self.name)
        
        # Hide the add form when profile is locked
        if profile_lock_enabled:
            add_profile_form = Div()  # Empty div when locked
        else:
            add_profile_form = Form(Group(Input(placeholder='Nickname', name='profile_name', id='profile-name-input-add', autofocus=True), Input(placeholder='Real Name (Optional)', name='profile_real_name', id='profile-real-name-input-add'), Input(placeholder=PLACEHOLDER_ADDRESS, name='profile_address', id='profile-address-input-add'), Input(placeholder=PLACEHOLDER_CODE, name='profile_code', id='profile-code-input-add'), Button('Add', type='submit', id='add-profile-button')), hx_post=f'/{self.name}', hx_target='#profile-list-ul', hx_swap='beforeend', hx_on_htmx_after_request="this.reset(); this.querySelector('input[name=profile_name]').focus();")
        
        container = Div(H2('Profiles'), add_profile_form, profile_list, cls='container-centered')
        return container


def render_profile(profile_record, main_plugin_instance: ProfilesPlugin):
    # Get current profile ID to highlight the selected row
    get_current_profile_id, _, _, _, _, _ = get_server_functions()
    current_profile_id = get_current_profile_id()
    
    # Ensure proper type comparison by converting both to int
    try:
        current_id_int = int(current_profile_id) if current_profile_id is not None else None
        profile_id_int = int(profile_record.id) if profile_record.id is not None else None
        is_current_profile = current_id_int is not None and profile_id_int is not None and current_id_int == profile_id_int
        
        # Debug logging to help identify the issue
        logger.debug(f"Profile highlighting check: profile_id={profile_id_int}, current_id={current_id_int}, is_current={is_current_profile}")
    except (ValueError, TypeError) as e:
        logger.warning(f"Error comparing profile IDs: {e}. profile_record.id={profile_record.id}, current_profile_id={current_profile_id}")
        is_current_profile = False
    
    item_id_dom = f'profile-item-{profile_record.id}'
    profile_crud_handler = main_plugin_instance.crud_handler
    delete_url = profile_crud_handler.get_action_url('delete', profile_record.id)
    toggle_url = profile_crud_handler.get_action_url('toggle', profile_record.id)
    update_url = f'/{main_plugin_instance.name}/{profile_record.id}'
    name_input_update_id = f'name-update-{profile_record.id}'
    update_form_id = f'update-form-{profile_record.id}'
    profile_text_display_id = f'profile-text-display-{profile_record.id}'
    toggle_edit_js = f"document.getElementById('{profile_text_display_id}').style.display='none'; var form = document.getElementById('{update_form_id}'); form.style.display='grid'; form.classList.add('editing');document.getElementById('{item_id_dom}').classList.add('editing-item');document.getElementById('{name_input_update_id}').focus();"
    toggle_display_js = f"var form = document.getElementById('{update_form_id}'); form.style.display='none'; form.classList.remove('editing');document.getElementById('{profile_text_display_id}').style.display='flex';document.getElementById('{item_id_dom}').classList.remove('editing-item');"
    update_profile_form = Form(Div(Input(type='text', name='profile_name', value=profile_record.name, placeholder='Nickname', id=name_input_update_id, cls='mb-2'), Input(type='text', name='profile_real_name', value=profile_record.real_name or '', placeholder='Real Name (Optional)', cls='mb-2'), Input(type='text', name='profile_address', value=profile_record.address or '', placeholder=PLACEHOLDER_ADDRESS, cls='mb-2'), Input(type='text', name='profile_code', value=profile_record.code or '', placeholder=PLACEHOLDER_CODE, cls='mb-2'), style='display:grid; grid-template-columns: 1fr; gap: 0.25rem; width:100%;'), Div(Button('Save', type='submit', cls='primary', style='margin-right: 0.5rem;'), Button('Cancel', type='button', cls='secondary outline', onclick=toggle_display_js), style='margin-top:0.5rem; display:flex; justify-content:start;'), hx_post=update_url, hx_target=f'#{item_id_dom}', hx_swap='outerHTML', id=update_form_id, style='display: none; width: 100%; padding: 0.5rem; box-sizing: border-box; background-color: var(--pico-form-element-background-color); border-radius: var(--pico-border-radius);', cls='profile-edit-form')
    # Task link to switch to tasks for this profile - inside the profile display with count
    task_count = main_plugin_instance.count_unchecked_tasks_for_profile(profile_record.id)
    tasks_link_text = f'✔️ Tasks ({task_count})'
    tasks_link_inline = A(tasks_link_text, href=f'/{main_plugin_instance.name}/switch_to_tasks/{profile_record.id}', 
                         cls='profile-tasks-link', 
                         title=f'View {task_count} unchecked tasks for {profile_record.name}',
                         style='margin-left: 15px; color: var(--pico-primary-color); text-decoration: none; font-size: 0.9em; cursor: pointer; font-weight: 500;',
                         onclick='event.stopPropagation();')  # Prevent triggering the edit onclick
    
    profile_display_div = Div(Span(profile_record.name, title='Click to edit', style='cursor:pointer; font-weight:bold;'), Span(f' ({profile_record.real_name})' if profile_record.real_name else '', style='margin-left:5px; color:var(--pico-muted-color); font-size:0.9em;'), Span(f'📍{profile_record.address}' if profile_record.address else '', style='margin-left:10px; font-size:0.85em; color:var(--pico-muted-color);'), Span(f'🌐{profile_record.code}' if profile_record.code else '', style='margin-left:10px; font-size:0.85em; color:var(--pico-muted-color);'), tasks_link_inline, id=profile_text_display_id, cls='profile-display-flex', onclick=toggle_edit_js)
    
    # Check if profile lock is enabled - FIX: Use same key as dropdown toggle
    profile_lock_enabled = main_plugin_instance.db_dictlike.get('profile_locked', '0') == '1'
    
    # Conditionally render elements based on lock state
    if profile_lock_enabled:
        # When locked: no checkbox, no lock icon, no delete icon
        active_checkbox_input = ''
        lock_to_profile_icon = ''
        delete_icon_span = ''
    else:
        # When unlocked: show all elements
        active_checkbox_input = Input(type='checkbox', name='active_status_profile', checked=bool(profile_record.active), hx_post=toggle_url, hx_target=f'#{item_id_dom}', hx_swap='outerHTML', style='margin-right: 10px; flex-shrink: 0;', title='Toggle Active Status')
        
        # Lock emoji for quick lock-to-profile action
        lock_to_profile_url = f'/{main_plugin_instance.name}/lock_to_profile/{profile_record.id}'
        lock_to_profile_icon = Span('🔒', hx_post=lock_to_profile_url, hx_target='.container-centered', hx_swap='outerHTML', style='margin-right: 8px; cursor: pointer; flex-shrink: 0; font-size: 0.9em;', title=f'Lock to {profile_record.name} profile')
        
        # Delete icon (always hide for Default Profile)
        delete_icon_span = '' if profile_record.name == 'Default Profile' else Span('🗑️', hx_delete=delete_url, hx_target=f'#{item_id_dom}', hx_swap='outerHTML', hx_confirm=f"Are you sure you want to delete the profile '{profile_record.name}'? This action cannot be undone.", cls='profile-delete-icon delete-icon', title='Delete Profile')
    
    # Apply PicoCSS-friendly highlighting classes
    profile_item_classes = 'profile-item-base'
    if is_current_profile:
        profile_item_classes += ' profile-item-selected'
    
    return Li(Div(active_checkbox_input, lock_to_profile_icon, Div(profile_display_div, update_profile_form, style='flex-grow:1; min-width:0;'), delete_icon_span, cls=profile_item_classes), id=item_id_dom, data_id=str(profile_record.id), data_priority=str(profile_record.priority or 0))
