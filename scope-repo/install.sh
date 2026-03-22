#!/usr/bin/env bash
# install.sh — Install scopework into PATH
#
# Usage: ./install.sh [--prefix DIR]
#   Default prefix: ~/.local/bin

set -euo pipefail

PREFIX="$HOME/.local/bin"

while [[ $# -gt 0 ]]; do
	case "$1" in
		--prefix)
			PREFIX="$2"
			shift 2
			;;
		*)
			echo "Usage: $0 [--prefix DIR]"
			exit 1
			;;
	esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

mkdir -p "$PREFIX"

chmod +x "$SCRIPT_DIR/scopework"
ln -sf "$SCRIPT_DIR/scopework" "$PREFIX/scopework"

echo "Installed:"
echo "  scopework → $PREFIX/scopework"
echo ""

if [[ ":$PATH:" != *":$PREFIX:"* ]]; then
	echo "Warning: $PREFIX is not in your PATH."
	echo "Add this to your shell profile:"
	echo "  export PATH=\"$PREFIX:\$PATH\""
	echo ""
fi

echo "Usage:"
echo "  cd ~/projects/your-repo"
echo "  scopework                              # full pipeline"
echo "  scopework --briefings DIR              # reuse prior briefings"
echo "  scopework --execute-quick-wins         # fix trivial items first"
echo "  scopework --dry-run                    # preview launch prompt"
echo "  scopework --no-issues                  # skip GitHub Issues"
