"""
Test suite for Android auto-fix modules:
- AutoPatcher
- BuildVerifier  
- LogcatAnalyzer
"""

import pytest
import tempfile
import os
from pathlib import Path

from graphify.connectors.android import (
    AutoPatcher,
    PatchProposal,
    BuildVerifier,
    BuildResult,
    LogcatAnalyzer,
    CrashReport
)


class TestAutoPatcher:
    """AutoPatcher testleri"""
    
    def test_init(self):
        """Başlatma testi"""
        with tempfile.TemporaryDirectory() as tmpdir:
            patcher = AutoPatcher(tmpdir)
            assert patcher.project_root == Path(tmpdir)
            assert len(patcher.patch_history) == 0
    
    def test_generate_patch_unresolved_reference(self):
        """Çözümlenemeyen referans hatası için yama oluşturma"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Test dosyası oluştur
            test_file = Path(tmpdir) / 'TestActivity.kt'
            test_file.write_text(
                'package com.example.app\n\n'
                'class TestActivity {\n'
                '    fun onCreate() {\n'
                '        val view = findViewById(R.id.button)\n'
                '    }\n'
                '}'
            )
            
            patcher = AutoPatcher(tmpdir)
            
            context = {
                'file_path': 'TestActivity.kt',
                'symbol': 'R.id.button',
                'package_name': 'com.example.app'
            }
            
            patch = patcher.generate_patch('unresolved_reference', '', context)
            
            # Import eklenmeli
            assert patch is not None
            assert 'import com.example.app.R' in patch.fixed_code
            assert patch.confidence > 0.9
    
    def test_apply_patch_dry_run(self):
        """Dry run modunda yama uygulama"""
        with tempfile.TemporaryDirectory() as tmpdir:
            patcher = AutoPatcher(tmpdir)
            
            patch = PatchProposal(
                file_path='test.txt',
                original_code='old',
                fixed_code='new',
                reason='test',
                confidence=1.0
            )
            
            # Dosya yoksa dry run başarılı olmalı
            result = patcher.apply_patch(patch, dry_run=True)
            assert result is True
    
    def test_create_diff(self):
        """Diff oluşturma testi"""
        patcher = AutoPatcher(tempfile.gettempdir())
        
        patch = PatchProposal(
            file_path='test.kt',
            original_code='val x = 1',
            fixed_code='val x = 2',
            reason='update',
            confidence=1.0
        )
        
        diff = patcher.create_diff(patch)
        assert '-val x = 1' in diff
        assert '+val x = 2' in diff


class TestBuildVerifier:
    """BuildVerifier testleri"""
    
    def test_init(self):
        """Başlatma testi"""
        with tempfile.TemporaryDirectory() as tmpdir:
            verifier = BuildVerifier(tmpdir)
            assert verifier.project_root == Path(tmpdir)
    
    def test_parse_errors(self):
        """Hata parse etme testi"""
        verifier = BuildVerifier(tempfile.gettempdir())
        
        output = """
        BUILD FAILED
        e: /app/Test.kt: (10, 5): Unresolved reference: foo
        ERROR: Missing permission
        """
        
        errors = verifier._parse_errors(output)
        assert len(errors) > 0
        assert any('Unresolved' in e for e in errors)
    
    def test_parse_warnings(self):
        """Uyarı parse etme testi"""
        verifier = BuildVerifier(tempfile.gettempdir())
        
        output = """
        w: /app/Test.kt: (5, 3): Variable is deprecated
        WARNING: Use another method
        """
        
        warnings = verifier._parse_warnings(output)
        assert len(warnings) > 0
    
    def test_verify_fix_all_fixed(self):
        """Tüm hataların düzelip düzelmediğini kontrol etme"""
        verifier = BuildVerifier(tempfile.gettempdir())
        
        previous_errors = ['Error A', 'Error B', 'Error C']
        
        current_result = BuildResult(
            success=True,
            errors=[],
            warnings=['Warning X'],
            duration_ms=1000,
            output_log=''
        )
        
        verification = verifier.verify_fix(previous_errors, current_result)
        
        assert verification['all_fixed'] is True
        assert len(verification['fixed']) == 3
        assert len(verification['remaining']) == 0
    
    def test_verify_fix_regression(self):
        """Yeni hata regresyonu testi"""
        verifier = BuildVerifier(tempfile.gettempdir())
        
        previous_errors = ['Error A']
        
        current_result = BuildResult(
            success=False,
            errors=['Error A', 'Error B'],  # Yeni hata
            warnings=[],
            duration_ms=1000,
            output_log=''
        )
        
        verification = verifier.verify_fix(previous_errors, current_result)
        
        assert verification['regression'] is True
        assert 'Error B' in verification['new']


class TestLogcatAnalyzer:
    """LogcatAnalyzer testleri"""
    
    def test_init(self):
        """Başlatma testi"""
        analyzer = LogcatAnalyzer()
        assert analyzer.device_id is None
        assert len(analyzer.crash_history) == 0
    
    def test_parse_crashes(self):
        """Crash parse etme testi"""
        analyzer = LogcatAnalyzer()
        
        logcat = """
2024-01-15 10:30:45.123 1234 5678 FATAL com.example.app: NullPointerException: Attempt to invoke virtual method on null
        at com.example.app.MainActivity.onCreate(MainActivity.kt:25)
        at android.app.Activity.performCreate(Activity.java:8000)
2024-01-15 10:31:00.456 1234 5679 ERROR com.example.app: Some other error
        """
        
        crashes = analyzer.parse_crashes(logcat)
        
        assert len(crashes) == 1
        assert crashes[0].exception_type == 'NullPointerException'
        assert crashes[0].package_name == 'com.example.app'
        assert crashes[0].cause_file == 'MainActivity.kt'
        assert crashes[0].cause_line == 25
    
    def test_filter_by_package(self):
        """Paket bazlı filtreleme testi"""
        analyzer = LogcatAnalyzer()
        
        # Sahte crash verisi ekle
        analyzer.crash_history = [
            CrashReport(
                package_name='com.example.app1',
                exception_type='NPE',
                exception_message='msg1',
                stack_trace=[],
                timestamp='2024-01-15',
                pid=1,
                tid=1,
                cause_file=None,
                cause_line=None,
                cause_method=None
            ),
            CrashReport(
                package_name='com.example.app2',
                exception_type='ISE',
                exception_message='msg2',
                stack_trace=[],
                timestamp='2024-01-15',
                pid=2,
                tid=2,
                cause_file=None,
                cause_line=None,
                cause_method=None
            )
        ]
        
        filtered = analyzer.filter_by_package('app1')
        assert len(filtered) == 1
        assert 'app1' in filtered[0].package_name
    
    def test_suggest_fix_npe(self):
        """NullPointerException için öneri üretme"""
        analyzer = LogcatAnalyzer()
        
        crash = CrashReport(
            package_name='com.example.app',
            exception_type='NullPointerException',
            exception_message='null object',
            stack_trace=['at Test.method(Test.kt:10)'],
            timestamp='2024-01-15',
            pid=1,
            tid=1,
            cause_file='Test.kt',
            cause_line=10,
            cause_method='method'
        )
        
        suggestion = analyzer.suggest_fix(crash)
        
        assert suggestion['crash_type'] == 'NullPointerException'
        assert len(suggestion['suggestions']) > 0
        assert suggestion['suggestions'][0]['type'] == 'null_check'
    
    def test_get_summary(self):
        """Özet raporu alma testi"""
        analyzer = LogcatAnalyzer()
        
        # Boş özet
        summary = analyzer.get_summary()
        assert summary['total_crashes'] == 0
        
        # Veri ekledikten sonra
        analyzer.crash_history = [
            CrashReport(
                package_name='com.example.app',
                exception_type='NPE',
                exception_message='msg',
                stack_trace=[],
                timestamp='2024-01-15',
                pid=1,
                tid=1,
                cause_file=None,
                cause_line=None,
                cause_method=None
            )
        ]
        
        summary = analyzer.get_summary()
        assert summary['total_crashes'] == 1


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
