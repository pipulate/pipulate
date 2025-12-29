# Edit this configuration file to define what should be installed on
# your system.  Help is available in the configuration.nix(5) man page
# and in the NixOS manual (accessible by running ‘nixos-help’).

{ config, pkgs, ... }:

{
  imports =
    [ # Include the results of the hardware scan.
      ./hardware-configuration.nix
      ./secrets.nix
    ];

  # Enable Flakes and the new Nix Command Line Tool
  nix.settings.experimental-features = [ "nix-command" "flakes" ];

  # Bootloader.
  boot.loader.systemd-boot.enable = true;
  boot.loader.efi.canTouchEfiVariables = true;

  networking.hostName = "honeybot"; # Define your hostname.
  # networking.wireless.enable = true;  # Enables wireless support via wpa_supplicant.

  # Allow Nginx to read files in /home/mike
  systemd.services.nginx.serviceConfig.ProtectHome = "read-only";

  # 2. THE INSOMNIA (Server Mode)
  # Prevent the laptop from sleeping when you close the lid
  services.logind.lidSwitch = "ignore";
  services.logind.lidSwitchExternalPower = "ignore";
  
  # Optional: Nuclear option to prevent sleep entirely (Good for servers)
  systemd.targets.sleep.enable = false;
  systemd.targets.suspend.enable = false;
  systemd.targets.hibernate.enable = false;
  systemd.targets.hybrid-sleep.enable = false;

  # ENSURE NGINX CAN WALK TO HOME
  # 'd' creates, 'z' adjusts mode of existing lines.
  # 'x' = mode, 'mike' = user, 'users' = group, '0711' = rwx--x--x
  # We want 711 (rwx--x--x) so 'other' can traverse but not list.
  systemd.tmpfiles.rules = [
    # path          mode user group age argument
    "d /home/mike     0711 mike users -"
    "d /home/mike/www 0755 mike users -"
  ];

  # Configure network proxy if necessary
  # networking.proxy.default = "http://user:password@proxy:port/";
  # networking.proxy.noProxy = "127.0.0.1,localhost,internal.domain";

  # Enable networking
  networking.networkmanager.enable = true;

  # Set your time zone.
  time.timeZone = "America/New_York";

  # Select internationalisation properties.
  i18n.defaultLocale = "en_US.UTF-8";

  i18n.extraLocaleSettings = {
    LC_ADDRESS = "en_US.UTF-8";
    LC_IDENTIFICATION = "en_US.UTF-8";
    LC_MEASUREMENT = "en_US.UTF-8";
    LC_MONETARY = "en_US.UTF-8";
    LC_NAME = "en_US.UTF-8";
    LC_NUMERIC = "en_US.UTF-8";
    LC_PAPER = "en_US.UTF-8";
    LC_TELEPHONE = "en_US.UTF-8";
    LC_TIME = "en_US.UTF-8";
  };

  # Enable the X11 windowing system.
  services.xserver.enable = true;

  # Enable the GNOME Desktop Environment.
  services.xserver.displayManager.gdm.enable = true;
  services.xserver.desktopManager.xfce.enable = true;
  services.xserver.displayManager.gdm.wayland = false; # <--- CRITICAL: Force X11 for automation

  # Remote Desktop - Debug Mode
  services.xrdp.enable = true;
  services.xrdp.openFirewall = true;
  services.xrdp.defaultWindowManager = "${pkgs.writeShellScript "start-xfce-debug" ''
    # Redirect ALL output to a log file we can read
    exec > /tmp/xrdp-debug.log 2>&1
    set -x

    echo "=== STARTING XRDP SESSION ==="
    echo "User: $USER"
    echo "Path: $PATH"
    
    # Force X11 Environment
    export XDG_SESSION_TYPE=x11
    export GDK_BACKEND=x11
    export DESKTOP_SESSION=xfce
    export XDG_CURRENT_DESKTOP=XFCE
    
    # Check if the binary exists
    if [ -f "${pkgs.xfce.xfce4-session}/bin/startxfce4" ]; then
        echo "Binary found. Launching..."
        ${pkgs.xfce.xfce4-session}/bin/startxfce4
    else
        echo "CRITICAL ERROR: startxfce4 not found!"
        # Keep session open so we can see the error if we had a window
        sleep 30
    fi
  ''}";

  # Configure keymap in X11
  services.xserver.xkb = {
    layout = "us";
    variant = "";
  };

  # Enable CUPS to print documents.
  services.printing.enable = true;

  # Enable sound with pipewire.
  services.pulseaudio.enable = false;
  security.rtkit.enable = true;
  services.pipewire = {
    enable = true;
    alsa.enable = true;
    alsa.support32Bit = true;
    pulse.enable = true;
    # If you want to use JACK applications, uncomment this
    #jack.enable = true;

    # use the example session manager (no others are packaged yet so this is enabled by default,
    # no need to redefine it in your config for now)
    #media-session.enable = true;
  };

  # Enable touchpad support (enabled default in most desktopManager).
  # services.xserver.libinput.enable = true;

  # 1. Enable OpenSSH
  services.openssh = {
    enable = true;
    settings = {
      # HARDENING: Disable password login immediately. 
      # This is crucial for a machine that will eventually face the web.
      PasswordAuthentication = false;
      PermitRootLogin = "no";
    };
  };

  # 2. Open the Firewall for SSH
  networking.firewall.allowedTCPPorts = [ 22 80 443 ];

  # ACME (Let's Encrypt) Automated Certs
  security.acme = {
    acceptTerms = true;
    defaults.email = "miklevin@gmail.com"; # Required for renewal alerts
  };

  # Nginx System Service
  services.nginx = {
    enable = true;
    recommendedGzipSettings = true;
    recommendedOptimisation = true;
    recommendedProxySettings = true;
    recommendedTlsSettings = true; 

    virtualHosts."mikelev.in" = {
      forceSSL = true;      # Force all traffic to HTTPS  # <--- Comment out (Don't force HTTPS yet)
      enableACME = true;    # Let's Encrypt magic # <--- Comment out (Don't try to get certs yet)

      # The Web Root
      root = "/home/mike/www/mikelev.in/_site"; 
    };
  };

  # Define a user account. Don't forget to set a password with ‘passwd’.
  users.users.mike = {
    isNormalUser = true;
    description = "Mike";
    extraGroups = [ "networkmanager" "wheel" "nginx" ];
    homeMode = "711"; 
    packages = with pkgs; [
    #  thunderbird
    ];
  };

  # Install firefox.
  programs.firefox.enable = true;

  # Allow unfree packages
  nixpkgs.config.allowUnfree = true;

  # List packages installed in system profile. To search, run:
  # $ nix search wget
  environment.systemPackages = with pkgs; [
    git
    tmux

    # The Broadcast Studio
    obs-studio
    pavucontrol     # Essential for routing audio (PulseAudio Volume Control)

    xfce.xfce4-session
    xfce.xfce4-terminal
    
    # The Automaton's Hands (Amiga AREXX style control)
    xdotool         # Keyboard/Mouse simulation
    wmctrl          # Window management

    # 🎭 THE PROPS (Visuals for the stage)
    cmatrix     # The "Digital Rain"
    fastfetch   # System info display (faster neofetch)
    bc          # Calculator (useful for timing math if needed)

    # 🗣️ THE VOICE (System Capability)
    piper-tts

    # 🎬 THE PERFORMER (The Choreographed Scene)
    (writeShellScriptBin "perform" ''
      # --- Setup ---
      MODEL_DIR="$HOME/.local/share/piper_voices"
      MODEL_NAME="en_US-amy-low.onnx"
      CACHE_DIR="/tmp/honeybot_voice_cache"
      mkdir -p "$CACHE_DIR"

      # ---------------------------------------------------------
      # THE ENGINE: Voice-Driven Timing
      # ---------------------------------------------------------
      
      # 1. Pre-render (Same as before)
      prepare() {
        local key="$1"
        local text="$2"
        echo "⚙️  Pre-rendering [$key]..."
        echo "$text" | \
          ${pkgs.piper-tts}/bin/piper --model "$MODEL_DIR/$MODEL_NAME" --output_raw > "$CACHE_DIR/$key.raw"
      }


      # 2. Action: Visual Background, Audio Foreground
      action() {
        local key="$1"
        local visual_cmd="$2"
        
        echo "---------------------------------------------------"
        echo "🎬 SCENE START: [$key]"
        
        # Start Visual in Background
        # We run it directly if possible to avoid subshell nesting hell
        # But eval is needed for complex strings
        bash -c "$visual_cmd" &
        VISUAL_PID=$!
        
        # Give it a moment to paint
        sleep 0.2
        
        # Play Audio (Blocking - The Timer)
        ${pkgs.alsa-utils}/bin/aplay -r 22050 -f S16_LE -t raw "$CACHE_DIR/$key.raw" 2>/dev/null
        
        # Scene Over. KILL THE CHILDREN.
        # This kills any process whose Parent Process ID (PPID) is our background shell
        pkill -P $VISUAL_PID
        
        # Then kill the shell itself
        kill $VISUAL_PID 2>/dev/null
        wait $VISUAL_PID 2>/dev/null
        
        # Restore terminal sanity (cmatrix often breaks newlines)
        stty sane
        
        echo "---------------------------------------------------"
      }

      # ---------------------------------------------------------
      # THE SCRIPT (Pre-production)
      # ---------------------------------------------------------
      echo "📝 Scripting the scene..."
      prepare "intro"   "Initiating visual diagnostic sequence. Stand by."
      prepare "matrix"  "Injecting digital rain into the framebuffer. Observe the flow."
      prepare "stats"   "Matrix simulation stable. Querying hardware abstraction layer."
      prepare "outro"   "Diagnostic complete. System nominal. Returning control to Watchdog."

      # ---------------------------------------------------------
      # THE PERFORMANCE (Execution)
      # ---------------------------------------------------------
      
      # Scene 1: Intro (Just voice)
      # We sleep in background to keep the PID logic valid
      action "intro" "sleep 10" 

      # Scene 2: The Matrix
      # REMOVED timeout command. The voice is the timeout.
      action "matrix" "${pkgs.cmatrix}/bin/cmatrix -b"

      # Scene 3: Stats
      # fastfetch finishes fast, so audio will continue over the static output
      action "stats" "${pkgs.fastfetch}/bin/fastfetch --logo none"

      # Scene 4: Outro
      action "outro" "sleep 10"
      
      # Cleanup
      rm -rf "$CACHE_DIR"
    '')

    # 🛡️ THE WATCHDOG (The Director)
    # Updated to call 'perform' instead of 'hello-voice'
    (writeShellScriptBin "hello" ''
      # 1. Define Model Storage
      MODEL_DIR="$HOME/.local/share/piper_voices"
      mkdir -p "$MODEL_DIR"
      
      MODEL_NAME="en_US-amy-low.onnx"
      JSON_NAME="en_US-amy-low.onnx.json"
      URL_BASE="https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/amy/low"
      
      # 2. Fetch if missing
      if [ ! -f "$MODEL_DIR/$MODEL_NAME" ]; then
        echo "📥 Downloading voice model (One-time setup)..."
        ${pkgs.curl}/bin/curl -L -o "$MODEL_DIR/$MODEL_NAME" "$URL_BASE/$MODEL_NAME?download=true"
        ${pkgs.curl}/bin/curl -L -o "$MODEL_DIR/$JSON_NAME" "$URL_BASE/$JSON_NAME?download=true"
      fi

      echo "🛡️ Watchdog Active. Starting Performance Loop..."
      
      # 3. The Infinite Loop
      while true; do
        echo "🎬 Action!"
        
        # Run the Choreographed Scene
        perform
        
        # The Intermission
        echo "⏳ Intermission (30 seconds)..."
        sleep 30
      done
    '')
  ];

  # The "Studio" Aliases
  # 'logs' = Old Aquarium (Legacy)
  # 'sonar' = New Sonar (The Pulse)
  environment.shellAliases = {
    logs = "tail -f /var/log/nginx/access.log | nix develop /home/mike/www/mikelev.in#quiet --command python3 -u /home/mike/www/mikelev.in/scripts/aquarium.py";
    sonar = "tail -f /var/log/nginx/access.log | nix develop /home/mike/www/mikelev.in#quiet --command python3 -u /home/mike/www/mikelev.in/scripts/sonar.py";
  };

  # 1. The Editor (The Bridge to AI)
  programs.neovim = {
    enable = true;
    defaultEditor = true;
    viAlias = true;
    vimAlias = true;
  };

  # Some programs need SUID wrappers, can be configured further or are
  # started in user sessions.
  # programs.mtr.enable = true;
  # programs.gnupg.agent = {
  #   enable = true;
  #   enableSSHSupport = true;
  # };

  # List services that you want to enable:

  # Enable the OpenSSH daemon.
  # services.openssh.enable = true;

  # Open ports in the firewall.
  # networking.firewall.allowedTCPPorts = [ ... ];
  # networking.firewall.allowedUDPPorts = [ ... ];
  # Or disable the firewall altogether.
  # networking.firewall.enable = false;

  # This value determines the NixOS release from which the default
  # settings for stateful data, like file locations and database versions
  # on your system were taken. It‘s perfectly fine and recommended to leave
  # this value at the release version of the first install of this system.
  # Before changing this value read the documentation for this option
  # (e.g. man configuration.nix or on https://nixos.org/nixos/options.html).
  system.stateVersion = "25.05"; # Did you read the comment?

}
