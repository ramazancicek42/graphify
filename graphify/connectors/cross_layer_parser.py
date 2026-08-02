"""
Cross-Layer Parser for Full-Stack Knowledge Graph

Bu modül, farklı katmanlardaki (Frontend, Backend, Database) kod parçalarını
tarayarak aralarındaki bağlantıları ortaya çıkarır.

Özellikler:
- Mobil/Web frontend'deki API çağrılarını tespit eder
- Backend route/endpoint tanımlamalarını parse eder
- SQL tabloları ve ORM modellerini analiz eder
- Çapraz katman bağlantılarını kurar
"""

import re
import ast
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional, Any
from dataclasses import dataclass, field
from enum import Enum


class LayerType(Enum):
    """Uygulama katmanları"""
    FRONTEND = "frontend"
    BACKEND = "backend"
    DATABASE = "database"
    API = "api"


class ConnectionType(Enum):
    """Bağlantı türleri"""
    CALLS_API = "calls_api"
    HANDLES_REQUEST = "handles_request"
    QUERIES_TABLE = "queries_table"
    UPDATES_TABLE = "updates_table"
    DELETES_FROM_TABLE = "deletes_from_table"
    INSERTS_INTO_TABLE = "inserts_into_table"
    IMPORTS_MODULE = "imports_module"
    EXTENDS_MODEL = "extends_model"


@dataclass
class APICall:
    """Frontend'deki API çağrısı"""
    file_path: str
    line_number: int
    method: str  # GET, POST, PUT, DELETE, etc.
    endpoint: str  # /api/v1/users gibi
    function_name: str  # Çağrıyı yapan fonksiyon
    payload_vars: List[str] = field(default_factory=list)
    layer: LayerType = LayerType.FRONTEND


@dataclass
class APIEndpoint:
    """Backend'deki API endpoint"""
    file_path: str
    line_number: int
    method: str
    path: str
    handler_function: str
    framework: str  # fastapi, flask, django, express, gin, etc.
    layer: LayerType = LayerType.BACKEND


@dataclass
class TableReference:
    """SQL tablo referansı"""
    file_path: str
    line_number: int
    table_name: str
    operation: str  # SELECT, INSERT, UPDATE, DELETE
    context_function: Optional[str] = None
    layer: LayerType = LayerType.DATABASE


@dataclass
class SchemaTable:
    """Veritabanı şema tablosu"""
    file_path: str
    table_name: str
    columns: Dict[str, str] = field(default_factory=dict)
    primary_key: Optional[str] = None
    foreign_keys: Dict[str, str] = field(default_factory=dict)  # column -> referenced_table
    layer: LayerType = LayerType.DATABASE


class CrossLayerParser:
    """
    Çok katmanlı projeleri tarayarak full-stack bilgi grafiği oluşturur.
    
    Kullanım:
        parser = CrossLayerParser()
        parser.scan_directory("/path/to/project")
        graph = parser.build_graph()
    """
    
    # Frontend API çağrı pattern'leri
    FRONTEND_PATTERNS = {
        # JavaScript/TypeScript fetch
        'fetch': r'fetch\s*\(\s*[\'"`](/[^\'"`]+)[\'"`]',
        # Axios calls
        'axios_get': r'axios\.get\s*\(\s*[\'"`](/[^\'"`]+)[\'"`]',
        'axios_post': r'axios\.post\s*\(\s*[\'"`](/[^\'"`]+)[\'"`]',
        'axios_put': r'axios\.put\s*\(\s*[\'"`](/[^\'"`]+)[\'"`]',
        'axios_delete': r'axios\.delete\s*\(\s*[\'"`](/[^\'"`]+)[\'"`]',
        # Axios with template literals (e.g., `${API_BASE}/users/${userId}`)
        'axios_get_tpl': r'axios\.get\s*\(\s*[\'"`]([^\'"`]+)[\'"`]',
        'axios_post_tpl': r'axios\.post\s*\(\s*[\'"`]([^\'"`]+)[\'"`]',
        'axios_put_tpl': r'axios\.put\s*\(\s*[\'"`]([^\'"`]+)[\'"`]',
        'axios_delete_tpl': r'axios\.delete\s*\(\s*[\'"`]([^\'"`]+)[\'"`]',
        # Generic HTTP methods
        'http_get': r'(?:http|https?)\.get\s*\(\s*[\'"`](/[^\'"`]+)[\'"`]',
        'http_post': r'(?:http|https?)\.post\s*\(\s*[\'"`](/[^\'"`]+)[\'"`]',
        'http_put': r'(?:http|https?)\.put\s*\(\s*[\'"`](/[^\'"`]+)[\'"`]',
        'http_delete': r'(?:http|https?)\.delete\s*\(\s*[\'"`](/[^\'"`]+)[\'"`]',
        # React Query / SWR
        'react_query': r'useQuery\s*\(\s*[\'"`][^\'"`]+[\'"`]\s*,\s*.*?(?:fetch|get|post)\s*\(\s*[\'"`](/[^\'"`]+)[\'"`]',
        # Swift URLSession
        'swift_url': r'URLSession\.shared\.dataTask\(with:\s*URL\(string:\s*"([^"]+)"',
        # Kotlin Retrofit
        'kotlin_retrofit': r'@(GET|POST|PUT|DELETE)\("([^"]+)"',
        # Dart HTTP (Flutter)
        'dart_http': r'http\.(get|post|put|delete)\s*\(\s*Uri\.parse\s*\(\s*[\'"`](/[^\'"`]+)[\'"`]',
    }
    
    # Backend route pattern'leri
    BACKEND_PATTERNS = {
        # FastAPI
        'fastapi_get': r'@app\.get\s*\(\s*[\'"`](/[^\'"`]+)[\'"`]',
        'fastapi_post': r'@app\.post\s*\(\s*[\'"`](/[^\'"`]+)[\'"`]',
        'fastapi_put': r'@app\.put\s*\(\s*[\'"`](/[^\'"`]+)[\'"`]',
        'fastapi_delete': r'@app\.delete\s*\(\s*[\'"`](/[^\'"`]+)[\'"`]',
        # Flask
        'flask_route': r'@(?:app|blueprint)\.route\s*\(\s*[\'"`](/[^\'"`]+)[\'"`]',
        # Django
        'django_path': r'path\s*\(\s*[\'"`]^(?P<path>[^\'"`]+)[\'"`]',
        'django_url': r'url\s*\(\s*r?[\'"`]^(?P<path>[^\'"`]+)[\'"`]',
        # Express.js
        'express_get': r'app\.get\s*\(\s*[\'"`](/[^\'"`]+)[\'"`]',
        'express_post': r'app\.post\s*\(\s*[\'"`](/[^\'"`]+)[\'"`]',
        'express_put': r'app\.put\s*\(\s*[\'"`](/[^\'"`]+)[\'"`]',
        'express_delete': r'app\.delete\s*\(\s*[\'"`](/[^\'"`]+)[\'"`]',
        # Go Gin
        'gin_get': r'\.GET\s*\(\s*[\'"`](/[^\'"`]+)[\'"`]',
        'gin_post': r'\.POST\s*\(\s*[\'"`](/[^\'"`]+)[\'"`]',
        'gin_put': r'\.PUT\s*\(\s*[\'"`](/[^\'"`]+)[\'"`]',
        'gin_delete': r'\.DELETE\s*\(\s*[\'"`](/[^\'"`]+)[\'"`]',
        # Spring Boot
        'spring_get': r'@GetMapping\s*\(\s*"(?P<path>[^"]+)"',
        'spring_post': r'@PostMapping\s*\(\s*"(?P<path>[^"]+)"',
        'spring_put': r'@PutMapping\s*\(\s*"(?P<path>[^"]+)"',
        'spring_delete': r'@DeleteMapping\s*\(\s*"(?P<path>[^"]+)"',
    }
    
    # SQL pattern'leri
    SQL_PATTERNS = {
        'select': r'SELECT\s+(?:.*?)\s+FROM\s+[\'"`]?(\w+)[\'"`]?',
        'insert': r'INSERT\s+INTO\s+[\'"`]?(\w+)[\'"`]?',
        'update': r'UPDATE\s+[\'"`]?(\w+)[\'"`]?\s+SET',
        'delete': r'DELETE\s+FROM\s+[\'"`]?(\w+)[\'"`]?',
        'join': r'JOIN\s+[\'"`]?(\w+)[\'"`]?',
    }
    
    # ORM pattern'leri
    ORM_PATTERNS = {
        # SQLAlchemy
        'sqlalchemy_table': r'class\s+(\w+)\s*\(\s*Base\s*\)',
        'sqlalchemy_tablename': r'__tablename__\s*=\s*[\'"`](\w+)[\'"`]',
        # Prisma
        'prisma_model': r'model\s+(\w+)\s*\{',
        # Django ORM
        'django_model': r'class\s+(\w+)\s*\(\s*models\.Model\s*\)',
        # Room (Android)
        'room_entity': r'@Entity\(tableName\s*=\s*"(?P<table>\w+)"',
    }
    
    def __init__(self):
        self.api_calls: List[APICall] = []
        self.api_endpoints: List[APIEndpoint] = []
        self.table_refs: List[TableReference] = []
        self.schema_tables: Dict[str, SchemaTable] = {}
        self.file_extensions = {
            'frontend': ['.js', '.jsx', '.ts', '.tsx', '.vue', '.svelte', '.swift', '.kt', '.dart', '.java'],
            'backend': ['.py', '.js', '.jsx', '.ts', '.tsx', '.go', '.java', '.php', '.rb'],
            'database': ['.sql', '.py', '.js', '.ts', '.go', '.java', '.prisma'],
        }
    
    def scan_directory(self, root_path: str) -> 'CrossLayerParser':
        """
        Proje dizinini tarayarak tüm katmanlardan bilgi toplar.
        
        Args:
            root_path: Tarancak proje kök dizini
            
        Returns:
            Kendi referansı (method chaining için)
        """
        root = Path(root_path)
        
        if not root.exists():
            raise FileNotFoundError(f"Dizin bulunamadı: {root_path}")
        
        for file_path in root.rglob('*'):
            if not file_path.is_file():
                continue
                
            rel_path = str(file_path.relative_to(root))
            
            # Frontend taraması
            if any(file_path.suffix.endswith(ext) for ext in self.file_extensions['frontend']):
                self._scan_frontend_file(str(file_path), rel_path)
            
            # Backend taraması
            if any(file_path.suffix.endswith(ext) for ext in self.file_extensions['backend']):
                self._scan_backend_file(str(file_path), rel_path)
            
            # Database taraması
            if any(file_path.suffix.endswith(ext) for ext in self.file_extensions['database']):
                self._scan_database_file(str(file_path), rel_path)
        
        return self
    
    def _scan_frontend_file(self, abs_path: str, rel_path: str):
        """Frontend dosyasını tarayarak API çağrılarını bul"""
        try:
            with open(abs_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                lines = content.split('\n')
        except Exception as e:
            print(f"⚠️  Dosya okunamadı {rel_path}: {e}")
            return
        
        # Her satırı tara
        for line_num, line in enumerate(lines, 1):
            for pattern_name, pattern in self.FRONTEND_PATTERNS.items():
                matches = re.finditer(pattern, line, re.IGNORECASE)
                
                for match in matches:
                    groups = match.groups()
                    
                    # Pattern'e göre grupları yorumla
                    if 'axios' in pattern_name or 'http' in pattern_name:
                        method = pattern_name.split('_')[1].upper()
                        endpoint = groups[0] if groups else ''
                        # Template literal'den /api/... yolunu çıkar
                        if endpoint and not endpoint.startswith('/'):
                            # ${API_BASE}/users/${userId} gibi pattern'leri parse et
                            match = re.search(r'(/api/[^\'"`]+)', endpoint)
                            if match:
                                endpoint = match.group(1)
                            else:
                                # Sadece path kısmını al
                                endpoint = re.sub(r'\$\{[^}]+\}', ':param', endpoint)
                    elif 'fetch' in pattern_name:
                        method = 'GET'  # Varsayılan, body varsa POST olabilir
                        endpoint = groups[0] if groups else ''
                    elif 'kotlin_retrofit' in pattern_name:
                        method = groups[0] if groups else 'GET'
                        endpoint = groups[1] if len(groups) > 1 else ''
                    elif 'dart_http' in pattern_name:
                        method = groups[0].upper() if groups else 'GET'
                        endpoint = groups[1] if len(groups) > 1 else ''
                    else:
                        method = 'GET'
                        endpoint = groups[0] if groups else ''
                    
                    if endpoint:
                        # Çağrıyı yapan fonksiyonu bulmaya çalış
                        func_name = self._extract_function_name(lines, line_num - 1)
                        
                        api_call = APICall(
                            file_path=rel_path,
                            line_number=line_num,
                            method=method,
                            endpoint=endpoint,
                            function_name=func_name or 'unknown'
                        )
                        self.api_calls.append(api_call)
    
    def _scan_backend_file(self, abs_path: str, rel_path: str):
        """Backend dosyasını tarayarak endpoint'leri ve SQL referanslarını bul"""
        try:
            with open(abs_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                lines = content.split('\n')
        except Exception as e:
            print(f"⚠️  Dosya okunamadı {rel_path}: {e}")
            return
        
        # Endpoint'leri bul
        for line_num, line in enumerate(lines, 1):
            for pattern_name, pattern in self.BACKEND_PATTERNS.items():
                matches = re.finditer(pattern, line, re.IGNORECASE)
                
                for match in matches:
                    groups = match.groups()
                    
                    # Framework tespiti
                    if 'fastapi' in pattern_name:
                        framework = 'fastapi'
                        method = pattern_name.split('_')[1].upper()
                        path = groups[0] if groups else ''
                    elif 'flask' in pattern_name:
                        framework = 'flask'
                        method = 'ANY'
                        path = groups[0] if groups else ''
                    elif 'express' in pattern_name:
                        framework = 'express'
                        method = pattern_name.split('_')[1].upper()
                        path = groups[0] if groups else ''
                    elif 'gin' in pattern_name:
                        framework = 'gin'
                        method = pattern_name.split('_')[1].upper()
                        path = groups[0] if groups else ''
                    elif 'spring' in pattern_name:
                        framework = 'spring'
                        method = pattern_name.split('_')[1].replace('mapping', '').upper()
                        path = groups[0] if groups else ''
                    else:
                        framework = 'unknown'
                        method = 'GET'
                        path = groups[0] if groups else ''
                    
                    if path:
                        # Handler fonksiyonunu bul
                        handler = self._extract_handler_name(lines, line_num - 1, framework)
                        
                        endpoint = APIEndpoint(
                            file_path=rel_path,
                            line_number=line_num,
                            method=method,
                            path=path,
                            handler_function=handler or 'unknown',
                            framework=framework
                        )
                        self.api_endpoints.append(endpoint)
        
        # SQL referanslarını bul
        self._extract_sql_references(content, lines, rel_path)
        
        # ORM modellerini bul
        self._extract_orm_models(content, abs_path, rel_path)
    
    def _scan_database_file(self, abs_path: str, rel_path: str):
        """SQL ve schema dosyalarını tara"""
        try:
            with open(abs_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                lines = content.split('\n')
        except Exception as e:
            print(f"⚠️  Dosya okunamadı {rel_path}: {e}")
            return
        
        # SQL dosyası ise
        if abs_path.endswith('.sql'):
            for line_num, line in enumerate(lines, 1):
                # CREATE TABLE
                create_match = re.search(r'CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?[\'"`]?(\w+)[\'"`]?', line, re.IGNORECASE)
                if create_match:
                    table_name = create_match.group(1)
                    self.schema_tables[table_name] = SchemaTable(
                        file_path=rel_path,
                        table_name=table_name
                    )
                
                # Foreign Key
                fk_match = re.search(r'FOREIGN\s+KEY\s*\((\w+)\)\s*REFERENCES\s+[\'"`]?(\w+)[\'"`]?', line, re.IGNORECASE)
                if fk_match and self.schema_tables:
                    last_table = list(self.schema_tables.values())[-1]
                    last_table.foreign_keys[fk_match.group(1)] = fk_match.group(2)
                
                # Primary Key
                pk_match = re.search(r'PRIMARY\s+KEY\s*\((\w+)\)', line, re.IGNORECASE)
                if pk_match and self.schema_tables:
                    last_table = list(self.schema_tables.values())[-1]
                    last_table.primary_key = pk_match.group(1)
        
        # Prisma schema
        elif abs_path.endswith('.prisma'):
            self._extract_prisma_schema(content, lines, rel_path)
    
    def _extract_sql_references(self, content: str, lines: List[str], rel_path: str):
        """Kod içindeki SQL referanslarını çıkar"""
        current_function = None
        
        for line_num, line in enumerate(lines, 1):
            # Fonksiyon tanımını takip et
            func_match = re.search(r'(?:def|function|func)\s+(\w+)', line)
            if func_match:
                current_function = func_match.group(1)
            
            # SQL pattern'lerini ara
            for op_type, pattern in self.SQL_PATTERNS.items():
                matches = re.finditer(pattern, line, re.IGNORECASE)
                
                for match in matches:
                    table_name = match.group(1)
                    
                    table_ref = TableReference(
                        file_path=rel_path,
                        line_number=line_num,
                        table_name=table_name,
                        operation=op_type.upper(),
                        context_function=current_function
                    )
                    self.table_refs.append(table_ref)
    
    def _extract_orm_models(self, content: str, abs_path: str, rel_path: str):
        """ORM model tanımlamalarını çıkar"""
        try:
            # Python dosyası ise AST ile parse et
            if abs_path.endswith('.py'):
                tree = ast.parse(content)
                
                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef):
                        # Base sınıfından türeyen modeller
                        for base in node.bases:
                            if isinstance(base, ast.Name):
                                if base.id == 'Base':  # SQLAlchemy DeclarativeBase
                                    self._process_sqlalchemy_model(node, rel_path, content)
                                elif base.id == 'Document':  # MongoDB ODM
                                    pass  # İleride eklenebilir
                            elif isinstance(base, ast.Attribute):
                                if base.attr == 'Model':  # Django ORM (models.Model)
                                    self._process_django_model(node, rel_path)
                                elif base.attr == 'Base':  # SQLAlchemy (module.Base)
                                    self._process_sqlalchemy_model(node, rel_path, content)
        except SyntaxError:
            pass  # Parse edilemeyen dosyaları atla
    
    def _process_django_model(self, node: ast.ClassDef, rel_path: str):
        """Django modelini işle"""
        table_name = node.name.lower()  # Django otomatik çoğul yapmazsa
        
        schema_table = SchemaTable(
            file_path=rel_path,
            table_name=table_name,
        )
        
        # Alanları çıkar
        for item in node.body:
            if isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name):
                        schema_table.columns[target.id] = 'unknown'
        
        self.schema_tables[table_name] = schema_table
    
    def _process_sqlalchemy_model(self, node: ast.ClassDef, rel_path: str, content: str):
        """SQLAlchemy modelini işle"""
        # Tablo adını bul
        table_name = None
        for item in node.body:
            if isinstance(item, ast.AnnAssign):
                target = item.target
                value = item.value
            elif isinstance(item, ast.Assign) and item.targets:
                target = item.targets[0]
                value = item.value
            else:
                continue
            if isinstance(target, ast.Name) and target.id == '__tablename__':
                if isinstance(value, ast.Constant):
                    table_name = value.value
                break
        
        if not table_name:
            table_name = node.name.lower()
        
        schema_table = SchemaTable(
            file_path=rel_path,
            table_name=table_name,
        )
        
        self.schema_tables[table_name] = schema_table
    
    def _extract_prisma_schema(self, content: str, lines: List[str], rel_path: str):
        """Prisma schema dosyasını parse et"""
        current_model = None
        
        for line_num, line in enumerate(lines, 1):
            # Model tanımı
            model_match = re.search(r'model\s+(\w+)\s*\{', line)
            if model_match:
                current_model = SchemaTable(
                    file_path=rel_path,
                    table_name=model_match.group(1)
                )
                self.schema_tables[model_match.group(1)] = current_model
                continue
            
            # Model sonu
            if line.strip() == '}' and current_model:
                current_model = None
                continue
            
            # Alan tanımları
            if current_model:
                field_match = re.search(r'^\s*(\w+)\s+(\w+)', line)
                if field_match:
                    field_name = field_match.group(1)
                    field_type = field_match.group(2)
                    current_model.columns[field_name] = field_type
                    
                    # ID alanı
                    if '@id' in line:
                        current_model.primary_key = field_name
                    
                    # Foreign key
                    if '@relation' in line:
                        ref_match = re.search(r'references:\s*\[(\w+)\]', line)
                        if ref_match:
                            current_model.foreign_keys[field_name] = ref_match.group(1)
    
    def _extract_function_name(self, lines: List[str], line_index: int) -> Optional[str]:
        """Verilen satırın bağlamındaki fonksiyon adını bul"""
        # Yukarı doğru fonksiyon tanımı ara
        for i in range(line_index, max(0, line_index - 50), -1):
            line = lines[i]
            
            # JavaScript/TypeScript function
            match = re.search(r'function\s+(\w+)', line)
            if match:
                return match.group(1)
            
            # Arrow function assignment
            match = re.search(r'(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s*)?\(', line)
            if match:
                return match.group(1)
            
            # Python function
            match = re.search(r'def\s+(\w+)', line)
            if match:
                return match.group(1)
            
            # Swift function
            match = re.search(r'func\s+(\w+)', line)
            if match:
                return match.group(1)
            
            # Kotlin function
            match = re.search(r'fun\s+(\w+)', line)
            if match:
                return match.group(1)
            
            # Dart function
            match = re.search(r'(?:void|Future|Widget)\s+(\w+)', line)
            if match:
                return match.group(1)
        
        return None
    
    def _extract_handler_name(self, lines: List[str], line_index: int, framework: str) -> Optional[str]:
        """Decorator'dan sonraki handler fonksiyonunu bul"""
        # Decorator'dan sonraki birkaç satıra bak
        for i in range(line_index + 1, min(len(lines), line_index + 5)):
            line = lines[i].strip()
            
            # Python (FastAPI, Flask, Django)
            match = re.search(r'(?:async\s+)?def\s+(\w+)', line)
            if match:
                return match.group(1)
            
            # JavaScript/TypeScript (Express)
            match = re.search(r'(?:async\s+)?(?:function\s+)?(\w+)', line)
            if match and '=>' in line:
                return match.group(1)
            
            # Go (Gin)
            match = re.search(r'func\s+\w*\s*\((?:\w+\s+\*\w+,?\s*)?c\s+\*\w+\.Context\)', line)
            if match:
                # Go'da handler genelde anonymous, context'ten al
                return 'handler'
        
        return None
    
    def build_connections(self) -> List[Tuple[Any, ConnectionType, Any]]:
        """
        Tespit edilen öğeler arasında bağlantılar kurar.
        
        Returns:
            (source, connection_type, target) tuple'ları listesi
        """
        connections = []
        
        # 1. API çağrıları -> API endpoint'leri eşleştir
        for call in self.api_calls:
            for endpoint in self.api_endpoints:
                if self._match_endpoint(call.endpoint, endpoint.path):
                    connections.append((call, ConnectionType.CALLS_API, endpoint))
        
        # 2. API endpoint'leri -> SQL tabloları eşleştir
        for endpoint in self.api_endpoints:
            # Endpoint'in handler fonksiyonunu kullanan SQL referanslarını bul
            for ref in self.table_refs:
                if ref.context_function == endpoint.handler_function:
                    conn_type = self._operation_to_connection(ref.operation)
                    connections.append((endpoint, conn_type, ref))
        
        # 3. SQL referansları -> Şema tabloları eşleştir
        for ref in self.table_refs:
            if ref.table_name in self.schema_tables:
                schema_table = self.schema_tables[ref.table_name]
                conn_type = self._operation_to_connection(ref.operation)
                connections.append((ref, conn_type, schema_table))
        
        return connections
    
    def _match_endpoint(self, call_path: str, endpoint_path: str) -> bool:
        """
        API çağrısı ile endpoint'i eşleştirir.
        Parametreli route'ları da destekler (:id, {id}, <id> vb.)
        """
        # Normalize et
        call_normalized = re.sub(r'/+', '/', call_path).rstrip('/')
        endpoint_normalized = re.sub(r'/+', '/', endpoint_path).rstrip('/')
        
        # Exact match
        if call_normalized == endpoint_normalized:
            return True
        
        # Parametreli route'ları normalize et
        # :id, {id}, <id>, %d, %s gibi parametreleri \w+ ile değiştir
        endpoint_pattern = re.sub(r'[:<{\%][\w\d]+[}>]?', r'\\w+', endpoint_normalized)
        endpoint_pattern = re.sub(r'%[ds]', r'\\w+', endpoint_pattern)
        
        return bool(re.fullmatch(endpoint_pattern, call_normalized))
    
    def _operation_to_connection(self, operation: str) -> ConnectionType:
        """SQL operasyonunu bağlantı türüne çevir"""
        op_map = {
            'SELECT': ConnectionType.QUERIES_TABLE,
            'INSERT': ConnectionType.INSERTS_INTO_TABLE,
            'UPDATE': ConnectionType.UPDATES_TABLE,
            'DELETE': ConnectionType.DELETES_FROM_TABLE,
        }
        return op_map.get(operation, ConnectionType.QUERIES_TABLE)
    
    def get_summary(self) -> Dict[str, Any]:
        """Taranan öğelerin özetini döndür"""
        return {
            'api_calls': len(self.api_calls),
            'api_endpoints': len(self.api_endpoints),
            'table_references': len(self.table_refs),
            'schema_tables': len(self.schema_tables),
            'tables': list(self.schema_tables.keys()),
        }
