# Full-Stack Knowledge Graph - Genişletilmiş Graphify

## 🎯 Genel Bakış

Bu modül, Graphify'ı **çok katmanlı full-stack projeleri** tarayabilir hale getirir. Artık sadece kod içindeki fonksiyon çağrılarını değil, **frontend → API → backend → database** zincirini tamamlayan end-to-end bağlantıları görebilirsiniz.

## ✨ Yeni Özellikler

### 1. Çapraz Katman Tarayıcı (Cross-Layer Parser)

```python
from graphify.connectors import CrossLayerParser

parser = CrossLayerParser()
parser.scan_directory("/path/to/fullstack/project")

# Tespit edilenler:
# - Frontend API çağrıları (axios, fetch, Retrofit, vb.)
# - Backend endpoint'leri (FastAPI, Flask, Express, Django, Gin, Spring)
# - SQL referansları (SELECT, INSERT, UPDATE, DELETE)
# - Veritabanı şemaları (SQL dosyaları, Prisma, SQLAlchemy, Django ORM)
```

**Desteklenen Framework'ler:**

| Katman | Teknolojiler |
|--------|-------------|
| Frontend | React, Vue, Angular, Swift (iOS), Kotlin (Android), Dart (Flutter) |
| Backend | FastAPI, Flask, Django, Express.js, Go Gin, Spring Boot |
| Database | Raw SQL, SQLAlchemy, Prisma, Django ORM, Room |

### 2. Birleşik Graf Oluşturucu (Unified Graph Builder)

```python
from graphify.connectors import UnifiedGraphBuilder

builder = UnifiedGraphBuilder()
builder.from_directory("/path/to/project")

# Full-stack grafı oluşturur:
# [Frontend Function] → [API Call] → [API Endpoint] → [Backend Handler] → [SQL Reference] → [Database Table]
```

### 3. Token-Optimize Subgraph Çıkarma

LLM token limitlerini aşmamak için sadece ilgili alt grafikleri çıkarır:

```python
# Sorguyla ilgili subgraph'ı çıkar
subgraph = builder.extract_subgraph(
    query="Kullanıcı profil resmi güncellerken hata alıyor",
    max_depth=5,      # BFS arama derinliği
    max_nodes=100     # Maksimum düğüm sayısı
)

# LLM için optimize edilmiş context oluştur
context = builder.to_llm_context(subgraph, format="markdown")
print(context)
```

## 📋 Kullanım Örnekleri

### Örnek 1: Temel Kullanım

```python
from graphify.connectors import CrossLayerParser, UnifiedGraphBuilder

# 1. Projeyi tara
parser = CrossLayerParser()
parser.scan_directory("./my-fullstack-app")

# 2. Özet bilgileri al
summary = parser.get_summary()
print(f"API Çağrıları: {summary['api_calls']}")
print(f"API Endpoint'leri: {summary['api_endpoints']}")
print(f"SQL Referansları: {summary['table_references']}")
print(f"Tablolar: {summary['tables']}")

# 3. Graf oluştur
builder = UnifiedGraphBuilder()
builder.from_parser(parser)

# 4. Graf özeti
graph_summary = builder.get_summary()
print(f"Toplam Düğüm: {graph_summary['total_nodes']}")
print(f"Toplam Kenar: {graph_summary['total_edges']}")
```

### Örnek 2: End-to-End Zincir Analizi

```python
from graphify.connectors import UnifiedGraphBuilder

builder = UnifiedGraphBuilder()
builder.from_directory("./ecommerce-app")

# "Ürün siparişi verme" ile ilgili tüm zinciri çıkar
subgraph = builder.extract_subgraph(
    query="Ürün siparişi verme ve ödeme işleme",
    max_depth=4
)

# Markdown formatında LLM context'i oluştur
context = builder.to_llm_context(subgraph, format="markdown")

# Context'i LLM'e gönder
# response = llm.chat(f"""
# Aşağıdaki full-stack graf bağlamını kullanarak:
# {context}
# 
# Soru: Kullanıcı ürün siparişi verirken hangi tablolar güncellenir?
# """)
```

### Örnek 3: JSON Export ve Görselleştirme

```python
from graphify.connectors import UnifiedGraphBuilder

builder = UnifiedGraphBuilder()
builder.from_directory("./my-app")

# JSON formatında dışa aktar
builder.export("output/graph.json", format="json")

# GraphML formatında (Gephi, Cytoscape için)
builder.export("output/graph.graphml", format="graphml")

# GEXF formatında (Gephi için)
builder.export("output/graph.gexf", format="gexf")
```

### Örnek 4: Farklı Formatlarda Context Çıktısı

```python
# Markdown formatı (insan tarafından okunabilir)
md_context = builder.to_llm_context(format="markdown")

# JSON formatı (programatik işlem için)
json_context = builder.to_llm_context(format="json")

# Düz metin formatı (basit çıktılar için)
text_context = builder.to_llm_context(format="text")
```

## 🔧 Mimari Detaylar

### Düğüm Türleri (Node Types)

| Tür | Açıklama | Katman |
|-----|----------|--------|
| `frontend_function` | API çağrısı yapan frontend fonksiyonu | Frontend |
| `api_call` | HTTP API çağrısı (GET, POST, PUT, DELETE) | Frontend |
| `api_endpoint` | Backend route/endpoint tanımı | Backend |
| `backend_handler` | API isteğini işleyen fonksiyon | Backend |
| `sql_reference` | Kod içindeki SQL sorgusu | Backend |
| `database_table` | Veritabanı tablosu şeması | Database |

### Bağlantı Türleri (Connection Types)

| Tür | Açıklama |
|-----|----------|
| `calls_api` | Frontend fonksiyonu API çağrısı yapıyor |
| `handles_request` | Backend handler endpoint'i işliyor |
| `queries_table` | SQL SELECT sorgusu |
| `updates_table` | SQL UPDATE sorgusu |
| `inserts_into_table` | SQL INSERT sorgusu |
| `deletes_from_table` | SQL DELETE sorgusu |

### Subgraph Algoritması

1. **Keyword Extraction**: Kullanıcı sorgusundan anahtar kelimeleri çıkarır (Türkçe ve İngilizce stop words filtreleme)
2. **Seed Node Matching**: Anahtar kelimelerle eşleşen başlangıç düğümlerini bulur (label, metadata, file_path'te arama)
3. **BFS Expansion**: Seed düğümlerden başlayarak iki yönlü BFS ile komşuları genişletir
4. **Limiting**: `max_depth` ve `max_nodes` parametreleriyle boyutu sınırlar

## 📊 Örnek Proje Yapısı

```
test_fullstack_project/
├── frontend/
│   └── userService.ts      # axios ile API çağrıları
├── backend/
│   └── user_api.py         # FastAPI endpoints + SQL sorguları
└── database/
    └── schema.sql          # CREATE TABLE tanımları
```

### Tespit Edilen Zincir

```
getUserProfile (frontend/userService.ts)
    ↓ calls_api
GET /api/v1/users/:id (frontend/userService.ts)
    ↓ matches
GET /api/v1/users/{user_id} (backend/user_api.py)
    ↓ handles_request
get_user handler (backend/user_api.py)
    ↓ queries_table
SELECT FROM users (backend/user_api.py)
    ↓ references
users table (database/schema.sql)
```

## 🚀 Performans ve Optimizasyon

### Token Tasarrufu

| Yaklaşım | Token Sayısı | Azalma |
|----------|-------------|--------|
| Tam graf (JSON) | ~15,000 | - |
| Subgraph (max_depth=3) | ~2,000 | %87 |
| Subgraph + Markdown | ~1,500 | %90 |

### Tarama Hızı

- Küçük projeler (< 100 dosya): < 1 saniye
- Orta projeler (100-500 dosya): 1-5 saniye
- Büyük projeler (> 500 dosya): 5-15 saniye

## 🔮 Gelecek Geliştirmeler

- [ ] GraphQL endpoint desteği
- [ ] gRPC servis keşfi
- [ ] Message queue (Kafka, RabbitMQ) bağlantıları
- [ ] Cloud resource mapping (AWS, GCP, Azure)
- [ ] Real-time WebSocket bağlantıları
- [ ] Authentication/Authorization flow tracking
- [ ] Microservice arası çağrı izleme

## 📝 Lisans

MIT License - Graphify projesinin bir parçası olarak dağıtılmaktadır.
