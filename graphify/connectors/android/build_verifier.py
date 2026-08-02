"""
Graphify Build Verifier Module
Derleme Sonrası Doğrulayıcı

Uygulanan yamalardan sonra projenin başarıyla derlenip derlenmediğini kontrol eder.
Termux ortamında gradle çıktısını parse eder ve yeni hataları tespit eder.
"""

import subprocess
import re
import logging
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class BuildResult:
    """Derleme sonucu"""
    success: bool
    errors: List[str]
    warnings: List[str]
    duration_ms: int
    output_log: str

class BuildVerifier:
    """Derleme doğrulama motoru"""
    
    def __init__(self, project_root: str, gradle_wrapper: str = './gradlew'):
        self.project_root = Path(project_root)
        self.gradle_wrapper = gradle_wrapper
        self.build_history: List[BuildResult] = []
        
    def run_build(self, task: str = 'assembleDebug', 
                  timeout_sec: int = 300) -> BuildResult:
        """Gradle derlemesini çalıştır"""
        
        gradle_cmd = self.project_root / self.gradle_wrapper
        
        if not gradle_cmd.exists():
            # Global gradle kullan
            gradle_cmd = ['gradle']
        else:
            gradle_cmd = [str(gradle_cmd)]
        
        cmd = gradle_cmd + [task, '--stacktrace', '--no-daemon']
        
        logger.info(f"Running build: {' '.join(cmd)}")
        
        try:
            result = subprocess.run(
                cmd,
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=timeout_sec
            )
            
            output = result.stdout + result.stderr
            success = result.returncode == 0
            
            errors = self._parse_errors(output)
            warnings = self._parse_warnings(output)
            
            build_result = BuildResult(
                success=success,
                errors=errors,
                warnings=warnings,
                duration_ms=0,  # subprocess zamanı ekleyebiliriz
                output_log=output
            )
            
            self.build_history.append(build_result)
            return build_result
            
        except subprocess.TimeoutExpired:
            logger.error("Build timed out")
            return BuildResult(
                success=False,
                errors=["Build timed out after {} seconds".format(timeout_sec)],
                warnings=[],
                duration_ms=timeout_sec * 1000,
                output_log=""
            )
        except Exception as e:
            logger.error(f"Build failed to start: {e}")
            return BuildResult(
                success=False,
                errors=[str(e)],
                warnings=[],
                duration_ms=0,
                output_log=""
            )
    
    def _parse_errors(self, output: str) -> List[str]:
        """Derleme hatalarını parse et"""
        errors = []
        
        # Genel hata patternleri
        error_patterns = [
            r'error:.*$',
            r'^\s*ERROR:.*$',
            r'^\s*FAILURE:.*$',
            r'^\s*Exception in thread.*$',
            r'^\s*e:.*$',  # Kotlin hataları
            r'^\s*\*.+\s+\^$',  # Pointer hataları
        ]
        
        for line in output.split('\n'):
            for pattern in error_patterns:
                if re.search(pattern, line, re.IGNORECASE | re.MULTILINE):
                    errors.append(line.strip())
                    break
        
        # Stack trace başlangıçlarını bul
        if 'BUILD FAILED' in output:
            errors.append("BUILD FAILED")
        
        return list(set(errors))  # Tekrarları kaldır
    
    def _parse_warnings(self, output: str) -> List[str]:
        """Uyarıları parse et"""
        warnings = []
        
        warning_patterns = [
            r'warning:.*$',
            r'^\s*WARNING:.*$',
            r'^\s*w:.*$',  # Kotlin uyarıları
            r'DeprecationWarning',
            r'is deprecated',
        ]
        
        for line in output.split('\n'):
            for pattern in warning_patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    warnings.append(line.strip())
                    break
        
        return list(set(warnings))
    
    def verify_fix(self, previous_errors: List[str], 
                   current_result: BuildResult) -> Dict:
        """Önceki hataların düzelip düzelmediğini kontrol et"""
        
        fixed_errors = []
        remaining_errors = []
        new_errors = []
        
        previous_error_set = set(previous_errors)
        current_error_set = set(current_result.errors)
        
        # Düzeltilen hatalar
        fixed_errors = list(previous_error_set - current_error_set)
        
        # Kalan hatalar
        remaining_errors = list(previous_error_set & current_error_set)
        
        # Yeni hatalar
        new_errors = list(current_error_set - previous_error_set)
        
        return {
            'fixed': fixed_errors,
            'remaining': remaining_errors,
            'new': new_errors,
            'all_fixed': len(remaining_errors) == 0 and len(new_errors) == 0,
            'regression': len(new_errors) > 0
        }
    
    def get_quick_check_command(self) -> str:
        """Hızlı kontrol için minimal gradle komutu öner"""
        return f"{self.gradle_wrapper} compileDebugKotlin --no-daemon"
    
    def get_summary(self) -> Dict:
        """Derleme geçmişi özeti"""
        if not self.build_history:
            return {'total_builds': 0}
        
        successful = sum(1 for b in self.build_history if b.success)
        
        return {
            'total_builds': len(self.build_history),
            'successful': successful,
            'failed': len(self.build_history) - successful,
            'last_build': {
                'success': self.build_history[-1].success,
                'errors': len(self.build_history[-1].errors),
                'warnings': len(self.build_history[-1].warnings)
            } if self.build_history else None
        }
