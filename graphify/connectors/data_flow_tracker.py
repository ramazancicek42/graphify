"""
Android Data Flow Tracker: Room Database & DataStore Analysis
Tracks: Entities, DAOs, Flows, LiveData, Coroutines
Optimized for Termux (Lazy Loading)
"""
import os
import re
from typing import Dict, List, Set, Optional
import networkx as nx

class DataFlowTracker:
    def __init__(self):
        self.entities: Dict[str, dict] = {}  # Table name -> {fields, type}
        self.daos: Dict[str, dict] = {}      # DAO class -> {methods, queries}
        self.repositories: Dict[str, dict] = {} # Repo -> {dao_calls}
        self.flows: List[dict] = []          # Flow/LiveData chains

    def scan_directory(self, root_path: str):
        """Room ve DataStore yapılarını tara."""
        print(f"💾 Data Flow Tracker taraması başlatılıyor: {root_path}")
        
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
        
        # 1. Room Entity Tespiti
        # @Entity(tableName = "users")
        if "@Entity" in content:
            self._parse_entity(fname, fpath, content)
        
        # 2. DAO Tespiti
        # @Dao interface UserDao
        if "@Dao" in content:
            self._parse_dao(fname, fpath, content)
        
        # 3. Repository Pattern
        if "Repository" in fname or "repository" in fpath.lower():
            self._parse_repository(fname, fpath, content)
        
        # 4. Flow / LiveData Kullanımları
        if "Flow<" in content or "LiveData<" in content or "StateFlow" in content:
            self._parse_reactive(fname, fpath, content)
        
        # 5. DataStore Usage
        if "DataStore" in content:
            self._parse_datastore(fname, fpath, content)

    def _parse_entity(self, fname: str, fpath: str, content: str):
        """@Entity sınıflarını ve tablolarını çıkar."""
        # Tablo ismi
        table_match = re.search(r'@Entity\(tableName\s*=\s*"(\w+)"\)', content)
        table_name = table_match.group(1) if table_match else fname.replace(".kt", "").replace(".java", "")
        
        # Alanlar (Fields)
        fields = []
        # Primay Key
        pk_match = re.search(r'@PrimaryKey(?:\(autoGenerate\s*=\s*true\))?\s+val\s+(\w+)', content)
        pk_field = pk_match.group(1) if pk_match else None
        
        # Tüm alanları bul (val/var)
        field_matches = re.findall(r'(?:val|var)\s+(\w+)\s*:\s*(\w+)', content)
        for field_name, field_type in field_matches:
            if field_name not in ["toString", "hashCode", "equals"]: # Metod değilse
                fields.append({"name": field_name, "type": field_type})
        
        self.entities[table_name] = {
            "file": fname,
            "path": fpath,
            "table_name": table_name,
            "primary_key": pk_field,
            "fields": fields,
            "relations": [] # Foreign key analizleri için
        }

    def _parse_dao(self, fname: str, fpath: str, content: str):
        """@DAO interfacelerini ve SQL sorgularını çıkar."""
        # Interface/Class ismi
        class_match = re.search(r'(?:interface|class)\s+(\w+)(?:\s*:|\s*\{)', content)
        class_name = class_match.group(1) if class_match else fname
        
        methods = []
        # @Query, @Insert, @Update, @Delete
        queries = re.findall(r'@Query\("([^"]+)"\)', content)
        inserts = len(re.findall(r'@Insert', content))
        updates = len(re.findall(r'@Update', content))
        deletes = len(re.findall(r'@Delete', content))
        
        # Metod imzaları
        method_sigs = re.findall(r'(?:suspend\s+)?fun\s+(\w+)\s*\([^)]*\)\s*:?[^{]+', content)
        
        for q in queries:
            # Hangi tabloya dokunduğunu bul (basit regex)
            touched_tables = re.findall(r'FROM\s+(\w+)|INTO\s+(\w+)|UPDATE\s+(\w+)|DELETE\s+FROM\s+(\w+)', q, re.IGNORECASE)
            tables = [t for group in touched_tables for t in group if t]
            
            methods.append({
                "query": q,
                "tables": tables,
                "type": "QUERY"
            })
        
        self.daos[class_name] = {
            "file": fname,
            "path": fpath,
            "methods": methods,
            "inserts": inserts,
            "updates": updates,
            "deletes": deletes
        }

    def _parse_repository(self, fname: str, fpath: str, content: str):
        """Repository sınıflarını ve DAO çağrılarını izle."""
        calls = []
        # dao.someMethod() pattern
        dao_calls = re.findall(r'(\w+)\.(\w+)\s*\(', content)
        for dao_var, method in dao_calls:
            calls.append({"dao_var": dao_var, "method": method})
        
        self.repositories[fname] = {
            "file": fname,
            "path": fpath,
            "dao_calls": calls
        }

    def _parse_reactive(self, fname: str, fpath: str, content: str):
        """Flow ve LiveData akışlarını haritala."""
        flows = []
        # flow { }, liveData { }, stateIn, sharedFlow
        flow_defs = re.findall(r'(?:val|var)\s+(\w+)\s*=\s*(?:flow|liveData|stateIn|sharedFlow)', content)
        for fd in flow_defs:
            flows.append({"name": fd, "type": "FLOW"})
        
        self.flows.extend([{
            "file": fname,
            "path": fpath,
            "name": f["name"],
            "type": f["type"]
        } for f in flows])

    def _parse_datastore(self, fname: str, fpath: str, content: str):
        """Jetpack DataStore kullanımlarını tespit et."""
        # preferencesDataStore veya protoDataStore
        ds_match = re.search(r'val\s+(\w+)\s*by\s*preferencesDataStore', content)
        if ds_match:
            print(f"📦 DataStore found: {ds_match.group(1)} in {fname}")

    def build_graph(self, G: Optional[nx.DiGraph] = None) -> nx.DiGraph:
        """Veri akış grafını oluştur."""
        if G is None:
            G = nx.DiGraph()
        
        # 1. Entity (Table) Node'ları
        for tname, data in self.entities.items():
            node_id = f"TABLE:{tname}"
            G.add_node(node_id, type="db_table", file=data["file"], pk=data["primary_key"])
            
            for field in data["fields"]:
                field_node = f"FIELD:{tname}.{field['name']}"
                G.add_node(field_node, type="db_column", dtype=field["type"])
                G.add_edge(node_id, field_node, relation="has_column")
        
        # 2. DAO Node'ları
        for dname, data in self.daos.items():
            node_id = f"DAO:{dname}"
            G.add_node(node_id, type="dao_interface", file=data["file"])
            
            for method in data["methods"]:
                for tbl in method["tables"]:
                    tbl_node = f"TABLE:{tbl}"
                    if G.has_node(tbl_node):
                        G.add_edge(node_id, tbl_node, relation="queries", query=method["query"][:50])
        
        # 3. Repository -> DAO Bağlantıları
        for rname, data in self.repositories.items():
            node_id = f"REPO:{rname}"
            G.add_node(node_id, type="repository", file=data["file"])
            
            # Basit eşleştirme: DAO değişken adı ile DAO sınıfı
            for call in data["dao_calls"]:
                # Bu kısım gelişmiş equating gerektirir, şimdilik genel bağlanıyor
                pass
        
        return G
