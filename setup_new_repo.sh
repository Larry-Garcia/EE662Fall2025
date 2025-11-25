#!/bin/bash

# Script to set up and push to a new GitHub repository
# Usage: ./setup_new_repo.sh YOUR_REPO_NAME

REPO_NAME=$1

if [ -z "$REPO_NAME" ]; then
    echo "Usage: ./setup_new_repo.sh YOUR_REPO_NAME"
    echo "Example: ./setup_new_repo.sh EE662Fall2025"
    exit 1
fi

echo "📦 Preparing repository for GitHub..."
echo "Repository name: $REPO_NAME"

# Stage all files (including CSV files)
echo "📝 Staging all files..."
git add .

# Commit changes
echo "💾 Committing changes..."
git commit -m "Initial commit: WSN simulation with data collection tree and metrics"

# Update remote to point to new repository
echo "🔗 Setting up remote..."
git remote set-url origin https://github.com/Larry-Garcia/$REPO_NAME.git

# Check if remote exists, if not add it
if ! git remote get-url origin &>/dev/null; then
    git remote add origin https://github.com/Larry-Garcia/$REPO_NAME.git
fi

echo ""
echo "✅ Local repository is ready!"
echo ""
echo "📋 Next steps:"
echo "1. Go to https://github.com/new"
echo "2. Create a new repository named: $REPO_NAME"
echo "3. DO NOT initialize with README, .gitignore, or license"
echo "4. Then run: git push -u origin main"
echo ""
echo "Or if you want to push now (after creating the repo on GitHub):"
echo "   git push -u origin main"

