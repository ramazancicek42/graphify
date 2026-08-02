"""
Graphify Logcat Analyzer Module
Runtime Crash ve Çökme Analizcisi

Android cihazlardan alınan logcat çıktılarını analiz eder,
crash raporlarını parse eder ve kök nedenleri tespit eder.
Termux'ta adb üzerinden çalışabilir.
"""

import subprocess
import re
import logging
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from collections import defaultdict

logger = logging.getLogger(__name__)

@dataclass
class CrashReport:
    """Çökme raporu"""
    package_name: str
    exception_type: str
    exception_message: str
    stack_trace: List[str]
    timestamp: str
    pid: int
    tid: int
    cause_file: Optional[str]
    cause_line: Optional[int]
    cause_method: Optional[str]

class LogcatAnalyzer:
    """Logcat analiz motoru"""
    
    def __init__(self, device_id: Optional[str] = None):
        self.device_id = device_id
        self.crash_history: List[CrashReport] = []
        
    def get_logcat(self, lines: int = 1000, 
                   timeout_sec: int = 30) -> str:
        """Cihazdan logcat al"""
        
        cmd = ['adb']
        if self.device_id:
            cmd.extend(['-s', self.device_id])
        
        cmd.extend(['logcat', '-d', '-t', str(lines)])
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout_sec
            )
            
            if result.returncode != 0:
                logger.error(f"adb failed: {result.stderr}")
                return ""
                
            return result.stdout
            
        except subprocess.TimeoutExpired:
            logger.error("logcat timed out")
            return ""
        except FileNotFoundError:
            logger.error("adb not found. Is Android SDK installed?")
            return ""
    
    def parse_crashes(self, logcat_output: str) -> List[CrashReport]:
        """Logcat çıktısından crash'leri parse et"""
        
        crashes = []
        
        # Crash başlangıç pattern'i - Android logcat formatı
        # Format: MM-DD HH:MM:SS.mmm PID TID Level Tag: Message
        crash_pattern = re.compile(
            r'^(?:\d{4}-)?(\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d{3})\s+'
            r'(\d+)\s+(\d+)\s+([A-Z]+)\s+([^:]+):\s+(.*)$',
            re.MULTILINE
        )
        
        # Stack trace pattern
        stack_pattern = re.compile(
            r'^\s+at\s+([^\(]+)\(([^\)]+)\)',
            re.MULTILINE
        )
        
        current_crash = None
        current_stack = []
        current_level = None  # Log seviyesini sakla
        
        for line in logcat_output.split('\n'):
            crash_match = crash_pattern.match(line)
            
            if crash_match:
                # Önceki crash'i kaydet (FATAL seviyesindeyse)
                if current_crash and current_level == 'FATAL':
                    current_crash.stack_trace = current_stack[:20]  # İlk 20 satır
                    crashes.append(current_crash)
                
                timestamp, pid, tid, level, tag, message = crash_match.groups()
                current_level = level  # Seviyeyi sakla
                
                # Exception tipini bul
                exc_match = re.match(r'([^\s:]+):\s*(.*)', message)
                if exc_match:
                    exc_type, exc_msg = exc_match.groups()
                else:
                    exc_type = message.split()[0] if message else 'Unknown'
                    exc_msg = message
                
                current_crash = CrashReport(
                    package_name=tag,
                    exception_type=exc_type,
                    exception_message=exc_msg,
                    stack_trace=[],
                    timestamp=timestamp,
                    pid=int(pid),
                    tid=int(tid),
                    cause_file=None,
                    cause_line=None,
                    cause_method=None
                )
                current_stack = []
                
            elif current_crash and stack_pattern.match(line):
                # Stack trace satırı
                match = stack_pattern.match(line)
                if match:
                    method, location = match.groups()
                    current_stack.append(f"{method}({location})")
                    
                    # İlk stack frame'den cause bilgilerini çıkar
                    if not current_crash.cause_file:
                        file_match = re.match(r'([^:]+):(\d+)', location)
                        if file_match:
                            current_crash.cause_file = file_match.group(1)
                            current_crash.cause_line = int(file_match.group(2))
                            current_crash.cause_method = method
        
        # Son crash'i ekle (FATAL seviyesindeyse)
        if current_crash and current_level == 'FATAL':
            current_crash.stack_trace = current_stack[:20]
            crashes.append(current_crash)
        
        self.crash_history.extend(crashes)
        return crashes
    
    def filter_by_package(self, package_name: str) -> List[CrashReport]:
        """Belirli pakete ait crash'leri filtrele"""
        return [
            c for c in self.crash_history 
            if package_name in c.package_name
        ]
    
    def get_top_exceptions(self, limit: int = 10) -> List[Dict]:
        """En sık oluşan exception'ları listele"""
        
        exc_counts = defaultdict(int)
        
        for crash in self.crash_history:
            key = f"{crash.exception_type}: {crash.exception_message}"
            exc_counts[key] += 1
        
        sorted_exc = sorted(
            exc_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )[:limit]
        
        return [
            {'exception': exc, 'count': count}
            for exc, count in sorted_exc
        ]
    
    def suggest_fix(self, crash: CrashReport) -> Dict:
        """Crash için çözüm önerisi üret"""
        
        suggestions = []
        
        # NullPointerException
        if 'NullPointerException' in crash.exception_type:
            suggestions.append({
                'type': 'null_check',
                'message': 'Add null check before accessing the object',
                'location': crash.cause_file,
                'line': crash.cause_line
            })
        
        # ClassCastException
        elif 'ClassCastException' in crash.exception_type:
            suggestions.append({
                'type': 'type_check',
                'message': 'Verify type before casting or use safe cast (as?)',
                'location': crash.cause_file,
                'line': crash.cause_line
            })
        
        # IndexOutOfBoundsException
        elif 'IndexOutOfBoundsException' in crash.exception_type:
            suggestions.append({
                'type': 'bounds_check',
                'message': 'Check collection size before accessing index',
                'location': crash.cause_file,
                'line': crash.cause_line
            })
        
        # IllegalStateException
        elif 'IllegalStateException' in crash.exception_type:
            suggestions.append({
                'type': 'state_check',
                'message': 'Ensure proper lifecycle state before operation',
                'location': crash.cause_file,
                'line': crash.cause_line
            })
        
        # ResourceNotFoundException
        elif 'ResourceNotFoundException' in crash.exception_type:
            suggestions.append({
                'type': 'resource_check',
                'message': 'Verify resource ID exists in res/ directory',
                'location': crash.cause_file,
                'line': crash.cause_line
            })
        
        return {
            'crash_type': crash.exception_type,
            'suggestions': suggestions,
            'stack_trace_summary': crash.stack_trace[:5] if crash.stack_trace else []
        }
    
    def start_monitoring(self, package_name: Optional[str] = None,
                         callback=None):
        """Canlı crash izleme başlat (background)"""
        
        cmd = ['adb']
        if self.device_id:
            cmd.extend(['-s', self.device_id])
        
        cmd.extend(['logcat', '*:E'])
        
        if package_name:
            cmd.extend(['--pid', str(self._get_pid(package_name))])
        
        # Bu fonksiyon normalde thread'de çalışmalı
        logger.info(f"Starting logcat monitor for {package_name or 'all'}")
        # Gerçek implementasyon için threading kullanılabilir
    
    def _get_pid(self, package_name: str) -> Optional[int]:
        """Paketin PID'sini bul"""
        
        cmd = ['adb']
        if self.device_id:
            cmd.extend(['-s', self.device_id])
        
        cmd.extend(['shell', 'pidof', package_name])
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0 and result.stdout.strip():
                return int(result.stdout.strip().split()[0])
        except:
            pass
        
        return None
    
    def get_summary(self) -> Dict:
        """Analiz özeti"""
        
        return {
            'total_crashes': len(self.crash_history),
            'unique_exceptions': len(set(c.exception_type for c in self.crash_history)),
            'top_packages': self._get_top_packages(),
            'recent_crashes': [
                {
                    'package': c.package_name,
                    'type': c.exception_type,
                    'message': c.exception_message[:50] + '...' if len(c.exception_message) > 50 else c.exception_message
                }
                for c in self.crash_history[-5:]
            ]
        }
    
    def _get_top_packages(self) -> List[Dict]:
        """En çok crash veren paketler"""
        
        pkg_counts = defaultdict(int)
        
        for crash in self.crash_history:
            pkg_counts[crash.package_name] += 1
        
        sorted_pkgs = sorted(
            pkg_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )[:5]
        
        return [
            {'package': pkg, 'crashes': count}
            for pkg, count in sorted_pkgs
        ]
