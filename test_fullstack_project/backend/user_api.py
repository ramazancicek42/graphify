"""
Backend User API - FastAPI örneği

Bu modül, kullanıcı yönetimi için REST API endpoint'lerini tanımlar.
Her endpoint, veritabanı işlemleriyle bağlantılıdır.
"""

from fastapi import FastAPI, HTTPException, Depends, UploadFile, File
from pydantic import BaseModel, EmailStr
from typing import Optional, List
import sqlite3

app = FastAPI(title="User Management API")

# Database connection helper
def get_db():
    conn = sqlite3.connect("app.db")
    try:
        yield conn
    finally:
        conn.close()


# Pydantic models
class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str


class UserUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    avatarUrl: Optional[str] = None


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    avatarUrl: Optional[str] = None


# CRUD Operations
@app.get("/api/v1/users", response_model=List[UserResponse])
async def list_users(db=Depends(get_db)):
    """
    Tüm kullanıcıları listeler
    """
    cursor = db.cursor()
    cursor.execute("SELECT id, username, email, avatar_url FROM users")
    rows = cursor.fetchall()
    
    return [
        UserResponse(
            id=row[0],
            username=row[1],
            email=row[2],
            avatarUrl=row[3]
        )
        for row in rows
    ]


@app.get("/api/v1/users/{user_id}", response_model=UserResponse)
async def get_user(user_id: int, db=Depends(get_db)):
    """
    Belirli bir kullanıcıyı getirir
    """
    cursor = db.cursor()
    cursor.execute(
        "SELECT id, username, email, avatar_url FROM users WHERE id = ?",
        (user_id,)
    )
    row = cursor.fetchone()
    
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    
    return UserResponse(
        id=row[0],
        username=row[1],
        email=row[2],
        avatarUrl=row[3]
    )


@app.put("/api/v1/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    user_data: UserUpdate,
    db=Depends(get_db)
):
    """
    Kullanıcı bilgilerini günceller
    
    Bu fonksiyon Users tablosunda UPDATE işlemi yapar.
    """
    cursor = db.cursor()
    
    # Güncellenecek alanları hazırla
    updates = []
    values = []
    
    if user_data.username is not None:
        updates.append("username = ?")
        values.append(user_data.username)
    
    if user_data.email is not None:
        updates.append("email = ?")
        values.append(user_data.email)
    
    if user_data.avatarUrl is not None:
        updates.append("avatar_url = ?")
        values.append(user_data.avatarUrl)
    
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    
    values.append(user_id)
    
    query = f"UPDATE users SET {', '.join(updates)} WHERE id = ?"
    cursor.execute(query, values)
    db.commit()
    
    # Güncellenen kullanıcıyı getir
    cursor.execute(
        "SELECT id, username, email, avatar_url FROM users WHERE id = ?",
        (user_id,)
    )
    row = cursor.fetchone()
    
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    
    return UserResponse(
        id=row[0],
        username=row[1],
        email=row[2],
        avatarUrl=row[3]
    )


@app.post("/api/v1/users/{user_id}/avatar", response_model=dict)
async def upload_avatar(
    user_id: int,
    file: UploadFile = File(...),
    db=Depends(get_db)
):
    """
    Kullanıcı avatarını yükler
    
    Dosyayı depolara yükler ve URL'yi Users tablosuna kaydeder.
    """
    # Dosya yükleme simülasyonu
    avatar_url = f"/storage/avatars/{user_id}_{file.filename}"
    
    cursor = db.cursor()
    cursor.execute(
        "UPDATE users SET avatar_url = ? WHERE id = ?",
        (avatar_url, user_id)
    )
    db.commit()
    
    return {"avatarUrl": avatar_url}


@app.delete("/api/v1/users/{user_id}")
async def delete_user(user_id: int, db=Depends(get_db)):
    """
    Kullanıcıyı siler
    
    Users tablosundan kaydı siler.
    """
    cursor = db.cursor()
    cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
    db.commit()
    
    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {"message": "User deleted successfully"}


@app.post("/api/v1/users", response_model=UserResponse)
async def create_user(user_data: UserCreate, db=Depends(get_db)):
    """
    Yeni kullanıcı oluşturur
    
    Users tablosuna INSERT işlemi yapar.
    """
    cursor = db.cursor()
    
    try:
        cursor.execute(
            "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
            (user_data.username, user_data.email, hash_password(user_data.password))
        )
        db.commit()
        user_id = cursor.lastrowid
        
        return UserResponse(
            id=user_id,
            username=user_data.username,
            email=user_data.email
        )
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="Username or email already exists")


def hash_password(password: str) -> str:
    """Parola hash'leme (basitleştirilmiş)"""
    import hashlib
    return hashlib.sha256(password.encode()).hexdigest()


# Order API - İlişkili tablo örneği
@app.get("/api/v1/users/{user_id}/orders")
async def get_user_orders(user_id: int, db=Depends(get_db)):
    """
    Kullanıcının siparişlerini getirir
    
    Users ve Orders tablolarını JOIN ile birleştirir.
    """
    cursor = db.cursor()
    cursor.execute("""
        SELECT o.id, o.product_name, o.amount, o.created_at
        FROM orders o
        INNER JOIN users u ON o.user_id = u.id
        WHERE u.id = ?
    """, (user_id,))
    
    rows = cursor.fetchall()
    
    return [
        {
            "id": row[0],
            "product_name": row[1],
            "amount": row[2],
            "created_at": row[3]
        }
        for row in rows
    ]
