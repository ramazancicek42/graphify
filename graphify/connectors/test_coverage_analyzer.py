"""
Test Coverage & Mock Data Generator for Graphify.
Analyzes code to identify missing test scenarios and generates mock data structures.
"""
import re
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass
from enum import Enum

class CoverageGapType(Enum):
    NO_TEST_FILE = "no_test_file"
    MISSING_EDGE_CASES = "missing_edge_cases"
    UNTESTED_FUNCTION = "untested_function"
    MISSING_MOCK = "missing_mock"
    NO_ASSERTION = "no_assertion"
    ASYNC_NOT_TESTED = "async_not_tested"

@dataclass
class CoverageGap:
    type: CoverageGapType
    file_path: str
    function_name: Optional[str]
    description: str
    suggestion: str
    priority: int  # 1-5, 5 being highest

@dataclass
class MockDataStructure:
    class_name: str
    fields: Dict[str, str]
    sample_data: Dict[str, str]

class TestCoverageAnalyzer:
    """Analyzes test coverage gaps and suggests improvements."""
    
    def __init__(self):
        self.gaps: List[CoverageGap] = []
        self.mock_structures: List[MockDataStructure] = []
        
    def analyze_project(self, source_files: Dict[str, str], test_files: Dict[str, str]) -> List[CoverageGap]:
        """Compare source and test files to find coverage gaps."""
        self.gaps = []
        
        # Map test files to source files
        test_mapping = self._map_tests_to_sources(test_files)
        
        for source_path, source_content in source_files.items():
            # Check if test file exists
            if source_path not in test_mapping:
                self.gaps.append(CoverageGap(
                    type=CoverageGapType.NO_TEST_FILE,
                    file_path=source_path,
                    function_name=None,
                    description=f"No test file found for {source_path}",
                    suggestion=f"Create test file: {self._get_test_path(source_path)}",
                    priority=5
                ))
                continue
            
            # Analyze functions in source
            functions = self._extract_functions(source_content)
            tested_functions = self._extract_tested_functions(test_mapping[source_path], functions)
            
            for func in functions:
                if func not in tested_functions:
                    self.gaps.append(CoverageGap(
                        type=CoverageGapType.UNTESTED_FUNCTION,
                        file_path=source_path,
                        function_name=func,
                        description=f"Function '{func}' has no corresponding test",
                        suggestion=f"Add test case for {func}",
                        priority=4
                    ))
            
            # Check for async functions without coroutine tests
            async_funcs = self._extract_async_functions(source_content)
            for func in async_funcs:
                if not self._has_coroutine_test(test_mapping.get(source_path, ""), func):
                    self.gaps.append(CoverageGap(
                        type=CoverageGapType.ASYNC_NOT_TESTED,
                        file_path=source_path,
                        function_name=func,
                        description=f"Async function '{func}' lacks coroutine test",
                        suggestion="Use runBlockingTest or Turbine for flow testing",
                        priority=3
                    ))
        
        return self.gaps
    
    def _map_tests_to_sources(self, test_files: Dict[str, str]) -> Dict[str, str]:
        """Map test files to their corresponding source files."""
        mapping = {}
        for test_path, test_content in test_files.items():
            # Simple heuristic: test filename matches source filename
            source_path = test_path.replace("/test/", "/src/").replace("Test.kt", ".kt")
            if source_path.endswith(".kt") or source_path.endswith(".java"):
                mapping[source_path] = test_content
        return mapping
    
    def _extract_functions(self, content: str) -> List[str]:
        """Extract function names from Kotlin/Java code."""
        patterns = [
            r"fun\s+(\w+)\s*\(",  # Kotlin
            r"(?:public|private|protected)?\s*(?:static)?\s*\w+\s+(\w+)\s*\(",  # Java
            r"suspend\s+fun\s+(\w+)\s*\("  # Kotlin suspend
        ]
        functions = []
        for pattern in patterns:
            matches = re.findall(pattern, content)
            functions.extend(matches)
        return list(set(functions))
    
    def _extract_async_functions(self, content: str) -> List[str]:
        """Extract async/suspend functions."""
        patterns = [
            r"suspend\s+fun\s+(\w+)\s*\(",
            r"Flow<[^>]+>\s+(\w+)\s*\(",
            r"LiveData<[^>]+>\s+(\w+)\s*\("
        ]
        functions = []
        for pattern in patterns:
            matches = re.findall(pattern, content)
            functions.extend(matches)
        return list(set(functions))
    
    def _extract_tested_functions(self, test_content: str, functions: List[str]) -> Set[str]:
        """Find which functions are tested."""
        tested = set()
        for func in functions:
            # Check for test methods that call this function
            if re.search(rf"{func}\s*\(", test_content):
                tested.add(func)
        return tested
    
    def _has_coroutine_test(self, test_content: str, func_name: str) -> bool:
        """Check if there's a coroutine test for the function."""
        patterns = [
            r"runBlockingTest",
            r"runBlocking\s*\{",
            r"Turbine",
            rf"flow.*?{func_name}",
            rf"{func_name}.*?collect"
        ]
        return any(re.search(p, test_content) for p in patterns)
    
    def _get_test_path(self, source_path: str) -> str:
        """Generate suggested test file path."""
        filename = source_path.split("/")[-1].replace(".kt", "Test.kt").replace(".java", "Test.java")
        return f"app/src/test/java/.../{filename}"
    
    def get_summary(self) -> str:
        """Generate coverage gap summary."""
        if not self.gaps:
            return "No coverage gaps detected."
        
        summary = [f"Found {len(self.gaps)} coverage gap(s):\n"]
        high_priority = [g for g in self.gaps if g.priority >= 4]
        
        if high_priority:
            summary.append(f"HIGH PRIORITY ({len(high_priority)} gaps):")
            for gap in high_priority[:10]:  # Limit output
                summary.append(f"  - [{gap.type.value}] {gap.file_path}")
                if gap.function_name:
                    summary.append(f"    Function: {gap.function_name}")
                summary.append(f"    Fix: {gap.suggestion}\n")
        
        return "\n".join(summary)


class MockDataGenerator:
    """Generates mock data structures for testing."""
    
    def generate_mocks(self, data_classes: Dict[str, str]) -> List[MockDataStructure]:
        """Generate mock data for data classes."""
        self.mock_structures = []
        
        for class_name, class_content in data_classes.items():
            fields = self._extract_fields(class_content)
            sample_data = self._generate_sample_data(fields)
            
            self.mock_structures.append(MockDataStructure(
                class_name=class_name,
                fields=fields,
                sample_data=sample_data
            ))
        
        return self.mock_structures
    
    def _extract_fields(self, content: str) -> Dict[str, str]:
        """Extract field names and types from data class."""
        fields = {}
        
        # Kotlin data class
        kotlin_pattern = r"data\s+class\s+\w+\s*\(([^)]+)\)"
        match = re.search(kotlin_pattern, content)
        if match:
            params = match.group(1).split(",")
            for param in params:
                param = param.strip()
                if ":" in param:
                    name, type_ = param.split(":")
                    fields[name.strip()] = type_.strip()
        
        # Java class with getters/setters
        if not fields:
            java_pattern = r"private\s+(\w+)\s+(\w+)\s*;"
            matches = re.findall(java_pattern, content)
            for type_, name in matches:
                fields[name] = type_
        
        return fields
    
    def _generate_sample_data(self, fields: Dict[str, str]) -> Dict[str, str]:
        """Generate realistic sample data for fields."""
        samples = {}
        
        for field, type_ in fields.items():
            if "String" in type_:
                if "name" in field.lower():
                    samples[field] = '"John Doe"'
                elif "email" in field.lower():
                    samples[field] = '"john@example.com"'
                elif "id" in field.lower():
                    samples[field] = '"uuid-12345"'
                else:
                    samples[field] = f'"sample_{field}"'
            elif "Int" in type_ or "int" in type_:
                samples[field] = "42"
            elif "Boolean" in type_ or "boolean" in type_:
                samples[field] = "true"
            elif "List" in type_ or "Array" in type_:
                samples[field] = "[]"
            elif "Double" in type_ or "Float" in type_:
                samples[field] = "3.14"
            else:
                samples[field] = "null"
        
        return samples
    
    def to_kotlin_code(self) -> str:
        """Generate Kotlin mock helper code."""
        code_lines = ["// Auto-generated mock data helpers\n"]
        
        for mock in self.mock_structures:
            code_lines.append(f"fun createMock{mock.class_name}(")
            for field, type_ in mock.fields.items():
                default = mock.sample_data.get(field, "null")
                code_lines.append(f"    {field}: {type_} = {default},")
            code_lines.append(f"): {mock.class_name} = {mock.class_name}(")
            for field in mock.fields.keys():
                code_lines.append(f"    {field} = {field},")
            code_lines.append(")\n")
        
        return "\n".join(code_lines)
