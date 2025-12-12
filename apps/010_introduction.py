"""
Introduction Workflow - The "Attract Mode" Narrator

This workflow serves as the "Why" - a cinematic, narrated slide deck that
sells the philosophy of the Forever Machine.

Features:
- Global Voice Toggle (persisted in pip.db as '1'/'0')
- Auto-advancing narration (if voice enabled)
- "Encore" button (Volume Icon) to re-speak slides
- Proper Containerization for HTMX navigation
"""

import asyncio
from fasthtml.common import *
from loguru import logger
from imports.crud import Step

# Define Roles for Menu Visibility
ROLES = ["Core", "Tutorial"]

class IntroductionPlugin:
    # Standard Workflow Configuration
    NAME = 'introduction'
    APP_NAME = 'introduction'
    DISPLAY_NAME = 'Introduction 🏠'
    ENDPOINT_MESSAGE = 'Welcome to the Machine. Click to enter.'
    
    # Narrative Script
    NARRATION = {
        'step_01': "Welcome. I am Chip O'Theseus. I am not a recording. I am generated locally on your machine, right now. I live here.",
        'step_02': "I am a 'Forever Machine.' I protect your work from cloud subscriptions, broken updates, and the entropy of the web.",
        'step_03': "This is not 'software as a service'. You are the operator. I am the interface. Together, we are sovereign.",
        'finalize': "You have initialized the system. The workshop is open. Select a tool from the menu to begin."
    }

    def __init__(self, app, pipulate, pipeline, db, app_name=APP_NAME):
        self.app = app
        self.pip = pipulate
        self.db = db
        self.app_name = app_name
        self.name = self.NAME 
        self.CONTAINER_ID = f"{self.app_name}-container"
        
        # Access UI constants
        self.ui = pipulate.get_ui_constants()
        
        # Define the Slides as Steps
        self.steps = [
            Step(id='step_01', done='intro_viewed', show='Identity', refill=False),
            Step(id='step_02', done='purpose_viewed', show='Purpose', refill=False),
            Step(id='step_03', done='sovereignty_viewed', show='Sovereignty', refill=False),
            Step(id='finalize', done='finalized', show='Enter Workshop', refill=False)
        ]
        
        # Register routes
        pipulate.register_workflow_routes(self)
        self.app.route(f'/{self.app_name}/toggle_voice', methods=['POST'])(self.toggle_voice)
        self.app.route(f'/{self.app_name}/speak/{{step_id}}', methods=['POST'])(self.speak_step)

    async def toggle_voice(self, request):
        """
        Toggles the global voice_enabled state.
        Uses '1' and '0' strings for safe SQLite storage.
        """
        # Explicit string comparison for boolean state
        current_state = self.pip.db.get('voice_enabled', '0') == '1'
        new_state = not current_state
        
        # Save as '1' or '0' string
        self.pip.db['voice_enabled'] = '1' if new_state else '0'
        
        logger.info(f"🔊 Voice toggled: {new_state}")
        return self._render_voice_controls(new_state)

    async def speak_step(self, step_id: str):
        """Trigger server-side audio playback."""
        text = self.NARRATION.get(step_id, "I have nothing to say about this.")
        
        from imports.voice_synthesis import chip_voice_system
        if chip_voice_system and chip_voice_system.voice_ready:
             logger.info(f"🎤 Speaking: {step_id}")
             asyncio.create_task(asyncio.to_thread(chip_voice_system.speak_text, text))
             
        return ""

    def _render_voice_controls(self, is_enabled):
        """Renders the Voice Toggle button."""
        icon = "🔊" if is_enabled else "🔇"
        style = "color: var(--pico-color-green-500); border-color: var(--pico-color-green-500);" if is_enabled else "color: var(--pico-muted-color);"
        text = "Voice On" if is_enabled else "Voice Off"
        
        return Button(
            f"{icon} {text}",
            hx_post=f"/{self.app_name}/toggle_voice",
            hx_swap="outerHTML",
            cls="secondary outline",
            style=f"{style} margin-bottom: 0; font-size: 0.8rem; padding: 4px 8px;",
            id="voice-toggle-btn",
            data_testid="voice-toggle"
        )

    def _render_slide(self, step_id, title, content, next_step_id=None):
        """Helper to render a standardized slide."""
        # Explicit check against string '1'
        voice_enabled = self.pip.db.get('voice_enabled', '0') == '1'
        
        # Auto-speak trigger
        onload_trigger = ""
        if voice_enabled:
             onload_trigger = Div(
                 hx_post=f"/{self.app_name}/speak/{step_id}",
                 hx_trigger="load",
                 style="display:none;"
             )

        # The "Encore" Button (Volume Icon)
        encore_btn = A(
            Img(src='/assets/feather/volume-2.svg', style="width: 24px; height: 24px; filter: invert(1);"),
            hx_post=f"/{self.app_name}/speak/{step_id}",
            hx_swap="none",
            cls="contrast",
            style="cursor: pointer; opacity: 0.7; margin-left: 10px;",
            title="Encore (Speak Again)"
        )

        # Navigation Buttons
        nav_buttons = []
        if next_step_id:
            nav_buttons.append(
                Button(
                    "Next ➡", 
                    hx_get=f"/{self.app_name}/{next_step_id}", 
                    hx_target=f"#{self.CONTAINER_ID}",
                    hx_swap="innerHTML",  # Explicitly swap inner content
                    id="next-button"
                )
            )

        return Div(
            onload_trigger,
            Card(
                Div(
                    Div(
                        H2(title, style="display: inline-block; margin-bottom: 0;"),
                        encore_btn,
                        style="display: flex; align-items: center;"
                    ),
                    self._render_voice_controls(voice_enabled),
                    style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 2rem;"
                ),
                P(content, style="font-size: 1.3rem; line-height: 1.6; margin-bottom: 2rem;"),
                Div(*nav_buttons, style="display: flex; justify-content: flex-end;"),
                id=step_id,
                cls="intro-slide"
            )
        )

    # --- Step Handlers ---

    async def landing(self, request):
        """Entry point: Wraps the first slide in the main container."""
        # This is CRITICAL: The first render must provide the container ID
        # that subsequent HTMX requests will target.
        return Div(
            await self.step_01(request),
            id=self.CONTAINER_ID,
            style="width: 100%; height: 100%;"
        )
        
    async def init(self, request):
        """Handler for initialization."""
        # Init also needs to return the container wrapper logic
        return await self.landing(request)

    async def step_01(self, request):
        return self._render_slide(
            'step_01', 
            "Identity", 
            "I am Chip O'Theseus. Born from code, living on your local metal.",
            next_step_id='step_02'
        )

    async def step_02(self, request):
        return self._render_slide(
            'step_02', 
            "Purpose", 
            "I am the antidote to the ephemeral web. I persist.",
            next_step_id='step_03'
        )

    async def step_03(self, request):
        return self._render_slide(
            'step_03', 
            "Sovereignty", 
            "No API keys required. No monthly fees. Just you and me.",
            next_step_id='finalize'
        )
        
    async def finalize(self, request):
        return self._render_slide(
            'finalize',
            "The Workshop",
            "You are ready. Select 'Profiles' or 'Hello Workflow' from the menu to begin work.",
            next_step_id=None
        )

    # Required stubs for workflow registration compatibility
    async def handle_revert(self, request): pass
    async def unfinalize(self, request): pass
