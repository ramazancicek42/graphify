"""
Config Validator: AndroidManifest.xml, build.gradle ve diğer yapılandırma
dosyalarındaki uyumsuzlukları önceden tespit eder.
"""
import re
from typing import List, Dict, Optional, Set
from dataclasses import dataclass
import networkx as nx

@dataclass
class ConfigIssue:
    issue_type: str
    severity: str  # ERROR, WARNING, INFO
    file_path: str
    description: str
    current_value: str
    expected_value: str
    fix_suggestion: str

class ConfigValidator:
    def __init__(self, graph: nx.DiGraph):
        self.graph = graph
        self.issues: List[ConfigIssue] = []

    def validate_all(self) -> List[ConfigIssue]:
        """Tüm yapılandırma kontrollerini çalıştır."""
        self.issues = []
        self._validate_manifest_permissions()
        self._validate_sdk_versions()
        self._validate_app_id_consistency()
        self._validate_network_security()
        self._validate_feature_flags()
        return self.issues

    def _validate_manifest_permissions(self):
        """Manifest izinleri ve kullanım kontrolleri."""
        manifest_node = None
        for node, data in self.graph.nodes(data=True):
            if 'AndroidManifest.xml' in data.get('file', ''):
                manifest_node = data
                break
        
        if not manifest_node:
            return
        
        declared_perms = set(manifest_node.get('permissions', []))
        used_perms = set()
        
        # Kodda kullanılan izinleri topla
        for node, data in self.graph.nodes(data=True):
            used_perms.update(data.get('required_permissions', []))
        
        # Kullanılan ama tanımlanmayan izinler
        missing_perms = used_perms - declared_perms
        for perm in missing_perms:
            self.issues.append(ConfigIssue(
                issue_type="MISSING_PERMISSION",
                severity="ERROR",
                file_path="AndroidManifest.xml",
                description=f"{perm} izni kullanılıyor ama Manifest'te tanımlı değil.",
                current_value="Tanımlı değil",
                expected_value=perm,
                fix_suggestion=f"<uses-permission android:name=\"{perm}\" /> ekleyin."
            ))
        
        # Tanımlanan ama kullanılmayan izinler (gereksiz)
        unused_perms = declared_perms - used_perms
        for perm in unused_perms:
            if not perm.startswith('android.permission.INTERNET'):  # İnternet her zaman gerekli olabilir
                self.issues.append(ConfigIssue(
                    issue_type="UNUSED_PERMISSION",
                    severity="WARNING",
                    file_path="AndroidManifest.xml",
                    description=f"{perm} izni tanımlı ama kodda kullanılmıyor.",
                    current_value=perm,
                    expected_value="Kaldırılmalı",
                    fix_suggestion=f"Gereksiz izinleri temizleyin."
                ))

    def _validate_sdk_versions(self):
        """SDK versiyon tutarlılığı."""
        build_gradle_data = None
        manifest_data = None
        
        for node, data in self.graph.nodes(data=True):
            if 'build.gradle' in data.get('file', ''):
                build_gradle_data = data
            if 'AndroidManifest.xml' in data.get('file', ''):
                manifest_data = data
        
        if not build_gradle_data:
            return
        
        min_sdk = build_gradle_data.get('minSdkVersion')
        target_sdk = build_gradle_data.get('targetSdkVersion')
        compile_sdk = build_gradle_data.get('compileSdkVersion')
        
        # Hedef SDK güncel olmalı
        if target_sdk and target_sdk < 33:  # En az Android 13
            self.issues.append(ConfigIssue(
                issue_type="OUTDATED_TARGET_SDK",
                severity="WARNING",
                file_path="build.gradle.kts",
                description=f"targetSdkVersion ({target_sdk}) güncel değil. Google Play gereksinimlerini karşılamayabilir.",
                current_value=str(target_sdk),
                expected_value=">= 33",
                fix_suggestion="targetSdkVersion'ı en az 33 yapın."
            ))
        
        # Compile SDK >= Target SDK olmalı
        if compile_sdk and target_sdk and compile_sdk < target_sdk:
            self.issues.append(ConfigIssue(
                issue_type="SDK_MISMATCH",
                severity="ERROR",
                file_path="build.gradle.kts",
                description=f"compileSdkVersion ({compile_sdk}) < targetSdkVersion ({target_sdk})",
                current_value=str(compile_sdk),
                expected_value=f">= {target_sdk}",
                fix_suggestion=f"compileSdkVersion'ı {target_sdk} veya üzerine çıkarın."
            ))
        
        # Min SDK çok düşük mü?
        if min_sdk and min_sdk < 21:
            self.issues.append(ConfigIssue(
                issue_type="LOW_MIN_SDK",
                severity="INFO",
                file_path="build.gradle.kts",
                description=f"minSdkVersion ({min_sdk}) çok düşük. Cihaz desteği geniş ama eski API'ler için kontrol gerekiyor.",
                current_value=str(min_sdk),
                expected_value=">= 21",
                fix_suggestion="Eski cihaz desteği gerçekten gerekli mi kontrol edin."
            ))

    def _validate_app_id_consistency(self):
        """Application ID tutarlılığı."""
        app_ids = set()
        
        for node, data in self.graph.nodes(data=True):
            if 'build.gradle' in data.get('file', ''):
                if 'applicationId' in data:
                    app_ids.add(data['applicationId'])
            if 'AndroidManifest.xml' in data.get('file', ''):
                if 'package' in data:
                    app_ids.add(data['package'])
        
        if len(app_ids) > 1:
            self.issues.append(ConfigIssue(
                issue_type="APP_ID_MISMATCH",
                severity="ERROR",
                file_path="build.gradle.kts / AndroidManifest.xml",
                description=f"Application ID tutarsızlığı: {app_ids}",
                current_value=", ".join(app_ids),
                expected_value="Tek bir ID",
                fix_suggestion="Tüm dosyalarda aynı applicationId kullanın."
            ))

    def _validate_network_security(self):
        """Güvenlik yapılandırması."""
        uses_cleartext = False
        has_network_config = False
        
        for node, data in self.graph.nodes(data=True):
            if 'AndroidManifest.xml' in data.get('file', ''):
                uses_cleartext = data.get('usesCleartextTraffic', False)
                has_network_config = 'networkSecurityConfig' in data
            
            if 'network_security_config.xml' in data.get('file', ''):
                has_network_config = True
        
        if uses_cleartext and not has_network_config:
            self.issues.append(ConfigIssue(
                issue_type="INSECURE_TRAFFIC",
                severity="ERROR",
                file_path="AndroidManifest.xml",
                description="Cleartext trafiğe izin veriliyor ama networkSecurityConfig tanımlı değil.",
                current_value="usesCleartextTraffic=true",
                expected_value="HTTPS only veya güvenli config",
                fix_suggestion="network_security_config.xml ekleyin veya usesCleartextTraffic=false yapın."
            ))
        
        # API anahtarları hardcoded mı?
        for node, data in self.graph.nodes(data=True):
            if 'api_key' in data.get('content', '').lower() or 'apikey' in data.get('content', '').lower():
                if 'BuildConfig' not in data.get('file', ''):
                    self.issues.append(ConfigIssue(
                        issue_type="HARDCODED_API_KEY",
                        severity="ERROR",
                        file_path=data.get('file', 'unknown'),
                        description="API anahtarı kaynak kodda hardcoded bulunmuş olabilir.",
                        current_value="Hardcoded",
                        expected_value="BuildConfig veya Keystore",
                        fix_suggestion="API anahtarlarını BuildConfig veya encrypted storage'a taşıyın."
                    ))

    def _validate_feature_flags(self):
        """Özellik bayrakları ve build types."""
        flavor_dims = set()
        build_types = set()
        
        for node, data in self.graph.nodes(data=True):
            if 'build.gradle' in data.get('file', ''):
                flavor_dims.update(data.get('flavorDimensions', []))
                build_types.update(data.get('buildTypes', []))
        
        # Product flavor tanımlıysa ama dimension yoksa
        flavors = []
        for node, data in self.graph.nodes(data=True):
            if 'productFlavors' in data:
                flavors.extend(data.get('productFlavors', []))
        
        if flavors and not flavor_dims:
            self.issues.append(ConfigIssue(
                issue_type="MISSING_FLAVOR_DIMENSION",
                severity="WARNING",
                file_path="build.gradle.kts",
                description="Product flavors tanımlı ama flavorDimensions eksik.",
                current_value="Tanımlı değil",
                expected_value="flavorDimensions tanımı",
                fix_suggestion="flavorDimensions bloğu ekleyin."
            ))

    def generate_report(self) -> str:
        if not self.issues:
            return "✅ Yapılandırma sorunları tespit edilmedi!"
        
        report = "## 🔧 Yapılandırma Doğrulama Raporu\n\n"
        
        errors = [i for i in self.issues if i.severity == "ERROR"]
        warnings = [i for i in self.issues if i.severity == "WARNING"]
        infos = [i for i in self.issues if i.severity == "INFO"]
        
        if errors:
            report += "### 🔴 Hatalar\n\n"
            for i, issue in enumerate(errors, 1):
                report += f"**{i}. {issue.issue_type}**\n"
                report += f"- 📁 Dosya: `{issue.file_path}`\n"
                report += f"- ❌ Sorun: {issue.description}\n"
                report += f"- ✅ Çözüm: {issue.fix_suggestion}\n\n"
        
        if warnings:
            report += "### ⚠️ Uyarılar\n\n"
            for i, issue in enumerate(warnings, 1):
                report += f"**{i}. {issue.issue_type}**\n"
                report += f"- 📁 Dosya: `{issue.file_path}`\n"
                report += f"- ⚠️ Sorun: {issue.description}\n"
                report += f"- 💡 Öneri: {issue.fix_suggestion}\n\n"
        
        if infos:
            report += "### ℹ️ Bilgiler\n\n"
            for i, issue in enumerate(infos, 1):
                report += f"**{i}. {issue.issue_type}**\n"
                report += f"- {issue.description}\n\n"
        
        report += f"**Özet:** {len(errors)} hata, {len(warnings)} uyarı, {len(infos)} bilgi"
        return report
