/**
 * HYBRID JAVASCRIPT PATTERN: Static File + Python Parameterization
 * 
 * This file is loaded statically but designed for Python configuration.
 * Python calls window.initializeChatScripts(config) with dynamic parameters.
 * 
 * Usage:
 * 1. Static: <script src="/assets/sortable-parameterized-init.js"></script>
 * 2. Dynamic: <script>initializeChatScripts({sortableSelector: '.sortable'})</script>
 * 
 * Benefits: Static caching + Python configuration without templates
 */

// Add this new function to the file
function setupGlobalScrollListener() {
    console.log('Setting up global htmx:afterSwap scroll listener.');
    const leftPanel = document.getElementById('grid-left-content');

    if (!leftPanel) {
        console.warn('Left panel #grid-left-content not found for scroll listener.');
        return;
    }

    document.body.addEventListener('htmx:afterSwap', function(evt) {
        // Check if the swap happened within the left panel
        if (leftPanel.contains(evt.detail.target)) {
            console.log('HTMX swap detected in left panel. Triggering scroll to bottom.');
            
            // Use a small timeout to allow the browser to render the new content
            // and calculate the correct scrollHeight before we try to scroll.
            setTimeout(() => {
                leftPanel.scrollTo({
                    top: leftPanel.scrollHeight,
                    behavior: 'smooth'
                });
            }, 400);
        }
    });
}

// Modify your existing initializeChatScripts function to call the new function
window.initializeChatScripts = function(config) {
    console.log('🚀 initializeChatScripts called with config:', config);
    
    if (window._pipulateInitialized) {
        console.warn('⚠️ Scripts already initialized, skipping duplicate call');
        return;
    }
    
    setupWebSocketAndSSE();
    setupInteractions();
    setupMenuFlashFeedback();
    setupGlobalScrollListener(); // <-- ADD THIS LINE
    
    if (typeof window.initializeSearchPluginsKeyboardNav === 'function') {
        setTimeout(() => {
            window.initializeSearchPluginsKeyboardNav();
        }, 100);
    }
    
    window._pipulateInitialized = true;
    console.log('✅ Chat scripts initialized (sortable handled separately)');
};

// setupSortable function removed - now handled by consolidated init.js

function setupWebSocketAndSSE() {
    // SSE Setup
    let lastMessage = null;
    const evtSource = new EventSource("/sse");
    
    evtSource.onmessage = function(event) {
        const data = event.data;
        console.log('SSE received:', data);
        
        // 🔄 WATCHDOG RESTART NOTIFICATION: Handle restart notifications with improved performance
        if (data.startsWith('restart_notification:')) {
            const restartHtml = data.substring('restart_notification:'.length);
            
            // Create a sleek, performance-optimized restart overlay
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
            `;
            overlay.innerHTML = restartHtml;
            
            // Add to body with minimal DOM impact
            document.body.appendChild(overlay);
            
            console.log('🔄 WATCHDOG_RESTART: Displaying restart notification overlay (performance optimized)');
            return; // Don't process as normal SSE message
        }
        
        // Only process if it's not a ping message
        if (!data.includes('Test ping at')) {
            const todoList = document.getElementById('todo-list');
            if (!todoList) {
                console.error('Could not find todo-list element');
                return;
            }

            const temp = document.createElement('div');
            temp.innerHTML = data;
            
            const newTodo = temp.firstChild;
            if (newTodo) {
                todoList.appendChild(newTodo);
                htmx.process(newTodo);
            }
        }
    };

    // Test functions
    window.testSSE = function() {
        alert('Latest SSE message: ' + (lastMessage || 'No messages received yet'));
    }
    
    window.sseLastMessage = function() {
        return lastMessage;
    }
    
    console.log('SSE handlers initialized (WebSocket handled by player-piano.js)');
}

function setupInteractions() {
    // Form reset after submission
    document.addEventListener('htmx:afterSwap', function(event) {
        // Handle both todo-list and competitor-list targets
        if ((event.target.id === 'todo-list' || event.target.id === 'competitor-list') && event.detail.successful) {
            const targetId = event.target.id;
            
            const form = document.querySelector(`form[hx-target="#${targetId}"]`);
            
            if (form) {
                form.reset();
            } else {
                // Try alternative selectors if the first one doesn't work
                const allForms = document.querySelectorAll('form[hx-target]');
                
                // Look for forms with matching target attributes
                allForms.forEach(f => {
                    if (f.getAttribute('hx-target') === `#${targetId}`) {
                        f.reset();
                    }
                });
            }
        }
    });

    // Add Enter/Shift+Enter handling for chat textarea
    const textarea = document.getElementById('msg');
    if (textarea) {
        textarea.addEventListener('keydown', function(e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                // Find the form and submit it
                var form = textarea.closest('form');
                if (form) {
                    form.requestSubmit ? form.requestSubmit() : form.submit();
                }
            }
            // else allow Shift+Enter for newline
        });
    }
}

/* ============================================================================
   SEARCH PLUGINS KEYBOARD NAVIGATION - Carson Gross HTMX Approach
   ============================================================================
   
   Keyboard navigation for search plugins dropdown following HTMX principles:
   • HTMX handles the heavy lifting (search API calls, DOM updates)
   • Minimal JavaScript for UI interaction (keyboard navigation)
   • Progressive enhancement - works without JavaScript
   • Clean separation of concerns
   
   🎯 FEATURES:
   • Arrow key navigation (up/down with wrapping)
   • Enter key selection and navigation
   • Escape key dismissal
   • Click-away dismissal with selection clearing
   • Mouse hover compatibility
   ============================================================================ */

// Global search plugins keyboard navigation functions
window.initializeSearchPluginsKeyboardNav = function() {
    console.log('🔍 Initializing Search Plugins keyboard navigation');
    
    const searchInput = document.getElementById('nav-plugin-search');
    const dropdown = document.getElementById('search-results-dropdown');
    
    if (!searchInput || !dropdown) {
        console.warn('⚠️ Search plugins elements not found, skipping keyboard nav setup');
        console.log('Debug: searchInput =', searchInput, 'dropdown =', dropdown);
        return;
    }
    
    console.log('✅ Search elements found:', { searchInput, dropdown });
    
    let selectedIndex = -1;
    
    // Global Ctrl+K shortcut to activate search
    document.addEventListener('keydown', function(event) {
        if (event.ctrlKey && event.key === 'k') {
            event.preventDefault();
            searchInput.focus();
            searchInput.select(); // Select all text for easy replacement
            console.log('🔍 Search activated via Ctrl+K');
        }
    });
    
    // Keyboard navigation for search input
    searchInput.addEventListener('keydown', function(event) {
        const items = dropdown.querySelectorAll('.search-result-item');
        
        if (event.key === 'ArrowDown') {
            event.preventDefault();
            if (dropdown.style.display === 'none' || items.length === 0) return;
            
            // Clear previous selection
            if (selectedIndex >= 0 && items[selectedIndex]) {
                items[selectedIndex].classList.remove('selected');
            }
            
            // Move to next item (wrap to first)
            selectedIndex = (selectedIndex + 1) % items.length;
            items[selectedIndex].classList.add('selected');
            
            // Scroll into view if needed
            items[selectedIndex].scrollIntoView({ block: 'nearest' });
            
        } else if (event.key === 'ArrowUp') {
            event.preventDefault();
            if (dropdown.style.display === 'none' || items.length === 0) return;
            
            // Clear previous selection
            if (selectedIndex >= 0 && items[selectedIndex]) {
                items[selectedIndex].classList.remove('selected');
            }
            
            // Move to previous item (wrap to last)
            selectedIndex = selectedIndex <= 0 ? items.length - 1 : selectedIndex - 1;
            items[selectedIndex].classList.add('selected');
            
            // Scroll into view if needed
            items[selectedIndex].scrollIntoView({ block: 'nearest' });
            
        } else if (event.key === 'Enter') {
            event.preventDefault();
            if (selectedIndex >= 0 && items[selectedIndex]) {
                // Simulate click on selected item
                items[selectedIndex].click();
            } else if (items.length === 1) {
                // No manual selection but only one result - select it
                items[0].click();
                console.log('🎯 Enter pressed on single unselected result - navigating');
            }
            
        } else if (event.key === 'Escape') {
            // Hide dropdown and clear selection
            dropdown.style.display = 'none';
            clearSearchSelection();
            searchInput.blur();
        }
    });
    
    // Clear selection when new search results arrive
    function clearSearchSelection() {
        selectedIndex = -1;
        const items = dropdown.querySelectorAll('.search-result-item.selected');
        items.forEach(item => item.classList.remove('selected'));
    }
    
    // Reset selection when dropdown content changes (HTMX updates)
    const observer = new MutationObserver(function(mutations) {
        mutations.forEach(function(mutation) {
            if (mutation.type === 'childList') {
                clearSearchSelection();
                // Auto-select single result after content update
                autoSelectSingleResult();
            }
        });
    });
    
    observer.observe(dropdown, { childList: true, subtree: true });
    
    // Auto-select single result function
    function autoSelectSingleResult() {
        const items = dropdown.querySelectorAll('.search-result-item');
        
        // Only auto-select if there's exactly one result and it has the auto-select marker
        if (items.length === 1 && items[0].classList.contains('auto-select-single')) {
            selectedIndex = 0;
            items[0].classList.add('selected');
            console.log('🎯 Auto-selected single search result');
        }
    }
    
    // Make auto-select function globally available for server-triggered calls
    window.initializeSearchPluginsAutoSelect = autoSelectSingleResult;
    
    // Global click handler for click-away dismissal
    document.addEventListener('click', function(event) {
        // Check if click is outside search area
        if (searchInput && dropdown) {
            const searchContainer = searchInput.closest('.search-dropdown-container');
            const isClickInsideSearch = searchContainer && searchContainer.contains(event.target);
            
            if (!isClickInsideSearch) {
                dropdown.style.display = 'none';
                clearSearchSelection();
                console.log('🔍 Search dropdown closed via click-away');
            }
        }
    });
    
    console.log('✅ Search Plugins keyboard navigation initialized');
};

function linkifyText(text) {
    const urlRegex = /(https?:\/\/[^\s]+)/g;
    return text.replace(urlRegex, function(url) {
        return '<a href="' + url + '" target="_blank">' + url + '</a>';
    });
}

// Splitter initialization removed - now handled by consolidated init.js

function setupMenuFlashFeedback() {
    console.log('🔔 Setting up enhanced menu flash feedback system');
    
    // Enhanced CSS for stronger, more appealing flash animation
    if (!document.getElementById('menu-flash-styles')) {
        const style = document.createElement('style');
        style.id = 'menu-flash-styles';
        style.textContent = `
            .menu-flash {
                animation: menuFlash 0.6s ease-out;
                position: relative;
                z-index: 10;
            }
            
            @keyframes menuFlash {
                0% { box-shadow: 0 0 0 0 rgba(74, 171, 247, 0.9); }
                50% { box-shadow: 0 0 0 12px rgba(74, 171, 247, 0.7); }
                100% { box-shadow: 0 0 0 0 rgba(74, 171, 247, 0); }
            }
            
            [data-theme="dark"] .menu-flash {
                animation: menuFlashDark 0.6s ease-out;
            }
            
            @keyframes menuFlashDark {
                0% { box-shadow: 0 0 0 0 rgba(120, 220, 255, 0.8); }
                50% { box-shadow: 0 0 0 12px rgba(120, 220, 255, 0.6); }
                100% { box-shadow: 0 0 0 0 rgba(120, 220, 255, 0); }
            }
            
            @media (prefers-reduced-motion: reduce) {
                .menu-flash { animation: none; }
            }
        `;
        document.head.appendChild(style);
    }
    
    // Enhanced flash function with consistent timing
    function flashMenu(elementId, menuType, delay = 0) {
        setTimeout(() => {
            const element = document.getElementById(elementId);
            if (!element) return;
            
            element.classList.remove('menu-flash');
            element.offsetHeight; // Force reflow
            element.classList.add('menu-flash');
            
            // Remove class after animation completes
            setTimeout(() => {
                element.classList.remove('menu-flash');
            }, 600);
            
            console.log(`🔔 ${menuType} menu flashed`);
        }, delay);
    }
    
    // Enhanced detection system for all menu update triggers
    
    // 1. Listen for HTMX requests that will trigger page refresh or menu updates
    document.addEventListener('htmx:beforeRequest', function(event) {
        const target = event.target;
        if (target && target.getAttribute) {
            const hxPost = target.getAttribute('hx-post');
            
            // Roles bulk operations (page refresh)
            if (hxPost && (hxPost.includes('select_all') || hxPost.includes('deselect_all') || hxPost.includes('select_default'))) {
                sessionStorage.setItem('pipulate_app_menu_flash', 'true');
                console.log('🔔 Roles bulk action detected, will flash APP menu after refresh');
            }
            
            // Role toggle operations (HTMX swap)
            if (hxPost && hxPost.includes('/roles/toggle/')) {
                sessionStorage.setItem('pipulate_app_menu_flash_immediate', 'true');
                console.log('🔔 Role toggle detected, will flash APP menu after swap');
            }
            
            // Profile operations (HTMX swap)
            if (hxPost && (hxPost.includes('/profiles/') || hxPost.includes('profiles'))) {
                sessionStorage.setItem('pipulate_profile_menu_flash_immediate', 'true');
                console.log('🔔 Profile operation detected, will flash PROFILE menu after swap');
            }
        }
    });
    
    // 2. Listen for HTMX afterSwap for immediate flash triggers
    document.addEventListener('htmx:afterSwap', function(event) {
        const targetId = event.target.id;
        
        // Check for stored flash flags and execute immediately
        if (sessionStorage.getItem('pipulate_app_menu_flash_immediate') === 'true') {
            sessionStorage.removeItem('pipulate_app_menu_flash_immediate');
            flashMenu('app-id', 'APP', 50); // Small delay for smooth effect
        }
        
        if (sessionStorage.getItem('pipulate_profile_menu_flash_immediate') === 'true') {
            sessionStorage.removeItem('pipulate_profile_menu_flash_immediate');
            flashMenu('profile-id', 'PROFILE', 50);
        }
        
        // Direct menu container updates (fallback)
        if (targetId === 'profile-dropdown-menu') {
            flashMenu('profile-id', 'PROFILE', 50);
        } else if (targetId === 'app-dropdown-menu') {
            flashMenu('app-id', 'APP', 50);
        }
    });
    
    // 3. Check for page refresh flash flags on load
    if (sessionStorage.getItem('pipulate_app_menu_flash') === 'true') {
        sessionStorage.removeItem('pipulate_app_menu_flash');
        flashMenu('app-id', 'APP', 150); // Longer delay for page refresh
    }
    
    if (sessionStorage.getItem('pipulate_profile_menu_flash') === 'true') {
        sessionStorage.removeItem('pipulate_profile_menu_flash');
        flashMenu('profile-id', 'PROFILE', 150);
    }
    
    console.log('🔔 Enhanced menu flash feedback system initialized');
}

// === GLOBAL AUTO-SUBMIT FOR NEW PIPELINE KEY ===
(function() {
    try {
        console.log('🔑 Setting up global auto-submit for new pipeline key');
        
        // Helper: Find and click the Enter Key button after new key appears
        function autoSubmitEnterKeyButton() {
            try {
                console.log('🔑 Auto-submit function called');
                
                // Find all new key buttons and enter key buttons
                const newKeyButtons = document.querySelectorAll('.new-key-button');
                const enterKeyButtons = document.querySelectorAll('.inline-button-submit');
                
                console.log('🔑 Found newKeyButtons:', newKeyButtons.length);
                console.log('🔑 Found enterKeyButtons:', enterKeyButtons.length);
                
                // Strategy: For each new key button, find the corresponding enter key button
                newKeyButtons.forEach((newKeyBtn, index) => {
                    try {
                        console.log(`🔑 Processing newKeyButton[${index}]:`, newKeyBtn);
                        
                        // Find closest form
                        let form = newKeyBtn.closest('form');
                        let enterBtn = null;
                        
                        if (form) {
                            enterBtn = form.querySelector('.inline-button-submit');
                            console.log(`🔑 Found form, enterBtn in form:`, enterBtn);
                        } else {
                            // Fallback: global search
                            enterBtn = document.querySelector('.inline-button-submit');
                            console.log(`🔑 No form found, using global enterBtn:`, enterBtn);
                        }
                        
                        if (enterBtn && !enterBtn.dataset.autoSubmitted) {
                            console.log('🔑 Auto-clicking enter button:', enterBtn);
                            // Mark as handled to avoid loops
                            enterBtn.dataset.autoSubmitted = 'true';
                            setTimeout(() => {
                                try {
                                    enterBtn.click();
                                    console.log('🔑 Enter button clicked!');
                                } catch (clickError) {
                                    console.error('🔑 Error clicking enter button:', clickError);
                                }
                            }, 150); // Slight delay for DOM readiness
                        } else if (!enterBtn) {
                            console.log('🔑 No enter button found for this new key button');
                        } else {
                            console.log('🔑 Enter button already auto-submitted, skipping');
                        }
                    } catch (forEachError) {
                        console.error('🔑 Error processing newKeyButton:', forEachError);
                    }
                });
            } catch (autoSubmitError) {
                console.error('🔑 Error in autoSubmitEnterKeyButton:', autoSubmitError);
            }
        }

        // HTMX: After swap, if a .new-key-button is present, auto-submit
        if (document && document.body) {
            document.body.addEventListener('htmx:afterSwap', function(evt) {
                try {
                    console.log('🔑 HTMX afterSwap event:', evt.target);
                    
                    // Check if the swapped content contains a new-key-button
                    if (evt.target && evt.target.querySelector && evt.target.querySelector('.new-key-button')) {
                        console.log('🔑 New key button found in swapped content, triggering auto-submit');
                        // Use a short delay to ensure DOM is ready
                        setTimeout(autoSubmitEnterKeyButton, 100);
                    }
                } catch (afterSwapError) {
                    console.error('🔑 Error in htmx:afterSwap handler:', afterSwapError);
                }
            });

            // On click of new-key-button, set a sessionStorage flag for page reload fallback
            document.body.addEventListener('click', function(evt) {
                try {
                    if (evt.target.classList && evt.target.classList.contains('new-key-button')) {
                        console.log('🔑 New key button clicked, setting sessionStorage flag');
                        sessionStorage.setItem('pipulate_auto_submit_new_key', 'true');
                    }
                } catch (clickError) {
                    console.error('🔑 Error in click handler:', clickError);
                }
            });
        } else {
            console.error('🔑 Document or document.body not available');
        }

        // On page load, if flag is set, auto-submit and clear flag
        if (document.readyState === 'loading') {
            if (document && document.addEventListener) {
                document.addEventListener('DOMContentLoaded', function() {
                    try {
                        if (sessionStorage.getItem('pipulate_auto_submit_new_key') === 'true') {
                            console.log('🔑 Page loaded with auto-submit flag, triggering auto-submit');
                            sessionStorage.removeItem('pipulate_auto_submit_new_key');
                            setTimeout(autoSubmitEnterKeyButton, 150);
                        }
                    } catch (domReadyError) {
                        console.error('🔑 Error in DOMContentLoaded handler:', domReadyError);
                    }
                });
            }
        } else {
            // Document already loaded
            try {
                if (sessionStorage.getItem('pipulate_auto_submit_new_key') === 'true') {
                    console.log('🔑 Document already loaded with auto-submit flag, triggering auto-submit');
                    sessionStorage.removeItem('pipulate_auto_submit_new_key');
                    setTimeout(autoSubmitEnterKeyButton, 150);
                }
            } catch (alreadyLoadedError) {
                console.error('🔑 Error checking already loaded state:', alreadyLoadedError);
            }
        }
        
        // Debug function for manual testing
        window.debugAutoSubmit = function() {
            console.log('🔑 Manual debug trigger');
            autoSubmitEnterKeyButton();
        };
        
        console.log('🔑 Global auto-submit for new pipeline key initialized');
    } catch (setupError) {
        console.error('🔑 Error setting up global auto-submit:', setupError);
    }
})();
