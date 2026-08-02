"""
gRPC Service Discovery Parser for Graphify.

Extracts:
- Services and their RPC methods
- Message definitions (request/response types)
- Streaming types (unary, server_streaming, client_streaming, bidirectional)
- Package and import relationships
- Code-level service implementations
"""

import re
import os
from typing import Dict, List, Set, Tuple, Optional, Any
from dataclasses import dataclass, field
import networkx as nx


@dataclass
class gRPCNode:
    """Represents a gRPC schema element."""
    name: str
    kind: str  # SERVICE, MESSAGE, ENUM, ONEOF
    file_path: str
    line_number: int
    package: Optional[str] = None
    fields: List[Dict[str, Any]] = field(default_factory=list)
    rpc_methods: List[Dict[str, Any]] = field(default_factory=list)
    imports: List[str] = field(default_factory=list)
    options: Dict[str, Any] = field(default_factory=dict)


class gRPCParser:
    """Parses .proto files and gRPC service implementations."""
    
    def __init__(self):
        self.nodes: Dict[str, gRPCNode] = {}
        self.edges: List[Tuple[str, str, Dict[str, Any]]] = []
        self.implementation_map: Dict[str, str] = {}  # service_method -> code_location
        
    def parse_file(self, file_path: str) -> None:
        """Parse a single .proto file."""
        if not os.path.exists(file_path):
            return
            
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        lines = content.split('\n')
        current_package: Optional[str] = None
        current_node: Optional[gRPCNode] = None
        brace_depth = 0
        in_message = False
        in_service = False
        in_enum = False
        
        for line_num, line in enumerate(lines, 1):
            stripped = line.strip()
            
            # Skip comments and empty lines
            if stripped.startswith('//') or not stripped:
                continue
                
            # Detect syntax and package
            syntax_match = re.match(r'^syntax\s*=\s*["\']proto3["\'];', stripped)
            if syntax_match:
                continue
                
            package_match = re.match(r'^package\s+([A-Za-z_][A-Za-z0-9_.]*);', stripped)
            if package_match:
                current_package = package_match.group(1)
                continue
                
            # Detect imports
            import_match = re.match(r'^import\s+(?:public\s+|weak\s+)?["\']([^"\']+)["\'];', stripped)
            if import_match:
                import_path = import_match.group(1)
                # Will be processed later for cross-file references
                continue
                
            # Detect message definitions
            message_match = re.match(r'^message\s+([A-Za-z_][A-Za-z0-9_]*)\s*\{', stripped)
            if message_match:
                msg_name = message_match.group(1)
                current_node = gRPCNode(
                    name=msg_name,
                    kind='MESSAGE',
                    file_path=file_path,
                    line_number=line_num,
                    package=current_package
                )
                self.nodes[msg_name] = current_node
                in_message = True
                brace_depth = 1
                continue
                
            # Detect service definitions
            service_match = re.match(r'^service\s+([A-Za-z_][A-Za-z0-9_]*)\s*\{', stripped)
            if service_match:
                svc_name = service_match.group(1)
                current_node = gRPCNode(
                    name=svc_name,
                    kind='SERVICE',
                    file_path=file_path,
                    line_number=line_num,
                    package=current_package
                )
                self.nodes[svc_name] = current_node
                in_service = True
                brace_depth = 1
                continue
                
            # Detect enum definitions
            enum_match = re.match(r'^enum\s+([A-Za-z_][A-Za-z0-9_]*)\s*\{', stripped)
            if enum_match:
                enum_name = enum_match.group(1)
                current_node = gRPCNode(
                    name=enum_name,
                    kind='ENUM',
                    file_path=file_path,
                    line_number=line_num,
                    package=current_package
                )
                self.nodes[enum_name] = current_node
                in_enum = True
                brace_depth = 1
                continue
                
            # Parse message fields
            if in_message and current_node and current_node.kind == 'MESSAGE':
                # Check for closing brace
                if stripped == '}':
                    in_message = False
                    current_node = None
                    continue
                    
                # Parse field: type name = tag;
                field_match = re.match(
                    r'^(optional|required|repeated)?\s*([A-Za-z_][A-Za-z0-9_.]*)\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(\d+)\s*(?:\[([^\]]*)\])?\s*;',
                    stripped
                )
                
                if field_match:
                    label = field_match.group(1)
                    field_type = field_match.group(2)
                    field_name = field_match.group(3)
                    tag = field_match.group(4)
                    options_str = field_match.group(5)
                    
                    field_info = {
                        'name': field_name,
                        'type': field_type,
                        'tag': int(tag),
                        'label': label or 'optional'
                    }
                    
                    if options_str:
                        field_info['options'] = options_str
                        
                    current_node.fields.append(field_info)
                    
                    # Add type reference edge
                    base_type = field_type.split('.')[-1]  # Handle package prefixes
                    if base_type not in {'string', 'bytes', 'int32', 'int64', 'uint32', 'uint64', 
                                         'sint32', 'sint64', 'fixed32', 'fixed64', 'sfixed32', 
                                         'sfixed64', 'float', 'double', 'bool'}:
                        self.edges.append((
                            f"{current_node.name}.{field_name}",
                            base_type,
                            {'edge_type': 'uses_type', 'file': file_path, 'line': line_num}
                        ))
                        
            # Parse service RPC methods
            if in_service and current_node and current_node.kind == 'SERVICE':
                # Check for closing brace
                if stripped == '}':
                    in_service = False
                    current_node = None
                    continue
                    
                # Parse rpc method
                rpc_match = re.match(
                    r'^rpc\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(\s*(stream\s+)?([A-Za-z_][A-Za-z0-9_.]*)\s*\)\s*returns\s*\(\s*(stream\s+)?([A-Za-z_][A-Za-z0-9_.]*)\s*\)',
                    stripped
                )
                
                if rpc_match:
                    method_name = rpc_match.group(1)
                    client_stream = rpc_match.group(2) is not None
                    request_type = rpc_match.group(3)
                    server_stream = rpc_match.group(4) is not None
                    response_type = rpc_match.group(5)
                    
                    # Determine streaming type
                    if client_stream and server_stream:
                        stream_type = 'bidirectional'
                    elif server_stream:
                        stream_type = 'server_streaming'
                    elif client_stream:
                        stream_type = 'client_streaming'
                    else:
                        stream_type = 'unary'
                        
                    method_info = {
                        'name': method_name,
                        'request_type': request_type,
                        'response_type': response_type,
                        'stream_type': stream_type,
                        'client_streaming': client_stream,
                        'server_streaming': server_stream
                    }
                    
                    current_node.rpc_methods.append(method_info)
                    
                    # Add edges for request/response types
                    req_base = request_type.split('.')[-1]
                    resp_base = response_type.split('.')[-1]
                    
                    full_method_name = f"{current_node.name}.{method_name}"
                    
                    self.edges.append((
                        full_method_name,
                        req_base,
                        {'edge_type': 'accepts_request', 'file': file_path, 'line': line_num}
                    ))
                    
                    self.edges.append((
                        full_method_name,
                        resp_base,
                        {'edge_type': 'returns_response', 'file': file_path, 'line': line_num}
                    ))
                    
            # Parse enum values
            if in_enum and current_node and current_node.kind == 'ENUM':
                if stripped == '}':
                    in_enum = False
                    current_node = None
                    continue
                    
                enum_value_match = re.match(r'^([A-Z_][A-Z0-9_]*)\s*=\s*(-?\d+)', stripped)
                if enum_value_match:
                    value_name = enum_value_match.group(1)
                    value_num = int(enum_value_match.group(2))
                    current_node.fields.append({
                        'name': value_name,
                        'value': value_num
                    })
                    
        # Track options and other metadata
        self._parse_options(content, file_path, current_package)
        
    def _parse_options(self, content: str, file_path: str, package: Optional[str]) -> None:
        """Parse proto options (e.g., go_package, java_package, etc.)."""
        option_patterns = [
            r'option\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*["\']([^"\']+)["\'];',
            r'option\s*\(([A-Za-z_][A-Za-z0-9_.]*)\)\s*=\s*([^;]+);'
        ]
        
        for pattern in option_patterns:
            for match in re.finditer(pattern, content):
                opt_name = match.group(1)
                opt_value = match.group(2)
                
                # Store in a special node for file-level options
                opt_node_name = f"_options_{os.path.basename(file_path)}"
                if opt_node_name not in self.nodes:
                    self.nodes[opt_node_name] = gRPCNode(
                        name=opt_node_name,
                        kind='FILE_OPTIONS',
                        file_path=file_path,
                        line_number=0,
                        package=package
                    )
                    
                self.nodes[opt_node_name].options[opt_name] = opt_value
                
    def parse_implementations(self, code_dir: str, languages: List[str] = ['python', 'go', 'java', 'typescript']) -> None:
        """Scan code directory for gRPC service implementations."""
        impl_patterns = {
            'python': [
                r'class\s+([A-Za-z_][A-Za-z0-9_]*)Servicer\s*\([^)]*\)',
                r'def\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(\s*self,\s*request,\s*context',
                r'add_([A-Za-z_][A-Za-z0-9_]*)Servicer_to_server',
            ],
            'go': [
                r'type\s+([A-Za-z_][A-Za-z0-9_]*)Server\s+interface',
                r'func\s+\([^)]+\)\s+([A-Za-z_][A-Za-z0-9_]*)\s*\([^)]*\)',
                r'register([A-Za-z_][A-Za-z0-9_]*)Server',
            ],
            'java': [
                r'public\s+static\s+abstract\s+class\s+([A-Za-z_][A-Za-z0-9_]*)Impl',
                r'@Override\s+public\s+void\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(',
            ],
            'typescript': [
                r'class\s+([A-Za-z_][A-Za-z0-9_]*)Service\s+implements',
                r'async\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(\s*call',
            ]
        }
        
        for root, dirs, files in os.walk(code_dir):
            # Skip common non-source directories
            dirs[:] = [d for d in dirs if d not in {'node_modules', 'vendor', '.git', '__pycache__', 'build', 'dist'}]
            
            for file in files:
                file_path = os.path.join(root, file)
                ext = os.path.splitext(file)[1].lower()
                
                lang_map = {'.py': 'python', '.go': 'go', '.java': 'java', '.ts': 'typescript', '.js': 'typescript'}
                lang = lang_map.get(ext)
                
                if lang not in languages:
                    continue
                    
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        
                    for pattern in impl_patterns.get(lang, []):
                        for match in re.finditer(pattern, content):
                            impl_name = match.group(1) if match.lastindex else match.group(0)
                            self.implementation_map[impl_name] = file_path
                            
                            # Try to link to proto definition
                            for node_name in self.nodes:
                                if node_name.lower() == impl_name.lower().replace('servicer', '').replace('service', ''):
                                    self.edges.append((
                                        file_path,
                                        node_name,
                                        {'edge_type': 'implements_service', 'line': content[:match.start()].count('\n') + 1}
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
                package=node.package,
                fields=node.fields,
                rpc_methods=node.rpc_methods,
                imports=node.imports,
                options=node.options,
                node_type='grpc'
            )
            
        # Add edges
        for source, target, attrs in self.edges:
            # For field-type edges, target might not be a node yet
            if source in G.nodes:
                if target not in G.nodes:
                    # Create placeholder node for external types
                    G.add_node(target, kind='EXTERNAL_TYPE', node_type='grpc')
                G.add_edge(source, target, **attrs)
                
        # Add implementation edges
        for code_path, service_name in self.implementation_map.items():
            # Try to find matching service
            for node_name in G.nodes:
                if node_name.lower() == service_name.lower().replace('servicer', '').replace('service', ''):
                    if G.nodes[node_name].get('kind') == 'SERVICE':
                        G.add_edge(
                            code_path,
                            node_name,
                            edge_type='implements_service',
                            node_type='code_to_grpc'
                        )
                        
        return G


def extract_proto_files(directory: str) -> List[str]:
    """Find all .proto files in directory."""
    proto_files = []
    for root, dirs, files in os.walk(directory):
        # Skip common non-source directories
        dirs[:] = [d for d in dirs if d not in {'node_modules', 'vendor', '.git', '__pycache__', 'build', 'dist'}]
        
        for file in files:
            if file.endswith('.proto'):
                proto_files.append(os.path.join(root, file))
                
    return proto_files


def parse_grpc_project(directory: str, include_implementations: bool = True) -> nx.DiGraph:
    """Main entry point for gRPC parsing."""
    parser = gRPCParser()
    
    # Parse proto files
    proto_files = extract_proto_files(directory)
    for file_path in proto_files:
        parser.parse_file(file_path)
        
    # Parse implementations
    if include_implementations:
        parser.parse_implementations(directory)
        
    return parser.build_graph()
