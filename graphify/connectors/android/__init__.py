"""
Android Connector Paketi: Hata teşhis ve analiz modülleri.
"""
from .smart_error_matcher import SmartErrorMatcher, ErrorMatch
from .broken_chain_detector import BrokenChainDetector, BrokenChain
from .config_validator import ConfigValidator, ConfigIssue
from .diagnose_cli import diagnose_error_log
from .auto_patcher import AutoPatcher, PatchProposal
from .build_verifier import BuildVerifier, BuildResult
from .logcat_analyzer import LogcatAnalyzer, CrashReport

__all__ = [
    # Diagnosis
    'SmartErrorMatcher',
    'ErrorMatch',
    'BrokenChainDetector',
    'BrokenChain',
    'ConfigValidator',
    'ConfigIssue',
    'diagnose_error_log',

    # Auto-fix
    'AutoPatcher',
    'PatchProposal',
    'BuildVerifier',
    'BuildResult',
    'LogcatAnalyzer',
    'CrashReport',
]
