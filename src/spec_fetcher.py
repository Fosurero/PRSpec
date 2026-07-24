"""Fetches Ethereum EIP specs, execution specs, and consensus specs from GitHub."""

import difflib
from typing import Dict, List, Optional

import requests

from .github_fetcher import CachedGitHubFetcher


class SpecFetcher(CachedGitHubFetcher):
    """Fetches Ethereum specifications from GitHub and other sources"""

    DEFAULT_CACHE_DIRNAME = ".spec_cache"

    # Supported EIPs: title, fork, and where to find their specs.
    EIP_REGISTRY = {
        1559: {
            "title": "EIP-1559: Fee market change for ETH 1.0 chain",
            "fork": "london",
            "predecessor_fork": "berlin",
            "execution_spec_paths": [
                "src/ethereum/forks/london/fork.py",
                "src/ethereum/forks/paris/fork.py",
            ],
        },
        4844: {
            "title": "EIP-4844: Shard Blob Transactions",
            "fork": "cancun",
            "predecessor_fork": "shanghai",
            "execution_spec_paths": [
                "src/ethereum/forks/cancun/fork.py",
                "src/ethereum/forks/cancun/blocks.py",
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
                "src/ethereum/forks/cancun/fork.py",
            ],
        },
        7002: {
            "title": "EIP-7002: Execution layer triggerable withdrawals",
            "fork": "prague",
            "predecessor_fork": "cancun",
            "execution_spec_paths": [
                "src/ethereum/forks/prague/fork.py",
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
                "src/ethereum/forks/berlin/fork.py",
            ],
        },
        # Pectra / Prague EIPs — actively being implemented across all clients now.
        7702: {
            "title": "EIP-7702: Set EOA Account Code",
            "fork": "prague",
            "predecessor_fork": "cancun",
            "execution_spec_paths": [
                "src/ethereum/forks/prague/fork.py",
                "src/ethereum/forks/prague/transactions.py",
            ],
        },
        2935: {
            "title": "EIP-2935: Serve Historical Block Hashes from State",
            "fork": "prague",
            "predecessor_fork": "cancun",
            "execution_spec_paths": [
                "src/ethereum/forks/prague/fork.py",
            ],
        },
        2537: {
            "title": "EIP-2537: Precompile for BLS12-381 Curve Operations",
            "fork": "prague",
            "predecessor_fork": "cancun",
            "execution_spec_paths": [
                "src/ethereum/forks/prague/vm/precompiled_contracts/bls12_381/__init__.py",
            ],
        },
        6110: {
            "title": "EIP-6110: Supply Validator Deposits on Chain",
            "fork": "prague",
            "predecessor_fork": "cancun",
            "execution_spec_paths": [
                "src/ethereum/forks/prague/fork.py",
            ],
        },
    }

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
        return self.fetch_raw_file(
            "ethereum", "EIPs", f"EIPS/eip-{eip_number}.md", "master",
            cache_key=f"eip-{eip_number}.md", use_cache=use_cache,
        )

    def fetch_execution_spec(self, file_path: str, branch: str = "master",
                             use_cache: bool = True) -> str:
        """Fetch a Python file from ethereum/execution-specs."""
        return self.fetch_raw_file(
            "ethereum", "execution-specs", file_path, branch,
            cache_key=f"exec_spec_{file_path.replace('/', '_')}",
            use_cache=use_cache,
        )

    def fetch_consensus_spec(self, file_path: str, branch: str = "dev",
                             use_cache: bool = True) -> str:
        """Fetch a file from ethereum/consensus-specs."""
        return self.fetch_raw_file(
            "ethereum", "consensus-specs", file_path, branch,
            cache_key=f"consensus_spec_{file_path.replace('/', '_')}",
            use_cache=use_cache,
        )

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
        new_path = f"src/ethereum/forks/{fork}/{spec_file}"
        old_path = f"src/ethereum/forks/{predecessor}/{spec_file}"

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

    def list_cached_specs(self) -> List[str]:
        """List all cached specification files"""
        return self.list_cached_files()
