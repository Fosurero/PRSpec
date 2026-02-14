"""Fetches implementation files from Ethereum client repos (geth, prysm, etc.)."""

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
    
    # Client repos and per-EIP file paths.
    CLIENTS: Dict[str, Dict[str, Any]] = {
        "go-ethereum": {
            "url": "https://github.com/ethereum/go-ethereum",
            "language": "go",
            "eip_files": {
                1559: [
                    "consensus/misc/eip1559.go",
                    "core/types/transaction.go",
                    "core/types/tx_dynamic_fee.go",
                    "params/protocol_params.go",
                    "core/state_transition.go",
                ],
                4844: [
                    "consensus/misc/eip4844/eip4844.go",
                    "core/types/tx_blob.go",
                    "crypto/kzg4844/kzg4844.go",
                    "params/protocol_params.go",
                    "core/txpool/legacypool/legacypool.go",
                ],
                4788: [
                    "core/vm/contracts.go",
                ],
                2930: [
                    "core/types/tx_access_list.go",
                    "core/state/access_list.go",
                ],
            },
            # Legacy alias kept for backward compatibility
            "eip1559_files": [
                "consensus/misc/eip1559.go",
                "core/types/transaction.go",
                "core/types/tx_dynamic_fee.go",
            ],
        },
        "prysm": {
            "url": "https://github.com/prysmaticlabs/prysm",
            "language": "go",
            "eip_files": {},
        },
        "lighthouse": {
            "url": "https://github.com/sigp/lighthouse",
            "language": "rust",
            "eip_files": {},
        },
        "nethermind": {
            "url": "https://github.com/NethermindEth/nethermind",
            "language": "csharp",
            "eip_files": {
                1559: [
                    "src/Nethermind/Nethermind.Core/BaseFeeCalculator.cs",
                    "src/Nethermind/Nethermind.Core/Eip1559Constants.cs",
                    "src/Nethermind/Nethermind.Core/Specs/IEip1559Spec.cs",
                    "src/Nethermind/Nethermind.Consensus/Validators/TxValidator.cs",
                    "src/Nethermind/Nethermind.Core/TxType.cs",
                ],
                4844: [
                    "src/Nethermind/Nethermind.Evm/BlobGasCalculator.cs",
                    "src/Nethermind/Nethermind.Core/Eip4844Constants.cs",
                    "src/Nethermind/Nethermind.Crypto/KzgPolynomialCommitments.cs",
                    "src/Nethermind/Nethermind.Consensus/Validators/TxValidator.cs",
                    "src/Nethermind/Nethermind.Consensus/Validators/HeaderValidator.cs",
                ],
            },
        },
        "besu": {
            "url": "https://github.com/hyperledger/besu",
            "language": "java",
            "eip_files": {
                1559: [
                    "ethereum/core/src/main/java/org/hyperledger/besu/ethereum/mainnet/feemarket/LondonFeeMarket.java",
                    "ethereum/core/src/main/java/org/hyperledger/besu/ethereum/mainnet/feemarket/BaseFeeMarket.java",
                    "ethereum/core/src/main/java/org/hyperledger/besu/ethereum/mainnet/feemarket/FeeMarket.java",
                    "ethereum/core/src/main/java/org/hyperledger/besu/ethereum/mainnet/MainnetTransactionValidator.java",
                    "ethereum/core/src/main/java/org/hyperledger/besu/ethereum/core/Transaction.java",
                ],
                4844: [
                    "evm/src/main/java/org/hyperledger/besu/evm/gascalculator/CancunGasCalculator.java",
                    "ethereum/core/src/main/java/org/hyperledger/besu/ethereum/mainnet/feemarket/ExcessBlobGasCalculator.java",
                    "datatypes/src/main/java/org/hyperledger/besu/datatypes/BlobGas.java",
                    "ethereum/core/src/main/java/org/hyperledger/besu/ethereum/mainnet/headervalidationrules/BlobGasValidationRule.java",
                    "evm/src/main/java/org/hyperledger/besu/evm/precompile/KZGPointEvalPrecompiledContract.java",
                ],
            },
        },
    }
    
    def __init__(self, github_token: Optional[str] = None, cache_dir: Optional[str] = None):
        """Set up HTTP session and local cache directory."""
        self.github_token = github_token
        self.cache_dir = Path(cache_dir) if cache_dir else Path.cwd() / ".code_cache"
        self.session = requests.Session()
        
        if github_token:
            self.session.headers["Authorization"] = f"token {github_token}"
        self.session.headers["Accept"] = "application/vnd.github.v3+json"
        
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    # ---- Helpers ----
    
    @classmethod
    def supported_clients(cls) -> List[str]:
        """Return list of known client names."""
        return list(cls.CLIENTS.keys())
    
    @classmethod
    def client_language(cls, client: str) -> str:
        """Return the primary language for a client."""
        info = cls.CLIENTS.get(client)
        if not info:
            raise ValueError(f"Unknown client: {client}")
        return info["language"]
    
    @classmethod
    def supported_eips_for_client(cls, client: str) -> List[int]:
        """Return the list of EIP numbers with file mappings for *client*."""
        info = cls.CLIENTS.get(client)
        if not info:
            raise ValueError(f"Unknown client: {client}")
        return sorted(info.get("eip_files", {}).keys())
    
    # ---- Core fetchers ----
    
    def fetch_file(self, owner: str, repo: str, path: str, 
                   branch: str = "master", use_cache: bool = True) -> str:
        """Fetch a single file from a GitHub repo via raw URL."""
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
        """Shortcut for fetching from go-ethereum."""
        return self.fetch_file("ethereum", "go-ethereum", path, branch, use_cache)
    
    # ---- Generic EIP implementation fetcher ----
    
    def fetch_eip_implementation(self, client: str, eip_number: int) -> Dict[str, str]:
        """Fetch all registered implementation files for an EIP/client pair."""
        if client not in self.CLIENTS:
            raise ValueError(
                f"Unknown client: {client}. "
                f"Supported: {', '.join(self.supported_clients())}"
            )
        
        client_info = self.CLIENTS[client]
        eip_files_map = client_info.get("eip_files", {})
        file_paths = eip_files_map.get(eip_number, [])
        
        if not file_paths:
            raise ValueError(
                f"No file mappings for EIP-{eip_number} in {client}. "
                f"Supported EIPs for {client}: "
                f"{', '.join(str(e) for e in self.supported_eips_for_client(client))}"
            )
        
        # Parse owner/repo from URL
        url_parts = client_info["url"].rstrip('/').split('/')
        owner, repo = url_parts[-2], url_parts[-1]
        
        files: Dict[str, str] = {}
        for file_path in file_paths:
            try:
                content = self.fetch_file(owner, repo, file_path)
                files[file_path] = content
            except requests.HTTPError as e:
                files[file_path] = f"# Error fetching file: {e}"
        
        return files
    
    # ---- Legacy convenience methods ----
    
    def fetch_eip1559_implementation(self, client: str = "go-ethereum") -> Dict[str, str]:
        """Shortcut for fetch_eip_implementation(client, 1559)."""
        return self.fetch_eip_implementation(client, 1559)
    
    def fetch_eip4844_implementation(self, client: str = "go-ethereum") -> Dict[str, str]:
        """Shortcut for fetch_eip_implementation(client, 4844)."""
        return self.fetch_eip_implementation(client, 4844)
    
    def fetch_geth_eip1559(self) -> Dict[str, str]:
        """Fetch EIP-1559 files from go-ethereum."""
        return self.fetch_eip_implementation("go-ethereum", 1559)
    
    def fetch_geth_eip4844(self) -> Dict[str, str]:
        """Fetch EIP-4844 files from go-ethereum."""
        return self.fetch_eip_implementation("go-ethereum", 4844)
    
    # ---- Search & clone ----
    
    def search_repository(self, owner: str, repo: str, query: str, 
                          language: Optional[str] = None) -> List[Dict[str, Any]]:
        """Search for code in a GitHub repo via the search API."""
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
        """Clone a repo locally for deeper analysis. Requires gitpython."""
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
        """Quick regex-based function extraction (parser.py has the full version)."""
        import re
        
        functions: List[Dict[str, Any]] = []
        
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
    
    # ---- Cache management ----
    
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
