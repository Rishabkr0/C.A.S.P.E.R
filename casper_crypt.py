#!/usr/bin/env python3
"""
Casper-Crypt: Transparent AES-256-GCM Git Encryption Filter
Protects source files on GitHub, in downloaded ZIPs, and in git clones.
"""

import os
import sys
import base64
import argparse
import subprocess
from pathlib import Path

HEADER_TAG = b"-----BEGIN CASPER ENCRYPTED FILE-----"
HEADER_END_TAG = b"-----END CASPER ENCRYPTED FILE-----"

NOTICE_TEXT = (
    "Version: 1.0\n"
    "Algorithm: AES-256-GCM\n"
    "Notice: This file is encrypted. Run 'python casper_crypt.py unlock' with your key to decrypt.\n\n"
)

KEY_FILE_NAME = ".casper_key"
REPO_ROOT = Path(__file__).resolve().parent


def get_cipher():
    """Ensure AESGCM is importable or fallback gracefully."""
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        return AESGCM
    except ImportError:
        # Check if venv exists in repo
        candidates = [
            REPO_ROOT / ".venv" / "Scripts" / "python.exe",
            REPO_ROOT / "venv" / "Scripts" / "python.exe",
            REPO_ROOT / ".venv" / "bin" / "python",
            REPO_ROOT / "venv" / "bin" / "python",
        ]
        for venv_py in candidates:
            if venv_py.is_file():
                # Re-exec with virtualenv
                proc = subprocess.run(
                    [str(venv_py), os.path.abspath(__file__)] + sys.argv[1:],
                    input=sys.stdin.buffer.read(),
                    capture_output=True,
                )
                sys.stdout.buffer.write(proc.stdout)
                sys.stderr.buffer.write(proc.stderr)
                sys.exit(proc.returncode)

        sys.stderr.write(
            "[casper-crypt] Error: 'cryptography' library is required.\n"
            "Run: pip install cryptography\n"
        )
        sys.exit(1)


def get_key_path() -> Path:
    return REPO_ROOT / KEY_FILE_NAME


def load_key() -> bytes | None:
    """Load the 256-bit encryption key from env or .casper_key."""
    env_key = os.environ.get("CASPER_CRYPT_KEY")
    if env_key:
        try:
            raw = base64.b64decode(env_key.strip())
            if len(raw) == 32:
                return raw
        except Exception:
            pass

    key_path = get_key_path()
    if key_path.is_file():
        try:
            content = key_path.read_bytes().strip()
            raw = base64.b64decode(content)
            if len(raw) == 32:
                return raw
        except Exception:
            pass
    return None


def generate_new_key() -> str:
    """Generate a cryptographic 256-bit key."""
    AESGCM = get_cipher()
    key = AESGCM.generate_key(bit_length=256)
    return base64.b64encode(key).decode("utf-8")


def save_key(key_b64: str):
    """Save key to .casper_key."""
    key_path = get_key_path()
    key_path.write_text(key_b64.strip() + "\n", encoding="utf-8")
    # Add to .gitignore if not present
    ensure_gitignore_has_key()


def ensure_gitignore_has_key():
    gitignore_path = REPO_ROOT / ".gitignore"
    patterns = [".casper_key", "casper.key", "*.key", ".casper_key.bak"]
    content = ""
    if gitignore_path.is_file():
        content = gitignore_path.read_text(encoding="utf-8", errors="ignore")

    missing = [p for p in patterns if p not in content]
    if missing:
        with open(gitignore_path, "a", encoding="utf-8") as f:
            f.write("\n# Casper Crypt Key Files (CRITICAL: Never commit to Git)\n")
            for m in missing:
                f.write(f"{m}\n")


def encrypt_bytes(data: bytes, key: bytes) -> bytes:
    """Encrypt byte buffer using AES-256-GCM and wrap in armored block."""
    if not data or HEADER_TAG in data:
        return data  # 0-byte or already encrypted

    AESGCM = get_cipher()
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)  # 96-bit nonce
    ciphertext = aesgcm.encrypt(nonce, data, None)  # Appends 128-bit authentication tag
    payload = base64.b64encode(nonce + ciphertext)

    # 76-character wrapped base64 lines
    lines = [payload[i : i + 76] for i in range(0, len(payload), 76)]
    wrapped_payload = b"\n".join(lines)

    header = HEADER_TAG + b"\n" + NOTICE_TEXT.encode("utf-8")
    footer = b"\n" + HEADER_END_TAG + b"\n"
    return header + wrapped_payload + footer


def decrypt_bytes(data: bytes, key: bytes) -> bytes:
    """Decrypt armored block using AES-256-GCM."""
    if not data or HEADER_TAG not in data:
        return data  # Not encrypted

    start = data.find(HEADER_TAG) + len(HEADER_TAG)
    end = data.find(HEADER_END_TAG)
    if end == -1:
        end = len(data)

    body = data[start:end]
    # Filter out header/notice lines and newlines
    b64_lines = []
    for line in body.splitlines():
        line_clean = line.strip()
        if not line_clean:
            continue
        if (
            line_clean.startswith(b"Version:")
            or line_clean.startswith(b"Algorithm:")
            or line_clean.startswith(b"Notice:")
        ):
            continue
        b64_lines.append(line_clean)

    b64_payload = b"".join(b64_lines)
    raw = base64.b64decode(b64_payload)
    nonce = raw[:12]
    ciphertext = raw[12:]

    AESGCM = get_cipher()
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(nonce, ciphertext, None)


# -------------------------------------------------------------
# Git Filter Handlers
# -------------------------------------------------------------

def handle_clean():
    """Clean filter: Called by Git on 'git add' / commit. Plaintext -> Ciphertext."""
    key = load_key()
    data = sys.stdin.buffer.read()
    if not key:
        # If no key, don't corrupt the file; pass through
        sys.stderr.write("[casper-crypt] Warning: No decryption key found. Passing unencrypted.\n")
        sys.stdout.buffer.write(data)
        return

    try:
        encrypted = encrypt_bytes(data, key)
        sys.stdout.buffer.write(encrypted)
    except Exception as e:
        sys.stderr.write(f"[casper-crypt] Clean error: {e}\n")
        sys.stdout.buffer.write(data)


def handle_smudge():
    """Smudge filter: Called by Git on checkout/pull. Ciphertext -> Plaintext."""
    key = load_key()
    data = sys.stdin.buffer.read()
    if not key or HEADER_TAG not in data:
        # If no key or not encrypted, keep file in its repository state (stay encrypted!)
        sys.stdout.buffer.write(data)
        return

    try:
        decrypted = decrypt_bytes(data, key)
        sys.stdout.buffer.write(decrypted)
    except Exception as e:
        sys.stderr.write(f"[casper-crypt] Smudge error: {e}. Preserving ciphertext.\n")
        sys.stdout.buffer.write(data)


def handle_textconv(filename: str):
    """Textconv filter: Called by Git for 'git diff'."""
    key = load_key()
    path = Path(filename)
    if not path.is_file():
        return
    data = path.read_bytes()
    if HEADER_TAG not in data:
        sys.stdout.buffer.write(data)
        return
    if not key:
        sys.stdout.write("[casper-crypt: Encrypted File - Key not loaded]\n")
        return
    try:
        sys.stdout.buffer.write(decrypt_bytes(data, key))
    except Exception as e:
        sys.stdout.write(f"[casper-crypt: Decryption Error: {e}]\n")


# -------------------------------------------------------------
# Setup & Repository Management Commands
# -------------------------------------------------------------

def configure_git():
    """Configure local git repository filters."""
    py_cmd = "python casper_crypt.py"
    subprocess.run(["git", "config", "filter.casper-crypt.clean", f"{py_cmd} clean"], check=True)
    subprocess.run(["git", "config", "filter.casper-crypt.smudge", f"{py_cmd} smudge"], check=True)
    subprocess.run(["git", "config", "filter.casper-crypt.required", "true"], check=True)
    subprocess.run(["git", "config", "diff.casper-crypt.textconv", f"{py_cmd} textconv"], check=True)


def update_gitattributes():
    """Ensure .gitattributes has protective rules for source code."""
    gitattributes_path = REPO_ROOT / ".gitattributes"
    current = ""
    if gitattributes_path.is_file():
        current = gitattributes_path.read_text(encoding="utf-8", errors="ignore")

    rules = """
# Casper-Crypt: Zero-Trust Transparent AES-256-GCM Git Encryption
casper_crypt.py -filter -diff
README.md -filter -diff
LICENSE.md -filter -diff
requirements.txt -filter -diff
.gitattributes -filter -diff
.gitignore -filter -diff

*.py filter=casper-crypt diff=casper-crypt
*.html filter=casper-crypt diff=casper-crypt
*.js filter=casper-crypt diff=casper-crypt
*.css filter=casper-crypt diff=casper-crypt
*.json filter=casper-crypt diff=casper-crypt
*.spec filter=casper-crypt diff=casper-crypt
"""
    if "filter=casper-crypt" not in current:
        with open(gitattributes_path, "a", encoding="utf-8") as f:
            f.write("\n" + rules.strip() + "\n")


def is_protected_file(file_path: Path) -> bool:
    rel = file_path.relative_to(REPO_ROOT).as_posix()
    # Unencrypted exceptions
    if rel in ("casper_crypt.py", "README.md", "LICENSE.md", "requirements.txt", ".gitattributes", ".gitignore"):
        return False
    if ".git" in rel or ".venv" in rel or "__pycache__" in rel or "node_modules" in rel or "build" in rel or "dist" in rel:
        return False
    # Target extensions
    return file_path.suffix.lower() in (".py", ".html", ".js", ".css", ".json", ".spec")


def cmd_init():
    """Initialize casper-crypt for the repository."""
    print("=" * 60)
    print("      CASPER-CRYPT: GIT ENCRYPTION INITIALIZATION")
    print("=" * 60)

    key_path = get_key_path()
    if key_path.is_file():
        print(f"[+] Existing master key found at: {key_path.name}")
        key_b64 = key_path.read_text(encoding="utf-8").strip()
    else:
        print("[+] Generating fresh 256-bit AES-GCM Master Key...")
        key_b64 = generate_new_key()
        save_key(key_b64)
        print(f"[+] Master key created and saved to: {key_path.name}")

    ensure_gitignore_has_key()
    print("[+] Verified .gitignore contains .casper_key")

    update_gitattributes()
    print("[+] Verified .gitattributes configuration")

    configure_git()
    print("[+] Configured Git filters (clean, smudge, textconv)")

    print("\n" + "=" * 60)
    print(">>> YOUR CASPER MASTER KEY (SAVE THIS SAFELY!): <<<")
    print(f"\n    {key_b64}\n")
    print("=" * 60)
    print("IMPORTANT:")
    print("1. If anyone downloads the ZIP from GitHub or clones the repository,")
    print("   all source files will be encrypted ciphertext.")
    print("2. You will need this key to unlock the files on any new computer:")
    print(f"   python casper_crypt.py unlock --key {key_b64[:10]}...")
    print("3. Keep this key in your password manager or private notes.\n")


def cmd_unlock(provided_key: str | None = None):
    """Unlock files in working directory."""
    if not provided_key:
        key_path = get_key_path()
        if key_path.is_file():
            provided_key = key_path.read_text(encoding="utf-8").strip()
        else:
            provided_key = input("Enter Casper Master Key (Base64): ").strip()

    try:
        raw = base64.b64decode(provided_key)
        if len(raw) != 32:
            raise ValueError("Key must be 32 bytes (256 bits).")
    except Exception as e:
        print(f"[-] Invalid master key format: {e}")
        sys.exit(1)

    save_key(provided_key)
    configure_git()
    key = raw

    # Decrypt working tree files in place
    count = 0
    for path in REPO_ROOT.rglob("*"):
        if path.is_file() and is_protected_file(path):
            try:
                data = path.read_bytes()
                if HEADER_TAG in data:
                    decrypted = decrypt_bytes(data, key)
                    path.write_bytes(decrypted)
                    count += 1
            except Exception as e:
                print(f"[-] Error decrypting {path.name}: {e}")

    print(f"[+] Repository successfully unlocked! ({count} files decrypted to plaintext)")


def cmd_lock():
    """Lock repository files locally on disk."""
    key = load_key()
    if not key:
        print("[-] Repository is already locked (no master key found).")
        return

    # Encrypt working tree files in place
    count = 0
    for path in REPO_ROOT.rglob("*"):
        if path.is_file() and is_protected_file(path):
            try:
                data = path.read_bytes()
                if HEADER_TAG not in data:
                    encrypted = encrypt_bytes(data, key)
                    path.write_bytes(encrypted)
                    count += 1
            except Exception as e:
                print(f"[-] Error encrypting {path.name}: {e}")

    # Remove active key file
    key_path = get_key_path()
    if key_path.is_file():
        bak = REPO_ROOT / ".casper_key.bak"
        key_path.rename(bak)
        print(f"[+] Key moved to backup: {bak.name}")

    print(f"[+] Repository locked! ({count} files encrypted to ciphertext on disk)")


def cmd_status():
    """Show encryption and filter status."""
    key = load_key()
    print("=" * 60)
    print("           CASPER-CRYPT REPOSITORY STATUS")
    print("=" * 60)
    print(f"Master Key Present:   {'YES (Unlocked)' if key else 'NO (Locked / Encrypted)'}")
    if key:
        print(f"Key File:             {get_key_path()}")

    # Git filter check
    try:
        res = subprocess.run(["git", "config", "filter.casper-crypt.clean"], capture_output=True, text=True)
        git_clean = res.stdout.strip()
        print(f"Git Clean Filter:     {git_clean if git_clean else 'NOT CONFIGURED'}")
    except Exception:
        print("Git Clean Filter:     ERROR checking git config")

    # Count files
    encrypted_count = 0
    plaintext_count = 0
    for path in REPO_ROOT.rglob("*"):
        if path.is_file() and is_protected_file(path):
            try:
                data = path.read_bytes()
                if HEADER_TAG in data:
                    encrypted_count += 1
                else:
                    plaintext_count += 1
            except Exception:
                pass

    print(f"Protected Files:      {plaintext_count + encrypted_count} total")
    print(f"  - Plaintext:        {plaintext_count}")
    print(f"  - Encrypted:        {encrypted_count}")
    print("=" * 60)


def cmd_show_key():
    """Display active master key."""
    key_path = get_key_path()
    if key_path.is_file():
        key_b64 = key_path.read_text(encoding="utf-8").strip()
        print(f"Casper Master Key: {key_b64}")
    else:
        print("No active .casper_key found in repository.")


# -------------------------------------------------------------
# CLI Entry Point
# -------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Casper-Crypt: Transparent AES-256-GCM Git Encryption Filter")
    subparsers = parser.add_subparsers(dest="command")

    # Git filter subcommands
    subparsers.add_parser("clean", help="Git clean filter (plaintext -> encrypted)")
    subparsers.add_parser("smudge", help="Git smudge filter (encrypted -> plaintext)")
    textconv_parser = subparsers.add_parser("textconv", help="Git textconv diff filter")
    textconv_parser.add_argument("file", help="File to decrypt for diff")

    # User management commands
    subparsers.add_parser("init", help="Initialize casper-crypt, generate master key, and configure git")
    unlock_parser = subparsers.add_parser("unlock", help="Unlock repository files using master key")
    unlock_parser.add_argument("--key", help="Base64 256-bit master key")
    subparsers.add_parser("lock", help="Encrypt working files on disk and lock repository")
    subparsers.add_parser("status", help="Show current encryption and filter status")
    subparsers.add_parser("key", help="Display the active master key")

    args = parser.parse_args()

    if args.command == "clean":
        handle_clean()
    elif args.command == "smudge":
        handle_smudge()
    elif args.command == "textconv":
        handle_textconv(args.file)
    elif args.command == "init":
        cmd_init()
    elif args.command == "unlock":
        cmd_unlock(args.key)
    elif args.command == "lock":
        cmd_lock()
    elif args.command == "status":
        cmd_status()
    elif args.command == "key":
        cmd_show_key()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
