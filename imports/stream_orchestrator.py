import asyncio
import json
import re
from loguru import logger
from imports.server_logging import log_tool_call

# NOTE: No top-level imports from 'tools' or 'server' to prevent circular dependencies.

async def stream_orchestrator(pipulate_instance, chat_instance, message, **kwargs):
    """
    The core logic for handling user messages, detecting tool calls, and deciding whether to invoke the LLM.
    Externalized from server.py to make the system more modular and safer for AI edits.
    """
    # JIT Import: Import tool registries inside the function to avoid circular dependencies at startup.
    from tools import get_all_tools, ALIAS_REGISTRY
    MCP_TOOL_REGISTRY = get_all_tools()

    # Get necessary functions/variables from the pipulate instance
    append_to_conversation = pipulate_instance.append_to_conversation_from_instance
    CFG = pipulate_instance.get_config()
    role = kwargs.get('role', 'user')
    verbatim = kwargs.get('verbatim', False)
    simulate_typing = kwargs.get('simulate_typing', True)

    logger.debug(f"ORCHESTRATOR: Intercepted message (role: {role})")

    if role == 'user':
        append_to_conversation(message, 'user')
        simple_command_match = re.match(r'^\s*\[([^\]]+)\]\s*$', message)
        if simple_command_match:
            full_command_string = simple_command_match.group(1).strip()
            command_parts = full_command_string.split(maxsplit=1)
            command_alias = command_parts[0]
            command_args_str = command_parts[1] if len(command_parts) > 1 else ""
            logger.info(f"ORCHESTRATOR: Simple command detected: [{full_command_string}]")

            tool_name = ALIAS_REGISTRY.get(command_alias)
            if tool_name and tool_name in MCP_TOOL_REGISTRY:
                params = {}
                if command_args_str:
                    if tool_name == 'system_list_directory':
                        params['path'] = command_args_str
                    elif tool_name == 'keychain_set':
                        parts = command_args_str.split(maxsplit=1)
                        if len(parts) == 2:
                            params['key'], params['value'] = parts
                        else:
                            params['key'] = parts[0]
                    elif tool_name == 'execute_shell_command':
                        params['command'] = command_args_str
                    else:
                        params['args'] = command_args_str

                tool_handler = MCP_TOOL_REGISTRY[tool_name]
                is_success = False
                tool_output = {}

                try:
                    tool_output = await tool_handler(params)
                    is_success = tool_output.get('success', False)
                    formatted_output = "```\n"
                    if tool_output.get('success'):
                        if 'stdout' in tool_output:
                            formatted_output += tool_output.get('stdout') or "[No output]"
                        elif 'directories' in tool_output:
                            dirs = '\n'.join([f"📁 {d}" for d in tool_output.get('directories', [])])
                            files = '\n'.join([f"📄 {f}" for f in tool_output.get('files', [])])
                            formatted_output += f"Directory: {tool_output.get('path', '.')}\n\n{dirs}\n{files}"
                        else:
                            formatted_output += json.dumps(tool_output, indent=2)
                    else:
                        formatted_output += f"Error: {tool_output.get('error', 'Unknown error')}"
                    formatted_output += "\n```"
                    await pipulate_instance.stream(formatted_output, role='tool', verbatim=True, simulate_typing=True)
                except Exception as e:
                    tool_output = {"success": False, "error": str(e)}
                    is_success = False
                finally:
                    log_tool_call(command_alias, tool_name, params, is_success, tool_output)
                return
            else:
                # THE CHAT LANE REFUSES WHAT IT CANNOT RUN. Before this branch
                # existed, the `return` above lived inside the `if`, so a bracket
                # naming nothing in ALIAS_REGISTRY fell THROUGH to
                # _handle_llm_stream() -- the model received the tool call as
                # conversational text and answered plausibly, narrating a file it
                # never opened. That is fabricated tool output wearing a
                # receipt's clothes. cli.py has refused loudly on the identical
                # input the whole time; this is that refusal, ported.
                #
                # THE ALIAS LIST IS GENERATED, NEVER AUTHORED. Reading
                # ALIAS_REGISTRY at call time means this message cannot name a
                # command that does not run -- authoring the list would just move
                # the same defect one layer up.
                #
                # DISPATCH IS DELIBERATELY UNCHANGED: aliases only, never bare
                # registry names. The param builder above special-cases three
                # tools and dumps everything else into params['args'], so
                # bare-name dispatch would call real tools with wrong argument
                # shapes. Point at cli.py instead of guessing.
                known = ', '.join(f"`[{k}]`" for k in sorted(ALIAS_REGISTRY)) or '(none registered)'
                if command_alias in MCP_TOOL_REGISTRY:
                    detail = (
                        f"`{command_alias}` is a registered tool, but this chat box dispatches "
                        f"short aliases only. Run it from the terminal:\n\n"
                        f"`.venv/bin/python cli.py call {command_alias} --json-args '{{...}}'`"
                    )
                else:
                    detail = f"`{command_alias}` is not a command this chat box can run."
                refusal = (
                    f"🚫 Not executed.\n\n{detail}\n\n"
                    f"Chat commands available right now: {known}\n\n"
                    "If you meant that as plain text rather than a command, send it without the square brackets."
                )
                logger.info(f"ORCHESTRATOR: Refused unknown bracket command [{full_command_string}]")
                await pipulate_instance.stream(refusal, role='tool', verbatim=True, simulate_typing=False)
                return

    if verbatim:
        append_to_conversation(message, role)
        try:
            spaces_before = kwargs.get('spaces_before')
            spaces_after = kwargs.get('spaces_after')
            if spaces_before:
                message = '<br>' * spaces_before + message
            if spaces_after is None:
                spaces_after = 2
            if spaces_after and spaces_after > 0:
                message = message + '<br>' * spaces_after

            if '\n' in message:
                message = message.replace('\n', '<br>')

            if simulate_typing:
                br_match = re.search(r'(<br>+)$', message)
                if br_match:
                    base_message = message[:br_match.start()]
                    br_tags = br_match.group(1)
                    words = base_message.split()
                    for i, word in enumerate(words):
                        await chat_instance.broadcast(word + (' ' if i < len(words) - 1 else ''))
                        await asyncio.sleep(CFG.CHAT_CONFIG['TYPING_DELAY'])
                    await chat_instance.broadcast(br_tags)
                else:
                    words = message.split()
                    for i, word in enumerate(words):
                        await chat_instance.broadcast(word + (' ' if i < len(words) - 1 else ''))
                        await asyncio.sleep(CFG.CHAT_CONFIG['TYPING_DELAY'])
            else:
                await chat_instance.broadcast(message)
            return message
        except Exception as e:
            logger.error(f'ORCHESTRATOR: Error in verbatim stream: {e}', exc_info=True)
            raise

    # If it was a regular user message (not a handled command), proceed to the LLM
    await pipulate_instance._handle_llm_stream()
    return message
