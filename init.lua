-- init.lua
--  _       _ _     _             
-- (_)_ __ (_) |_  | |_   _  __ _ 
-- | | '_ \| | __| | | | | |/ _` |
-- | | | | | | |_ _| | |_| | (_| |
-- |_|_| |_|_|\__(_)_|\__,_|\__,_|
--                                

-- Session AI Dialogue Label (`il` in terminal to edit, <F2> in Neovim to reload)
local AI_LABEL = "Gemini 4 Argon High"

-- Basic Settings
local set = vim.opt

set.spell = true
set.spelllang = 'en_us'
local custom_spellfile = vim.fn.expand('~/repos/nixos/en.utf-8.add')
if vim.fn.filereadable(custom_spellfile) == 1 then
    set.spellfile = custom_spellfile
end
vim.opt.virtualedit = "block"
set.mouse = ''
set.clipboard = 'unnamedplus'
set.textwidth = 80
set.wrap = false
set.belloff = 'all'
set.tabstop = 4
set.expandtab = true
set.shiftwidth = 4
set.softtabstop = 4
set.autoindent = true
set.smartindent = false
set.smarttab = true
set.smartcase = true
set.incsearch = true
set.hlsearch = true
set.ignorecase = true
set.number = true
set.relativenumber = true
set.scrolloff = 5
set.wildmenu = true
set.wildmode = 'list:longest'
set.showmatch = true
set.matchtime = 2
set.matchpairs:append('<:>')
set.matchpairs:append('*:*')

-- Visual mode highlighting
vim.cmd([[hi Visual ctermbg=2 ctermfg=0 guibg=green guifg=black]])

-- Filetype Specific Settings
vim.api.nvim_create_autocmd({"BufRead", "BufNewFile"}, {
    pattern = "journal.txt",
    command = "set filetype=markdown"
})

-- context.txt: the list of files an AI will read. The walk writes it and
-- `context` opens it, so it is a newcomer's first vim (2026-09-20, read off
-- the first Mac screen; one file for the walk and the workbench since
-- 2026-09-25). THE LIST IS NOT PROSE: every line is a path or a `! `
-- command, so the journal defaults above are wrong here in three ways a
-- newcomer sees at once. spell paints every path red, which reads as
-- errors. textwidth=80 hard-wraps a path or command typed past the column,
-- turning one line into two and breaking it. relativenumber counts distance
-- from the cursor, which reads as 4 3 2 1 5 to someone meeting it cold.
-- Three buffer-local resets, nothing global.
vim.api.nvim_create_autocmd({"BufRead", "BufNewFile"}, {
    pattern = "context.txt",
    callback = function()
        vim.opt_local.textwidth = 0
        vim.opt_local.spell = false
        vim.opt_local.relativenumber = false
    end,
})

--  _____                 _   _                 
-- |  ___|   _ _ __   ___| |_(_) ___  _ __  ___ 
-- | |_ | | | | '_ \ / __| __| |/ _ \| '_ \/ __|
-- |  _|| |_| | | | | (__| |_| | (_) | | | \__ \
-- |_|   \__,_|_| |_|\___|\__|_|\___/|_| |_|___/
--                                              

-- Functions
function new_journal_entry()
    -- Search for the marker
    local marker = "# Beginning of Notes"
    local current_line = vim.fn.search(marker, 'nw')
    
    if current_line == 0 then
        print("Marker '# Beginning of Notes' not found.")
        return
    end

    -- Generate the new entry
    local date_cmd = "date +\"%a %b %d, %Y, %H:%M\""
    local date = vim.fn.system(date_cmd):gsub("\n", "")
    
    local entry = "--------------------------------------------------------------------------------\n"
                  .. "date: " .. date .. "\n---\n\n"
                  .. "--- BEGIN NEW ARTICLE ---\n\n**Me**:  \n\n"
                  .. "!!!"
                  .. string.rep("\n", 23)  -- Restore the psychological blank slate

    -- Insert the new entry below the marker
    vim.api.nvim_buf_set_lines(0, current_line, current_line, false, vim.split(entry, "\n"))

    -- Move the cursor to the empty line exactly two lines below the BEGIN header
    -- (current_line + 7 lands perfectly between the header and the exclamation marks)
    vim.api.nvim_win_set_cursor(0, {current_line + 7, 10})

    -- Center the screen
    vim.cmd('normal! zz')

    -- Enter insert mode
    vim.cmd('startinsert')
end

function git_commit_push()
    -- Get the current buffer's file name (not full path) and remember the
    -- source window, because the split below becomes the current window.
    local file_name = vim.fn.expand('%:t')
    local src_win = vim.api.nvim_get_current_win()
    -- ==========================================================
    -- FIRST FRAME: acknowledge the keypress BEFORE any blocking work.
    -- Every vim.fn.system() below is synchronous, and `git log` on a
    -- long-history file can take a visible beat. The split and its
    -- redraw come first so a mistaken \g is seen in one frame; the
    -- rest of this function writes into this same buffer.
    -- ==========================================================
    vim.cmd('botright 20split git_output')
    vim.cmd('setlocal buftype=nofile bufhidden=hide noswapfile')
    vim.api.nvim_buf_set_keymap(0, 'n', 'q', ':q<CR>', { noremap = true, silent = true })
    vim.api.nvim_buf_set_lines(0, 0, -1, false, {
        "===========================================================",
        " 🚀 \\g received: " .. file_name,
        "===========================================================",
        "",
        " ⏳ Saving and measuring the diff... (press q to close this panel afterwards)",
    })
    vim.cmd('redraw')
    -- Automatically save the source buffer (not this scratch split)
    vim.api.nvim_win_call(src_win, function() vim.cmd('w') end)

    -- STEP 1: Add the file FIRST so we can measure the payload.
    local git_add = vim.fn.system('git add ' .. vim.fn.shellescape(file_name))
    
    -- STEP 2: Capture both the full diff and the high-level stat map.
    local git_diff = vim.fn.system('git diff --cached ' .. vim.fn.shellescape(file_name))
    local git_stat = vim.fn.system('git diff --cached --stat ' .. vim.fn.shellescape(file_name))
    
    -- Guard clause: If diff is empty, open split with warning and abort
    if git_diff == "" then
        -- The split is already open (first frame above); just update it.
        vim.api.nvim_buf_set_lines(0, 0, -1, false, {"⚠️  No changes detected to commit.", " 💡 Press 'q' or type :q to exit this panel."})
        return
    end

    -- Calculate metrics and prepare the safe slice
    local diff_bytes = string.len(git_diff)
    local safe_diff = git_diff

    -- Keep Neovim's frontend payload budget aligned with scripts/ai.py and Ollama.
    -- The extra prompt reserve avoids claiming the whole context window for the diff
    -- while the commit prompt, git stat, and generated response still need room.
    local max_ctx = math.floor(tonumber(os.getenv("PIPULATE_OLLAMA_NUM_CTX") or "") or 131072)
    if max_ctx < 8192 then
        max_ctx = 8192
    end

    local output_reserve_tokens = math.floor(tonumber(os.getenv("PIPULATE_OLLAMA_OUTPUT_RESERVE_TOKENS") or "") or 4096)
    if output_reserve_tokens < 1024 then
        output_reserve_tokens = 4096
    end

    local prompt_reserve_tokens = math.floor(tonumber(os.getenv("PIPULATE_OLLAMA_PROMPT_RESERVE_TOKENS") or "") or 2048)
    if prompt_reserve_tokens < 512 then
        prompt_reserve_tokens = 2048
    end

    local chars_per_token = tonumber(os.getenv("PIPULATE_CHARS_PER_TOKEN") or "") or 4.0
    if chars_per_token <= 0 then
        chars_per_token = 4.0
    end

    local available_tokens = max_ctx - output_reserve_tokens - prompt_reserve_tokens
    if available_tokens < 4000 then
        available_tokens = 4000
    end

    local max_diff_size = math.floor(available_tokens * chars_per_token)
    if max_diff_size < 16000 then
        max_diff_size = 16000
    end

    local diff_display = tostring(diff_bytes) .. " bytes"

    if diff_bytes > max_diff_size then
        -- Find the last newline within the limit to avoid slicing mid-word/syntax
        local slice = string.sub(git_diff, 1, max_diff_size)
        local last_newline = slice:match(".*()\n")
        if last_newline then
            safe_diff = string.sub(slice, 1, last_newline - 1)
        else
            safe_diff = slice
        end
        
        safe_diff = safe_diff .. "\n\n... [NARRATIVE DIFF TRUNCATED DUE TO SIZE]"
        diff_display = diff_display .. " ✂️  (Sliced to " .. max_diff_size .. ")"
    end

    -- Assemble the Hybrid Payload
    local hybrid_payload = "COMMIT STATISTICS:\n" .. git_stat .. "\n\nDETAILED CHANGES:\n" .. safe_diff

    local last_commit_time = vim.fn.system('git log -1 --format=%cr ' .. vim.fn.shellescape(file_name)):gsub("\n", "")
    if last_commit_time == "" then last_commit_time = "First commit" end
    
    local target_model = "ai.py default (config.DEFAULT_PROMPT_MODEL); actual reported as Model Used below" 

    -- ==========================================================
    -- INSTANT DRAMATIC FEEDBACK: Open the split immediately
    -- ==========================================================
    -- (Split already open since the first frame; refresh its contents.)
    
    local waiting_msg = {
        "===========================================================",
        " 🚀 COMMITTING: " .. file_name,
        "===========================================================",
        "",
        " 📊 Payload: " .. diff_display .. " (Hybrid Map + Slice)",
        " ⏱️ Last Commit: " .. last_commit_time,
        " 🤖 Target Model: " .. target_model,
        "",
        " ⏳ 1. Added file...",
        " ⏳ 2. Synthesizing context & waiting for local LLM (90s limit)...",
        " ⏳ 3. Pushing to remote...",
        "",
        " Editor is temporarily locked. Please stand by..."
    }
    
    vim.api.nvim_buf_set_lines(0, 0, -1, false, waiting_msg)
    vim.cmd('redraw') 
    
    -- ==========================================================
    -- THE BLOCKING WORK (Using the Hybrid Payload)
    -- ==========================================================
    local commit_message = ""
    local used_model = "None (Manual / Fallback)"

    if vim.fn.executable('ollama') == 1 then
        local git_commit_prompt = "Generate a concise but descriptive git commit message for the following changes. " ..
                  "The message should be in the present tense and not end with a period. " ..
                  "Focus on the overarching structure from the statistics and the content of the detailed changes. " ..
                  "Respond with ONLY the commit message, nothing else:\n\n{input_text}"

        -- Pass the same dynamic context size down to scripts/ai.py so Ollama
        -- does not silently fall back to a smaller default context window.
        local command = string.format('ai-commit --format plain --ctx %d --prompt %s',
                                      max_ctx, vim.fn.shellescape(git_commit_prompt))

        local raw_ai_output = vim.fn.system(command, hybrid_payload)
        
        -- Split output to separate the message from the model name
        local output_parts = vim.split(raw_ai_output, "\n__MODEL_DELIMITER__\n")
        commit_message = vim.fn.trim(output_parts[1] or "")
        
        if #output_parts > 1 then
            used_model = vim.fn.trim(output_parts[2])
        end
        
        if commit_message == "" or string.match(commit_message, "^Error:") then
            commit_message = "Update " .. file_name
        end
    else
        commit_message = "Update " .. file_name
    end

    -- Perform git commit and push
    local git_commit = vim.fn.system('git commit -m ' .. vim.fn.shellescape(commit_message))
    local git_push = vim.fn.system('git push')

    -- ==========================================================
    -- 4. FINAL UPDATE: Replace waiting text with actual results
    -- ==========================================================
    local output = "Git Add Output:\n" .. git_add ..
                   "\nGit Commit Output:\n" .. git_commit .. 
                   "\nGit Push Output:\n" .. git_push ..
                   "\n\n===========================================================" ..
                   "\n 📝 Message Used: " .. commit_message ..
                   "\n 🤖 Model Used: " .. used_model ..
                   "\n 💡 Press 'q' or type :q to exit this panel." ..
                   "\n==========================================================="
    
    vim.api.nvim_buf_set_lines(0, 0, -1, false, vim.split(output, '\n'))
    
    -- Set up a key mapping to easily close this split
    vim.api.nvim_buf_set_keymap(0, 'n', 'q', ':q<CR>', { noremap = true, silent = true })
end

function get_pipulate_root()
    local env_root = os.getenv("PIPULATE_ROOT")
    if env_root and env_root ~= "" and vim.fn.isdirectory(env_root) == 1 then
        return env_root
    end
    local pipulate_home = vim.fn.expand("~/pipulate")
    if vim.fn.filereadable(pipulate_home .. "/init.lua") == 1 then
        return pipulate_home
    end
    return vim.fn.expand("~/repos/pipulate")
end

function reload_config()
    -- Clear existing mappings
    vim.cmd('mapclear')
    vim.cmd('mapclear!')

    -- Unload the current configuration
    for name, _ in pairs(package.loaded) do
        if name:match('^user') or name:match('^plugins') then
            package.loaded[name] = nil
        end
    end

    -- Re-source the init.lua file from PIPULATE_ROOT (falling back to ~/pipulate or ~/repos/pipulate)
    local init_path = get_pipulate_root() .. "/init.lua"
    vim.cmd('source ' .. vim.fn.fnameescape(init_path))

    -- Force re-evaluation of all autocmds
    vim.cmd('doautocmd VimEnter')

    -- Get current date and time
    local datetime = os.date("%Y-%m-%d %H:%M:%S")
    
    -- Notify with datetime
    vim.notify("Configuration reloaded at " .. datetime, vim.log.levels.INFO)
end

function correct_misspelling()
    vim.cmd('normal! [s1z=e')
end

function toggle_line_numbers()
    local next_state = not vim.opt.number:get()
    vim.opt.relativenumber = next_state
    vim.opt.number = next_state
    if next_state then
        vim.notify("Line numbers enabled", vim.log.levels.INFO)
    else
        vim.notify("Line numbers disabled", vim.log.levels.INFO)
    end
end

function toggle_word_wrap()
    local next_state = not vim.opt.wrap:get()
    vim.opt.wrap = next_state
    if next_state then
        vim.notify("Word wrap enabled (soft wrap)", vim.log.levels.INFO)
    else
        vim.notify("Word wrap disabled (nowrap)", vim.log.levels.INFO)
    end
end

function toggle_text_width()
    -- THE MARGIN RELEASE: flip between tw=80 (journal prose auto-wraps at
    -- the column) and tw=0 (long lines run free for context.txt lines
    -- and other wide-format work). One key, no :set incantation, and the
    -- notify always tells you which regime you are typing in.
    if vim.opt.textwidth:get() == 0 then
        vim.opt.textwidth = 80
        vim.notify("textwidth = 80 (prose wraps)", vim.log.levels.INFO)
    else
        vim.opt.textwidth = 0
        vim.notify("textwidth = 0 (margins released)", vim.log.levels.INFO)
    end
end

function toggle_spell_check()
    vim.opt.spell = not vim.opt.spell._value
    if vim.opt.spell._value then
        vim.notify("Spell check enabled", vim.log.levels.INFO)
    else
        vim.notify("Spell check disabled", vim.log.levels.INFO)
    end
end

function bold_dialogue_speaker()
    -- Move to the beginning of the current line and up one line
    vim.cmd('normal! 0k')

    -- Search for the next line containing a valid speaker name followed by ':'
    -- but not starting with "Step" followed by a number and colon
    local colon_line = vim.fn.search('^\\(Step\\s*\\d\\+:\\)\\@!\\([A-Za-z0-9][A-Za-z0-9 .-]*:\\)', 'nW')
    if colon_line == 0 then
        vim.notify("No valid dialogue found", vim.log.levels.WARN)
        return
    end

    -- Get the line content
    local line = vim.fn.getline(colon_line)

    -- Find the position of the colon
    local colon_pos = string.find(line, ":")
    if not colon_pos then
        vim.notify("Unexpected error: colon not found", vim.log.levels.ERROR)
        return
    end

    -- Extract the speaker part (text before the colon)
    local speaker = string.sub(line, 1, colon_pos - 1)

    -- Check if the speaker is already bolded
    if speaker:match("^%*%*.*%*%*$") then
        vim.notify("Speaker already bolded", vim.log.levels.INFO)
        return
    end

    -- Check if the speaker is no more than 7 words
    local word_count = select(2, speaker:gsub("%S+", "")) + 1
    if word_count > 7 then
        vim.notify("Speaker name is more than 7 words, skipping", vim.log.levels.WARN)
        return
    end

    -- Replace the line with the bolded version
    local new_line = "**" .. speaker .. "**" .. string.sub(line, colon_pos)
    vim.fn.setline(colon_line, new_line)

    -- Move the cursor to just after the closing asterisks and one word forward
    vim.fn.cursor(colon_line, #speaker + 4)
    vim.cmd('normal! w')

    vim.notify("Dialogue speaker bolded", vim.log.levels.INFO)
end

function escape_html_tags()
    -- Search for the next HTML-like tag pattern
    local found = vim.fn.search('<[^>]*>', 'W')
    if found == 0 then
        vim.notify("No HTML-like tags found", vim.log.levels.INFO)
        return
    end
    
    -- Save current register contents
    local save_reg = vim.fn.getreg('"')
    local save_regtype = vim.fn.getregtype('"')
    
    -- Use visual mode to select the tag
    vim.cmd('normal! v')
    vim.fn.search('>', 'W')
    vim.cmd('normal! y')
    
    -- Get the yanked text (the tag)
    local tag = vim.fn.getreg('"')
    
    -- Restore register
    vim.fn.setreg('"', save_reg, save_regtype)
    
    -- Replace angle brackets with HTML entities
    local escaped_tag = tag:gsub('<', '&lt;'):gsub('>', '&gt;')
    
    -- Get the current cursor position and tag boundaries
    local start_row = vim.fn.line('.') - 1  -- 0-based index for API
    local start_col = vim.fn.col('.') - 1   -- 0-based index for API
    local end_row = start_row
    local end_col = start_col + #tag
    
    -- Get the current buffer
    local bufnr = vim.api.nvim_get_current_buf()
    
    -- Replace the tag directly in the buffer
    vim.api.nvim_buf_set_text(bufnr, start_row, start_col, end_row, end_col, {escaped_tag})
    
    -- Move the cursor to the end of the escaped tag
    vim.api.nvim_win_set_cursor(0, {start_row + 1, start_col + #escaped_tag})
    
    vim.notify("HTML tag escaped", vim.log.levels.INFO)
end


function add_liquid_raw_tags()
    -- Get cursor position before any operations
    local cursor_pos = vim.fn.getcurpos()
    local cursor_col = cursor_pos[3]

    -- Search for a line containing "{{"
    local line_num = vim.fn.search('{{', 'n')
    if line_num == 0 then
        vim.notify("No lines with '{{' found", vim.log.levels.INFO)
        return
    end
    
    -- Move to that line but maintain column position
    vim.api.nvim_win_set_cursor(0, {line_num, cursor_col - 1})
    
    -- Temporarily set textwidth to 0
    local old_tw = vim.opt.textwidth
    vim.opt.textwidth = 0
    
    -- Insert the raw tag at current cursor position
    vim.cmd('normal! i{% raw %}')
    
    -- Go to the end of the line and add the endraw tag
    vim.cmd('normal! A{% endraw %}')
    
    -- Restore the original textwidth
    vim.opt.textwidth = old_tw
    
    -- Move to the beginning of the next line
    vim.cmd('normal! 0j')
    
    vim.notify("Added raw tags around liquid syntax", vim.log.levels.INFO)
end

function jump_next_active_chop()
    -- Search forward for the next line that is not purely blank 
    -- and does not start with a comment hash.
    -- Pattern: ^\s*[^ \t#] (Start of line, optional space, then anything not space/tab/hash)
    local found = vim.fn.search('^\\s*[^ \\t#]', 'W')
    
    if found == 0 then
        vim.notify("No active chop lines found below cursor", vim.log.levels.INFO)
    else
        -- Center the screen on the found line to maintain optimal visual context
        vim.cmd('normal! zz')
    end
end

function sync_to_bridge()
    -- Yank the visual selection to a temporary file on the Z640
    vim.cmd('normal! gvy')
    local text = vim.fn.getreg('"')
    local bridge_file = "/tmp/clipboard_bridge.txt"
    local f = io.open(bridge_file, "w")
    if f then
        f:write(text)
        f:close()
        vim.notify("Bridge Prepared: /tmp/clipboard_bridge.txt", vim.log.levels.INFO)
    end
end

function select_current_article()
    -- Save the current cursor position to restore if we fail
    local original_pos = vim.fn.getcurpos()
    
    -- Search backwards for the start marker. 
    -- 'b' = backward, 'c' = accept at cursor, 'W' = don't wrap around the file
    local start_line = vim.fn.search('^--- BEGIN NEW ARTICLE ---$', 'bcW')
    
    if start_line == 0 then
        vim.notify("Upper bound not found. Are you inside an article?", vim.log.levels.WARN)
        vim.fn.setpos('.', original_pos)
        return
    end
    
    -- Move cursor to the start line to ensure we find the *next* ending marker 
    -- specifically belonging to this block, not a previous one.
    vim.api.nvim_win_set_cursor(0, {start_line, 0})
    
    -- Search forwards for the end marker. 
    -- The ^!!!$ pattern ensures it matches the standalone floor marker, ignoring inline prose.
    local end_line = vim.fn.search('^!!!$', 'W')
    
    if end_line == 0 then
        vim.notify("Lower bound (!!!) not found.", vim.log.levels.WARN)
        vim.fn.setpos('.', original_pos)
        return
    end
    
    -- Execute the visual selection: 
    -- Move to start line, enter Line-wise Visual mode (V), move to one line BEFORE the end marker.
    vim.api.nvim_win_set_cursor(0, {start_line, 0})
    vim.cmd('normal! V')
    -- Subtract 1 to keep the '!!!' out of the clipboard payload
    vim.api.nvim_win_set_cursor(0, {end_line - 1, 0})
    
    vim.notify("Article stage selected.", vim.log.levels.INFO)
end

-- THE OAUTH SCRUB (\x in visual mode): shape-based redaction for pasted
-- terminal output, and the deliberate OPPOSITE POLARITY of pii_substitutions.txt.
--
--   pii_substitutions.txt -> IDENTITY. Client names. Recurring literals, so one
--     table entry covers every future article. Applied at publish time.
--   scrub_oauth           -> EPHEMERA. One-time, high-entropy values minted
--     fresh on every OAuth run. A substitution table can NEVER catch up with
--     these -- by the time a value is in the table, it is already published.
--     Applied at PASTE time, by shape, on the selection under the cursor.
--
-- THE MASK IS NOT COSMETIC. TRIPWIRE_FIXTURE_MARKERS in prompt_foo.py exempts a
-- credential-shaped match when a marker word ("redacted" among them) rides
-- INSIDE the matched value. So "<redacted:40>" passes the secrets tripwire by
-- construction, and every future compile carrying the scrubbed article compiles
-- clean. A mask spelled "XXXXXXXX" would be a landmine: a redaction that still
-- blocks the gate is exactly the four-copies-of-a-fixture conviction.
--
-- THE LENGTH IS THE TEACHING CONTENT: a reader learns a dynamic-registration
-- client_id is 40 chars and a PKCE challenge is 43, without ever seeing one.
--
-- IDEMPOTENT BY CONSTRUCTION: every value pattern excludes "<", so an already
-- masked value cannot re-match. Running twice reports 0 the second time, which
-- is an honest reading rather than a silent no-op.
--
-- WHAT IT DELIBERATELY DOES NOT TOUCH: home paths, hostnames, vendor slot names,
-- and the ephemeral loopback port in redirect_uri. The first three are identity
-- and belong to the other lane; the port is a random local listener that leaks
-- nothing and teaches the reader how the redirect catcher works.
function scrub_oauth()
    local first = vim.fn.line("'<")
    local last = vim.fn.line("'>")
    if first == 0 or last == 0 or last < first then
        vim.notify("scrub: no visual selection found", vim.log.levels.WARN)
        return
    end
    local secret_params = {
        "client_id", "client_secret", "code_challenge", "code_verifier",
        "code", "state", "access_token", "refresh_token", "id_token",
        "token", "api_key", "apikey", "signature", "nonce",
        "assertion", "session",
    }
    local lines = vim.api.nvim_buf_get_lines(0, first - 1, last, false)
    local hits = 0
    local function mask(n)
        return "<redacted:" .. n .. ">"
    end
    for i, line in ipairs(lines) do
        for _, name in ipairs(secret_params) do
            -- Query-string form: ?name=VALUE or &name=VALUE
            -- The leading [?&] is what keeps "code" from eating
            -- "code_challenge_method=S256"; the literal "=" does the rest.
            line = line:gsub("([?&]" .. name .. "=)([^&%s\"'<>]+)", function(head, val)
                hits = hits + 1
                return head .. mask(#val)
            end)
            -- Quoted JSON form: "name": "VALUE"
            line = line:gsub("(\"" .. name .. "\"%s*:%s*\")([^\"<]+)(\")", function(head, val, tail)
                hits = hits + 1
                return head .. mask(#val) .. tail
            end)
        end
        -- Authorization header form: Bearer VALUE
        line = line:gsub("([Bb]earer%s+)([%w%-%._~%+/=]+)", function(head, val)
            hits = hits + 1
            return head .. mask(#val)
        end)
        -- VENDOR PREFIX SHAPES -- the half of prompt_foo.py's SECRET_TRIPWIRES
        -- list that belongs one lane upstream. Safe here for the same reason it
        -- is safe there: every rule below matches a VENDOR-ISSUED PREFIX, never
        -- an English word. "GOCSPX-" cannot occur in prose except while quoting
        -- a credential, so this has no false-positive surface in a journal.
        -- DELIBERATELY ABSENT: a bare-assignment form (name = value) driven by
        -- the secret_params list above. That list carries "code", "state",
        -- "token" and "session" -- ordinary English AND ordinary Python
        -- identifiers -- and a journal about writing code is full of lines like
        -- "session = requests.Session()". Masking those is the PII GREEDY-NAME
        -- INCIDENT in a new costume, and that incident is why the substitution
        -- table was emptied once already. If an assignment form is ever added it
        -- takes a SEPARATE compound-only name list (client_secret,
        -- signing_secret, app_secret) and a 20-character floor, exactly as
        -- prompt_foo.py already spells it.
        -- RUNS AFTER Bearer ON PURPOSE: "Bearer ghp_..." must be masked once as
        -- a whole value, not twice as prefix plus remainder.
        -- IDEMPOTENT: the value class is POSITIVE and excludes "<", so an
        -- already-masked value cannot re-match. LUA PATTERNS, NOT REGEX: there
        -- is no {n} quantifier here, because {} are literal characters in Lua
        -- and a rule spelled with them silently never fires.
        -- Preserve only the stable family discriminator. Vendor-issued routing
        -- segments left before <redacted:N> can still satisfy a downstream
        -- minimum-length tripwire, which defeats the marker-inside-value rule.
        local vendor_prefixes = {
            "GOCSPX%-",                 -- Google OAuth client secret
            "xox[baprs]%-",             -- Slack token family
            "gh[pousr]_",               -- GitHub PAT family
            "sk%-ant%-",                -- Anthropic
            "AKIA",                     -- AWS access key id
        }
        for _, prefix in ipairs(vendor_prefixes) do
            line = line:gsub("(" .. prefix .. ")([%w%-_%./+=]+)", function(head, val)
                if #val < 8 then return head .. val end
                hits = hits + 1
                return head .. mask(#val)
            end)
        end
        lines[i] = line
    end
    -- THE DISCRIMINATION QUESTION, answered: a scrub that found nothing and a
    -- scrub that never ran must never print the same thing. Zero is reported
    -- LOUDLY, at WARN, because "I selected the wrong lines" and "this block was
    -- already clean" are the two worlds this line exists to separate.
    if hits == 0 then
        vim.notify("scrub: 0 values redacted -- selection already clean, or no known shapes in it", vim.log.levels.WARN)
        return
    end
    vim.api.nvim_buf_set_lines(0, first - 1, last, false, lines)
    vim.notify(string.format("scrub: %d value(s) redacted across %d line(s)", hits, last - first + 1), vim.log.levels.INFO)
end

-- THE MATHJAX SINGLE-TO-DOUBLE DOLLAR CONVERTER (\d in normal & visual mode):
-- Kramdown/Jekyll requires double-dollar delimiters even for inline MathJax,
-- whereas LLMs frequently emit single-dollar spans. A blind regex corrupts
-- currency, shell variables, or already-doubled spans on the same line.
-- NOTE: ASCII 36 (\36) and ASCII 96 (\96) are used in string literals below so
-- web chat LaTeX/Markdown renderers never mangle this file in transit.
local function is_mathjax_span(masked_line, s_pos, e_pos)
    local expr = masked_line:sub(s_pos + 1, e_pos - 1)
    if #expr == 0 or #expr > 120 then
        return false
    end
    if expr:match("^%s") or expr:match("%s\36") then
        return false
    end
    local prev_ch = s_pos > 1 and masked_line:sub(s_pos - 1, s_pos - 1) or ""
    local next_ch = e_pos < #masked_line and masked_line:sub(e_pos + 1, e_pos + 1) or ""
    if prev_ch:match("[%w\\\36]") then
        return false
    end
    if next_ch:match("[%w\36]") then
        return false
    end
    if expr:match("^%d[%d,%.]*/%a%a+") or expr:match("^%d[%d,%.]*[kKmMbB]?%s+%a%a+") then
        return false
    end
    if expr:find("\\", 1, true) then
        return true
    end
    if expr:find("[%^_=<>&+]") then
        return true
    end
    if expr:match("^%a'?\36") or expr:match("^%d+/%d+\36") or expr:match("^%a/%a\36") then
        return true
    end
    if expr:match("^%a+%b()\36") then
        return true
    end
    if expr:match("^[%w_]+%s*[%-%+%*/]%s*[%w_]+\36") then
        return true
    end
    return false
end

function transform_mathjax_line(line)
    local shadow = line
    shadow = shadow:gsub("\96+[^\96]*\96+", function(m)
        return string.rep("#", #m)
    end)
    shadow = shadow:gsub("%\36%\36.-%\36%\36", function(m)
        return string.rep("#", #m)
    end)
    shadow = shadow:gsub("%\36%\36+", function(m)
        return string.rep("#", #m)
    end)
    local positions = {}
    local init = 1
    while true do
        local p = shadow:find("%\36", init)
        if not p then break end
        table.insert(positions, p)
        init = p + 1
    end
    local matches = {}
    local idx = 1
    while idx < #positions do
        local s_pos = positions[idx]
        local e_pos = positions[idx + 1]
        if is_mathjax_span(shadow, s_pos, e_pos) then
            table.insert(matches, {
                s_pos = s_pos,
                e_pos = e_pos,
                expr = line:sub(s_pos, e_pos),
            })
            idx = idx + 2
        else
            idx = idx + 1
        end
    end
    if #matches == 0 then
        return line, matches
    end
    local out = {}
    local cursor = 1
    for _, m in ipairs(matches) do
        table.insert(out, line:sub(cursor, m.s_pos - 1))
        table.insert(out, "\36\36")
        table.insert(out, line:sub(m.s_pos + 1, m.e_pos - 1))
        table.insert(out, "\36\36")
        cursor = m.e_pos + 1
    end
    table.insert(out, line:sub(cursor))
    return table.concat(out), matches
end

local function build_fenced_line_map(lines)
    local fenced = {}
    local in_fence = false
    local fence_char = nil
    for i, line in ipairs(lines) do
        local opener = line:match("^%s*(\96\96\96+)") or line:match("^%s*(~~~+)")
        if opener then
            local ch = opener:sub(1, 1)
            if not in_fence then
                in_fence = true
                fence_char = ch
                fenced[i] = true
            elseif ch == fence_char then
                fenced[i] = true
                in_fence = false
                fence_char = nil
            else
                fenced[i] = true
            end
        elseif in_fence then
            fenced[i] = true
        end
    end
    return fenced
end

function find_next_mathjax_candidate()
    local lines = vim.api.nvim_buf_get_lines(0, 0, -1, false)
    local total = #lines
    if total == 0 then return end
    local fenced = build_fenced_line_map(lines)
    local cur_pos = vim.api.nvim_win_get_cursor(0)
    local cur_line = cur_pos[1]
    local cur_col = cur_pos[2] + 1  -- 1-based byte index

    -- Check remaining candidates after cursor on current line first
    if not fenced[cur_line] then
        local _, matches = transform_mathjax_line(lines[cur_line])
        for idx, m in ipairs(matches) do
            if m.s_pos > cur_col then
                vim.api.nvim_win_set_cursor(0, {cur_line, m.s_pos - 1})
                vim.cmd('normal! zz')
                vim.notify(string.format("mathjax: %s (%d/%d on line %d) -- V then \\d to double", m.expr, idx, #matches, cur_line), vim.log.levels.INFO)
                return
            end
        end
    end

    -- Scan forward through the buffer, wrapping around once if needed
    for offset = 1, total do
        local lnum = ((cur_line - 1 + offset) % total) + 1
        if not fenced[lnum] then
            local _, matches = transform_mathjax_line(lines[lnum])
            if #matches > 0 then
                local m = matches[1]
                local wrapped = lnum <= cur_line and " [wrapped]" or ""
                vim.api.nvim_win_set_cursor(0, {lnum, m.s_pos - 1})
                vim.cmd('normal! zz')
                vim.notify(string.format("mathjax: %s (1/%d on line %d)%s -- V then \\d to double", m.expr, #matches, lnum, wrapped), vim.log.levels.INFO)
                return
            end
        end
    end
    vim.notify("mathjax: 0 single-\36 candidates found in buffer", vim.log.levels.WARN)
end

function double_mathjax_dollars()
    local first = vim.fn.line("'<")
    local last = vim.fn.line("'>")
    if first == 0 or last == 0 or last < first then
        vim.notify("mathjax: no visual selection found", vim.log.levels.WARN)
        return
    end
    local vmode = vim.fn.visualmode()
    local all_lines = vim.api.nvim_buf_get_lines(0, 0, -1, false)
    local fenced = build_fenced_line_map(all_lines)
    local lines = vim.api.nvim_buf_get_lines(0, first - 1, last, false)
    local hits = 0
    local changed_lines = 0

    -- Single-line character-wise visual selection ('v'): respect exact range
    -- and allow manual override when the operator directly highlights a span.
    if vmode == "v" and first == last and #lines == 1 then
        local line = lines[1]
        local s_col = vim.fn.col("'<")
        local e_col = vim.fn.col("'>")
        if e_col > #line then e_col = #line end
        local sub = line:sub(s_col, e_col)
        local new_sub, matches = transform_mathjax_line(sub)
        if #matches > 0 then
            hits = #matches
            changed_lines = 1
            lines[1] = line:sub(1, s_col - 1) .. new_sub .. line:sub(e_col + 1)
        else
            local prev_ch = s_col > 1 and line:sub(s_col - 1, s_col - 1) or ""
            local next_ch = e_col < #line and line:sub(e_col + 1, e_col + 1) or ""
            if sub:match("^%\36[^%\36]+%\36\36") and sub ~= "\36\\rightarrow\36" and prev_ch ~= "\36" and next_ch ~= "\36" then
                hits = 1
                changed_lines = 1
                lines[1] = line:sub(1, s_col - 1) .. "\36" .. sub .. "\36" .. line:sub(e_col + 1)
            end
        end
    else
        for i, line in ipairs(lines) do
            local buf_lnum = first + i - 1
            if not fenced[buf_lnum] then
                local new_line, matches = transform_mathjax_line(line)
                if #matches > 0 then
                    lines[i] = new_line
                    hits = hits + #matches
                    changed_lines = changed_lines + 1
                end
            end
        end
    end

    if hits == 0 then
        vim.notify("mathjax: 0 expressions doubled -- already \36\36...\36\36 or no single-\36 math in selection", vim.log.levels.WARN)
        return
    end
    vim.api.nvim_buf_set_lines(0, first - 1, last, false, lines)
    vim.notify(string.format("mathjax: %d expression(s) doubled across %d line(s)", hits, changed_lines), vim.log.levels.INFO)
end

-- THE MARKDOWN NESTING & FENCE HYGIENE TOOL (\f in normal & visual mode):
-- Finds and heals the Markdown syntax glitches that break Neovim's @Spell
-- highlighting: naked opening triple-backtick fences, 4+ backtick runs,
-- cross-nested bold/italic + inline-code spans (**`code**`, **text `code**`,
-- *text `code*`, `**code`**), and mismatched **token* spans, plus locates
-- any remaining unbalanced single backtick on a prose line.
local function classify_markdown_fences(lines)
    local state = {}
    local in_fence = false
    local fence_char = nil
    for i, line in ipairs(lines) do
        local bt_run, bt_lang = line:match("^%s*(\96\96\96+)([^%s\96]*)%s*$")
        local tl_run, tl_lang = line:match("^%s*(~~~+)([^%s~]*)%s*$")
        local run = bt_run or tl_run
        local lang = bt_run and bt_lang or tl_lang
        if run and #run == 3 then
            local ch = run:sub(1, 1)
            if not in_fence then
                in_fence = true
                fence_char = ch
                if ch == "\96" and (not lang or lang == "") then
                    state[i] = "naked_opener"
                else
                    state[i] = "opener"
                end
            elseif ch == fence_char and (not lang or lang == "") then
                state[i] = "closer"
                in_fence = false
                fence_char = nil
            else
                state[i] = "inside"
            end
        elseif in_fence then
            state[i] = "inside"
        else
            state[i] = "prose"
        end
    end
    return state
end

function transform_markdown_glitch_line(line, fence_state)
    local hits = 0
    local notes = {}
    if fence_state == "inside" or fence_state == "opener" or fence_state == "closer" then
        return line, hits, notes, nil
    end
    if fence_state == "naked_opener" then
        local indent, ticks = line:match("^(%s*)(\96\96\96+)%s*$")
        if ticks then
            return indent .. "\96\96\96text", 1, {"naked fence -> \96\96\96text"}, #indent + 1
        end
    end
    local out = line
    local first_col = nil

    -- 1. Replace 4+ backtick runs with [N-backticks]
    local q_pos = out:find("\96\96\96\96+")
    if q_pos then
        if not first_col or q_pos < first_col then first_col = q_pos end
        out = out:gsub("\96\96\96\96+", function(m)
            hits = hits + 1
            local repl = string.format("[%d-backticks]", #m)
            table.insert(notes, repl)
            return repl
        end)
    end

    -- 2. Fix bold + inline-code right-boundary cross-nesting: **`code**` and **text `code**`
    local b1 = out:find("%*%*\96[^\96*\n]+%*%*\96")
    if b1 then
        if not first_col or b1 < first_col then first_col = b1 end
        out = out:gsub("%*%*(\96[^\96*\n]+)%*%*\96", function(code)
            hits = hits + 1
            table.insert(notes, "**\96...\96**")
            return "**" .. code .. "\96**"
        end)
    end
    local b2 = out:find("%*%*[^\96*\n]-\96[^\96*\n]+%*%*\96")
    if b2 then
        if not first_col or b2 < first_col then first_col = b2 end
        out = out:gsub("(%*%*[^\96*\n]-)(\96[^\96*\n]+)%*%*\96", function(head, code)
            hits = hits + 1
            table.insert(notes, "**...\96...\96**")
            return head .. code .. "\96**"
        end)
    end

    -- 3. Fix bold + inline-code left-boundary cross-nesting: `**code`**
    local b3 = out:find("\96%*%*[^\96*\n]+\96%*%*")
    if b3 then
        if not first_col or b3 < first_col then first_col = b3 end
        out = out:gsub("\96%*%*([^\96*\n]+)\96%*%*", function(inner)
            hits = hits + 1
            table.insert(notes, "**\96...\96**")
            return "**\96" .. inner .. "\96**"
        end)
    end

    -- 4. Fix italic + inline-code right-boundary cross-nesting: *text `code*` -> *text `code`*
    local outside_code = out:gsub("\96+[^\96]*\96+", function(m) return string.rep(" ", #m) end)
    local outside_no_bold = outside_code:gsub("%*%*+", function(m) return string.rep(" ", #m) end)
    outside_no_bold = outside_no_bold:gsub("^%s*%*%s+", function(m) return string.rep(" ", #m) end)
    local _, single_stars = outside_no_bold:gsub("%*", "")
    if single_stars % 2 == 1 then
        local i1 = out:find("\96[^\96*\n]+%*\96")
        if i1 then
            if not first_col or i1 < first_col then first_col = i1 end
            out = out:gsub("\96([^\96*\n]+)%*\96", function(inner)
                hits = hits + 1
                table.insert(notes, "*...\96...\96*")
                return "\96" .. inner .. "\96*"
            end, 1)
        end
    end

    -- 5. Fix mismatched **token* -> *token* (e.g. (PIE **h2r-ti-*))
    local m_pos = out:find("%*%*[^%*\96%s]+%*[%)%].,;:!?%s]")
    if m_pos then
        if not first_col or m_pos < first_col then first_col = m_pos end
        out = out:gsub("%*%*([^%*\96%s]+)%*([%)%].,;:!?%s])", function(inner, tail)
            hits = hits + 1
            table.insert(notes, "**...* -> *...*")
            return "*" .. inner .. "*" .. tail
        end)
    end

    -- 6. Detect any remaining unbalanced single backtick on a prose line
    local stripped_pairs = out:gsub("\96+[^\96]+\96+", function(m) return string.rep(" ", #m) end)
    local stray_pos = stripped_pairs:find("\96")
    if stray_pos then
        if not first_col or stray_pos < first_col then first_col = stray_pos end
        table.insert(notes, "unbalanced \96")
    end

    return out, hits, notes, first_col
end

function find_next_markdown_glitch()
    local lines = vim.api.nvim_buf_get_lines(0, 0, -1, false)
    local total = #lines
    if total == 0 then return end
    local states = classify_markdown_fences(lines)
    local cur_pos = vim.api.nvim_win_get_cursor(0)
    local cur_line = cur_pos[1]

    for offset = 1, total do
        local lnum = ((cur_line - 1 + offset) % total) + 1
        local _, hits, notes, col = transform_markdown_glitch_line(lines[lnum], states[lnum])
        if hits > 0 or #notes > 0 then
            local wrapped = lnum <= cur_line and " [wrapped]" or ""
            vim.api.nvim_win_set_cursor(0, {lnum, math.max(0, (col or 1) - 1)})
            vim.cmd('normal! zz')
            vim.notify(string.format("md-glitch: %s on line %d%s -- V then \\f to fix", table.concat(notes, ", "), lnum, wrapped), vim.log.levels.INFO)
            return
        end
    end
    vim.notify("md-glitch: 0 Markdown nesting/fence glitches found in buffer", vim.log.levels.INFO)
end

function fix_markdown_glitches()
    local first = vim.fn.line("'<")
    local last = vim.fn.line("'>")
    if first == 0 or last == 0 or last < first then
        vim.notify("md-glitch: no visual selection found", vim.log.levels.WARN)
        return
    end
    local all_lines = vim.api.nvim_buf_get_lines(0, 0, -1, false)
    local states = classify_markdown_fences(all_lines)
    local lines = vim.api.nvim_buf_get_lines(0, first - 1, last, false)
    local total_hits = 0
    local changed_lines = 0
    local unfixed_lnum = nil
    local unfixed_col = nil

    for i, line in ipairs(lines) do
        local buf_lnum = first + i - 1
        local new_line, hits, notes, col = transform_markdown_glitch_line(line, states[buf_lnum])
        if hits > 0 then
            lines[i] = new_line
            total_hits = total_hits + hits
            changed_lines = changed_lines + 1
        end
        if not unfixed_lnum then
            for _, n in ipairs(notes) do
                if n == "unbalanced \96" then
                    unfixed_lnum = buf_lnum
                    unfixed_col = col or 1
                end
            end
        end
    end

    if total_hits > 0 then
        vim.api.nvim_buf_set_lines(0, first - 1, last, false, lines)
    end
    if unfixed_lnum then
        vim.api.nvim_win_set_cursor(0, {unfixed_lnum, math.max(0, unfixed_col - 1)})
        vim.cmd('normal! zz')
        vim.notify(string.format("md-glitch: fixed %d glitch(es) across %d line(s); jumped to unbalanced \96 on line %d", total_hits, changed_lines, unfixed_lnum), vim.log.levels.WARN)
    elseif total_hits == 0 then
        vim.notify("md-glitch: 0 Markdown glitches found in selection", vim.log.levels.WARN)
    else
        vim.notify(string.format("md-glitch: %d glitch(es) healed across %d line(s)", total_hits, changed_lines), vim.log.levels.INFO)
    end
end
function sync_to_prompt()
    -- Yank the visual selection
    vim.cmd('normal! gvy')
    local text = vim.fn.getreg('"')
    
    -- Resolve prompt.md from the active Pipulate root
    local prompt_file = get_pipulate_root() .. "/prompt.md"
    
    -- Open the file in "w" (overwrite) mode. 
    -- Note: Change "w" to "a" if you'd rather append multiple chunks!
    local f = io.open(prompt_file, "w")
    if f then
        f:write(text)
        f:close()
        vim.notify("Prompt Extracted: " .. prompt_file, vim.log.levels.INFO)
    else
        vim.notify("Error: Could not open " .. prompt_file, vim.log.levels.ERROR)
    end
end

function mount_sandworm()
    -- THE MOUNT: \x saddles the worm at the cursor. On a blank line, the
    -- full ride template replaces it; on a non-blank line it inserts below,
    -- protecting existing prose. Either way the cursor lands in insert mode
    -- right after the speaker label -- the old i**Me**: feel, full saddle.
    local template = "**Me**: \n\n"
        .. "## THE AI-EDIT METHOD\n\n"
        .. "> Same commands, run twice, one change between them. Where the readings\n"
        .. "> differ is what the change did; the diff in the middle is the receipt.\n\n"
        .. "**1: BEFORE** (PROBE): \n\n"
        .. "```bash\n[Paste AI-provided \"Probe\" into command-line then copy-paste those results here.]\n```\n\n"
        .. "**2: AFTER** (NEXT CONTEXT): \n\n"
        .. "```text\n[Paste AI-provided \"Context\" into context.txt by using the context command.]\n```\n\n"
        .. "**3: CHANGE** (PATCHES): \n\n"
        .. "```diff\n[Copy AI-provided patch. Type: patch, app, d, m. Paste diff receipt here.]\n```\n\n"
        .. "Ignition: often \"exit\", \"nix develop\". Instructions may vary.\n\n"
        .. "**4: PROMPT**: \n\n"
        .. "[Does the AFTER reading support your prediction?]\n\n"
        .. "**5: DELIVERABLE**: \n\n"
        .. "[What does \"DONE\" look like?]"
    local row = vim.api.nvim_win_get_cursor(0)[1]
    local cur = vim.api.nvim_buf_get_lines(0, row - 1, row, false)[1] or ""
    local lines = vim.split(template, "\n")
    if cur:match("^%s*$") then
        vim.api.nvim_buf_set_lines(0, row - 1, row, false, lines)
        vim.api.nvim_win_set_cursor(0, {row, 0})
    else
        vim.api.nvim_buf_set_lines(0, row, row, false, lines)
        vim.api.nvim_win_set_cursor(0, {row + 1, 0})
    end
    vim.cmd('startinsert!')
end

function hop_off_sandworm()
    -- THE DISMOUNT: the fourth beat after Probe, Patch, Prompt. When a ride
    -- series reaches its stated goal, stage the canned wrap-up prompt above
    -- the current article's !!! floor: VERIFY, BANK, DANGLING, SEED.
    local original_pos = vim.fn.getcurpos()
    local start_line = vim.fn.search('^--- BEGIN NEW ARTICLE ---$', 'bcW')
    if start_line == 0 then
        vim.notify("Not inside an article (no BEGIN marker above).", vim.log.levels.WARN)
        vim.fn.setpos('.', original_pos)
        return
    end
    vim.api.nvim_win_set_cursor(0, {start_line, 0})
    local end_line = vim.fn.search('^!!!$', 'W')
    if end_line == 0 then
        vim.notify("Lower bound (!!!) not found.", vim.log.levels.WARN)
        vim.fn.setpos('.', original_pos)
        return
    end
    local dismount = "Hop off the ride. This ride's stated goal is reached -- dismount.\n"
        .. "This is the NOTARY BEAT: the ride ends here, is witnessed here, and is\n"
        .. "sealed here. Answer all seven beats, briefly:\n\n"
        .. "0. **TL;DR**: a short, dry, neutral abstract for the TOP of the published\n"
        .. "   article -- written for an unfamiliar reader or AI summarizer who has\n"
        .. "   never seen this system. No hype, no insider handles unexplained.\n"
        .. "1. VERIFY: restate the goal from the top of this article and confirm\n"
        .. "   (or deny) it was met, citing THIS compile's receipts, not memory.\n"
        .. "   Name any ignition this ride required that never fired -- an AFTER\n"
        .. "   tap taken without one is a stale BEFORE wearing the AFTER's label.\n"
        .. "2. BANK: name everything that graduates -- rule, earmark, todo, pin --\n"
        .. "   as SEARCH/REPLACE patch cars against raw source present in THIS\n"
        .. "   context (Target line inside the fence, one car per commit story),\n"
        .. "   deletions included. A 'paste-ready' line with no Target and no\n"
        .. "   SEARCH anchor is not banked; it is a hand edit the operator will\n"
        .. "   not make. These BANK cars are the ONLY patches a dismount emits.\n"
        .. "3. DANGLING: what carries forward unbanked? One line each, no essays.\n"
        .. "4. SEED: the context.txt lines (and TODO_SLUGS if narrative context is\n"
        .. "   needed) for the next ride's first compile.\n"
        .. "5. CLOSING: a closing summary for the BOTTOM of the article -- the\n"
        .. "   final take-away, tied to the book's larger arc where it fits\n"
        .. "   naturally, never forced. Storytelling over inventory.\n"
        .. "6. NOTARIZE: read the exact Deed line from THIS compile's final\n"
        .. "   QA ARCHIVE SEAL footer, outside the payload, not a quoted older\n"
        .. "   footer or a newest-file guess. It names the input archive, not\n"
        .. "   this later response or the generated Jekyll post. State verification\n"
        .. "   separately: only a verifier receipt naming that archive supports\n"
        .. "   a verified claim; otherwise say not independently verified here.\n"
        .. "   Count this Manifest's live-command receipts, including failures.\n"
        .. "   Quote only recorded digests, sizes and dates, naming their source;\n"
        .. "   filesystem mtime and fixed ZIP dates are not command timestamps.\n"
        .. "   Do not demand absent wc -c or dated-receipt fields. If the footer\n"
        .. "   is missing, say so; otherwise close with its exact Deed line.\n\n"
        .. "FINALITY: after beat 6, this discussion is CLOSED. Emit NO five-car\n"
        .. "train, NO probes, NO patches beyond the BANK cars of beat 2, and NO\n"
        .. "next-turn prompt beyond the SEED lines in beat 4. Any reader or model\n"
        .. "encountering this article later should treat it as a finished,\n"
        .. "notarized document -- an archive entry, not an open thread.\n"
    vim.api.nvim_buf_set_lines(0, end_line - 1, end_line - 1, false, vim.split(dismount, "\n"))
    vim.api.nvim_win_set_cursor(0, {end_line - 1, 0})
    vim.cmd('normal! zz')
    vim.notify("Dismount staged above the !!! floor.", vim.log.levels.INFO)
end

-- Map it to <leader>c (for "Clip to Bridge")
vim.api.nvim_set_keymap('v', '<leader>c', '<cmd>lua sync_to_bridge()<CR>', { noremap = true, silent = true })

--   __  __                   _                 
-- |  \/  | __ _ _ __  _ __ (_)_ __   __ _ ___ 
-- | |\/| |/ _` | '_ \| '_ \| | '_ \ / _` / __|
-- | |  | | (_| | |_) | |_) | | | | | (_| \__ \
-- |_|  |_|\__,_| .__/| .__/|_|_| |_|\__, |___/
--              |_|   |_|            |___/     

-- Mappings
local map = vim.api.nvim_set_keymap
local opts = { noremap = true, silent = true }

-- F2: Reload Neovim configuration
map('n', '<F2>', '<cmd>lua reload_config()<CR>', opts)

-- F3: Toggle spell check on/off
map('n', '<F3>', '<cmd>lua toggle_spell_check()<CR>', opts)

-- F4: Toggle soft word-wrap on/off (visual wrap without inserting newlines)
map('n', '<F4>', '<cmd>lua toggle_word_wrap()<CR>', opts)

-- F5 / <leader>t: Toggle textwidth 0 <-> 80 (the Margin Release / hard wrap)
map('n', '<F5>', '<cmd>lua toggle_text_width()<CR>', opts)
map('n', '<leader>t', '<cmd>lua toggle_text_width()<CR>', opts)

-- F6: Toggle line numbers/ruler on/off (both normal and relative)
map('n', '<F6>', '<cmd>lua toggle_line_numbers()<CR>', opts)

-- Leader key mappings
-- Text Processing
map('n', '<leader>s', '<cmd>lua correct_misspelling()<CR>', opts)  -- Spell correction
map('n', '<leader>q', '<cmd>lua escape_html_tags()<CR>', opts)  -- HTML tag escaping
map('n', '<leader>r', '<cmd>lua add_liquid_raw_tags()<CR>', opts)  -- Add Liquid raw tags
map('n', '<leader>d', '<cmd>lua find_next_mathjax_candidate()<CR>', opts)  -- Find next single-dollar MathJax candidate
map('n', '<leader>f', '<cmd>lua find_next_markdown_glitch()<CR>', opts)  -- Find next Markdown nesting/fence glitch

-- Dialogue Labelers
map('n', '<leader>b', '<cmd>lua bold_dialogue_speaker()<CR>', opts)  -- Bold dialogue speaker
map('n', '<leader>x', '<cmd>lua mount_sandworm()<CR>', opts) -- the human: mount the worm (full saddle at cursor) x for eXperiment
map('n', '<leader>m', 'i**Me**: ', opts) -- You
map('n', '<leader>n', 'i**Note**: ', opts) -- You
map('n', '<leader>i', 'i**' .. AI_LABEL .. '**: ', opts) -- AI dialogue label
map('n', '<leader>l', 'i**' .. AI_LABEL .. '**: ', opts) -- AI dialogue label (alias)

-- Git Operations
map('n', '<leader>g', '<cmd>lua git_commit_push()<CR>', opts)  -- Git commit and push

-- Journal and Notes
map('n', '<leader>j', '<cmd>lua new_journal_entry()<CR>', opts)  -- New journal entry

-- Text Cleanup
map('n', '<leader>w', '<cmd>%s/\\s\\+$//e<CR>', opts)  -- Remove trailing whitespace
map('n', '<leader>e', '<cmd>g/^\\n\\{4,}/d<CR>', opts)  -- Remove excessive blank lines (4+)

-- Navigation
map('n', '<leader>a', '<cmd>lua jump_next_active_chop()<CR>', opts)  -- Jump to next Active line (non-comment)

-- Article / Workflow Selection
map('n', '<leader>h', '<cmd>lua select_current_article()<CR>', opts)  -- Highlight (select) current article block
map('n', '<leader>z', '<cmd>lua hop_off_sandworm()<CR>', opts)  -- Hop off: stage the dismount wrap-up above !!!

-- Map it to <leader>p (for "Clip to Prompt")
vim.api.nvim_set_keymap('v', '<leader>p', '<cmd>lua sync_to_prompt()<CR>', { noremap = true, silent = true })
-- Map it to <leader>x (for "X out the secrets"). The ':<C-u>' idiom is load
-- bearing and is NOT the '<cmd>' spelling used by \c and \p above: '<cmd>' keeps
-- visual mode active, which leaves '< and '> pointing at the PREVIOUS selection.
-- Leaving visual mode via ':' is what sets those marks to the selection the
-- operator just made. \c and \p get away with '<cmd>' only because they call
-- 'normal! gvy' to reselect; a line-range edit has no such escape.
vim.api.nvim_set_keymap('v', '<leader>x', ':<C-u>lua scrub_oauth()<CR>', { noremap = true, silent = true })
vim.api.nvim_set_keymap('v', '<leader>d', ':<C-u>lua double_mathjax_dollars()<CR>', { noremap = true, silent = true })
vim.api.nvim_set_keymap('v', '<leader>f', ':<C-u>lua fix_markdown_glitches()<CR>', { noremap = true, silent = true })

-- Print a message to confirm init.lua is loaded
print("init.lua loaded successfully!")

-- ============================================================================
-- Leader Key Mappings Documentation
-- ============================================================================
-- This section documents all available leader key mappings in the configuration.
-- Leader key is set to '\' by default in Neovim.

-- Text Processing
-- <leader>s - Correct misspelling before cursor
-- <leader>b - Bold dialogue speaker in text
-- <leader>q - Escape HTML tags in text
-- <leader>r - Add Liquid {% raw %}/{% endraw %} tags around {{ content
-- <leader>d - Jump to next single-dollar MathJax candidate (skips code fences, double-dollar, and currency)
-- <leader>d (visual) - Convert single-dollar MathJax to double-dollar in selection (no double-doubling)
-- <leader>f - Jump to next Markdown nesting/fence glitch (naked fences, 4+ backticks, **/` cross-nesting, unbalanced `)
-- <leader>f (visual) - Heal Markdown nesting/fence glitches across selection and jump to any unbalanced `
-- <leader>t - Toggle textwidth 0 <-> 80 (the Margin Release; also F5)
-- <F2> - Reload init.lua configuration
-- <F3> - Toggle spell check on/off
-- <F4> - Toggle soft word-wrap on/off (wrap <-> nowrap)
-- <F5> - Toggle hard textwidth on/off (tw=80 <-> tw=0; also <leader>t)
-- <F6> - Toggle line numbers/ruler on/off (number & relativenumber)

-- Dialogue & Sandworm Ride Controls
-- <leader>x - Mount sandworm (stage full AI-Edit Method saddle at cursor)
-- <leader>z - Hop off sandworm (stage Notary Beat dismount above !!!)
-- <leader>m - Insert "**Me**: " speaker label
-- <leader>n - Insert "**Note**: " speaker label
-- <leader>i / <leader>l - Insert "**" .. AI_LABEL .. "**: " speaker label
-- <leader>x (visual) - Scrub OAuth/ephemeral secrets in selection

-- Git Operations
-- <leader>g - Git commit and push changes

-- Journal and Notes
-- <leader>j - Create a new journal entry

-- Text Cleanup
-- <leader>w - Remove trailing whitespace from all lines
-- <leader>e - Remove excessive blank lines (4 or more consecutive)

-- Navigation
-- <leader>a - Jump to the next Active (non-commented, non-blank) line

-- Article / Workflow Selection
-- <leader>h - Highlight (select) current article block
-- <leader>c (visual) - Sync selection to /tmp/clipboard_bridge.txt
-- <leader>p (visual) - Sync selection to $PIPULATE_ROOT/prompt.md
