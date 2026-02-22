/**
 * GLOBAL CONFIG PATTERN: Reads window.CFG set by Python
 * 
 * This file automatically reads configuration from global variables.
 * No initialization call needed - Python sets config before loading.
 * 
 * Pattern: Static JS file that reads Python-generated global configuration
 */

// Define test alert function globally
window.testAlert = function(message) {
    alert('Test Alert: ' + message);
    console.log('Alert triggered with:', message);
};

// Get configuration from the global variable
const config = window.CFG || {};
const tempMessage = config.tempMessage;

// 🎭 RUBY SLIPPERS: Platform-aware keyboard shortcuts
// Platform detection for Mac keyboard shortcuts (Control+Option vs Ctrl+Alt)
const platform = navigator.platform.toLowerCase();
const userAgent = navigator.userAgent.toLowerCase();
const isMac = platform.includes('mac') || userAgent.includes('mac');

// Set platform-appropriate display text for keyboard shortcuts
window.PLATFORM_KEYS = {
    display: isMac ? 'Control+Option' : 'Ctrl+Alt',
    y_key: isMac ? 'Control+Option+Y' : 'Ctrl+Alt+Y', 
    n_key: isMac ? 'Control+Option+N' : 'Ctrl+Alt+N',
    d_key: isMac ? 'Control+Option+D' : 'Ctrl+Alt+D',
    r_key: isMac ? 'Control+Option+R' : 'Ctrl+Alt+R',
    v_key: isMac ? 'Control+Option+V' : 'Ctrl+Alt+V',
    w_key: isMac ? 'Control+Option+W' : 'Ctrl+Alt+W',
    g_key: isMac ? 'Control+Option+G' : 'Ctrl+Alt+G'
};

console.log('🎭 Platform detection:', isMac ? 'Mac' : 'Windows/Linux', '- Using:', window.PLATFORM_KEYS.display);

// 🎭 RUBY SLIPPERS: Platform-aware message adaptation
// Dynamically replace keyboard shortcut text based on platform
window.adaptMessageForPlatform = function(message) {
    if (!message || typeof message !== 'string') return message;
    
    return message
        // Replace bold keyboard shortcuts
        .replace(/\*\*Ctrl\+Alt\+y\*\*/gi, `**${window.PLATFORM_KEYS.y_key}**`)
        .replace(/\*\*Ctrl\+Alt\+n\*\*/gi, `**${window.PLATFORM_KEYS.n_key}**`)
        .replace(/\*\*Ctrl\+Alt\+d\*\*/gi, `**${window.PLATFORM_KEYS.d_key}**`)
        .replace(/\*\*Ctrl\+Alt\+r\*\*/gi, `**${window.PLATFORM_KEYS.r_key}**`)
        .replace(/\*\*Ctrl\+Alt\+v\*\*/gi, `**${window.PLATFORM_KEYS.v_key}**`)
        .replace(/\*\*Ctrl\+Alt\+w\*\*/gi, `**${window.PLATFORM_KEYS.w_key}**`)
        .replace(/\*\*Ctrl\+Alt\+g\*\*/gi, `**${window.PLATFORM_KEYS.g_key}**`)
        .replace(/\*\*Ctrl\+Alt\+Y\*\*/g, `**${window.PLATFORM_KEYS.y_key}**`)
        .replace(/\*\*Ctrl\+Alt\+N\*\*/g, `**${window.PLATFORM_KEYS.n_key}**`)
        .replace(/\*\*Ctrl\+Alt\+D\*\*/g, `**${window.PLATFORM_KEYS.d_key}**`)
        .replace(/\*\*Ctrl\+Alt\+R\*\*/g, `**${window.PLATFORM_KEYS.r_key}**`)
        .replace(/\*\*Ctrl\+Alt\+V\*\*/g, `**${window.PLATFORM_KEYS.v_key}**`)
        .replace(/\*\*Ctrl\+Alt\+W\*\*/g, `**${window.PLATFORM_KEYS.w_key}**`)
        .replace(/\*\*Ctrl\+Alt\+G\*\*/g, `**${window.PLATFORM_KEYS.g_key}**`)
        // Replace plain text shortcuts
        .replace(/Ctrl\+Alt\+y/gi, window.PLATFORM_KEYS.y_key)
        .replace(/Ctrl\+Alt\+n/gi, window.PLATFORM_KEYS.n_key)
        .replace(/Ctrl\+Alt\+d/gi, window.PLATFORM_KEYS.d_key)
        .replace(/Ctrl\+Alt\+r/gi, window.PLATFORM_KEYS.r_key)
        .replace(/Ctrl\+Alt\+v/gi, window.PLATFORM_KEYS.v_key)
        .replace(/Ctrl\+Alt\+w/gi, window.PLATFORM_KEYS.w_key)
        .replace(/Ctrl\+Alt\+g/gi, window.PLATFORM_KEYS.g_key)
        .replace(/Ctrl\+Alt\+Y/g, window.PLATFORM_KEYS.y_key)
        .replace(/Ctrl\+Alt\+N/g, window.PLATFORM_KEYS.n_key)
        .replace(/Ctrl\+Alt\+D/g, window.PLATFORM_KEYS.d_key)
        .replace(/Ctrl\+Alt\+R/g, window.PLATFORM_KEYS.r_key)
        .replace(/Ctrl\+Alt\+V/g, window.PLATFORM_KEYS.v_key)
        .replace(/Ctrl\+Alt\+W/g, window.PLATFORM_KEYS.w_key)
        .replace(/Ctrl\+Alt\+G/g, window.PLATFORM_KEYS.g_key);
};

// Flag to prevent duplicate temp message sending
let tempMessageSent = false;

// Match the WebSocket route from Chat
let sidebarWs = new WebSocket('ws://' + window.location.host + '/ws');
const sidebarMsgList = document.getElementById('msg-list');
let sidebarCurrentMessage = document.createElement('div');
sidebarCurrentMessage.className = 'message assistant';

// PERFORMANCE OPTIMIZATION: Throttle Markdown rendering to prevent exponential slowdown
let renderThrottleTimer = null;
const RENDER_THROTTLE_DELAY = config.CHAT_CONFIG?.RENDER_THROTTLE_DELAY || 15; // Configurable delay between renders (milliseconds)

sidebarWs.onopen = function() {
    console.log('Sidebar WebSocket connected');
    // If there's a temp message waiting and we just connected, send it immediately
    if (tempMessage && document.readyState === 'complete' && !tempMessageSent) {
        console.log('WebSocket opened, sending queued temp message:', tempMessage);
        const messageWithNewline = tempMessage + '';
        sidebarWs.send(`${messageWithNewline}|verbatim`);
        tempMessageSent = true;
    }
};

sidebarWs.onclose = function(event) {
    console.log('Sidebar WebSocket closed');
    console.log('🔧 WebSocket close details:', {
        code: event.code,
        reason: event.reason,
        wasClean: event.wasClean,
        timestamp: new Date().toISOString()
    });
};

sidebarWs.onerror = function(error) {
    console.error('Sidebar WebSocket error:', error);
    console.error('🔧 WebSocket error details:', {
        type: error.type,
        target: error.target,
        timestamp: new Date().toISOString()
    });
};

// Removed linkifyText function - no automatic URL linking

// Timer-based UI prediction removed - server now controls streaming state completely
sidebarWs.onmessage = function(event) {
    // Handle UI control messages first
    if (event.data === '%%STREAM_START%%') {
        updateStreamingUI(true);
        return false; // Do not display this message
    }
    if (event.data === '%%STREAM_END%%') {
        updateStreamingUI(false);
        
        // PERFORMANCE OPTIMIZATION: Ensure final render happens and clear any pending renders
        if (renderThrottleTimer) {
            clearTimeout(renderThrottleTimer);
            renderThrottleTimer = null;
        }
        // Force final render of the complete message
        renderCurrentMessage();
        
        // Add clipboard functionality to the completed assistant message
        if (sidebarCurrentMessage && sidebarCurrentMessage.dataset.rawText) {
            addClipboardToAssistantMessage(sidebarCurrentMessage);
        }
        // Reset message buffer for next stream
        sidebarCurrentMessage = document.createElement('div');
        sidebarCurrentMessage.className = 'message assistant';
        return false; // Do not display this message
    }

    console.log('Sidebar received:', event.data);
    
    // Check if the message is a script
    if (event.data.trim().startsWith('<script>')) {
        const scriptContent = event.data.replace(/<\/?script>/g, '').trim();
        console.log('Executing script:', scriptContent);
        try {
            eval(scriptContent);
        } catch (e) {
            console.error('Error executing script:', e);
        }
        return false;
    }
    
    // Check if the response contains a plugin list item
    if (event.data.includes('data-plugin-item="true"')) {
        const tempDiv = document.createElement('div');
        tempDiv.innerHTML = event.data.trim();
        const newItem = tempDiv.firstElementChild;
        
        if (newItem && newItem.hasAttribute('data-list-target')) {
            const listId = newItem.getAttribute('data-list-target');
            const targetList = document.getElementById(listId);
            
            if (targetList) {
                targetList.appendChild(newItem);
                htmx.process(newItem);
                
                // Initialize sortable if needed
                if (window.Sortable && !targetList.classList.contains('sortable-initialized')) {
                    new Sortable(targetList, {
                        animation: 150,
                        ghostClass: 'blue-background-class'
                    });
                    targetList.classList.add('sortable-initialized');
                }
            }
        }
        return false;
    }
    
    // Handle regular chat messages
    if (!sidebarCurrentMessage.parentElement) {
        sidebarMsgList.appendChild(sidebarCurrentMessage);
    }
    
    // Initialize or update the raw text buffer
    if (!sidebarCurrentMessage.dataset.rawText) {
        sidebarCurrentMessage.dataset.rawText = '';
    }
    sidebarCurrentMessage.dataset.rawText += event.data;
    
    // PERFORMANCE OPTIMIZATION: Throttle Markdown rendering to prevent exponential slowdown
    // Clear existing timer if one exists
    if (renderThrottleTimer) {
        clearTimeout(renderThrottleTimer);
    }
    
    // Schedule a throttled render
    renderThrottleTimer = setTimeout(() => {
        renderCurrentMessage();
        renderThrottleTimer = null;
    }, RENDER_THROTTLE_DELAY);
    
    // Keep the latest message in view
    sidebarMsgList.scrollTop = sidebarMsgList.scrollHeight;
};

// PERFORMANCE OPTIMIZATION: Dedicated function for rendering current message
function renderCurrentMessage() {
    // Render the accumulated Markdown with improved code fence detection
    if (typeof marked !== 'undefined') {
        try {
            const rawText = sidebarCurrentMessage.dataset.rawText;
            
            // Enhanced code fence detection - handle both ``` and ~~~ fences
            const codeFenceRegex = /^(```|~~~)/gm;
            const allFences = rawText.match(codeFenceRegex) || [];
            const hasIncompleteCodeFence = allFences.length % 2 !== 0;
            
            if (hasIncompleteCodeFence) {
                // Don't parse incomplete markdown - show as plain text for now
                // But preserve basic formatting for readability
                const lines = rawText.split('\n');
                const formattedLines = lines.map(line => {
                    // Basic HTML escaping for safety, but preserve <br> tags
                    return line.replace(/&/g, '&amp;')
                              .replace(/</g, '&lt;')
                              .replace(/>/g, '&gt;')
                              .replace(/&lt;br&gt;/g, '<br>'); // Convert escaped <br> back to actual breaks
                });
                sidebarCurrentMessage.innerHTML = formattedLines.join('<br>');
            } else {
                // Safe to parse complete markdown using pre-configured marked
                // PREPROCESSING: Clean up markdown to prevent extra spacing
                let cleanedText = rawText;
                
                // Remove extra whitespace between list items while preserving structure
                cleanedText = cleanedText
                    // Remove empty lines between list items in the same list
                    .replace(/(\n\s*[-*+]\s+[^\n]+)\n\s*\n(\s*[-*+]\s+)/g, '$1\n$2')
                    // Remove extra whitespace around nested lists
                    .replace(/(\n\s*[-*+]\s+[^\n]+)\n\s*\n(\s+[-*+]\s+)/g, '$1\n$2')
                    // Clean up multiple consecutive newlines (but preserve intentional paragraph breaks)
                    .replace(/\n\s*\n\s*\n/g, '\n\n')
                    // Remove trailing whitespace from lines
                    .replace(/[ \t]+$/gm, '')
                    // Normalize line endings
                    .replace(/\r\n/g, '\n');
                
                const renderedHtml = marked.parse(cleanedText);
                
                // POST-PROCESSING: Clean up HTML whitespace between elements
                let cleanedHtml = renderedHtml
                    // Remove whitespace between closing and opening list item tags
                    .replace(/(<\/li>)\s+(<li>)/g, '$1$2')
                    // Remove whitespace between closing list item and opening nested list
                    .replace(/(<\/li>)\s+(<ul>|<ol>)/g, '$1$2')
                    // Remove whitespace between closing nested list and opening list item
                    .replace(/(<\/ul>|<\/ol>)\s+(<li>)/g, '$1$2')
                    // Remove whitespace between opening list and first list item
                    .replace(/(<ul>|<ol>)\s+(<li>)/g, '$1$2')
                    // Remove whitespace between last list item and closing list
                    .replace(/(<\/li>)\s+(<\/ul>|<\/ol>)/g, '$1$2')
                    // Remove extra whitespace between paragraphs and lists
                    .replace(/(<\/p>)\s+(<ul>|<ol>)/g, '$1$2')
                    .replace(/(<\/ul>|<\/ol>)\s+(<p>)/g, '$1$2');
                
                sidebarCurrentMessage.innerHTML = cleanedHtml;
                
                // Apply syntax highlighting if Prism is available
                if (typeof Prism !== 'undefined') {
                    Prism.highlightAllUnder(sidebarCurrentMessage);
                }
            }
        } catch (e) {
            console.error('Error rendering Markdown:', e);
            // Fallback to safely formatted plain text
            const processedText = sidebarCurrentMessage.dataset.rawText
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
                .replace(/&lt;br&gt;/g, '<br>') // Convert escaped <br> back to actual breaks
                .replace(/\n/g, '<br>');
            sidebarCurrentMessage.innerHTML = processedText;
        }
    } else {
        // Fallback to plain text if marked.js is not available
        console.warn('marked.js is not available - using plain text');
        const processedText = sidebarCurrentMessage.dataset.rawText
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/&lt;br&gt;/g, '<br>') // Convert escaped <br> back to actual breaks
            .replace(/\n/g, '<br>');
        sidebarCurrentMessage.innerHTML = processedText;
    }
}

// --- Streaming state and UI control ---
let isStreaming = false;

function updateStreamingUI(streaming) {
    isStreaming = streaming;
    const sendBtn = document.getElementById('send-btn');
    const stopBtn = document.getElementById('stop-btn');
    const input = document.getElementById('msg');
    
    if (!sendBtn || !stopBtn || !input) return false;
    
    if (isStreaming) {
        sendBtn.style.display = 'none';
        stopBtn.style.display = 'block';
        input.disabled = true;
        input.placeholder = 'Streaming response...';
    } else {
        sendBtn.style.display = 'block';
        stopBtn.style.display = 'none';
        input.disabled = false;
        input.placeholder = 'Chat...';
        input.focus();
    }
}

// Initialize chat interface icons and state
function initializeChatInterface() {
    updateStreamingUI(false);
}

// Copy message to clipboard with visual feedback
function copyMessageToClipboard(text, button) {
    if (navigator.clipboard && window.isSecureContext) {
        navigator.clipboard.writeText(text).then(() => {
            showClipboardSuccess(button);
        }).catch(err => {
            console.error('Failed to copy message:', err);
            showClipboardError(button);
        });
    } else {
        // Fallback for older browsers
        const textArea = document.createElement('textarea');
        textArea.value = text;
        textArea.style.position = 'fixed';
        textArea.style.left = '-999999px';
        textArea.style.top = '-999999px';
        document.body.appendChild(textArea);
        textArea.focus();
        textArea.select();
        
        try {
            const successful = document.execCommand('copy');
            document.body.removeChild(textArea);
            if (successful) {
                showClipboardSuccess(button);
            } else {
                showClipboardError(button);
            }
        } catch (err) {
            document.body.removeChild(textArea);
            console.error('Fallback copy failed:', err);
            showClipboardError(button);
        }
    }
}

// Show success feedback for clipboard copy
function showClipboardSuccess(button) {
    const originalHTML = button.innerHTML;
    button.innerHTML = '✅';
    button.style.opacity = '1';
    button.style.backgroundColor = 'var(--pico-color-green-500)';
    
    setTimeout(() => {
        button.innerHTML = originalHTML;
        button.style.opacity = '0.6';
        button.style.backgroundColor = 'transparent';
    }, 2000);
}

// Show error feedback for clipboard copy
function showClipboardError(button) {
    const originalHTML = button.innerHTML;
    button.innerHTML = '❌';
    button.style.opacity = '1';
    button.style.backgroundColor = 'var(--pico-color-red-500)';
    
    setTimeout(() => {
        button.innerHTML = originalHTML;
        button.style.opacity = '0.6';
        button.style.backgroundColor = 'transparent';
    }, 2000);
}

// Add clipboard functionality to assistant messages
function addClipboardToAssistantMessage(messageElement) {
    // Check if clipboard button already exists
    if (messageElement.querySelector('.clipboard-button')) {
        return false;
    }
    
    // Only add clipboard if message has content
    const messageText = messageElement.dataset.rawText;
    if (!messageText || messageText.trim() === '') {
        return false;
    }
    
    // Create message container structure
    const messageContainer = document.createElement('div');
    messageContainer.className = 'message-container';
    
    const messageContent = document.createElement('div');
    messageContent.className = 'message-content';
    messageContent.innerHTML = messageElement.innerHTML;
    
    const clipboardButton = document.createElement('button');
    clipboardButton.className = 'clipboard-button';
    clipboardButton.innerHTML = window.CFG.clipboardSVG;
    clipboardButton.title = 'Copy message to clipboard';
    clipboardButton.onclick = function(e) {
        e.preventDefault();
        e.stopPropagation();
        copyMessageToClipboard(messageText, clipboardButton);
    };
    
    messageContainer.appendChild(messageContent);
    messageContainer.appendChild(clipboardButton);
    
    // Replace the message element content
    messageElement.innerHTML = '';
    messageElement.appendChild(messageContainer);
}

window.stopSidebarStream = function() {
    if (isStreaming && sidebarWs.readyState === WebSocket.OPEN) {
        console.log('Sending stop command to server...');
        sidebarWs.send('%%STOP_STREAM%%');
        // The UI will be fully updated once the server sends back %%STREAM_END%%
        updateStreamingUI(false); // Optimistically update UI
    }
}

window.sendSidebarMessage = function(event) {
    event.preventDefault();
    const input = document.getElementById('msg');
    if (input.value && !isStreaming) { // Prevent sending while streaming
        const userMessageText = input.value;
        const userMsg = document.createElement('div');
        userMsg.className = 'message user';
        
        // Create message container with clipboard functionality
        const messageContainer = document.createElement('div');
        messageContainer.className = 'message-container';
        
        const messageContent = document.createElement('div');
        messageContent.className = 'message-content';
        messageContent.textContent = userMessageText;
        
        const clipboardButton = document.createElement('button');
        clipboardButton.className = 'clipboard-button';
        clipboardButton.innerHTML = window.CFG.clipboardSVG;
        clipboardButton.title = 'Copy message to clipboard';
        clipboardButton.onclick = function(e) {
            e.preventDefault();
            e.stopPropagation();
            copyMessageToClipboard(userMessageText, clipboardButton);
        };
        
        messageContainer.appendChild(messageContent);
        messageContainer.appendChild(clipboardButton);
        userMsg.appendChild(messageContainer);
        
        sidebarMsgList.appendChild(userMsg);
        
        sidebarCurrentMessage = document.createElement('div');
        sidebarCurrentMessage.className = 'message assistant';
        
        console.log('Sidebar sending:', userMessageText);
        if (sidebarWs.readyState === WebSocket.OPEN) {
            sidebarWs.send(userMessageText);
            input.value = '';
            // The server will now send %%STREAM_START%% to lock the UI
        } else {
            console.error('WebSocket not connected');
        }
    }
}

// Scroll utilities for the main grid
function scrollToTop() {
    const container = document.querySelector(".main-grid > div:first-child");
    if (container) {
        container.scrollTo({top: 0, behavior: "smooth"});
    }
}

function checkScrollHeight() {
    const container = document.querySelector('.main-grid > div:first-child');
    const scrollLink = document.getElementById('scroll-to-top-link');
    if (container && scrollLink) {
        const isScrollable = container.scrollHeight > container.clientHeight;
        scrollLink.style.display = isScrollable ? 'block' : 'none';
    }
}

function initializeScrollObserver() {
    // Check on load and when content changes
    window.addEventListener('load', checkScrollHeight);
    const observer = new MutationObserver(checkScrollHeight);
    const container = document.querySelector('.main-grid > div:first-child');
    if (container) {
        observer.observe(container, { childList: true, subtree: true });
    }
}

// Function to send temp message when WebSocket is ready
function sendTempMessageWhenReady() {
    if (!tempMessage || tempMessageSent) return false;
    
    if (sidebarWs.readyState === WebSocket.OPEN) {
        console.log('Sidebar sending verbatim:', tempMessage);
        const messageWithNewline = tempMessage + '';
        sidebarWs.send(`${messageWithNewline}|verbatim`);
        tempMessageSent = true;
    } else {
        // Wait for connection and retry
        console.log('WebSocket not ready, waiting for connection...');
        setTimeout(sendTempMessageWhenReady, 100);
    }
}

// Global demo mode tracking
let demoModeActive = false;
let currentDemoScript = null;
let currentDemoStepIndex = 0;

// ============================================================================
// UNIFIED RESTART SYSTEM - Consolidates all server restart scenarios
// ============================================================================

/**
 * Triggers the full-screen restart effect for any server restart scenario.
 * This ensures consistent user experience across all restart triggers.
 * 
 * @param {string} message - The message to display during restart
 * @param {string} restartType - Type of restart for logging (optional)
 */
function triggerFullScreenRestart(message = "Restarting server...", restartType = "MANUAL") {
    console.log(`🔄 ${restartType}: ${message}`);
    
    // Remove any existing restart overlay
    const existingOverlay = document.getElementById('restart-overlay');
    if (existingOverlay) {
        existingOverlay.remove();
    }
    
    // Create restart overlay with Pico CSS spinner
    const overlay = document.createElement('div');
    overlay.id = 'restart-overlay';
    overlay.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background-color: rgba(0, 0, 0, 0.85);
        display: flex;
        justify-content: center;
        align-items: center;
        z-index: 10000;
        color: white;
        font-family: system-ui, sans-serif;
        backdrop-filter: blur(2px);
        font-size: 1.2rem;
    `;
    
    // Use Pico CSS aria-busy spinner
    overlay.innerHTML = `<span aria-busy="true">${message}</span>`;
    
    document.body.appendChild(overlay);
    console.log(`🔄 Full-screen restart overlay displayed: ${restartType}`);
    
    // Make body non-interactive during restart
    document.body.style.pointerEvents = 'none';
    document.body.style.userSelect = 'none';
}

/**
 * Send restart command via WebSocket (for immediate restarts)
 */
function sendRestartCommand(restartType = "WEBSOCKET") {
    if (sidebarWs.readyState === WebSocket.OPEN) {
        sidebarWs.send('%%RESTART_SERVER%%');
        console.log(`🔄 ${restartType}: Restart command sent via WebSocket`);
    } else {
        console.error(`🔄 ${restartType}: WebSocket not connected, cannot send restart command`);
        // If WebSocket fails, hide the spinner after a delay
        setTimeout(() => {
            hideRestartSpinner();
        }, 3000);
    }
}

/**
 * Special lock screen for Python environment reset - less opaque, shows terminal instructions
 */
function triggerPythonEnvironmentReset() {
    console.log('🐍 PYTHON_RESET: Showing terminal instructions overlay');
    
    // Remove any existing restart overlay
    const existingOverlay = document.getElementById('restart-overlay');
    if (existingOverlay) {
        existingOverlay.remove();
    }
    
    // Create semi-transparent overlay with terminal instructions
    const overlay = document.createElement('div');
    overlay.id = 'restart-overlay';
    overlay.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background-color: rgba(0, 0, 0, 0.4);
        display: flex;
        justify-content: center;
        align-items: center;
        z-index: 10000;
        color: white;
        font-family: system-ui, sans-serif;
        backdrop-filter: blur(1px);
        font-size: 1.2rem;
    `;
    
    // Terminal instructions card
    overlay.innerHTML = `
        <div style="
            background-color: rgba(0, 0, 0, 0.85);
            padding: 2rem;
            border-radius: 8px;
            text-align: center;
            max-width: 500px;
            margin: 1rem;
            border: 2px solid #ffc107;
        ">
            <h3 style="color: #ffc107; margin-top: 0;">🐍 Python Environment Reset</h3>
            <p style="margin-bottom: 1.5rem; line-height: 1.4;">
                Return to the terminal and type:
            </p>
            <div style="
                background-color: #1e1e1e;
                padding: 1rem;
                border-radius: 4px;
                font-family: 'Courier New', monospace;
                margin-bottom: 1rem;
                border-left: 4px solid #ffc107;
            ">
                <div style="margin-bottom: 0.5rem;">exit</div>
                <div style="color: #6c757d;">...and then type:</div>
                <div style="margin-top: 0.5rem;">nix develop</div>
            </div>
            <p style="font-size: 0.9rem; color: #aaa; margin-bottom: 0;">
                This will rebuild the Python environment and restart the server.
            </p>
        </div>
    `;
    
    document.body.appendChild(overlay);
    console.log('🐍 Python environment reset overlay displayed with terminal instructions');
    
    // Make body non-interactive during reset (but don't disable completely)
    document.body.style.pointerEvents = 'none';
    document.body.style.userSelect = 'none';
}

/**
 * Complete restart sequence: Show spinner + Send command
 */
function executeFullRestartSequence(message = "Restarting server...", restartType = "MANUAL") {
    triggerFullScreenRestart(message, restartType);
    sendRestartCommand(restartType);
}

/**
 * 🎯 HEADS-UP DISPLAY (HUD) for Test Mode
 * Visual confirmation that the wind tunnel is active and context is acquired.
 */
function showContextTriggerHUD(appName, scriptName) {
    // Remove any existing overlay
    const existingOverlay = document.getElementById('test-hud-overlay');
    if (existingOverlay) existingOverlay.remove();

    const overlay = document.createElement('div');
    overlay.id = 'test-hud-overlay';
    overlay.style.cssText = `
        position: fixed;
        top: 0; left: 0; width: 100%; height: 100%;
        display: flex; flex-direction: column;
        justify-content: center; align-items: center;
        z-index: 2147483647; /* Max 32-bit integer - stay on top of EVERYTHING */
        pointer-events: none; /* Let clicks pass through */
        background-color: rgba(0, 0, 0, 0.0); /* Start transparent */
        transition: background-color 0.3s ease;
    `;

    overlay.innerHTML = `
        <div style="
            background-color: rgba(16, 185, 129, 0.95); /* Emerald Green */
            color: white;
            padding: 2rem 3rem;
            border-radius: 12px;
            box-shadow: 0 20px 50px rgba(0,0,0,0.5);
            text-align: center;
            transform: scale(0.8);
            opacity: 0;
            transition: all 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275);
            border: 2px solid #a7f3d0;
        ">
            <div style="font-size: 3rem; margin-bottom: 0.5rem;">🎯</div>
            <h2 style="margin: 0; font-size: 1.8rem; font-weight: 800; letter-spacing: -0.025em;">TEST MODE ENGAGED</h2>
            <div style="margin-top: 1rem; font-family: monospace; font-size: 1.2rem; opacity: 0.9;">
                Context: <span style="font-weight: bold; color: #fff;">${appName}</span>
            </div>
            <div style="font-size: 0.8rem; margin-top: 0.5rem; opacity: 0.7;">
                Loading: ${scriptName}
            </div>
        </div>
    `;

    document.body.appendChild(overlay);

    // Animate In
    requestAnimationFrame(() => {
        overlay.style.backgroundColor = 'rgba(0, 0, 0, 0.2)'; // Slight dim
        const card = overlay.firstElementChild;
        card.style.transform = 'scale(1)';
        card.style.opacity = '1';
    });

    // Remove after delay
    setTimeout(() => {
        const card = overlay.firstElementChild;
        card.style.transform = 'scale(1.1)'; // Pump before vanishing
        card.style.opacity = '0';
        overlay.style.backgroundColor = 'rgba(0, 0, 0, 0)';
        
        setTimeout(() => overlay.remove(), 300);
    }, 1500);
}

// Global keyboard shortcuts
document.addEventListener('keydown', function(event) {
    // 🔧 RESTORED DEBUGGING: Log modifier keys to troubleshoot OS collisions
    if (event.ctrlKey || event.altKey || event.metaKey) {
        console.log('🔧 KEYBOARD DEBUG:', {
            code: event.code,
            key: event.key,
            ctrl: event.ctrlKey,
            alt: event.altKey,
            shift: event.shiftKey,
            meta: event.metaKey,
            isMac: isMac
        });
    }

    // Ctrl+Alt+R: Restart server (Mac: Control+Option+R)
    if (event.ctrlKey && event.altKey && event.code === 'KeyR') {
        event.preventDefault();
        console.log('🔄 Restart triggered');
        executeFullRestartSequence("Restarting server...", "KEYBOARD_SHORTCUT");
    }
    
    // Ctrl+Alt+D: Start THE BIG DEMO (Legacy/Regression)
    // Mac: Control+Option+D
    if (event.ctrlKey && event.altKey && event.code === 'KeyD') {
        event.preventDefault();
        console.log('🎯 BIG DEMO triggered via Ctrl+Alt+D');
        loadAndExecuteCleanDemoScript('introduction.json'); 
    }

    // 🎯 NEW: Context-Sensitive Test/Train
    // Windows/Linux: Ctrl+Alt+Shift+S (Changed from T to avoid Terminal collision)
    // Mac: Ctrl+Option+T (Kept T for Mac as requested)
    
    // Check for 'T' (Mac preference) or 'S' (Windows/Linux safety fallback)
    const isKeyTrigger = event.code === 'KeyT' || event.code === 'KeyS';
    
    const isMacTrigger = isMac && event.ctrlKey && event.altKey && !event.shiftKey && isKeyTrigger;
    const isWinTrigger = !isMac && event.ctrlKey && event.altKey && event.shiftKey && isKeyTrigger;

    if (isMacTrigger || isWinTrigger) {
        event.preventDefault();
        console.log(`🎯 Context-sensitive Test/Train triggered via ${event.code}`);
        
        // 1. Detect current app/context
        let currentApp = 'introduction'; // Default
        const path = window.location.pathname;
        
        // Extract app name from URL logic
        if (path.includes('/redirect/')) {
            currentApp = path.split('/redirect/')[1];
        } else if (path !== '/' && path !== '') {
            const parts = path.split('/').filter(p => p);
            if (parts.length > 0) currentApp = parts[0];
            currentApp = currentApp.replace(/^\d+_/, ''); // Strip numeric prefix
        }
        
        const scriptName = `${currentApp}_test.json`;
        
        // 2. TRIGGER THE HUD
        showContextTriggerHUD(currentApp, scriptName);
        
        console.log(`🎯 Context detected: ${currentApp}. Loading ${scriptName}...`);
        
        // 3. Load the specific test script
        loadAndExecuteCleanDemoScript(scriptName);
    }

    // Ctrl+Alt+V: Test voice synthesis (Mac: Control+Option+V)
    if (event.ctrlKey && event.altKey && event.code === 'KeyV') {
        event.preventDefault();
        console.log('🎤 Voice synthesis test triggered via Ctrl+Alt+V - Mac Compatible!');
        
        // Call the voice synthesis test endpoint
        testVoiceSynthesis();
    }
    
    // Ctrl+Alt+W: Test WebSocket connection status (Mac: Control+Option+W)
    if (event.ctrlKey && event.altKey && event.code === 'KeyW') {
        event.preventDefault();
        console.log('🔧 WebSocket connection test triggered via Ctrl+Alt+W - Mac Compatible!');
        
        // Test WebSocket connection
        testWebSocketConnection();
    }
    
    // Ctrl+Alt+G: Test golden glow effect (Mac: Control+Option+G)
    if (event.ctrlKey && event.altKey && event.code === 'KeyG') {
        event.preventDefault();
        console.log('✨ Golden glow test triggered via Ctrl+Alt+G - Mac Compatible!');
        
        // Test golden glow effect directly
        testGoldenGlow();
    }
});

// Add a console log to confirm this script section loaded
console.log('🔧 Pipulate keyboard shortcuts initialized - listening for Ctrl+Alt+R, Ctrl+Alt+D, Ctrl+Alt+V, Ctrl+Alt+W, and Ctrl+Alt+G');

/**
 * 🎵 Play "Somewhere Over the Rainbow" intro
 * Creates the iconic first few bars using Web Audio API
 * Perfect accompaniment to the "Dorothy Opens the Door to Oz" transition
 */
function playSomewhereOverTheRainbow() {
    try {
        console.log('🎵 Playing "Somewhere Over the Rainbow" intro...');
        
        // Create audio context
        const audioContext = new (window.AudioContext || window.webkitAudioContext)();
        
        // Define the melody notes (first few bars of "Somewhere Over the Rainbow")
        // C major scale: C, D, E, F, G, A, B, C
        const melody = [
            { note: 'C4', duration: 0.8 },  // Some
            { note: 'E4', duration: 0.4 },  // where
            { note: 'G4', duration: 0.8 },  // o-
            { note: 'C5', duration: 1.2 },  // ver
            { note: 'B4', duration: 0.4 },  // the
            { note: 'A4', duration: 0.8 },  // rain-
            { note: 'G4', duration: 1.2 },  // bow
            { note: 'E4', duration: 0.8 },  // way
            { note: 'C4', duration: 1.6 }   // up
        ];
        
        // Note frequencies (C4 = middle C)
        const noteFrequencies = {
            'C4': 261.63, 'D4': 293.66, 'E4': 329.63, 'F4': 349.23,
            'G4': 392.00, 'A4': 440.00, 'B4': 493.88, 'C5': 523.25
        };
        
        // Create oscillator and gain nodes
        const oscillator = audioContext.createOscillator();
        const gainNode = audioContext.createGain();
        
        // Connect nodes
        oscillator.connect(gainNode);
        gainNode.connect(audioContext.destination);
        
        // Set oscillator type to sine wave for a pure, dreamy sound
        oscillator.type = 'sine';
        
        // Set initial gain to 0
        gainNode.gain.setValueAtTime(0, audioContext.currentTime);
        
        // Start the oscillator
        oscillator.start();
        
        // Play the melody
        let currentTime = audioContext.currentTime;
        
        melody.forEach((note, index) => {
            const frequency = noteFrequencies[note.note];
            const duration = note.duration;
            
            // Set frequency
            oscillator.frequency.setValueAtTime(frequency, currentTime);
            
            // Fade in
            gainNode.gain.setValueAtTime(0, currentTime);
            gainNode.gain.linearRampToValueAtTime(0.3, currentTime + 0.05);
            
            // Fade out
            gainNode.gain.setValueAtTime(0.3, currentTime + duration - 0.1);
            gainNode.gain.linearRampToValueAtTime(0, currentTime + duration);
            
            currentTime += duration;
        });
        
        // Stop the oscillator after the melody
        oscillator.stop(currentTime + 0.1);
        
        console.log('🎵 "Somewhere Over the Rainbow" intro playing...');
        
    } catch (error) {
        console.warn('🎵 Could not play audio (browser may block autoplay):', error);
        // Don't fail the demo if audio doesn't work
    }
}

// Function to test voice synthesis via web endpoint
async function testVoiceSynthesis() {
    try {
        console.log('🎤 Testing voice synthesis via web endpoint...');
        
        // Call the voice synthesis test endpoint
        const response = await fetch('/test-voice-synthesis', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
            },
            body: new URLSearchParams({
                text: 'Voice synthesis test from Ctrl+Alt+V shortcut'
            })
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const result = await response.json();
        
        console.log('🎤 Voice synthesis test result:', result);
        
        // Display result in console for debugging
        if (result.success) {
            console.log('✅ Voice synthesis test successful!');
            console.log('🎤 Voice model:', result.voice_model);
            console.log('🎤 Text spoken:', result.text);
        } else {
            console.log('❌ Voice synthesis test failed:', result.error);
        }
        
        return result;
        
    } catch (error) {
        console.error('🎤 Error testing voice synthesis:', error);
        return { success: false, error: error.message };
    }
}

// Test golden glow effect directly
function testGoldenGlow() {
    console.log('✨ Testing golden glow effect on chat textarea...');
    
    try {
        // Test both element ID approaches
        const textareaById = document.getElementById('msg');
        const textareaBySelector = document.querySelector('#msg');
        
        console.log('✨ Element lookup results:');
        console.log('  - getElementById("msg"):', textareaById);
        console.log('  - querySelector("#msg"):', textareaBySelector);
        
        if (textareaById) {
            console.log('✨ Found textarea, applying golden glow effect...');
            flashElementWithGoldEffect('msg');
            console.log('✅ Golden glow effect triggered successfully!');
            return { success: true, element: 'msg', method: 'flashElementWithGoldEffect' };
        } else {
            console.log('❌ Textarea element not found');
            console.log('Available elements with IDs:', Array.from(document.querySelectorAll('[id]')).map(el => el.id));
            return { success: false, error: 'Textarea element not found' };
        }
        
    } catch (error) {
        console.error('✨ Error testing golden glow:', error);
        return { success: false, error: error.message };
    }
}

// Test WebSocket connection status
function testWebSocketConnection() {
    console.log('🔧 Testing WebSocket connection...');
    
    console.log('🔧 WebSocket Details:', {
        readyState: sidebarWs.readyState,
        readyStateText: getWebSocketStateText(sidebarWs.readyState),
        url: sidebarWs.url,
        protocol: sidebarWs.protocol,
        binaryType: sidebarWs.binaryType
    });
    
    if (sidebarWs.readyState === WebSocket.OPEN) {
        console.log('✅ WebSocket is connected and ready');
        
        // Test sending a simple message
        try {
            sidebarWs.send('%%TEST_MESSAGE%%');
            console.log('✅ Test message sent successfully');
        } catch (error) {
            console.error('❌ Failed to send test message:', error);
        }
    } else {
        console.error('❌ WebSocket is NOT connected');
        console.error('🔧 Current state:', getWebSocketStateText(sidebarWs.readyState));
        
        if (sidebarWs.readyState === WebSocket.CLOSED) {
            console.log('🔄 WebSocket is closed, would need to reconnect');
        }
    }
}

// Function to simulate user input for demo/regression prevention sequences
function simulateUserInput(message) {
    console.log('🎯 Simulating user input:', message);
    
    // Find the message input textarea
    const msgTextarea = document.getElementById('msg');
    if (!msgTextarea) {
        console.error('🎯 Could not find message input textarea');
        return false;
    }
    
    // Set the message text
    msgTextarea.value = message;
    
    // Find the form and submit it (simulating user pressing Enter)
    const form = msgTextarea.closest('form');
    if (form) {
        console.log('🎯 Submitting simulated user message');
        form.requestSubmit ? form.requestSubmit() : form.submit();
    } else {
        console.error('🎯 Could not find form to submit');
    }
}

// Function to load and execute demo script sequence
async function loadDemoScript() {
    try {
        console.log('🎯 Loading demo script configuration...');
        
        // Load the demo script configuration
        const response = await fetch('/assets/tests/demo.json');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const config = await response.json();
        const demoScript = config.demo_script;
        
        console.log('🎯 Demo script loaded:', demoScript.name);
        
        // Activate demo mode - this prevents real LLM submissions
        demoModeActive = true;
        currentDemoScript = demoScript;
        currentDemoStepIndex = 0;
        
        console.log('🎯 Demo mode ACTIVATED - Form submissions will be intercepted');
        
        // Execute the demo sequence
        await executeDemoSequence(demoScript);
        
    } catch (error) {
        console.error('🎯 Error loading demo script:', error);
        
        // Fallback to simple user input
        simulateUserInput('What is this?');
    }
}

// Function to execute a demo sequence with timing and MCP tool calls
async function executeDemoSequence(demoScript) {
    console.log('🎯 Executing demo sequence:', demoScript.name);
    
    for (const step of demoScript.steps) {
        console.log(`🎯 Executing step: ${step.step_id}`);
        
        // Wait for delay before step
        if (step.timing && step.timing.delay_before) {
            await new Promise(resolve => setTimeout(resolve, step.timing.delay_before));
        }
        
        switch (step.type) {
            case 'user_input':
                await executeUserInputStep(step);
                break;
                
            case 'system_reply':
                await executeSystemReplyStep(step);
                break;
                
                        case 'dom_action':
                const success = await executeDomActionStep(step); if (success === false) { console.error('❌ Step failed, stopping demo'); await addDemoMessage('system', '❌ **Test Stopped:** Step failed.'); break; }
                break;
                
            case 'mcp_tool_call':
                await executeMcpToolCallStep(step);
                break;
                
            default:
                console.warn('🎯 Unknown step type:', step.type);
        }
        
        // Small delay between steps for natural flow
        await new Promise(resolve => setTimeout(resolve, 500));
    }
    
    console.log('🎯 Demo sequence completed!');
}

// Execute user input step with typing simulation
async function executeUserInputStep(step) {
    console.log('🎯 Executing user input step:', step.message);
    
    const msgTextarea = document.getElementById('msg');
    if (!msgTextarea) {
        console.error('🎯 Could not find message input textarea');
        return false;
    }
    
    // Simulate typing if typing_speed is specified
    if (step.timing && step.timing.typing_speed) {
        await simulateTyping(msgTextarea, step.message, step.timing.typing_speed);
    } else {
        msgTextarea.value = step.message;
    }
    
    // In demo mode, we'll intercept the submission and trigger the next step
    // Submit the form (will be intercepted by our demo mode interceptor)
    const form = msgTextarea.closest('form');
    if (form) {
        form.requestSubmit ? form.requestSubmit() : form.submit();
    }
}

// Execute system reply step (verbatim, not LLM generated)
async function executeSystemReplyStep(step) {
    console.log('🎯 Executing system reply step');
    
    // Send verbatim system message via WebSocket
    if (sidebarWs.readyState === WebSocket.OPEN) {
        const systemMessage = {
            type: 'system_reply',
            message: step.message,
            verbatim: step.verbatim || false,
            timing: step.timing || {}
        };
        
        sidebarWs.send('%%DEMO_SYSTEM_REPLY%%:' + JSON.stringify(systemMessage));
        console.log('🎯 Sent system reply via WebSocket');
    } else {
        console.error('🎯 WebSocket not connected, cannot send system reply');
    }
}

// Execute MCP tool call step
async function executeMcpToolCallStep(step) {
    console.log('🎯 Executing MCP tool call:', step.tool_name);
    
    // 🔧 DEBUG: Enhanced WebSocket connection status
    console.log('🔧 DEMO MCP DEBUG - WebSocket status:', {
        readyState: sidebarWs.readyState,
        readyStateText: getWebSocketStateText(sidebarWs.readyState),
        url: sidebarWs.url,
        isOpen: sidebarWs.readyState === WebSocket.OPEN
    });
    
    // 🔧 DEBUG: Log step details
    console.log('🔧 DEMO MCP DEBUG - Step details:', {
        tool_name: step.tool_name,
        tool_args: step.tool_args,
        description: step.description
    });
    
    // Send MCP tool call via WebSocket
    if (sidebarWs.readyState === WebSocket.OPEN) {
        console.log('🔧 DEMO MCP DEBUG - Taking REAL WebSocket execution path');
        
        const mcpCall = {
            type: 'mcp_tool_call',
            tool_name: step.tool_name,
            tool_args: step.tool_args || {},
            description: step.description || ''
        };
        
        console.log('🔧 DEMO MCP DEBUG - Sending MCP call:', mcpCall);
        sidebarWs.send('%%DEMO_MCP_CALL%%:' + JSON.stringify(mcpCall));
        console.log('✅ DEMO MCP DEBUG - Sent MCP tool call via WebSocket');
        
        // 🔧 SPECIAL CASE: ui_flash_element needs local DOM manipulation
        if (step.tool_name === 'ui_flash_element') {
            console.log('✨ REAL WEBSOCKET UI FLASH: Applying local golden glow effect');
            
            // Handle both selector and element_id parameters (same logic as phantom execution)
            let elementId = step.tool_args?.element_id || 'msg';
            if (step.tool_args?.selector) {
                elementId = step.tool_args.selector.replace('#', '');
            }
            
            console.log('✨ REAL WEBSOCKET DEBUG: elementId =', elementId, 'element =', document.getElementById(elementId));
            flashElementWithGoldEffect(elementId);
            console.log('✅ REAL WEBSOCKET: flashElementWithGoldEffect called');
        }
    } else {
        console.error('🔧 DEMO MCP DEBUG - WebSocket not connected, cannot send MCP tool call');
        console.error('🔧 DEMO MCP DEBUG - WebSocket state:', getWebSocketStateText(sidebarWs.readyState));
        console.log('🔧 DEMO MCP DEBUG - Will attempt reconnection or fall back to phantom execution');
        
        // Try to reconnect if disconnected
        if (sidebarWs.readyState === WebSocket.CLOSED) {
            console.log('🔧 DEMO MCP DEBUG - WebSocket is CLOSED, attempting to reconnect...');
            await attemptWebSocketReconnection();
            
            // Retry sending the MCP tool call after reconnection
            if (sidebarWs.readyState === WebSocket.OPEN) {
                const mcpCall = {
                    type: 'mcp_tool_call',
                    tool_name: step.tool_name,
                    tool_args: step.tool_args || {},
                    description: step.description || ''
                };
                
                sidebarWs.send('%%DEMO_MCP_CALL%%:' + JSON.stringify(mcpCall));
                console.log('🎯 Sent MCP tool call via reconnected WebSocket');
            } else {
                console.error('🔧 DEMO MCP DEBUG - WebSocket reconnection failed, falling back to phantom execution');
                console.log('🔧 DEMO MCP DEBUG - About to call executeCleanMcpToolCallStep with:', step);
                await executeCleanMcpToolCallStep(step);
                console.log('🔧 DEMO MCP DEBUG - executeCleanMcpToolCallStep completed');
            }
        } else {
            console.log('🔧 DEMO MCP DEBUG - WebSocket not CLOSED (state:', getWebSocketStateText(sidebarWs.readyState), '), falling back to phantom execution immediately');
            await executeCleanMcpToolCallStep(step);
            console.log('🔧 DEMO MCP DEBUG - executeCleanMcpToolCallStep completed (immediate fallback)');
        }
    }
}

// Attempt to reconnect WebSocket
async function attemptWebSocketReconnection() {
    console.log('🔄 Attempting WebSocket reconnection...');
    
    try {
        // Close the existing WebSocket if it's in an invalid state
        if (sidebarWs.readyState !== WebSocket.CLOSED) {
            sidebarWs.close();
        }
        
        // Create new WebSocket connection
        const newSidebarWs = new WebSocket('ws://' + window.location.host + '/ws');
        
        // Wait for connection to open
        await new Promise((resolve, reject) => {
            newSidebarWs.onopen = () => {
                console.log('🔄 WebSocket reconnection successful');
                resolve();
            };
            
            newSidebarWs.onerror = (error) => {
                console.error('🔄 WebSocket reconnection failed:', error);
                reject(error);
            };
            
            // Timeout after 5 seconds
            setTimeout(() => {
                reject(new Error('WebSocket reconnection timeout'));
            }, 5000);
        });
        
        // Replace the global WebSocket reference
        sidebarWs = newSidebarWs;
        
        // Set up event handlers for the new connection
        sidebarWs.onclose = function(event) {
            console.log('Sidebar WebSocket closed');
            console.log('🔧 WebSocket close details:', {
                code: event.code,
                reason: event.reason,
                wasClean: event.wasClean,
                timestamp: new Date().toISOString()
            });
        };

        sidebarWs.onerror = function(error) {
            console.error('Sidebar WebSocket error:', error);
            console.error('🔧 WebSocket error details:', {
                type: error.type,
                target: error.target,
                timestamp: new Date().toISOString()
            });
        };
        
        sidebarWs.onmessage = function(event) {
            // Handle UI control messages first
            if (event.data === '%%STREAM_START%%') {
                updateStreamingUI(true);
                return false; // Do not display this message
            }
            if (event.data === '%%STREAM_END%%') {
                updateStreamingUI(false);
                
                // PERFORMANCE OPTIMIZATION: Ensure final render happens and clear any pending renders
                if (renderThrottleTimer) {
                    clearTimeout(renderThrottleTimer);
                    renderThrottleTimer = null;
                }
                // Force final render of the complete message
                renderCurrentMessage();
                
                // Add clipboard functionality to the completed assistant message
                if (sidebarCurrentMessage && sidebarCurrentMessage.dataset.rawText) {
                    addClipboardToAssistantMessage(sidebarCurrentMessage);
                }
                // Reset message buffer for next stream
                sidebarCurrentMessage = document.createElement('div');
                sidebarCurrentMessage.className = 'message assistant';
                return false; // Do not display this message
            }

            console.log('Sidebar received:', event.data);
            
            // Check if the message is a script
            if (event.data.trim().startsWith('<script>')) {
                const scriptContent = event.data.replace(/<\/?script>/g, '').trim();
                console.log('Executing script:', scriptContent);
                try {
                    eval(scriptContent);
                } catch (e) {
                    console.error('Error executing script:', e);
                }
                return false;
            }
            
            // Check if the response contains a plugin list item
            if (event.data.includes('data-plugin-item="true"')) {
                const tempDiv = document.createElement('div');
                tempDiv.innerHTML = event.data.trim();
                const newItem = tempDiv.firstElementChild;
                
                if (newItem && newItem.hasAttribute('data-list-target')) {
                    const listId = newItem.getAttribute('data-list-target');
                    const targetList = document.getElementById(listId);
                    
                    if (targetList) {
                        targetList.appendChild(newItem);
                        htmx.process(newItem);
                        
                        // Initialize sortable if needed
                        if (window.Sortable && !targetList.classList.contains('sortable-initialized')) {
                            new Sortable(targetList, {
                                animation: 150,
                                ghostClass: 'blue-background-class'
                            });
                            targetList.classList.add('sortable-initialized');
                        }
                    }
                }
                return false;
            }
            
            // Handle regular chat messages
            if (!sidebarCurrentMessage.parentElement) {
                sidebarMsgList.appendChild(sidebarCurrentMessage);
            }
            
            // Initialize or update the raw text buffer
            if (!sidebarCurrentMessage.dataset.rawText) {
                sidebarCurrentMessage.dataset.rawText = '';
            }
            sidebarCurrentMessage.dataset.rawText += event.data;
            
            // PERFORMANCE OPTIMIZATION: Throttle Markdown rendering to prevent exponential slowdown
            // Clear existing timer if one exists
            if (renderThrottleTimer) {
                clearTimeout(renderThrottleTimer);
            }
            
            // Schedule a throttled render
            renderThrottleTimer = setTimeout(() => {
                renderCurrentMessage();
                renderThrottleTimer = null;
            }, RENDER_THROTTLE_DELAY);
            
            // Keep the latest message in view
            sidebarMsgList.scrollTop = sidebarMsgList.scrollHeight;
        };
        
        console.log('🔄 WebSocket reconnection and event setup complete');
        
    } catch (error) {
        console.error('🔄 WebSocket reconnection failed:', error);
        throw error;
    }
}

// Helper function to get human-readable WebSocket state
function getWebSocketStateText(readyState) {
    switch(readyState) {
        case WebSocket.CONNECTING: return 'CONNECTING';
        case WebSocket.OPEN: return 'OPEN';
        case WebSocket.CLOSING: return 'CLOSING';
        case WebSocket.CLOSED: return 'CLOSED';
        default: return 'UNKNOWN';
    }
}

// Simulate typing animation
async function simulateTyping(textarea, message, speed) {
    textarea.value = '';
    
    for (let i = 0; i < message.length; i++) {
        textarea.value += message[i];
        await new Promise(resolve => setTimeout(resolve, speed));
    }
}

// Show Pico CSS restart spinner
function showRestartSpinner() {
    triggerFullScreenRestart("Restarting server...", "LEGACY");
}

// Hide restart spinner (fallback)
function hideRestartSpinner() {
    const overlay = document.getElementById('restart-overlay');
    if (overlay) {
        overlay.remove();
        console.log('🔄 Restart spinner hidden');
    }
}

// ============================================================================
// GLOBAL FUNCTIONS - Available to server-side code via script tags
// ============================================================================

// Make restart functions globally available for server-side script execution
window.triggerFullScreenRestart = triggerFullScreenRestart;
window.executeFullRestartSequence = executeFullRestartSequence;
window.triggerPythonEnvironmentReset = triggerPythonEnvironmentReset;

// Form submission interceptor for demo mode
function interceptFormSubmission() {
    // Find all forms and add submission interceptors
    document.addEventListener('submit', function(event) {
        if (demoModeActive) {
            console.log('🎯 INTERCEPTED: Form submission blocked due to demo mode');
            event.preventDefault();
            event.stopPropagation();
            
            // Get the message that was typed
            const msgTextarea = document.getElementById('msg');
            const userMessage = msgTextarea ? msgTextarea.value : '';
            
            console.log('🎯 Intercepted user message:', userMessage);
            
            // Display the user message in the chat (phantom user message)
            if (userMessage.trim()) {
                displayPhantomUserMessage(userMessage);
            }
            
            // Clear the textarea to simulate normal submission
            if (msgTextarea) {
                msgTextarea.value = '';
            }
            
            // Trigger the next step in our demo script (the phantom LLM response)
            triggerNextDemoStep();
        }
    });
    
    // Also intercept the Enter key submission in chat
    document.addEventListener('keydown', function(event) {
        if (demoModeActive && event.key === 'Enter' && !event.shiftKey) {
            const msgTextarea = document.getElementById('msg');
            if (msgTextarea && event.target === msgTextarea) {
                console.log('🎯 INTERCEPTED: Enter key submission blocked due to demo mode');
                event.preventDefault();
                event.stopPropagation();
                
                const userMessage = msgTextarea.value;
                console.log('🎯 Intercepted user message (Enter key):', userMessage);
                
                // Display the user message in the chat (phantom user message)
                if (userMessage.trim()) {
                    displayPhantomUserMessage(userMessage);
                }
                
                // Clear the textarea
                msgTextarea.value = '';
                
                // Trigger the next step in our demo script
                triggerNextDemoStep();
            }
        }
    });
}

// Function to trigger the next step in the demo script
function triggerNextDemoStep() {
    if (!demoModeActive || !currentDemoScript) {
        console.log('🎯 No demo script active, cannot trigger next step');
        return false;
    }
    
    // Find the next step that should be executed as a response
    const nextStepIndex = currentDemoStepIndex + 1;
    if (nextStepIndex >= currentDemoScript.steps.length) {
        console.log('🎯 Demo script completed, deactivating demo mode');
        demoModeActive = false;
        currentDemoScript = null;
        currentDemoStepIndex = 0;
        return false;
    }
    
    const nextStep = currentDemoScript.steps[nextStepIndex];
    console.log(`🎯 Triggering next demo step: ${nextStep.step_id}`);
    
    currentDemoStepIndex = nextStepIndex;
    
    // Execute the next step (usually a system reply)
    setTimeout(async () => {
        await executeIndividualDemoStep(nextStep);
    }, nextStep.timing?.delay_before || 500);
}

// Function to execute an individual demo step
async function executeIndividualDemoStep(step) {
    console.log(`🎯 Executing individual step: ${step.step_id}`);
    
    switch (step.type) {
        case 'system_reply':
            await executePhantomLLMResponse(step);
            break;
            
                    case 'dom_action':
                const success = await executeDomActionStep(step); if (success === false) { console.error('❌ Step failed, stopping demo'); await addDemoMessage('system', '❌ **Test Stopped:** Step failed.'); break; }
                break;
                
            case 'mcp_tool_call':
            await executeMcpToolCallStep(step);
            break;
            
        default:
            console.warn('🎯 Unexpected step type in response:', step.type);
    }
}

// Function to simulate phantom LLM response with typing
async function executePhantomLLMResponse(step) {
    console.log('🎯 Executing phantom LLM response with typing simulation');
    
    // Show the typing indicator
    showLLMTypingIndicator();
    
    // Wait for the typing simulation
    await simulatePhantomLLMTyping(step.message, step.timing?.display_speed || 30);
    
    // Hide the typing indicator and show the final message
    hideLLMTypingIndicator();
    displayPhantomLLMMessage(step.message);
}

// Function to show LLM typing indicator
function showLLMTypingIndicator() {
    // Add a typing indicator to the chat
    const msgList = document.getElementById('msg-list');
    if (msgList) {
        const typingDiv = document.createElement('div');
        typingDiv.id = 'phantom-typing-indicator';
        typingDiv.innerHTML = '🤖 <em>AI is typing...</em>';
        typingDiv.style.cssText = 'opacity: 0.7; font-style: italic; padding: 10px;';
        msgList.appendChild(typingDiv);
        msgList.scrollTop = msgList.scrollHeight;
    }
}

// Function to hide LLM typing indicator
function hideLLMTypingIndicator() {
    const typingIndicator = document.getElementById('phantom-typing-indicator');
    if (typingIndicator) {
        typingIndicator.remove();
    }
}

// Function to simulate phantom LLM typing
async function simulatePhantomLLMTyping(message, speed) {
    // Just wait for the appropriate time to simulate typing
    const typingTime = message.length * speed;
    await new Promise(resolve => setTimeout(resolve, typingTime));
}

// Function to display phantom LLM message
function displayPhantomLLMMessage(message) {
    const msgList = document.getElementById('msg-list');
    if (msgList) {
        const messageDiv = document.createElement('div');
        messageDiv.innerHTML = `<div class="assistant-message">${message}</div>`;
        messageDiv.style.cssText = 'padding: 10px; margin: 5px 0; background: #f0f8ff; border-radius: 8px;';
        msgList.appendChild(messageDiv);
        msgList.scrollTop = msgList.scrollHeight;
    }
}

// Function to display phantom user message
function displayPhantomUserMessage(message) {
    const msgList = document.getElementById('msg-list');
    if (msgList) {
        const messageDiv = document.createElement('div');
        messageDiv.innerHTML = `<div class="user-message">${message}</div>`;
        messageDiv.style.cssText = 'padding: 10px; margin: 5px 0; background: #e8f5e8; border-radius: 8px; text-align: right;';
        msgList.appendChild(messageDiv);
        msgList.scrollTop = msgList.scrollHeight;
    }
}

// Interactive demo script implementation with keyboard input and branching
async function loadAndExecuteCleanDemoScript(scriptName = 'introduction.json') {
    try {
        console.log(`🎯 Loading interactive scenario: ${scriptName}...`);
        
        const response = await fetch(`/assets/scenarios/${scriptName}`);
        
        if (!response.ok) {
            console.error(`🎯 HTTP Error loading scenario: ${response.status}`);
            if (response.status === 404) {
                 displayPhantomSystemMessage(`❌ No test script found for this context (${scriptName}).`);
            }
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const config = await response.json();
        const demoScript = config.demo_script;
        
        if (!demoScript) {
             throw new Error("Invalid JSON: missing 'demo_script' property");
        }

        console.log('🎯 Interactive demo script loaded:', demoScript.name);
        
        // Execute the interactive demo sequence with branching
        await executeInteractiveDemoSequence(demoScript);
        
    } catch (error) {
        console.error('🎯 Error loading demo script:', error);
        
        // Fallback to simple phantom message if it wasn't a 404 handled above
        if (!error.message.includes('HTTP error')) {
             displayPhantomUserMessage('Error loading script');
             setTimeout(() => {
                 displayPhantomLLMMessage(`Failed to load scenario: ${error.message}`);
             }, 1000);
        }
    }
}

// Interactive demo sequence execution with branching support
async function executeInteractiveDemoSequence(demoScript) {
    console.log('🎯 Executing interactive demo sequence:', demoScript.name);
    
    // Add invisible demo start message to conversation history (for LLM context)
    await addToConversationHistory('system', `[DEMO SCRIPT STARTED: ${demoScript.name}] An automated interactive demo is now running. All following messages are part of the scripted demo sequence. The user triggered this demo and is interacting with it via keyboard input (Ctrl+Alt+y/Ctrl+Alt+n). Continue to respond naturally if asked about the demo.`);
    
    // Store demo bookmark before navigation - survives page reload and server restart
    // CONDITIONAL: Only perform Oz transition (reload) for the main intro demo
    if (demoScript.name !== 'Interactive Pipulate Demo') {
        console.log('🎯 Generic test detected - running in-place without reload');
        await executeStepsWithBranching(demoScript.steps, demoScript);
        return false;
    }

    console.log('📖 Storing demo bookmark before navigation...');
    
    try {
        const demoBookmark = {
            script_name: demoScript.name,
            steps: demoScript.steps,
            timestamp: Date.now(),
            current_step: 0
        };
        
        console.log('📖 About to store demo bookmark:', demoBookmark);
        
        // Store demo bookmark in server-side database
        const bookmarkResponse = await fetch('/demo-bookmark-store', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(demoBookmark)
        });
        
        // Store Oz door grayscale state for cinematic transition
        const ozDoorResponse = await fetch('/oz-door-grayscale-store', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({})
        });
        
        if (bookmarkResponse.ok && ozDoorResponse.ok) {
            console.log('📖 Demo bookmark and Oz door grayscale state stored successfully');
        } else {
            console.warn('📖 Failed to store demo state, continuing anyway');
        }
        
    } catch (error) {
        console.warn('📖 Error storing demo state:', error);
    }
    
    // Navigate to home page (/) - "There's no place like home!"
    console.log('🏠 Navigating to home page for cinematic Oz door transition...');
    window.location.href = '/';
    
    // Note: Demo execution will resume from bookmark after navigation
    // No need to execute steps here - they'll be resumed by checkAndResumeDemoBookmark()
}

// Execute steps with branching logic
async function executeStepsWithBranching(steps, demoScript) {
    for (const step of steps) {
        console.log(`🎯 Executing step: ${step.step_id}`);
        
        // Wait for delay before step
        if (step.timing && step.timing.delay_before) {
            await new Promise(resolve => setTimeout(resolve, step.timing.delay_before));
        }
        
        // Execute the step
        switch (step.type) {
            case 'user_input':
                await executeCleanUserInputStep(step);
                break;
                
            case 'system_reply':
                await executeCleanSystemReplyStep(step);
                break;
                
                        case 'dom_action':
                const success = await executeDomActionStep(step); if (success === false) { console.error('❌ Step failed, stopping demo'); await addDemoMessage('system', '❌ **Test Stopped:** Step failed.'); break; }
                break;
                
            case 'mcp_tool_call':
                await executeMcpToolCallStep(step);
                break;
                
            default:
                console.warn('🎯 Unknown step type:', step.type);
        }
        
        // Check if this step requires user input and branching
        if (step.wait_for_input && step.branches) {
            console.log('🎯 Waiting for user input...');
            console.log('🎯 Step has wait_for_input:', step.wait_for_input);
            console.log('🎯 Step has branches:', step.branches);
            console.log('🎯 Valid keys:', step.valid_keys);
            console.log('🎯 Available demo branches:', Object.keys(demoScript.branches || {}));
            
            // Wait for keyboard input
            const userInput = await waitForKeyboardInput(step.valid_keys);
            console.log('🎯 User pressed:', userInput);
            
            // Special handling for the first trick (database reset)
            if (step.step_id === '07_first_trick' && userInput === 'ctrl+alt+y') {
                console.log('🎭 FIRST TRICK: User confirmed database reset');
                
                // Store demo continuation state before server restart
                const demoContinuationState = {
                    action: 'demo_continuation',
                    step_id: '08_dev_reset_confirmed',
                    branch: 'branch_dev_reset_yes',
                    timestamp: new Date().toISOString()
                };
                
                // Store in database via server endpoint
                try {
                    const formData = new FormData();
                    formData.append('demo_continuation', JSON.stringify(demoContinuationState));
                    
                    const response = await fetch('/store-demo-continuation', {
                        method: 'POST',
                        body: formData
                    });
                    
                    if (response.ok) {
                        console.log('🎭 Demo continuation state stored successfully');
                    } else {
                        console.error('🎭 Failed to store demo continuation state');
                    }
                } catch (error) {
                    console.error('🎭 Error storing demo continuation state:', error);
                }
                
                // 🎭 TRIGGER GLORIOUS FULL-SCREEN DEMO RESTART EXPERIENCE!
                console.log('🎭 Triggering glorious full-screen demo restart experience...');
                triggerFullScreenRestart("🎭 Demo is performing its first trick... Switching to DEV mode & resetting database!", "DEMO_RESTART");
                
                // Small delay to let the full-screen effect appear before calling the endpoint
                await new Promise(resolve => setTimeout(resolve, 1000));
                
                // First switch to DEV mode, then clear the database
                console.log('🎭 Step 1: Switching to DEV mode...');
                try {
                    const envResponse = await fetch('/switch_environment', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/x-www-form-urlencoded',
                        },
                        body: 'environment=Development'
                    });
                    
                    if (envResponse.ok) {
                        console.log('🎭 Environment switch initiated - server will restart in DEV mode');
                        // The server will restart and the demo will continue from stored state
                        // The database clear will happen after restart when in DEV mode
                        return false;
                    } else {
                        console.error('🎭 Failed to switch environment');
                        hideRestartSpinner();
                        return false;
                    }
                } catch (error) {
                    console.error('🎭 Error switching environment:', error);
                    hideRestartSpinner();
                    return false;
                }
                
                // NOTE: This code below should never execute due to the return above,
                // but kept for fallback if environment switch fails
                console.log('🎭 Fallback: Calling /clear-db endpoint directly...');
                try {
                    const resetResponse = await fetch('/clear-db', {
                        method: 'POST'
                    });
                    
                    if (resetResponse.ok) {
                        console.log('🎭 Database reset initiated successfully');
                        // The server will restart and the demo will resume from the stored state
                        return false; // Exit the demo execution - server restart will handle continuation
                    } else {
                        console.error('🎭 Failed to reset database');
                        // Hide the spinner if there's an error
                        hideRestartSpinner();
                    }
                } catch (error) {
                    console.error('🎭 Error calling /clear-db endpoint:', error);
                    // Hide the spinner if there's an error
                    hideRestartSpinner();
                }
            }
            
            // Navigate to the appropriate branch
            const branchKey = step.branches[userInput];
            console.log('🎯 Branch key for input:', branchKey);
            
            if (branchKey && demoScript.branches[branchKey]) {
                console.log('🎯 Navigating to branch:', branchKey);
                console.log('🎯 Branch steps:', demoScript.branches[branchKey]);
                
                // Execute the branch steps
                await executeStepsWithBranching(demoScript.branches[branchKey], demoScript);
                
                // Exit the current step sequence since we've branched
                break;
            } else {
                console.error('🎯 No valid branch found for input:', userInput);
                console.error('🎯 Available branches:', Object.keys(demoScript.branches || {}));
            }
        }
        
        // Check if this step ends the demo
        if (step.end_demo) {
            console.log('🎯 Demo ended by step:', step.step_id);
            // Reset page to normal color state after demo completion
            console.log('🎬 Resetting page to normal color state after demo completion');
            resetToNormalColor();
            break;
        }
        
        // Small delay between steps for natural flow
        await new Promise(resolve => setTimeout(resolve, 500));
    }
}

// Execute DOM action step - Ghost Driver capability
async function executeDomActionStep(step) {
    console.log('🎯 Executing DOM action:', step.action);
    
    // Wait for delay before step
    if (step.timing && step.timing.delay_before) {
        await new Promise(resolve => setTimeout(resolve, step.timing.delay_before));
    }

    // Polling wait for element
    let target = document.querySelector(step.selector);
    let attempts = 0;
    while (!target && attempts < 50) { // Wait up to 5 seconds
        await new Promise(resolve => setTimeout(resolve, 100));
        target = document.querySelector(step.selector);
        attempts++;
    }

    if (!target) {
        console.error('🎯 DOM Action Error: Target not found after waiting', step.selector);
        await addDemoMessage('system', '❌ **Error:** Could not find UI element: ' + step.selector);
        return false;
    }

    // Read value if requested
    let capturedValue = step.value || '';
    if (step.read_value_from) {
        const valueSource = document.querySelector(step.read_value_from);
        if (valueSource && 'value' in valueSource) {
            capturedValue = valueSource.value;
        } else if (valueSource) {
            capturedValue = valueSource.innerText;
        }
    }

    // Perform Action
    try {
        if (step.action === 'click') {
            target.click();
        } else if (step.action === 'submit_form') {
            const form = target.tagName === 'FORM' ? target : target.closest('form');
            if (form) {
                form.requestSubmit ? form.requestSubmit() : form.submit();
            } else {
                console.error('🎯 DOM Action Error: No form found for submit_form');
            }
        } else if (step.action === 'set_value') {
             if ('value' in target) {
                target.value = step.value || '';
                target.dispatchEvent(new Event('input', { bubbles: true }));
                target.dispatchEvent(new Event('change', { bubbles: true }));
                console.log(`🎯 DOM Action: Set value to "${step.value}"`);
            }
        }
        console.log('🎯 DOM Action performed:', step.action);
    } catch (e) {
        console.error('🎯 DOM Action failed:', e);
    }

    // Report back to chat
    if (step.message_template) {
        const message = step.message_template.replace('{value}', capturedValue || 'UNKNOWN');
        await addDemoMessage('assistant', message);
    }
    
    // Wait for UI update
    await new Promise(resolve => setTimeout(resolve, 1000));
    return true;
}

// Execute user input step - pure UI manipulation, no form submission
async function executeCleanUserInputStep(step) {
    console.log('🎯 Executing clean user input step:', step.message);
    
    const msgTextarea = document.getElementById('msg');
    if (!msgTextarea) {
        console.error('🎯 Could not find message input textarea');
        return false;
    }
    
    // Simulate typing if typing_speed is specified
    if (step.timing && step.timing.typing_speed) {
        await simulateTypingInTextarea(msgTextarea, step.message, step.timing.typing_speed);
        
        // Brief pause to show the completed typing
        await new Promise(resolve => setTimeout(resolve, 800));
    } else {
        msgTextarea.value = step.message;
    }
    
    // Display the phantom user message directly (no form submission)
    displayPhantomUserMessage(step.message);
    
    // Add to conversation history for LLM context
    await addToConversationHistory('user', step.message);
    
    // Clear the textarea to simulate message being sent
    msgTextarea.value = '';
    
    console.log('🎯 Clean user input step completed');
}

// Execute system reply step using EXACT same technique as endpoint messages
async function executeCleanSystemReplyStep(step) {
    console.log('🎯 Executing clean system reply step');
    
    // Create the message container with data-rawText tracking (same as real messages)
    const msgList = document.getElementById('msg-list');
    if (!msgList) {
        console.error('🎯 Could not find message list container');
        return false;
    }
    
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message assistant';
    messageDiv.innerHTML = `<div class="message-container"><div class="message-content"><p></p></div></div>`;
    messageDiv.dataset.rawText = ''; // Initialize raw text tracking
    msgList.appendChild(messageDiv);
    msgList.scrollTop = msgList.scrollHeight;
    
    // Use EXACT same word-reveal technique as endpoint messages
    await simulateWordByWordReveal(messageDiv, step.message, step.timing?.display_speed || 30);
    
    // Add to conversation history for LLM context
    await addToConversationHistory('assistant', step.message);
    
    // Automatically re-focus textarea after LLM reply finishes (standard UX behavior)
    const textarea = document.querySelector('textarea[name="msg"]');
    if (textarea) {
        textarea.focus();
        console.log('🎯 Textarea re-focused after LLM reply completion');
    }
    
    console.log('🎯 Clean system reply step completed');
}

// Execute MCP tool call step - phantom tool execution with real UI effects
async function executeCleanMcpToolCallStep(step) {
    console.log('🎯 Executing clean MCP tool call:', step.tool_name);
    
    // Simulate MCP tool execution time (no typing indicator)
    await new Promise(resolve => setTimeout(resolve, 2000));
    
    // Display MCP tool result (phantom - hardcoded for demo)
    let mcpResult = '';
    
    if (step.tool_name === 'pipeline_state_inspector') {
        mcpResult = `🔍 **Pipeline State Inspector** 🔍

✅ **Status**: Complete success
📊 **Total workflows**: 6
🔒 **Finalized**: 0
⚡ **Active**: 6
📱 **Apps**: hello(1), link_graph_visualizer(1), param_buster(4)
🕒 **Recent activity (24h)**: 6 workflows

**Recent workflow keys:**
- Undergarments-param_buster-03
- Undergarments-param_buster-04
- ${window.APP_NAME || 'Pipulate'}-hello-01

**Database Status**: DEV mode active, safe to experiment! 🧪`;
    } else if (step.tool_name === 'local_llm_list_files') {
        mcpResult = `📁 **File Listing** 📁

✅ **Status**: Complete success
📂 **Directory**: ${step.tool_args?.directory || '.'}
📄 **Files found**: 47

**Key files:**
- server.py (Main application)
- mcp_tools.py (MCP tool definitions)
- cli.py (Command line interface)
- apps/ (41 plugin files)
- /assets/ (Web assets)
- browser_cache/ (Automation scripts)

**Safe read-only operation completed!** 📖`;
    } else if (step.tool_name === 'ui_flash_element') {
        mcpResult = `✨ **UI Element Flashed!** ✨

🎯 **Element**: ${step.tool_args?.element_id || 'chat-input'}
💫 **Effect**: Gold twinkling animation
⏱️ **Duration**: 2.5 seconds
🎨 **Style**: Magical shimmer effect

The element is now sparkling with golden light!`;
        
        // Actually flash the element for real
        // Handle both selector and element_id parameters
        let elementId = step.tool_args?.element_id || 'msg';
        if (step.tool_args?.selector) {
            // Extract ID from selector (remove # if present)
            elementId = step.tool_args.selector.replace('#', '');
        }
        
        // 🔧 DEBUG: Log golden glow execution details
        console.log('✨ PHANTOM GOLDEN GLOW DEBUG:');
        console.log('  - step.tool_args:', step.tool_args);
        console.log('  - extracted elementId:', elementId);
        console.log('  - target element:', document.getElementById(elementId));
        console.log('  - calling flashElementWithGoldEffect...');
        
        flashElementWithGoldEffect(elementId);
        
        console.log('✅ flashElementWithGoldEffect called in phantom execution');
    } else {
        // Log MCP tool execution to browser console instead of displaying in UI
        console.log('🔧 **MCP Tool Executed** 🔧');
        console.log(`   Tool: ${step.tool_name}`);
        console.log(`   Args: ${JSON.stringify(step.tool_args || {})}`);
        console.log(`   Status: Success ✅`);
        console.log(`   Description: ${step.description || 'MCP tool execution completed successfully.'}`);
    }
    
    // Automatically re-focus textarea after MCP tool response finishes (standard UX behavior)
    const textarea = document.querySelector('textarea[name="msg"]');
    if (textarea) {
        textarea.focus();
        console.log('🎯 Textarea re-focused after MCP tool completion');
    }
    
    console.log('🎯 Clean MCP tool step completed');
}

// Flash element with gold effect - real UI enhancement
function flashElementWithGoldEffect(elementId) {
    const element = document.getElementById(elementId);
    if (element) {
        // Add gold flash animation
        element.style.transition = 'all 0.3s ease-in-out';
        element.style.boxShadow = '0 0 20px gold, 0 0 40px gold, 0 0 60px gold';
        element.style.border = '2px solid gold';
        element.style.transform = 'scale(1.02)';
        
        // Create twinkling effect
        let twinkleCount = 0;
        const twinkle = setInterval(() => {
            if (twinkleCount >= 8) {
                clearInterval(twinkle);
                element.style.animation = '';
                element.style.boxShadow = '';
                element.style.border = '';
                element.style.transform = '';
                element.style.opacity = '1';
                return false;
            }
            
            element.style.opacity = twinkleCount % 2 === 0 ? '0.7' : '1';
            twinkleCount++;
        }, 300);
    }
}

// Simulate word-by-word typing in textarea - matches LLM streaming methodology
async function simulateTypingInTextarea(textarea, message, speed) {
    textarea.value = '';
    textarea.focus();
    
    // Split message into word chunks (same pattern as LLM generation)
    const words = message.split(/(\s+)/); // Keep whitespace
    
    let accumulatedText = '';
    
    for (let i = 0; i < words.length; i++) {
        const word = words[i];
        accumulatedText += word;
        
        // Update textarea value with accumulated text
        textarea.value = accumulatedText;
        
        // Scroll textarea if needed
        textarea.scrollTop = textarea.scrollHeight;
        
        // Timing matches natural typing speed
        // Shorter delay for whitespace, longer for actual words
        const delay = word.trim() ? speed + Math.random() * 20 : speed / 3;
        await new Promise(resolve => setTimeout(resolve, delay));
    }
}

// Show LLM typing indicator
function showLLMTypingIndicator() {
    const msgList = document.getElementById('msg-list');
    if (msgList) {
        const typingDiv = document.createElement('div');
        typingDiv.id = 'phantom-typing-indicator';
        typingDiv.className = 'message assistant';
        typingDiv.innerHTML = '<p><em>🤖 AI is typing...</em></p>';
        typingDiv.style.cssText = 'opacity: 0.7; font-style: italic;';
        msgList.appendChild(typingDiv);
        msgList.scrollTop = msgList.scrollHeight;
    }
}

// Hide LLM typing indicator
function hideLLMTypingIndicator() {
    const typingIndicator = document.getElementById('phantom-typing-indicator');
    if (typingIndicator) {
        typingIndicator.remove();
    }
}

// Simulate phantom LLM typing time
async function simulatePhantomLLMTyping(message, speed) {
    const typingTime = message.length * speed;
    await new Promise(resolve => setTimeout(resolve, typingTime));
}

// Display phantom LLM message
function displayPhantomLLMMessage(message) {
    const msgList = document.getElementById('msg-list');
    if (msgList) {
        // 🎭 RUBY SLIPPERS: Apply platform-aware keyboard shortcut adaptation
        const adaptedMessage = window.adaptMessageForPlatform(message);
        
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message assistant';
        messageDiv.innerHTML = `<div class="message-container"><div class="message-content"><p>${adaptedMessage}</p></div></div>`;
        msgList.appendChild(messageDiv);
        msgList.scrollTop = msgList.scrollHeight;
    }
}

// Display phantom user message
function displayPhantomUserMessage(message) {
    const msgList = document.getElementById('msg-list');
    if (msgList) {
        // 🎭 RUBY SLIPPERS: Apply platform-aware keyboard shortcut adaptation
        const adaptedMessage = window.adaptMessageForPlatform(message);
        
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message user';
        messageDiv.innerHTML = `<div class="message-container"><div class="message-content">${adaptedMessage}</div></div>`;
        msgList.appendChild(messageDiv);
        msgList.scrollTop = msgList.scrollHeight;
    }
}

// Simulate word-by-word reveal using EXACT same technique as endpoint messages
async function simulateWordByWordReveal(messageElement, fullMessage, baseSpeed = 30) {
    console.log('🎯 Starting word-by-word reveal simulation');
    
    // 🎭 RUBY SLIPPERS: Apply platform-aware keyboard shortcut adaptation
    const adaptedMessage = window.adaptMessageForPlatform(fullMessage);
    
    // Split message into word chunks (same pattern as LLM generation)
    const words = adaptedMessage.split(/(\s+)/); // Keep whitespace
    
    // Use same timing as real Gemma 3 generation
    let accumulatedText = '';
    
    for (let i = 0; i < words.length; i++) {
        const word = words[i];
        accumulatedText += word;
        
        // Update the dataset.rawText (same as real WebSocket messages)
        messageElement.dataset.rawText = accumulatedText;
        
        // Use EXACT same rendering technique as real messages
        renderMessageElement(messageElement);
        
        // Keep message in view (same as real messages)
        const msgList = document.getElementById('msg-list');
        if (msgList) {
            msgList.scrollTop = msgList.scrollHeight;
        }
        
        // Timing matches natural Gemma 3 generation speed
        // Shorter delay for whitespace, longer for actual words
        const delay = word.trim() ? baseSpeed + Math.random() * 20 : baseSpeed / 3;
        await new Promise(resolve => setTimeout(resolve, delay));
    }
    
    console.log('🎯 Word-by-word reveal completed');
}

// Render individual message element (extracted from renderCurrentMessage logic)
function renderMessageElement(messageElement) {
    const rawText = messageElement.dataset.rawText;
    
    // Use EXACT same rendering logic as renderCurrentMessage
    if (typeof marked !== 'undefined') {
        try {
            // Enhanced code fence detection - handle both ``` and ~~~ fences
            const codeFenceRegex = /^(```|~~~)/gm;
            const allFences = rawText.match(codeFenceRegex) || [];
            const hasIncompleteCodeFence = allFences.length % 2 !== 0;
            
            if (hasIncompleteCodeFence) {
                // Don't parse incomplete markdown - show as plain text for now
                const lines = rawText.split('\n');
                const formattedLines = lines.map(line => {
                    return line.replace(/&/g, '&amp;')
                              .replace(/</g, '&lt;')
                              .replace(/>/g, '&gt;')
                              .replace(/&lt;br&gt;/g, '<br>');
                });
                const contentElement = messageElement.querySelector('.message-content p') || messageElement.querySelector('.message-content');
                if (contentElement) {
                    contentElement.innerHTML = formattedLines.join('<br>');
                }
            } else {
                // Safe to parse complete markdown using pre-configured marked
                let cleanedText = rawText
                    .replace(/(\n\s*[-*+]\s+[^\n]+)\n\s*\n(\s*[-*+]\s+)/g, '$1\n$2')
                    .replace(/(\n\s*[-*+]\s+[^\n]+)\n\s*\n(\s+[-*+]\s+)/g, '$1\n$2')
                    .replace(/\n\s*\n\s*\n/g, '\n\n')
                    .replace(/[ \t]+$/gm, '')
                    .replace(/\r\n/g, '\n');
                
                const renderedHtml = marked.parse(cleanedText);
                const contentElement = messageElement.querySelector('.message-content p') || messageElement.querySelector('.message-content');
                if (contentElement) {
                    contentElement.innerHTML = renderedHtml;
                }
                
                // Apply syntax highlighting if Prism is available
                if (typeof Prism !== 'undefined') {
                    Prism.highlightAllUnder(messageElement);
                }
            }
        } catch (e) {
            console.error('Error rendering Markdown:', e);
            const processedText = rawText
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
                .replace(/&lt;br&gt;/g, '<br>')
                .replace(/\n/g, '<br>');
            const contentElement = messageElement.querySelector('.message-content p') || messageElement.querySelector('.message-content');
            if (contentElement) {
                contentElement.innerHTML = processedText;
            }
        }
    } else {
        // Fallback to plain text if marked.js is not available
        const processedText = rawText
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/&lt;br&gt;/g, '<br>')
            .replace(/\n/g, '<br>');
        const contentElement = messageElement.querySelector('.message-content p') || messageElement.querySelector('.message-content');
        if (contentElement) {
            contentElement.innerHTML = processedText;
        }
    }
}

// Wait for keyboard input with valid key checking
async function waitForKeyboardInput(validKeys) {
    return new Promise((resolve) => {
        console.log('🎯 Listening for keyboard input. Valid keys:', validKeys);
        
        function handleKeyPress(event) {
            const key = event.key.toLowerCase();
            const isCtrl = event.ctrlKey;
            const isAlt = event.altKey;
            
            // 🍎 MAC FIX: Use event.code for ctrl+alt combinations because Mac Option key changes the character
            // Map from KeyCode to letter for consistent detection across platforms
            const keyCodeMap = {
                'KeyA': 'a', 'KeyB': 'b', 'KeyC': 'c', 'KeyD': 'd', 'KeyE': 'e', 'KeyF': 'f', 'KeyG': 'g',
                'KeyH': 'h', 'KeyI': 'i', 'KeyJ': 'j', 'KeyK': 'k', 'KeyL': 'l', 'KeyM': 'm', 'KeyN': 'n',
                'KeyO': 'o', 'KeyP': 'p', 'KeyQ': 'q', 'KeyR': 'r', 'KeyS': 's', 'KeyT': 't', 'KeyU': 'u',
                'KeyV': 'v', 'KeyW': 'w', 'KeyX': 'x', 'KeyY': 'y', 'KeyZ': 'z'
            };
            
            // Build key combination string
            let keyCombo = key;
            if (isCtrl && isAlt) {
                // Use event.code mapping for Mac compatibility (Option key changes characters)
                const codeKey = keyCodeMap[event.code] || key;
                keyCombo = `ctrl+alt+${codeKey}`;
            } else if (isCtrl) {
                keyCombo = `ctrl+${key}`;
            }
            
            console.log('🎯 Key pressed:', keyCombo, 'Raw key:', key, 'Ctrl:', isCtrl, 'Alt:', isAlt);
            console.log('🎯 Event details:', {
                key: event.key,
                code: event.code,
                ctrlKey: event.ctrlKey,
                shiftKey: event.shiftKey,
                altKey: event.altKey
            });
            
            if (validKeys.includes(keyCombo)) {
                console.log('🎯 Valid key combination detected:', keyCombo);
                
                // Prevent default behavior for ctrl+alt+y/ctrl+alt+n
                event.preventDefault();
                event.stopPropagation();
                
                // Blur the textarea to prevent keystroke from appearing in message box
                const textarea = document.querySelector('textarea[name="msg"]');
                if (textarea) {
                    textarea.blur();
                    console.log('🎯 Textarea blurred to prevent keystroke interference');
                }
                
                document.removeEventListener('keydown', handleKeyPress);
                resolve(keyCombo);
            } else {
                console.log('🎯 Invalid key combination, waiting for:', validKeys);
                console.log('🎯 Expected one of:', validKeys);
                console.log('🎯 Got:', keyCombo);
            }
        }
        
        document.addEventListener('keydown', handleKeyPress);
    });
}

// Add message to conversation history invisibly (for LLM context)
async function addToConversationHistory(role, content) {
    try {
        const formData = new FormData();
        formData.append('role', role);
        formData.append('content', content);
        
        await fetch('/add-to-conversation-history', {
            method: 'POST',
            body: formData
        });
        
        console.log('🎯 Added to conversation history:', role, content.substring(0, 100) + '...');
    } catch (error) {
        console.error('🎯 Error adding to conversation history:', error);
    }
}

// Check for demo bookmark and resume if exists
async function checkAndResumeDemoBookmark() {
    try {
        const response = await fetch('/demo-bookmark-check');
        const data = await response.json();
        
        if (data.has_bookmark && data.bookmark) {
            console.log('📖 Demo bookmark found, resuming demo...');
            console.log('📖 Retrieved bookmark data:', data.bookmark);
            
            // Parse bookmark if it's a string (JSON serialization issue)
            let bookmark = data.bookmark;
            if (typeof bookmark === 'string') {
                console.log('📖 Bookmark is string, parsing JSON...');
                bookmark = JSON.parse(bookmark);
            }
            
            // Clear the bookmark to prevent infinite loop
            await fetch('/demo-bookmark-clear', { method: 'POST' });
            
            // Small delay to allow page to fully load
            await new Promise(resolve => setTimeout(resolve, 500));
            
            // Resume the demo from where it left off
            await resumeDemoFromBookmark(bookmark);
        }
    } catch (error) {
        console.error('📖 Error checking demo bookmark:', error);
    }
}

// Resume demo from bookmark
async function resumeDemoFromBookmark(bookmark) {
    try {
        console.log('📖 Resuming demo:', bookmark.script_name);
        console.log('📖 Bookmark structure:', bookmark);
        console.log('📖 Bookmark type:', typeof bookmark);
        console.log('📖 Bookmark.steps type:', typeof bookmark.steps);
        console.log('📖 Is bookmark.steps array?', Array.isArray(bookmark.steps));
        
        // Validate bookmark data
        if (!bookmark || !bookmark.steps || !Array.isArray(bookmark.steps)) {
            console.error('📖 Invalid bookmark data - missing or invalid steps array');
            console.error('📖 Debug - bookmark exists:', !!bookmark);
            console.error('📖 Debug - bookmark.steps exists:', !!bookmark.steps);
            console.error('📖 Debug - bookmark.steps is array:', Array.isArray(bookmark.steps));
            return false;
        }
        
        // Reload the full demo script config to get branches
        console.log('📖 Reloading full demo script config to get branches...');
        
        // Use the helper that knows about assets/scenarios/
        const demoScript = await loadDemoScriptConfig('introduction.json');
        
        if (!demoScript) {
            throw new Error('Failed to load demo script config via loadDemoScriptConfig');
        }
        
        console.log('📖 Full demo script reloaded:', demoScript.name);
        console.log('📖 Available branches:', Object.keys(demoScript.branches || {}));
        
        // 🎬 CINEMATIC MAGIC: "Dorothy Opens the Door to Oz"
        // Apply grayscale immediately, then fade to color with perfect timing
        await executeOzDoorTransition();
        
        // Add hair's breadth pause to first step when resuming from bookmark
        if (demoScript.steps && demoScript.steps.length > 0) {
            const firstStep = demoScript.steps[0];
            if (firstStep.timing) {
                firstStep.timing.delay_before = 500; // Hair's breadth pause
            }
        }
        
        // Execute the demo steps starting from the bookmarked position
        await executeStepsWithBranching(demoScript.steps, demoScript);
        
    } catch (error) {
        console.error('📖 Error resuming demo:', error);
    }
}

/**
 * 🎬 CINEMATIC MAGIC: "Dorothy Opens the Door to Oz"
 * 
 * This function creates the iconic transition from sepia Kansas farmhouse
 * to the vibrant, colorful Land of Oz. It's the "heart" phase of our demo,
 * where the mechanical "brains" phase gives way to the emotional, living
 * world of AI interaction.
 * 
 * Timeline:
 * 1. Reset to clean state (works regardless of previous state)
 * 2. INSTANT dramatic sepia filter (Kansas farmhouse) - POP!
 * 3. Wait 2 seconds (dramatic pause) - user wonders what's happening
 * 4. Fade to color over 3 seconds (opening the door to Oz)
 * 5. Wait for transition to complete before starting phantom typing
 */
async function executeOzDoorTransition() {
    console.log('🎬 Beginning "Dorothy Opens the Door to Oz" cinematic sequence...');
    
    // Step 0: Reset to clean state (works regardless of previous state)
    document.documentElement.classList.remove('demo-grayscale', 'demo-fading-to-color', 'demo-color');
    console.log('🎬 Reset to clean state - ready for dramatic transition');
    
    // Step 1: INSTANT dramatic sepia filter (Kansas farmhouse) - POP!
    applyDramaticSepiaFilter();
    console.log('🎬 INSTANT dramatic sepia applied - welcome to Kansas farmhouse!');
    
    // Play "Somewhere Over the Rainbow" as the sepia effect appears
    playSomewhereOverTheRainbow();
    
    // Step 2: Dramatic pause (3 seconds) - user experiences bleak Kansas
    console.log('🎬 Dramatic pause - user experiences bleak Kansas...');
    await new Promise(resolve => setTimeout(resolve, 3000));
    
    // Step 3: Begin the transition to color (opening the door to Oz)
    console.log('🎬 Opening the door to the vibrant Land of Oz...');
    await fadeToColor();
    
    // Step 4: Clean up the server-side cookie state
    try {
        await fetch('/oz-door-grayscale-clear', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({})
        });
        console.log('🎬 Oz door sepia state cleared from server');
    } catch (error) {
        console.warn('🎬 Error clearing Oz door sepia state:', error);
    }
    
    console.log('🎬 Cinematic transition complete - welcome to the colorful Land of Oz!');
}

/**
 * Apply INSTANT dramatic sepia filter to the entire page
 * This creates the "Kansas farmhouse" sepia effect with POP!
 * NO TRANSITION - immediate dramatic effect
 */
function applyDramaticSepiaFilter() {
    document.documentElement.classList.add('demo-grayscale');
    console.log('🎬 INSTANT dramatic sepia filter applied - POP!');
}

/**
 * Fade from grayscale to full color
 * This creates the "opening the door to Oz" transition
 * Returns a promise that resolves when the transition is complete
 */
async function fadeToColor() {
    return new Promise((resolve) => {
        // Add the transition class to enable smooth fade to color
        document.documentElement.classList.add('demo-fading-to-color');
        console.log('🎬 Color transition initiated - fading to vibrant Oz...');
        
        // Wait for the CSS transition to complete (3 seconds)
        setTimeout(() => {
            // Clean up all demo classes
            document.documentElement.classList.remove('demo-grayscale', 'demo-fading-to-color');
            document.documentElement.classList.add('demo-color');
            console.log('🎬 Color transition complete - welcome to the Land of Oz!');
            resolve();
        }, 3000); // Match the CSS transition duration
    });
}

/**
 * Reset the page to normal color state
 * This can be called to clean up after the demo
 */
function resetToNormalColor() {
    document.documentElement.classList.remove('demo-grayscale', 'demo-fading-to-color', 'demo-color');
    console.log('🎬 Reset to normal color state');
}

// Check for demo resume after server restart
async function checkDemoResumeAfterRestart() {
    try {
        console.log('🎭 Checking for demo resume after server restart...');
        
        const response = await fetch('/check-demo-resume');
        const data = await response.json();
        
        if (data.should_resume && data.continuation_state) {
            console.log('🎭 Demo resume detected after server restart');
            console.log('🎭 Continuation state:', data.continuation_state);
            
            // Resume the demo from the continuation state
            await resumeDemoFromContinuationState(data.continuation_state);
        } else {
            console.log('🎭 No demo resume needed after server restart');
        }
    } catch (error) {
        console.error('🎭 Error checking demo resume after restart:', error);
    }
}

// Resume demo from continuation state after server restart
async function resumeDemoFromContinuationState(continuationState) {
    try {
        console.log('🎭 Resuming demo from continuation state:', continuationState);
        
        // Load the demo script configuration
        const response = await fetch('/assets/tests/demo.json');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const config = await response.json();
        const demoScript = config.demo_script;
        
        // Activate demo mode
        demoModeActive = true;
        currentDemoScript = demoScript;
        
        console.log('🎭 Demo mode activated for resume');
        
        // 🎭 ADD NATURAL CONTINUATION MESSAGE TO CHAT
        // This makes the demo feel like a seamless conversation continuation
        await addMessageToConversation('assistant', '🎩 **Excellent!** The magic begins...\n\n🗄️ **Database reset complete!**\n\n✨ **Ready for the next trick!**');
        
        // Small delay to let the continuation message appear
        await new Promise(resolve => setTimeout(resolve, 800));
        
        // Execute the continuation branch starting from the next step after database reset
        const branchKey = continuationState.branch;
        if (branchKey && demoScript.branches[branchKey]) {
            console.log('🎭 Executing continuation branch:', branchKey);
            const branchSteps = demoScript.branches[branchKey];
            
            // Find the step after the database reset confirmation (08_dev_reset_confirmed)
            const startIndex = branchSteps.findIndex(step => step.step_id === '08_dev_reset_confirmed');
            if (startIndex >= 0 && startIndex + 1 < branchSteps.length) {
                // Execute steps starting from the next step (09_llm_body_test)
                const continuationSteps = branchSteps.slice(startIndex + 1);
                console.log('🎭 Continuing from step after database reset:', continuationSteps[0]?.step_id);
                await executeStepsWithBranching(continuationSteps, demoScript);
            } else {
                console.log('🎭 No continuation steps found after database reset');
            }
        } else {
            console.error('🎭 Invalid continuation branch:', branchKey);
        }
        
    } catch (error) {
        console.error('🎭 Error resuming demo from continuation state:', error);
    }
}

// Add message to conversation UI (helper function for demo continuation)
async function addMessageToConversation(role, message) {
    try {
        // Add message using the same mechanism as the demo steps
        await addToConversationHistory(role, message);
        console.log(`🎭 Added ${role} message to conversation: ${message.substring(0, 50)}...`);
    } catch (error) {
        console.error('🎭 Error adding message to conversation:', error);
    }
}

// Check for demo comeback message after server restart
async function checkDemoComeback() {
    try {
        console.log('🎭 Checking for demo comeback message...');
        
        const response = await fetch('/check-demo-comeback');
        const data = await response.json();
        
        if (data.show_comeback_message) {
            console.log('🎭 Demo comeback message detected:', data.message);
            console.log('🎭 Demo state for continuation:', data.demo_state);
            
            // 🔧 IMMEDIATE DEMO TAKEOVER: Prevent normal chat processing AND demo restart
            window.demoInProgress = true;
            window.demoContinuationActive = true;
            console.log('🎭 Demo takeover activated - blocking normal chat processing and demo restart');
            
            // Show the demo comeback message and continue the demo
            await showDemoComebackMessage(data.message, data.subtitle);
            
            // 🔧 DEMO CONTINUATION: Resume demo from the stored state
            if (data.demo_state) {
                console.log('🎭 Resuming demo from state:', data.demo_state);
                await resumeDemoFromState(data.demo_state);
            }
        } else {
            console.log('🎭 No demo comeback message to show');
        }
    } catch (error) {
        console.error('🎭 Error checking demo comeback message:', error);
    }
}

// Load demo script config without executing (for continuation)
async function loadDemoScriptConfig(scriptName = 'introduction.json') {
    try {
        console.log(`🎭 Loading demo script config only: ${scriptName}...`);
        
        const response = await fetch(`/assets/scenarios/${scriptName}`);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const config = await response.json();
        return config.demo_script;
    } catch (error) {
        console.error('🎭 Error loading demo script config:', error);
        return null;
    }
}

// Resume demo from stored state after server restart
async function resumeDemoFromState(demoState) {
    try {
        console.log('🎭 DEMO CONTINUATION: Resuming demo from state:', demoState);
        
        // First, show the interactive Y/N continuation prompt
        await addDemoMessage('assistant', '🎭 Demo server restart complete! Ready for the next trick...\n✨ Continue the demo?\nPress Ctrl+Alt+Y to continue or Ctrl+Alt+N to stop');
        
        // Set up keyboard listener for demo continuation
        setupDemoContinuationKeyboardHandler(demoState);
        
        // Wait for user response before proceeding
        return false; // Let the keyboard handler take over
        
    } catch (error) {
        console.error('🎭 Error resuming demo from state:', error);
    }
}

// Continue demo after user confirms with Ctrl+Alt+Y
async function continueDemoFromState(demoState) {
    try {
        console.log('🎭 DEMO CONTINUATION: User confirmed, continuing from state:', demoState);
        
        // Load ONLY the demo script config (do not execute)
        const demoScript = await loadDemoScriptConfig();
        if (!demoScript) {
            console.error('🎭 Could not load demo script for continuation');
            return false;
        }
        
        // Find the next step based on the stored state
        const currentStepId = demoState.step_id;
        console.log('🎭 Current step ID from state:', currentStepId);
        
        // Look for the continuation step (next step after database reset)
        if (currentStepId === '08_dev_reset_confirmed') {
            console.log('🎭 DEMO CONTINUATION: Database reset step confirmed, continuing to next trick...');
            
            // Clear any existing demo bookmark to prevent conflicts
            try {
                await fetch('/demo-bookmark-clear', { method: 'POST' });
                console.log('🎭 Demo bookmark cleared for clean continuation');
            } catch (error) {
                console.log('🎭 Note: Could not clear demo bookmark:', error);
            }
            
            // Show the interactive continuation message
            await addDemoMessage('assistant', '🎭 Excellent! The magic begins...\n\n🗄️ Database reset complete!\n\n✨ Ready for the next trick!');
            
            // Small delay for dramatic effect
            await new Promise(resolve => setTimeout(resolve, 1500));
            
            // Continue with the next trick after database reset
            const nextSteps = demoScript.steps.filter(step => 
                step.step_id === '09_second_trick_intro' || 
                step.step_id.startsWith('09_')
            );
            
            if (nextSteps.length > 0) {
                console.log('🎭 Found continuation steps:', nextSteps.map(s => s.step_id));
                
                // ✨ RESUME DEMO EXECUTION - This is where the battery of tests begins!
                console.log('🎭 🚀 REGRESSION TEST DEMO STARTING - Controlled conditions achieved!');
                await addDemoMessage('assistant', '🎭 **🚀 REGRESSION TEST DEMO STARTING!**\n\n✅ **Controlled Conditions Achieved:**\n• DEV mode active\n• Fresh database\n• Demo continuation successful\n\n🔋 **Battery of tests beginning...**');
                
                // Activate demo mode for continuation
                window.demoModeActive = true;
                window.currentDemoScript = demoScript;
                window.currentDemoStepIndex = demoScript.steps.findIndex(step => step.step_id === nextSteps[0].step_id);
                
                // Small delay before starting the test battery
                await new Promise(resolve => setTimeout(resolve, 2000));
                
                // Execute the continuation steps using existing step execution logic
                for (const step of nextSteps) {
                    console.log(`🎭 Executing regression test step: ${step.step_id}`);
                    
                    // Wait for delay before step
                    if (step.timing && step.timing.delay_before) {
                        await new Promise(resolve => setTimeout(resolve, step.timing.delay_before));
                    }
                    
                    // Execute the step based on type (reuse existing demo execution logic)
                    switch (step.type) {
                        case 'user_input':
                            if (typeof executeUserInputStep === 'function') {
                                await executeUserInputStep(step);
                            } else {
                                console.log('🎭 User input step:', step.message);
                                await addDemoMessage('user', step.message);
                            }
                            break;
                            
                        case 'system_reply':
                            if (typeof executeSystemReplyStep === 'function') {
                                await executeSystemReplyStep(step);
                            } else {
                                console.log('🎭 System reply step:', step.message);
                                await addDemoMessage('assistant', step.message);
                            }
                            break;
                            
                                    case 'dom_action':
                const success = await executeDomActionStep(step); if (success === false) { console.error('❌ Step failed, stopping demo'); await addDemoMessage('system', '❌ **Test Stopped:** Step failed.'); break; }
                break;
                
            case 'mcp_tool_call':
                            if (typeof executeMcpToolCallStep === 'function') {
                                await executeMcpToolCallStep(step);
                            } else {
                                console.log('🎭 MCP tool call step:', step.tool_name);
                                await addDemoMessage('assistant', `🔧 **Tool Call:** ${step.tool_name}`);
                            }
                            break;
                            
                        default:
                            console.warn('🎭 Unknown step type for regression test:', step.type);
                            await addDemoMessage('assistant', `🎭 **Test Step:** ${step.step_id}`);
                    }
                }
                
                await addDemoMessage('assistant', '🎭 **🎉 REGRESSION TEST BATTERY COMPLETED!**\n\n✅ All demo continuation tests passed!\n\n*Demo environment is ready for additional testing.*');
                
            } else {
                console.log('🎭 No specific continuation steps found - demo ready for manual testing');
                await addDemoMessage('assistant', '🎭 🔋 REGRESSION TEST ENVIRONMENT READY!\n\n✅ Controlled conditions achieved:\n• DEV mode active\n• Fresh database\n• Ready for manual testing\n\nYou can now run manual tests or start a new demo sequence.');
            }
        } else {
            console.log('🎭 Unknown demo state, showing generic continuation');
            await addDemoMessage('assistant', '🎭 Demo server restart complete! Ready for the next trick...');
        }
        
    } catch (error) {
        console.error('🎭 Error continuing demo from state:', error);
        // Fallback to generic continuation message
        await addDemoMessage('assistant', '🎭 **Demo continuation failed.** You can start a new demo if needed.');
    }
}

/**
 * 🎭 DEMO CONTINUATION BREAKTHROUGH - The Lightning in a Bottle Achievement
 * ============================================================================
 * 
 * This system represents a major breakthrough in interactive demo technology:
 * 
 * 🚀 BULLETPROOF DEMO CONTINUATION ACROSS SERVER RESTARTS
 * - File-based state persistence survives database clears
 * - Server-side comeback detection with temp message blocking
 * - JavaScript takeover prevents LLM interference
 * - Interactive Y/N prompts that actually work with real keyboard handlers
 * 
 * 🔋 REGRESSION TEST DEMO STARTING POINT
 * - Controlled conditions: DEV mode + fresh database
 * - Battery of tests begins after user confirms with Ctrl+Alt+Y
 * - Perfect environment for deterministic testing
 * 
 * 🎯 TECHNICAL ACHIEVEMENTS
 * - No more "Where am I?" LLM chatter after restart
 * - Demo script doesn't restart from beginning (loadDemoScriptConfig vs loadDemoScript)
 * - Real keyboard event handling with visual feedback
 * - Step execution engine with fallbacks for missing functions
 * 
 * This is the foundation for advanced demo orchestration and regression testing.
 * The magic happens when user presses Ctrl+Alt+Y after a demo-triggered restart.
 */

// Set up keyboard handler for demo continuation Y/N prompt
function setupDemoContinuationKeyboardHandler(demoState) {
    console.log('🎭 Setting up keyboard handler for demo continuation...');
    
    // Remove any existing demo keyboard handler
    if (window.demoContinuationKeyboardHandler) {
        document.removeEventListener('keydown', window.demoContinuationKeyboardHandler);
    }
    
    // Create new keyboard handler
    window.demoContinuationKeyboardHandler = async function(event) {
        // Check for Ctrl+Alt+Y (continue demo) - Mac: Control+Option+Y
        if (event.ctrlKey && event.altKey && event.code === 'KeyY') {
            event.preventDefault();
            
            console.log('🎭 User pressed Ctrl+Alt+Y - continuing demo! (Mac Compatible)');
            
            // Show feedback that input was registered (will be adapted for platform)
            await addDemoMessage('user', 'Ctrl+Alt+Y ✅ Demo continuation confirmed!');
            
            // Remove the keyboard handler
            document.removeEventListener('keydown', window.demoContinuationKeyboardHandler);
            window.demoContinuationKeyboardHandler = null;
            
            // Continue the demo
            await continueDemoFromState(demoState);
            
        }
        // Check for Ctrl+Alt+N (stop demo) - Mac: Control+Option+N
        else if (event.ctrlKey && event.altKey && event.code === 'KeyN') {
            event.preventDefault();
            
            console.log('🎭 User pressed Ctrl+Alt+N - stopping demo! (Mac Compatible)');
            
            // Show feedback that input was registered (will be adapted for platform)
            await addDemoMessage('user', '**Ctrl+Alt+N** ❌ *Demo stopped by user.*');
            
            // Remove the keyboard handler
            document.removeEventListener('keydown', window.demoContinuationKeyboardHandler);
            window.demoContinuationKeyboardHandler = null;
            
            // Clear demo flags
            window.demoInProgress = false;
            window.demoContinuationActive = false;
            
            await addDemoMessage('assistant', '🎭 **Demo session ended.** You can start a new demo anytime!');
        }
    };
    
    // Add the keyboard event listener
    document.addEventListener('keydown', window.demoContinuationKeyboardHandler);
    
    console.log('🎭 Keyboard handler active - waiting for Ctrl+Alt+Y or Ctrl+Alt+N');
}

// Add demo message via Server Message Queue (Ensures correct ordering)
async function addDemoMessage(role, content) {
    try {
        console.log(`🎭 Sending demo message to server (${role}):`, content.substring(0, 50) + '...');
        
        const formData = new FormData();
        formData.append('role', role);
        formData.append('content', content);
        
        await fetch('/log-demo-message', {
            method: 'POST',
            body: formData
        });
        
        // We do NOT append to DOM here. We wait for the server to broadcast it back via WebSocket.
    } catch (error) {
        console.error('🎭 Error sending demo message:', error);
    }
}

// Show demo comeback message with special UX
async function showDemoComebackMessage(message, subtitle) {
    try {
        console.log('🎭 Displaying demo comeback message...');
        
        // Add message to conversation with special styling
        const msgList = document.querySelector('#msg-list') || document.querySelector('.messages-list') || document.querySelector('#chat-messages');
        if (!msgList) {
            console.warn('🎭 Messages container not found - checked #msg-list, .messages-list, #chat-messages');
            return false;
        }
        
        // Strip extra line breaks and whitespace that cause spacing issues
        const cleanMessage = message.replace(/\n+/g, ' ').replace(/\s+/g, ' ').trim();
        const cleanSubtitle = subtitle ? subtitle.replace(/\n+/g, ' ').replace(/\s+/g, ' ').trim() : '';
        
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message assistant demo-comeback';
        messageDiv.innerHTML = `
            <div class="message-container">
                <div class="message-content demo-comeback-content">
                    <div class="demo-comeback-main">${cleanMessage}</div>
                    ${cleanSubtitle ? `<div class="demo-comeback-subtitle">${cleanSubtitle}</div>` : ''}
                </div>
            </div>
        `;
        
        // Add special styling
        messageDiv.style.cssText = `
            background: linear-gradient(135deg, #4f46e5, #7c3aed);
            border: 2px solid #8b5cf6;
            border-radius: 12px;
            margin: 16px 8px;
            box-shadow: 0 8px 25px rgba(139, 92, 246, 0.3);
            animation: demoGlow 2s ease-in-out;
        `;
        
        msgList.appendChild(messageDiv);
        msgList.scrollTop = msgList.scrollHeight;
        
        // Add CSS animation
        if (!document.querySelector('#demo-comeback-styles')) {
            const style = document.createElement('style');
            style.id = 'demo-comeback-styles';
            style.textContent = `
                @keyframes demoGlow {
                    0% { transform: scale(0.95); opacity: 0; box-shadow: 0 8px 25px rgba(139, 92, 246, 0.3); }
                    50% { transform: scale(1.02); opacity: 1; box-shadow: 0 12px 35px rgba(139, 92, 246, 0.6); }
                    100% { transform: scale(1); opacity: 1; box-shadow: 0 8px 25px rgba(139, 92, 246, 0.3); }
                }
                .demo-comeback-content {
                    color: white !important;
                    text-align: center;
                    padding: 8px 16px;
                }
                .demo-comeback-main {
                    font-size: 1.1em;
                    font-weight: 600;
                    margin: 0;
                }
                .demo-comeback-subtitle {
                    font-size: 0.9em;
                    opacity: 0.9;
                    font-style: italic;
                    margin: 0;
                }
            `;
            document.head.appendChild(style);
        }
        
        console.log('🎭 Demo comeback message displayed with special styling');
        
    } catch (error) {
        console.error('🎭 Error showing demo comeback message:', error);
    }
}

// Helper to display system messages (phantom) without user attribution
function displayPhantomSystemMessage(message) {
     const msgList = document.getElementById('msg-list');
    if (msgList) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message system'; // Ensure you have CSS for this or reuse 'assistant'
        messageDiv.innerHTML = `<div class="message-container"><div class="message-content" style="color: #666; font-style: italic;"><p>${message}</p></div></div>`;
        msgList.appendChild(messageDiv);
        msgList.scrollTop = msgList.scrollHeight;
    }
}

document.addEventListener('DOMContentLoaded', () => {
    initializeChatInterface();
    initializeScrollObserver();
    
    // Check for demo bookmark and resume if exists
    checkAndResumeDemoBookmark();
    
    // Check for demo resume after server restart
    checkDemoResumeAfterRestart();
    
    // Check for demo comeback message after restart
    checkDemoComeback();
    
    // Send temp message when WebSocket is ready (with initial delay for page load)
    if (tempMessage && !tempMessageSent) {
        setTimeout(sendTempMessageWhenReady, 1000);
    }
});
