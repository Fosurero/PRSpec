"""Fetches Ethereum EIP specs, execution specs, and consensus specs from GitHub."""

import difflib
from pathlib import Path
from typing import Dict, List, Optional

import requests


class SpecFetcher:
    """Fetches Ethereum specifications from GitHub and other sources"""

    # Supported EIPs: title, fork, and where to find their specs.
    EIP_REGISTRY = {
        1559: {
            "title": "EIP-1559: Fee market change for ETH 1.0 chain",
            "fork": "london",
            "predecessor_fork": "berlin",
            "execution_spec_paths": [
                "src/ethereum/london/fork.py",
                "src/ethereum/paris/fork.py",
            ],
        },
        4844: {
            "title": "EIP-4844: Shard Blob Transactions",
            "fork": "cancun",
            "predecessor_fork": "shanghai",
            "execution_spec_paths": [
                "src/ethereum/cancun/fork.py",
                "src/ethereum/cancun/blocks.py",
            ],
            "consensus_spec_paths": [
                "specs/deneb/beacon-chain.md",
                "specs/deneb/polynomial-commitments.md",
            ],
        },
        4788: {
            "title": "EIP-4788: Beacon block root in the EVM",
            "fork": "cancun",
            "predecessor_fork": "shanghai",
            "execution_spec_paths": [
                "src/ethereum/cancun/fork.py",
            ],
        },
        7002: {
            "title": "EIP-7002: Execution layer triggerable withdrawals",
            "fork": "prague",
            "predecessor_fork": "cancun",
            "execution_spec_paths": [
                "src/ethereum/prague/fork.py",
            ],
        },
        7251: {
            "title": "EIP-7251: Increase the MAX_EFFECTIVE_BALANCE",
            "fork": "prague",
            "execution_spec_paths": [],
            "consensus_spec_paths": [
                "specs/electra/beacon-chain.md",
            ],
        },
        2930: {
            "title": "EIP-2930: Optional access lists",
            "fork": "berlin",
            "predecessor_fork": "muir_glacier",
            "execution_spec_paths": [
                "src/ethereum/berlin/fork.py",
            ],
        },
        # Pectra / Prague EIPs — actively being implemented across all clients now.
        7702: {
            "title": "EIP-7702: Set EOA Account Code",
            "fork": "prague",
            "predecessor_fork": "cancun",
            "execution_spec_paths": [
                "src/ethereum/prague/fork.py",
                "src/ethereum/prague/transactions.py",
            ],
        },
        2935: {
            "title": "EIP-2935: Serve Historical Block Hashes from State",
            "fork": "prague",
            "predecessor_fork": "cancun",
            "execution_spec_paths": [
                "src/ethereum/prague/fork.py",
            ],
        },
        2537: {
            "title": "EIP-2537: Precompile for BLS12-381 Curve Operations",
            "fork": "prague",
            "predecessor_fork": "cancun",
            "execution_spec_paths": [
                "src/ethereum/prague/vm/precompiled_contracts/bls12_381/__init__.py",
            ],
        },
        6110: {
            "title": "EIP-6110: Supply Validator Deposits on Chain",
            "fork": "prague",
            "predecessor_fork": "cancun",
            "execution_spec_paths": [
                "src/ethereum/prague/fork.py",
            ],
        },
    }

    def __init__(self, github_token: Optional[str] = None, cache_dir: Optional[str] = None):
        """Set up HTTP session and local cache directory."""
        self.github_token = github_token
        self.cache_dir = Path(cache_dir) if cache_dir else Path.cwd() / ".spec_cache"
        self.session = requests.Session()

        if github_token:
            self.session.headers["Authorization"] = f"token {github_token}"

        # Create cache directory
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    # ---- Supported EIP helpers ----

    @classmethod
    def supported_eips(cls) -> List[int]:
        """Return a sorted list of EIP numbers with full support."""
        return sorted(cls.EIP_REGISTRY.keys())

    @classmethod
    def get_eip_title(cls, eip_number: int) -> str:
        """Return the human-readable title for an EIP, or a generic fallback."""
        info = cls.EIP_REGISTRY.get(eip_number)
        if info:
            return info["title"]
        return f"EIP-{eip_number}"

    # ---- Core fetchers ----

    def fetch_eip(self, eip_number: int, use_cache: bool = True) -> str:
        """Fetch the raw EIP markdown. Works for any EIP number."""
        cache_file = self.cache_dir / f"eip-{eip_number}.md"

        # Check cache
        if use_cache and cache_file.exists():
            return cache_file.read_text(encoding="utf-8")

        # Fetch from GitHub
        url = f"https://raw.githubusercontent.com/ethereum/EIPs/master/EIPS/eip-{eip_number}.md"
        response = self.session.get(url)
        response.raise_for_status()

        content = response.text

        # Cache the result
        cache_file.write_text(content, encoding="utf-8")

        return content

    def fetch_execution_spec(self, file_path: str, branch: str = "master",
                             use_cache: bool = True) -> str:
        """Fetch a Python file from ethereum/execution-specs."""
        cache_file = self.cache_dir / f"exec_spec_{file_path.replace('/', '_')}"

        if use_cache and cache_file.exists():
            return cache_file.read_text(encoding="utf-8")

        url = f"https://raw.githubusercontent.com/ethereum/execution-specs/{branch}/{file_path}"
        response = self.session.get(url)
        response.raise_for_status()

        content = response.text
        cache_file.write_text(content, encoding="utf-8")

        return content

    def fetch_consensus_spec(self, file_path: str, branch: str = "dev",
                             use_cache: bool = True) -> str:
        """Fetch a file from ethereum/consensus-specs."""
        cache_file = self.cache_dir / f"consensus_spec_{file_path.replace('/', '_')}"

        if use_cache and cache_file.exists():
            return cache_file.read_text(encoding="utf-8")

        url = f"https://raw.githubusercontent.com/ethereum/consensus-specs/{branch}/{file_path}"
        response = self.session.get(url)
        response.raise_for_status()

        content = response.text
        cache_file.write_text(content, encoding="utf-8")

        return content

    def fetch_execution_spec_diff(self, eip_number: int, branch: str = "master",
                                  use_cache: bool = True) -> Optional[str]:
        """Return the fork-to-fork diff that introduced an EIP.

        execution-specs follows the WET principle: each fork's reference code is
        a near-copy of the previous fork with that fork's EIPs applied.  Diffing
        the implementing fork against its predecessor therefore isolates the
        EIP's actual delta instead of the whole ~thousand-line ``fork.py``.
        This is the fork-to-fork technique the execution-specs maintainers
        recommend for EIP boundary detection.

        Returns the unified diff, or ``None`` when the EIP has no registered
        predecessor or either fork file cannot be fetched (callers fall back to
        the full spec).
        """
        info = self.EIP_REGISTRY.get(eip_number, {})
        fork = info.get("fork")
        predecessor = info.get("predecessor_fork")
        if not fork or not predecessor:
            return None

        spec_file = info.get("spec_file", "fork.py")
        new_path = f"src/ethereum/{fork}/{spec_file}"
        old_path = f"src/ethereum/{predecessor}/{spec_file}"

        try:
            new_src = self.fetch_execution_spec(new_path, branch, use_cache)
            old_src = self.fetch_execution_spec(old_path, branch, use_cache)
        except (requests.HTTPError, requests.ConnectionError):
            return None

        diff = difflib.unified_diff(
            old_src.splitlines(keepends=True),
            new_src.splitlines(keepends=True),
            fromfile=old_path,
            tofile=new_path,
            n=3,
        )
        text = "".join(diff)
        return text or None

    # ---- Generic EIP spec fetcher ----

    def fetch_eip_spec(self, eip_number: int, mode: str = "full") -> Dict[str, str]:
        """Fetch EIP markdown + any execution/consensus specs for this EIP.

        ``mode="diff"`` supplies the fork-to-fork execution-spec delta (see
        :meth:`fetch_execution_spec_diff`) instead of the full fork file, and
        falls back to the full file when no diff is available.  ``mode="full"``
        (default) preserves the original whole-file behaviour.
        """
        info = self.EIP_REGISTRY.get(eip_number, {})
        title = info.get("title", f"EIP-{eip_number}")

        result: Dict[str, Optional[str]] = {
            "eip_markdown": self.fetch_eip(eip_number),
            "execution_spec": None,
            "execution_spec_mode": "full",
            "consensus_spec": None,
            "title": title,
        }

        # Prefer the focused fork diff when asked for it.
        if mode == "diff":
            diff = self.fetch_execution_spec_diff(eip_number)
            if diff:
                result["execution_spec"] = diff
                result["execution_spec_mode"] = "diff"

        # Fall back to (or default to) the first whole spec file that fetches.
        if result["execution_spec"] is None:
            for path in info.get("execution_spec_paths", []):
                try:
                    result["execution_spec"] = self.fetch_execution_spec(path)
                    break
                except (requests.HTTPError, requests.ConnectionError):
                    continue

        # Try consensus spec paths; concatenate all that succeed
        consensus_parts: List[str] = []
        for path in info.get("consensus_spec_paths", []):
            try:
                consensus_parts.append(self.fetch_consensus_spec(path))
            except (requests.HTTPError, requests.ConnectionError):
                continue
        if consensus_parts:
            result["consensus_spec"] = "\n\n---\n\n".join(consensus_parts)

        return result

    # ---- Legacy convenience methods ----

    def fetch_eip1559_spec(self) -> Dict[str, str]:
        """Shortcut for fetch_eip_spec(1559)."""
        return self.fetch_eip_spec(1559)

    def fetch_eip4844_spec(self) -> Dict[str, str]:
        """Shortcut for fetch_eip_spec(4844)."""
        return self.fetch_eip_spec(4844)

    # ---- Section extraction ----

    def extract_eip_sections(self, eip_content: str) -> Dict[str, str]:
        """Split an EIP markdown into its ## sections."""
        sections = {}
        current_section = "header"
        current_content: List[str] = []

        for line in eip_content.split('\n'):
            if line.startswith('## '):
                # Save previous section
                if current_content:
                    sections[current_section] = '\n'.join(current_content)

                # Start new section
                current_section = line[3:].strip().lower().replace(' ', '_')
                current_content = []
            else:
                current_content.append(line)

        # Save last section
        if current_content:
            sections[current_section] = '\n'.join(current_content)

        return sections

    def get_eip_specification_section(self, eip_number: int) -> str:
        """Return just the Specification section, or the first 10k chars as fallback."""
        eip_content = self.fetch_eip(eip_number)
        sections = self.extract_eip_sections(eip_content)
        return sections.get("specification", eip_content[:10000])

    def get_eip1559_base_fee_spec(self) -> str:
        """
        Extract the base fee calculation specification from EIP-1559.

        Returns:
            Text describing the base fee calculation algorithm
        """
        eip_content = self.fetch_eip(1559)
        sections = self.extract_eip_sections(eip_content)

        # Look for specification section
        spec_section = sections.get('specification', '')

        # Extract base fee relevant parts
        base_fee_spec: List[str] = []
        in_base_fee = False

        for line in spec_section.split('\n'):
            line_lower = line.lower()
            if 'base fee' in line_lower or 'basefee' in line_lower:
                in_base_fee = True
            if in_base_fee:
                base_fee_spec.append(line)
                if line.strip() == '' and len(base_fee_spec) > 5:
                    break

        return '\n'.join(base_fee_spec) if base_fee_spec else spec_section

    # ---- Cache management ----

    def clear_cache(self):
        """Clear the specification cache"""
        import shutil
        if self.cache_dir.exists():
            shutil.rmtree(self.cache_dir)
            self.cache_dir.mkdir(parents=True, exist_ok=True)

    def list_cached_specs(self) -> List[str]:
        """List all cached specification files"""
        if not self.cache_dir.exists():
            return []
        return [f.name for f in self.cache_dir.iterdir() if f.is_file()]
