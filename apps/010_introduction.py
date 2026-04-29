"""
Introduction Workflow - The "Attract Mode" Narrator

This workflow serves as the "Why" - a cinematic, narrated slide deck that
sells the philosophy of the Forever Machine.

Features:
- Global Voice Toggle (persisted in wand.db as '1'/'0')
- Auto-advancing narration (if voice enabled)
- "Encore" button (Volume Icon) to re-speak slides
- Proper Containerization for HTMX navigation
"""

import time
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
    ENDPOINT_MESSAGE = 'Welcome! Chat with me here.'

    # Narrative Script (Base template)
    NARRATION = {
        'step_01': "Welcome to the dashboard. I am Chip O'Theseus. My speech is rendered entirely on your local metal, but my reasoning engines are currently idling. You can return to this homepage at any time by clicking the home link in the upper-left corner of the screen.",
        'step_02': "I am about to hand you over to the Configuration Workflow. You will repeat what you just did Notebook-side in JupyterLab; telling me your name, local and cloud AI preferences, and Botify API key if you're a Botify employee or customer. After that, we remember it. The Configuration Workflow will feel a lot like running a Jupyter Notebook, proceeding top-to-bottom as if through the cells. Only you don't have to see any of the Python code.",
        'finalize': "Every workflow requires a unique Key to store its memory. You can keep the default key, or generate a New Key to start a fresh configuration. Let's establish your permanent identity."
    }

    def __init__(self, app, pipulate, pipeline, db, app_name=APP_NAME):
        self.app = app
        self.wand = pipulate
        self.db = db
        self.app_name = app_name
        self.name = self.NAME 
        self.CONTAINER_ID = f"{self.app_name}-container"
        
        # Access UI constants
        self.ui = pipulate.get_ui_constants()

        # Dynamically fetch the current App Name (e.g. Botifython or Pipulate)
        dynamic_app_name = self.wand.get_config().APP_NAME

        # 🧠 THE GATEKEEPER: Check the topological manifold for the sentinel file
        self.sentinel_path = self.wand.paths.root / "Notebooks" / "data" / ".onboarded"
        self.has_onboarded = self.sentinel_path.exists()

        # 🧠 CHISEL-STRIKE 3: Dynamic Model Negotiation
        self.narration = self.NARRATION.copy()
        
        # Run the global negotiation at startup
        ai_status = self.wand.negotiate_ai_models(
            preferred_local=self.wand.get_config().PREFERRED_LOCAL_MODELS,
            preferred_cloud=self.wand.get_config().PREFERRED_CLOUD_MODELS
        )
        
        if ai_status.get('has_any_local'):
            local_model = ai_status.get('local')
            if local_model:
                standard_intro = f"Welcome to {dynamic_app_name}. I am Chip O'Theseus. My speech is rendered entirely on your local metal, but my reasoning engines are currently idling. You can return to this homepage at any time by clicking the '{dynamic_app_name}' link in the upper-left corner of the screen."
            else:
                standard_intro = f"Welcome to {dynamic_app_name}. I am Chip O'Theseus. My speech is rendered entirely on your local metal. You have not yet set up your local AI capabilities. Please visit Ollama.com."
        else:
            standard_intro = f"Welcome to {dynamic_app_name}. I am Chip O'Theseus. I am currently running without a local brain. Please install Ollama with Gemma 4 to fully awaken me."
        
        # 🚧 THE FORK IN THE ROAD: Adjust the reality based on the Sentinel
        if not self.has_onboarded:
            # The Bouncer Persona
            self.narration['step_01'] = (
                "Halt. I am Chip O'Theseus, and you are trying to sneak into the VIP lounge through the kitchen. "
                "You have discovered port 5001, but the doors to the Control Room remain sealed until you complete the initiation rite. "
                "Return to your JupyterLab tab, execute the Golden Path, and drop the sentinel file."
            )
            # Truncate the workflow to a single, impassable step
            self.steps = [
                Step(id='step_01', done='intro_viewed', show='Access Denied', refill=False)
            ]
        else:
            # The Tour Guide Persona
            self.narration['step_01'] = standard_intro
            # Provide the full philosophical slide deck
            self.steps = [
                Step(id='step_01', done='intro_viewed', show='Welcome', refill=False),
                Step(id='step_02', done='purpose_viewed', show='Expectations', refill=False),
                Step(id='finalize', done='finalized', show='Hand-off', refill=False)
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
        current_state = self.wand.db.get('voice_enabled', '0') == '1'
        new_state = not current_state
        
        # Save as '1' or '0' string
        self.wand.db['voice_enabled'] = '1' if new_state else '0'
        
        logger.info(f"🔊 Voice toggled: {new_state}")
        return self._render_voice_controls(new_state)

    async def speak_step(self, step_id: str):
        """Trigger server-side audio playback."""
        text = self.narration.get(step_id, "I have nothing to say about this.")
        
        from imports.voice_synthesis import chip_voice_system
        if chip_voice_system and chip_voice_system.voice_ready:
             chip_voice_system.stop_speaking()  # 🛑 INTERRUPT: Prevent voice overlapping on Back button
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
        import time
        
        # Explicit check against string '1'
        voice_enabled = self.wand.db.get('voice_enabled', '0') == '1'
        
        # 🚦 THE 80/20 POLITE INTERRUPTION: If the server just woke up, 
        # tell HTMX to hold the request for 7 seconds so the server can speak first.
        server_start = float(self.wand.db.get('server_start_time', 0))
        is_startup = (time.time() - server_start) < 8
        trigger_logic = "load delay:7s" if is_startup else "load"
        
        # Auto-speak trigger
        onload_trigger = ""
        if voice_enabled:
             onload_trigger = Div(
                 hx_post=f"/{self.app_name}/speak/{step_id}",
                 hx_trigger=trigger_logic,  # <-- USE DYNAMIC TRIGGER HERE
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
                    "Next Step ▸", 
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
        if not self.has_onboarded:
            return self._render_slide(
                'step_01', 
                "Access Denied 🛑", 
                "You've discovered the Control Room port. Clever, but premature. The UI is locked because you haven't completed the Onboarding sequence in JupyterLab. Go back, follow the rhythm of Shift+Enter, and earn your dashboard.",
                next_step_id=None  # This kills the "Next" button, trapping them here.
            )
        else:
            return self._render_slide(
                'step_01', 
                "Welcome", 
                self.narration['step_01'],
                next_step_id='step_02'
            )

    async def step_02(self, request):
        return self._render_slide(
            'step_02', 
            "Expectations", 
            self.narration["step_02"],
            next_step_id='finalize'
        )

    async def finalize(self, request):
        # The explicit, clickable transition to the Configuration App
        config_button = A(
            "⚙️ Proceed to Configuration", 
            href="/redirect/config", 
            role="button", 
            cls="primary",
            style="margin-top: 1rem;"
        )
        
        return self._render_slide(
            'finalize',
            "Hand-off",
            (
                self.narration["finalize"],
                Br(), Br(),
                config_button
            ),
            next_step_id=None
        )

    # Required stubs for workflow registration compatibility
    async def handle_revert(self, request): pass
    async def unfinalize(self, request): pass
