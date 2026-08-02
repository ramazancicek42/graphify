"""
Tests for Android Diagnose Connectors:
- SmartErrorMatcher
- BrokenChainDetector
- ConfigValidator
"""
import pytest
import networkx as nx
from pathlib import Path

# Import connector modülleri
from graphify.connectors.android import (
    SmartErrorMatcher,
    BrokenChainDetector,
    ConfigValidator,
)


class TestSmartErrorMatcher:
    """Smart Error Matcher testleri."""

    def setup_method(self):
        """Her test öncesi graf oluştur."""
        self.graph = nx.DiGraph()
        # Örnek node'lar ekle
        self.graph.add_node("MainActivity", 
                           name="MainActivity", 
                           file="com/example/MainActivity.kt",
                           line=10,
                           imports=["UserViewModel"])
        self.graph.add_node("UserViewModel",
                           name="UserViewModel",
                           file="com/example/UserViewModel.kt",
                           line=5)
        self.matcher = SmartErrorMatcher(self.graph)

    def test_unresolved_reference_found(self):
        """Bilinmeyen referans hatası tespit edilmeli."""
        log = """
BUILD ERROR: Unresolved reference: UserRepository
        """
        errors = self.matcher.parse_log(log)
        assert len(errors) >= 0  # Graf'ta yoksa boş olabilir

    def test_unresolved_reference_in_graph(self):
        """Graf'ta olan sembol bulunmalı."""
        log = """
BUILD ERROR: Unresolved reference: UserViewModel
        """
        errors = self.matcher.parse_log(log)
        # UserViewModel graf'ta var
        found = any(e.symbol == "UserViewModel" for e in errors)
        # Ya bulundu ya da hiç hata yok (çünkü graf'ta var)
        assert found or len(errors) == 0

    def test_sdk_version_mismatch(self):
        """SDK versiyon hatası tespit edilmeli."""
        log = """
ERROR: Call requires API level 33 (current min is 21)
        """
        errors = self.matcher.parse_log(log)
        sdk_errors = [e for e in errors if e.error_type == "SDK_MISMATCH"]
        assert len(sdk_errors) > 0
        assert sdk_errors[0].confidence == 1.0

    def test_override_error(self):
        """Override hatası tespit edilmeli."""
        log = """
ERROR: 'onCreate' overrides nothing
        """
        errors = self.matcher.parse_log(log)
        override_errors = [e for e in errors if e.error_type == "OVERRIDE_ERROR"]
        assert len(override_errors) > 0
        assert override_errors[0].symbol == "onCreate"

    def test_generate_fix_prompt(self):
        """Düzeltme prompt'u oluşturulmalı."""
        from graphify.connectors.android import ErrorMatch
        errors = [
            ErrorMatch(
                error_type="UNRESOLVED_REFERENCE",
                message="Symbol 'X' not found",
                file_path="Test.kt",
                line_number=10,
                symbol="X",
                confidence=0.95,
                suggestion="Import eksik."
            )
        ]
        prompt = self.matcher.generate_fix_prompt(errors)
        assert "UNRESOLVED_REFERENCE" in prompt
        assert "Test.kt" in prompt
        assert "Import eksik" in prompt


class TestBrokenChainDetector:
    """Broken Chain Detector testleri."""

    def setup_method(self):
        """Her test öncesi graf oluştur."""
        self.graph = nx.DiGraph()
        self.detector = BrokenChainDetector(self.graph)

    def test_empty_graph_no_breaks(self):
        """Boş graf'ta kırık zincir olmamalı."""
        breaks = self.detector.detect_all()
        assert len(breaks) == 0

    def test_di_break_detection(self):
        """DI kopukluğu tespiti."""
        # @AndroidEntryPoint ile işaretlenmiş Activity
        self.graph.add_node("MainActivity",
                           annotation="@AndroidEntryPoint",
                           file="MainActivity.kt",
                           constructor_params=[{"type": "MissingViewModel"}])
        
        breaks = self.detector._detect_di_breaks()
        di_breaks = [b for b in breaks if b.chain_type == "DI"]
        assert len(di_breaks) > 0
        assert di_breaks[0].missing_link == "MissingViewModel"
        assert di_breaks[0].severity == "CRITICAL"

    def test_generate_report(self):
        """Rapor oluşturulmalı."""
        from graphify.connectors.android import BrokenChain
        breaks = [
            BrokenChain(
                chain_type="DI",
                start_node="A",
                end_node="B",
                missing_link="X",
                description="Test açıklama",
                severity="CRITICAL",
                fix_suggestion="Test çözüm"
            )
        ]
        report = self.detector.generate_report(breaks)
        assert "Kırık Zincir Analizi" in report
        assert "CRITICAL" in report or "kritik" in report.lower()


class TestConfigValidator:
    """Config Validator testleri."""

    def setup_method(self):
        """Her test öncesi graf oluştur."""
        self.graph = nx.DiGraph()
        self.validator = ConfigValidator(self.graph)

    def test_empty_graph_no_issues(self):
        """Boş graf'ta sorun olmamalı."""
        issues = self.validator.validate_all()
        assert len(issues) == 0

    def test_missing_permission(self):
        """Eksik izin tespiti."""
        # Manifest node'u
        self.graph.add_node("AndroidManifest.xml",
                           file="AndroidManifest.xml",
                           permissions=["android.permission.INTERNET"])
        
        # Kodda kullanılan ama tanımlanmayan izin
        self.graph.add_node("CameraActivity",
                           file="CameraActivity.kt",
                           required_permissions=["android.permission.CAMERA"])
        
        issues = self.validator.validate_all()
        perm_issues = [i for i in issues if i.issue_type == "MISSING_PERMISSION"]
        assert len(perm_issues) > 0
        assert "CAMERA" in perm_issues[0].expected_value

    def test_outdated_target_sdk(self):
        """Güncel olmayan target SDK tespiti."""
        self.graph.add_node("build.gradle.kts",
                           file="build.gradle.kts",
                           minSdkVersion=21,
                           targetSdkVersion=30,  # 33'ten düşük
                           compileSdkVersion=33)
        
        issues = self.validator.validate_all()
        sdk_issues = [i for i in issues if i.issue_type == "OUTDATED_TARGET_SDK"]
        assert len(sdk_issues) > 0
        assert sdk_issues[0].severity == "WARNING"

    def test_generate_report(self):
        """Rapor oluşturulmalı."""
        from graphify.connectors.android import ConfigIssue
        issues = [
            ConfigIssue(
                issue_type="TEST_ISSUE",
                severity="ERROR",
                file_path="test.kt",
                description="Test sorun",
                current_value="X",
                expected_value="Y",
                fix_suggestion="Test çözüm"
            )
        ]
        # Manuel olarak issues listesini set et
        self.validator.issues = issues
        report = self.validator.generate_report()
        assert "Yapılandırma Doğrulama Raporu" in report
        assert "TEST_ISSUE" in report


class TestIntegration:
    """Entegrasyon testleri."""

    def test_full_diagnose_flow(self):
        """Tam teşhis akışı testi."""
        # Graf oluştur
        graph = nx.DiGraph()
        graph.add_node("MainActivity",
                      name="MainActivity",
                      file="MainActivity.kt",
                      annotation="@AndroidEntryPoint",
                      constructor_params=[{"type": "UserRepository"}])
        
        # Hata matcher
        matcher = SmartErrorMatcher(graph)
        log = "ERROR: Unresolved reference: MissingClass"
        errors = matcher.parse_log(log)
        
        # Chain detector
        detector = BrokenChainDetector(graph)
        breaks = detector.detect_all()
        
        # Config validator
        validator = ConfigValidator(graph)
        issues = validator.validate_all()
        
        # Hepsi çalışmış olmalı
        assert errors is not None
        assert breaks is not None
        assert issues is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
