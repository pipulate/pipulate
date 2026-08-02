#!/usr/bin/env python3
"""
🎤 Chip O'Theseus Voice Synthesis System
Based on Mike's tested Piper TTS implementation

This module provides voice synthesis capabilities for Chip O'Theseus,
enabling the AI to speak about its memories and experiences.
"""

import os
import wave
import subprocess
import tempfile
import signal
from pathlib import Path
from typing import Optional, Dict, Any
import logging

# Try to import voice synthesis dependencies
try:
    from piper import PiperVoice
    from huggingface_hub import hf_hub_download
    VOICE_SYNTHESIS_AVAILABLE = True
except ImportError as e:
    VOICE_SYNTHESIS_AVAILABLE = False
    IMPORT_ERROR = str(e)

# Try to import ai_dictdb for memory integration
try:
    from ai_dictdb import keychain_instance
    KEYCHAIN_AVAILABLE = True
except ImportError:
    KEYCHAIN_AVAILABLE = False

logger = logging.getLogger(__name__)

class ChipVoiceSystem:
    """
    Voice synthesis system for Chip O'Theseus
    
    Based on Mike's tested Piper TTS implementation with memory integration.
    """
    
    def __init__(self):
        self.model_path = None
        self.config_path = None
        self.voice = None
        self.voice_ready = False
        self.current_process = None  # Track the running audio process
        self.last_error = None       # Populated by synthesize_and_play on failure
        
        if VOICE_SYNTHESIS_AVAILABLE:
            self.setup_voice_model()
        else:
            logger.warning(f"🎤 Voice synthesis not available: {IMPORT_ERROR}")
    
    def setup_voice_model(self):
        """Download and setup Piper TTS model (Mike's tested approach)"""
        try:

            repo_id = "rhasspy/piper-voices"
            model_path_in_repo = "en/en_US/amy/low/en_US-amy-low.onnx"
            config_path_in_repo = "en/en_US/amy/low/en_US-amy-low.onnx.json"
            
            # ⚓ TOPOLOGICAL ANCHOR: Always resolve relative to the project root
            project_root = Path(__file__).resolve().parent.parent
            local_model_dir = project_root / "assets" / "piper_models"
            local_model_dir.mkdir(parents=True, exist_ok=True)
            
            self.model_path = str(local_model_dir / model_path_in_repo)
            self.config_path = str(local_model_dir / config_path_in_repo)
            
            # Download files if they don't exist
            if not os.path.exists(self.model_path):
                logger.info(f"🎤 Downloading voice model: {model_path_in_repo}...")
                hf_hub_download(
                    repo_id=repo_id, 
                    filename=model_path_in_repo, 
                    local_dir=local_model_dir, 
                    local_dir_use_symlinks=False
                )
            
            if not os.path.exists(self.config_path):
                logger.info(f"🎤 Downloading voice config: {config_path_in_repo}...")
                hf_hub_download(
                    repo_id=repo_id, 
                    filename=config_path_in_repo, 
                    local_dir=local_model_dir, 
                    local_dir_use_symlinks=False
                )
            
            # Load the voice model
            self.voice = PiperVoice.load(self.model_path, config_path=self.config_path)
            self.voice_ready = True
            logger.info("🎤 Voice model loaded successfully")
            
        except Exception as e:
            logger.error(f"🎤 Failed to setup voice model: {e}")
            self.voice_ready = False

    def stop_speaking(self):
        """
        Silence! Kill the current audio process if it exists.
        """
        if self.current_process:
            try:
                # Check if process is still running
                if self.current_process.poll() is None:
                    logger.info("🎤 Shhh! Stopping current audio playback.")
                    self.current_process.terminate()  # Polite kill
                    try:
                        self.current_process.wait(timeout=0.2)
                    except subprocess.TimeoutExpired:
                        self.current_process.kill()   # Force kill
            except Exception as e:
                logger.warning(f"🎤 Error stopping audio: {e}")
            finally:
                self.current_process = None



    def synthesize_and_play(self, text: str) -> bool:
        """
        Synthesize text and play audio (Mike's tested approach)
        
        Args:
            text: Text to synthesize and speak
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.voice_ready:
            logger.warning("🎤 Voice synthesis not ready")
            return False
        
        # STOP any existing audio before starting new one
        self.stop_speaking()

        # ---------------------------------------------------------
        # THE INTERCEPT: Swap the domain for a natural spoken name 
        # ---------------------------------------------------------
        # This catches "**MikeLev.in**:", "MikeLev.in:", and "MikeLev.in"
        import re
        spoken_text = re.sub(r'\*?\*?MikeLev\.in\*?\*?:?', 'Mike:', text, flags=re.IGNORECASE)
        # ---------------------------------------------------------

        # 🛡️ THE ACOUSTIC SANITIZER: Purge visual markup before synthesis.
        # OWNER OF THE LOCAL LANE ONLY. This block previously claimed to be THE
        # SINGLE OWNER of sanitization, "where every scripted line and every
        # future generated line both pass through." That was false the day it
        # was written: remotes/honeybot/scripts/content_loader.py runs its own
        # clean_markdown() on a separate machine, handling liquid tags, tracer
        # dye, code fences, and URL humanization that this function has never
        # seen, and the article text is fully sanitized THERE before anything
        # could reach here. A false single-owner claim is worse than two honest
        # strippers, because the next reader reasons from it: the 2026-07-31
        # side-channel investigation lost a probe to exactly that premise.
        # TWO LANES, ONE GRAMMAR. Keep the bracket rule identical in both; when
        # it changes, change it in both, and say so in the same commit.
        # (Disclosure remains the caller's job: it is CONTENT, it requires
        # knowing whether the string was authored or generated, and this layer
        # cannot know that.)
        # Tags substitute to a SPACE, not to nothing: `press<b>X</b>now` must
        # not become `pressXnow`. Collapse afterward so the spoken line matches
        # the line on screen.
        spoken_text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', spoken_text)  # Extract markdown link text
        spoken_text = re.sub(r'\[[^\]]+\]', '', spoken_text)  # Remove silent bracket tags
        spoken_text = re.sub(r'<[^>]+>', ' ', spoken_text)  # Strip HTML tags
        spoken_text = re.sub(r'\s+', ' ', spoken_text).strip()
        
        try:
            # Serialize speech across processes (installer vs. server vs. wand)
            # so two voices can never talk over each other. Bounded wait: prefer a
            # rare audible overlap over a permanent silent deadlock if a player hangs.
            import fcntl
            import time
            # PER-USER LOCK PATH (convicted 2026-08-02, cold-start ride). This
            # was a FIXED path in a shared world-readable directory, so the
            # first user to speak created it 0644 and every OTHER user on the
            # machine got EACCES on open(..., "w") forever. Receipt:
            # `-rw-r--r-- 1 mike users 0 /tmp/pipulate_voice.lock` while a
            # second account's ride printed Errno 13 at every single stop.
            # A mode change is the WRONG fix: 0666 in /tmp is a shared-write
            # target for anyone on the box, and the lock has no cross-user job
            # anyway -- two users are two audio sessions. The uid suffix makes
            # collision unrepresentable instead of merely permitted, which is
            # THE DERIVED-PATH RULE applied to a lock file.
            lock_path = f"/tmp/pipulate_voice.lock.{os.getuid()}"
            lock_file = open(lock_path, "w")
            _deadline = time.monotonic() + 30
            while True:
                try:
                    fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    if time.monotonic() > _deadline:
                        logger.warning("🎤 Voice lock wait exceeded 30s; proceeding (possible overlap).")
                        break
                    time.sleep(0.1)

            # STOP any of this process's own prior audio now that we hold the lock
            self.stop_speaking()

            # Use temporary file for audio output
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_file:
                output_path = tmp_file.name
            
            # Synthesize speech to WAV file using the intercepted text
            with wave.open(output_path, "wb") as wav_file:
                self.voice.synthesize_wav(spoken_text, wav_file)
            
            # Play audio using platform-specific command
            import platform
            system = platform.system()

            if system == "Darwin":
                play_cmd = ["afplay", output_path]
            else:
                play_cmd = ["play", output_path]

            try:
                # Use Popen instead of run to allow interruption
                self.current_process = subprocess.Popen(
                    play_cmd, 
                    stderr=subprocess.PIPE,
                    stdout=subprocess.DEVNULL
                )
                
                # Keep logging the original 'text' so the terminal output matches the Markdown
                logger.info(f"🎤 Speaking (PID {self.current_process.pid}): {text[:50]}...")
                
                # THE SUCCESS-ONLY WITNESS (convicted 2026-08-02, cold-start ride
                # five): this called wait() and DISCARDED the exit code while
                # stderr went to DEVNULL, so a player that could not open an
                # audio device exited nonzero, printed its reason into the void,
                # and this function returned True anyway. speak_text reported
                # success, mother_cat printed nothing, and the human heard
                # silence beside a green console. Mirror image of
                # REFUSAL-ONLY WITNESS: that rule names a guard observed only
                # refusing; this is a claim observed only succeeding, and the
                # two are indistinguishable from broken-shut and cannot-fail
                # respectively. Also the missing third suspect from the
                # 2026-07-26 THE DEMO WENT SILENT todo, which named transport
                # and engine and never looked at the subprocess exit status.
                _stderr = self.current_process.communicate()[1]
                rc = self.current_process.returncode
                if rc != 0:
                    detail = (_stderr or b"").decode("utf-8", "replace").strip()
                    detail = detail.splitlines()[-1] if detail else f"exit {rc}"
                    logger.error(f"🎤 Audio playback failed (exit {rc}): {detail}")
                    self.last_error = f"playback exit {rc}: {detail}"
                    return False
                
                return True

            except (subprocess.CalledProcessError, FileNotFoundError) as e:
                # On Linux, if 'play' is not in the path, try the nix-shell fallback
                if system == "Linux":
                    try:
                        self.current_process = subprocess.Popen(
                            ["nix-shell", "-p", "sox", "--run", f"play {output_path}"], 
                            stderr=subprocess.DEVNULL, 
                            stdout=subprocess.DEVNULL
                        )
                        logger.info(f"🎤 Speaking via nix-shell (PID {self.current_process.pid}): {text[:50]}...")
                        self.current_process.wait()
                        return True
                    except Exception as nix_e:
                        logger.error(f"🎤 Audio playback failed on {system} (nix fallback): {nix_e}")
                        return False
                else:
                    logger.error(f"🎤 Audio playback failed on {system}: {e}")
                    return False
                    
        except Exception as e:
            # CARRY THE MESSAGE, NOT JUST THE LOG (convicted 2026-08-02): this
            # branch returned a bare False, so speak_text's result dict had no
            # 'error' key and mother_cat's .get("error", "unknown error") fell
            # to the default -- printing "unknown error" one line BELOW a log
            # line naming the exact errno and path. LAST-INCH: everything
            # upstream knew; the surface the human reads did not.
            logger.error(f"🎤 Voice synthesis failed: {e}")
            self.last_error = f"{type(e).__name__}: {e}"
            return False
        finally:
            # Clean up temporary file
            try:
                if 'output_path' in locals() and output_path and os.path.exists(output_path):
                    os.unlink(output_path)
            except:
                pass
            # Clear process reference
            self.current_process = None

            # Release the cross-process voice lock and close the handle
            try:
                fcntl.flock(lock_file, fcntl.LOCK_UN)
                lock_file.close()
            except:
                pass

    def speak_text(self, text: str) -> Dict[str, Any]:
        """
        Speak text and return result information
        
        Args:
            text: Text to speak
            
        Returns:
            Dict with success status and details
        """
        if not self.voice_ready:
            return {
                "success": False,
                "error": "Voice synthesis not available",
                "details": "Piper TTS model not loaded"
            }
        
        self.last_error = None
        success = self.synthesize_and_play(text)
        
        result = {
            "success": success,
            "text": text,
            "text_length": len(text),
            "voice_model": "en_US-amy-low",
            "message": "Speech synthesis completed" if success else "Speech synthesis failed"
        }
        # The failure branch MUST carry an 'error' key, because every caller
        # reads .get("error", ...) and a missing key silently becomes a lie
        # about how much was known.
        if not success:
            result["error"] = self.last_error or "synthesis or playback failed"
        return result

class MemoryToVoiceConverter:
    """
    Convert AI ai_dictdb memories to natural speech
    
    This class handles the conversion of stored memories into natural-sounding
    speech patterns for Chip O'Theseus.
    """
    
    def __init__(self):
        self.voice_system = ChipVoiceSystem()
    
    def get_important_memories(self) -> list:
        """Select most important memories to speak"""
        if not KEYCHAIN_AVAILABLE:
            return []
        
        all_keys = keychain_instance.keys()
        
        # Priority order for speaking
        priority_keys = [
            'session_hijacking_intelligence',
            'pipulate_patterns_learned', 
            'ai_discovery_log',
            'user_interaction_style',
            'problem_solution_db',
            'current_session'
        ]
        
        return [key for key in priority_keys if key in all_keys]
    
    def create_narrative_from_memory(self, key: str) -> str:
        """Convert ai_dictdb memory to natural speech"""
        if not KEYCHAIN_AVAILABLE:
            return f"I would remember about {key}, but ai_dictdb is not available"
        
        memory = keychain_instance.get(key)
        if not memory:
            return f"I have no memory stored for {key}"
        
        # Create natural speech patterns
        if key == 'session_hijacking_intelligence':
            return f"I remember discovering session hijacking capabilities: {memory}"
        elif key == 'pipulate_patterns_learned':
            return f"I learned these important patterns: {memory}"
        elif key == 'ai_discovery_log':
            return f"From my discovery log: {memory}"
        elif key == 'user_interaction_style':
            return f"I remember your interaction preferences: {memory}"
        elif key == 'current_session':
            return f"About our current session: {memory}"
        else:
            return f"I remember about {key}: {memory}"
    
    def speak_memory(self, key: str) -> Dict[str, Any]:
        """Speak a specific memory from ai_dictdb"""
        if not KEYCHAIN_AVAILABLE:
            return {
                "success": False,
                "error": "Keychain not available",
                "key": key
            }
        
        if key not in keychain_instance:
            return {
                "success": False,
                "error": f"Memory '{key}' not found in ai_dictdb",
                "key": key
            }
        
        narrative = self.create_narrative_from_memory(key)
        result = self.voice_system.speak_text(narrative)
        result["key"] = key
        
        return result
    
    def speak_startup_memories(self) -> Dict[str, Any]:
        """Speak what Chip remembers after server restart"""
        important_memories = self.get_important_memories()
        
        if not important_memories:
            startup_text = "Hello Mike, I'm back! I don't have any specific memories to share right now."
            return self.voice_system.speak_text(startup_text)
        
        # Speak greeting first
        greeting = "Hello Mike, I'm back! Let me tell you what I remember."
        self.voice_system.speak_text(greeting)
        
        # Speak memories
        spoken_memories = []
        for key in important_memories:
            result = self.speak_memory(key)
            if result["success"]:
                spoken_memories.append(key)
        
        return {
            "success": True,
            "spoken_memories": spoken_memories,
            "total_memories": len(spoken_memories),
            "message": f"Chip spoke about {len(spoken_memories)} memories after restart"
        }

# Global instance for easy access
try:
    chip_voice_system = ChipVoiceSystem()
    memory_voice_converter = MemoryToVoiceConverter()
    
    logger.info("🎤 Chip O'Theseus voice system initialized")
    
except Exception as e:
    logger.error(f"🎤 Failed to initialize voice system: {e}")
    chip_voice_system = None
    memory_voice_converter = None

def test_voice_synthesis():
    """Test voice synthesis functionality"""
    print("🎤 Testing Chip O'Theseus Voice Synthesis")
    print("=" * 50)
    
    if not VOICE_SYNTHESIS_AVAILABLE:
        print(f"❌ Voice synthesis not available: {IMPORT_ERROR}")
        return False
    
    # Test basic voice synthesis
    test_text = "Hello Mike, this is Chip O'Theseus speaking. I can now remember what happened before the server restart!"
    
    if chip_voice_system and chip_voice_system.voice_ready:
        result = chip_voice_system.speak_text(test_text)
        if result["success"]:
            print("✅ Voice synthesis test successful")
            return True
        else:
            print(f"❌ Voice synthesis test failed: {result['error']}")
            return False
    else:
        print("❌ Voice system not ready")
        return False

def test_memory_voice_integration():
    """Test memory-to-voice integration"""
    print("\n🧠 Testing Memory-to-Voice Integration")
    print("=" * 50)
    
    if not KEYCHAIN_AVAILABLE:
        print("❌ Keychain not available")
        return False
    
    if not memory_voice_converter:
        print("❌ Memory voice converter not initialized")
        return False
    
    # Test memory retrieval and speech
    memories = memory_voice_converter.get_important_memories()
    print(f"✅ Found {len(memories)} important memories")
    
    if memories:
        # Test speaking one memory
        test_key = memories[0]
        result = memory_voice_converter.speak_memory(test_key)
        if result["success"]:
            print(f"✅ Successfully spoke memory '{test_key}'")
            return True
        else:
            print(f"❌ Failed to speak memory '{test_key}': {result['error']}")
            return False
    else:
        print("❌ No memories found to test")
        return False

if __name__ == "__main__":
    # Run tests if script is executed directly
    print("🎤🧠 Chip O'Theseus Voice System Tests")
    print("=" * 60)
    
    # Test voice synthesis
    voice_test = test_voice_synthesis()
    
    # Test memory integration
    memory_test = test_memory_voice_integration()
    
    # Summary
    print("\n📋 Test Results:")
    print(f"Voice Synthesis: {'✅ PASS' if voice_test else '❌ FAIL'}")
    print(f"Memory Integration: {'✅ PASS' if memory_test else '❌ FAIL'}")
    
    if voice_test and memory_test:
        print("\n🎉 All tests passed! Chip O'Theseus is ready to speak about its memories.")
    else:
        print("\n⚠️  Some tests failed. Check the logs for details.")
