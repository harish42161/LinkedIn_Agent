"""Secure LinkedIn Authentication and Session Management.

Manages encrypted session tokens, validates live sessions against LinkedIn,
and provides interactive/manual authentication flows without storing plaintext passwords.
"""

import os
import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
import requests
from cryptography.fernet import Fernet
from linkedin_job_agent.config import config

logger = logging.getLogger("linkedin_agent.auth")


class LinkedInAuthManager:
    """Handles secure LinkedIn authentication, token encryption, and session verification."""

    def __init__(self):
        self.session_file = config.session_storage_path
        self._key = self._get_or_create_key()
        self.cipher = Fernet(self._key)

    def _get_or_create_key(self) -> bytes:
        """Loads or generates AES encryption key for local session persistence."""
        key_env = os.getenv("LINKEDIN_ENCRYPTION_KEY")
        if key_env:
            try:
                return key_env.encode("utf-8")
            except Exception:
                pass

        key_file = self.session_file.parent / ".secret_key"
        if key_file.exists():
            return key_file.read_bytes()
        else:
            new_key = Fernet.generate_key()
            key_file.parent.mkdir(parents=True, exist_ok=True)
            key_file.write_bytes(new_key)
            return new_key

    @staticmethod
    def mask_token(token: str) -> str:
        """Masks sensitive token for display in logs or UI."""
        if not token:
            return "None"
        if len(token) <= 8:
            return "***"
        return f"{token[:4]}...{token[-4:]}"

    def save_session(self, li_at: str, jsessionid: Optional[str] = None):
        """Encrypts and persists LinkedIn session cookies."""
        payload = {
            "li_at": li_at.strip(),
            "jsessionid": jsessionid.strip() if jsessionid else ""
        }
        encrypted = self.cipher.encrypt(json.dumps(payload).encode("utf-8"))
        self.session_file.parent.mkdir(parents=True, exist_ok=True)
        self.session_file.write_bytes(encrypted)
        logger.info(f"LinkedIn session saved securely (li_at: {self.mask_token(li_at)})")

    def load_session(self) -> Optional[Dict[str, str]]:
        """Decrypts and loads session cookies from storage or environment."""
        # 1. Check environment variables first
        if config.li_at:
            return {
                "li_at": config.li_at,
                "jsessionid": config.jsessionid
            }

        # 2. Check encrypted file
        if self.session_file.exists():
            try:
                data = self.cipher.decrypt(self.session_file.read_bytes())
                return json.loads(data.decode("utf-8"))
            except Exception as e:
                logger.error(f"Failed to decrypt session storage: {e}")
                return None
        return None

    def get_session_cookies(self) -> Dict[str, str]:
        """Returns cookies dictionary ready for requests or browser automation."""
        session = self.load_session()
        if not session or not session.get("li_at"):
            return {}
        cookies = {"li_at": session["li_at"]}
        if session.get("jsessionid"):
            cookies["JSESSIONID"] = session["jsessionid"]
        return cookies

    def verify_session(self) -> Tuple[bool, str]:
        """Checks if the saved session is valid and not expired or challenged."""
        cookies = self.get_session_cookies()
        if not cookies or "li_at" not in cookies:
            return False, "No LinkedIn session configured. Set LINKEDIN_LI_AT in .env or run authentication."

        url = "https://www.linkedin.com/feed/"
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }

        try:
            resp = requests.get(url, cookies=cookies, headers=headers, allow_redirects=False, timeout=10)
            
            # If redirected to login page or challenge
            if resp.status_code in (301, 302, 303, 307):
                loc = resp.headers.get("Location", "")
                if "login" in loc or "checkpoint" in loc:
                    return False, f"Session expired or checkpoint requested: redirected to '{loc.split('?')[0]}'"
            
            if resp.status_code == 200:
                if "checkpoint/challenge" in resp.text.lower():
                    return False, "Security verification or CAPTCHA challenge detected. Manual resolution required."
                return True, "Active and authenticated LinkedIn session verified."

            return False, f"Unexpected response status code: {resp.status_code}"
        except Exception as e:
            return False, f"Connection error during session verification: {str(e)}"

    def prompt_interactive_login_instructions(self) -> str:
        """Returns helpful guidance for official authentication without password risks."""
        return (
            "====================================================================\n"
            "               LINKEDIN AUTHENTICATION INSTRUCTIONS                \n"
            "====================================================================\n"
            "To safeguard your account and respect LinkedIn terms:\n"
            "1. Open your browser and log into https://www.linkedin.com normally.\n"
            "2. Complete any MFA or SMS 2-factor authentication prompts.\n"
            "3. Open Developer Tools (F12 or Cmd+Opt+I) -> Application / Storage -> Cookies.\n"
            "4. Copy the value of cookie 'li_at' (and optionally 'JSESSIONID').\n"
            "5. Save it in your .env file or run:\n"
            "   python linkedin_job_agent/main.py auth --cookie <your_li_at_value>\n"
            "====================================================================\n"
        )


auth_manager = LinkedInAuthManager()
