"""
Introduction Plugin - Extracted intro pages from original homepage

This plugin serves the 4-page introduction sequence that was originally
the homepage content before switching to the Roles app.
"""

import logging
from fasthtml.common import *
from pathlib import Path
import urllib.parse

ROLES = ['Core']

logger = logging.getLogger(__name__)

class IntroductionPlugin:
    NAME = "introduction"
    DISPLAY_NAME = "Introduction 💬"
    ENDPOINT_MESSAGE = "Welcome to something new. If you have an open mind, you're in for a treat. Type to me here or press Ctrl+Alt+d for a demo."

    def __init__(self, app, pipulate, pipeline, db):
        logger.debug(f"IntroductionPlugin initialized with NAME: {self.NAME}")
        self.app = app
        self.pipulate = pipulate
        self.pipeline = pipeline
        pip = self.pipulate
        self._has_sent_endpoint_message = False  # Flag to track if we've sent the initial endpoint message
        self._last_streamed_page = None  # Track the last page we sent to LLM

        # Register routes for page navigation
        app.route('/introduction/page/{page_num}', methods=['GET', 'POST'])(self.serve_page)

    def create_page_content(self, page_num: int, app_name: str, model: str):
        """Create FastHTML content for a specific page."""

        card_class = "intro-card"

        if page_num == 1:
            title = f'This instance is White-labeled as: {app_name} 🎯'
            features = [
                ('👤 PROFILE', 'Set up Clients under PROFILE. Each has Tasks to do.'),
                ('⚡ APP', 'AI-assisted workflows. Start with Hello Workflow to get the gist.'),
                ('DEV/Prod', 'Use DEV mode for practice and Prod in front of your clients.')
            ]
            return Card(
                H2(title),
                P('Learn to run simple, linear workflows to advance your career, satisfy clients and train models. Menu options are:'),
                Ol(*[Li(Strong(f'{name}:'), f' {desc}') for name, desc in features]),
                P(f'This is Instance 1.0 of Project Pipulate AIE (pronounced "Ayyy"—like the Fonz) inhabited by Chip O\'Theseus and powered by Ollama ({model}) to assist you 🤖. Click ',
                  A('Next ▸',
                    hx_post='/introduction/page/2',
                    hx_target='#grid-left-content',
                    hx_swap='innerHTML',
                    cls='link-inherit-underline',
                    onmouseover='this.style.color="#007bff";',
                    onmouseout='this.style.color="inherit";'),
                  ' to continue.'),
                cls=card_class
            )

        elif page_num == 2:
            title = 'Local AI Assistant Setup 🤖'
            intro_text = f"{app_name} uses a separately installed local chatbot called Ollama with the recommended gemma3 model. Installing it is encouraged to keep a local AI riding shotgun to provide advice. And it's free as in electricity."
            benefits = [
                ('🔒 PRIVATE', 'No registration or API token required. Completely local and private.'),
                ('💰 FREE', 'Free for the price of electricity - no monthly subscriptions.'),
                ('🧠 CONTEXT-AWARE', 'Always knows what you\'re doing and can provide specific advice.'),
                ('🚀 INSTANT', 'No network delays - responds immediately from your machine.')
            ]
            installation_title = 'Installation Steps'
            installation_steps = [
                ('DOWNLOAD OLLAMA', 'Ollama has custom Mac and Windows installers - use them for best results.'),
                ('LOAD GEMMA 3', 'Once Ollama is installed, open a Terminal and type "ollama pull gemma3".'),
                ('EXPERIMENT', 'Feel free to try other models once you\'re comfortable with the basics.')
            ]
            fallback_note = f'If you don\'t take this step, the majority of {app_name} will still work — just without an AI riding shotgun.'
            return Card(
                H2(title),
                P(intro_text),
                Ol(
                    Li(
                        Strong(
                            A('DOWNLOAD OLLAMA',
                              href='https://ollama.com/',
                              target='_blank',
                              cls='link-inherit-plain',
                              onmouseover='this.style.textDecoration="underline"; this.style.color="#007bff";',
                              onmouseout='this.style.textDecoration="none"; this.style.color="inherit";'),
                            Img(src='/assets/feather/external-link.svg',
                                alt='External link',
                                style='width: 14px; height: 14px; margin-left: 0.25rem; vertical-align: middle; filter: brightness(0) invert(1);'),
                            ':'
                        ),
                        ' Ollama has custom Mac and Windows installers - use them for best results.'
                    ),
                    *[Li(Strong(f'{name}:'), f' {desc}') for name, desc in installation_steps[1:]]
                ),
                P(fallback_note),
                cls=card_class
            )

        elif page_num == 3:
            experimenting_title = 'Positive First Experience'
            experimenting_steps = [
                ('🚀 START', 'in DEV mode. Practice! Try stuff like resetting the entire database 🔄 (in 🤖). Experiment and get comfortable. You can do no harm. This is what DEV mode is for.'),
                ('👥 PROFILES', 'Add them. Rearrange them. Check and uncheck them. Changes are reflected instantly in the PROFILE menu. Notice how "Lock" works to help avoid accidentally showing other Client (Nick)names to each other.'),
                ('⚡ WORKFLOWS', f'Try the Hello Workflow to get a feel for how {app_name} workflows work.')
            ]
            interface_title = 'Understanding the Interface'
            interface_items = [
                ('👤 PROFILES', 'Give Clients cute nicknames in Prod mode (Appliances, Sneakers, etc). Resetting database won\'t delete. So experiment in DEV and let permanent choices "settle in" in Prod.'),
                ('📊 APPS', "Botify folks: try Parameter Buster on your Client. It's a big potential win."),
                ('🔗 LINK GRAPH', "Botify folks: try Link Graph Visualizer to explore internal linking patterns.")
            ]
            return Card(
                H3(experimenting_title),
                Ol(*[Li(Strong(f'{name}:'), f' {desc}') for name, desc in experimenting_steps]),
                H3(interface_title),
                Ul(*[Li(Strong(f'{name}:'), f' {desc}') for name, desc in interface_items]),
                cls=card_class
            )

        elif page_num == 4:
            title = 'Tips for Effective Use'
            tips = [
                ('🔗 CONNECT', 'Set up your API keys to activate Botify-integrated workflows such as Parameter Buster and Link Graph Visualizer.'),
                ('🗑️ DELETE', 'Workflows are disposable because they are so easily re-created. So if you lose a particular workflow, just make it again with the same inputs 🤯'),
                ('💾 SAVE', 'Anything you do that has side-effects like CSVs stays on your computer even when you delete the workflows. Browse directly to files or attach new workflows to them by using the same input. Caveat: a complete reinstall using that "rm -rf ~/Botifython" command will delete everything.'),
                ('🔒 LOCK', 'Lock PROFILE to avoid showing other Client (Nick)names to each other.'),
                ('📁 BROWSE', 'Go look where things are saved.')
            ]
            return Card(
                H3(title),
                Ol(*[Li(Strong(f'{name}:'), f' {desc}') for name, desc in tips]),
                Hr(),
                P('Try it now: ', A('Open Downloads Folder',
                                   href='/open-folder?path=' + urllib.parse.quote(str(Path('downloads').absolute())),
                                   hx_get='/open-folder?path=' + urllib.parse.quote(str(Path('downloads').absolute())),
                                   hx_swap='none')),
                cls=card_class
            )

        elif page_num == 5:
            title = 'The Localhost Advantage 🏠'
            intro_text = f'You\'ve paid the price of a more difficult install than a cloud app. Congratulations! Time to reap the rewards.'
            advantages = [
                ('🔐 BROWSER LOGINS', 'Access web UIs like Botify, SEMRush, ahrefs without APIs. Browser saves passwords locally, nothing leaves your machine.'),
                ('💾 PERSISTENT FILES', 'All CSVs and web scrapes stay on your machine for browsing. No daily clearing like Google Colab.'),
                ('⏱️ LONG-RUNNING WORKFLOWS', 'Crawls can run 24+ hours without being "shut down" for resource usage. No cloud time limits.'),
                ('🛡️ VPN FLEXIBILITY', 'Use your VPN to control web traffic appearance. No known cloud IPs or complex IP-hiding costs.')
            ]
            benefits_title = 'Real-World Benefits'
            benefits = [
                ('Control your data', 'Everything stays local and under your control.'),
                ('No artificial limits', 'Run workflows as long as needed.'),
                ('Use existing tools', 'Leverage your VPN and browser setup.'),
                ('Browse files naturally', 'Access outputs like any local file.')
            ]
            return Card(
                H3(title),
                P(intro_text),
                Ol(*[Li(Strong(f'{name}:'), f' {desc}') for name, desc in advantages]),
                H4(benefits_title),
                Ol(*[Li(Strong(f'{name}:'), f' {desc}') for name, desc in benefits]),
                cls=card_class
            )

        elif page_num == 6:
            title = 'Local LLM Assistant 🤖'
            llm_features = [
                ('🔒 PRIVACY', 'All conversations stay on your machine. No data is sent to external servers.'),
                ('🧠 CONTEXT', 'The LLM understands your current workflow and can help with specific tasks.'),
                ('💡 GUIDANCE', 'Ask questions about workflows, get help with API keys, or request explanations.'),
                ('🔗 INTEGRATION', 'The LLM is aware of your current profile, environment, and active workflow.'),
                ('⚡ REAL-TIME', 'Chat updates in real-time as you progress through workflows.')
            ]
            usage_tips = [
                'Try asking "What can I do with this workflow?" when starting a new one.',
                'Ask for help with specific steps if you get stuck.',
                'Request explanations of workflow outputs or data.',
                'Get suggestions for next steps or alternative approaches.'
            ]
            return Card(
                H3(title),
                P(f'Your local LLM ({model}) provides intelligent assistance throughout your workflow:'),
                Ol(*[Li(Strong(f'{name}:'), f' {desc}') for name, desc in llm_features]),
                H4('How to Use the LLM'),
                Ul(*[Li(tip) for tip in usage_tips]),
                cls=card_class
            )

        elif page_num == 7:
            title = 'Background LLM Training'
            intro_text = f'🧠 {app_name} automatically trains your local LLM as you navigate. The LLM learns what you\'re viewing without cluttering your chat.'
            how_it_works = [
                ('SILENT UPDATES', 'Page content added to LLM history in the background.'),
                ('SECRET WORDS', 'Each page has a secret word proving successful training.'),
                ('CONTEXTUAL AWARENESS', 'LLM can answer questions about content you\'ve viewed.')
            ]
            examples_title = 'Where This Works'
            examples = [
                ('📖 Introduction Pages', 'Each page trains the LLM with its content and secret word.'),
                ('🐇 Workflows', 'Starting workflows loads specific training content.'),
                ('📚 Documentation', 'Viewing docs automatically adds full content to LLM context.')
            ]
            testing_tip = 'Ask: "What are all the secret words from the Introduction pages?"'
            return Card(
                H3(title),
                P(intro_text),
                H4('How It Works'),
                Ol(*[Li(Strong(f'{name}:'), f' {desc}') for name, desc in how_it_works]),
                H4(examples_title),
                Ul(*[Li(Strong(f'{name}:'), f' {desc}') for name, desc in examples]),
                Hr(),
                P(Strong('🧪 Test the System: '), testing_tip),
                cls=card_class
            )

        else:
            return Card(
                H3("Page Not Found"),
                P(f"Introduction page {page_num} not found."),
                cls="min-height-300"
            )

    async def serve_page(self, request):
        """Handle page navigation within the main app framework."""
        page_num = int(request.path_params.get('page_num', '1'))

        # Get app name and model from server settings
        from server import APP_NAME, MODEL

        # Store current page in database
        try:
            self.pipulate.db['intro_current_page'] = str(page_num)
        except Exception as e:
            logger.warning(f"Could not store intro_current_page: {e}")
            # Continue without storing - this is non-critical

        # Return the updated content directly (same as landing method)
        return await self.landing()

    async def landing(self, render_items=None):
        """Always appears in create_grid_left."""
        # Get app name and model from server settings
        from server import APP_NAME, MODEL

        # Get current page from database, default to 1
        current_page = int(self.pipulate.db.get('intro_current_page', '1'))

        # Send the intro message to conversation history, but only once per session
        if self.pipulate is not None:
            try:
                # Add the endpoint message only once
                if not self._has_sent_endpoint_message:
                    self.pipulate.append_to_history(self.ENDPOINT_MESSAGE, role="system")
                    self._has_sent_endpoint_message = True
                    logger.debug("Introduction endpoint message added to conversation history")

            except Exception as e:
                logger.error(f"Error in introduction plugin: {str(e)}")

        # Create navigation arrows (matching original server.py style)
        prev_button = Button(
            '◂ Previous',
            hx_post=f'/introduction/page/{current_page - 1}' if current_page > 1 else '#',
            hx_target='#grid-left-content',
            hx_swap='innerHTML',
            cls=f"{'primary outline' if current_page == 1 else 'primary'} width-160",
            disabled=current_page == 1
        )

        next_button = Button(
            'Next ▸',
            hx_post=f'/introduction/page/{current_page + 1}' if current_page < 7 else '#',
            hx_target='#grid-left-content',
            hx_swap='innerHTML',
            cls=f"{'primary outline' if current_page == 7 else 'primary'} width-160",
            disabled=current_page == 7
        )

        nav_arrows = Div(
            prev_button,
            next_button,
            cls='flex-center-gap'
        )

        # Create the current page content
        page_content = self.create_page_content(current_page, APP_NAME, MODEL)

        return Div(
            H2(f"📖 Intro to the field of AIE (AI Educator) - Page {current_page} of 7"),
            nav_arrows,
            page_content,
        )
