"""
Resource ID Conflict Detector for Graphify.
Detects duplicate resource names, unused resources, and ID conflicts in Android projects.
"""
import re
import os
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass
from collections import defaultdict
from xml.etree import ElementTree as ET

@dataclass
class ResourceConflict:
    type: str  # duplicate, unused, missing, conflicting_id
    resource_type: str  # string, color, drawable, layout, etc.
    name: str
    files: List[str]
    severity: str  # error, warning, info
    suggestion: str

@dataclass
class ResourceUsage:
    resource_type: str
    name: str
    defined_in: str
    used_in: List[str]
    reference_count: int

class ResourceConflictDetector:
    """Detects resource conflicts and issues in Android projects."""

    def __init__(self):
        self.conflicts: List[ResourceConflict] = []
        self.resources: Dict[str, Dict[str, List[str]]] = defaultdict(lambda: defaultdict(list))
        self.usages: Dict[str, ResourceUsage] = {}

    def scan_resources(self, res_dir: str) -> None:
        """Scan all resource XML files in the res/ directory."""
        if not os.path.exists(res_dir):
            return

        # Scan each resource type directory
        for type_dir in os.listdir(res_dir):
            type_path = os.path.join(res_dir, type_dir)

            if not os.path.isdir(type_path):
                continue

            # Determine resource type from directory name
            res_type = self._get_resource_type(type_dir)

            # Parse XML files in this directory
            for file_name in os.listdir(type_path):
                if not file_name.endswith('.xml'):
                    continue

                file_path = os.path.join(type_path, file_name)
                self._parse_resource_file(file_path, res_type)

    def _get_resource_type(self, dir_name: str) -> str:
        """Map directory name to resource type."""
        mapping = {
            'values': 'values',  # strings, colors, dims, etc.
            'layout': 'layout',
            'drawable': 'drawable',
            'mipmap': 'mipmap',
            'anim': 'anim',
            'menu': 'menu',
            'raw': 'raw',
            'xml': 'xml',
            'font': 'font'
        }
        return mapping.get(dir_name.split('-')[0], 'unknown')

    def _parse_resource_file(self, file_path: str, res_type: str) -> None:
        """Parse a resource XML file and extract resource names."""
        try:
            tree = ET.parse(file_path)
            root = tree.getroot()

            # Handle values resources (strings, colors, dims, styles, etc.)
            if res_type == 'values':
                self._parse_values_resource(root, file_path)
            # Handle layout resources
            elif res_type == 'layout':
                self._parse_layout_resource(root, file_path)
            # Handle drawable and other resources
            else:
                # Use filename as resource name
                name = os.path.basename(file_path).replace('.xml', '')
                self.resources[res_type][name].append(file_path)

        except ET.ParseError as e:
            self.conflicts.append(ResourceConflict(
                type="parse_error",
                resource_type=res_type,
                name=os.path.basename(file_path),
                files=[file_path],
                severity="error",
                suggestion=f"Fix XML syntax error: {str(e)}"
            ))

    def _parse_values_resource(self, root: ET.Element, file_path: str) -> None:
        """Parse values XML (strings.xml, colors.xml, etc.)."""
        for child in root:
            tag = child.tag
            name = child.get('name')

            if name:
                # Specific resource types within values
                if tag == 'string':
                    self.resources['string'][name].append(file_path)
                elif tag == 'color':
                    self.resources['color'][name].append(file_path)
                elif tag == 'dimen':
                    self.resources['dimen'][name].append(file_path)
                elif tag == 'style':
                    self.resources['style'][name].append(file_path)
                elif tag == 'array':
                    self.resources['array'][name].append(file_path)
                elif tag == 'integer':
                    self.resources['integer'][name].append(file_path)
                elif tag == 'bool':
                    self.resources['bool'][name].append(file_path)

    def _parse_layout_resource(self, root: ET.Element, file_path: str) -> None:
        """Parse layout XML and extract view IDs."""
        file_name = os.path.basename(file_path).replace('.xml', '')
        self.resources['layout'][file_name].append(file_path)

        # Extract all android:id attributes
        for elem in root.iter():
            id_attr = elem.get('{http://schemas.android.com/apk/res/android}id')
            if id_attr and id_attr.startswith('@+id/'):
                view_id = id_attr.replace('@+id/', '')
                self.resources['id'][view_id].append(file_path)

    def detect_conflicts(self) -> List[ResourceConflict]:
        """Analyze collected resources for conflicts."""
        self.conflicts = []

        # Check for duplicates
        for res_type, names in self.resources.items():
            for name, files in names.items():
                if len(files) > 1:
                    # Check if it's a legitimate qualifier-based duplicate
                    if not self._is_qualified_duplicate(files):
                        self.conflicts.append(ResourceConflict(
                            type="duplicate",
                            resource_type=res_type,
                            name=name,
                            files=files,
                            severity="error",
                            suggestion=f"Remove duplicate {res_type} '{name}' or use proper qualifiers (e.g., values-en, layout-land)"
                        ))

        # Check for naming conflicts with Android framework
        android_reserved = ['id', 'text', 'button', 'image', 'list', 'content']
        for res_type, names in self.resources.items():
            for name in names.keys():
                if name.lower() in android_reserved:
                    self.conflicts.append(ResourceConflict(
                        type="conflicting_id",
                        resource_type=res_type,
                        name=name,
                        files=names[name],
                        severity="warning",
                        suggestion=f"Rename '{name}' to avoid conflict with Android framework identifiers"
                    ))

        return self.conflicts

    def _is_qualified_duplicate(self, files: List[str]) -> bool:
        """Check if duplicates are due to different qualifiers (legitimate)."""
        qualifiers = set()
        for f in files:
            # Extract qualifier from path (e.g., values-v21, layout-land)
            parts = os.path.dirname(f).split('-')
            if len(parts) > 1:
                qualifier = parts[-1].split('/')[0]
                qualifiers.add(qualifier)
            else:
                qualifiers.add('default')

        # If all qualifiers are different, it's legitimate
        return len(qualifiers) == len(files)

    def scan_code_usage(self, source_files: Dict[str, str]) -> None:
        """Scan source code for resource references."""
        usage_counts: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        usage_locations: Dict[str, Dict[str, List[str]]] = defaultdict(lambda: defaultdict(list))

        for file_path, content in source_files.items():
            # Find R.type.name references
            pattern = r'R\.(\w+)\.(\w+)'
            matches = re.findall(pattern, content)

            for res_type, name in matches:
                usage_counts[res_type][name] += 1
                usage_locations[res_type][name].append(file_path)

        # Build usage records
        for res_type, names in self.resources.items():
            for name, files in names.items():
                count = usage_counts.get(res_type, {}).get(name, 0)

                self.usages[f"{res_type}:{name}"] = ResourceUsage(
                    resource_type=res_type,
                    name=name,
                    defined_in=files[0] if files else '',
                    used_in=usage_locations.get(res_type, {}).get(name, []),
                    reference_count=count
                )

    def find_unused_resources(self) -> List[ResourceConflict]:
        """Find resources that are never referenced in code."""
        unused = []

        for key, usage in self.usages.items():
            if usage.reference_count == 0:
                # Skip certain resource types that might be used dynamically
                if usage.resource_type in ['raw', 'xml', 'anim']:
                    continue

                unused.append(ResourceConflict(
                    type="unused",
                    resource_type=usage.resource_type,
                    name=usage.name,
                    files=[usage.defined_in],
                    severity="warning",
                    suggestion=f"Consider removing unused {usage.resource_type} '{usage.name}'"
                ))

        return unused

    def get_summary(self) -> str:
        """Generate summary of resource analysis."""
        total_resources = sum(len(names) for names in self.resources.values())
        total_conflicts = len(self.conflicts)
        errors = len([c for c in self.conflicts if c.severity == 'error'])
        warnings = len([c for c in self.conflicts if c.severity == 'warning'])

        summary = [f"""Resource Analysis Summary:
- Total resources found: {total_resources}
- Conflicts detected: {total_conflicts}
  - Errors: {errors}
  - Warnings: {warnings}
"""]

        if self.conflicts:
            summary.append("\nTop Issues:")
            for conflict in self.conflicts[:10]:
                summary.append(f"- [{conflict.severity.upper()}] {conflict.type}: {conflict.resource_type}/{conflict.name}")
                summary.append(f"  Files: {', '.join(os.path.basename(f) for f in conflict.files[:3])}")
                summary.append(f"  Fix: {conflict.suggestion}\n")

        return "\n".join(summary)
