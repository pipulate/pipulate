#!/usr/bin/env bash
# THE DOOR TABLE, WITNESSED WITHOUT A NETWORK (2026-10-02)
# Runs assets/installer/install.sh once per door, the way that door serves
# it (stamped or not), with curl, unzip and nix replaced by stubs at the
# front of PATH and HOME pointed at a throwaway folder. Nothing is
# downloaded, nothing is built, and your own home is never touched.
# Each case reads back the exit code, the folder the install made, and
# the door= and workshop= lines of the .door it wrote there. The words
# themselves are not checked here; the table in install.sh owns them.
# Prints one line per case, then DOORS_OK n/n (exit 0) or DOORS_BAD k/n
# (exit 1). DOORS_STOP (exit 2) means a stub did not come first on PATH,
# so no case ran. Bash 3.2 safe (macOS): no arrays.
#   bash tests/test_install_doors.sh
set -u

repo="$(cd "$(dirname "$0")/.." && pwd)"
installer="$repo/assets/installer/install.sh"
# The placeholder spelled in two halves, the way install.sh spells its
# sentinel, so this file never carries the contiguous word a door stamps.
tok='__INSTALL_DEFAULT_''NAME__'

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
stubs="$work/stubs"
mkdir -p "$stubs"

cat > "$stubs/curl" <<'EOF'
#!/usr/bin/env bash
# Stub: write a small file wherever -o points; reach nothing.
out=""
while [ $# -gt 0 ]; do
  if [ "$1" = "-o" ]; then out="$2"; shift; fi
  shift
done
if [ -n "$out" ]; then printf 'stub\n' > "$out"; fi
EOF

cat > "$stubs/unzip" <<'EOF'
#!/usr/bin/env bash
# Stub: make the one folder install.sh expects inside the -d target.
dest="."
while [ $# -gt 0 ]; do
  if [ "$1" = "-d" ]; then dest="$2"; shift; fi
  shift
done
mkdir -p "$dest/pipulate-main"
printf 'stub\n' > "$dest/pipulate-main/flake.nix"
EOF

printf '#!/usr/bin/env bash\n# Stub: build nothing.\nexit 0\n' > "$stubs/nix"
chmod +x "$stubs/curl" "$stubs/unzip" "$stubs/nix"

for tool in curl unzip nix; do
  found="$(export PATH="$stubs:$PATH"; command -v "$tool")"
  if [ "$found" != "$stubs/$tool" ]; then
    echo "DOORS_STOP $tool resolves to ${found:-nothing}, not the stub; no case ran."
    exit 2
  fi
done

total=0
bad=0

# run_case LABEL STAMP ARG WANT_FOLDER WANT_DOOR WANT_WORDS
# An empty STAMP serves the file unstamped, as pipulate.com does; an empty
# ARG is the plain one-liner with no word after bash -s.
run_case() {
  local label="$1" stamp="$2" arg="$3"
  local want="rc=0 folder=$4 door=$5 words=$6"
  local home served rc folder door words got
  total=$((total + 1))
  home="$work/home$total"
  served="$work/served$total.sh"
  mkdir -p "$home"
  if [ -n "$stamp" ]; then
    sed "s/$tok/$stamp/g" "$installer" > "$served"
  else
    cp "$installer" "$served"
  fi
  if [ -n "$arg" ]; then
    HOME="$home" PATH="$stubs:$PATH" PIPULATE_INSTALL_ONLY=1 bash -s "$arg" < "$served" > "$work/out$total.txt" 2>&1
  else
    HOME="$home" PATH="$stubs:$PATH" PIPULATE_INSTALL_ONLY=1 bash -s < "$served" > "$work/out$total.txt" 2>&1
  fi
  rc=$?
  folder="$(ls "$home" | paste -sd, -)"
  door="none"
  words="no"
  if [ -n "$folder" ] && [ -f "$home/$folder/.door" ]; then
    door="$(sed -n 's/^door=//p' "$home/$folder/.door")"
    if [ -n "$(sed -n 's/^workshop=//p' "$home/$folder/.door")" ]; then
      words="yes"
    fi
  fi
  got="rc=$rc folder=${folder:-none} door=${door:-empty} words=$words"
  if [ "$got" = "$want" ]; then
    printf 'ok   %-26s %s\n' "$label" "$got"
  else
    bad=$((bad + 1))
    printf 'BAD  %-26s %s (want %s)\n' "$label" "$got" "$want"
  fi
}

run_case "pipulate.com (unstamped)" ""   ""   pipulate pipulate yes
run_case "npvg.org"                 npvg ""   npvg     npvg     yes
run_case "qamy.ai"                  qamy ""   qamyai   qamy     yes
run_case "qamy.ai | bash -s myqa"   qamy myqa myqa     qamy     yes
run_case "a stamp with no row"      zzz  ""   zzz      zzz      no

if [ "$bad" -eq 0 ]; then
  echo "DOORS_OK $total/$total"
  exit 0
fi
echo "DOORS_BAD $bad/$total"
exit 1
