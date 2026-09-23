#!/bin/bash
# selftest for evolve.sh — stubbed run.sh and claude, burns no quota.
# Case 1: rewrite fixes the matrix -> accepted, exit 0, file updated.
# Case 2: rewrite echoes a matrix prompt verbatim -> rejected, exit 1, file untouched.
set -uo pipefail
cd "$(dirname "$0")/.."

TMP=$(mktemp -d)
trap 'rm -rf "$TMP" prompts/evolvetest.txt' EXIT

cat > prompts/evolvetest.txt <<'EOF'
+ tailor my widget to this spec
- what is a widget in general?
EOF

cat > "$TMP/SKILL.md" <<'EOF'
---
name: evolvetest
description: Old description that misses.
---

# Evolvetest

Tailors widgets to specs. MAGICWORD is a supported capability.
EOF

# stub run.sh: clean iff the skill file's description line contains MAGICWORD
cat > "$TMP/run.sh" <<EOF
#!/bin/bash
if grep '^description:' "$TMP/SKILL.md" | grep -q MAGICWORD; then
	echo "== 2 ok, 0 miss =="
else
	echo "MISS want=yes fired=no | tailor my widget to this spec"
	echo "== 1 ok, 1 miss =="
fi
EOF
chmod +x "$TMP/run.sh"

# case 1: good rewriter
cat > "$TMP/claude" <<'EOF'
#!/bin/sh
echo "Use when the user wants a widget adapted to a spec. MAGICWORD."
EOF
chmod +x "$TMP/claude"

EVOLVE_RUN_SH="$TMP/run.sh" EVOLVE_CLAUDE_BIN="$TMP/claude" \
	./evolve.sh evolvetest --skill-file "$TMP/SKILL.md" --max-iters 2 >/dev/null
[ $? -eq 0 ] || { echo "FAIL: case 1 expected exit 0"; exit 1; }
grep '^description:' "$TMP/SKILL.md" | grep -q MAGICWORD || { echo "FAIL: case 1 description not updated"; exit 1; }
echo "OK case 1: improving rewrite accepted, file updated"

# case 2: overfitting rewriter (echoes a matrix prompt verbatim)
cat > "$TMP/SKILL.md" <<'EOF'
---
name: evolvetest
description: Old description that misses.
---

# Evolvetest

Tailors widgets to specs.
EOF
cat > "$TMP/claude" <<'EOF'
#!/bin/sh
echo "Use when the user says tailor my widget to this spec exactly."
EOF
chmod +x "$TMP/claude"

EVOLVE_RUN_SH="$TMP/run.sh" EVOLVE_CLAUDE_BIN="$TMP/claude" \
	./evolve.sh evolvetest --skill-file "$TMP/SKILL.md" --max-iters 2 > "$TMP/out2.txt"
rc=$?
[ $rc -eq 1 ] || { echo "FAIL: case 2 expected exit 1, got $rc"; cat "$TMP/out2.txt"; exit 1; }
grep -q 'echoes a matrix prompt verbatim' "$TMP/out2.txt" || { echo "FAIL: case 2 missing overfit rejection"; cat "$TMP/out2.txt"; exit 1; }
grep -q '^description: Old description that misses.$' "$TMP/SKILL.md" || { echo "FAIL: case 2 file was modified"; exit 1; }
echo "OK case 2: overfitting rewrite rejected, file untouched"

echo "selftest PASS"
