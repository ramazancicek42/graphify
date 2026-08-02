"""
Android Diagnose CLI: Hata loglarını analiz edip AI için optimize edilmiş
düzeltme talimatları üretir.
"""
import argparse
import sys
import os
from pathlib import Path
from typing import Optional

# Graphify connector'larını import et
try:
    from .smart_error_matcher import SmartErrorMatcher
    from .broken_chain_detector import BrokenChainDetector
    from .config_validator import ConfigValidator
except ImportError:
    from smart_error_matcher import SmartErrorMatcher
    from broken_chain_detector import BrokenChainDetector
    from config_validator import ConfigValidator

def load_graph(graph_path: str):
    """GraphML veya JSON graf dosyasını yükle."""
    import networkx as nx

    if graph_path.endswith('.graphml'):
        return nx.read_graphml(graph_path)
    elif graph_path.endswith('.json'):
        import json
        with open(graph_path, 'r') as f:
            data = json.load(f)
        return nx.node_link_graph(data)
    else:
        raise ValueError(f"Desteklenmeyen graf formatı: {graph_path}")

def diagnose_error_log(log_path: str, graph_path: str, output_path: Optional[str] = None):
    """Hata logunu analiz et ve düzeltme talimatları üret."""

    # Grafı yükle
    print(f"📊 Graf yükleniyor: {graph_path}")
    try:
        graph = load_graph(graph_path)
        print(f"✅ Graf yüklendi: {graph.number_of_nodes()} düğüm, {graph.number_of_edges()} kenar")
    except Exception as e:
        print(f"❌ Graf yüklenemedi: {e}")
        return 1

    # Hata logunu oku
    print(f"📋 Hata logu okunuyor: {log_path}")
    try:
        with open(log_path, 'r', encoding='utf-8') as f:
            log_content = f.read()
    except Exception as e:
        print(f"❌ Hata logu okunamadı: {e}")
        return 1

    # 1. Smart Error Matcher ile hataları eşleştir
    print("🔍 Hatalar analiz ediliyor...")
    error_matcher = SmartErrorMatcher(graph)
    errors = error_matcher.parse_log(log_content)

    # 2. Broken Chain Detector ile zincir kopukluklarını bul
    print("🔗 Bağımlılık zincirleri kontrol ediliyor...")
    chain_detector = BrokenChainDetector(graph)
    broken_chains = chain_detector.detect_all()

    # 3. Config Validator ile yapılandırma sorunlarını bul
    print("⚙️  Yapılandırma doğrulanıyor...")
    config_validator = ConfigValidator(graph)
    config_issues = config_validator.validate_all()

    # Rapor oluştur
    report = "# 🚑 Android Hata Teşhis Raporu\n\n"
    report += "Bu rapor, AI asistanına verilerek hızlı düzeltme yapılabilir.\n\n"

    # Bölüm 1: Derleme Hataları
    if errors:
        report += "## 1️⃣ Derleme Hataları\n\n"
        report += error_matcher.generate_fix_prompt(errors)
        report += "\n\n"
    else:
        report += "## 1️⃣ Derleme Hataları\n\n✅ Derleme hatası bulunamadı.\n\n"

    # Bölüm 2: Kırık Zincirler
    if broken_chains:
        report += "## 2️⃣ Kırık Zincirler\n\n"
        report += chain_detector.generate_report(broken_chains)
        report += "\n\n"
    else:
        report += "## 2️⃣ Kırık Zincirler\n\n✅ Kırık zincir tespit edilmedi.\n\n"

    # Bölüm 3: Yapılandırma Sorunları
    if config_issues:
        report += "## 3️⃣ Yapılandırma Sorunları\n\n"
        report += config_validator.generate_report()
        report += "\n\n"
    else:
        report += "## 3️⃣ Yapılandırma Sorunları\n\n✅ Yapılandırma sorunu bulunamadı.\n\n"

    # Özet
    report += "---\n\n"
    report += "## 📊 Özet\n\n"
    report += f"- **Derleme Hataları:** {len(errors)}\n"
    report += f"- **Kırık Zincirler:** {len(broken_chains)}\n"
    report += f"- **Yapılandırma Sorunları:** {len(config_issues)}\n\n"

    total_issues = len(errors) + len(broken_chains) + len(config_issues)
    if total_issues == 0:
        report += "🎉 Proje sağlıklı görünüyor!\n"
    else:
        report += f"⚠️ Toplam **{total_issues}** sorun tespit edildi.\n\n"
        report += "**AI Talimatı:** Yukarıdaki hataları öncelik sırasına göre düzelt:\n"
        report += "1. 🔴 Derleme hataları (build başarısız)\n"
        report += "2. 🔴 Kritik zincir kopuklukları (runtime crash)\n"
        report += "3. ⚠️ Yapılandırma uyarıları (güvenlik/performans)\n"

    # Çıktıyı yaz veya stdout'a bas
    if output_path:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(report)
        print(f"✅ Rapor kaydedildi: {output_path}")
    else:
        print("\n" + "="*60)
        print(report)

    return 0

def main():
    parser = argparse.ArgumentParser(
        description="Android proje hatalarını teşhis et ve AI için düzeltme talimatları üret."
    )
    parser.add_argument(
        "log_file",
        help="Build error log dosyası (örn: build_error.log)"
    )
    parser.add_argument(
        "--graph", "-g",
        default="graph.graphml",
        help="Graphify graf dosyası (varsayılan: graph.graphml)"
    )
    parser.add_argument(
        "--output", "-o",
        help="Çıktı dosyası (varsayılan: stdout)"
    )

    args = parser.parse_args()

    if not os.path.exists(args.log_file):
        print(f"❌ Hata logu bulunamadı: {args.log_file}")
        sys.exit(1)

    if not os.path.exists(args.graph):
        print(f"❌ Graf dosyası bulunamadı: {args.graph}")
        print("💡 Önce 'graphify scan .' komutuyla projeyi tarayın.")
        sys.exit(1)

    exit_code = diagnose_error_log(args.log_file, args.graph, args.output)
    sys.exit(exit_code)

if __name__ == "__main__":
    main()
