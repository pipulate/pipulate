-- init.lua
--  _       _ _     _             
-- (_)_ __ (_) |_  | |_   _  __ _ 
-- | | '_ \| | __| | | | | |/ _` |
-- | | | | | | |_ _| | |_| | (_| |
-- |_|_| |_|_|\__(_)_|\__,_|\__,_|
--                                

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
    -- Automatically save the current buffer
    vim.cmd('w')

    -- Get the current buffer's file name (not full path)
    local file_name = vim.fn.expand('%:t')
    -- STEP 1: Add the file FIRST so we can measure the payload.
    local git_add = vim.fn.system('git add ' .. vim.fn.shellescape(file_name))
    
    -- STEP 2: Capture both the full diff and the high-level stat map.
    local git_diff = vim.fn.system('git diff --cached ' .. vim.fn.shellescape(file_name))
    local git_stat = vim.fn.system('git diff --cached --stat ' .. vim.fn.shellescape(file_name))
    
    -- Guard clause: If diff is empty, open split with warning and abort
    if git_diff == "" then
        vim.cmd('botright 20split git_output')
        vim.cmd('setlocal buftype=nofile bufhidden=hide noswapfile')
        vim.api.nvim_buf_set_lines(0, 0, -1, false, {"⚠️  No changes detected to commit."})
        vim.api.nvim_buf_set_keymap(0, 'n', 'q', ':q<CR>', { noremap = true, silent = true })
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
    
    local target_model = "gemma3:latest (Default)" 

    -- ==========================================================
    -- INSTANT DRAMATIC FEEDBACK: Open the split immediately
    -- ==========================================================
    vim.cmd('botright 20split git_output')
    vim.cmd('setlocal buftype=nofile bufhidden=hide noswapfile')
    
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

    -- Re-source the init.lua file from its new Pipulate location
    vim.cmd('source ~/repos/pipulate/init.lua')

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
    vim.opt.relativenumber = not vim.opt.relativenumber._value
    vim.opt.number = not vim.opt.number._value
end

function toggle_text_width()
    -- THE MARGIN RELEASE: flip between tw=80 (journal prose auto-wraps at
    -- the column) and tw=0 (long lines run free for adhoc.txt masthead art
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
    
    -- Search for the next line containing a valid speaker name followed by ': '
    -- but not starting with "Step" followed by a number and colon
    -- Updated pattern to include periods in speaker names
    local colon_line = vim.fn.search('^\\(Step\\s*\\d\\+:\\)\\@!\\([A-Za-z0-9][A-Za-z0-9 .-]*: \\)', 'nW')
    if colon_line == 0 then
        vim.notify("No valid dialogue found", vim.log.levels.WARN)
        return
    end

    -- Get the line content
    local line = vim.fn.getline(colon_line)
    
    -- Find the position of the colon followed by a space
    local colon_pos = string.find(line, ": ")
    if not colon_pos then
        vim.notify("Unexpected error: colon with space not found", vim.log.levels.ERROR)
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

function clean_gemini_markdown()
    -- Automatically enable wrap for visibility during the cleanup
    vim.opt.wrap = true
    
    -- Save the starting cursor position so we can return to it for each step
    local start_pos = vim.fn.getcurpos()
    
    -- Helper function to reset cursor, pause for the user, and execute
    local function execute_step(step_num, desc, cmd)
        -- Break the 'y' spam momentum and allow skipping
        local prompt = "\nReady for Step " .. step_num .. "/4: " .. desc .. " [Press <Enter> to start, 's' to skip, or 'q' to abort] "
        local user_input = vim.fn.input(prompt)
        
        if user_input:lower() == 'q' then
            print("\nAborted cleanup sequence.")
            return false
        elseif user_input:lower() == 's' then
            print("\nSkipped Step " .. step_num .. ".")
            return true -- Return true to continue to the next step without executing the regex
        end
        
        -- Return to the original starting line so '.,$' searches the same text block
        vim.fn.setpos('.', start_pos)
        
        -- Execute the replacement safely
        pcall(function() vim.cmd(cmd) end)
        return true
    end

    if not execute_step(1, "Remove excessive backslashes", [[.,$s/\\\([\-+\[\]_#\*.]\)/\1/gc]]) then return end
    if not execute_step(2, "Escape pipes in citations", [[.,$g/^\d\+\. /s/|/\\|/gc]]) then return end
    if not execute_step(3, "Tag ambiguous inline footnotes", [[.,$s/\s\+\zs\(1\d\d\|[1-9]\d\|[1-9]\)\ze\s\+/<sup>&<\/sup>/gc]]) then return end
    if not execute_step(4, "Wrap footnote numbers", [[.,$s/\([.):]\)\zs\(1\d\d\|[1-9]\d\|[1-9]\)\>\|\<\(1\d\d\|[1-9]\d\|[1-9]\)\ze[:,]\|\s\zs\(1\d\d\|[1-9]\d\|[1-9]\)\ze\s*$/<sup>&<\/sup>/gc]]) then return end

    print("\nGemini Deep Research cleanup complete!")
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

function sync_to_prompt()
    -- Yank the visual selection
    vim.cmd('normal! gvy')
    local text = vim.fn.getreg('"')
    
    -- Explicit path to your Pipulate prompt file
    local prompt_file = vim.fn.expand("~/repos/pipulate/prompt.md")
    
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
    -- THE MOUNT: \m saddles the worm at the cursor. On a blank line, the
    -- full ride template replaces it; on a non-blank line it inserts below,
    -- protecting existing prose. Either way the cursor lands in insert mode
    -- right after the speaker label — the old i**Me**: feel, full saddle.
    local template = "**Me**: \n\n"
        .. "**1: Probe**:\n\n"
        .. "```bash\n[Paste terminal output of running probe here]\n```\n\n"
        .. "**2: Context**:\n\n"
        .. "```text\n[Paste entire `adhoc.txt` here]\n```\n\n"
        .. "**3: Patches**: [patch, app, d, m, patch, app, d, m...]\n\n"
        .. "```diff\n[Paste all diffs drag-copied from terminal here]\n```\n\n"
        .. "**4: Ignition**: [make the patched code RUN, then re-run the Probe verbatim]\n\n"
        .. "```bash\n[What you paste here may vary, but often probe run again]\n```\n\n"
        .. "**5: Prompt**: [The AI prompting itself (BEWARB the jabberwocky ouroboros dinosaurs!]\n\n"
        .. "```text\n[Probably what the AI gives you, but BEWARB the ouroboros]\n```"
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
    local dismount = "**Me**: Hop off the worm. This ride's stated goal is reached — dismount.\n"
        .. "Answer all four beats, briefly:\n\n"
        .. "1. VERIFY: restate the goal from the top of this article and confirm\n"
        .. "   (or deny) it was met, citing THIS compile's receipts, not memory.\n"
        .. "   Name any ignition this ride required that never fired -- an AFTER\n"
        .. "   tap taken without one is a stale BEFORE wearing the AFTER's label.\n"
        .. "2. BANK: name everything that graduates — rule, earmark, todo, pin —\n"
        .. "   as exact paste-ready lines, plus the exact lines to delete.\n"
        .. "3. DANGLING: what carries forward unbanked? One line each, no essays.\n"
        .. "4. SEED: end with the adhoc.txt lines (and TODO_SLUGS if narrative\n"
        .. "   context is needed) for the next ride's first compile.\n"
    vim.api.nvim_buf_set_lines(0, end_line - 1, end_line - 1, false, vim.split(dismount, "\n"))
    vim.api.nvim_win_set_cursor(0, {end_line - 1, 0})
    vim.cmd('normal! zz')
    vim.notify("Dismount staged above the !!! floor.", vim.log.levels.INFO)
end

-- Map it to <leader>c (for "Clip to Bridge")
vim.api.nvim_set_keymap('v', '<leader>c', '<cmd>lua sync_to_bridge()<CR>', { noremap = true, silent = true })

--  __  __                   _                 
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

-- F4: Toggle line numbers on/off (both normal and relative)
map('n', '<F4>', '<cmd>lua toggle_line_numbers()<CR>', opts)

-- F5 / <leader>t: Toggle textwidth 0 <-> 80 (the Margin Release)
map('n', '<F5>', '<cmd>lua toggle_text_width()<CR>', opts)
map('n', '<leader>t', '<cmd>lua toggle_text_width()<CR>', opts)

-- Leader key mappings
-- Text Processing
map('n', '<leader>s', '<cmd>lua correct_misspelling()<CR>', opts)  -- Spell correction
map('n', '<leader>q', '<cmd>lua escape_html_tags()<CR>', opts)  -- HTML tag escaping
map('n', '<leader>r', '<cmd>lua add_liquid_raw_tags()<CR>', opts)  -- Add Liquid raw tags

-- Dialogue Labelers
map('n', '<leader>b', '<cmd>lua bold_dialogue_speaker()<CR>', opts)  -- Bold dialogue speaker
map('n', '<leader>m', '<cmd>lua mount_sandworm()<CR>', opts) -- the human: mount the worm (full saddle at cursor)
map('n', '<leader>yy', 'i**Gemini 3.5 Thinking**: ', opts) -- you: Gemini 3.5 Extended
map('n', '<leader>yc', 'i**Claude Sonnet 4.6**: ', opts) -- you: Claude
map('n', '<leader>yg', 'i**ChatGPT 5.5**: ', opts)           -- you: GPT
map('n', '<leader>y1', 'i**Gemini 3.1 Pro**: ', opts)   -- fallback: Gemini 3.1 Fallback

-- Git Operations
map('n', '<leader>g', '<cmd>lua git_commit_push()<CR>', opts)  -- Git commit and push

-- Journal and Notes
map('n', '<leader>j', '<cmd>lua new_journal_entry()<CR>', opts)  -- New journal entry

-- Text Cleanup
map('n', '<leader>w', '<cmd>%s/\\s\\+$//e<CR>', opts)  -- Remove trailing whitespace
map('n', '<leader>e', '<cmd>g/^\\n\\{4,}/d<CR>', opts)  -- Remove excessive blank lines (4+)

-- Clean up Gemini Deep Research Markdown
map('n', '<leader>z', '<cmd>lua clean_gemini_markdown()<CR>', opts)

-- Navigation
map('n', '<leader>a', '<cmd>lua jump_next_active_chop()<CR>', opts)  -- Jump to next Active line (non-comment)

-- Article / Workflow Selection
map('n', '<leader>h', '<cmd>lua select_current_article()<CR>', opts)  -- Highlight (select) current article block
map('n', '<leader>k', '<cmd>lua hop_off_sandworm()<CR>', opts)  -- Hop off: stage the dismount wrap-up above !!!

-- Map it to <leader>p (for "Clip to Prompt")
vim.api.nvim_set_keymap('v', '<leader>p', '<cmd>lua sync_to_prompt()<CR>', { noremap = true, silent = true })

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
-- <leader>ya - Insert AI speaker label (Gemini)
-- <leader>yc - Insert AI speaker label (Claude)
-- <leader>yg - Insert AI speaker label (ChatGPT)
-- <leader>f  - Insert human speaker label (follow-up)

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
