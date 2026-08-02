-- Veritabanı Şeması
-- Kullanıcı yönetimi ve sipariş sistemi için SQL tabloları

-- Users tablosu: Kullanıcı bilgilerini saklar
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    avatar_url TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Users tablosu için indexler
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);

-- Orders tablosu: Kullanıcı siparişlerini saklar
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    product_name TEXT NOT NULL,
    amount DECIMAL(10, 2) NOT NULL,
    status TEXT DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Foreign Key constraint
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Orders tablosu için indexler
CREATE INDEX IF NOT EXISTS idx_orders_user_id ON orders(user_id);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);

-- UserSessions tablosu: Kullanıcı oturumlarını takip eder
CREATE TABLE IF NOT EXISTS user_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    session_token TEXT NOT NULL UNIQUE,
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Foreign Key constraint
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Index for session lookup
CREATE INDEX IF NOT EXISTS idx_sessions_token ON user_sessions(session_token);
CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON user_sessions(user_id);

-- AuditLog tablosu: Sistem değişikliklerini loglar
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    action TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id INTEGER,
    old_value TEXT,
    new_value TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Foreign Key constraint
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
);

-- Index for audit queries
CREATE INDEX IF NOT EXISTS idx_audit_user_id ON audit_log(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_entity ON audit_log(entity_type, entity_id);

-- Örnek veri ekleme (seed data)
INSERT OR IGNORE INTO users (username, email, password_hash, avatar_url) 
VALUES 
    ('alice', 'alice@example.com', 'hash123', '/avatars/alice.png'),
    ('bob', 'bob@example.com', 'hash456', '/avatars/bob.png'),
    ('charlie', 'charlie@example.com', 'hash789', NULL);

-- Örnek siparişler
INSERT OR IGNORE INTO orders (user_id, product_name, amount, status)
VALUES
    (1, 'Premium Subscription', 99.99, 'completed'),
    (1, 'API Credits', 25.00, 'completed'),
    (2, 'Basic Plan', 19.99, 'pending');
