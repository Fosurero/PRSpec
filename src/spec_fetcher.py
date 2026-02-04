"""
Specification Fetcher for PRSpec
Author: Safi El-Hassanine

Fetches Ethereum specifications from official sources.
"""

import requests
from typing import Dict, Optional, List
from pathlib import Path
import os


class SpecFetcher:
    """Fetches Ethereum specifications from GitHub and other sources"""
    
    # EIP specification sources
    SOURCES = {
        "eip1559": {
            "eip_url": "https://raw.githubusercontent.com/ethereum/EIPs/master/EIPS/eip-1559.md",
            "execution_spec_url": "https://raw.githubusercontent.com/ethereum/execution-specs/master/src/ethereum/london/fork.py",
            "title": "EIP-1559: Fee market change for ETH 1.0 chain"
        },
        "eip4844": {
            "eip_url": "https://raw.githubusercontent.com/ethereum/EIPs/master/EIPS/eip-4844.md",
            "title": "EIP-4844: Shard Blob Transactions"
        },
        "eip2930": {
            "eip_url": "https://raw.githubusercontent.com/ethereum/EIPs/master/EIPS/eip-2930.md",
            "title": "EIP-2930: Optional access lists"
        }
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
    
    def fetch_eip(self, eip_number: int, use_cache: bool = True) -> str:
        """
        Fetch an EIP specification document.
        
        Args:
            eip_number: The EIP number (e.g., 1559)
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
    
    def fetch_eip1559_spec(self) -> Dict[str, str]:
        """
        Fetch complete EIP-1559 specification materials.
        
        Returns:
            Dictionary with EIP markdown and execution spec code
        """
        result = {
            "eip_markdown": self.fetch_eip(1559),
            "execution_spec": None,
            "title": "EIP-1559: Fee market change for ETH 1.0 chain"
        }
        
        # Try to fetch execution spec
        try:
            # Try London fork first (where EIP-1559 was introduced)
            result["execution_spec"] = self.fetch_execution_spec(
                "src/ethereum/london/fork.py"
            )
        except requests.HTTPError:
            # Try Paris fork
            try:
                result["execution_spec"] = self.fetch_execution_spec(
                    "src/ethereum/paris/fork.py"
                )
            except requests.HTTPError:
                pass
        
        return result
    
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
        current_content = []
        
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
        base_fee_spec = []
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
