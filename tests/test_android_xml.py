"""Test Android XML extraction."""
from pathlib import Path
import pytest

from graphify.extractors.android_xml import (
    extract_android_xml,
    _parse_manifest,
    _parse_layout,
    _parse_values_resources,
)


FIXTURES_DIR = Path(__file__).parent / "fixtures" / "android"


class TestAndroidManifestExtraction:
    """Test AndroidManifest.xml parsing."""

    def test_parse_manifest_components(self):
        """Test that manifest components are extracted correctly."""
        manifest_path = FIXTURES_DIR / "AndroidManifest.xml"
        source = manifest_path.read_bytes()
        
        result = _parse_manifest(manifest_path, source)
        
        assert "nodes" in result
        assert "edges" in result
        
        # Check for expected node types
        node_types = {node["type"] for node in result["nodes"]}
        assert "android_manifest" in node_types
        assert "android_application" in node_types
        assert "android_activity" in node_types
        assert "android_service" in node_types
        assert "android_broadcast_receiver" in node_types
        assert "android_content_provider" in node_types
        assert "android_permission" in node_types
        
        # Check for specific components
        node_names = {node["name"] for node in result["nodes"]}
        assert "com.example.myapp.MainActivity" in node_names
        assert "com.example.myapp.ui.ProfileActivity" in node_names
        assert "com.example.myapp.services.SyncService" in node_names
        assert "com.example.myapp.receivers.NetworkChangeReceiver" in node_names
        
        # Check permissions
        assert "android.permission.INTERNET" in node_names
        assert "android.permission.CAMERA" in node_names
        
        # Check intent actions
        action_names = {node["name"] for node in result["nodes"] if node["type"] == "android_intent_action"}
        assert "android.intent.action.MAIN" in action_names
        assert "android.intent.category.LAUNCHER" in action_names
        assert "android.net.conn.CONNECTIVITY_CHANGE" in action_names

    def test_parse_manifest_edges(self):
        """Test that manifest edges are created correctly."""
        manifest_path = FIXTURES_DIR / "AndroidManifest.xml"
        source = manifest_path.read_bytes()
        
        result = _parse_manifest(manifest_path, source)
        
        relations = {edge["relation"] for edge in result["edges"]}
        assert "declares" in relations
        assert "requires" in relations
        assert "handles" in relations
        
        # Check edge count is reasonable
        assert len(result["edges"]) >= 10


class TestLayoutExtraction:
    """Test layout XML parsing."""

    def test_parse_layout_views(self):
        """Test that layout views with IDs are extracted."""
        layout_path = FIXTURES_DIR / "activity_main.xml"
        source = layout_path.read_bytes()
        
        result = _parse_layout(layout_path, source)
        
        assert "nodes" in result
        assert "edges" in result
        
        # Check for layout root node
        node_types = {node["type"] for node in result["nodes"]}
        assert "android_layout" in node_types
        
        # Check for view nodes
        view_nodes = [n for n in result["nodes"] if n["type"] == "android_view"]
        assert len(view_nodes) >= 4  # toolbar, title_text, submit_button, profile_image
        
        # Check specific view IDs
        view_names = {node["name"] for node in view_nodes}
        assert "toolbar" in view_names
        assert "title_text" in view_names
        assert "submit_button" in view_names
        assert "profile_image" in view_names
        assert "main_container" in view_names

    def test_parse_layout_hierarchy(self):
        """Test that layout hierarchy edges are created."""
        layout_path = FIXTURES_DIR / "activity_main.xml"
        source = layout_path.read_bytes()
        
        result = _parse_layout(layout_path, source)
        
        # Check for contains relations
        contains_edges = [e for e in result["edges"] if e["relation"] == "contains"]
        assert len(contains_edges) >= 3


class TestValuesResourceExtraction:
    """Test values XML parsing."""

    def test_parse_strings_resources(self):
        """Test that string resources are extracted."""
        strings_path = FIXTURES_DIR / "strings.xml"
        source = strings_path.read_bytes()
        
        result = _parse_values_resources(strings_path, source)
        
        assert "nodes" in result
        assert "edges" in result
        
        # Check for string resource nodes
        string_nodes = [n for n in result["nodes"] if n["type"] == "android_string_resource"]
        assert len(string_nodes) >= 6
        
        # Check specific string names
        string_names = {node["name"] for node in string_nodes}
        assert "app_name" in string_names
        assert "welcome_message" in string_names
        assert "submit" in string_names
        assert "profile_image_desc" in string_names

    def test_parse_strings_metadata(self):
        """Test that string values are stored in metadata."""
        strings_path = FIXTURES_DIR / "strings.xml"
        source = strings_path.read_bytes()
        
        result = _parse_values_resources(strings_path, source)
        
        string_nodes = {n["name"]: n for n in result["nodes"] if n["type"] == "android_string_resource"}
        
        assert "Welcome to MyApp!" in string_nodes["welcome_message"]["metadata"]["value"]
        assert "MyApp" in string_nodes["app_name"]["metadata"]["value"]


class TestMainExtractorDispatch:
    """Test the main extract_android_xml dispatcher."""

    def test_dispatch_manifest(self):
        """Test that AndroidManifest.xml is routed correctly."""
        manifest_path = FIXTURES_DIR / "AndroidManifest.xml"
        
        result = extract_android_xml(manifest_path)
        
        assert len(result["nodes"]) > 0
        assert any(n["type"] == "android_manifest" for n in result["nodes"])

    def test_dispatch_layout(self):
        """Test that layout files are routed correctly."""
        layout_path = FIXTURES_DIR / "activity_main.xml"
        
        result = extract_android_xml(layout_path)
        
        assert len(result["nodes"]) > 0
        assert any(n["type"] == "android_layout" for n in result["nodes"])

    def test_dispatch_values(self):
        """Test that values files are routed correctly."""
        strings_path = FIXTURES_DIR / "strings.xml"
        
        result = extract_android_xml(strings_path)
        
        assert len(result["nodes"]) > 0
        assert any(n["type"] == "android_string_resource" for n in result["nodes"])

    def test_handles_missing_file(self):
        """Test that missing files return empty result."""
        fake_path = FIXTURES_DIR / "nonexistent.xml"
        
        result = extract_android_xml(fake_path)
        
        assert result == {"nodes": [], "edges": []}

    def test_handles_invalid_xml(self, tmp_path):
        """Test that invalid XML returns empty result."""
        invalid_xml = tmp_path / "invalid.xml"
        invalid_xml.write_text("<invalid><xml>")
        
        result = extract_android_xml(invalid_xml)
        
        assert result == {"nodes": [], "edges": []}


class TestNodeIDGeneration:
    """Test node ID uniqueness and consistency."""

    def test_unique_ids_for_different_components(self):
        """Test that different components get unique IDs."""
        manifest_path = FIXTURES_DIR / "AndroidManifest.xml"
        source = manifest_path.read_bytes()
        
        result = _parse_manifest(manifest_path, source)
        
        node_ids = [node["id"] for node in result["nodes"]]
        assert len(node_ids) == len(set(node_ids)), "Node IDs should be unique"

    def test_consistent_ids_across_calls(self):
        """Test that same input produces consistent IDs."""
        manifest_path = FIXTURES_DIR / "AndroidManifest.xml"
        source = manifest_path.read_bytes()
        
        result1 = _parse_manifest(manifest_path, source)
        result2 = _parse_manifest(manifest_path, source)
        
        ids1 = sorted([node["id"] for node in result1["nodes"]])
        ids2 = sorted([node["id"] for node in result2["nodes"]])
        
        assert ids1 == ids2
