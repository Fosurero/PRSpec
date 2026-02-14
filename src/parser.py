"""Source code parser — extracts functions, classes, and EIP-relevant blocks."""

import re
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path


@dataclass
class CodeBlock:
    """Represents a parsed code block (function, class, etc.)"""
    name: str
    type: str  # "function", "class", "method", etc.
    content: str
    start_line: int
    end_line: int
    language: str
    signature: Optional[str] = None
    docstring: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "type": self.type,
            "content": self.content,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "language": self.language,
            "signature": self.signature,
            "docstring": self.docstring,
        }


class CodeParser:
    """
    Multi-language code parser for extracting functions and classes.
    Uses regex patterns for simplicity; can be enhanced with tree-sitter.
    """
    
    def __init__(self, use_tree_sitter: bool = False):
        """Optionally enable tree-sitter for more accurate parsing."""
        self.use_tree_sitter = use_tree_sitter
        self._ts_parsers = {}
        
        if use_tree_sitter:
            self._init_tree_sitter()
    
    def _init_tree_sitter(self):
        """Initialize tree-sitter parsers"""
        try:
            import tree_sitter_python
            import tree_sitter_go
            from tree_sitter import Language, Parser
            
            # Set up parsers
            self._ts_parsers["python"] = Parser()
            self._ts_parsers["python"].set_language(Language(tree_sitter_python.language(), "python"))
            
            self._ts_parsers["go"] = Parser()
            self._ts_parsers["go"].set_language(Language(tree_sitter_go.language(), "go"))
            
        except ImportError:
            self.use_tree_sitter = False
    
    def parse_file(self, content: str, language: str, 
                   filename: Optional[str] = None) -> List[CodeBlock]:
        """Parse source code and return a list of CodeBlock entries."""
        language = language.lower()
        
        if self.use_tree_sitter and language in self._ts_parsers:
            return self._parse_with_tree_sitter(content, language)
        
        # Fallback to regex parsing
        if language == "go":
            return self._parse_go(content)
        elif language == "python":
            return self._parse_python(content)
        else:
            return self._parse_generic(content, language)
    
    def _parse_go(self, content: str) -> List[CodeBlock]:
        """Parse Go source code"""
        blocks = []
        lines = content.split('\n')
        
        # Pattern for function definitions
        # Return-type group handles: single word, pointer (*big.Int), tuple ((a, b)), or nothing.
        func_pattern = re.compile(
            r'^func\s+(?:\((\w+)\s+\*?(\w+)\)\s+)?(\w+)\s*\(([^)]*)\)\s*(?:\(([^)]*)\)|(\*?\w+(?:\.\w+)?))?(?:\s*)\{'
        )
        
        i = 0
        while i < len(lines):
            line = lines[i]
            match = func_pattern.match(line.strip())
            
            if match:
                # Found function start
                func_name = match.group(3)
                receiver = match.group(2) if match.group(2) else None
                start_line = i + 1
                
                # Find matching closing brace
                brace_count = line.count('{') - line.count('}')
                end_line = i
                
                while brace_count > 0 and end_line < len(lines) - 1:
                    end_line += 1
                    brace_count += lines[end_line].count('{')
                    brace_count -= lines[end_line].count('}')
                
                content_block = '\n'.join(lines[i:end_line + 1])
                
                blocks.append(CodeBlock(
                    name=func_name,
                    type="method" if receiver else "function",
                    content=content_block,
                    start_line=start_line,
                    end_line=end_line + 1,
                    language="go",
                    signature=line.strip()
                ))
                
                i = end_line
            
            i += 1
        
        return blocks
    
    def _parse_python(self, content: str) -> List[CodeBlock]:
        """Parse Python source code"""
        blocks = []
        lines = content.split('\n')
        
        # Patterns
        func_pattern = re.compile(r'^(\s*)def\s+(\w+)\s*\(([^)]*)\)\s*(?:->.*)?:')
        class_pattern = re.compile(r'^(\s*)class\s+(\w+)\s*(?:\([^)]*\))?\s*:')
        
        i = 0
        while i < len(lines):
            line = lines[i]
            
            # Check for class definition
            class_match = class_pattern.match(line)
            if class_match:
                indent = len(class_match.group(1))
                class_name = class_match.group(2)
                start_line = i + 1
                end_line = i
                
                # Find end of class
                while end_line < len(lines) - 1:
                    end_line += 1
                    next_line = lines[end_line]
                    if next_line.strip() and not next_line.startswith(' ' * (indent + 1)):
                        if not next_line.startswith(' ' * indent) or next_line.strip().startswith('class '):
                            break
                
                content_block = '\n'.join(lines[i:end_line])
                
                blocks.append(CodeBlock(
                    name=class_name,
                    type="class",
                    content=content_block,
                    start_line=start_line,
                    end_line=end_line,
                    language="python",
                    signature=line.strip()
                ))
                
                i = end_line - 1
                i += 1
                continue
            
            # Check for function definition
            func_match = func_pattern.match(line)
            if func_match:
                indent = len(func_match.group(1))
                func_name = func_match.group(2)
                start_line = i + 1
                end_line = i
                
                # Find end of function
                while end_line < len(lines) - 1:
                    end_line += 1
                    next_line = lines[end_line]
                    if next_line.strip() and not next_line.startswith(' ' * (indent + 1)):
                        if not next_line[indent:].startswith(' '):
                            break
                
                content_block = '\n'.join(lines[i:end_line])
                
                # Extract docstring
                docstring = None
                if i + 1 < len(lines):
                    next_stripped = lines[i + 1].strip()
                    if next_stripped.startswith('"""') or next_stripped.startswith("'''"):
                        docstring_lines = []
                        quote = next_stripped[:3]
                        j = i + 1
                        while j < len(lines):
                            docstring_lines.append(lines[j])
                            if lines[j].strip().endswith(quote) and j > i + 1:
                                break
                            if lines[j].count(quote) >= 2:
                                break
                            j += 1
                        docstring = '\n'.join(docstring_lines)
                
                blocks.append(CodeBlock(
                    name=func_name,
                    type="function" if indent == 0 else "method",
                    content=content_block,
                    start_line=start_line,
                    end_line=end_line,
                    language="python",
                    signature=line.strip(),
                    docstring=docstring
                ))
            
            i += 1
        
        return blocks
    
    def _parse_generic(self, content: str, language: str) -> List[CodeBlock]:
        """Generic parsing for unsupported languages"""
        return [CodeBlock(
            name="file",
            type="file",
            content=content,
            start_line=1,
            end_line=len(content.split('\n')),
            language=language
        )]
    
    def _parse_with_tree_sitter(self, content: str, language: str) -> List[CodeBlock]:
        """Parse using tree-sitter for more accurate results"""
        parser = self._ts_parsers.get(language)
        if not parser:
            return self._parse_generic(content, language)
        
        tree = parser.parse(bytes(content, "utf8"))
        blocks = []
        
        # Language-specific node types
        if language == "go":
            func_types = ["function_declaration", "method_declaration"]
        elif language == "python":
            func_types = ["function_definition", "class_definition"]
        else:
            return self._parse_generic(content, language)
        
        def traverse(node):
            if node.type in func_types:
                # Extract name
                name = None
                for child in node.children:
                    if child.type == "identifier" or child.type == "name":
                        name = content[child.start_byte:child.end_byte]
                        break
                
                if name:
                    blocks.append(CodeBlock(
                        name=name,
                        type="function" if "function" in node.type else "class",
                        content=content[node.start_byte:node.end_byte],
                        start_line=node.start_point[0] + 1,
                        end_line=node.end_point[0] + 1,
                        language=language
                    ))
            
            for child in node.children:
                traverse(child)
        
        traverse(tree.root_node)
        return blocks
    
    def find_function(self, content: str, function_name: str, 
                      language: str) -> Optional[CodeBlock]:
        """Find a specific function by name."""
        blocks = self.parse_file(content, language)
        
        for block in blocks:
            if block.name == function_name:
                return block
        
        return None
    
    def find_eip1559_functions(self, content: str, language: str) -> List[CodeBlock]:
        """Find EIP-1559 related functions. Delegates to find_eip_functions."""
        return self.find_eip_functions(content, language, 1559)
    
    def find_eip4844_functions(self, content: str, language: str) -> List[CodeBlock]:
        """Find EIP-4844 related functions. Delegates to find_eip_functions."""
        return self.find_eip_functions(content, language, 4844)
    
    # Per-EIP keyword sets for find_eip_functions.
    EIP_KEYWORDS: Dict[int, List[str]] = {
        1559: [
            "basefee", "base_fee", "gaslimit", "gas_limit",
            "feecap", "fee_cap", "tiplimit", "priority",
            "1559", "dynamicfee", "dynamic_fee",
            "calcbasefee", "calc_base_fee", "verifyeip1559",
        ],
        4844: [
            "blob", "4844", "kzg", "shard",
            "blob_gas", "blobgas", "excess_blob_gas", "excessblobgas",
            "blob_fee", "blobfee", "blobhash", "blob_hash",
            "blobsidecar", "blob_sidecar", "blobtx", "blob_tx",
            "max_blob", "maxblob", "validateblobtransaction",
            "validate_blob", "fakeblobsidecar", "calcexcessblobgas",
            "calc_excess_blob_gas", "blobbasefee", "blob_base_fee",
            "point_evaluation", "pointevaluation",
        ],
        4788: [
            "4788", "beacon_root", "beaconroot",
            "parent_beacon_block_root", "parentbeaconblockroot",
        ],
        2930: [
            "2930", "access_list", "accesslist",
            "accesslisttx", "access_list_tx",
        ],
        7002: [
            "7002", "withdrawal_request", "withdrawalrequest",
            "execution_layer_exit", "executionlayerexit",
        ],
        7251: [
            "7251", "max_effective_balance", "maxeffectivebalance",
            "consolidation",
        ],
    }
    
    def find_eip_functions(self, content: str, language: str,
                           eip_number: int) -> List[CodeBlock]:
        """Return all code blocks whose name or body matches registered keywords
        for the given EIP.  Falls back to the bare EIP number string."""
        blocks = self.parse_file(content, language)
        
        keywords = self.EIP_KEYWORDS.get(eip_number, [str(eip_number)])
        
        relevant: List[CodeBlock] = []
        for block in blocks:
            name_lower = block.name.lower()
            content_lower = block.content.lower()
            
            for keyword in keywords:
                if keyword in name_lower or keyword in content_lower:
                    relevant.append(block)
                    break
        
        return relevant
    
    def extract_comments(self, content: str, language: str) -> List[Dict[str, Any]]:
        """Pull out single-line comments, multi-line comments, and docstrings."""
        comments = []
        
        if language == "go":
            # Single line comments
            for i, line in enumerate(content.split('\n')):
                if '//' in line:
                    comment_start = line.index('//')
                    comments.append({
                        "line": i + 1,
                        "type": "single",
                        "content": line[comment_start + 2:].strip()
                    })
            
            # Multi-line comments
            pattern = re.compile(r'/\*.*?\*/', re.DOTALL)
            for match in pattern.finditer(content):
                comments.append({
                    "type": "multi",
                    "content": match.group()[2:-2].strip()
                })
        
        elif language == "python":
            # Single line comments
            for i, line in enumerate(content.split('\n')):
                stripped = line.strip()
                if stripped.startswith('#'):
                    comments.append({
                        "line": i + 1,
                        "type": "single",
                        "content": stripped[1:].strip()
                    })
            
            # Docstrings
            pattern = re.compile(r'""".*?"""|\'\'\'.*?\'\'\'', re.DOTALL)
            for match in pattern.finditer(content):
                comments.append({
                    "type": "docstring",
                    "content": match.group()[3:-3].strip()
                })
        
        return comments
