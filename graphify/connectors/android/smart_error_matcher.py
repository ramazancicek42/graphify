"""
Smart Error Matcher: Hata mesajlarını Graf düğümleriyle eşleştirir.
Unresolved reference, ClassCastException, NullPointerException gibi hataları
doğrudan kaynak dosya ve satıra işaret eder.
"""
import re
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
import networkx as nx

@dataclass
class ErrorMatch:
    error_type: str
    message: str
    file_path: str
    line_number: Optional[int]
    symbol: str
    confidence: float
    suggestion: str

class SmartErrorMatcher:
    def __init__(self, graph: nx.DiGraph):
        self.graph = graph
        # Yaygın Android hata kalıpları
        self.patterns = {
            'unresolved_reference': re.compile(r"Unresolved reference[=:]\s*([a-zA-Z0-9_.]+)"),
            'class_cast': re.compile(r"Cannot cast.*?to\s*([a-zA-Z0-9_$<>]+)"),
            'null_pointer': re.compile(r"NullPointerException.*?at\s*([a-zA-Z0-9_$\.]+)\(([^\)]+):(\d+)"),
            'resource_not_found': re.compile(r"Resource ID\s*#?([0-9a-fx]+)\s*not found|cannot resolve symbol\s*['\"]?R\.(?:layout|string|id|drawable)\.([a-zA-Z0-9_]+)"),
            'type_mismatch': re.compile(r"Type mismatch: inferred type is\s*([a-zA-Z0-9_$<>]+)\s*but\s*([a-zA-Z0-9_$<>]+)\s*was expected"),
            'override_error': re.compile(r"'([a-zA-Z0-9_]+)' overrides nothing"),
            'visibility_error': re.compile(r"([a-zA-Z0-9_.]+) is private|cannot access ([a-zA-Z0-9_.]+)"),
            'sdk_version': re.compile(r"Call requires API level (\d+) \(current min is (\d+)\)"),
            'duplicate_class': re.compile(r"Duplicate class\s*([a-zA-Z0-9_.]+)"),
        }

    def parse_log(self, log_content: str) -> List[ErrorMatch]:
        matches = []
        lines = log_content.split('\n')
        
        for i, line in enumerate(lines):
            match = self._analyze_line(line, i, lines)
            if match:
                matches.append(match)
        
        return matches

    def _analyze_line(self, line: str, line_idx: int, all_lines: List[str]) -> Optional[ErrorMatch]:
        # 1. Unresolved Reference
        m = self.patterns['unresolved_reference'].search(line)
        if m:
            symbol = m.group(1)
            node_data = self._find_symbol_in_graph(symbol)
            if node_data:
                return ErrorMatch(
                    error_type="UNRESOLVED_REFERENCE",
                    message=f"Symbol '{symbol}' tanımlanamadı.",
                    file_path=node_data.get('file', 'unknown'),
                    line_number=node_data.get('line'),
                    symbol=symbol,
                    confidence=0.95,
                    suggestion=f"{symbol} için import eksik olabilir veya sınıf silinmiş olabilir."
                )
            # R kaynağı eksikse özel durum
            if symbol.startswith("R."):
                return ErrorMatch(
                    error_type="MISSING_RESOURCE",
                    message=f"Kaynak '{symbol}' bulunamadı.",
                    file_path="res/",
                    line_number=None,
                    symbol=symbol,
                    confidence=0.9,
                    suggestion="res/ klasöründeki ilgili XML dosyasını kontrol edin veya sync yapın."
                )

        # 2. Class Cast Exception
        m = self.patterns['class_cast'].search(line)
        if m:
            target_class = m.group(1)
            return ErrorMatch(
                error_type="CLASS_CAST",
                message=f"Geçersiz tür dönüşümü: {target_class}",
                file_path=self._extract_file_from_stack(all_lines, line_idx),
                line_number=self._extract_line_from_stack(all_lines, line_idx),
                symbol=target_class,
                confidence=0.85,
                suggestion=f"Dönüşüm yapılmadan önce 'is' veya 'as?' operatörü kullanın."
            )

        # 3. Resource Not Found
        m = self.patterns['resource_not_found'].search(line)
        if m:
            res_name = m.group(2) if m.group(2) else m.group(1)
            return ErrorMatch(
                error_type="RESOURCE_MISSING",
                message=f"Kaynak ID bulunamadı: {res_name}",
                file_path="res/",
                line_number=None,
                symbol=res_name,
                confidence=0.9,
                suggestion="Layout XML dosyasının varlığını ve ID'nin doğruluğunu kontrol edin."
            )

        # 4. Override Error
        m = self.patterns['override_error'].search(line)
        if m:
            method_name = m.group(1)
            return ErrorMatch(
                error_type="OVERRIDE_ERROR",
                message=f"'{method_name}' metodu üst sınıfta yok.",
                file_path=self._extract_file_from_stack(all_lines, line_idx),
                line_number=self._extract_line_from_stack(all_lines, line_idx),
                symbol=method_name,
                confidence=0.95,
                suggestion="Metod imzasını veya üst sınıfın versiyonunu kontrol edin."
            )
            
        # 5. SDK Version Mismatch
        m = self.patterns['sdk_version'].search(line)
        if m:
            req_api = m.group(1)
            curr_api = m.group(2)
            return ErrorMatch(
                error_type="SDK_MISMATCH",
                message=f"API {req_api} gerekiyor, mevcut: {curr_api}",
                file_path=self._extract_file_from_stack(all_lines, line_idx),
                line_number=self._extract_line_from_stack(all_lines, line_idx),
                symbol=f"API {req_api}",
                confidence=1.0,
                suggestion=f"build.gradle.kts içinde minSdkVersion değerini {req_api} yapın veya @RequiresApi ekleyin."
            )

        return None

    def _find_symbol_in_graph(self, symbol: str) -> Optional[Dict]:
        # Graf üzerinde sembolü ara
        for node, data in self.graph.nodes(data=True):
            if data.get('name') == symbol or data.get('simple_name') == symbol:
                return data
            # Import yolunu kontrol et
            if symbol in data.get('imports', []):
                return data
        return None

    def _extract_file_from_stack(self, lines: List[str], current_idx: int) -> str:
        # Hata satırından sonraki stack trace'den dosya adını bul
        for i in range(current_idx + 1, min(current_idx + 10, len(lines))):
            m = re.search(r"at\s*[a-zA-Z0-9_$\.]+\(([^\)]+):(\d+)\)", lines[i])
            if m:
                return m.group(1)
        return "unknown_file"

    def _extract_line_from_stack(self, lines: List[str], current_idx: int) -> Optional[int]:
        for i in range(current_idx + 1, min(current_idx + 10, len(lines))):
            m = re.search(r"at\s*[a-zA-Z0-9_$\.]+\([^\)]+:(\d+)\)", lines[i])
            if m:
                return int(m.group(1))
        return None

    def generate_fix_prompt(self, errors: List[ErrorMatch]) -> str:
        if not errors:
            return "Hata bulunamadı."
        
        prompt = "## Tespit Edilen Hatalar ve Çözüm Önerileri\n\n"
        for i, err in enumerate(errors, 1):
            prompt += f"### {i}. {err.error_type}\n"
            prompt += f"- **Dosya:** `{err.file_path}`\n"
            if err.line_number:
                prompt += f"- **Satır:** {err.line_number}\n"
            prompt += f"- **Sorun:** {err.message}\n"
            prompt += f"- **Çözüm:** {err.suggestion}\n\n"
        
        prompt += "**AI Talimatı:** Yukarıdaki hataları sırasıyla düzelt. Sadece belirtilen dosyaları düzenle."
        return prompt
