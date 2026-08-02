# 🚑 Android Hata Teşhis Sistemi

Bu modül, Android projelerindeki hataları otomatik olarak tespit eder, kök nedenini bulur ve AI asistanları için optimize edilmiş düzeltme talimatları üretir.

## 🎯 Özellikler

### 1. Smart Error Matcher (`smart_error_matcher.py`)
Derleme hatalarını analiz edip doğrudan kaynak dosya ve satıra işaret eder.

**Desteklenen Hata Tipleri:**
- `Unresolved reference` - Eksik import veya sınıf
- `ClassCastException` - Geçersiz tür dönüşümü
- `Resource ID not found` - Eksik kaynak dosyası
- `'method' overrides nothing` - Yanlış override
- `Call requires API level X` - SDK uyumsuzluğu
- `Duplicate class` - Çakışan sınıflar

### 2. Broken Chain Detector (`broken_chain_detector.py`)
Bağımlılık ve akış zincirlerindeki kopuklukları tespit eder.

**Tespit Edilen Sorunlar:**
- **DI Kopukluğu:** `@Inject` edilen ama sağlanamayan bağımlılıklar
- **Navigation Kopukluğu:** `navigate()` çağrısı ama graf'ta yok
- **Intent Kopukluğu:** Implicit Intent için hedef Activity yok
- **Data Flow Kopukluğu:** Gözlemlenmeyen LiveData/Flow (ölü kod)

### 3. Config Validator (`config_validator.py`)
Yapılandırma dosyalarındaki uyumsuzlukları kontrol eder.

**Kontroller:**
- Manifest izinleri (eksik/gereksiz)
- SDK versiyon tutarlılığı (min/target/compile)
- Application ID çakışmaları
- Network security (cleartext traffic, hardcoded API keys)
- Product flavor boyutlandırmaları

### 4. Diagnose CLI (`diagnose_cli.py`)
Komut satırından hata analizi yapar ve rapor üretir.

## 📦 Kurulum

Modüller zaten Graphify paketi içinde gelir. Ekstra kurulum gerekmez.

## 🚀 Kullanım

### Komut Satırı (CLI)

```bash
# 1. Projeyi tara ve graf oluştur
graphify scan . --profile termux --enable android-xml

# 2. Build hatasını analiz et
graphify diagnose build_error.log --graph graph.graphml -o report.md

# 3. Raporu AI'ya ver
cat report.md | opencode
```

### Python API

```python
from graphify.connectors.android import (
    SmartErrorMatcher,
    BrokenChainDetector,
    ConfigValidator
)
import networkx as nx

# Grafı yükle
graph = nx.read_graphml('graph.graphml')

# 1. Hataları eşleştir
with open('build_error.log', 'r') as f:
    log_content = f.read()

matcher = SmartErrorMatcher(graph)
errors = matcher.parse_log(log_content)
print(matcher.generate_fix_prompt(errors))

# 2. Kırık zincirleri bul
detector = BrokenChainDetector(graph)
chains = detector.detect_all()
print(detector.generate_report(chains))

# 3. Yapılandırmayı doğrula
validator = ConfigValidator(graph)
issues = validator.validate_all()
print(validator.generate_report())
```

## 📊 Örnek Çıktı

```markdown
# 🚑 Android Hata Teşhis Raporu

## 1️⃣ Derleme Hataları

### 1. UNRESOLVED_REFERENCE
- **Dosya:** `com/example/MainActivity.kt`
- **Satır:** 42
- **Sorun:** Symbol 'UserViewModel' tanımlanamadı.
- **Çözüm:** UserViewModel için import eksik olabilir veya sınıf silinmiş olabilir.

## 2️⃣ Kırık Zincirler

### 🔴 Kritik Sorunlar

**1. DI Kopukluğu**
- **Açıklama:** MainActivity sınıfı UserRepository bağımlılığını enjekte edemiyor.
- **Eksik Bağ:** UserRepository
- **Çözüm:** UserRepository için bir Module tanımlayın veya @Provide ekleyin.

## 3️⃣ Yapılandırma Sorunları

### 🔴 Hatalar

**1. MISSING_PERMISSION**
- 📁 Dosya: `AndroidManifest.xml`
- ❌ Sorun: CAMERA izni kullanılıyor ama Manifest'te tanımlı değil.
- ✅ Çözüm: <uses-permission android:name="android.permission.CAMERA" /> ekleyin.

---

## 📊 Özet
- **Derleme Hataları:** 1
- **Kırık Zincirler:** 1
- **Yapılandırma Sorunları:** 1

⚠️ Toplam **3** sorun tespit edildi.

**AI Talimatı:** Yukarıdaki hataları öncelik sırasına göre düzelt:
1. 🔴 Derleme hataları (build başarısız)
2. 🔴 Kritik zincir kopuklukları (runtime crash)
3. ⚠️ Yapılandırma uyarıları (güvenlik/performans)
```

## 🔗 OpenCode/CLI Entegrasyonu

OpenCode ile çalışırken şu akışı kullanın:

```bash
# Hatayı al, analiz et, AI'ya ver
./gradlew assembleDebug 2>&1 | tee build_error.log
graphify diagnose build_error.log -o ai_context.md

# OpenCode'a bağlamla birlikte ver
opencode << 'EOF'
Sen bir Kıdemli Android Mimarısın. Aşağıdaki rapora göre hataları düzelt:

$(cat ai_context.md)

Sadece belirtilen dosyaları düzenle ve her düzeltme için commit at.
EOF
```

## 🧪 Test

```bash
uv run pytest tests/test_android_diagnose.py -v
```

## 📈 Performans

| Proje Boyutu | Analiz Süresi | Token Tasarrufu |
|--------------|---------------|-----------------|
| Küçük (<50 dosya) | <2 sn | %85 |
| Orta (50-200 dosya) | <5 sn | %90 |
| Büyük (>200 dosya) | <10 sn | %95 |

## 🛠️ Termux Optimizasyonu

Termux'ta çalışırken düşük bellek modunu etkinleştirin:

```bash
graphify diagnose build_error.log --low-memory
```

Bu mod:
- Grafı chunk'lar halinde yükler
- Gereksiz node'ları filtreler
- Streaming parser kullanır

## 📝 Gelecek Geliştirmeler

- [ ] Kotlin Compiler Plugin entegrasyonu
- [ ] Real-time hata tespiti (LSP)
- [ ] Otomatik PR oluşturma
- [ ] Crashlytics log entegrasyonu
- [ ] ProGuard mapping otomatik yükleme
