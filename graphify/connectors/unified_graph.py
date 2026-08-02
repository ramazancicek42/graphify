"""
Unified Graph Builder for Full-Stack Knowledge Graph

Cross-layer parser'dan gelen verileri alarak tek bir birleşik graf oluşturur.
Bu graf, frontend'den database'e kadar tüm zinciri temsil eder.

Özellikler:
- Çok katmanlı düğümler (Frontend, Backend, Database)
- Tip tabanlı kenarlar (CALLS_API, QUERIES_TABLE, vb.)
- Subgraph filtreleme (sorguya göre ilgili kısmı çıkarır)
- Token optimizasyonu (sadece gerekli bilgiyi LLM'e gönderir)
"""

import networkx as nx
from typing import Dict, List, Set, Tuple, Optional, Any, Union
from dataclasses import dataclass, field, asdict
from enum import Enum
import json
import hashlib

from .cross_layer_parser import (
    CrossLayerParser,
    APICall,
    APIEndpoint,
    TableReference,
    SchemaTable,
    ConnectionType,
    LayerType,
)


class NodeType(Enum):
    """Graf düğüm türleri"""
    FRONTEND_FUNCTION = "frontend_function"
    API_CALL = "api_call"
    API_ENDPOINT = "api_endpoint"
    BACKEND_HANDLER = "backend_handler"
    SQL_REFERENCE = "sql_reference"
    DATABASE_TABLE = "database_table"
    ORM_MODEL = "orm_model"


@dataclass
class GraphNode:
    """Graf düğümü"""
    id: str
    type: NodeType
    layer: LayerType
    label: str
    file_path: str
    line_number: int
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Sözlük temsili"""
        return {
            'id': self.id,
            'type': self.type.value,
            'layer': self.layer.value,
            'label': self.label,
            'file_path': self.file_path,
            'line_number': self.line_number,
            'metadata': self.metadata,
        }


@dataclass
class GraphEdge:
    """Graf kenarı"""
    source: str
    target: str
    type: ConnectionType
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Sözlük temsili"""
        return {
            'source': self.source,
            'target': self.target,
            'type': self.type.value,
            'metadata': self.metadata,
        }


class UnifiedGraphBuilder:
    """
    Full-stack bilgi grafiği oluşturucu.

    Kullanım:
        builder = UnifiedGraphBuilder()
        builder.from_directory("/path/to/project")
        graph = builder.build()

        # Subgraph çıkar
        subgraph = builder.extract_subgraph(query="Kullanıcı profil güncelleme")

        # LLM için optimize et
        context = builder.to_llm_context(subgraph)
    """

    def __init__(self):
        self.parser = CrossLayerParser()
        self.graph = nx.MultiDiGraph()
        self.nodes: Dict[str, GraphNode] = {}
        self.edges: List[GraphEdge] = []
        self._node_counter = 0

    def from_directory(self, root_path: str) -> 'UnifiedGraphBuilder':
        """
        Proje dizinini tarayarak grafı oluştur.

        Args:
            root_path: Tarancak proje kök dizini

        Returns:
            Kendi referansı (method chaining için)
        """
        self.parser.scan_directory(root_path)
        self._build_graph_from_parser()
        return self

    def from_parser(self, parser: CrossLayerParser) -> 'UnifiedGraphBuilder':
        """
        Mevcut parser'dan graf oluştur.

        Args:
            parser: Önceden taranmış CrossLayerParser örneği

        Returns:
            Kendi referansı
        """
        self.parser = parser
        self._build_graph_from_parser()
        return self

    def _generate_node_id(self, obj: Any, prefix: str) -> str:
        """Benzersiz düğüm ID'si oluştur"""
        self._node_counter += 1

        # İçeriğe dayalı hash oluştur
        if isinstance(obj, APICall):
            content = f"{obj.file_path}:{obj.line_number}:{obj.endpoint}"
        elif isinstance(obj, APIEndpoint):
            content = f"{obj.file_path}:{obj.line_number}:{obj.path}"
        elif isinstance(obj, TableReference):
            content = f"{obj.file_path}:{obj.line_number}:{obj.table_name}"
        elif isinstance(obj, SchemaTable):
            content = f"{obj.file_path}:{obj.table_name}"
        else:
            content = f"{prefix}:{self._node_counter}"

        hash_suffix = hashlib.md5(content.encode()).hexdigest()[:8]
        return f"{prefix}_{hash_suffix}"

    def _build_graph_from_parser(self):
        """Parser verilerinden grafı inşa et"""
        # API çağrılarını ekle
        for call in self.parser.api_calls:
            node_id = self._generate_node_id(call, "api_call")

            # Çağrıyı yapan fonksiyon düğümü
            func_id = self._generate_node_id(
                type('obj', (object,), {'file_path': call.file_path, 'name': call.function_name}),
                "func"
            )

            if func_id not in self.nodes:
                func_node = GraphNode(
                    id=func_id,
                    type=NodeType.FRONTEND_FUNCTION,
                    layer=LayerType.FRONTEND,
                    label=call.function_name,
                    file_path=call.file_path,
                    line_number=call.line_number,
                    metadata={'calls': [call.endpoint]}
                )
                self.nodes[func_id] = func_node
                self.graph.add_node(func_id, **func_node.to_dict())

            # API çağrı düğümü
            call_node = GraphNode(
                id=node_id,
                type=NodeType.API_CALL,
                layer=LayerType.FRONTEND,
                label=f"{call.method} {call.endpoint}",
                file_path=call.file_path,
                line_number=call.line_number,
                metadata={
                    'method': call.method,
                    'endpoint': call.endpoint,
                    'function': call.function_name,
                }
            )
            self.nodes[node_id] = call_node
            self.graph.add_node(node_id, **call_node.to_dict())

            # Fonksiyon -> API çağrı kenarı
            edge = GraphEdge(
                source=func_id,
                target=node_id,
                type=ConnectionType.CALLS_API
            )
            self.edges.append(edge)
            self.graph.add_edge(func_id, node_id, type=edge.type.value)

        # API endpoint'lerini ekle
        for endpoint in self.parser.api_endpoints:
            node_id = self._generate_node_id(endpoint, "endpoint")

            # Handler fonksiyon düğümü
            handler_id = self._generate_node_id(
                type('obj', (object,), {'file_path': endpoint.file_path, 'name': endpoint.handler_function}),
                "handler"
            )

            if handler_id not in self.nodes:
                handler_node = GraphNode(
                    id=handler_id,
                    type=NodeType.BACKEND_HANDLER,
                    layer=LayerType.BACKEND,
                    label=endpoint.handler_function,
                    file_path=endpoint.file_path,
                    line_number=endpoint.line_number,
                    metadata={
                        'framework': endpoint.framework,
                        'endpoints': [],
                    }
                )
                self.nodes[handler_id] = handler_node
                self.graph.add_node(handler_id, **handler_node.to_dict())

            # Endpoint düğümü
            endpoint_node = GraphNode(
                id=node_id,
                type=NodeType.API_ENDPOINT,
                layer=LayerType.BACKEND,
                label=f"{endpoint.method} {endpoint.path}",
                file_path=endpoint.file_path,
                line_number=endpoint.line_number,
                metadata={
                    'method': endpoint.method,
                    'path': endpoint.path,
                    'framework': endpoint.framework,
                    'handler': endpoint.handler_function,
                }
            )
            self.nodes[node_id] = endpoint_node
            self.graph.add_node(node_id, **endpoint_node.to_dict())

            # Handler -> Endpoint kenarı
            edge = GraphEdge(
                source=handler_id,
                target=node_id,
                type=ConnectionType.HANDLES_REQUEST
            )
            self.edges.append(edge)
            self.graph.add_edge(handler_id, node_id, type=edge.type.value)

            # Handler'ın endpoint listesine ekle
            self.nodes[handler_id].metadata.setdefault('endpoints', []).append(endpoint.path)

        # SQL referanslarını ekle
        for ref in self.parser.table_refs:
            node_id = self._generate_node_id(ref, "sql_ref")

            sql_node = GraphNode(
                id=node_id,
                type=NodeType.SQL_REFERENCE,
                layer=LayerType.DATABASE,
                label=f"{ref.operation} {ref.table_name}",
                file_path=ref.file_path,
                line_number=ref.line_number,
                metadata={
                    'table': ref.table_name,
                    'operation': ref.operation,
                    'function': ref.context_function,
                }
            )
            self.nodes[node_id] = sql_node
            self.graph.add_node(node_id, **sql_node.to_dict())

        # Şema tablolarını ekle
        for table_name, table in self.parser.schema_tables.items():
            node_id = self._generate_node_id(table, "table")

            table_node = GraphNode(
                id=node_id,
                type=NodeType.DATABASE_TABLE,
                layer=LayerType.DATABASE,
                label=table_name,
                file_path=table.file_path,
                line_number=0,
                metadata={
                    'columns': table.columns,
                    'primary_key': table.primary_key,
                    'foreign_keys': table.foreign_keys,
                }
            )
            self.nodes[node_id] = table_node
            self.graph.add_node(node_id, **table_node.to_dict())

        # Bağlantıları kur
        self._build_cross_layer_edges()

    def _build_cross_layer_edges(self):
        """Katmanlar arası bağlantıları oluştur"""
        connections = self.parser.build_connections()

        for source_obj, conn_type, target_obj in connections:
            # Kaynak ve hedef düğüm ID'lerini bul
            source_id = self._find_node_id_for_object(source_obj)
            target_id = self._find_node_id_for_object(target_obj)

            if source_id and target_id:
                edge = GraphEdge(
                    source=source_id,
                    target=target_id,
                    type=conn_type
                )
                self.edges.append(edge)
                self.graph.add_edge(source_id, target_id, type=conn_type.value)

    def _find_node_id_for_object(self, obj: Any) -> Optional[str]:
        """Nesneye karşılık gelen düğüm ID'sini bul"""
        for node_id, node in self.nodes.items():
            if isinstance(obj, APICall):
                if (node.type == NodeType.API_CALL and
                    node.metadata.get('endpoint') == obj.endpoint and
                    node.file_path == obj.file_path):
                    return node_id
            elif isinstance(obj, APIEndpoint):
                if (node.type == NodeType.API_ENDPOINT and
                    node.metadata.get('path') == obj.path and
                    node.file_path == obj.file_path):
                    return node_id
            elif isinstance(obj, TableReference):
                if (node.type == NodeType.SQL_REFERENCE and
                    node.metadata.get('table') == obj.table_name and
                    node.file_path == obj.file_path):
                    return node_id
            elif isinstance(obj, SchemaTable):
                if (node.type == NodeType.DATABASE_TABLE and
                    node.label == obj.table_name):
                    return node_id

        return None

    def extract_subgraph(
        self,
        query: str,
        max_depth: int = 5,
        max_nodes: int = 100
    ) -> nx.MultiDiGraph:
        """
        Sorguyla ilgili alt grafı çıkarır.

        Args:
            query: Kullanıcı sorgusu (örn: "Kullanıcı profil resmi güncellerken hata")
            max_depth: BFS arama derinliği
            max_nodes: Maksimum düğüm sayısı

        Returns:
            Filtrelenmiş alt graf
        """
        # Sorgudan anahtar kelimeleri çıkar
        keywords = self._extract_keywords(query)

        # İlgili düğümleri bul
        seed_nodes = self._find_seed_nodes(keywords)

        if not seed_nodes:
            # Eşleşme yoksa boş graf döndür
            return nx.MultiDiGraph()

        # BFS ile komşuları genişlet
        subgraph_nodes = set()
        for seed in seed_nodes:
            neighbors = self._bfs_expand(seed, max_depth, max_nodes // len(seed_nodes))
            subgraph_nodes.update(neighbors)

        # Alt grafı oluştur
        subgraph = self.graph.subgraph(subgraph_nodes).copy()

        return subgraph

    def _extract_keywords(self, query: str) -> List[str]:
        """Sorgudan anahtar kelimeleri çıkar"""
        import re

        # Türkçe ve İngilizce yaygın durdurma kelimeleri
        stop_words = {
            'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
            'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
            've', 're', 'll', 'd', 'n', 'to', 'of', 'in', 'for', 'on', 'with',
            'at', 'by', 'from', 'as', 'into', 'through', 'during', 'before',
            'after', 'above', 'below', 'between', 'under', 'again', 'further',
            'then', 'once', 'here', 'there', 'when', 'where', 'why', 'how',
            'all', 'each', 'few', 'more', 'most', 'other', 'some', 'such',
            'no', 'nor', 'not', 'only', 'own', 'same', 'so', 'than', 'too',
            'very', 'just', 'and', 'but', 'if', 'or', 'because', 'until',
            'while', 'although', 'though', 'after', 'before', 'when', 'whenever',
            'i', 'me', 'my', 'myself', 'we', 'our', 'ours', 'ourselves',
            'you', 'your', 'yours', 'yourself', 'yourselves',
            'he', 'him', 'his', 'himself', 'she', 'her', 'hers', 'herself',
            'it', 'its', 'itself', 'they', 'them', 'their', 'theirs', 'themselves',
            'what', 'which', 'who', 'whom', 'this', 'that', 'these', 'those',
            'am', 'bir', 'bu', 'şu', 'o', 'biz', 'siz', 'onlar',
            'ile', 've', 'veya', 'ama', 'fakat', 'ancak', 'ki', 'de', 'da',
            'mı', 'mi', 'mu', 'mü', 'için', 'gibi', 'kadar', 'üzere',
        }

        # Kelimeleri ayır ve normalize et
        words = re.findall(r'\b\w+\b', query.lower())

        # Durdurma kelimelerini filtrele ve benzersiz yap
        keywords = list(set(w for w in words if w not in stop_words and len(w) > 2))

        return keywords

    def _find_seed_nodes(self, keywords: List[str]) -> List[str]:
        """Anahtar kelimelerle eşleşen başlangıç düğümlerini bul"""
        seed_nodes = []

        for node_id, node in self.nodes.items():
            score = 0

            # Label'da ara
            label_lower = node.label.lower()
            for keyword in keywords:
                if keyword in label_lower:
                    score += 3

            # Metadata'da ara
            for key, value in node.metadata.items():
                if isinstance(value, str):
                    if keyword in value.lower():
                        score += 2
                elif isinstance(value, list):
                    for item in value:
                        if isinstance(item, str) and keyword in item.lower():
                            score += 1

            # Dosya yolunda ara
            if any(keyword in node.file_path.lower() for keyword in keywords):
                score += 1

            if score > 0:
                seed_nodes.append((node_id, score))

        # Skorlara göre sırala ve en yüksek skorlu düğümleri döndür
        seed_nodes.sort(key=lambda x: x[1], reverse=True)

        # En iyi 5 düğümü döndür
        return [node_id for node_id, _ in seed_nodes[:5]]

    def _bfs_expand(
        self,
        start_node: str,
        max_depth: int,
        max_nodes: int
    ) -> Set[str]:
        """BFS ile komşu düğümleri genişlet"""
        visited = {start_node}
        queue = [(start_node, 0)]

        while queue and len(visited) < max_nodes:
            current, depth = queue.pop(0)

            if depth >= max_depth:
                continue

            # Komşuları ziyaret et
            for neighbor in self.graph.neighbors(current):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, depth + 1))

            # Gelen kenarları da takip et (reverse direction)
            for predecessor in self.graph.predecessors(current):
                if predecessor not in visited:
                    visited.add(predecessor)
                    queue.append((predecessor, depth + 1))

        return visited

    def to_llm_context(
        self,
        subgraph: Optional[nx.MultiDiGraph] = None,
        format: str = "markdown"
    ) -> str:
        """
        Grafı LLM için optimize edilmiş bağlama dönüştürür.

        Args:
            subgraph: Filtrelenmiş alt graf (None ise tam graf)
            format: Çıktı formatı ("markdown", "json", "text")

        Returns:
            LLM'e gönderilecek metin bağlamı
        """
        if subgraph is None:
            subgraph = self.graph

        if format == "json":
            return self._to_json_context(subgraph)
        elif format == "markdown":
            return self._to_markdown_context(subgraph)
        else:
            return self._to_text_context(subgraph)

    def _to_json_context(self, subgraph: nx.MultiDiGraph) -> str:
        """JSON formatında bağlam"""
        nodes = []
        edges = []

        for node_id in subgraph.nodes():
            node_data = subgraph.nodes[node_id]
            nodes.append(node_data)

        for u, v, key, data in subgraph.edges(keys=True, data=True):
            edges.append({
                'source': u,
                'target': v,
                'type': data.get('type', 'unknown'),
            })

        context = {
            'nodes': nodes,
            'edges': edges,
            'summary': {
                'total_nodes': len(nodes),
                'total_edges': len(edges),
                'layers': list(set(n.get('layer', 'unknown') for n in nodes)),
            }
        }

        return json.dumps(context, indent=2, ensure_ascii=False)

    def _to_markdown_context(self, subgraph: nx.MultiDiGraph) -> str:
        """Markdown formatında bağlam"""
        lines = ["# Full-Stack Knowledge Graph Context\n"]

        # Özet
        nodes_list = list(subgraph.nodes(data=True))
        edges_list = list(subgraph.edges(data=True))

        lines.append(f"**Toplam Düğümler:** {len(nodes_list)}")
        lines.append(f"**Toplam Bağlantılar:** {len(edges_list)}\n")

        # Katmanlara göre grupla
        layers = {}
        for node_id, data in nodes_list:
            layer = data.get('layer', 'unknown')
            if layer not in layers:
                layers[layer] = []
            layers[layer].append((node_id, data))

        for layer, nodes in layers.items():
            lines.append(f"\n## {layer.upper()} Layer\n")

            for node_id, data in nodes:
                lines.append(f"### {data.get('label', 'Unknown')}")
                lines.append(f"- **ID:** `{node_id}`")
                lines.append(f"- **Dosya:** `{data.get('file_path', 'N/A')}`")
                lines.append(f"- **Satır:** {data.get('line_number', 'N/A')}")

                if data.get('metadata'):
                    lines.append("- **Metadata:**")
                    for key, value in data['metadata'].items():
                        if isinstance(value, (dict, list)):
                            value = json.dumps(value, ensure_ascii=False)
                        lines.append(f"  - `{key}`: {value}")

                lines.append("")

        # Bağlantılar
        lines.append("\n## Connections\n")
        for u, v, data in edges_list:
            u_label = subgraph.nodes[u].get('label', u)
            v_label = subgraph.nodes[v].get('label', v)
            conn_type = data.get('type', 'unknown')

            lines.append(f"- `{u_label}` --[{conn_type}]--> `{v_label}`")

        return "\n".join(lines)

    def _to_text_context(self, subgraph: nx.MultiDiGraph) -> str:
        """Düz metin formatında bağlam"""
        lines = ["FULL-STACK KNOWLEDGE GRAPH CONTEXT", "=" * 40]

        for node_id, data in subgraph.nodes(data=True):
            layer = data.get('layer', 'unknown').upper()
            label = data.get('label', 'Unknown')
            file_path = data.get('file_path', 'N/A')

            lines.append(f"\n[{layer}] {label}")
            lines.append(f"  File: {file_path}")

        lines.append("\nCONNECTIONS:")
        for u, v, data in subgraph.edges(data=True):
            u_label = subgraph.nodes[u].get('label', u)
            v_label = subgraph.nodes[v].get('label', v)
            conn_type = data.get('type', 'unknown')

            lines.append(f"  {u_label} -> {conn_type} -> {v_label}")

        return "\n".join(lines)

    def get_summary(self) -> Dict[str, Any]:
        """Graf özetini döndür"""
        return {
            'total_nodes': len(self.nodes),
            'total_edges': len(self.edges),
            'api_calls': sum(1 for n in self.nodes.values() if n.type == NodeType.API_CALL),
            'api_endpoints': sum(1 for n in self.nodes.values() if n.type == NodeType.API_ENDPOINT),
            'handlers': sum(1 for n in self.nodes.values() if n.type == NodeType.BACKEND_HANDLER),
            'sql_references': sum(1 for n in self.nodes.values() if n.type == NodeType.SQL_REFERENCE),
            'database_tables': sum(1 for n in self.nodes.values() if n.type == NodeType.DATABASE_TABLE),
            'parser_summary': self.parser.get_summary(),
        }

    def export(self, output_path: str, format: str = "graphml"):
        """
        Grafı dosyaya dışa aktar.

        Args:
            output_path: Çıktı dosya yolu
            format: Format türü ("graphml", "gexf", "json")
        """
        if format == "graphml":
            # GraphML için metadata'yı string'e çevir (dict desteklenmiyor)
            export_graph = self.graph.copy()
            for node_id in export_graph.nodes():
                data = export_graph.nodes[node_id]
                if 'metadata' in data and isinstance(data['metadata'], dict):
                    import json
                    data['metadata'] = json.dumps(data['metadata'], ensure_ascii=False)
            for u, v, key in export_graph.edges(keys=True):
                data = export_graph[u][v][key]
                if 'metadata' in data and isinstance(data['metadata'], dict):
                    import json
                    data['metadata'] = json.dumps(data['metadata'], ensure_ascii=False)
            nx.write_graphml(export_graph, output_path)
        elif format == "gexf":
            # GEXF için de aynı işlem
            export_graph = self.graph.copy()
            for node_id in export_graph.nodes():
                data = export_graph.nodes[node_id]
                if 'metadata' in data and isinstance(data['metadata'], dict):
                    import json
                    data['metadata'] = json.dumps(data['metadata'], ensure_ascii=False)
            nx.write_gexf(export_graph, output_path)
        elif format == "json":
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(self.to_llm_context(format="json"))
        else:
            raise ValueError(f"Bilinmeyen format: {format}")
