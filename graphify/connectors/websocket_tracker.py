"""
WebSocket Connection Tracker for Graphify.

Extracts:
- WebSocket server endpoints
- Client connection code
- Message handlers (on_message, on_open, on_close, on_error)
- WebSocket upgrade paths from HTTP
- Real-time event subscriptions
"""

import re
import os
from typing import Dict, List, Set, Tuple, Optional, Any
from dataclasses import dataclass, field
import networkx as nx
import logging
logger = logging.getLogger(__name__)


@dataclass
class WSNode:
    """Represents a WebSocket element."""
    name: str
    kind: str  # SERVER_ENDPOINT, CLIENT, HANDLER, MESSAGE_TYPE
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    endpoint_path: Optional[str] = None
    protocols: List[str] = field(default_factory=list)
    message_handlers: Dict[str, str] = field(default_factory=dict)


class WebSocketTracker:
    """Tracks WebSocket connections and message flows."""

    def __init__(self):
        self.nodes: Dict[str, WSNode] = {}
        self.edges: List[Tuple[str, str, Dict[str, Any]]] = []

    def parse_websocket_servers(self, code_dir: str, languages: List[str] = ['python', 'javascript', 'typescript', 'java', 'go']) -> None:
        """Scan code for WebSocket server definitions."""

        ws_server_patterns = {
            'python': {
                'server': [
                    r'websockets\.serve\s*\(\s*([A-Za-z_][A-Za-z0-9_]*)\s*,\s*[\'"]([^"\']+)[\'"]\s*,\s*(\d+)',
                    r'@app\.websocket\s*\(\s*[\'"]([^"\']+)[\'"]',
                    r'SocketIO\s*\(\s*.*?\s*origins\s*=\s*\[([^\]]+)\]',
                ],
                'handler': [
                    r'async\s+def\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(\s*websocket\s*,\s*path',
                    r'async\s+def\s+on_message\s*\(\s*self\s*,\s*websocket\s*,\s*message',
                    r'async\s+def\s+on_connect\s*\(\s*self\s*,\s*websocket',
                ],
                'upgrade': [
                    r'request\.scope\[["\']type["\']\]\s*==\s*["\']websocket["\']',
                    r'Upgrade\s*:\s*websocket',
                ]
            },
            'javascript': {
                'server': [
                    r'new\s+WebSocket\.Server\s*\(\s*\{\s*port\s*:\s*(\d+)',
                    r'ws\.Server\s*\(\s*\{\s*path\s*:\s*[\'"]([^"\']+)[\'"]',
                    r'io\s*\(\s*\)\s*\.\s*on\s*\(\s*[\'"]connection[\'"]',
                ],
                'handler': [
                    r'\.on\s*\(\s*[\'"]connection[\'"]\s*,\s*\(\s*([A-Za-z_][A-Za-z0-9_]*)',
                    r'\.on\s*\(\s*[\'"]message[\'"]\s*,\s*\(\s*([A-Za-z_][A-Za-z0-9_]*)',
                    r'async\s+function\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(\s*socket',
                ]
            },
            'typescript': {
                'server': [
                    r'@WebSocketGateway\s*\(\s*(\d+)?\s*(?:,\s*\{\s*path\s*:\s*[\'"]([^"\']+)[\'"]',
                    r'new\s+WebSocketServer\s*\(\s*\{\s*port\s*:\s*(\d+)',
                ],
                'handler': [
                    r'@SubscribeMessage\s*\(\s*[\'"]([^"\']+)[\'"]',
                    r'handleConnection\s*\(\s*client\s*:',
                ]
            },
            'java': {
                'server': [
                    r'@ServerEndpoint\s*\(\s*[\'"]([^"\']+)[\'"]',
                    r'new\s+ServerBuilder\s*\(\s*(\d+)\s*\)',
                ],
                'handler': [
                    r'@OnMessage\s+public\s+void\s+([A-Za-z_][A-Za-z0-9_]*)',
                    r'@OnOpen\s+public\s+void\s+([A-Za-z_][A-Za-z0-9_]*)',
                ]
            },
            'go': {
                'server': [
                    r'http\.HandleFunc\s*\(\s*[\'"]([^"\']+)[\'"]\s*,\s*func\s*\(\s*w\s+http\.ResponseWriter\s*,\s*r\s+\*http\.Request\s*\)\s*\{[^}]*upgrader\.Upgrade',
                    r'websocket\.Upgrader\s*\{\}',
                ],
                'handler': [
                    r'func\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(\s*conn\s+\*websocket\.Conn',
                ]
            }
        }

        for root, dirs, files in os.walk(code_dir):
            dirs[:] = [d for d in dirs if d not in {'node_modules', 'vendor', '.git', '__pycache__', 'build', 'dist'}]

            for file in files:
                file_path = os.path.join(root, file)
                ext = os.path.splitext(file)[1].lower()

                lang_map = {'.py': 'python', '.js': 'javascript', '.ts': 'typescript', '.java': 'java', '.go': 'go'}
                lang = lang_map.get(ext)

                if lang not in languages:
                    continue

                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()

                    lines = content.split('\n')

                    # Find server endpoints
                    for pattern in ws_server_patterns.get(lang, {}).get('server', []):
                        for match in re.finditer(pattern, content):
                            endpoint_path = None
                            port = None

                            if match.lastindex:
                                groups = match.groups()
                                if len(groups) >= 2:
                                    # Try to identify which group is path vs port
                                    for g in groups:
                                        if g and g.startswith('/'):
                                            endpoint_path = g
                                        elif g and g.isdigit():
                                            port = int(g)

                            if not endpoint_path:
                                endpoint_path = f"/ws_{match.start()}"

                            node_name = f"ws_server_{os.path.basename(file_path)}_{match.start()}"
                            line_num = content[:match.start()].count('\n') + 1

                            self.nodes[node_name] = WSNode(
                                name=node_name,
                                kind='SERVER_ENDPOINT',
                                file_path=file_path,
                                line_number=line_num,
                                endpoint_path=endpoint_path or '/ws',
                                protocols=['websocket']
                            )

                    # Find message handlers
                    for pattern in ws_server_patterns.get(lang, {}).get('handler', []):
                        for match in re.finditer(pattern, content):
                            handler_name = match.group(1) if match.lastindex else match.group(0)
                            line_num = content[:match.start()].count('\n') + 1

                            # Determine handler type
                            handler_type = 'generic'
                            if 'message' in handler_name.lower() or 'on_message' in handler_name.lower():
                                handler_type = 'on_message'
                            elif 'connect' in handler_name.lower() or 'on_open' in handler_name.lower() or 'onopen' in handler_name.lower():
                                handler_type = 'on_open'
                            elif 'close' in handler_name.lower() or 'on_close' in handler_name.lower() or 'onclose' in handler_name.lower():
                                handler_type = 'on_close'
                            elif 'error' in handler_name.lower() or 'on_error' in handler_name.lower() or 'onerror' in handler_name.lower():
                                handler_type = 'on_error'

                            handler_node = f"ws_handler_{handler_name}_{match.start()}"

                            self.nodes[handler_node] = WSNode(
                                name=handler_name,
                                kind='HANDLER',
                                file_path=file_path,
                                line_number=line_num,
                                message_handlers={'type': handler_type}
                            )

                            # Link handler to nearest server endpoint
                            self._link_handler_to_server(handler_node, file_path, match.start())

                except Exception as e:
                    logger.debug("skipping entry: %s", e)
    def _link_handler_to_server(self, handler_node: str, file_path: str, position: int) -> None:
        """Link a handler to its nearest server endpoint."""
        # Find the closest server endpoint in the same file
        closest_server = None
        min_distance = float('inf')

        for node_name, node in self.nodes.items():
            if node.kind == 'SERVER_ENDPOINT' and node.file_path == file_path:
                distance = abs(position - (node.line_number or 0))
                if distance < min_distance:
                    min_distance = distance
                    closest_server = node_name

        if closest_server:
            self.edges.append((
                handler_node,
                closest_server,
                {'edge_type': 'handles_for', 'file': file_path}
            ))

    def parse_websocket_clients(self, code_dir: str, languages: List[str] = ['python', 'javascript', 'typescript', 'java', 'go', 'swift', 'kotlin']) -> None:
        """Scan code for WebSocket client connections."""

        ws_client_patterns = {
            'python': {
                'client': [
                    r'websockets\.connect\s*\(\s*[\'"]([^"\']+)[\'"]',
                    r'WebSocketClient\s*\(\s*[\'"]([^"\']+)[\'"]',
                ],
                'send': [
                    r'await\s+websocket\.send\s*\(\s*[\'"]([^"\']+)[\'"]',
                    r'websocket\.send\s*\(\s*json\.dumps\s*\(\s*\{[^}]*["\']type["\']:\s*["\']([^"\']+)[\'"]',
                ]
            },
            'javascript': {
                'client': [
                    r'new\s+WebSocket\s*\(\s*[\'"]([^"\']+)[\'"]',
                    r'ws\s*=\s*new\s+WebSocket\s*\(',
                ],
                'send': [
                    r'\.send\s*\(\s*JSON\.stringify\s*\(\s*\{[^}]*type:\s*[\'"]([^"\']+)[\'"]',
                ]
            },
            'typescript': {
                'client': [
                    r'new\s+WebSocket\s*\(\s*[\'"]([^"\']+)[\'"]',
                    r'\.create\s*\(\s*[\'"]([^"\']+)[\'"]',
                ]
            },
            'java': {
                'client': [
                    r'new\s+WebSocketClient\s*\(\s*URI\.create\s*\(\s*[\'"]([^"\']+)[\'"]',
                    r'@ClientEndpoint\s*\(\s*[\'"]([^"\']+)[\'"]',
                ]
            },
            'go': {
                'client': [
                    r'websocket\.Dial\s*\(\s*[\'"]([^"\']+)[\'"]',
                    r'DialContext\s*\(\s*ctx\s*,\s*[\'"]([^"\']+)[\'"]',
                ]
            },
            'swift': {
                'client': [
                    r'URLSession\s*\.\s*webSocketTask\s*\(\s*with:\s*URL\s*\(\s*string:\s*[\'"]([^"\']+)[\'"]',
                ]
            },
            'kotlin': {
                'client': [
                    r'WebSocket\s*\(\s*[\'"]([^"\']+)[\'"]',
                    r'okhttp3\.WebSocket',
                ]
            }
        }

        for root, dirs, files in os.walk(code_dir):
            dirs[:] = [d for d in dirs if d not in {'node_modules', 'vendor', '.git', '__pycache__', 'build', 'dist'}]

            for file in files:
                file_path = os.path.join(root, file)
                ext = os.path.splitext(file)[1].lower()

                lang_map = {
                    '.py': 'python', '.js': 'javascript', '.ts': 'typescript',
                    '.java': 'java', '.go': 'go', '.swift': 'swift', '.kt': 'kotlin'
                }
                lang = lang_map.get(ext)

                if lang not in languages:
                    continue

                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()

                    # Find client connections
                    for pattern in ws_client_patterns.get(lang, {}).get('client', []):
                        for match in re.finditer(pattern, content):
                            ws_url = match.group(1) if match.lastindex else 'unknown'
                            line_num = content[:match.start()].count('\n') + 1

                            client_node = f"ws_client_{os.path.basename(file_path)}_{match.start()}"

                            self.nodes[client_node] = WSNode(
                                name=client_node,
                                kind='CLIENT',
                                file_path=file_path,
                                line_number=line_num,
                                endpoint_path=ws_url
                            )

                    # Find message sends (for tracking message types)
                    for pattern in ws_client_patterns.get(lang, {}).get('send', []):
                        for match in re.finditer(pattern, content):
                            msg_type = match.group(1) if match.lastindex else 'unknown'
                            line_num = content[:match.start()].count('\n') + 1

                            msg_node = f"ws_message_{msg_type}_{match.start()}"

                            if msg_node not in self.nodes:
                                self.nodes[msg_node] = WSNode(
                                    name=msg_type,
                                    kind='MESSAGE_TYPE',
                                    file_path=file_path,
                                    line_number=line_num
                                )

                except Exception as e:
                    logger.debug("skipping entry: %s", e)
    def build_graph(self) -> nx.DiGraph:
        """Build NetworkX graph from parsed WebSocket data."""
        G = nx.DiGraph()

        # Add nodes
        for name, node in self.nodes.items():
            G.add_node(
                name,
                kind=node.kind,
                file=node.file_path,
                line=node.line_number,
                endpoint_path=node.endpoint_path,
                protocols=node.protocols,
                message_handlers=node.message_handlers,
                node_type='websocket'
            )

        # Add edges
        for source, target, attrs in self.edges:
            if source in G.nodes and target in G.nodes:
                G.add_edge(source, target, **attrs)

        # Add client-to-server connection edges
        self._add_connection_edges(G)

        return G

    def _add_connection_edges(self, G: nx.DiGraph) -> None:
        """Add edges connecting clients to servers based on endpoint paths."""
        clients = [(name, node) for name, node in self.nodes.items() if node.kind == 'CLIENT']
        servers = [(name, node) for name, node in self.nodes.items() if node.kind == 'SERVER_ENDPOINT']

        for client_name, client_node in clients:
            client_path = client_node.endpoint_path or ''

            for server_name, server_node in servers:
                server_path = server_node.endpoint_path or ''

                # Simple path matching
                if client_path and server_path and (client_path == server_path or client_path.endswith(server_path)):
                    G.add_edge(
                        client_name,
                        server_name,
                        edge_type='connects_to',
                        file=client_node.file_path
                    )


def parse_websocket_project(directory: str) -> nx.DiGraph:
    """Main entry point for WebSocket parsing."""
    tracker = WebSocketTracker()

    # Parse servers
    tracker.parse_websocket_servers(directory)

    # Parse clients
    tracker.parse_websocket_clients(directory)

    return tracker.build_graph()
