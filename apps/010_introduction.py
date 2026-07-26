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
import os
import re
import json
import asyncio
from fasthtml.common import *
from loguru import logger
from imports.crud import Step

# Define Roles for Menu Visibility
ROLES = []

class IntroductionPlugin:
    # Standard Workflow Configuration
    NAME = 'introduction'
    APP_NAME = 'introduction'
    DISPLAY_NAME = 'Home 🏠'
    ENDPOINT_MESSAGE = 'Welcome! Chat with me here.'

    # Narrative Script (Base template)
    NARRATION = {
        'finalize': 'Workflows use auto-generated "Keys" so that they can be pulled up again. Keep the default. Proceed to Configuration workflow.'
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
            Step(id='finalize', done='finalized', show='Hand-off', refill=False)
        ]
        
        # Register routes
        pipulate.register_workflow_routes(self)
        self.app.route(f'/{self.app_name}/speak/{{step_id}}', methods=['POST'])(self.speak_step)

    def _get_slide_data(self, step_id: str):
        """
        JIT (Just-In-Time) State Evaluation.
        Evaluates the hard drive and database at the exact moment of the HTTP request,
        ensuring the UI perfectly reflects the user's latest actions in the Notebook.
        Returns: (Title, Content/Speech, Next_Step_ID)
        """

        if step_id == 'step_01':
            # Check if we have an operator name (proof the airlock worked)
            operator_name = self.wand.db.get('operator_name')

            # 🪄 THE DETERMINISTIC STATE MATRIX
            # Robust SSOT check: Does a finalized config pipeline exist?
            has_configured = False
            try:
                for record in self.wand.pipeline_table():
                    pkey = record['pkey'] if isinstance(record, dict) else record.pkey
                    if 'config' in pkey.lower():
                        data = record['data'] if isinstance(record, dict) else record.data
                        state = json.loads(data)
                        if state.get('finalize', {}).get('finalized') is True:
                            has_configured = True
                            break
            except Exception as e:
                logger.warning(f"Could not verify config pipeline state: {e}")
            dynamic_app_name = self.wand.get_config().APP_NAME
            active_model = self.wand.db.get('active_local_model', 'not yet selected')

            if not operator_name:
                # STATE 1: The Doorway (Airlock has not fired)
                # ATTRIBUTED VOICE: the first thing a stranger hears must say
                # what is producing it. This is Piper reading a fixed string,
                # so it says so, and it does not borrow a persona to do it.
                msg = (
                    "One disclosure before anything else. This voice is Piper, a speech "
                    "synthesizer running entirely on your machine, reading a fixed script. "
                    "There is no language model behind it yet. You have found port 5001 early, "
                    "which is fine, but this room fills in as you finish onboarding. "
                    "Head back to your JupyterLab tab, run the Onboarding notebook top to bottom, "
                    "and this page will have something worth saying."
                )
                return "Onboarding Not Finished 🔒", msg, None

            elif not has_configured:
                # STATE 2: The Guide (Airlock fired, but Configuration is pending)
                # The demo is a scripted scenario driven by player-piano.js, so
                # it is a tour OF THE SYSTEM, never of anyone's "capabilities."
                msg = (
                    f"Welcome to {dynamic_app_name}, {operator_name}. This voice is still a local "
                    "speech synthesizer reading a script, not a language model. The thinking "
                    "engines, local and cloud, get wired up next in Configuration. For a scripted "
                    "tour of the interface, press ",
                    Strong("Ctrl+Alt+D", cls="platform-shortcut"),
                    " right now. Otherwise, we will proceed to finalize your configuration."
                )
                return "Welcome", msg, 'finalize'
                
            else:
                # STATE 3: The Veteran (Config workflow is finalized)
                # Even here the narration stays scripted. The model name is a
                # receipt, so it is spoken only about the engine, never as a
                # claim about the speaker.
                msg = (
                    f"Welcome back to {dynamic_app_name}, {operator_name}. This narration is still "
                    f"scripted speech, not inference. Your local engine is {active_model}. Anything "
                    "a model actually generates from here on will name the model that generated it."
                )
                return "Dashboard Ready ✅", msg, None
                
        elif step_id == 'finalize':
            return "Hand-off", self.NARRATION["finalize"], None
            
        return "Unknown", "I have nothing to say about this.", None


    async def speak_step(self, step_id: str):
        """Trigger server-side audio playback using JIT evaluated text."""
        if step_id == 'step_01':
            sentinel = self.wand.paths.data / '.has_greeted'
            sentinel.touch(exist_ok=True)

        _, content, _ = self._get_slide_data(step_id)
         
        # Convert FastHTML components to string for the voice engine
        if isinstance(content, tuple):
            text = "".join(to_xml(c) if hasattr(c, '__html__') else str(c) for c in content)
        elif hasattr(content, '__html__'):
            text = to_xml(content)
        else:
            text = str(content)

        # THE NARRATOR READS PROSE, NOT MARKUP. to_xml() renders a full tag
        # (<strong class="platform-shortcut">Ctrl+Alt+D</strong>) and Piper
        # will happily pronounce the attributes. Strip tags and collapse the
        # whitespace so the spoken line matches the line on the screen.
        text = re.sub(r'<[^>]+>', ' ', text)
        text = re.sub(r'\s+', ' ', text).strip()

        
        from imports.voice_synthesis import chip_voice_system
        if chip_voice_system and chip_voice_system.voice_ready:
             chip_voice_system.stop_speaking()  # 🛑 INTERRUPT: Prevent voice overlapping on Back button
             logger.info(f"🎤 Speaking: {step_id}")
             asyncio.create_task(asyncio.to_thread(chip_voice_system.speak_text, text))
             
        return ""

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
            allow_auto_speak = True
            if step_id == 'step_01':
                sentinel = self.wand.paths.data / '.has_greeted'
                if sentinel.exists():
                    allow_auto_speak = False
            
            if allow_auto_speak:
                onload_trigger = Div(
                    hx_post=f"/{self.app_name}/speak/{step_id}",
                    hx_trigger=trigger_logic,
                    style="display:none;"
                )

        # The "Encore" Button (Volume Icon)
        encore_btn = A(
            Img(src='/assets/feather/message-circle.svg', style="width: 24px; height: 24px; filter: invert(1);"),
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

        if isinstance(content, tuple):
            content_tag = P(*content, style="font-size: 1.3rem; line-height: 1.6; margin-bottom: 2rem;")
        else:
            content_tag = P(content, style="font-size: 1.3rem; line-height: 1.6; margin-bottom: 2rem;")

        # JIT Client-Side Text Replacement for Shortcuts
        shortcut_script = Script('''
            const shortcutEl = document.querySelector('.platform-shortcut');
            if (shortcutEl && window.PLATFORM_KEYS) {
                shortcutEl.textContent = window.PLATFORM_KEYS.d_key;
            }
        ''')

        return Div(
                onload_trigger,
                Article(
                    Div(
                       H2(title, style="display: inline-block; margin-bottom: 0;"),
                       encore_btn,
                       style="display: flex; align-items: center; margin-bottom: 2rem;"
                   ),
                   content_tag,
                   Div(*nav_buttons, style="display: flex; justify-content: flex-end;"),
                   id=step_id,
                   cls="intro-slide",
                   ),
                shortcut_script
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
