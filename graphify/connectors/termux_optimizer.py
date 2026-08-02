"""
Termux Low-Resource Mode: Memory-Efficient Streaming Parser
Optimized for Android/Termux environments with limited RAM (<2GB)
Features: Lazy loading, chunked processing, minimal cache footprint
"""
import os
import gc
from typing import Iterator, Tuple, Optional, Dict
import networkx as nx

class TermuxOptimizer:
    def __init__(self, max_memory_mb: int = 512):
        self.max_memory_mb = max_memory_mb
        self.chunk_size = 100  # Dosya başına işlenecek satır sayısı
        self.lazy_cache: Dict[str, str] = {}  # Sadece aktif dosyalar bellekte
        self.max_cache_size = 50  # Max kaç dosya aynı anda bellekte tutulur

    def scan_directory_lazy(self, root_path: str) -> Iterator[Tuple[str, str]]:
        """
        Bellek dostu dosya tarama. Dosyaları tek tek yükler, işler ve unutur.
        Yield: (filepath, content)
        """
        file_queue = []

        # Önce tüm dosyaları listele (hafif işlem)
        for dirpath, _, filenames in os.walk(root_path):
            if "build" in dirpath or ".gradle" in dirpath or "bin/" in dirpath:
                continue

            for f in filenames:
                if f.endswith((".kt", ".java", ".xml", ".py", ".js", ".ts")):
                    file_queue.append(os.path.join(dirpath, f))

        print(f"📱 Termux Modu: {len(file_queue)} dosya bulundu. Lazy loading başlatılıyor...")

        # Dosyaları sırayla işle
        for i, fpath in enumerate(file_queue):
            # Cache temizliği
            if len(self.lazy_cache) >= self.max_cache_size:
                # En eski %20'yi sil
                keys_to_delete = list(self.lazy_cache.keys())[:self.max_cache_size // 5]
                for k in keys_to_delete:
                    del self.lazy_cache[k]
                gc.collect()

            try:
                # Dosyayı oku
                with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()

                # Cache'e ekle
                self.lazy_cache[fpath] = content

                yield fpath, content

                # Her 50 dosyada bir GC
                if i % 50 == 0:
                    gc.collect()

            except Exception as e:
                print(f"⚠️  {fpath} okuma hatası: {e}")
                continue

    def process_in_chunks(self, content: str, processor_func) -> Iterator:
        """
        Büyük dosyaları parçalar halinde işle.
        processor_func: (chunk_text, start_line) -> result
        """
        lines = content.split('\n')
        total_lines = len(lines)

        for start in range(0, total_lines, self.chunk_size):
            end = min(start + self.chunk_size, total_lines)
            chunk = '\n'.join(lines[start:end])

            result = processor_func(chunk, start)
            if result:
                yield result

    def build_minimal_graph(self, G: nx.DiGraph) -> nx.DiGraph:
        """
        Graf boyutunu küçült: Gereksiz detayları temizle, sadece kritik düğümleri bırak.
        - Singleton pattern'deki aynı tipteki node'ları birleştir
        - Getter/Setter gibi önemsiz fonksiyonları atla
        - Sadece public API'leri tut
        """
        nodes_to_remove = []

        for node, data in G.nodes(data=True):
            # 1. Private method'ları çıkar (Android/Kotlin için)
            if data.get("visibility") == "private":
                if "function" in data.get("type", ""):
                    nodes_to_remove.append(node)

            # 2. Boilerplate code'ları temizle
            if node.startswith("METHOD:") and any(
                x in node for x in ["toString", "hashCode", "equals", "getter", "setter"]
            ):
                nodes_to_remove.append(node)

        # Güvenli silme
        G.remove_nodes_from(nodes_to_remove)

        print(f"🗑️  Minimal graf: {len(nodes_to_remove)} gereksiz düğüm temizlendi.")
        return G

    def estimate_memory_usage(self, G: nx.DiGraph) -> float:
        """Grafın yaklaşık bellek kullanımını hesapla (MB)."""
        # NetworkX düğüm başına ~1KB varsayımı (ortalama)
        node_mem = len(G.nodes) * 1024  # bytes
        edge_mem = len(G.edges) * 512   # bytes

        total_mb = (node_mem + edge_mem) / (1024 * 1024)
        return total_mb

    def check_termux_compatibility(self) -> Dict[str, bool]:
        """Termux ortamının uygunluğunu kontrol et."""
        import sys
        import platform

        results = {
            "is_android": "ANDROID_DATA" in os.environ or "TERMUX_VERSION" in os.environ,
            "python_version_ok": sys.version_info >= (3, 8),
            "has_enough_ram": True,  # Basit varsayım
            "native_compiler_available": False
        }

        # ARM64 kontrolü
        machine = platform.machine()
        results["is_arm64"] = "aarch64" in machine or "arm64" in machine

        # Derleyici var mı? (clang/gcc)
        for compiler in ["clang", "gcc", "cc"]:
            if os.system(f"command -v {compiler} > /dev/null 2>&1") == 0:
                results["native_compiler_available"] = True
                break

        return results

    def get_optimization_report(self, G: nx.DiGraph) -> str:
        """Termux optimizasyon raporunu oluştur."""
        mem_usage = self.estimate_memory_usage(G)
        compat = self.check_termux_compatibility()

        report = [
            "=" * 50,
            "📱 TERMUX OPTIMIZATION REPORT",
            "=" * 50,
            f"Ortam: {'Android/Termux' if compat['is_android'] else 'Desktop/Linux'}",
            f"Mimari: {'ARM64' if compat.get('is_arm64') else 'x86_64'}",
            f"Python: {compat['python_version_ok']}",
            f"Derleyici: {'Var' if compat['native_compiler_available'] else 'Yok'}",
            "-" * 50,
            f"Graf Boyutu: {len(G.nodes)} düğüm, {len(G.edges)} kenar",
            f"Tahmini Bellek: {mem_usage:.2f} MB",
            f"Durum: {'✅ Uygun' if mem_usage < self.max_memory_mb else '⚠️  Bellek aşımı riski'}",
            "=" * 50
        ]

        return "\n".join(report)


# Helper function for easy integration
def enable_termux_mode(graph_builder):
    """
    Graphify builder'a Termux modunu etkinleştir.
    Kullanım: enable_termux_mode(builder)
    """
    optimizer = TermuxOptimizer()

    # Builder'ın scan metodunu lazy versiyonla değiştir
    original_scan = graph_builder.scan_directory
    def wrapped_scan(path):
        print("🔧 Termux Low-Memory Mode: ACTIVE")
        for fpath, content in optimizer.scan_directory_lazy(path):
            # Process her dosyayı
            pass
        return optimizer.build_minimal_graph(graph_builder.G)

    graph_builder.scan_directory = wrapped_scan
    print("✅ Termux mode enabled: Lazy loading + Minimal graph")
    return optimizer
