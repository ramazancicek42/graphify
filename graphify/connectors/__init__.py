"""
Connectors package for Full-Stack Knowledge Graph

Bu paket, Graphify'i cok katmanli full-stack projeleri tarayabilir hale getirir.

Available connectors:
- GraphQL Parser
- gRPC Parser  
- Message Queue Parser (Kafka, RabbitMQ)
- Cloud Resource Mapper (AWS, GCP, Azure)
- WebSocket Tracker
- Auth Flow Tracker
- Microservice Tracer
- Cross-Layer Parser
- Unified Graph Builder
"""

from .cross_layer_parser import (
    CrossLayerParser,
    APICall,
    APIEndpoint,
    TableReference,
    SchemaTable,
    LayerType,
    ConnectionType,
)

from .unified_graph import (
    UnifiedGraphBuilder,
    GraphNode,
    GraphEdge,
    NodeType,
)

from .graphql_parser import (
    parse_graphql_project,
    GraphQLParser,
    extract_graphql_files,
)

from .grpc_parser import (
    parse_grpc_project,
    gRPCParser,
    extract_proto_files,
)

from .mq_parser import (
    parse_mq_project,
    MessageQueueParser,
)

from .cloud_mapper import (
    parse_cloud_resources,
    CloudResourceMapper,
)

from .websocket_tracker import (
    parse_websocket_project,
    WebSocketTracker,
)

from .auth_tracker import (
    parse_auth_flows,
    AuthFlowTracker,
)

from .microservice_tracer import (
    parse_microservices,
    MicroserviceTracer,
)

# Android-specific connectors
from .ui_mapper import UIMapper
from .data_flow_tracker import DataFlowTracker
from .di_resolver import DIGraphResolver
from .manifest_analyzer import ManifestAnalyzer
from .termux_optimizer import TermuxOptimizer, enable_termux_mode

__all__ = [
    # Cross-Layer Parser
    'CrossLayerParser',
    'APICall',
    'APIEndpoint',
    'TableReference',
    'SchemaTable',
    'LayerType',
    'ConnectionType',

    # Graph Builder
    'UnifiedGraphBuilder',
    'GraphNode',
    'GraphEdge',
    'NodeType',

    # GraphQL
    'parse_graphql_project',
    'GraphQLParser',
    'extract_graphql_files',

    # gRPC
    'parse_grpc_project',
    'gRPCParser',
    'extract_proto_files',

    # Message Queues
    'parse_mq_project',
    'MessageQueueParser',

    # Cloud Resources
    'parse_cloud_resources',
    'CloudResourceMapper',

    # WebSocket
    'parse_websocket_project',
    'WebSocketTracker',

    # Auth Flows
    'parse_auth_flows',
    'AuthFlowTracker',

    # Microservices
    'parse_microservices',
    'MicroserviceTracer',
    
    # Android-Specific Connectors
    'UIMapper',
    'DataFlowTracker',
    'DIGraphResolver',
    'ManifestAnalyzer',
    'TermuxOptimizer',
    'enable_termux_mode',
]


def parse_fullstack_project(
    directory: str,
    enable_all: bool = True,
    enable_graphql: bool = False,
    enable_grpc: bool = False,
    enable_mq: bool = False,
    enable_cloud: bool = False,
    enable_websocket: bool = False,
    enable_auth: bool = False,
    enable_microservices: bool = False,
    enable_cross_layer: bool = True,
) -> dict:
    """
    Parse a full-stack project with all available connectors.
    
    Returns a dictionary of graphs by type.
    """
    import networkx as nx
    
    graphs = {}
    
    if enable_all or enable_graphql:
        try:
            graphs['graphql'] = parse_graphql_project(directory)
        except Exception as e:
            graphs['graphql_error'] = str(e)
            
    if enable_all or enable_grpc:
        try:
            graphs['grpc'] = parse_grpc_project(directory)
        except Exception as e:
            graphs['grpc_error'] = str(e)
            
    if enable_all or enable_mq:
        try:
            graphs['message_queue'] = parse_mq_project(directory)
        except Exception as e:
            graphs['mq_error'] = str(e)
            
    if enable_all or enable_cloud:
        try:
            graphs['cloud'] = parse_cloud_resources(directory)
        except Exception as e:
            graphs['cloud_error'] = str(e)
            
    if enable_all or enable_websocket:
        try:
            graphs['websocket'] = parse_websocket_project(directory)
        except Exception as e:
            graphs['websocket_error'] = str(e)
            
    if enable_all or enable_auth:
        try:
            graphs['auth'] = parse_auth_flows(directory)
        except Exception as e:
            graphs['auth_error'] = str(e)
            
    if enable_all or enable_microservices:
        try:
            graphs['microservices'] = parse_microservices(directory)
        except Exception as e:
            graphs['microservices_error'] = str(e)
            
    if enable_all or enable_cross_layer:
        try:
            parser = CrossLayerParser()
            parser.scan_directory(directory)
            builder = UnifiedGraphBuilder()
            builder.from_parser(parser)
            graphs['cross_layer'] = builder.graph
        except Exception as e:
            graphs['cross_layer_error'] = str(e)
            
    return graphs


def merge_graphs(graphs: dict) -> 'nx.Graph':
    """Merge multiple graphs into a single unified graph."""
    import networkx as nx
    
    merged = nx.Graph()
    
    for graph_type, graph in graphs.items():
        if isinstance(graph, nx.Graph):
            for node, attrs in graph.nodes(data=True):
                attrs['source_graph'] = graph_type
                merged.add_node(f"{graph_type}:{node}", **attrs)
                
            for source, target, attrs in graph.edges(data=True):
                merged.add_edge(
                    f"{graph_type}:{source}",
                    f"{graph_type}:{target}",
                    **attrs
                )
                
    return merged
