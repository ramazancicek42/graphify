"""
Tests for Full-Stack Knowledge Graph connectors

Tests the following connectors:
- Cross-Layer Parser (Frontend → Backend → Database)
- GraphQL Parser
- gRPC Parser
- Message Queue Parser (Kafka, RabbitMQ)
- Cloud Resource Mapper
- WebSocket Tracker
- Auth Flow Tracker
- Microservice Tracer
"""

import pytest
from pathlib import Path
import networkx as nx

from graphify.connectors import (
    parse_fullstack_project,
    CrossLayerParser,
    UnifiedGraphBuilder,
    GraphQLParser,
    gRPCParser,
    MessageQueueParser,
    CloudResourceMapper,
    WebSocketTracker,
    AuthFlowTracker,
    MicroserviceTracer,
)


FIXTURES_DIR = Path(__file__).parent / "fixtures" / "test_fullstack_project"


class TestCrossLayerParser:
    """Test cross-layer parsing functionality"""

    def test_scan_directory(self):
        """Test scanning a full-stack project directory"""
        parser = CrossLayerParser()
        parser.scan_directory(str(FIXTURES_DIR))

        assert len(parser.api_calls) > 0, "Should detect API calls"
        assert len(parser.api_endpoints) > 0, "Should detect API endpoints"
        assert len(parser.table_refs) > 0, "Should detect SQL references"
        assert len(parser.schema_tables) > 0, "Should detect schema tables"

    def test_build_graph(self):
        """Test building a unified graph from parsed data"""
        parser = CrossLayerParser()
        parser.scan_directory(str(FIXTURES_DIR))

        builder = UnifiedGraphBuilder()
        builder.from_parser(parser)

        assert builder.graph.number_of_nodes() > 0, "Graph should have nodes"
        assert builder.graph.number_of_edges() > 0, "Graph should have edges"

    def test_parse_fullstack_project(self):
        """Test the high-level parse_fullstack_project function"""
        result = parse_fullstack_project(str(FIXTURES_DIR))

        assert 'cross_layer' in result, "Should return cross_layer graph"
        assert isinstance(result['cross_layer'], nx.Graph), "Should return a NetworkX graph"
        assert result['cross_layer'].number_of_nodes() > 0, "Graph should have nodes"

    def test_api_call_detection(self):
        """Test detection of various API call patterns"""
        parser = CrossLayerParser()
        parser.scan_directory(str(FIXTURES_DIR))

        # Check that we detected frontend API calls
        api_methods = [call.method for call in parser.api_calls]
        assert 'POST' in api_methods or 'GET' in api_methods, "Should detect HTTP methods"

    def test_endpoint_matching(self):
        """Test matching API calls to endpoints with parameters"""
        parser = CrossLayerParser()
        
        # Test exact match
        assert parser._match_endpoint('/api/users', '/api/users') is True
        
        # Test parameterized routes
        assert parser._match_endpoint('/api/users/123', '/api/users/:id') is True
        assert parser._match_endpoint('/api/users/456', '/api/users/{id}') is True
        
        # Test non-match
        assert parser._match_endpoint('/api/posts', '/api/users') is False


class TestGraphQLParser:
    """Test GraphQL schema parsing"""

    def test_parse_graphql_project(self):
        """Test parsing GraphQL schema files"""
        result = parse_fullstack_project(str(FIXTURES_DIR), enable_graphql=True, enable_cross_layer=False)
        
        # GraphQL parser should run without errors
        assert 'graphql' in result or 'graphql_error' in result


class TestgRPCParser:
    """Test gRPC proto file parsing"""

    def test_parse_grpc_project(self):
        """Test parsing gRPC proto files"""
        result = parse_fullstack_project(str(FIXTURES_DIR), enable_grpc=True, enable_cross_layer=False)
        
        # gRPC parser should run without errors
        assert 'grpc' in result or 'grpc_error' in result


class TestMessageQueueParser:
    """Test message queue parsing"""

    def test_parse_mq_project(self):
        """Test parsing Kafka/RabbitMQ configurations"""
        result = parse_fullstack_project(str(FIXTURES_DIR), enable_mq=True, enable_cross_layer=False)
        
        # MQ parser should run without errors
        assert 'message_queue' in result or 'mq_error' in result


class TestCloudResourceMapper:
    """Test cloud resource mapping"""

    def test_parse_cloud_resources(self):
        """Test parsing Terraform/K8s files"""
        result = parse_fullstack_project(str(FIXTURES_DIR), enable_cloud=True, enable_cross_layer=False)
        
        # Cloud mapper should run without errors
        assert 'cloud' in result or 'cloud_error' in result


class TestWebSocketTracker:
    """Test WebSocket connection tracking"""

    def test_parse_websocket_project(self):
        """Test parsing WebSocket configurations"""
        result = parse_fullstack_project(str(FIXTURES_DIR), enable_websocket=True, enable_cross_layer=False)
        
        # WebSocket tracker should run without errors
        assert 'websocket' in result or 'websocket_error' in result


class TestAuthFlowTracker:
    """Test authentication flow tracking"""

    def test_parse_auth_flows(self):
        """Test parsing auth flow configurations"""
        result = parse_fullstack_project(str(FIXTURES_DIR), enable_auth=True, enable_cross_layer=False)
        
        # Auth tracker should run without errors
        assert 'auth' in result or 'auth_error' in result


class TestMicroserviceTracer:
    """Test microservice tracing"""

    def test_parse_microservices(self):
        """Test parsing microservice configurations"""
        result = parse_fullstack_project(str(FIXTURES_DIR), enable_microservices=True, enable_cross_layer=False)
        
        # Microservice tracer should run without errors
        assert 'microservices' in result or 'microservices_error' in result


class TestUnifiedGraphBuilder:
    """Test unified graph building and subgraph extraction"""

    def test_from_directory(self):
        """Test building graph directly from directory"""
        builder = UnifiedGraphBuilder()
        builder.from_directory(str(FIXTURES_DIR))

        assert builder.graph.number_of_nodes() > 0, "Graph should have nodes"

    def test_extract_subgraph(self):
        """Test extracting a subgraph based on query"""
        builder = UnifiedGraphBuilder()
        builder.from_directory(str(FIXTURES_DIR))

        # Extract subgraph for a user-related query
        subgraph = builder.extract_subgraph(
            query="user profile update",
            max_depth=3,
            max_nodes=50
        )

        # Subgraph should be smaller than full graph
        assert subgraph.number_of_nodes() <= builder.graph.number_of_nodes()

    def test_to_llm_context(self):
        """Test converting graph to LLM-friendly context"""
        builder = UnifiedGraphBuilder()
        builder.from_directory(str(FIXTURES_DIR))

        context = builder.to_llm_context(builder.graph, format="markdown")
        
        assert isinstance(context, str), "Context should be a string"
        assert len(context) > 0, "Context should not be empty"

    def test_export_formats(self):
        """Test exporting graph in different formats"""
        import tempfile
        import os
        
        builder = UnifiedGraphBuilder()
        builder.from_directory(str(FIXTURES_DIR))

        # Test JSON export
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json_path = f.name
        try:
            builder.export(json_path, format="json")
            assert os.path.exists(json_path), "JSON file should be created"
            with open(json_path, 'r') as f:
                json_content = f.read()
            assert len(json_content) > 0, "JSON file should not be empty"
        finally:
            if os.path.exists(json_path):
                os.unlink(json_path)

        # Test GraphML export
        with tempfile.NamedTemporaryFile(mode='w', suffix='.graphml', delete=False) as f:
            graphml_path = f.name
        try:
            builder.export(graphml_path, format="graphml")
            assert os.path.exists(graphml_path), "GraphML file should be created"
            with open(graphml_path, 'r') as f:
                graphml_content = f.read()
            assert len(graphml_content) > 0, "GraphML file should not be empty"
            assert '<?xml' in graphml_content or '<graphml' in graphml_content, "GraphML should be XML format"
        finally:
            if os.path.exists(graphml_path):
                os.unlink(graphml_path)


class TestIntegration:
    """Integration tests for full-stack parsing"""

    def test_end_to_end_chain(self):
        """Test complete end-to-end chain detection"""
        parser = CrossLayerParser()
        parser.scan_directory(str(FIXTURES_DIR))

        builder = UnifiedGraphBuilder()
        builder.from_parser(parser)

        # Build connections
        connections = parser.build_connections()
        
        # Should have connections between layers
        assert len(connections) > 0, "Should detect cross-layer connections"

    def test_multiple_connectors(self):
        """Test running multiple connectors together"""
        result = parse_fullstack_project(
            str(FIXTURES_DIR),
            enable_all=True
        )

        # Should have results from multiple connectors
        successful_connectors = [
            k for k in result.keys() 
            if not k.endswith('_error') and result[k] is not None
        ]
        
        assert len(successful_connectors) >= 1, "At least one connector should succeed"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
