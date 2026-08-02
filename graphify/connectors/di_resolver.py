"""
Android DI Graph Resolver: Hilt & Koin Dependency Injection Analyzer
Tracks: @Inject, @Provides, @Module, component dependencies
Optimized for Termux (Memory Efficient)
"""
import os
import re
from typing import Dict, List, Set, Optional
import networkx as nx

class DIGraphResolver:
    def __init__(self):
        self.modules: Dict[str, dict] = {}      # Module class -> {provides}
        self.inject_targets: Dict[str, list] = {} # Class -> [injected deps]
        self.scopes: Dict[str, str] = {}        # Class -> Scope (@Singleton, @ViewModelScoped)

    def scan_directory(self, root_path: str):
        """Hilt ve Koin yapılarını tara."""
        print(f"🔌 DI Graph Resolver taraması başlatılıyor: {root_path}")
        
        for dirpath, _, filenames in os.walk(root_path):
            if "build" in dirpath or ".gradle" in dirpath:
                continue
            
            for f in filenames:
                if not (f.endswith(".kt") or f.endswith(".java")):
                    continue
                
                fpath = os.path.join(dirpath, f)
                self._parse_file(fpath)

    def _parse_file(self, fpath: str):
        with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        
        fname = os.path.basename(fpath)
        
        # 1. Hilt Module Tespiti
        if "@Module" in content or "@InstallIn" in content:
            self._parse_hilt_module(fname, fpath, content)
        
        # 2. @Inject Kullanımları (Constructor/Field Injection)
        if "@Inject" in content:
            self._parse_injection(fname, fpath, content)
        
        # 3. Koin Module (DSL based)
        if "module {" in content or "single {" in content or "factory {" in content:
            self._parse_koin_module(fname, fpath, content)
        
        # 4. Scope Annotations
        if "@Singleton" in content or "@ViewModelScoped" in content or "@ActivityScoped" in content:
            self._parse_scopes(fname, content)

    def _parse_hilt_module(self, fname: str, fpath: str, content: str):
        """@Module sınıflarını ve @Provides metodlarını çıkar."""
        # Module sınıf ismi
        class_match = re.search(r'@Module\s+(?:object\s+)?(?:class\s+)?(\w+)', content)
        class_name = class_match.group(1) if class_match else fname
        
        provides_methods = []
        # @Provides fun provideX(): Type
        provides = re.findall(r'@Provides\s+(?:suspend\s+)?fun\s+(\w+)\s*\([^)]*\)\s*:\s*(\w+)', content)
        for method_name, return_type in provides:
            provides_methods.append({
                "method": method_name,
                "provides_type": return_type
            })
        
        # InstallIn annotation (AppComponent, ViewModelComponent vb.)
        install_match = re.search(r'@InstallIn\s*\(\s*(\w+)\s*\)', content)
        installed_in = install_match.group(1) if install_match else "Unknown"
        
        self.modules[class_name] = {
            "file": fname,
            "path": fpath,
            "type": "HILT_MODULE",
            "installed_in": installed_in,
            "provides": provides_methods
        }

    def _parse_injection(self, fname: str, fpath: str, content: str):
        """@Inject annotated constructor veya fieldları bul."""
        injected_deps = []
        
        # Constructor Injection: @Inject constructor(val repo: UserRepository)
        ctor_matches = re.findall(r'@Inject\s+constructor\s*\(([^)]+)\)', content)
        for ctor_params in ctor_matches:
            # param1: Type1, param2: Type2
            params = re.findall(r'(?:val|var)?\s*(\w+)\s*:\s*(\w+)', ctor_params)
            for param_name, param_type in params:
                injected_deps.append({
                    "name": param_name,
                    "type": param_type,
                    "injection_type": "CONSTRUCTOR"
                })
        
        # Field Injection: @Inject lateinit var repo: UserRepository
        field_matches = re.findall(r'@Inject\s+(?:lateinit\s+)?(?:val|var)\s+(\w+)\s*:\s*(\w+)', content)
        for field_name, field_type in field_matches:
            injected_deps.append({
                "name": field_name,
                "type": field_type,
                "injection_type": "FIELD"
            })
        
        if injected_deps:
            self.inject_targets[fname] = injected_deps

    def _parse_koin_module(self, fname: str, fpath: str, content: str):
        """Koin DSL modüllerini parse et."""
        # module { single { MyClass() } factory { MyViewModel() } }
        singles = re.findall(r'single\s*(?:<(\w+)>)?\s*\{\s*(?:named\("[^"]+"\)\s*)?(\w+)\s*\(', content)
        factories = re.findall(r'factory\s*(?:<(\w+)>)?\s*\{\s*(?:named\("[^"]+"\)\s*)?(\w+)\s*\(', content)
        
        # Koin modülleri genellikle global tanımlanır, fname yerine içerikten isim bul
        # Basitlik için dosya bazlı tutuyoruz
        koin_defs = []
        for type_name, instance in singles:
            koin_defs.append({"type": type_name or instance, "instance": instance, "scope": "SINGLETON"})
        for type_name, instance in factories:
            koin_defs.append({"type": type_name or instance, "instance": instance, "scope": "FACTORY"})
        
        if koin_defs:
            self.modules[f"KOIN_{fname}"] = {
                "file": fname,
                "path": fpath,
                "type": "KOIN_MODULE",
                "definitions": koin_defs
            }

    def _parse_scopes(self, fname: str, content: str):
        """Class seviyesindeki scope annotationlarını kaydet."""
        # @Singleton class MyRepository
        singleton_matches = re.findall(r'@Singleton\s+(?:class|object)\s+(\w+)', content)
        for cls in singleton_matches:
            self.scopes[cls] = "SINGLETON"
        
        vm_scoped = re.findall(r'@ViewModelScoped\s+(?:class|object)\s+(\w+)', content)
        for cls in vm_scoped:
            self.scopes[cls] = "VIEWMODEL"

    def build_graph(self, G: Optional[nx.DiGraph] = None) -> nx.DiGraph:
        """DI bağımlılık grafını oluştur."""
        if G is None:
            G = nx.DiGraph()
        
        # 1. Module Node'ları
        for mname, data in self.modules.items():
            node_id = f"MODULE:{mname}"
            G.add_node(node_id, type="di_module", kind=data["type"], file=data["file"])
            
            if data["type"] == "HILT_MODULE":
                for prov in data["provides"]:
                    type_node = f"TYPE:{prov['provides_type']}"
                    G.add_node(type_node, type="provided_type")
                    G.add_edge(node_id, type_node, relation="provides", method=prov["method"])
            
            elif data["type"] == "KOIN_MODULE":
                for defn in data.get("definitions", []):
                    type_node = f"TYPE:{defn['type']}"
                    G.add_node(type_node, type="koin_definition", scope=defn["scope"])
                    G.add_edge(node_id, type_node, relation="defines")
        
        # 2. Injection Target -> Dependency Bağlantıları
        for fname, deps in self.inject_targets.items():
            target_node = f"CLASS:{fname}"
            G.add_node(target_node, type="inject_target", file=fname)
            
            for dep in deps:
                dep_node = f"TYPE:{dep['type']}"
                # Eğer bu tip daha önce tanımlanmamışsa placeholder olarak ekle
                if not G.has_node(dep_node):
                    G.add_node(dep_node, type="dependency_placeholder")
                
                G.add_edge(target_node, dep_node, relation="injects", mode=dep["injection_type"])
        
        # 3. Scope Bilgilerini Ekle
        for cls_name, scope_type in self.scopes.items():
            node_id = f"CLASS:{cls_name}"
            if G.has_node(node_id):
                G.nodes[node_id]["scope"] = scope_type
            else:
                G.add_node(node_id, type="scoped_class", scope=scope_type)
        
        return G

    def get_dependency_chain(self, target_class: str, G: nx.DiGraph) -> List[str]:
        """Bir sınıfın tüm bağımlılık zincirini geriye doğru izle."""
        chain = []
        queue = [f"CLASS:{target_class}"]
        visited = set()
        
        while queue:
            current = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)
            chain.append(current)
            
            # Predecessors (dependencies)
            for pred in G.predecessors(current):
                if G.edges[pred, current].get("relation") == "injects":
                    queue.append(pred)
        
        return chain
