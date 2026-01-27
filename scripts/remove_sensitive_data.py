#!/usr/bin/env python
"""
Script to remove sensitive data from git history using git filter-repo.

This script removes all occurrences of sensitive data (API keys, library IDs) from git history.

Usage:
    python scripts/remove_sensitive_data.py

WARNING: This rewrites git history. Make sure you have a backup before running!
"""

import subprocess
import sys

# Sensitive data patterns to remove
SENSITIVE_PATTERNS = [
    ("5452188", "REDACTED_LIBRARY_ID"),
    ("nYnc5ygaobQstQyxt3K2632N", "REDACTED_API_KEY"),
    ("sk-84adad772ff5439a853cf2159153861e", "REDACTED_DEEPSEEK_KEY"),
]


def check_git_filter_repo():
    """Check if git-filter-repo is available."""
    try:
        result = subprocess.run(
            ["git", "filter-repo", "--version"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            print(f"✓ git-filter-repo version: {result.stdout.strip()}")
            return True
        else:
            print("✗ git-filter-repo not found")
            return False
    except FileNotFoundError:
        print("✗ git command not found")
        return False


def install_instructions():
    """Print installation instructions for git-filter-repo."""
    print("\n" + "=" * 70)
    print("git-filter-repo is not installed.")
    print("=" * 70)
    print("\nInstallation instructions:")
    print("\n1. Using pip:")
    print("   pip install git-filter-repo")
    print("\n2. Using system package manager:")
    print("   - Ubuntu/Debian: sudo apt install git-filter-repo")
    print("   - macOS: brew install git-filter-repo")
    print("   - Windows: pip install git-filter-repo")
    print("\n3. Manual download:")
    print("   Download from: https://github.com/newren/git-filter-repo")
    print("=" * 70)


def create_replacements_file():
    """Create a replacements file for git-filter-repo."""
    replacements_file = "git_replacements.txt"

    with open(replacements_file, "w", encoding="utf-8") as f:
        for old, new in SENSITIVE_PATTERNS:
            # Use literal string replacement
            f.write(f"literal:{old}==>{new}\n")

    print(f"\n✓ Created replacements file: {replacements_file}")
    print(f"  Contains {len(SENSITIVE_PATTERNS)} replacement patterns")

    return replacements_file


def run_filter_repo(replacements_file):
    """Run git-filter-repo to remove sensitive data."""
    print("\n" + "=" * 70)
    print("WARNING: This will rewrite git history!")
    print("=" * 70)
    print("\nMake sure you have:")
    print("  1. Committed or stashed all changes")
    print("  2. Created a backup of your repository")
    print("  3. Informed collaborators (if any)")
    print("\n" + "=" * 70)

    response = input("\nProceed with rewriting history? (yes/no): ").strip().lower()

    if response != "yes":
        print("\n✗ Operation cancelled by user")
        return False

    print("\n🔧 Running git filter-repo...")

    # Run git filter-repo
    cmd = [
        "git",
        "filter-repo",
        "--replace-text",
        replacements_file,
        "--force",
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)

        if result.returncode == 0:
            print("\n✓ Git history successfully rewritten!")
            print("\nNext steps:")
            print("  1. Verify the changes: git log --oneline")
            print("  2. Force push to remote: git push origin main --force")
            print("  3. Notify collaborators to re-clone the repository")
            return True
        else:
            print(f"\n✗ Error running git filter-repo:")
            print(result.stderr)
            return False
    except Exception as e:
        print(f"\n✗ Exception occurred: {e}")
        return False


def main():
    """Main function."""
    print("=" * 70)
    print("Git History Cleanup - Remove Sensitive Data")
    print("=" * 70)

    # Check if git-filter-repo is available
    if not check_git_filter_repo():
        install_instructions()
        sys.exit(1)

    # Create replacements file
    replacements_file = create_replacements_file()

    # Run filter-repo
    success = run_filter_repo(replacements_file)

    if success:
        print("\n✓ Cleanup completed successfully!")
        sys.exit(0)
    else:
        print("\n✗ Cleanup failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()
