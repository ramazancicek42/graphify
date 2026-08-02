"""
Android UI Mapper: XML Layouts <-> Kotlin/Java Code Linker
Supports: Traditional Views (findViewById) and Jetpack Compose
Optimized for Termux (Low Memory)
"""
import os
import re
from typing import Dict, List, Set, Tuple, Optional
import xml.etree.ElementTree as ET
from graphify.connectors.cross_layer_parser import CrossLayerParser
import networkx as nx

class UIMapper:
    def __init__(self):
        self.layout_nodes: Dict[str, dict] = {}  # layout_file -> {views}
        self.composable_nodes: Dict[str, dict] = {}  # file -> {functions}
        self.bindings: List[dict] = []  # (code_file, function, layout_id, view_type)

    def scan_directory(self, root_path: str):
        """Tara: XML layoutleri ve Kotlin/Java UI kodlarını bul."""
        print(f"📱 UI Mapper taraması başlatılıyor: {root_path}")

        # 1. XML Layoutleri Tara
        layout_dir = os.path.join(root_path, "res", "layout")
        if os.path.exists(layout_dir):
            self._parse_layouts(layout_dir)

        # 2. Compose Dosyalarını Tara
        for dirpath, _, filenames in os.walk(root_path):
            if "build" in dirpath or ".gradle" in dirpath:
                continue
            for f in filenames:
                if f.endswith(".kt") or f.endswith(".java"):
                    self._parse_ui_code(os.path.join(dirpath, f))

    def _parse_layouts(self, layout_dir: str):
        """XML Layout dosyalarındaki View ID'lerini çıkar."""
        for fname in os.listdir(layout_dir):
            if not fname.endswith(".xml"):
                continue

            fpath = os.path.join(layout_dir, fname)
            try:
                tree = ET.parse(fpath)
                root = tree.getroot()

                views = []
                # Namespace handling
                ns = {'android': 'http://schemas.android.com/apk/res/android'}

                # Recursive search for all elements with android:id
                for elem in root.iter():
                    vid = elem.attrib.get("{http://schemas.android.com/apk/res/android}id")
                    if vid:
                        # R.id.xxx formatına çevir
                        clean_id = vid.split("/")[-1] if "/" in vid else vid
                        views.append({
                            "id": clean_id,
                            "type": elem.tag.split("}")[-1], # LinearLayout, TextView vb.
                            "file": fname
                        })

                self.layout_nodes[fname] = {
                    "file": fname,
                    "path": fpath,
                    "views": views,
                    "root_type": root.tag.split("}")[-1]
                }
            except Exception as e:
                print(f"⚠️  {fname} parse hatası: {e}")

    def _parse_ui_code(self, fpath: str):
        """Kotlin/Java kodundaki UI referanslarını bul."""
        with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        fname = os.path.basename(fpath)

        # 1. setContentView / inflate pattern
        # setContentView(R.layout.activity_main)
        layout_refs = re.findall(r'setContentView\(R\.layout\.(\w+)\)', content)
        # inflate(R.layout.item_row, ...)
        layout_refs += re.findall(r'inflate\(R\.layout\.(\w+)', content)

        # 2. findViewById pattern
        # findViewById(R.id.username)
        find_refs = re.findall(r'findViewById<\w+>\(R\.id\.(\w+)\)|findViewById\(R\.id\.(\w+)\)', content)
        found_ids = [x[0] or x[1] for x in find_refs if x[0] or x[1]]

        # 3. Jetpack Compose @Composable functions
        # @Composable fun HomeScreen(...)
        composables = re.findall(r'@Composable\s+fun\s+(\w+)', content)

        # 4. Compose Preview
        # @Preview
        previews = re.findall(r'@Preview\s+fun\s+(\w+)', content)

        if layout_refs or found_ids or composables:
            self.composable_nodes[fname] = {
                "file": fname,
                "path": fpath,
                "layouts_used": list(set(layout_refs)),
                "ids_found": list(set(found_ids)),
                "composables": composables,
                "previews": previews
            }

    def build_graph(self, G: Optional[nx.DiGraph] = None) -> nx.DiGraph:
        """UI bağlantılarını graf üzerine ekle."""
        if G is None:
            G = nx.DiGraph()

        # 1. Layout Node'larını Ekle
        for lname, data in self.layout_nodes.items():
            node_id = f"LAYOUT:{lname}"
            G.add_node(node_id, type="ui_layout", file=data["file"], views=len(data["views"]))

            for view in data["views"]:
                view_node = f"VIEW:{view['id']}"
                G.add_node(view_node, type="ui_view", widget=view["type"], layout=lname)
                G.add_edge(node_id, view_node, relation="contains")

        # 2. Kod-Layout Bağlantılarını Kur
        for fname, data in self.composable_nodes.items():
            code_node = f"CODE:{fname}"
            # Sadece class/function node'ı varsa bağla, yoksa genel dosya node'u
            if not G.has_node(code_node):
                G.add_node(code_node, type="source_file", lang="kotlin" if fname.endswith(".kt") else "java")

            # Layout Kullanımı
            for layout in data["layouts_used"]:
                layout_node = f"LAYOUT:{layout}.xml"
                if G.has_node(layout_node):
                    G.add_edge(code_node, layout_node, relation="sets_content")

            # ID Eşleştirme (En Kritik Kısım)
            for vid in data["ids_found"]:
                view_node = f"VIEW:{vid}"
                if G.has_node(view_node):
                    G.add_edge(code_node, view_node, relation="binds_to")

            # Compose Fonksiyonları
            for comp in data["composables"]:
                comp_node = f"COMPOSABLE:{comp}"
                G.add_node(comp_node, type="compose_function", file=fname)
                G.add_edge(code_node, comp_node, relation="defines")

        return G

    def get_ui_chain(self, element_id: str) -> List[str]:
        """Bir UI elementinin koddaki kullanım zincirini bul."""
        chain = []
        view_node = f"VIEW:{element_id}"
        # Bu fonksiyon graf oluştuktan sonra çalıştırılmalı
        return chain
