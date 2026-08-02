"""android_xml — Android XML resource extractor for Graphify.

Extracts nodes and edges from:
- AndroidManifest.xml (activities, services, receivers, providers, permissions)
- res/layout/*.xml (UI views with android:id)
- res/values/strings.xml, colors.xml, themes.xml (resource definitions)
- Kotlin/Java code references to R.* resources

This enables end-to-end tracing from UI elements → Activities → API calls → Backend.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from graphify.ids import make_id


def _make_id(*parts: str) -> str:
    return make_id(*parts)


def _file_stem(path: Path) -> str:
    """Get file stem without extension for node ID generation."""
    if not path.name:
        return ""
    return path.with_suffix("").as_posix()


def _parse_manifest(xml_path: Path, source: bytes) -> dict[str, Any]:
    """Parse AndroidManifest.xml and extract component declarations.
    
    Returns:
        Dictionary with 'nodes' and 'edges' lists.
    """
    nodes: list[dict] = []
    edges: list[dict] = []
    
    try:
        root = ET.fromstring(source.decode('utf-8', errors='replace'))
    except ET.ParseError:
        return {"nodes": nodes, "edges": edges}
    
    # Android namespace handling
    ANDROID_NS = '{http://schemas.android.com/apk/res/android}'
    
    package = root.get('package', '')
    file_stem = _file_stem(xml_path)
    manifest_id = _make_id(file_stem)
    
    # Manifest root node
    nodes.append({
        "id": manifest_id,
        "name": f"AndroidManifest.xml",
        "type": "android_manifest",
        "file": str(xml_path),
        "line": "L1",
        "metadata": {
            "package": package,
            "source_file": str(xml_path),
        }
    })
    
    # Application node
    application = root.find('application')
    if application is not None:
        app_name = application.get(f'{ANDROID_NS}name', 'Application')
        app_id = _make_id(file_stem, 'app')
        
        nodes.append({
            "id": app_id,
            "name": app_name if app_name else "Application",
            "type": "android_application",
            "file": str(xml_path),
            "line": "L1",
            "metadata": {
                "package": package,
                "source_file": str(xml_path),
            }
        })
        
        edges.append({
            "source": manifest_id,
            "target": app_id,
            "relation": "declares",
            "context": "manifest",
            "confidence": "EXTRACTED",
            "source_file": str(xml_path),
            "weight": 1.0,
        })
        
        # Extract components
        component_types = [
            ('activity', 'android_activity'),
            ('service', 'android_service'),
            ('receiver', 'android_broadcast_receiver'),
            ('provider', 'android_content_provider'),
        ]
        
        for elem_name, node_type in component_types:
            for comp in application.findall(elem_name):
                comp_name = comp.get(f'{ANDROID_NS}name', '')
                if not comp_name:
                    continue
                
                # Resolve relative class names
                if comp_name.startswith('.'):
                    full_name = f"{package}{comp_name}"
                elif '.' not in comp_name:
                    full_name = f"{package}.{comp_name}"
                else:
                    full_name = comp_name
                
                comp_id = _make_id(file_stem, elem_name, comp_name.replace('.', '_'))
                
                nodes.append({
                    "id": comp_id,
                    "name": full_name,
                    "type": node_type,
                    "file": str(xml_path),
                    "line": "L1",
                    "metadata": {
                        "package": package,
                        "class_name": full_name,
                        "source_file": str(xml_path),
                    }
                })
                
                edges.append({
                    "source": app_id,
                    "target": comp_id,
                    "relation": "declares",
                    "context": "manifest",
                    "confidence": "EXTRACTED",
                    "source_file": str(xml_path),
                    "weight": 1.0,
                })
                
                # Extract intent-filters
                intent_filter = comp.find('intent-filter')
                if intent_filter is not None:
                    for action in intent_filter.findall('action'):
                        action_name = action.get(f'{ANDROID_NS}name', '')
                        if action_name:
                            action_id = _make_id(file_stem, elem_name, comp_name.replace('.', '_'), 'action', action_name.replace('.', '_'))
                            
                            nodes.append({
                                "id": action_id,
                                "name": action_name,
                                "type": "android_intent_action",
                                "file": str(xml_path),
                                "line": "L1",
                                "metadata": {
                                    "source_file": str(xml_path),
                                }
                            })
                            
                            edges.append({
                                "source": comp_id,
                                "target": action_id,
                                "relation": "handles",
                                "context": "intent_filter",
                                "confidence": "EXTRACTED",
                                "source_file": str(xml_path),
                                "weight": 1.0,
                            })
        
        # Extract permissions
        for perm in application.findall('uses-permission'):
            perm_name = perm.get(f'{ANDROID_NS}name', '')
            if perm_name:
                perm_id = _make_id(file_stem, 'permission', perm_name.replace('.', '_'))
                
                nodes.append({
                    "id": perm_id,
                    "name": perm_name,
                    "type": "android_permission",
                    "file": str(xml_path),
                    "line": "L1",
                    "metadata": {
                        "source_file": str(xml_path),
                    }
                })
                
                edges.append({
                    "source": app_id,
                    "target": perm_id,
                    "relation": "requires",
                    "context": "manifest",
                    "confidence": "EXTRACTED",
                    "source_file": str(xml_path),
                    "weight": 1.0,
                })
    
    # Top-level uses-permission (outside application)
    for perm in root.findall('uses-permission'):
        perm_name = perm.get(f'{ANDROID_NS}name', '')
        if perm_name:
            perm_id = _make_id(file_stem, 'permission', perm_name.replace('.', '_'))
            
            # Check if already added
            if not any(n['id'] == perm_id for n in nodes):
                nodes.append({
                    "id": perm_id,
                    "name": perm_name,
                    "type": "android_permission",
                    "file": str(xml_path),
                    "line": "L1",
                    "metadata": {
                        "source_file": str(xml_path),
                    }
                })
                
                edges.append({
                    "source": manifest_id,
                    "target": perm_id,
                    "relation": "requires",
                    "context": "manifest",
                    "confidence": "EXTRACTED",
                    "source_file": str(xml_path),
                    "weight": 1.0,
                })
    
    return {"nodes": nodes, "edges": edges}


def _parse_layout(xml_path: Path, source: bytes) -> dict[str, Any]:
    """Parse layout XML file and extract view hierarchy with IDs.
    
    Returns:
        Dictionary with 'nodes' and 'edges' lists.
    """
    nodes: list[dict] = []
    edges: list[dict] = []
    
    try:
        root = ET.fromstring(source.decode('utf-8', errors='replace'))
    except ET.ParseError:
        return {"nodes": nodes, "edges": edges}
    
    file_stem = _file_stem(xml_path)
    layout_name = xml_path.stem  # e.g., "activity_main" from "activity_main.xml"
    layout_id = _make_id(file_stem)
    
    # Root layout node
    nodes.append({
        "id": layout_id,
        "name": layout_name,
        "type": "android_layout",
        "file": str(xml_path),
        "line": "L1",
        "metadata": {
            "root_tag": root.tag,
            "source_file": str(xml_path),
        }
    })
    
    # Recursively extract views with IDs
    def walk_views(element: ET.Element, parent_id: str | None, depth: int = 0):
        view_id_attr = element.get('{http://schemas.android.com/apk/res/android}id')
        if not view_id_attr:
            view_id_attr = element.get('android:id')
        
        if view_id_attr:
            # Clean @+id/ prefix
            clean_id = view_id_attr.replace('@+id/', '').replace('@id/', '')
            view_node_id = _make_id(file_stem, 'view', clean_id)
            
            class_name = element.tag.split('}')[-1] if '}' in element.tag else element.tag
            
            nodes.append({
                "id": view_node_id,
                "name": clean_id,
                "type": "android_view",
                "file": str(xml_path),
                "line": f"L{element.sourceline}" if hasattr(element, 'sourceline') else "L1",
                "metadata": {
                    "class": class_name,
                    "android_id": view_id_attr,
                    "source_file": str(xml_path),
                }
            })
            
            if parent_id:
                edges.append({
                    "source": parent_id,
                    "target": view_node_id,
                    "relation": "contains",
                    "context": "layout_hierarchy",
                    "confidence": "EXTRACTED",
                    "source_file": str(xml_path),
                    "weight": 1.0,
                })
            
            # Use this view as parent for children
            parent_id = view_node_id
        
        # Walk children
        for child in element:
            walk_views(child, parent_id, depth + 1)
    
    walk_views(root, layout_id)
    
    return {"nodes": nodes, "edges": edges}


def _parse_values_resources(xml_path: Path, source: bytes) -> dict[str, Any]:
    """Parse values XML files (strings.xml, colors.xml, themes.xml).
    
    Returns:
        Dictionary with 'nodes' and 'edges' lists.
    """
    nodes: list[dict] = []
    edges: list[dict] = []
    
    try:
        root = ET.fromstring(source.decode('utf-8', errors='replace'))
    except ET.ParseError:
        return {"nodes": nodes, "edges": edges}
    
    file_stem = _file_stem(xml_path)
    resource_type = xml_path.parent.name if xml_path.parent.name else 'values'  # e.g., "strings", "colors"
    
    # Determine resource type from filename
    if 'strings' in xml_path.name:
        res_type = 'string'
        node_type = 'android_string_resource'
    elif 'colors' in xml_path.name:
        res_type = 'color'
        node_type = 'android_color_resource'
    elif 'themes' in xml_path.name:
        res_type = 'theme'
        node_type = 'android_theme_resource'
    elif 'dimens' in xml_path.name:
        res_type = 'dimen'
        node_type = 'android_dimen_resource'
    elif 'styles' in xml_path.name:
        res_type = 'style'
        node_type = 'android_style_resource'
    else:
        res_type = 'resource'
        node_type = 'android_resource'
    
    # Container node for the file
    container_id = _make_id(file_stem)
    nodes.append({
        "id": container_id,
        "name": xml_path.name,
        "type": f"android_{res_type}_file",
        "file": str(xml_path),
        "line": "L1",
        "metadata": {
            "source_file": str(xml_path),
        }
    })
    
    # Extract individual resources
    for element in root:
        name = element.get('name', '')
        if not name:
            continue
        
        res_id = _make_id(file_stem, res_type, name)
        value = (element.text or '').strip()[:200]  # Truncate long values
        
        nodes.append({
            "id": res_id,
            "name": name,
            "type": node_type,
            "file": str(xml_path),
            "line": f"L{element.sourceline}" if hasattr(element, 'sourceline') else "L1",
            "metadata": {
                "value": value,
                "source_file": str(xml_path),
            }
        })
        
        edges.append({
            "source": container_id,
            "target": res_id,
            "relation": "defines",
            "context": "resource_declaration",
            "confidence": "EXTRACTED",
            "source_file": str(xml_path),
            "weight": 1.0,
        })
        
        # For styles, extract parent and items
        if element.tag == 'style':
            parent = element.get('parent', '')
            if parent:
                parent_id = _make_id(file_stem, 'style', parent.replace('.', '_'))
                edges.append({
                    "source": res_id,
                    "target": parent_id,
                    "relation": "extends",
                    "context": "style_inheritance",
                    "confidence": "EXTRACTED",
                    "source_file": str(xml_path),
                    "weight": 1.0,
                })
            
            for item in element.findall('item'):
                item_name = item.get('name', '')
                if item_name:
                    item_value = (item.text or '').strip()[:200]
                    item_id = _make_id(file_stem, 'style_item', name, item_name.replace('.', '_'))
                    
                    nodes.append({
                        "id": item_id,
                        "name": item_name,
                        "type": "android_style_item",
                        "file": str(xml_path),
                        "line": f"L{item.sourceline}" if hasattr(item, 'sourceline') else "L1",
                        "metadata": {
                            "value": item_value,
                            "source_file": str(xml_path),
                        }
                    })
                    
                    edges.append({
                        "source": res_id,
                        "target": item_id,
                        "relation": "has_attribute",
                        "context": "style_definition",
                        "confidence": "EXTRACTED",
                        "source_file": str(xml_path),
                        "weight": 1.0,
                    })
    
    return {"nodes": nodes, "edges": edges}


def extract_android_xml(path: Path) -> dict[str, Any]:
    """Main entry point for Android XML extraction.
    
    Dispatches to appropriate parser based on file path and name.
    
    Args:
        path: Path to the XML file
        
    Returns:
        Dictionary with 'nodes' and 'edges' lists
    """
    try:
        source = path.read_bytes()
    except (IOError, OSError):
        return {"nodes": [], "edges": []}
    
    # Determine file type from path
    path_str = str(path)
    file_name = path.name.lower()
    
    # AndroidManifest.xml
    if file_name == 'androidmanifest.xml':
        return _parse_manifest(path, source)
    
    # Layout files
    if '/layout/' in path_str or '\\layout\\' in path_str:
        return _parse_layout(path, source)
    
    # Values resources
    if '/values/' in path_str or '\\values\\' in path_str:
        return _parse_values_resources(path, source)
    
    # Other XML files (drawables, menus, anim, etc.) - basic extraction
    try:
        root = ET.fromstring(source.decode('utf-8', errors='replace'))
        file_stem = _file_stem(path)
        
        nodes = [{
            "id": _make_id(file_stem),
            "name": path.name,
            "type": "android_xml_resource",
            "file": str(path),
            "line": "L1",
            "metadata": {
                "root_tag": root.tag,
                "source_file": str(path),
            }
        }]
        
        return {"nodes": nodes, "edges": []}
    except ET.ParseError:
        return {"nodes": [], "edges": []}
