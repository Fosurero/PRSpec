"""
Code Fetcher for PRSpec
Author: Safi El-Hassanine

Fetches implementation code from Ethereum client repositories.
"""

import requests
from typing import Dict, Optional, List, Any
from pathlib import Path
import tempfile
import os

try:
    from git import Repo
    GIT_AVAILABLE = True
except ImportError:
    GIT_AVAILABLE = False


class CodeFetcher:
    """Fetches code from Ethereum client implementations"""
    
    # Known Ethereum client repositories
    CLIENTS = {
        "go-ethereum": {
            "url": "https://github.com/ethereum/go-ethereum",
            "language": "go",
            "eip1559_files": [
                "consensus/misc/eip1559.go",
                "core/types/transaction.go",
                "core/types/tx_dynamic_fee.go",
            ]
        },
        "prysm": {
            "url": "https://github.com/prysmaticlabs/prysm",
            "language": "go",
        },
        "lighthouse": {
            "url": "https://github.com/sigp/lighthouse",
            "language": "rust",
        },
        "nethermind": {
            "url": "https://github.com/NethermindEth/nethermind",
            "language": "csharp",
        },
        "besu": {
            "url": "https://github.com/hyperledger/besu",
            "language": "java",
        }
    }
    
    def __init__(self, github_token: Optional[str] = None, cache_dir: Optional[str] = None):
        """
        Initialize the code fetcher.
        
        Args:
            github_token: Optional GitHub token for API access
            cache_dir: Directory to cache fetched code
        """
        self.github_token = github_token
        self.cache_dir = Path(cache_dir) if cache_dir else Path.cwd() / ".code_cache"
        self.session = requests.Session()
        
        if github_token:
            self.session.headers["Authorization"] = f"token {github_token}"
        self.session.headers["Accept"] = "application/vnd.github.v3+json"
        
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def fetch_file(self, owner: str, repo: str, path: str, 
                   branch: str = "master", use_cache: bool = True) -> str:
        """
        Fetch a single file from a GitHub repository.
        
        Args:
            owner: Repository owner
            repo: Repository name
            path: File path within the repository
            branch: Branch to fetch from
            use_cache: Whether to use cached version
            
        Returns:
            File contents as string
        """
        cache_key = f"{owner}_{repo}_{path.replace('/', '_')}_{branch}"
        cache_file = self.cache_dir / cache_key
        
        if use_cache and cache_file.exists():
            return cache_file.read_text()
        
        # Use raw GitHub URL
        url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path}"
        response = self.session.get(url)
        response.raise_for_status()
        
        content = response.text
        cache_file.write_text(content)
        
        return content
    
    def fetch_geth_file(self, path: str, branch: str = "master", 
                        use_cache: bool = True) -> str:
        """
        Fetch a file from go-ethereum repository.
        
        Args:
            path: File path within the go-ethereum repo
            branch: Branch to fetch from
            use_cache: Whether to use cached version
            
        Returns:
            File contents
        """
        return self.fetch_file("ethereum", "go-ethereum", path, branch, use_cache)
    
    def fetch_eip1559_implementation(self, client: str = "go-ethereum") -> Dict[str, str]:
        """
        Fetch EIP-1559 implementation files from a client.
        
        Args:
            client: Client name (e.g., "go-ethereum")
            
        Returns:
            Dictionary mapping file paths to their contents
        """
        if client not in self.CLIENTS:
            raise ValueError(f"Unknown client: {client}")
        
        client_info = self.CLIENTS[client]
        files = {}
        
        # Parse owner/repo from URL
        url_parts = client_info["url"].rstrip('/').split('/')
        owner, repo = url_parts[-2], url_parts[-1]
        
        eip1559_files = client_info.get("eip1559_files", [])
        
        for file_path in eip1559_files:
            try:
                content = self.fetch_file(owner, repo, file_path)
                files[file_path] = content
            except requests.HTTPError as e:
                files[file_path] = f"# Error fetching file: {e}"
        
        return files
    
    def fetch_geth_eip1559(self) -> Dict[str, str]:
        """
        Fetch all EIP-1559 related files from go-ethereum.
        
        Returns:
            Dictionary mapping file paths to contents
        """
        files = {}
        
        eip1559_paths = [
            "consensus/misc/eip1559.go",
            "core/types/transaction.go",
            "core/types/tx_dynamic_fee.go",
            "params/protocol_params.go",
        ]
        
        for path in eip1559_paths:
            try:
                files[path] = self.fetch_geth_file(path)
            except requests.HTTPError:
                # Try alternate locations
                pass
        
        return files
    
    def search_repository(self, owner: str, repo: str, query: str, 
                          language: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Search for code within a repository using GitHub API.
        
        Args:
            owner: Repository owner
            repo: Repository name
            query: Search query
            language: Optional language filter
            
        Returns:
            List of search results
        """
        search_query = f"{query} repo:{owner}/{repo}"
        if language:
            search_query += f" language:{language}"
        
        url = "https://api.github.com/search/code"
        params = {"q": search_query, "per_page": 10}
        
        response = self.session.get(url, params=params)
        response.raise_for_status()
        
        return response.json().get("items", [])
    
    def clone_repository(self, url: str, target_dir: Optional[str] = None,
                         branch: str = "master", shallow: bool = True) -> str:
        """
        Clone a repository locally for deeper analysis.
        
        Args:
            url: Repository URL
            target_dir: Target directory (uses temp if not specified)
            branch: Branch to clone
            shallow: Whether to do a shallow clone
            
        Returns:
            Path to cloned repository
        """
        if not GIT_AVAILABLE:
            raise RuntimeError("GitPython not installed. Install with: pip install gitpython")
        
        if target_dir is None:
            target_dir = tempfile.mkdtemp(prefix="prspec_")
        
        clone_args = {"branch": branch}
        if shallow:
            clone_args["depth"] = 1
        
        Repo.clone_from(url, target_dir, **clone_args)
        
        return target_dir
    
    def get_file_functions(self, content: str, language: str = "go") -> List[Dict[str, Any]]:
        """
        Extract function signatures from file content.
        Simple regex-based extraction (parser.py has full implementation).
        
        Args:
            content: File content
            language: Programming language
            
        Returns:
            List of function info dictionaries
        """
        import re
        
        functions = []
        
        if language == "go":
            # Match Go function definitions
            pattern = r'func\s+(?:\([^)]+\)\s+)?(\w+)\s*\([^)]*\)'
            for match in re.finditer(pattern, content):
                functions.append({
                    "name": match.group(1),
                    "start": match.start(),
                    "signature": match.group(0)
                })
        
        elif language == "python":
            # Match Python function definitions
            pattern = r'def\s+(\w+)\s*\([^)]*\)'
            for match in re.finditer(pattern, content):
                functions.append({
                    "name": match.group(1),
                    "start": match.start(),
                    "signature": match.group(0)
                })
        
        return functions
    
    def clear_cache(self):
        """Clear the code cache"""
        import shutil
        if self.cache_dir.exists():
            shutil.rmtree(self.cache_dir)
            self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def list_cached_files(self) -> List[str]:
        """List all cached code files"""
        if not self.cache_dir.exists():
            return []
        return [f.name for f in self.cache_dir.iterdir() if f.is_file()]
