"""
Broken Chain Detector: Dependency Injection, Navigation ve Intent akışlarındaki
kopuklukları otomatik tespit eder.
"""
import networkx as nx
from typing import List, Dict, Set, Tuple
from dataclasses import dataclass

@dataclass
class BrokenChain:
    chain_type: str  # DI, NAVIGATION, INTENT, DATA_FLOW
    start_node: str
    end_node: str
    missing_link: str
    description: str
    severity: str  # CRITICAL, WARNING, INFO
    fix_suggestion: str

class BrokenChainDetector:
    def __init__(self, graph: nx.DiGraph):
        self.graph = graph

    def detect_all(self) -> List[BrokenChain]:
        chains = []
        chains.extend(self._detect_di_breaks())
        chains.extend(self._detect_navigation_breaks())
        chains.extend(self._detect_intent_breaks())
        chains.extend(self._detect_data_flow_breaks())
        return chains

    def _detect_di_breaks(self) -> List[BrokenChain]:
        """Dependency Injection zincirindeki kopuklukları bul."""
        breaks = []
        
        # @Inject veya @HiltInject ile işaretlenmiş node'ları bul
        injected_nodes = [
            (node, data) for node, data in self.graph.nodes(data=True)
            if data.get('annotation') in ['@Inject', '@HiltInject', '@AndroidEntryPoint']
        ]
        
        for node, data in injected_nodes:
            # Constructor parametrelerini kontrol et
            constructor_params = data.get('constructor_params', [])
            for param in constructor_params:
                param_type = param.get('type')
                if param_type:
                    # Bu tip graf var mı?
                    if not self._node_exists_with_type(param_type):
                        breaks.append(BrokenChain(
                            chain_type="DI",
                            start_node=data.get('file', 'unknown'),
                            end_node=param_type,
                            missing_link=param_type,
                            description=f"{node} sınıfı {param_type} bağımlılığını enjekte edemiyor.",
                            severity="CRITICAL",
                            fix_suggestion=f"{param_type} için bir Module tanımlayın veya @Provide ekleyin."
                        ))
        
        # Module sınıflarında eksik @Provides
        module_nodes = [
            (node, data) for node, data in self.graph.nodes(data=True)
            if data.get('annotation') == '@Module' or data.get('annotation') == '@InstallIn'
        ]
        
        for node, data in module_nodes:
            provided_types = data.get('provides', [])
            # Module'da tanımlanan ama implementasyonu olmayan tipler
            for p_type in provided_types:
                if not self._node_exists_with_type(p_type):
                    breaks.append(BrokenChain(
                        chain_type="DI",
                        start_node=data.get('file', 'unknown'),
                        end_node=p_type,
                        missing_link=p_type,
                        description=f"Module {node}, {p_type} sağlıyor ama implementasyon bulunamadı.",
                        severity="WARNING",
                        fix_suggestion=f"{p_type} sınıfının varlığını kontrol edin."
                    ))
        
        return breaks

    def _detect_navigation_breaks(self) -> List[BrokenChain]:
        """Navigation Graph ve kod arasındaki uyumsuzlukları bul."""
        breaks = []
        
        # nav_graph.xml'deki destination'ları bul
        nav_destinations = set()
        for node, data in self.graph.nodes(data=True):
            if data.get('file', '').endswith('nav_graph.xml'):
                nav_destinations.update(data.get('destinations', []))
        
        # Kod içindeki navigate çağrılarını bul
        navigate_calls = []
        for node, data in self.graph.nodes(data=True):
            if 'navigate' in data.get('methods', []):
                navigate_calls.extend(data.get('navigate_targets', []))
        
        # Graf'ta olmayan destination'ları tespit et
        for target in navigate_calls:
            if target not in nav_destinations:
                # Belki action ID'dir
                if not self._action_exists(target):
                    breaks.append(BrokenChain(
                        chain_type="NAVIGATION",
                        start_node=data.get('file', 'unknown'),
                        end_node=target,
                        missing_link=target,
                        description=f"navigate({target}) çağrısı graf'ta tanımlı değil.",
                        severity="CRITICAL",
                        fix_suggestion=f"nav_graph.xml'e {target} destination'ını ekleyin."
                    ))
        
        return breaks

    def _detect_intent_breaks(self) -> List[BrokenChain]:
        """Intent filter ve başlatma uyumsuzluklarını bul."""
        breaks = []
        
        # Manifest'teki Activity/Service filtrelerini al
        manifest_filters = {}
        for node, data in self.graph.nodes(data=True):
            if data.get('component_type') in ['activity', 'service', 'receiver']:
                filters = data.get('intent_filters', [])
                for f in filters:
                    if 'action' in f:
                        manifest_filters[f['action']] = data.get('name')
        
        # Kod içindeki Implicit Intent çağrılarını kontrol et
        for node, data in self.graph.nodes(data=True):
            implicit_intents = data.get('implicit_intents', [])
            for intent_action in implicit_intents:
                if intent_action not in manifest_filters:
                    breaks.append(BrokenChain(
                        chain_type="INTENT",
                        start_node=data.get('file', 'unknown'),
                        end_node=intent_action,
                        missing_link=intent_action,
                        description=f"Implicit Intent ({intent_action}) için hedef bulunamadı.",
                        severity="CRITICAL",
                        fix_suggestion=f"AndroidManifest.xml'e {intent_action} action'ına sahip component ekleyin."
                    ))
        
        return breaks

    def _detect_data_flow_breaks(self) -> List[BrokenChain]:
        """LiveData/Flow veri akışındaki kopuklukları bul."""
        breaks = []
        
        # ViewModel'de tanımlanan LiveData/Flow'ları bul
        viewmodel_flows = {}
        for node, data in self.graph.nodes(data=True):
            if 'ViewModel' in data.get('parent_class', ''):
                flows = data.get('observable_fields', [])
                for flow in flows:
                    viewmodel_flows[flow] = node
        
        # Observer olarak kaydedilenleri bul
        observers = []
        for node, data in self.graph.nodes(data=True):
            observers.extend(data.get('observers', []))
        
        # Gözlemlenmeyen Flow'lar
        for flow_name, vm_node in viewmodel_flows.items():
            if flow_name not in observers:
                breaks.append(BrokenChain(
                    chain_type="DATA_FLOW",
                    start_node=vm_node,
                    end_node=flow_name,
                    missing_link=flow_name,
                    description=f"{flow_name} kimse tarafından gözlemlenmiyor (ölü kod).",
                    severity="WARNING",
                    fix_suggestion="İlgili UI component'inde observe() ekleyin veya gereksizse silin."
                ))
        
        return breaks

    def _node_exists_with_type(self, type_name: str) -> bool:
        """Graf'ta belirli tipe sahip node var mı?"""
        for node, data in self.graph.nodes(data=True):
            if data.get('name') == type_name or data.get('simple_name') == type_name:
                return True
        return False

    def _action_exists(self, action_id: str) -> bool:
        """Navigation action var mı?"""
        for node, data in self.graph.nodes(data=True):
            if action_id in data.get('actions', []):
                return True
        return False

    def generate_report(self, breaks: List[BrokenChain]) -> str:
        if not breaks:
            return "✅ Kırık zincir tespit edilmedi. Tüm akışlar sağlam!"
        
        report = "## 🚨 Kırık Zincir Analizi\n\n"
        
        # Kritik olanları önce göster
        critical = [b for b in breaks if b.severity == "CRITICAL"]
        warnings = [b for b in breaks if b.severity == "WARNING"]
        
        if critical:
            report += "### 🔴 Kritik Sorunlar\n\n"
            for i, b in enumerate(critical, 1):
                report += f"**{i}. {b.chain_type} Kopukluğu**\n"
                report += f"- **Açıklama:** {b.description}\n"
                report += f"- **Eksik Bağ:** `{b.missing_link}`\n"
                report += f"- **Çözüm:** {b.fix_suggestion}\n\n"
        
        if warnings:
            report += "### ⚠️ Uyarılar\n\n"
            for i, b in enumerate(warnings, 1):
                report += f"**{i}. {b.chain_type}**\n"
                report += f"- {b.description}\n"
                report += f"- Öneri: {b.fix_suggestion}\n\n"
        
        report += f"**Toplam:** {len(breaks)} sorun ({len(critical)} kritik, {len(warnings)} uyarı)"
        return report
