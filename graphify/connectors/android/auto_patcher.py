"""
Graphify Auto-Patcher Module
Otonom Hata Düzeltme ve Yama Uygulayıcı

Android projelerinde tespit edilen hatalar için bağlam odaklı düzeltmeler üretir ve uygular.
Termux ortamında güvenli çalışacak şekilde tasarlanmıştır.
"""

import os
import re
import difflib
import logging
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class PatchProposal:
    """Önerilen yama teklifi"""
    file_path: str
    original_code: str
    fixed_code: str
    reason: str
    confidence: float  # 0.0 - 1.0 arası güven skoru

class AutoPatcher:
    """Otonom hata düzeltme motoru"""
    
    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self.patch_history: List[PatchProposal] = []
        
    def generate_patch(self, error_type: str, error_location: str, 
                      context: Dict) -> Optional[PatchProposal]:
        """Hata tipine göre yama önerisi oluştur"""
        
        handlers = {
            'unresolved_reference': self._fix_unresolved_reference,
            'sdk_mismatch': self._fix_sdk_mismatch,
            'missing_permission': self._fix_missing_permission,
            'override_error': self._fix_override_error,
            'type_mismatch': self._fix_type_mismatch,
            'null_pointer': self._fix_null_pointer,
            'import_missing': self._fix_import_missing,
        }
        
        handler = handlers.get(error_type)
        if not handler:
            logger.warning(f"Unknown error type: {error_type}")
            return None
            
        try:
            return handler(error_location, context)
        except Exception as e:
            logger.error(f"Patch generation failed: {e}")
            return None
    
    def _fix_resource_not_found(self, location: str, context: Dict) -> Optional[PatchProposal]:
        """Kaynak bulunamadı hatasını düzelt"""
        # Henüz implement edilmedi
        return None
    
    def _fix_override_error(self, location: str, context: Dict) -> Optional[PatchProposal]:
        """Override hatasını düzelt"""
        # Henüz implement edilmedi
        return None
    
    def _fix_type_mismatch(self, location: str, context: Dict) -> Optional[PatchProposal]:
        """Tip uyumsuzluğu hatasını düzelt"""
        # Henüz implement edilmedi
        return None
    
    def _fix_null_pointer(self, location: str, context: Dict) -> Optional[PatchProposal]:
        """Null pointer hatasını düzelt"""
        # Henüz implement edilmedi
        return None
    
    def _fix_import_missing(self, location: str, context: Dict) -> Optional[PatchProposal]:
        """Eksik import'u düzelt"""
        # _fix_unresolved_reference tarafından kapsanır
        return None
    
    def _fix_unresolved_reference(self, location: str, context: Dict) -> Optional[PatchProposal]:
        """Çözümlenemeyen referans hatalarını düzelt"""
        file_path = context.get('file_path')
        symbol = context.get('symbol')
        
        if not file_path or not symbol:
            return None
            
        full_path = self.project_root / file_path
        if not full_path.exists():
            return None
            
        content = full_path.read_text(encoding='utf-8')
        
        # R.resource eksikliği için
        if symbol.startswith('R.'):
            # Import ekle
            import_line = f"import {context.get('package_name', '')}.R"
            if import_line not in content:
                lines = content.split('\n')
                # Son import'tan sonra ekle
                insert_idx = 0
                for i, line in enumerate(lines):
                    if line.startswith('import'):
                        insert_idx = i + 1
                
                lines.insert(insert_idx, import_line)
                fixed_code = '\n'.join(lines)
                
                return PatchProposal(
                    file_path=file_path,
                    original_code=content,
                    fixed_code=fixed_code,
                    reason=f"Missing import for {symbol}",
                    confidence=0.95
                )
        
        return None
    
    def _fix_missing_permission(self, location: str, context: Dict) -> Optional[PatchProposal]:
        """Eksik izinleri AndroidManifest.xml'e ekle"""
        manifest_path = self.project_root / 'app' / 'src' / 'main' / 'AndroidManifest.xml'
        
        if not manifest_path.exists():
            return None
            
        content = manifest_path.read_text(encoding='utf-8')
        permission = context.get('permission')
        
        if not permission:
            return None
            
        permission_tag = f'    <uses-permission android:name="{permission}" />'
        
        if permission_tag not in content:
            # </manifest> etiketinden önce ekle
            fixed_code = content.replace(
                '</manifest>',
                f'{permission_tag}\n</manifest>'
            )
            
            return PatchProposal(
                file_path=str(manifest_path.relative_to(self.project_root)),
                original_code=content,
                fixed_code=fixed_code,
                reason=f"Missing permission: {permission}",
                confidence=0.98
            )
        
        return None
    
    def _fix_sdk_mismatch(self, location: str, context: Dict) -> Optional[PatchProposal]:
        """SDK versiyon uyumsuzluklarını düzelt"""
        build_gradle = self.project_root / 'app' / 'build.gradle'
        if not build_gradle.exists():
            build_gradle = self.project_root / 'app' / 'build.gradle.kts'
        
        if not build_gradle.exists():
            return None
            
        content = build_gradle.read_text(encoding='utf-8')
        required_api = context.get('required_api_level')
        
        if not required_api:
            return None
            
        # compileSdkVersion güncelle
        pattern = r'(compileSdkVersion\s+)(\d+)'
        match = re.search(pattern, content)
        
        if match and int(match.group(2)) < required_api:
            fixed_code = re.sub(
                pattern,
                f'\\g<1>{required_api}',
                content
            )
            
            return PatchProposal(
                file_path=str(build_gradle.relative_to(self.project_root)),
                original_code=content,
                fixed_code=fixed_code,
                reason=f"compileSdkVersion must be at least {required_api}",
                confidence=0.90
            )
        
        return None
    
    def apply_patch(self, patch: PatchProposal, dry_run: bool = False) -> bool:
        """Yamayı uygula"""
        if not patch:
            return False
            
        full_path = self.project_root / patch.file_path
        
        if dry_run:
            logger.info(f"[DRY RUN] Would patch {patch.file_path}: {patch.reason}")
            return True
        
        try:
            # Yedek oluştur
            backup_path = full_path.with_suffix(full_path.suffix + '.bak')
            full_path.rename(backup_path)
            
            # Yeni kodu yaz
            full_path.write_text(patch.fixed_code, encoding='utf-8')
            
            self.patch_history.append(patch)
            logger.info(f"Successfully patched {patch.file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to apply patch: {e}")
            # Geri al
            if backup_path.exists():
                backup_path.rename(full_path)
            return False
    
    def create_diff(self, patch: PatchProposal) -> str:
        """Unified diff formatında fark oluştur"""
        return '\n'.join(difflib.unified_diff(
            patch.original_code.splitlines(),
            patch.fixed_code.splitlines(),
            fromfile=f"a/{patch.file_path}",
            tofile=f"b/{patch.file_path}",
            lineterm=''
        ))
    
    def get_summary(self) -> Dict:
        """Yama özeti döndür"""
        return {
            'total_patches': len(self.patch_history),
            'patches': [
                {
                    'file': p.file_path,
                    'reason': p.reason,
                    'confidence': p.confidence
                }
                for p in self.patch_history
            ]
        }
