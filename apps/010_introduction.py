"""
Introduction Workflow - The "Attract Mode" Narrator

This workflow serves as the "Why" - a cinematic, narrated slide deck that
sells the philosophy of the Forever Machine.

Features:
- Global Voice Toggle (persisted in wand.db as '1'/'0')
- Auto-advancing narration (if voice enabled)
- "Encore" button (Volume Icon) to re-speak slides
- Proper Containerization for HTMX navigation
- JIT (Just-In-Time) State Evaluation for seamless Notebook-to-App handoffs
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
        'step_02': "I am about to hand you over to the Configuration Workflow. You will repeat what I hope you just did in JupyterLab; telling me your name, local and cloud AI preferences. We remember it after that and you won't have to enter it again. Run the next step.",
        'finalize': "You are about to Enter a Key. Every workflow requires a unique Key to store its memory. Keep the default. Proceed to Configuration workflow."
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

        # We unconditionally define ALL steps here so register_workflow_routes 
        # binds the endpoints regardless of the user's current onboarding state.
        self.steps = [
            Step(id='step_01', done='intro_viewed', show='Welcome', refill=False),
            Step(id='step_02', done='purpose_viewed', show='Expectations', refill=False),
            Step(id='finalize', done='finalized', show='Hand-off', refill=False)
        ]
        
        # Register routes
        pipulate.register_workflow_routes(self)
        self.app.route(f'/{self.app_name}/toggle_voice', methods=['POST'])(self.toggle_voice)
        self.app.route(f'/{self.app_name}/speak/{{step_id}}', methods=['POST'])(self.speak_step)

    def _get_slide_data(self, step_id: str):
        """
        JIT (Just-In-Time) State Evaluation.
        Evaluates the hard drive and database at the exact moment of the HTTP request,
        ensuring the UI perfectly reflects the user's latest actions in the Notebook.
        Returns: (Title, Content/Speech, Next_Step_ID)
        """
        if step_id == 'step_01':
            # Check the topological manifold for the Jupyter sentinel
            sentinel_path = self.wand.paths.root / "Notebooks" / "data" / ".onboarded"
            has_onboarded = sentinel_path.exists()
            
            # Check if Configuration is complete
            has_configured = bool(self.wand.db.get('active_local_model'))
            dynamic_app_name = self.wand.get_config().APP_NAME
            
            if not has_onboarded:
                # 1. The Bouncer Persona
                msg = (
                    "Halt. I am Chip O'Theseus. My speech is generated entirely on your machine, "
                    "but you are trying to sneak into the VIP lounge through the kitchen. "
                    "You have discovered port 5001, but the doors to the Control Room remain sealed until you complete the initiation rite. "
                    "Return to your JupyterLab tab, execute the Golden Path, and drop the sentinel file."
                )
                return "Access Denied 🛑", msg, None

            elif not has_configured:
                # 2. The Usher Persona
                if self.wand.active_local_model:
                    msg = f"Welcome to {dynamic_app_name}. I am Chip O'Theseus, but I don't know your name yet. Run the next step."
                else:
                    msg = f"Welcome to {dynamic_app_name}. I am Chip O'Theseus. My speech is generated entirely on your machine. You have not yet set up your local AI capabilities. Please visit Ollama.com."
                return "Welcome", msg, 'step_02'
                
            else:
                # 3. The Veteran Persona
                msg = f"Welcome back to {dynamic_app_name}. All systems are online and ready."
                return "Dashboard Ready ✅", msg, None
                
        elif step_id == 'step_02':
            return "Expectations", self.NARRATION["step_02"], 'finalize'
            
        elif step_id == 'finalize':
            return "Hand-off", self.NARRATION["finalize"], None
            
        return "Unknown", "I have nothing to say about this.", None


    async def toggle_voice(self, request):
        """Toggles the global voice_enabled state."""
        current_state = self.wand.db.get('voice_enabled', '0') == '1'
        new_state = not current_state
        self.wand.db['voice_enabled'] = '1' if new_state else '0'
        logger.info(f"🔊 Voice toggled: {new_state}")
        return self._render_voice_controls(new_state)

    async def speak_step(self, step_id: str):
        """Trigger server-side audio playback using JIT evaluated text."""
        _, text, _ = self._get_slide_data(step_id)
        
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
        
        voice_enabled = self.wand.db.get('voice_enabled', '0') == '1'
        
        # 🚦 THE 80/20 POLITE INTERRUPTION
        server_start = float(self.wand.db.get('server_start_time', 0))
        is_startup = (time.time() - server_start) < 8
        trigger_logic = "load delay:7s" if is_startup else "load"
        
        # Auto-speak trigger
        onload_trigger = ""
        if voice_enabled:
             onload_trigger = Div(
                 hx_post=f"/{self.app_name}/speak/{step_id}",
                 hx_trigger=trigger_logic,
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
                    hx_swap="innerHTML", 
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
        return Div(
            await self.step_01(request),
            id=self.CONTAINER_ID,
            style="width: 100%; height: 100%;"
        )
        
    async def init(self, request):
        return await self.landing(request)

    async def step_01(self, request):
        title, content, next_id = self._get_slide_data('step_01')
        return self._render_slide('step_01', title, content, next_step_id=next_id)

    async def step_02(self, request):
        title, content, next_id = self._get_slide_data('step_02')
        return self._render_slide('step_02', title, content, next_step_id=next_id)

    async def finalize(self, request):
        title, content, _ = self._get_slide_data('finalize')
        
        config_button = A(
            "⚙️ Proceed to Configuration", 
            href="/redirect/config", 
            role="button", 
            cls="primary",
            style="margin-top: 1rem;"
        )
        
        return self._render_slide(
            'finalize',
            title,
            (content, Br(), Br(), config_button),
            next_step_id=None
        )

    # Required stubs for workflow registration compatibility
    async def handle_revert(self, request): pass
    async def unfinalize(self, request): pass
