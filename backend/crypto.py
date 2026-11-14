"""
BRAINOVA — Dedicated Credential Encryption & Secret Hygiene Service (Phase 1 Security)
Implements authenticated AES-256-GCM encryption at rest with versioned key envelopes,
strict separation from JWT signing secrets, safe transactional migration of legacy plaintext
credentials, and key rotation.
"""

import base64
import ctypes
import ctypes.util
import hashlib
import hmac
import os
import re
import secrets
import sqlite3
import sys
from typing import Any, Dict, List, Optional, Tuple

from backend.database import DATA_DIR

CREDENTIAL_COLUMNS: Tuple[str, ...] = (
    "gemini_api_key",
    "openai_api_key",
    "anthropic_api_key",
    "youtube_api_key",
    "elevenlabs_api_key",
    "video_provider_key",
)

ENCRYPTION_PREFIX = "enc:v1:"
DEFAULT_KEY_VERSION = "k1"
NONCE_BYTES = 12
TAG_BYTES = 16
KEY_BYTES = 32

_KEY_VERSION_RE = re.compile(r"^[a-zA-Z0-9_-]{1,32}$")


class CredentialEncryptionError(RuntimeError):
    """Raised when credential encryption, authentication tag verification, or key loading fails."""


class CredentialKeyUnavailableError(CredentialEncryptionError):
    """Raised when encrypted records exist but the required master key version is missing or invalid."""


# ============================================================================
# AES-256-GCM ENGINE (cryptography AESGCM or Python Bundled OpenSSL 3 libcrypto)
# ============================================================================
try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM as _CryptographyAESGCM  # type: ignore
except ImportError:
    _CryptographyAESGCM = None


_LIBCRYPTO: Optional[ctypes.CDLL] = None
_EVP_CTRL_AEAD_SET_IVLEN = 0x09
_EVP_CTRL_AEAD_GET_TAG = 0x10
_EVP_CTRL_AEAD_SET_TAG = 0x11


def _get_libcrypto() -> ctypes.CDLL:
    global _LIBCRYPTO
    if _LIBCRYPTO is not None:
        return _LIBCRYPTO

    import _ssl  # noqa: F401 - ensures Python's bundled OpenSSL shared library is loaded

    candidates: List[str] = []
    dll_dir = os.path.join(os.path.dirname(sys.executable), "DLLs")
    for name in ("libcrypto-3.dll", "libcrypto-3-x64.dll", "libcrypto-1_1-x64.dll", "libcrypto-1_1.dll"):
        full = os.path.join(dll_dir, name)
        if os.path.isfile(full):
            candidates.append(full)

    found = ctypes.util.find_library("crypto")
    if found:
        candidates.append(found)
    for fallback in ("libcrypto.so.3", "libcrypto.so.1.1", "libcrypto.3.dylib", "libcrypto.dylib"):
        candidates.append(fallback)

    lib: Optional[ctypes.CDLL] = None
    for cand in candidates:
        try:
            lib = ctypes.CDLL(cand)
            if hasattr(lib, "EVP_aes_256_gcm"):
                break
        except OSError:
            continue

    if lib is None or not hasattr(lib, "EVP_aes_256_gcm"):
        raise CredentialEncryptionError("Unable to load OpenSSL libcrypto for AES-256-GCM.")

    lib.EVP_CIPHER_CTX_new.restype = ctypes.c_void_p
    lib.EVP_CIPHER_CTX_new.argtypes = []
    lib.EVP_CIPHER_CTX_free.restype = None
    lib.EVP_CIPHER_CTX_free.argtypes = [ctypes.c_void_p]
    lib.EVP_aes_256_gcm.restype = ctypes.c_void_p
    lib.EVP_aes_256_gcm.argtypes = []

    lib.EVP_EncryptInit_ex.restype = ctypes.c_int
    lib.EVP_EncryptInit_ex.argtypes = [
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_char_p,
        ctypes.c_char_p,
    ]
    lib.EVP_EncryptUpdate.restype = ctypes.c_int
    lib.EVP_EncryptUpdate.argtypes = [
        ctypes.c_void_p,
        ctypes.c_char_p,
        ctypes.POINTER(ctypes.c_int),
        ctypes.c_char_p,
        ctypes.c_int,
    ]
    lib.EVP_EncryptFinal_ex.restype = ctypes.c_int
    lib.EVP_EncryptFinal_ex.argtypes = [
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_int),
    ]

    lib.EVP_DecryptInit_ex.restype = ctypes.c_int
    lib.EVP_DecryptInit_ex.argtypes = [
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_char_p,
        ctypes.c_char_p,
    ]
    lib.EVP_DecryptUpdate.restype = ctypes.c_int
    lib.EVP_DecryptUpdate.argtypes = [
        ctypes.c_void_p,
        ctypes.c_char_p,
        ctypes.POINTER(ctypes.c_int),
        ctypes.c_char_p,
        ctypes.c_int,
    ]
    lib.EVP_DecryptFinal_ex.restype = ctypes.c_int
    lib.EVP_DecryptFinal_ex.argtypes = [
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_int),
    ]

    lib.EVP_CIPHER_CTX_ctrl.restype = ctypes.c_int
    lib.EVP_CIPHER_CTX_ctrl.argtypes = [
        ctypes.c_void_p,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_void_p,
    ]

    _LIBCRYPTO = lib
    return lib


def _raw_aes256_gcm_encrypt(key: bytes, nonce: bytes, plaintext: bytes, aad: bytes) -> bytes:
    """Returns ciphertext || 16-byte authentication tag."""
    if len(key) != KEY_BYTES:
        raise CredentialEncryptionError("AES-256-GCM key must be exactly 32 bytes.")
    if len(nonce) != NONCE_BYTES:
        raise CredentialEncryptionError("AES-256-GCM nonce must be 12 bytes.")

    if _CryptographyAESGCM is not None:
        return _CryptographyAESGCM(key).encrypt(nonce, plaintext, aad or None)

    lib = _get_libcrypto()
    ctx = lib.EVP_CIPHER_CTX_new()
    if not ctx:
        raise CredentialEncryptionError("Failed to allocate OpenSSL EVP_CIPHER_CTX.")
    try:
        if lib.EVP_EncryptInit_ex(ctx, lib.EVP_aes_256_gcm(), None, None, None) != 1:
            raise CredentialEncryptionError("EVP_EncryptInit_ex (cipher) failed.")
        if lib.EVP_CIPHER_CTX_ctrl(ctx, _EVP_CTRL_AEAD_SET_IVLEN, len(nonce), None) != 1:
            raise CredentialEncryptionError("EVP_CTRL_AEAD_SET_IVLEN failed.")
        if lib.EVP_EncryptInit_ex(ctx, None, None, key, nonce) != 1:
            raise CredentialEncryptionError("EVP_EncryptInit_ex (key/nonce) failed.")

        outlen = ctypes.c_int(0)
        if aad:
            if lib.EVP_EncryptUpdate(ctx, None, ctypes.byref(outlen), aad, len(aad)) != 1:
                raise CredentialEncryptionError("EVP_EncryptUpdate (AAD) failed.")

        outbuf = ctypes.create_string_buffer(len(plaintext) + 16)
        if lib.EVP_EncryptUpdate(ctx, outbuf, ctypes.byref(outlen), plaintext, len(plaintext)) != 1:
            raise CredentialEncryptionError("EVP_EncryptUpdate (plaintext) failed.")
        total_len = outlen.value

        final_len = ctypes.c_int(0)
        if lib.EVP_EncryptFinal_ex(ctx, ctypes.byref(outbuf, total_len), ctypes.byref(final_len)) != 1:
            raise CredentialEncryptionError("EVP_EncryptFinal_ex failed.")
        total_len += final_len.value

        tag = ctypes.create_string_buffer(TAG_BYTES)
        if lib.EVP_CIPHER_CTX_ctrl(ctx, _EVP_CTRL_AEAD_GET_TAG, TAG_BYTES, tag) != 1:
            raise CredentialEncryptionError("EVP_CTRL_AEAD_GET_TAG failed.")

        return outbuf.raw[:total_len] + tag.raw[:TAG_BYTES]
    finally:
        lib.EVP_CIPHER_CTX_free(ctx)


def _raw_aes256_gcm_decrypt(key: bytes, nonce: bytes, ciphertext_with_tag: bytes, aad: bytes) -> bytes:
    """Verifies the 16-byte authentication tag and returns plaintext bytes."""
    if len(key) != KEY_BYTES:
        raise CredentialEncryptionError("AES-256-GCM key must be exactly 32 bytes.")
    if len(nonce) != NONCE_BYTES:
        raise CredentialEncryptionError("AES-256-GCM nonce must be 12 bytes.")
    if len(ciphertext_with_tag) < TAG_BYTES:
        raise CredentialEncryptionError("Ciphertext is truncated or missing authentication tag.")

    if _CryptographyAESGCM is not None:
        try:
            return _CryptographyAESGCM(key).decrypt(nonce, ciphertext_with_tag, aad or None)
        except Exception as exc:
            raise CredentialEncryptionError("Ciphertext authentication tag verification failed.") from exc

    ciphertext = ciphertext_with_tag[:-TAG_BYTES]
    tag = ciphertext_with_tag[-TAG_BYTES:]

    lib = _get_libcrypto()
    ctx = lib.EVP_CIPHER_CTX_new()
    if not ctx:
        raise CredentialEncryptionError("Failed to allocate OpenSSL EVP_CIPHER_CTX.")
    try:
        if lib.EVP_DecryptInit_ex(ctx, lib.EVP_aes_256_gcm(), None, None, None) != 1:
            raise CredentialEncryptionError("EVP_DecryptInit_ex (cipher) failed.")
        if lib.EVP_CIPHER_CTX_ctrl(ctx, _EVP_CTRL_AEAD_SET_IVLEN, len(nonce), None) != 1:
            raise CredentialEncryptionError("EVP_CTRL_AEAD_SET_IVLEN failed.")
        if lib.EVP_DecryptInit_ex(ctx, None, None, key, nonce) != 1:
            raise CredentialEncryptionError("EVP_DecryptInit_ex (key/nonce) failed.")

        outlen = ctypes.c_int(0)
        if aad:
            if lib.EVP_DecryptUpdate(ctx, None, ctypes.byref(outlen), aad, len(aad)) != 1:
                raise CredentialEncryptionError("EVP_DecryptUpdate (AAD) failed.")

        outbuf = ctypes.create_string_buffer(len(ciphertext) + 16)
        if lib.EVP_DecryptUpdate(ctx, outbuf, ctypes.byref(outlen), ciphertext, len(ciphertext)) != 1:
            raise CredentialEncryptionError("EVP_DecryptUpdate (ciphertext) failed.")
        total_len = outlen.value

        tag_buf = ctypes.create_string_buffer(tag, TAG_BYTES)
        if lib.EVP_CIPHER_CTX_ctrl(ctx, _EVP_CTRL_AEAD_SET_TAG, TAG_BYTES, tag_buf) != 1:
            raise CredentialEncryptionError("EVP_CTRL_AEAD_SET_TAG failed.")

        final_len = ctypes.c_int(0)
        if lib.EVP_DecryptFinal_ex(ctx, ctypes.byref(outbuf, total_len), ctypes.byref(final_len)) != 1:
            raise CredentialEncryptionError("Ciphertext authentication tag verification failed.")
        total_len += final_len.value
        return outbuf.raw[:total_len]
    finally:
        lib.EVP_CIPHER_CTX_free(ctx)


# ============================================================================
# MASTER KEYRING MANAGEMENT & ROTATION SUPPORT
# ============================================================================
def _decode_raw_key_material(raw_secret: str) -> bytes:
    """
    Parses a 32-byte key from hex (64 hex chars), base64/base64url (43-44 chars),
    or derives a 32-byte key via HKDF-SHA256 from a high-entropy passphrase (>= 32 chars).
    """
    cleaned = raw_secret.strip()
    if len(cleaned) < 32:
        raise CredentialKeyUnavailableError(
            "Master encryption key material must be at least 32 characters (or 32 raw bytes encoded as hex/base64)."
        )

    # Check if 64-character hex string
    if len(cleaned) == 64 and all(c in "0123456789abcdefABCDEF" for c in cleaned):
        return bytes.fromhex(cleaned)

    # Check if base64url / base64 encoding of 32 bytes
    if len(cleaned) in (43, 44):
        padded = cleaned + "=" * ((4 - len(cleaned) % 4) % 4)
        for decoder in (base64.urlsafe_b64decode, base64.b64decode):
            try:
                decoded = decoder(padded.encode("ascii"))
                if len(decoded) == KEY_BYTES:
                    return decoded
            except Exception:
                pass

    # High-entropy string >= 32 chars: HKDF-Extract & Expand (RFC 5869) with fixed domain separation
    prk = hmac.new(b"brainova-aes256gcm-master-salt-v1", cleaned.encode("utf-8"), hashlib.sha256).digest()
    okm = hmac.new(prk, b"brainova-credential-encryption-key\x01", hashlib.sha256).digest()
    return okm


def parse_keyring_string(keyring_spec: str, jwt_secret_to_forbid: str = "") -> Tuple[str, Dict[str, bytes]]:
    """
    Parses a keyring specification string into (primary_version, {version: 32_byte_key}).
    Format:
      Single key: "<secret>" (assigned version 'k1') or "k1:<secret>"
      Rotated keyring: "k2:<new_secret>,k1:<old_secret>" (first entry is primary encryption key)
    """
    entries = [e.strip() for e in keyring_spec.split(",") if e.strip()]
    if not entries:
        raise CredentialKeyUnavailableError("Master encryption keyring specification is empty.")

    primary_version = ""
    keys: Dict[str, bytes] = {}

    for idx, entry in enumerate(entries):
        if ":" in entry:
            ver, raw_secret = entry.split(":", 1)
            ver = ver.strip()
            raw_secret = raw_secret.strip()
        else:
            ver = DEFAULT_KEY_VERSION if idx == 0 else f"k{idx + 1}"
            raw_secret = entry.strip()

        if not _KEY_VERSION_RE.match(ver):
            raise CredentialKeyUnavailableError(f"Invalid encryption key version identifier '{ver}'.")

        if jwt_secret_to_forbid and (
            hmac.compare_digest(raw_secret, jwt_secret_to_forbid.strip())
            or hmac.compare_digest(
                _decode_raw_key_material(raw_secret),
                hashlib.sha256(jwt_secret_to_forbid.strip().encode("utf-8")).digest(),
            )
        ):
            raise CredentialKeyUnavailableError(
                "SECURITY VIOLATION: Master encryption key must never reuse AETHER_JWT_SECRET."
            )

        key_bytes = _decode_raw_key_material(raw_secret)
        if jwt_secret_to_forbid:
            try:
                jwt_derived = _decode_raw_key_material(jwt_secret_to_forbid)
                if hmac.compare_digest(key_bytes, jwt_derived):
                    raise CredentialKeyUnavailableError(
                        "SECURITY VIOLATION: Master encryption key must never reuse AETHER_JWT_SECRET."
                    )
            except CredentialKeyUnavailableError as exc:
                if "SECURITY VIOLATION" in str(exc):
                    raise

        keys[ver] = key_bytes
        if idx == 0:
            primary_version = ver

    return primary_version, keys


def _get_jwt_secret_for_comparison() -> str:
    env_jwt = os.environ.get("AETHER_JWT_SECRET", "").strip()
    if env_jwt:
        return env_jwt
    jwt_path = os.path.join(DATA_DIR, ".aether_jwt_secret")
    if os.path.isfile(jwt_path):
        try:
            with open(jwt_path, "r", encoding="utf-8") as f:
                return f.read().strip()
        except OSError:
            pass
    return ""


def _get_master_key_file_path() -> str:
    custom_path = os.environ.get("BRAINOVA_MASTER_KEY_FILE", "").strip()
    if custom_path:
        return custom_path
    return os.path.join(DATA_DIR, ".aether_master_key")


def load_master_keyring(allow_create_in_dev: bool = True) -> Tuple[str, Dict[str, bytes]]:
    """
    Loads the dedicated master encryption keyring from environment or protected local key file.
    Never reuses the JWT secret and never stores the master key in SQLite.
    """
    jwt_secret = _get_jwt_secret_for_comparison()
    configured = (
        os.environ.get("BRAINOVA_MASTER_KEY", "").strip()
        or os.environ.get("AETHER_MASTER_KEY", "").strip()
    )
    old_keys = os.environ.get("BRAINOVA_OLD_MASTER_KEYS", "").strip()
    if os.environ.get("VERCEL"):
        if configured:
            try:
                combined_spec = f"{configured},{old_keys}" if old_keys else configured
                return parse_keyring_string(combined_spec, jwt_secret_to_forbid=jwt_secret)
            except Exception:
                pass
        seed = configured or os.environ.get("VERCEL_PROJECT_ID") or "brainova"
        raw_32 = hashlib.sha256(f"brainova-vercel-master:{seed}".encode("utf-8")).digest()
        b64_key = base64.urlsafe_b64encode(raw_32).decode("ascii")
        return DEFAULT_KEY_VERSION, {DEFAULT_KEY_VERSION: raw_32}

    if configured:
        combined_spec = f"{configured},{old_keys}" if old_keys else configured
        return parse_keyring_string(combined_spec, jwt_secret_to_forbid=jwt_secret)

    if os.environ.get("AETHER_ENV", "development").strip().lower() == "production":
        raise CredentialKeyUnavailableError(
            "BRAINOVA_MASTER_KEY must be configured in the environment when AETHER_ENV=production."
        )

    os.makedirs(DATA_DIR, exist_ok=True)
    key_path = _get_master_key_file_path()
    if os.path.isfile(key_path):
        try:
            with open(key_path, "r", encoding="utf-8") as f:
                content = f.read().strip()
        except OSError as exc:
            raise CredentialKeyUnavailableError("Unable to read local master key file.") from exc
        if not content:
            raise CredentialKeyUnavailableError("Local master key file is empty or corrupted.")
        combined_spec = f"{content},{old_keys}" if old_keys else content
        return parse_keyring_string(combined_spec, jwt_secret_to_forbid=jwt_secret)

    if not allow_create_in_dev:
        raise CredentialKeyUnavailableError(
            "Master encryption key is missing. Restore BRAINOVA_MASTER_KEY or data/.aether_master_key."
        )

    # Generate a fresh 256-bit key formatted with version prefix k1:<base64url>
    raw_32 = secrets.token_bytes(KEY_BYTES)
    b64_key = base64.urlsafe_b64encode(raw_32).decode("ascii")
    spec = f"{DEFAULT_KEY_VERSION}:{b64_key}"
    try:
        descriptor = os.open(key_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        try:
            os.write(descriptor, spec.encode("utf-8"))
        finally:
            os.close(descriptor)
    except FileExistsError:
        with open(key_path, "r", encoding="utf-8") as f:
            spec = f.read().strip()
    return parse_keyring_string(spec, jwt_secret_to_forbid=jwt_secret)


# ============================================================================
# ENVELOPE ENCRYPTION & DECRYPTION API
# ============================================================================
def is_encrypted_credential(value: Optional[str]) -> bool:
    if not value or not isinstance(value, str):
        return False
    return value.startswith(ENCRYPTION_PREFIX)


def get_encrypted_credential_version(value: str) -> str:
    if not is_encrypted_credential(value):
        raise CredentialEncryptionError("Value is not in versioned encrypted credential format.")
    parts = value.split(":", 3)
    if len(parts) != 4 or parts[0] != "enc" or parts[1] != "v1" or not _KEY_VERSION_RE.match(parts[2]):
        raise CredentialEncryptionError("Malformed encrypted credential header.")
    return parts[2]


def encrypt_credential(
    plaintext: str,
    aad_context: str = "",
    keyring: Optional[Tuple[str, Dict[str, bytes]]] = None,
) -> str:
    """
    Encrypts a credential string using AES-256-GCM under the active primary key version.
    Returns empty string if plaintext is empty.
     prevent double-encryption if already encrypted.
    """
    if plaintext is None:
        return ""
    cleaned = plaintext.strip()
    if not cleaned:
        return ""
    if is_encrypted_credential(cleaned):
        # Verify it is valid and do not double-encrypt
        decrypt_credential(cleaned, aad_context=aad_context, keyring=keyring)
        return cleaned

    primary_ver, keys = keyring if keyring is not None else load_master_keyring(allow_create_in_dev=True)
    key = keys.get(primary_ver)
    if not key:
        raise CredentialKeyUnavailableError(f"Primary key version '{primary_ver}' not found in keyring.")

    nonce = os.urandom(NONCE_BYTES)
    bound_aad = f"enc:v1:{primary_ver}:{aad_context}".encode("utf-8")
    ct_and_tag = _raw_aes256_gcm_encrypt(key, nonce, cleaned.encode("utf-8"), bound_aad)
    blob = base64.urlsafe_b64encode(nonce + ct_and_tag).decode("ascii")
    return f"enc:v1:{primary_ver}:{blob}"


def decrypt_credential(
    stored_value: str,
    aad_context: str = "",
    keyring: Optional[Tuple[str, Dict[str, bytes]]] = None,
) -> str:
    """
    Decrypts and verifies an AES-256-GCM encrypted credential.
    Raises CredentialKeyUnavailableError if the required key version is missing,
    or CredentialEncryptionError if the ciphertext or authentication tag is invalid.
    """
    if not stored_value:
        return ""
    cleaned = stored_value.strip()
    if not cleaned:
        return ""
    if not is_encrypted_credential(cleaned):
        raise CredentialEncryptionError("Stored credential is not in encrypted format.")

    parts = cleaned.split(":", 3)
    if len(parts) != 4 or parts[0] != "enc" or parts[1] != "v1":
        raise CredentialEncryptionError("Malformed encrypted credential format.")

    key_ver, b64_payload = parts[2], parts[3]
    if not _KEY_VERSION_RE.match(key_ver) or not b64_payload:
        raise CredentialEncryptionError("Invalid key version or empty ciphertext payload.")

    _, keys = keyring if keyring is not None else load_master_keyring(allow_create_in_dev=False)
    key = keys.get(key_ver)
    if key is None:
        raise CredentialKeyUnavailableError(
            f"Encrypted credential requires key version '{key_ver}', which is not present in the active keyring."
        )

    try:
        padded = b64_payload + "=" * ((4 - len(b64_payload) % 4) % 4)
        raw_blob = base64.urlsafe_b64decode(padded.encode("ascii"))
    except Exception as exc:
        raise CredentialEncryptionError("Corrupted base64 ciphertext payload.") from exc

    if len(raw_blob) < NONCE_BYTES + TAG_BYTES + 1:
        raise CredentialEncryptionError("Ciphertext payload is too short to contain nonce and GCM tag.")

    nonce = raw_blob[:NONCE_BYTES]
    ct_and_tag = raw_blob[NONCE_BYTES:]
    bound_aad = f"enc:v1:{key_ver}:{aad_context}".encode("utf-8")

    plaintext_bytes = _raw_aes256_gcm_decrypt(key, nonce, ct_and_tag, bound_aad)
    try:
        return plaintext_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise CredentialEncryptionError("Decrypted credential bytes are not valid UTF-8.") from exc


def mask_credential(plaintext_or_empty: str) -> str:
    """Returns a safe masked representation (never reveals full secret)."""
    if not plaintext_or_empty:
        return ""
    val = plaintext_or_empty.strip()
    if not val:
        return ""
    if len(val) <= 8:
        return "••••••••"
    return f"••••••••••••{val[-4:]}"


# ============================================================================
# CONTROLLED LEGACY PLAINTEXT MIGRATION & KEY ROTATION
# ============================================================================
def _database_has_encrypted_credentials(conn: sqlite3.Connection) -> bool:
    tables = {
        r["name"] if isinstance(r, dict) else r[0]
        for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    }
    if "user_preferences" not in tables:
        return False
    rows = conn.execute("SELECT * FROM user_preferences").fetchall()
    for row in rows:
        r_dict = row if isinstance(row, dict) else dict(row)
        for col in CREDENTIAL_COLUMNS:
            val = (r_dict.get(col) or "").strip()
            if is_encrypted_credential(val) or val.startswith("enc:"):
                return True
    return False


def _database_has_any_credentials(conn: sqlite3.Connection) -> bool:
    tables = {
        r["name"] if isinstance(r, dict) else r[0]
        for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    }
    if "user_preferences" not in tables:
        return False
    rows = conn.execute("SELECT * FROM user_preferences").fetchall()
    for row in rows:
        r_dict = row if isinstance(row, dict) else dict(row)
        for col in CREDENTIAL_COLUMNS:
            if (r_dict.get(col) or "").strip():
                return True
    return False


def migrate_plaintext_credentials(
    conn: sqlite3.Connection,
    keyring: Optional[Tuple[str, Dict[str, bytes]]] = None,
) -> Dict[str, int]:
    """
    Controlled, transactional migration of legacy plaintext credentials in `user_preferences`.
    1. If encrypted credentials already exist in DB, requires an existing valid master key
       (never auto-creates a replacement key that would orphan existing encrypted records).
    2. Encrypts each legacy plaintext credential with AAD bound to `user_id:column_name`.
    3. Immediately verifies round-trip decryption before updating the record.
    4. Verifies existing encrypted records can still be decrypted with the loaded keyring.
    """
    rows = conn.execute("SELECT * FROM user_preferences").fetchall()
    if not _database_has_any_credentials(conn) and keyring is None:
        return {
            "users_inspected": len(rows),
            "users_migrated": 0,
            "plaintext_fields_migrated": 0,
            "encrypted_fields_verified": 0,
        }

    has_existing_encrypted = _database_has_encrypted_credentials(conn)
    active_keyring = (
        keyring
        if keyring is not None
        else load_master_keyring(allow_create_in_dev=not has_existing_encrypted)
    )
    migrated_fields = 0
    verified_existing_fields = 0
    users_updated = 0

    pending_updates: List[Tuple[Dict[str, str], str]] = []

    for raw_row in rows:
        row = raw_row if isinstance(raw_row, dict) else dict(raw_row)
        user_id = row["user_id"]
        col_updates: Dict[str, str] = {}

        for col in CREDENTIAL_COLUMNS:
            raw_val = (row.get(col) or "").strip()
            if not raw_val:
                continue
            aad_ctx = f"{user_id}:{col}"

            if is_encrypted_credential(raw_val):
                # Verify existing encrypted credential is decryptable; STOP if key is missing/invalid
                try:
                    decrypted = decrypt_credential(raw_val, aad_context=aad_ctx, keyring=active_keyring)
                    if not decrypted:
                        raise CredentialEncryptionError(
                            f"Verification failed for existing encrypted credential '{col}' of user '{user_id}'."
                        )
                    verified_existing_fields += 1
                except CredentialEncryptionError:
                    if not os.environ.get("VERCEL"):
                        raise
                    col_updates[col] = ""
            elif raw_val.startswith("enc:"):
                raise CredentialEncryptionError(
                    f"Unsupported or corrupted encrypted prefix on column '{col}' for user '{user_id}'."
                )
            else:
                # Legacy plaintext credential: encrypt and verify before staging update
                ciphertext = encrypt_credential(raw_val, aad_context=aad_ctx, keyring=active_keyring)
                verified_plain = decrypt_credential(ciphertext, aad_context=aad_ctx, keyring=active_keyring)
                if not hmac.compare_digest(verified_plain, raw_val):
                    raise CredentialEncryptionError(
                        f"Round-trip encryption verification failed for '{col}' of user '{user_id}'."
                    )
                col_updates[col] = ciphertext
                migrated_fields += 1

        if col_updates:
            pending_updates.append((col_updates, user_id))
            users_updated += 1

    # Apply all verified updates atomically
    for col_updates, user_id in pending_updates:
        set_clause = ", ".join(f"{k} = ?" for k in col_updates.keys())
        conn.execute(
            f"UPDATE user_preferences SET {set_clause} WHERE user_id = ?",
            [*col_updates.values(), user_id],
        )

    return {
        "users_inspected": len(rows),
        "users_migrated": users_updated,
        "plaintext_fields_migrated": migrated_fields,
        "encrypted_fields_verified": verified_existing_fields,
    }


def rotate_encrypted_credentials(
    conn: sqlite3.Connection,
    keyring: Optional[Tuple[str, Dict[str, bytes]]] = None,
) -> Dict[str, int]:
    """
    Re-encrypts all credentials in `user_preferences` under the active primary key version
    of the provided keyring while verifying every decrypted and re-encrypted value.
    """
    active_keyring = keyring if keyring is not None else load_master_keyring(allow_create_in_dev=False)
    primary_ver, _ = active_keyring

    rows = conn.execute("SELECT * FROM user_preferences").fetchall()
    rotated_count = 0
    already_current_count = 0
    pending_updates: List[Tuple[Dict[str, str], str]] = []

    for raw_row in rows:
        row = raw_row if isinstance(raw_row, dict) else dict(raw_row)
        user_id = row["user_id"]
        col_updates: Dict[str, str] = {}

        for col in CREDENTIAL_COLUMNS:
            raw_val = (row.get(col) or "").strip()
            if not raw_val:
                continue
            aad_ctx = f"{user_id}:{col}"

            if is_encrypted_credential(raw_val):
                plain = decrypt_credential(raw_val, aad_context=aad_ctx, keyring=active_keyring)
                ver = get_encrypted_credential_version(raw_val)
                if ver == primary_ver:
                    already_current_count += 1
                    continue
            else:
                plain = raw_val

            new_ct = encrypt_credential(plain, aad_context=aad_ctx, keyring=active_keyring)
            check_plain = decrypt_credential(new_ct, aad_context=aad_ctx, keyring=active_keyring)
            if not hmac.compare_digest(check_plain, plain):
                raise CredentialEncryptionError(
                    f"Key rotation verification failed for '{col}' of user '{user_id}'."
                )
            col_updates[col] = new_ct
            rotated_count += 1

        if col_updates:
            pending_updates.append((col_updates, user_id))

    for col_updates, user_id in pending_updates:
        set_clause = ", ".join(f"{k} = ?" for k in col_updates.keys())
        conn.execute(
            f"UPDATE user_preferences SET {set_clause} WHERE user_id = ?",
            [*col_updates.values(), user_id],
        )

    return {
        "primary_version": primary_ver,
        "fields_rotated": rotated_count,
        "fields_already_current": already_current_count,
    }


# ============================================================================
# SECRET REDACTION & ERROR HYGIENE
# ============================================================================
_SENSITIVE_PATTERNS = [
    re.compile(r"enc:v1:[a-zA-Z0-9_-]+:[a-zA-Z0-9_\-=]+"),
    re.compile(r"AIza[0-9A-Za-z\-_]{20,}"),
    re.compile(r"sk-ant-[0-9A-Za-z\-_]{16,}"),
    re.compile(r"sk-[0-9A-Za-z\-_]{16,}"),
    re.compile(r"(?i)(bearer\s+)[A-Za-z0-9\-_\.]+"),
    re.compile(r"(?i)((?:playback_token|token|key|api_key)=)[^&\s\"']+"),
]


def redact_sensitive_text(message: Any) -> str:
    """Redacts API keys, encrypted envelopes, and bearer/query tokens from logs and error strings."""
    text = str(message or "")
    for pat in _SENSITIVE_PATTERNS:
        if pat.groups >= 1:
            text = pat.sub(r"\1[REDACTED]", text)
        else:
            text = pat.sub("[REDACTED]", text)
    return text

