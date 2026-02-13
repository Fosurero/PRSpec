"""
Specification Fetcher for PRSpec
Author: Safi El-Hassanine

Fetches Ethereum specifications from official sources.
Supports multiple EIPs with dynamic routing and execution spec resolution.
"""

import requests
from typing import Dict, Optional, List
from pathlib import Path
import os


class SpecFetcher:
    """Fetches Ethereum specifications from GitHub and other sources"""
    
    # Registry of supported EIPs with metadata and execution spec paths.
    # Each entry contains:
    #   - title: human-readable title
    #   - fork: the Ethereum fork that introduced this EIP
    #   - execution_spec_paths: ordered list of paths to try in execution-specs repo
    #   - consensus_spec_paths: (optional) paths in consensus-specs repo
    EIP_REGISTRY = {
        1559: {
            "title": "EIP-1559: Fee market change for ETH 1.0 chain",
            "fork": "london",
            "execution_spec_paths": [
                "src/ethereum/london/fork.py",
                "src/ethereum/paris/fork.py",
            ],
        },
        4844: {
            "title": "EIP-4844: Shard Blob Transactions",
            "fork": "cancun",
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
            "execution_spec_paths": [
                "src/ethereum/cancun/fork.py",
            ],
        },
        7002: {
            "title": "EIP-7002: Execution layer triggerable withdrawals",
            "fork": "prague",
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
            "execution_spec_paths": [
                "src/ethereum/berlin/fork.py",
            ],
        },
    }
    
    # Legacy SOURCES dict kept for backward compatibility
    SOURCES = {
        f"eip{num}": {
            "eip_url": f"https://raw.githubusercontent.com/ethereum/EIPs/master/EIPS/eip-{num}.md",
            "title": info["title"],
        }
        for num, info in EIP_REGISTRY.items()
    }
    
    def __init__(self, github_token: Optional[str] = None, cache_dir: Optional[str] = None):
        """
        Initialize the spec fetcher.
        
        Args:
            github_token: Optional GitHub token for higher rate limits
            cache_dir: Directory to cache fetched specs
        """
        self.github_token = github_token
        self.cache_dir = Path(cache_dir) if cache_dir else Path.cwd() / ".spec_cache"
        self.session = requests.Session()
        
        if github_token:
            self.session.headers["Authorization"] = f"token {github_token}"
        
        # Create cache directory
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    # ------------------------------------------------------------------
    # Supported EIP helpers
    # ------------------------------------------------------------------
    
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
    
    # ------------------------------------------------------------------
    # Core fetchers
    # ------------------------------------------------------------------
    
    def fetch_eip(self, eip_number: int, use_cache: bool = True) -> str:
        """
        Fetch an EIP specification document.
        
        Works for *any* EIP number — registered or not — since the URL
        pattern is predictable.
        
        Args:
            eip_number: The EIP number (e.g., 1559, 4844)
            use_cache: Whether to use cached version if available
            
        Returns:
            The EIP specification text
        """
        cache_file = self.cache_dir / f"eip-{eip_number}.md"
        
        # Check cache
        if use_cache and cache_file.exists():
            return cache_file.read_text()
        
        # Fetch from GitHub
        url = f"https://raw.githubusercontent.com/ethereum/EIPs/master/EIPS/eip-{eip_number}.md"
        response = self.session.get(url)
        response.raise_for_status()
        
        content = response.text
        
        # Cache the result
        cache_file.write_text(content)
        
        return content
    
    def fetch_execution_spec(self, file_path: str, branch: str = "master", 
                             use_cache: bool = True) -> str:
        """
        Fetch Python execution specification from ethereum/execution-specs.
        
        Args:
            file_path: Path to file within the execution-specs repo
            branch: Git branch to fetch from
            use_cache: Whether to use cached version
            
        Returns:
            The specification source code
        """
        cache_file = self.cache_dir / f"exec_spec_{file_path.replace('/', '_')}"
        
        if use_cache and cache_file.exists():
            return cache_file.read_text()
        
        url = f"https://raw.githubusercontent.com/ethereum/execution-specs/{branch}/{file_path}"
        response = self.session.get(url)
        response.raise_for_status()
        
        content = response.text
        cache_file.write_text(content)
        
        return content
    
    def fetch_consensus_spec(self, file_path: str, branch: str = "dev",
                             use_cache: bool = True) -> str:
        """
        Fetch a file from ethereum/consensus-specs.
        
        Args:
            file_path: Path to file within the consensus-specs repo
            branch: Git branch to fetch from
            use_cache: Whether to use cached version
            
        Returns:
            The specification text
        """
        cache_file = self.cache_dir / f"consensus_spec_{file_path.replace('/', '_')}"
        
        if use_cache and cache_file.exists():
            return cache_file.read_text()
        
        url = f"https://raw.githubusercontent.com/ethereum/consensus-specs/{branch}/{file_path}"
        response = self.session.get(url)
        response.raise_for_status()
        
        content = response.text
        cache_file.write_text(content)
        
        return content
    
    # ------------------------------------------------------------------
    # Generic EIP spec fetcher (replaces per-EIP methods)
    # ------------------------------------------------------------------
    
    def fetch_eip_spec(self, eip_number: int) -> Dict[str, str]:
        """
        Fetch complete specification materials for any supported EIP.
        
        For registered EIPs this includes the EIP markdown *and* any
        execution / consensus spec files listed in EIP_REGISTRY.
        For unregistered EIPs it falls back to the EIP markdown only.
        
        Args:
            eip_number: The EIP number
            
        Returns:
            Dictionary with keys:
                - eip_markdown: the raw EIP text
                - execution_spec: combined execution spec code (or None)
                - consensus_spec: combined consensus spec text (or None)
                - title: human-readable title
        """
        info = self.EIP_REGISTRY.get(eip_number, {})
        title = info.get("title", f"EIP-{eip_number}")
        
        result: Dict[str, Optional[str]] = {
            "eip_markdown": self.fetch_eip(eip_number),
            "execution_spec": None,
            "consensus_spec": None,
            "title": title,
        }
        
        # Try execution spec paths in order; first success wins
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
    
    # ------------------------------------------------------------------
    # Legacy per-EIP convenience methods (delegate to generic fetcher)
    # ------------------------------------------------------------------
    
    def fetch_eip1559_spec(self) -> Dict[str, str]:
        """
        Fetch complete EIP-1559 specification materials.
        
        Returns:
            Dictionary with EIP markdown and execution spec code
        """
        return self.fetch_eip_spec(1559)
    
    def fetch_eip4844_spec(self) -> Dict[str, str]:
        """
        Fetch complete EIP-4844 (Shard Blob Transactions) specification materials.
        
        Returns:
            Dictionary with EIP markdown, execution spec, and consensus spec
        """
        return self.fetch_eip_spec(4844)
    
    # ------------------------------------------------------------------
    # Section extraction helpers
    # ------------------------------------------------------------------
    
    def extract_eip_sections(self, eip_content: str) -> Dict[str, str]:
        """
        Extract sections from an EIP markdown document.
        
        Args:
            eip_content: Raw EIP markdown content
            
        Returns:
            Dictionary mapping section names to content
        """
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
        """
        Extract the 'Specification' section from any EIP.
        
        Falls back to the first 10 000 characters of the full EIP text
        if no explicit specification section is found.
        
        Args:
            eip_number: The EIP number
            
        Returns:
            The specification text
        """
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
    
    # ------------------------------------------------------------------
    # Cache management
    # ------------------------------------------------------------------
    
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
