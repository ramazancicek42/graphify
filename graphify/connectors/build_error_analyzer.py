"""
Gradle Build Error Analyzer for Graphify.
Analyzes build logs to identify errors, suggest fixes, and link them to source nodes.
"""
import re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

class ErrorType(Enum):
    DUPLICATE_CLASS = "duplicate_class"
    MIN_SDK_CONFLICT = "min_sdk_conflict"
    MISSING_DEPENDENCY = "missing_dependency"
    SYMBOL_NOT_FOUND = "symbol_not_found"
    RESOURCE_ERROR = "resource_error"
    KAPT_ERROR = "kapt_error"
    PROGUARD_ERROR = "proguard_error"
    GENERIC_ERROR = "generic_error"

@dataclass
class BuildError:
    type: ErrorType
    message: str
    file_path: Optional[str]
    line_number: Optional[int]
    suggestion: str
    related_nodes: List[str]

class GradleBuildErrorAnalyzer:
    """Analyzes Gradle build logs and connects errors to source code."""

    def __init__(self):
        self.errors: List[BuildError] = []
        self.patterns = {
            ErrorType.DUPLICATE_CLASS: re.compile(
                r"Duplicate class\s+([^\s]+)\s+found.*?ModuleA.*?ModuleB",
                re.IGNORECASE | re.DOTALL
            ),
            ErrorType.MIN_SDK_CONFLICT: re.compile(
                r"uses-sdk:minSdkVersion\s+(\d+)\s+cannot be smaller than version\s+(\d+)",
                re.IGNORECASE
            ),
            ErrorType.MISSING_DEPENDENCY: re.compile(
                r"Cannot resolve dependency\s+['\"]([^'\"]+)['\"]|error:\s+package\s+([^\s]+)\s+does not exist",
                re.IGNORECASE
            ),
            ErrorType.SYMBOL_NOT_FOUND: re.compile(
                r"error:\s+cannot find symbol\s+symbol:\s+([^\n]+)\n.*?location:\s+([^\n]+)",
                re.IGNORECASE | re.DOTALL
            ),
            ErrorType.RESOURCE_ERROR: re.compile(
                r"error:\s+resource\s+([^\s]+)\s+not found|Error retrieving parent for item",
                re.IGNORECASE
            ),
            ErrorType.KAPT_ERROR: re.compile(
                r"kapt\s+.*?\s+error:\s+([^\n]+)",
                re.IGNORECASE
            ),
            ErrorType.PROGUARD_ERROR: re.compile(
                r"Warning:\s+([^\s]+):\s+can't find referenced class\s+([^\s]+)",
                re.IGNORECASE
            )
        }

    def analyze_log(self, log_content: str) -> List[BuildError]:
        """Parse build log and extract errors."""
        self.errors = []
        lines = log_content.split('\n')

        for i, line in enumerate(lines):
            # Check specific patterns
            for error_type, pattern in self.patterns.items():
                match = pattern.search(log_content)
                if match:
                    error = self._create_error(error_type, match, lines, i)
                    if error:
                        self.errors.append(error)

            # Generic error fallback
            if 'error:' in line.lower() and not any(p.search(line) for p in self.patterns.values()):
                generic_match = re.search(r"error:\s*(.+)", line, re.IGNORECASE)
                if generic_match:
                    self.errors.append(BuildError(
                        type=ErrorType.GENERIC_ERROR,
                        message=generic_match.group(1).strip(),
                        file_path=self._extract_file_path(lines, i),
                        line_number=i + 1,
                        suggestion="Check syntax and imports.",
                        related_nodes=[]
                    ))

        return self.errors

    def _create_error(self, error_type: ErrorType, match, lines: List[str], line_idx: int) -> Optional[BuildError]:
        """Create structured error from regex match."""
        suggestions = {
            ErrorType.DUPLICATE_CLASS: "Remove duplicate dependency or exclude module.",
            ErrorType.MIN_SDK_CONFLICT: "Increase minSdkVersion or update library.",
            ErrorType.MISSING_DEPENDENCY: "Add missing dependency in build.gradle.",
            ErrorType.SYMBOL_NOT_FOUND: "Check import statements and class names.",
            ErrorType.RESOURCE_ERROR: "Verify resource exists in res/ directory.",
            ErrorType.KAPT_ERROR: "Check annotation processor configuration.",
            ErrorType.PROGUARD_ERROR: "Add ProGuard keep rule for the class."
        }

        file_path = self._extract_file_path(lines, line_idx)
        line_num = self._extract_line_number(lines, line_idx)

        return BuildError(
            type=error_type,
            message=match.group(0).strip()[:200],
            file_path=file_path,
            line_number=line_num,
            suggestion=suggestions.get(error_type, "Review error message."),
            related_nodes=[file_path] if file_path else []
        )

    def _extract_file_path(self, lines: List[str], idx: int) -> Optional[str]:
        """Extract file path from nearby lines."""
        search_range = max(0, idx - 5), min(len(lines), idx + 5)
        for i in range(*search_range):
            match = re.search(r"([a-zA-Z0-9_/\.]+\.(kt|java|xml))", lines[i])
            if match:
                return match.group(1)
        return None

    def _extract_line_number(self, lines: List[str], idx: int) -> Optional[int]:
        """Extract line number from error message."""
        for i in range(max(0, idx - 3), min(len(lines), idx + 3)):
            match = re.search(r":(\d+):", lines[i])
            if match:
                return int(match.group(1))
        return None

    def get_summary(self) -> str:
        """Generate human-readable summary."""
        if not self.errors:
            return "No build errors detected."

        summary = [f"Found {len(self.errors)} build error(s):\n"]
        for i, err in enumerate(self.errors, 1):
            summary.append(f"{i}. [{err.type.value}] {err.message}")
            if err.file_path:
                summary.append(f"   File: {err.file_path}:{err.line_number or '?'}")
            summary.append(f"   Fix: {err.suggestion}\n")

        return "\n".join(summary)
