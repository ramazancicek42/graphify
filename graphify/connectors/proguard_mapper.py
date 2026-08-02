"""
ProGuard/R8 Obfuscation Map Parser for Graphify.
Parses mapping files to link obfuscated names back to original source code.
"""
import re
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass
from collections import defaultdict

@dataclass
class MappingEntry:
    original_name: str
    obfuscated_name: str
    file_path: Optional[str]
    line_numbers: Dict[int, int]  # original -> obfuscated
    type: str  # class, method, field

@dataclass
class CrashFrame:
    obfuscated_class: str
    obfuscated_method: str
    obfuscated_line: int
    original_class: Optional[str]
    original_method: Optional[str]
    original_line: Optional[int]

class ProGuardMapParser:
    """Parses ProGuard/R8 mapping.txt files."""

    def __init__(self):
        self.entries: Dict[str, MappingEntry] = {}
        self.class_mappings: Dict[str, str] = {}  # obfuscated -> original
        self.method_mappings: Dict[str, Dict[str, str]] = defaultdict(dict)
        self.field_mappings: Dict[str, Dict[str, str]] = defaultdict(dict)
        self.line_mappings: Dict[str, Dict[int, int]] = defaultdict(dict)

    def parse_mapping_file(self, content: str) -> None:
        """Parse ProGuard mapping.txt content."""
        current_class = None
        current_original_class = None

        lines = content.split('\n')

        for line in lines:
            if not line.strip():
                continue

            # Class mapping: com.example.MyClass -> a.b.c:
            class_match = re.match(r'^(com\.[^\s]+)\s+->\s+([a-z0-9_\.]+):\s*$', line)
            if class_match:
                original = class_match.group(1)
                obfuscated = class_match.group(2)
                current_original_class = original
                current_class = obfuscated

                self.class_mappings[obfuscated] = original
                self.entries[original] = MappingEntry(
                    original_name=original,
                    obfuscated_name=obfuscated,
                    file_path=None,
                    line_numbers={},
                    type="class"
                )
                continue

            if not current_class:
                continue

            # Method mapping: int getValue() -> a
            method_match = re.match(r'^\s+(\d+:\d+:)?([^\s]+)\s+([^\(]+)\(([^)]*)\)\s+->\s+([a-z0-9_]+):?(\d+:\d+)?', line)
            if method_match:
                line_info = method_match.group(1)
                return_type = method_match.group(2)
                method_name = method_match.group(3)
                params = method_match.group(4)
                obfuscated_name = method_match.group(5)

                full_method = f"{current_original_class}.{method_name}({params})"
                obfuscated_full = f"{current_class}.{obfuscated_name}"

                self.method_mappings[current_class][obfuscated_name] = full_method
                continue

            # Field mapping: int value -> a
            field_match = re.match(r'^\s+(\d+:\d+:)?([^\s]+)\s+([^\s]+)\s+->\s+([a-z0-9_]+):?', line)
            if field_match:
                field_type = field_match.group(2)
                field_name = field_match.group(3)
                obfuscated_name = field_match.group(4)

                self.field_mappings[current_class][obfuscated_name] = f"{current_original_class}.{field_name}"
                continue

            # Line number mapping: 15:16 -> 42
            line_match = re.match(r'^\s+(\d+):(\d+)\s+->\s+(\d+):?(\d+)?', line)
            if line_match:
                original_line = int(line_match.group(1))
                obfuscated_line = int(line_match.group(3))

                if current_class not in self.line_mappings:
                    self.line_mappings[current_class] = {}
                self.line_mappings[current_class][obfuscated_line] = original_line

    def deobfuscate_crash(self, stack_trace: str) -> List[CrashFrame]:
        """Deobfuscate a crash stack trace."""
        frames = []

        # Parse stack trace lines
        pattern = r'at\s+([a-z0-9_\.]+)\.([a-z0-9_]+)\(([^:]+):(\d+)\)'
        matches = re.findall(pattern, stack_trace)

        for obfuscated_class, obfuscated_method, file_name, line_str in matches:
            line_num = int(line_str)

            original_class = self.class_mappings.get(obfuscated_class)
            original_method = None
            original_line = None

            # Try to find method mapping
            if obfuscated_class in self.method_mappings:
                method_key = obfuscated_method
                if method_key in self.method_mappings[obfuscated_class]:
                    original_method = self.method_mappings[obfuscated_class][method_key]

            # Try to find line mapping
            if obfuscated_class in self.line_mappings:
                original_line = self.line_mappings[obfuscated_class].get(line_num)

            frames.append(CrashFrame(
                obfuscated_class=obfuscated_class,
                obfuscated_method=obfuscated_method,
                obfuscated_line=line_num,
                original_class=original_class,
                original_method=original_method,
                original_line=original_line
            ))

        return frames

    def get_original_name(self, obfuscated_name: str) -> Optional[str]:
        """Get original name for an obfuscated identifier."""
        # Check class mappings
        if obfuscated_name in self.class_mappings:
            return self.class_mappings[obfuscated_name]

        # Check method/field mappings
        parts = obfuscated_name.rsplit('.', 1)
        if len(parts) == 2:
            class_part, member_part = parts
            if class_part in self.method_mappings:
                if member_part in self.method_mappings[class_part]:
                    return self.method_mappings[class_part][member_part]
            if class_part in self.field_mappings:
                if member_part in self.field_mappings[class_part]:
                    return self.field_mappings[class_part][member_part]

        return None

    def get_summary(self) -> str:
        """Generate summary of mapping statistics."""
        total_classes = len(self.class_mappings)
        total_methods = sum(len(m) for m in self.method_mappings.values())
        total_fields = sum(len(f) for f in self.field_mappings.values())
        total_lines = sum(len(l) for l in self.line_mappings.values())

        return f"""ProGuard Mapping Summary:
- Classes mapped: {total_classes}
- Methods mapped: {total_methods}
- Fields mapped: {total_fields}
- Line numbers mapped: {total_lines}
"""


class ObfuscationGraphIntegrator:
    """Integrates ProGuard mappings with Graphify graph."""

    def __init__(self, parser: ProGuardMapParser):
        self.parser = parser

    def enrich_graph_nodes(self, nodes: List[Dict]) -> List[Dict]:
        """Add original names to obfuscated node references."""
        enriched = []

        for node in nodes:
            name = node.get('name', '')
            original = self.parser.get_original_name(name)

            if original:
                node['original_name'] = original
                node['is_obfuscated'] = True

            enriched.append(node)

        return enriched

    def link_crash_to_graph(self, crash_frames: List[CrashFrame], graph_nodes: List[Dict]) -> List[Dict]:
        """Link crash frames to graph nodes."""
        linked = []

        for frame in crash_frames:
            if frame.original_class:
                # Find matching node in graph
                for node in graph_nodes:
                    if frame.original_class in node.get('name', '') or frame.original_class in node.get('path', ''):
                        linked.append({
                            'crash_frame': frame,
                            'graph_node': node,
                            'confidence': 'high' if frame.original_line else 'medium'
                        })
                        break

        return linked
