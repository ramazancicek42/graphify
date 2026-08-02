"""
GraphQL Schema & Resolver Parser for Graphify.

Extracts:
- Types (Object, Input, Interface, Enum, Union, Scalar)
- Fields & Arguments
- Queries, Mutations, Subscriptions
- Directives
- Resolver mappings (code -> schema)
"""

import re
import os
from typing import Dict, List, Set, Tuple, Optional, Any
from dataclasses import dataclass, field
import networkx as nx


@dataclass
class GraphQLNode:
    """Represents a GraphQL schema element."""
    name: str
    kind: str  # OBJECT, INPUT_OBJECT, INTERFACE, ENUM, UNION, SCALAR
    file_path: str
    line_number: int
    fields: List[str] = field(default_factory=list)
    arguments: List[Dict[str, Any]] = field(default_factory=list)
    directives: List[str] = field(default_factory=list)
    implements: List[str] = field(default_factory=list)
    description: Optional[str] = None


class GraphQLParser:
    """Parses GraphQL schema files and resolver code."""
    
    TYPE_KEYWORDS = {'type', 'input', 'interface', 'enum', 'union', 'scalar'}
    ROOT_TYPES = {'Query', 'Mutation', 'Subscription'}
    
    def __init__(self):
        self.nodes: Dict[str, GraphQLNode] = {}
        self.edges: List[Tuple[str, str, Dict[str, Any]]] = []
        self.resolver_map: Dict[str, str] = {}  # schema_field -> code_location
        
    def parse_file(self, file_path: str) -> None:
        """Parse a single .graphql or .gql file."""
        if not os.path.exists(file_path):
            return
            
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        lines = content.split('\n')
        current_type: Optional[GraphQLNode] = None
        brace_depth = 0
        
        for line_num, line in enumerate(lines, 1):
            stripped = line.strip()
            
            # Skip comments and empty lines
            if stripped.startswith('#') or not stripped:
                continue
                
            # Detect type definitions
            type_match = re.match(
                r'^(type|input|interface|enum|union|scalar)\s+([A-Za-z_][A-Za-z0-9_]*)\s*(?:implements\s+([A-Za-z_][A-Za-z0-9_,\s]*))?\s*(?:@([A-Za-z_][A-Za-z0-9_]*(?:\([^)]*\))?))?\s*\{?',
                stripped
            )
            
            if type_match:
                kind_keyword = type_match.group(1).upper()
                type_name = type_match.group(2)
                implements_str = type_match.group(3)
                directive_str = type_match.group(4)
                
                implements_list = []
                if implements_str:
                    implements_list = [i.strip() for i in implements_str.split(',')]
                    
                directives = []
                if directive_str:
                    directives = [directive_str]
                
                # Handle union special case (uses = instead of {})
                if kind_keyword == 'UNION':
                    union_match = re.search(r'=\s*(.+)$', stripped)
                    if union_match:
                        types_str = union_match.group(1)
                        current_type = GraphQLNode(
                            name=type_name,
                            kind=kind_keyword,
                            file_path=file_path,
                            line_number=line_num,
                            fields=[t.strip() for t in types_str.split('|')],
                            directives=directives
                        )
                        self.nodes[type_name] = current_type
                        self._add_type_edges(current_type)
                    continue
                
                current_type = GraphQLNode(
                    name=type_name,
                    kind=kind_keyword,
                    file_path=file_path,
                    line_number=line_num,
                    implements=implements_list,
                    directives=directives
                )
                self.nodes[type_name] = current_type
                
                if '{' in stripped:
                    brace_depth = 1
                continue
            
            # Track braces
            if current_type:
                brace_depth += stripped.count('{') - stripped.count('}')
                
                # Parse fields
                if brace_depth > 0:
                    field_match = re.match(
                        r'^([A-Za-z_][A-Za-z0-9_]*)\s*(?:\(([^)]*)\))?\s*:\s*([A-Za-z_][A-Za-z0-9_!\[\]?]*)\s*(?:@([A-Za-z_][A-Za-z0-9_]*(?:\([^)]*\))?))?',
                        stripped
                    )
                    
                    if field_match:
                        field_name = field_match.group(1)
                        args_str = field_match.group(2)
                        return_type = field_match.group(3)
                        field_directive = field_match.group(4)
                        
                        current_type.fields.append(field_name)
                        
                        if args_str:
                            # Parse arguments
                            args = self._parse_arguments(args_str)
                            current_type.arguments.extend(args)
                            
                        if field_directive:
                            current_type.directives.append(field_directive)
                            
                        # Add field type edge
                        base_type = re.sub(r'[\[\]!]', '', return_type)
                        self.edges.append((
                            f"{current_type.name}.{field_name}",
                            base_type,
                            {'edge_type': 'returns_type', 'file': file_path, 'line': line_num}
                        ))
                        
                if brace_depth <= 0:
                    current_type = None
                    
        self._add_type_edges(current_type)
        
    def _parse_arguments(self, args_str: str) -> List[Dict[str, Any]]:
        """Parse field arguments."""
        args = []
        for arg in args_str.split(','):
            arg = arg.strip()
            match = re.match(r'([A-Za-z_][A-Za-z0-9_]*)\s*:\s*([A-Za-z_][A-Za-z0-9_!\[\]?]*)', arg)
            if match:
                args.append({
                    'name': match.group(1),
                    'type': match.group(2)
                })
        return args
        
    def _add_type_edges(self, type_node: Optional[GraphQLNode]) -> None:
        """Add edges for implements and references."""
        if not type_node:
            return
            
        for impl in type_node.implements:
            self.edges.append((
                type_node.name,
                impl,
                {'edge_type': 'implements', 'file': type_node.file_path, 'line': type_node.line_number}
            ))
            
    def parse_resolvers(self, code_dir: str, languages: List[str] = ['python', 'javascript', 'typescript']) -> None:
        """Scan code directory for resolver implementations."""
        # This would integrate with existing tree-sitter extractors
        # Pattern matching for common resolver patterns
        resolver_patterns = {
            'python': [
                r'def\s+resolve_([A-Za-z_][A-Za-z0-9_]*)\s*\(',
                r'@resolver\(\'([A-Za-z_][A-Za-z0-9_.]*)\'\)',
                r'class\s+([A-Za-z_][A-Za-z0-9_]*)Resolver',
            ],
            'javascript': [
                r'([A-Za-z_][A-Za-z0-9_]*):\s*async\s*\([^)]*\)\s*=>',
                r'resolve([A-Za-z_][A-Za-z0-9_]*)\s*:',
            ],
            'typescript': [
                r'([A-Za-z_][A-Za-z0-9_]*)\s*:\s*Resolver<[^>]+>',
                r'@ResolveField\(\s*[\'"]([A-Za-z_][A-Za-z0-9_]*)[\'"]',
            ]
        }
        
        for root, dirs, files in os.walk(code_dir):
            for file in files:
                file_path = os.path.join(root, file)
                ext = os.path.splitext(file)[1].lower()
                
                lang_map = {'.py': 'python', '.js': 'javascript', '.ts': 'typescript'}
                lang = lang_map.get(ext)
                
                if lang not in languages:
                    continue
                    
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        
                    for pattern in resolver_patterns.get(lang, []):
                        for match in re.finditer(pattern, content):
                            resolver_name = match.group(1) if match.lastindex else match.group(0)
                            self.resolver_map[resolver_name] = file_path
                            
                            # Link to schema if possible
                            if resolver_name in self.nodes:
                                self.edges.append((
                                    file_path,
                                    resolver_name,
                                    {'edge_type': 'implements_resolver', 'line': content[:match.start()].count('\n') + 1}
                                ))
                except Exception:
                    pass
                    
    def build_graph(self) -> nx.DiGraph:
        """Build NetworkX graph from parsed data."""
        G = nx.DiGraph()
        
        # Add nodes
        for name, node in self.nodes.items():
            G.add_node(
                name,
                kind=node.kind,
                file=node.file_path,
                line=node.line_number,
                fields=node.fields,
                arguments=node.arguments,
                directives=node.directives,
                implements=node.implements,
                node_type='graphql'
            )
            
        # Add edges
        for source, target, attrs in self.edges:
            if source in G.nodes and target in G.nodes:
                G.add_edge(source, target, **attrs)
                
        # Add resolver edges
        for code_path, schema_name in self.resolver_map.items():
            if schema_name in G.nodes:
                G.add_edge(
                    code_path,
                    schema_name,
                    edge_type='resolves',
                    node_type='code_to_graphql'
                )
                
        return G


def extract_graphql_files(directory: str) -> List[str]:
    """Find all GraphQL files in directory."""
    graphql_files = []
    for root, dirs, files in os.walk(directory):
        # Skip node_modules, vendor, etc.
        dirs[:] = [d for d in dirs if d not in {'node_modules', 'vendor', '.git', '__pycache__'}]
        
        for file in files:
            if file.endswith(('.graphql', '.gql')):
                graphql_files.append(os.path.join(root, file))
                
    return graphql_files


def parse_graphql_project(directory: str, include_resolvers: bool = True) -> nx.DiGraph:
    """Main entry point for GraphQL parsing."""
    parser = GraphQLParser()
    
    # Parse schema files
    graphql_files = extract_graphql_files(directory)
    for file_path in graphql_files:
        parser.parse_file(file_path)
        
    # Parse resolvers
    if include_resolvers:
        parser.parse_resolvers(directory)
        
    return parser.build_graph()
