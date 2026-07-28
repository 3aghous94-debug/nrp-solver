#!/bin/bash
# =============================================================================
# Push script for nrp-solver repository
# =============================================================================
#
# INSTRUCTIONS:
#
# 1. REVOKE the token you shared in chat — it is compromised.
#    Go to: https://github.com/settings/tokens
#    Delete the token starting with ghp_kOY8PAC...
#
# 2. Create a new token at https://github.com/settings/tokens/new
#    - Note: "nrp-solver-push"
#    - Expiration: 7 days (or whatever you prefer)
#    - Scopes: ✓ repo (full control of private repositories)
#    - Click "Generate token"
#    - COPY the token immediately (you won't see it again)
#
# 3. Create the repository on GitHub:
#    - Go to: https://github.com/new
#    - Repository name: nrp-solver
#    - Description: Envy-Free Nurse Rostering with Coverage, Skills, and Availability
#    - Visibility: Public (or Private, your choice)
#    - DO NOT initialize with README, .gitignore, or license (we have them)
#    - Click "Create repository"
#
# 4. Run this script with your new token:
#
#    cd /home/z/my-project/nrp-solver
#    GITHUB_TOKEN=ghp_YOUR_NEW_TOKEN_HERE bash push_to_github.sh
#
# 5. After successful push, REVOKE the new token too (or let it expire).
#    For future updates, configure git credentials properly:
#    https://docs.github.com/en/get-started/getting-started-with-git/set-up-git
#
# =============================================================================

set -e

REPO_DIR="/home/z/my-project/nrp-solver"
REPO_NAME="nrp-solver"
GITHUB_USER="3aghous94-debug"

if [ -z "$GITHUB_TOKEN" ]; then
    echo "ERROR: GITHUB_TOKEN environment variable not set."
    echo ""
    echo "Usage:"
    echo "  GITHUB_TOKEN=ghp_your_token_here bash push_to_github.sh"
    echo ""
    echo "Get a token from: https://github.com/settings/tokens/new"
    echo "Required scope: repo"
    exit 1
fi

cd "$REPO_DIR"

echo "=== Pushing nrp-solver to GitHub ==="
echo "User: $GITHUB_USER"
echo "Repo: $REPO_NAME"
echo ""

# Verify we're on the main branch with a commit
echo "=== Current git state ==="
git log --oneline -1
git branch --show-current
echo ""

# Set the remote (remove if exists, then add fresh)
git remote remove origin 2>/dev/null || true

# Use the token in the remote URL (will be stored in .git/config)
# Note: this stores the token in plain text in .git/config
# We'll remove it after the push
REMOTE_URL="https://${GITHUB_USER}:${GITHUB_TOKEN}@github.com/${GITHUB_USER}/${REPO_NAME}.git"
git remote add origin "$REMOTE_URL"

echo "=== Pushing to GitHub ==="
git push -u origin main

# Remove the token from the remote URL (replace with token-less URL)
git remote set-url origin "https://github.com/${GITHUB_USER}/${REPO_NAME}.git"

echo ""
echo "=== Success! ==="
echo "Your repository is now at: https://github.com/${GITHUB_USER}/${REPO_NAME}"
echo ""
echo "The token has been removed from the local git config."
echo "For future pushes, you'll need to authenticate again (token, SSH key, or credential helper)."
echo ""
echo "REMEMBER: Revoke the token at https://github.com/settings/tokens when done."
