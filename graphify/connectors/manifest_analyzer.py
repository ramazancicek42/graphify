"""
Android Manifest & Intent Flow Analyzer
Tracks: Permissions, Activities, Services, Intent Filters, Deep Links
Optimized for Termux (Security Focused)
"""
import os
import re
import xml.etree.ElementTree as ET
from typing import Dict, List, Set, Optional
import networkx as nx

class ManifestAnalyzer:
    def __init__(self):
        self.permissions: Dict[str, dict] = {}
        self.components: Dict[str, dict] = {}  # Activities, Services, Receivers, Providers
        self.intents: List[dict] = []          # Explicit/Implicit intent flows
        self.deep_links: List[dict] = []       # App links / Deep links

    def scan_directory(self, root_path: str):
        """AndroidManifest.xml ve Intent kullanımlarını tara."""
        print(f"🛡️  Manifest Analyzer taraması başlatılıyor: {root_path}")

        # 1. AndroidManifest.xml Parse
        manifest_path = os.path.join(root_path, "AndroidManifest.xml")
        if os.path.exists(manifest_path):
            self._parse_manifest(manifest_path)

        # 2. Kotlin/Java Intent Kullanımları
        for dirpath, _, filenames in os.walk(root_path):
            if "build" in dirpath or ".gradle" in dirpath:
                continue

            for f in filenames:
                if not (f.endswith(".kt") or f.endswith(".java")):
                    continue

                fpath = os.path.join(dirpath, f)
                self._parse_intent_usage(fpath)

    def _parse_manifest(self, fpath: str):
        """AndroidManifest.xml'i detaylı parse et."""
        try:
            tree = ET.parse(fpath)
            root = tree.getroot()
            ns = {'android': 'http://schemas.android.com/apk/res/android'}

            # 1. Permissions
            for perm in root.findall(".//uses-permission"):
                pname = perm.attrib.get("{http://schemas.android.com/apk/res/android}name")
                if pname:
                    self.permissions[pname] = {
                        "type": "USES_PERMISSION",
                        "file": "AndroidManifest.xml"
                    }

            # 2. Application Components
            app = root.find(".//application")
            if app is not None:
                # Activities
                for activity in app.findall(".//activity"):
                    self._parse_component(activity, "ACTIVITY", ns)

                # Services
                for service in app.findall(".//service"):
                    self._parse_component(service, "SERVICE", ns)

                # Receivers
                for receiver in app.findall(".//receiver"):
                    self._parse_component(receiver, "RECEIVER", ns)

                # Providers
                for provider in app.findall(".//provider"):
                    self._parse_component(provider, "PROVIDER", ns)

            print(f"✅ Manifest parse edildi: {len(self.components)} component, {len(self.permissions)} izin")

        except Exception as e:
            print(f"⚠️  Manifest parse hatası: {e}")

    def _parse_component(self, elem, comp_type: str, ns: dict):
        """Activity, Service vb. componentleri parse et."""
        name = elem.attrib.get("{http://schemas.android.com/apk/res/android}name")
        if not name:
            return

        # Kısa isimleri tam isme çevir (.MainActivity -> com.example.MainActivity)
        if name.startswith("."):
            # Package adını bulmak gerekir, şimdilik placeholder
            full_name = f"${name}"  # Sonradan resolve edilecek
        else:
            full_name = name

        # Intent Filters
        intent_filters = []
        for filter_elem in elem.findall(".//intent-filter"):
            actions = []
            categories = []
            data_schemes = []

            for action in filter_elem.findall(".//action"):
                aname = action.attrib.get("{http://schemas.android.com/apk/res/android}name")
                if aname:
                    actions.append(aname)

            for category in filter_elem.findall(".//category"):
                cname = category.attrib.get("{http://schemas.android.com/apk/res/android}name")
                if cname:
                    categories.append(cname)

            for data in filter_elem.findall(".//data"):
                scheme = data.attrib.get("{http://schemas.android.com/apk/res/android}scheme")
                host = data.attrib.get("{http://schemas.android.com/apk/res/android}host")
                if scheme:
                    data_schemes.append({"scheme": scheme, "host": host})

            intent_filters.append({
                "actions": actions,
                "categories": categories,
                "data_schemes": data_schemes
            })

            # Deep Link tespiti
            if "android.intent.action.VIEW" in actions and data_schemes:
                for ds in data_schemes:
                    self.deep_links.append({
                        "component": full_name,
                        "scheme": ds["scheme"],
                        "host": ds.get("host"),
                        "type": "DEEP_LINK"
                    })

        # Exported attribute (Güvenlik için kritik)
        exported = elem.attrib.get("{http://schemas.android.com/apk/res/android}exported")

        self.components[full_name] = {
            "type": comp_type,
            "file": "AndroidManifest.xml",
            "intent_filters": intent_filters,
            "exported": exported == "true" if exported else (comp_type == "ACTIVITY" and any(
                "MAIN" in f.get("actions", []) for f in intent_filters
            )),
            "permission": elem.attrib.get("{http://schemas.android.com/apk/res/android}permission")
        }

    def _parse_intent_usage(self, fpath: str):
        """Kotlin/Java kodundaki Intent başlatmalarını izle."""
        with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        fname = os.path.basename(fpath)

        # 1. Explicit Intent (Class bazlı)
        # Intent(this, TargetActivity::class.java)
        explicit = re.findall(r'Intent\s*\(\s*this\s*,\s*(\w+)::class', content)

        # 2. Implicit Intent (Action bazlı)
        # Intent("com.example.ACTION_X")
        implicit_actions = re.findall(r'Intent\s*\(\s*"([^"]+)"\s*\)', content)

        # 3. startActivity, startService
        starts = re.findall(r'(?:startActivity|startService|sendBroadcast)\s*\(\s*intent\s*\)', content)

        # 4. Pending Intent
        pending = re.findall(r'PendingIntent\.get(?:Activity|Service|Broadcast)', content)

        if explicit or implicit_actions:
            self.intents.append({
                "file": fname,
                "path": fpath,
                "explicit_targets": explicit,
                "implicit_actions": implicit_actions,
                "has_start_call": len(starts) > 0,
                "has_pending": len(pending) > 0
            })

    def build_graph(self, G: Optional[nx.DiGraph] = None) -> nx.DiGraph:
        """Manifest ve Intent akış grafını oluştur."""
        if G is None:
            G = nx.DiGraph()

        # 1. Permission Node'ları
        for pname, data in self.permissions.items():
            node_id = f"PERMISSION:{pname}"
            G.add_node(node_id, type="permission", file=data["file"])

        # 2. Component Node'ları
        for cname, data in self.components.items():
            node_id = f"COMPONENT:{cname}"
            G.add_node(node_id,
                      type="android_component",
                      kind=data["type"],
                      exported=data["exported"],
                      file=data["file"])

            # Permission bağı
            if data.get("permission"):
                perm_node = f"PERMISSION:{data['permission']}"
                if G.has_node(perm_node):
                    G.add_edge(node_id, perm_node, relation="requires_permission")
                else:
                    G.add_node(perm_node, type="permission_required")
                    G.add_edge(node_id, perm_node, relation="requires_permission")

            # Intent Filter Actions
            for filt in data.get("intent_filters", []):
                for action in filt["actions"]:
                    action_node = f"ACTION:{action}"
                    G.add_node(action_node, type="intent_action")
                    G.add_edge(node_id, action_node, relation="handles_action")

        # 3. Deep Link Node'ları
        for dl in self.deep_links:
            dl_node = f"DEEPLINK:{dl['scheme']}://{dl.get('host', '')}"
            G.add_node(dl_node, type="deep_link", scheme=dl["scheme"], host=dl.get("host"))
            comp_node = f"COMPONENT:{dl['component']}"
            if G.has_node(comp_node):
                G.add_edge(dl_node, comp_node, relation="opens")

        # 4. Kod -> Component Intent Bağlantıları
        for intent_data in self.intents:
            code_node = f"CODE:{intent_data['file']}"
            if not G.has_node(code_node):
                G.add_node(code_node, type="source_file", file=intent_data["file"])

            # Explicit Intent hedefleri
            for target in intent_data["explicit_targets"]:
                # Hedef component'i bul (tam isim eşleştirme gerekli)
                # Şimdilik genel eşleştirme
                for cname in self.components.keys():
                    if target in cname or cname.endswith(f".{target}"):
                        comp_node = f"COMPONENT:{cname}"
                        G.add_edge(code_node, comp_node, relation="starts_explicit")

            # Implicit Action'lar
            for action in intent_data["implicit_actions"]:
                action_node = f"ACTION:{action}"
                G.add_node(action_node, type="intent_action")
                G.add_edge(code_node, action_node, relation="broadcasts_action")

        return G

    def get_security_report(self) -> Dict[str, list]:
        """Güvenlik risklerini raporla."""
        risks = {
            "exported_without_permission": [],
            "dangerous_permissions": [],
            "implicit_intent_risks": []
        }

        dangerous_perms = [
            "READ_CONTACTS", "WRITE_CONTACTS",
            "CAMERA", "RECORD_AUDIO",
            "ACCESS_FINE_LOCATION", "ACCESS_BACKGROUND_LOCATION",
            "READ_SMS", "SEND_SMS"
        ]

        for pname in self.permissions.keys():
            for dp in dangerous_perms:
                if dp in pname:
                    risks["dangerous_permissions"].append(pname)

        for cname, data in self.components.items():
            if data["exported"] and not data.get("permission"):
                if data["type"] in ["SERVICE", "RECEIVER", "PROVIDER"]:
                    risks["exported_without_permission"].append({
                        "component": cname,
                        "type": data["type"]
                    })

        return risks
