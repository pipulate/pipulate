"""
Discussion History Plugin

Provides a comprehensive view of conversation history using the append-only
conversation system. Features include:
- Chronological message display with proper site navigation
- Role-based filtering (user/assistant/system)
- Copy-to-clipboard functionality
- Conversation statistics
- Session tracking
- PicoCSS-consistent color scheme
"""

import logging
import asyncio
from datetime import datetime
from fasthtml.common import *
from pathlib import Path

ROLES = ['Workshop']

logger = logging.getLogger(__name__)

# Import the append-only conversation system
try:
    from imports.append_only_conversation import (
        get_conversation_history, 
        get_conversation_stats,
        archive_message_by_id
    )
    CONVERSATION_SYSTEM_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Append-only conversation system not available: {e}")
    CONVERSATION_SYSTEM_AVAILABLE = False

class HistoryViewer:
    """
    Discussion History Viewer
    
    Provides a comprehensive view of conversation history using the append-only
    conversation system. Features include:
    - Chronological message display
    - Role-based filtering
    - Copy-to-clipboard functionality
    - Conversation statistics
    - Session tracking
    """
    
    APP_NAME = 'history'
    DISPLAY_NAME = 'Discussion History 💬'
    ENDPOINT_MESSAGE = """📜 Discussion History Viewer: Browse and manage your complete conversation history. View all messages chronologically, filter by role (user/assistant/system), copy individual messages or entire conversations to clipboard, and see conversation statistics. All data is preserved using the bulletproof append-only architecture."""
    
    # PicoCSS-consistent UI styling constants
    UI_CONSTANTS = {
        'user_color': 'var(--pico-primary-background)',
        'assistant_color': 'var(--pico-secondary-background)', 
        'system_color': 'var(--pico-color)',
        'background_color': 'var(--pico-background-color)',
        'border_color': 'var(--pico-border-color)',
        'text_color': 'var(--pico-color)',
        'muted_color': 'var(--pico-muted-color)',
        'border_radius': 'var(--pico-border-radius)',
        'spacing': 'var(--pico-spacing)',
        'card_background': 'var(--pico-card-background-color)',
        'card_border': 'var(--pico-card-border-color)'
    }

    def __init__(self, app, pipulate, pipeline, db):
        logger.debug(f"HistoryViewer initialized with APP_NAME: {self.APP_NAME}")
        self.app = app
        self.pipulate = pipulate
        self.pipeline = pipeline
        wand = self.pipulate
        
        # Register HTMX interaction routes (utility plugin pattern)
        app.route('/history/refresh', methods=['GET'])(self.refresh_history)
        app.route('/history/filter', methods=['POST'])(self.filter_messages)
        app.route('/history/copy', methods=['POST'])(self.copy_to_clipboard)
        app.route('/history/delete', methods=['POST'])(self.delete_message)

    async def landing(self, request):
        """
        Main landing page with proper navigation integration.
        This method ensures the history viewer gets the standard site navigation.
        """
        try:
            # Get conversation data
            messages = []
            stats = {'total_messages': 0, 'role_distribution': {}, 'avg_length': 0}
            
            logger.debug(f"Conversation system available: {CONVERSATION_SYSTEM_AVAILABLE}")
            
            if CONVERSATION_SYSTEM_AVAILABLE:
                messages = await get_conversation_history()
                stats = await get_conversation_stats()
                logger.debug(f"Retrieved {len(messages)} messages from conversation system")
                logger.debug(f"Stats: {stats}")
            else:
                logger.warning("Conversation system not available")
            
            # Create the main content
            content = self.render_history_page(messages, stats)
            return content
            
        except Exception as e:
            logger.error(f"Error in history landing: {e}")
            return self.render_error_page(f"Error loading history: {str(e)}")



    async def refresh_history(self, request):
        """Refresh the history display"""
        return await self.landing(request)

    async def filter_messages(self, request):
        """Filter messages by role"""
        try:
            form_data = await request.form()
            role_filter = form_data.get('role', 'all')
            
            if not CONVERSATION_SYSTEM_AVAILABLE:
                return self.render_error_page("Conversation system not available")
            
            messages = await get_conversation_history()
            stats = await get_conversation_stats()
            
            # Filter messages if needed
            if role_filter != 'all':
                messages = [msg for msg in messages if msg.get('role') == role_filter]
            
            return self.render_messages_section(messages, stats, role_filter)
            
        except Exception as e:
            logger.error(f"Error filtering messages: {e}")
            return self.render_error_page(f"Error filtering messages: {str(e)}")

    async def copy_to_clipboard(self, request):
        """Handle copy to clipboard requests"""
        try:
            form_data = await request.form()
            copy_type = form_data.get('type', 'message')
            
            if copy_type == 'conversation':
                if not CONVERSATION_SYSTEM_AVAILABLE:
                    return self.render_copy_error("Conversation system not available")
                
                messages = await get_conversation_history()
                content = self.format_conversation_for_clipboard(messages)
                return self.render_copy_success("Entire conversation copied to clipboard!", content)
            
            elif copy_type == 'message':
                message_index = int(form_data.get('index', 0))
                if not CONVERSATION_SYSTEM_AVAILABLE:
                    return self.render_copy_error("Conversation system not available")
                
                messages = await get_conversation_history()
                if message_index < len(messages):
                    message = messages[message_index]
                    content = self.format_message_for_clipboard(message)
                    return self.render_copy_success("Message copied to clipboard!", content)
                else:
                    return self.render_copy_error("Message not found")
            
            return self.render_copy_error("Invalid copy type")
            
        except Exception as e:
            logger.error(f"Error copying to clipboard: {e}")
            return self.render_copy_error(f"Error copying: {str(e)}")

    async def delete_message(self, request):
        """Handle message deletion (archive) requests"""
        try:
            form_data = await request.form()
            message_id = int(form_data.get('message_id'))
            
            if not CONVERSATION_SYSTEM_AVAILABLE:
                return Div("❌ Conversation system not available", 
                          style="color: var(--pico-del-color); padding: 1rem;")
            
            # Archive the message (soft delete)
            success = await archive_message_by_id(message_id)
            
            if success:
                # Return success response that will trigger UI refresh
                return Div(
                    "✅ Message archived successfully",
                    hx_get="/history/refresh",
                    hx_target="#history-container", 
                    hx_swap="outerHTML",
                    hx_trigger="load delay:500ms",
                    style="color: var(--pico-primary); padding: 1rem;"
                )
            else:
                return Div("❌ Failed to archive message", 
                          style="color: var(--pico-del-color); padding: 1rem;")
                
        except Exception as e:
            logger.error(f"Error deleting message: {e}")
            return Div(f"❌ Error: {str(e)}", 
                      style="color: var(--pico-del-color); padding: 1rem;")

    def render_history_page(self, messages, stats):
        """Render the complete history page"""
        return Div(
            self.render_stats_section(stats),
            self.render_controls_section(),
            self.render_messages_section(messages, stats),
            self.render_copy_scripts(),
            id="history-container",
            style=f"""
                padding: {self.UI_CONSTANTS['spacing']};
                background-color: {self.UI_CONSTANTS['background_color']};
                color: {self.UI_CONSTANTS['text_color']};
                min-height: 100vh;
            """
        )

    def render_stats_section(self, stats):
        """Render the statistics section"""
        role_badges = []
        for role, count in stats.get('role_distribution', {}).items():
            icon = {'user': '👤', 'assistant': '🤖', 'system': '⚙️'}.get(role, '❓')
            role_badges.append(
                Span(
                    f"{icon} {role.title()}: {count}",
                    style=f"""
                        display: inline-block;
                        margin-right: {self.UI_CONSTANTS['spacing']};
                        padding: 0.25rem 0.5rem;
                        background-color: {self.UI_CONSTANTS['card_background']};
                        border: 1px solid {self.UI_CONSTANTS['border_color']};
                        border-radius: {self.UI_CONSTANTS['border_radius']};
                        font-size: 0.85rem;
                    """
                )
            )
        
        # Calculate average length from stats
        total_messages = stats.get('total_messages', 0)
        total_characters = stats.get('total_characters', 0)
        avg_length = total_characters / total_messages if total_messages > 0 else 0
        archived_count = stats.get('archived_messages', 0)
        
        return Card(
            H3("📊 Conversation Statistics", style=f"color: {self.UI_CONSTANTS['text_color']}; margin-bottom: 1rem;"),
            Div(
                Div(f"📈 Total Messages: {total_messages}", style="margin-bottom: 0.5rem;"),
                Div(f"📏 Average Length: {avg_length:.0f} characters", style="margin-bottom: 0.5rem;"),
                Div(f"🗃️ Archived Messages: {archived_count}", 
                    title="Messages you've deleted are safely archived and can be recovered",
                    style="margin-bottom: 0.5rem; color: var(--pico-muted-color);"),
                Div(*role_badges, style="margin-top: 1rem;"),
                style=f"color: {self.UI_CONSTANTS['text_color']};"
            ),
            style=f"""
                background-color: {self.UI_CONSTANTS['card_background']};
                border: 1px solid {self.UI_CONSTANTS['card_border']};
                margin-bottom: 1rem;
            """
        )

    def render_controls_section(self):
        """Render the filter and action controls"""
        return Card(
            H4("🎛️ Controls", style=f"color: {self.UI_CONSTANTS['text_color']}; margin-bottom: 1rem;"),
            Div(
                # Filter controls
                Div(
                    Label("Filter by Role:", style=f"color: {self.UI_CONSTANTS['text_color']}; margin-right: 0.5rem;"),
                    Select(
                        Option("All Messages", value="all"),
                        Option("👤 User Messages", value="user"),
                        Option("🤖 Chip O'Theseus Messages", value="assistant"),
                        Option("⚙️ System Messages", value="system"),
                        name="role",
                        hx_post="/history/filter",
                        hx_target="#messages-container",
                        hx_swap="outerHTML",
                        style=f"""
                            margin-right: 1rem;
                            background-color: {self.UI_CONSTANTS['card_background']};
                            border: 1px solid {self.UI_CONSTANTS['border_color']};
                            color: {self.UI_CONSTANTS['text_color']};
                        """
                    ),
                    style="display: inline-block; margin-right: 1rem;"
                ),
                # Action buttons
                Div(
                    Button(
                        "🔄 Refresh",
                        hx_get="/history/refresh",
                        hx_target="#history-container",
                        hx_swap="outerHTML",
                        style=f"""
                            margin-right: 0.5rem;
                            background-color: {self.UI_CONSTANTS['user_color']};
                            border: 1px solid {self.UI_CONSTANTS['border_color']};
                            color: white;
                        """
                    ),
                    Button(
                        "📋 Copy All",
                        onclick="copyConversation()",
                        style=f"""
                            background-color: {self.UI_CONSTANTS['assistant_color']};
                            border: 1px solid {self.UI_CONSTANTS['border_color']};
                            color: white;
                        """
                    ),
                    style="display: inline-block;"
                ),
                style="display: flex; align-items: center; gap: 1rem;"
            ),
            style=f"""
                background-color: {self.UI_CONSTANTS['card_background']};
                border: 1px solid {self.UI_CONSTANTS['card_border']};
                margin-bottom: 1rem;
            """
        )

    def render_messages_section(self, messages, stats, role_filter='all'):
        """Render the messages section"""
        if not messages:
            return Div(
                Card(
                    H4("📭 No Messages", style=f"color: {self.UI_CONSTANTS['text_color']};"),
                    P("No conversation history found.", style=f"color: {self.UI_CONSTANTS['muted_color']};"),
                    style=f"""
                        background-color: {self.UI_CONSTANTS['card_background']};
                        border: 1px solid {self.UI_CONSTANTS['card_border']};
                        text-align: center;
                    """
                ),
                id="messages-container"
            )
        
        message_elements = []
        for i, message in enumerate(messages):
            message_elements.append(self.render_single_message(message, i))
        
        return Div(
            H4(f"💬 Messages ({len(messages)})", style=f"color: {self.UI_CONSTANTS['text_color']}; margin-bottom: 1rem;"),
            Div(*message_elements, style="display: flex; flex-direction: column; gap: 0.5rem;"),
            id="messages-container"
        )

    def render_single_message(self, message, index):
        """Render a single message"""
        role = message.get('role', 'unknown')
        content = message.get('content', '')
        timestamp = message.get('timestamp', '')
        message_id = message.get('id')  # Get database ID for deletion
        
        # Role-specific styling
        role_styles = {
            'user': {
                'icon': '👤',
                'color': self.UI_CONSTANTS['user_color'],
                'border_color': self.UI_CONSTANTS['user_color']
            },
            'assistant': {
                'icon': '🤖', 
                'color': self.UI_CONSTANTS['assistant_color'],
                'border_color': self.UI_CONSTANTS['assistant_color']
            },
            'system': {
                'icon': '⚙️',
                'color': self.UI_CONSTANTS['system_color'],
                'border_color': self.UI_CONSTANTS['border_color']
            }
        }
        
        role_style = role_styles.get(role, role_styles['system'])
        
        # Format timestamp
        try:
            if timestamp:
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                formatted_time = dt.strftime('%Y-%m-%d %H:%M:%S')
            else:
                formatted_time = 'Unknown time'
        except:
            formatted_time = str(timestamp)
        
        # Truncate very long messages for display
        display_content = content
        if len(content) > 500:
            display_content = content[:500] + "..."
        
        return Div(
            Div(
                Div(
                    Span(f"{role_style['icon']} {role.title()}", style=f"font-weight: bold; color: {role_style['color']};"),
                    Span(formatted_time, style=f"font-size: 0.8rem; color: {self.UI_CONSTANTS['muted_color']};"),
                    style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;"
                ),
                Pre(
                    display_content,
                    style=f"""
                        white-space: pre-wrap;
                        word-wrap: break-word;
                        margin: 0;
                        padding: 0.75rem;
                        background-color: {self.UI_CONSTANTS['background_color']};
                        border: 1px solid {self.UI_CONSTANTS['border_color']};
                        border-radius: {self.UI_CONSTANTS['border_radius']};
                        color: {self.UI_CONSTANTS['text_color']};
                        font-family: var(--pico-font-family);
                        font-size: 0.9rem;
                        line-height: 1.4;
                    """
                ),
                # Button container with copy and delete buttons
                Div(
                    Button(
                        "📋 Copy",
                        onclick=f"copyMessage({index})",
                        id=f"copy-btn-{index}",
                        style=f"""
                            margin-right: 0.5rem;
                            padding: 0.25rem 0.5rem;
                            font-size: 0.8rem;
                            background-color: {self.UI_CONSTANTS['assistant_color']};
                            border: 1px solid {self.UI_CONSTANTS['border_color']};
                            color: white;
                            border-radius: {self.UI_CONSTANTS['border_radius']};
                            cursor: pointer;
                        """
                    ),
                    Button(
                        "🗑️ Delete",
                        hx_post="/history/delete",
                        hx_vals=f'{{"message_id": {message_id}}}' if message_id else '{}',
                        hx_target=f"#message-{index}",
                        hx_swap="outerHTML",
                        hx_confirm="Are you sure you want to delete this message? It will be archived but can be recovered.",
                        id=f"delete-btn-{index}",
                        style=f"""
                            padding: 0.25rem 0.5rem;
                            font-size: 0.8rem;
                            background-color: var(--pico-del-color);
                            border: 1px solid {self.UI_CONSTANTS['border_color']};
                            color: white;
                            border-radius: {self.UI_CONSTANTS['border_radius']};
                            cursor: pointer;
                        """
                    ),
                    style="margin-top: 0.5rem; display: flex; gap: 0.5rem;"
                ),
                style=f"""
                    padding: 1rem;
                    background-color: {self.UI_CONSTANTS['card_background']};
                    border: 1px solid {self.UI_CONSTANTS['card_border']};
                    border-left: 4px solid {role_style['color']};
                    border-radius: {self.UI_CONSTANTS['border_radius']};
                """
            ),
            data_message_index=str(index),
            data_message_content=content,  # Store full content for copying
            data_message_id=str(message_id) if message_id else "",  # Store message ID for deletion
            id=f"message-{index}",  # ID for HTMX targeting
            style="margin-bottom: 0.5rem;"
        )

    def render_copy_scripts(self):
        """Render JavaScript for copy functionality"""
        return Script(f"""
            // Copy individual message
            function copyMessage(index) {{
                const messageDiv = document.querySelector(`[data-message-index="${{index}}"]`);
                const copyBtn = document.querySelector(`#copy-btn-${{index}}`);
                
                if (messageDiv && copyBtn) {{
                    const content = messageDiv.getAttribute('data-message-content');
                    const originalText = copyBtn.textContent;
                    
                    if (content) {{
                        navigator.clipboard.writeText(content).then(() => {{
                            // Success feedback in button
                            copyBtn.textContent = '✅ Copied!';
                            copyBtn.style.backgroundColor = '{self.UI_CONSTANTS['user_color']}';
                            
                            // Reset button after 2 seconds
                            setTimeout(() => {{
                                copyBtn.textContent = originalText;
                                copyBtn.style.backgroundColor = '{self.UI_CONSTANTS['assistant_color']}';
                            }}, 2000);
                        }}).catch(err => {{
                            console.error('Failed to copy message:', err);
                            // Error feedback in button
                            copyBtn.textContent = '❌ Failed';
                            copyBtn.style.backgroundColor = 'var(--pico-del-color)';
                            
                            // Reset button after 2 seconds
                            setTimeout(() => {{
                                copyBtn.textContent = originalText;
                                copyBtn.style.backgroundColor = '{self.UI_CONSTANTS['assistant_color']}';
                            }}, 2000);
                        }});
                    }}
                }}
            }}
            
            // Copy entire conversation
            function copyConversation() {{
                const copyAllBtn = document.querySelector('button[onclick="copyConversation()"]');
                const originalText = copyAllBtn ? copyAllBtn.textContent : '📋 Copy All';
                
                if (copyAllBtn) {{
                    copyAllBtn.textContent = '⏳ Copying...';
                    copyAllBtn.disabled = true;
                }}
                
                fetch('/history/copy', {{
                    method: 'POST',
                    headers: {{
                        'Content-Type': 'application/x-www-form-urlencoded',
                    }},
                    body: 'type=conversation'
                }})
                .then(response => response.json())
                .then(data => {{
                    if (data.success && data.content) {{
                        navigator.clipboard.writeText(data.content).then(() => {{
                            if (copyAllBtn) {{
                                copyAllBtn.textContent = '✅ All Copied!';
                                copyAllBtn.style.backgroundColor = '{self.UI_CONSTANTS['user_color']}';
                                
                                // Reset button after 3 seconds
                                setTimeout(() => {{
                                    copyAllBtn.textContent = originalText;
                                    copyAllBtn.style.backgroundColor = '{self.UI_CONSTANTS['assistant_color']}';
                                    copyAllBtn.disabled = false;
                                }}, 3000);
                            }}
                        }}).catch(err => {{
                            console.error('Failed to copy conversation:', err);
                            if (copyAllBtn) {{
                                copyAllBtn.textContent = '❌ Failed';
                                copyAllBtn.style.backgroundColor = 'var(--pico-del-color)';
                                
                                // Reset button after 3 seconds
                                setTimeout(() => {{
                                    copyAllBtn.textContent = originalText;
                                    copyAllBtn.style.backgroundColor = '{self.UI_CONSTANTS['assistant_color']}';
                                    copyAllBtn.disabled = false;
                                }}, 3000);
                            }}
                        }});
                    }} else {{
                        if (copyAllBtn) {{
                            copyAllBtn.textContent = '❌ Failed';
                            copyAllBtn.style.backgroundColor = 'var(--pico-del-color)';
                            
                            // Reset button after 3 seconds
                            setTimeout(() => {{
                                copyAllBtn.textContent = originalText;
                                copyAllBtn.style.backgroundColor = '{self.UI_CONSTANTS['assistant_color']}';
                                copyAllBtn.disabled = false;
                            }}, 3000);
                        }}
                    }}
                }})
                .catch(err => {{
                    console.error('Error copying conversation:', err);
                    if (copyAllBtn) {{
                        copyAllBtn.textContent = '❌ Error';
                        copyAllBtn.style.backgroundColor = 'var(--pico-del-color)';
                        
                        // Reset button after 3 seconds
                        setTimeout(() => {{
                            copyAllBtn.textContent = originalText;
                            copyAllBtn.style.backgroundColor = '{self.UI_CONSTANTS['assistant_color']}';
                            copyAllBtn.disabled = false;
                        }}, 3000);
                    }}
                }});
            }}
        """)

    def render_error_page(self, error_message):
        """Render error page"""
        return Card(
            H3("❌ Error Loading History", style=f"color: {self.UI_CONSTANTS['text_color']}; margin-bottom: 1rem;"),
            P(f"Error: {error_message}", style=f"color: {self.UI_CONSTANTS['text_color']};"),
            Button(
                "🔄 Retry",
                hx_get="/history/refresh",
                hx_target="#history-container",
                hx_swap="outerHTML",
                style=f"""
                    background-color: {self.UI_CONSTANTS['user_color']};
                    border: 1px solid {self.UI_CONSTANTS['border_color']};
                    color: white;
                """
            ),
            style=f"""
                background-color: {self.UI_CONSTANTS['card_background']};
                border: 1px solid {self.UI_CONSTANTS['card_border']};
                text-align: center;
                padding: 2rem;
            """
        )

    def render_copy_success(self, message, content):
        """Render copy success response"""
        return {"success": True, "message": message, "content": content}

    def render_copy_error(self, message):
        """Render copy error response"""
        return {"success": False, "message": message}

    def format_message_for_clipboard(self, message):
        """Format a single message for clipboard"""
        role = message.get('role', 'unknown')
        content = message.get('content', '')
        timestamp = message.get('timestamp', '')
        
        return f"[{role.upper()}] {timestamp}\n{content}\n"

    def format_conversation_for_clipboard(self, messages):
        """Format the entire conversation for clipboard"""
        formatted_messages = []
        for message in messages:
            formatted_messages.append(self.format_message_for_clipboard(message))
        
        return "\n" + "="*50 + "\n".join(formatted_messages) + "="*50 + "\n" 
