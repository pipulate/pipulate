import logging
import time

from fastcore.xml import *
from fasthtml.common import *

# Place this utility in the 'Workshop' role
ROLES = ['Workshop']

logger = logging.getLogger(__name__)


class AspectPlugin:
    NAME = "aspect"
    DISPLAY_NAME = "9:16 Aspect 🎬"
    ENDPOINT_MESSAGE = "Loading 9:16 aspect ratio guide..."

    # -------------------------------------------------------------------------
    # CSS for the IN-APP widget (works inside the template)
    # -------------------------------------------------------------------------
    IN_APP_HOTSPOT_STYLES = """
    .hotspot-wrapper {
        display: flex;
        justify-content: center;
        align-items: center;
        /* Use 70vh to roughly fill the available app area height */
        height: 70vh;
        width: 100%;
        overflow: hidden;
        padding: 1rem;
    }
    /* This is the 9:16 "hot spot" */
    #in-app-hotspot {
        /*
         * This is the "magic" adapted for an app container:
         * Height is 95% of the wrapper's height.
         * 'aspect-ratio' property automatically calculates the
         * correct 9:16 width based on that height.
         */
        height: 95%;
        aspect-ratio: 9 / 16;
        
        /* Make it look like an "acetate" */
        background-color: rgba(255, 0, 0, 0.2); /* 20% red */
        border: 2px dashed rgba(255, 0, 0, 0.7); /* Solid red border */
        
        /* Just so we know what it is */
        display: flex;
        justify-content: center;
        align-items: center;
        color: rgba(255, 255, 255, 0.7);
        font-size: 3vh; /* vh is fine for font size */
        font-family: sans-serif;
        font-weight: bold;
        text-shadow: 0 0 5px black;
    }
    """

    # -------------------------------------------------------------------------
    # HTML for the FULLSCREEN 'Acetate' (bypasses all templates)
    # This is the *original* HTML from your article
    # -------------------------------------------------------------------------
    FULLSCREEN_ACETATE_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>9:16 Hot Spot</title>
    <style>
        body, html {
            margin: 0;
            padding: 0;
            height: 100vh;
            width: 100vw;
            background-color: rgba(0, 0, 0, 0.0); /* Transparent background */
            display: flex;
            justify-content: center;
            align-items: center;
            overflow: hidden;
        }
        /* This is the 9:16 "hot spot" */
        #hotspot {
            /* * This is the "magic":
             * Height is 95% of the screen height.
             * Width is 95% of the screen height * (9/16).
             * This *guarantees* a 9:16 aspect ratio on ANY screen.
             */
            height: 95vh;
            width: calc(95vh * (9 / 16));
            
            /* Make it look like an "acetate" */
            background-color: rgba(255, 0, 0, 0.2); /* 20% red */
            border: 2px dashed rgba(255, 0, 0, 0.7); /* Solid red border */
            
            /* Just so we know what it is */
            display: flex;
            justify-content: center;
            align-items: center;
            color: rgba(255, 255, 255, 0.7);
            font-size: 3vh;
            font-family: sans-serif;
            font-weight: bold;
            text-shadow: 0 0 5px black;
        }
    </style>
</head>
<body>
    <div id="hotspot">
        9:16 HOT SPOT
    </div>
</body>
</html>
"""

    def __init__(self, app, pipulate, pipeline, db):
        logger.debug(f"AspectPlugin initialized with NAME: {self.NAME}")
        self.pipulate = pipulate
        self._has_streamed = False
        
        # --- (Step 1) Register the new custom route ---
        # This is the "Jiu-Jitsu" move from 050_documentation.py
        app.route('/aspect-fullscreen', methods=['GET'])(self.serve_fullscreen_aspect)

    async def landing(self, render_items=None):
        """Always appears in create_grid_left."""
        # Send the endpoint message to the conversation history, but only once
        if self.pipulate is not None and not self._has_streamed:
            try:
                await self.pipulate.stream(
                    self.ENDPOINT_MESSAGE,
                    verbatim=True,
                    role="system",
                    spaces_before=1,
                    spaces_after=1
                )
                self._has_streamed = True
            except Exception as e:
                logger.error(f"Error in aspect plugin: {str(e)}")

        # --- (Step 3) Add a link to the new fullscreen mode ---
        fullscreen_link = A(
            "Open Fullscreen 'Acetate' Mode ↗",
            href="/aspect-fullscreen",
            target="_blank",  # This opens it in a new tab
            role="button",
            cls="secondary outline",
            style="margin-top: 1rem;"
        )

        # Return the page content: Style + Wrapper + Hotspot + Link
        return Div(
            Style(self.IN_APP_HOTSPOT_STYLES),
            H2(self.DISPLAY_NAME),
            P("A 'No-Gooey' 9:16 vertical video aspect ratio guide for screen recording alignment."),
            P("This widget shows the aspect ratio inside the Pipulate UI. For a minimal, template-free 'acetate' overlay, use the link below."),
            
            # The new link
            fullscreen_link,
            
            # The original in-app widget
            Div(
                Div(
                    "9:16 IN-APP",
                    id="in-app-hotspot"
                ),
                cls="hotspot-wrapper"
            )
        )

    # -------------------------------------------------------------------------
    # (Step 2) The new route handler that serves the standalone page
    # -------------------------------------------------------------------------
    async def serve_fullscreen_aspect(self, request):
        """
        Serves the standalone, template-free 9:16 'acetate'
        by returning a full HTMLResponse, bypassing the main template.
        """
        logger.debug("Serving fullscreen 9:16 'acetate'...")
        return HTMLResponse(self.FULLSCREEN_ACETATE_HTML)