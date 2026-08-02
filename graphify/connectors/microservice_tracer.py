"""
Microservice Call Tracer for Graphify.

Extracts:
- Inter-service HTTP/RPC calls
- Service discovery configurations
- Circuit breaker patterns
- Retry and timeout configurations
- Distributed tracing headers propagation
- Service mesh configurations (Istio, Linkerd)
"""

import re
import os
from typing import Dict, List, Set, Tuple, Optional, Any
from dataclasses import dataclass, field
import networkx as nx
import logging
logger = logging.getLogger(__name__)


@dataclass
class MicroserviceNode:
    """Represents a microservice or service interaction element."""
    name: str
    kind: str  # SERVICE, API_CALL, CIRCUIT_BREAKER, RETRY_CONFIG, TRACING
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    target_service: Optional[str] = None
    endpoint: Optional[str] = None
    protocol: str = 'HTTP'  # HTTP, gRPC, GraphQL
    configs: Dict[str, Any] = field(default_factory=dict)


class MicroserviceTracer:
    """Traces inter-service communication patterns."""

    def __init__(self):
        self.nodes: Dict[str, MicroserviceNode] = {}
        self.edges: List[Tuple[str, str, Dict[str, Any]]] = []
        self.service_registry: Dict[str, str] = {}  # service_name -> base_url

    def parse_service_definitions(self, code_dir: str, languages: List[str] = ['python', 'javascript', 'typescript', 'java', 'go']) -> None:
        """Scan code for service definitions and registrations."""

        service_patterns = {
            'python': {
                'define': [
                    r'class\s+([A-Za-z_][A-Za-z0-9_]*)Service\s*:',
                    r'@app\.service\s*\(\s*[\'"]([^"\']+)[\'"]',
                    r'register_service\s*\(\s*name\s*=\s*[\'"]([^"\']+)[\'"]',
                ],
                'config': [
                    r'SERVICE_NAME\s*=\s*[\'"]([^"\']+)[\'"]',
                    r'"name":\s*[\'"]([^"\']+)[\'"]\s*,.*"port":\s*(\d+)',
                ]
            },
            'javascript': {
                'define': [
                    r'class\s+([A-Za-z_][A-Za-z0-9_]*)Service',
                    r'microservice\s*\(\s*\{\s*name:\s*[\'"]([^"\']+)[\'"]',
                ]
            },
            'typescript': {
                'define': [
                    r'@Controller\s*\(\s*[\'"]([^"\']+)[\'"]',
                    r'@Microservice\s*\(\s*\{\s*name:\s*[\'"]([^"\']+)[\'"]',
                ]
            },
            'java': {
                'define': [
                    r'@RestController\s*@RequestMapping\s*\(\s*[\'"]/([^"\']+)[\'"]',
                    r'@Service\s+public\s+class\s+([A-Za-z_][A-Za-z0-9_]*)',
                ]
            },
            'go': {
                'define': [
                    r'func\s+New([A-Za-z_][A-Za-z0-9_]*)Service',
                    r'service\.Register\s*\(\s*[\'"]([^"\']+)[\'"]',
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

                    for pattern in service_patterns.get(lang, {}).get('define', []):
                        for match in re.finditer(pattern, content):
                            service_name = match.group(1) if match.lastindex else match.group(0)
                            line_num = content[:match.start()].count('\n') + 1

                            node_name = f"service_{service_name}"

                            self.nodes[node_name] = MicroserviceNode(
                                name=service_name,
                                kind='SERVICE',
                                file_path=file_path,
                                line_number=line_num,
                                protocol='HTTP'
                            )

                            self.service_registry[service_name.lower()] = node_name

                except Exception as e:
                    logger.debug("skipping entry: %s", e)
    def parse_inter_service_calls(self, code_dir: str, languages: List[str] = ['python', 'javascript', 'typescript', 'java', 'go']) -> None:
        """Scan code for HTTP/RPC calls between services."""

        call_patterns = {
            'python': {
                'http': [
                    r'requests\.(get|post|put|delete|patch)\s*\(\s*[\'"]([^"\']+)[\'"]',
                    r'httpx\.(get|post|put|delete|patch)\s*\(\s*[\'"]([^"\']+)[\'"]',
                    r'aiohttp\.ClientSession\s*\(\s*\)\.(get|post|put|delete)\s*\(\s*[\'"]([^"\']+)[\'"]',
                    r'async with\s+aiohttp\.ClientSession\s*\(\s*\)\s+as\s+session:\s+async\s+with\s+session\.(get|post)\s*\(\s*[\'"]([^"\']+)[\'"]',
                ],
                'grpc': [
                    r'stub\.([A-Za-z_][A-Za-z0-9_]*)\s*\(\s*',
                    r'grpc_client\.([A-Za-z_][A-Za-z0-9_]*)',
                ]
            },
            'javascript': {
                'http': [
                    r'axios\.(get|post|put|delete|patch)\s*\(\s*[\'"]([^"\']+)[\'"]',
                    r'fetch\s*\(\s*[\'"]([^"\']+)[\'"]',
                    r'request\s*\(\s*\{\s*url:\s*[\'"]([^"\']+)[\'"]',
                ],
                'grpc': [
                    r'client\.([A-Za-z_][A-Za-z0-9_]*)\s*\(\s*',
                ]
            },
            'typescript': {
                'http': [
                    r'axios\.(get|post|put|delete|patch)\s*\(\s*[\'"]([^"\']+)[\'"]',
                    r'fetch\s*\(\s*[\'"]([^"\']+)[\'"]',
                    r'HttpService\.(get|post|put|delete)',
                ]
            },
            'java': {
                'http': [
                    r'RestTemplate\s*\.\s*(getForObject|postForObject|exchange)\s*\(\s*[\'"]([^"\']+)[\'"]',
                    r'WebClient\s*\.\s*(get|post|put|delete)\s*\(\s*[\'"]([^"\']+)[\'"]',
                    r'@FeignClient\s*\(\s*name\s*=\s*[\'"]([^"\']+)[\'"]',
                ],
                'grpc': [
                    r'stub\.([A-Za-z_][A-Za-z0-9_]*)\s*\(',
                ]
            },
            'go': {
                'http': [
                    r'http\.(Get|Post|Put|Delete|Patch)\s*\(\s*[\'"]([^"\']+)[\'"]',
                    r'http\.Client\s*\{\}\.(Do)\s*\(\s*&http\.Request\s*\{.*URL:\s*[\'"]([^"\']+)[\'"]',
                ],
                'grpc': [
                    r'client\.([A-Za-z_][A-Za-z0-9_]*)\s*\(',
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

                    # Find HTTP calls
                    for pattern in call_patterns.get(lang, {}).get('http', []):
                        for match in re.finditer(pattern, content):
                            method = match.group(1) if match.lastindex else 'GET'
                            url = match.group(2) if match.lastindex and len(match.groups()) > 1 else match.group(0)
                            line_num = content[:match.start()].count('\n') + 1

                            # Extract service name from URL if possible
                            target_service = self._extract_service_from_url(url)

                            call_node = f"api_call_{os.path.basename(file_path)}_{match.start()}"

                            self.nodes[call_node] = MicroserviceNode(
                                name=call_node,
                                kind='API_CALL',
                                file_path=file_path,
                                line_number=line_num,
                                target_service=target_service,
                                endpoint=url,
                                protocol='HTTP',
                                configs={'method': method.upper()}
                            )

                            # Link to source service (the file's service)
                            source_service = self._find_source_service(file_path, content)
                            if source_service:
                                self.edges.append((
                                    source_service,
                                    call_node,
                                    {'edge_type': 'calls', 'file': file_path}
                                ))

                            # Link to target service if identified
                            if target_service and target_service in self.service_registry:
                                self.edges.append((
                                    call_node,
                                    self.service_registry[target_service],
                                    {'edge_type': 'targets', 'file': file_path}
                                ))

                except Exception as e:
                    logger.debug("skipping entry: %s", e)
    def _extract_service_from_url(self, url: str) -> Optional[str]:
        """Extract service name from URL."""
        # Patterns like http://user-service:8080/api/users
        service_patterns = [
            r'http[s]?://([a-zA-Z0-9\-]+)(?::\d+)?/',
            r'http[s]?://([a-zA-Z0-9\-]+)\.([a-zA-Z0-9\-]+)\./',  # Kubernetes DNS
        ]

        for pattern in service_patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1).lower()

        return None

    def _find_source_service(self, file_path: str, content: str) -> Optional[str]:
        """Find which service this file belongs to."""
        # Check for SERVICE_NAME constants
        match = re.search(r'SERVICE_NAME\s*=\s*[\'"]([^"\']+)[\'"]', content)
        if match:
            service_name = match.group(1).lower()
            if service_name in self.service_registry:
                return self.service_registry[service_name]

        # Check filename for service name
        basename = os.path.basename(file_path).lower()
        for service_name, node_name in self.service_registry.items():
            if service_name in basename:
                return node_name

        return None

    def parse_circuit_breakers(self, code_dir: str, languages: List[str] = ['python', 'javascript', 'typescript', 'java', 'go']) -> None:
        """Scan code for circuit breaker patterns."""

        cb_patterns = {
            'python': [
                r'@circuit_breaker\s*\(\s*failure_threshold\s*=\s*(\d+)',
                r'CircuitBreaker\s*\(\s*failure_threshold\s*=\s*(\d+)',
                r'pybreaker\.CircuitBreaker\s*\(\s*name\s*=\s*[\'"]([^"\']+)[\'"]',
            ],
            'javascript': [
                r'new\s+CircuitBreaker\s*\(\s*\{\s*failureThreshold:\s*(\d+)',
                r'opossum\s*\(\s*\{\s*timeout:\s*(\d+)',
            ],
            'java': [
                r'@CircuitBreaker\s*\(\s*name\s*=\s*[\'"]([^"\']+)[\'"]',
                r'@HystrixCommand\s*\(\s*commandProperties\s*=\s*\{',
                r'resilience4j\.circuitbreaker\.CircuitBreaker',
            ],
            'go': [
                r'gobreaker\.NewCircuitBreaker\s*\(\s*gobreaker\.Settings\s*\{',
                r'Name:\s*[\'"]([^"\']+)[\'"]',
            ]
        }

        for root, dirs, files in os.walk(code_dir):
            dirs[:] = [d for d in dirs if d not in {'node_modules', 'vendor', '.git', '__pycache__'}]

            for file in files:
                file_path = os.path.join(root, file)
                ext = os.path.splitext(file)[1].lower()

                lang_map = {'.py': 'python', '.js': 'javascript', '.ts': 'javascript', '.java': 'java', '.go': 'go'}
                lang = lang_map.get(ext)

                if lang not in languages:
                    continue

                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()

                    for pattern in cb_patterns.get(lang, []):
                        for match in re.finditer(pattern, content):
                            cb_name = match.group(1) if match.lastindex else f"cb_{match.start()}"
                            threshold = match.group(1) if match.lastindex else '5'
                            line_num = content[:match.start()].count('\n') + 1

                            cb_node = f"circuit_breaker_{cb_name}_{match.start()}"

                            self.nodes[cb_node] = MicroserviceNode(
                                name=cb_name,
                                kind='CIRCUIT_BREAKER',
                                file_path=file_path,
                                line_number=line_num,
                                configs={
                                    'failure_threshold': threshold,
                                    'type': 'circuit_breaker'
                                }
                            )

                except Exception as e:
                    logger.debug("skipping entry: %s", e)
    def parse_retry_configs(self, code_dir: str) -> None:
        """Scan code for retry and timeout configurations."""

        retry_patterns = [
            r'@retry\s*\(\s*stops?\s*=\s*stop_after_attempt\s*\(\s*(\d+)\)',
            r'retry\s*\(\s*attempts\s*=\s*(\d+)',
            r'RetryPolicy\s*\(\s*maxAttempts\s*=\s*(\d+)',
            r'timeout\s*=\s*(\d+)',
            r'connectTimeout\s*:\s*(\d+)',
            r'readTimeout\s*:\s*(\d+)',
        ]

        for root, dirs, files in os.walk(code_dir):
            dirs[:] = [d for d in dirs if d not in {'node_modules', 'vendor', '.git', '__pycache__'}]

            for file in files:
                file_path = os.path.join(root, file)
                ext = os.path.splitext(file)[1].lower()

                if ext not in ['.py', '.js', '.ts', '.java', '.go']:
                    continue

                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()

                    for pattern in retry_patterns:
                        for match in re.finditer(pattern, content):
                            value = match.group(1)
                            line_num = content[:match.start()].count('\n') + 1

                            retry_node = f"retry_config_{os.path.basename(file_path)}_{match.start()}"

                            self.nodes[retry_node] = MicroserviceNode(
                                name=retry_node,
                                kind='RETRY_CONFIG',
                                file_path=file_path,
                                line_number=line_num,
                                configs={
                                    'value': value,
                                    'type': 'retry/timeout'
                                }
                            )

                except Exception as e:
                    logger.debug("skipping entry: %s", e)
    def parse_distributed_tracing(self, code_dir: str) -> None:
        """Scan code for distributed tracing headers propagation."""

        tracing_patterns = [
            r'X-B3-TraceId',
            r'X-B3-SpanId',
            r'X-B3-ParentSpanId',
            r'traceparent',
            r'X-Cloud-Trace-Context',
            r'X-Amzn-Trace-Id',
            r'propagate\s*\(\s*[\'"]traceparent[\'"]',
            r'TracingMiddleware',
            r'opentelemetry',
            r'jaeger',
            r'zipkin',
        ]

        for root, dirs, files in os.walk(code_dir):
            dirs[:] = [d for d in dirs if d not in {'node_modules', 'vendor', '.git', '__pycache__'}]

            for file in files:
                file_path = os.path.join(root, file)

                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()

                    for pattern in tracing_patterns:
                        if re.search(pattern, content, re.IGNORECASE):
                            line_num = content.count('\n')  # Approximate

                            trace_node = f"tracing_{os.path.basename(file_path)}"

                            if trace_node not in self.nodes:
                                self.nodes[trace_node] = MicroserviceNode(
                                    name=trace_node,
                                    kind='TRACING',
                                    file_path=file_path,
                                    line_number=line_num,
                                    configs={
                                        'pattern': pattern,
                                        'type': 'distributed_tracing'
                                    }
                                )

                except Exception as e:
                    logger.debug("skipping entry: %s", e)
    def build_graph(self) -> nx.DiGraph:
        """Build NetworkX graph from parsed microservice data."""
        G = nx.DiGraph()

        # Add nodes
        for name, node in self.nodes.items():
            G.add_node(
                name,
                kind=node.kind,
                file=node.file_path,
                line=node.line_number,
                target_service=node.target_service,
                endpoint=node.endpoint,
                protocol=node.protocol,
                configs=node.configs,
                node_type='microservice'
            )

        # Add edges
        for source, target, attrs in self.edges:
            if source in G.nodes and target in G.nodes:
                G.add_edge(source, target, **attrs)

        # Build service-to-service call graph
        self._build_service_graph(G)

        return G

    def _build_service_graph(self, G: nx.DiGraph) -> None:
        """Build high-level service-to-service call graph."""
        services = [n for n, node in self.nodes.items() if node.kind == 'SERVICE']
        api_calls = [(n, node) for n, node in self.nodes.items() if node.kind == 'API_CALL']

        for call_name, call_node in api_calls:
            if call_node.target_service:
                target_lower = call_node.target_service.lower()
                for svc_name in services:
                    svc_lower = svc_name.replace('service_', '').lower()
                    if target_lower == svc_lower or target_lower in svc_lower:
                        # Find source service
                        for edge in G.in_edges(call_name):
                            source_svc = edge[0]
                            if G.nodes[source_svc].get('kind') == 'SERVICE':
                                G.add_edge(
                                    source_svc,
                                    svc_name,
                                    edge_type='calls_service',
                                    via=call_name,
                                    endpoint=call_node.endpoint
                                )


def parse_microservices(directory: str) -> nx.DiGraph:
    """Main entry point for microservice tracing."""
    tracer = MicroserviceTracer()

    # Parse in order
    tracer.parse_service_definitions(directory)
    tracer.parse_inter_service_calls(directory)
    tracer.parse_circuit_breakers(directory)
    tracer.parse_retry_configs(directory)
    tracer.parse_distributed_tracing(directory)

    return tracer.build_graph()
