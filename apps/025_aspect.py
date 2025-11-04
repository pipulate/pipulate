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

    # Adapted CSS from your 'browser-acetate' article
    # This is modified to work *inside* the app's content area
    # instead of taking over the full browser viewport.
    HOTSPOT_STYLES = """
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
    #hotspot {
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

    def __init__(self, app, pipulate, pipeline, db):
        logger.debug(f"AspectPlugin initialized with NAME: {self.NAME}")
        self.pipulate = pipulate
        self._has_streamed = False  # Flag to track if we've already streamed

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

        # Return the page content: Style + Wrapper + Hotspot
        return Div(
            Style(self.HOTSPOT_STYLES),
            H2(self.DISPLAY_NAME),
            P("A 'No-Gooey' 9:16 vertical video aspect ratio guide for screen recording alignment."),
            P("Use this visual guide to position elements for your 'No-Gooey Video' workflow."),
            Div(
                Div(
                    "9:16 HOT SPOT",
                    id="hotspot"
                ),
                cls="hotspot-wrapper"
            )
        )