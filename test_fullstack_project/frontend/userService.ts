// Frontend User Service - React/TypeScript örneği

import axios from 'axios';

const API_BASE = '/api/v1';

export interface UserProfile {
  id: number;
  username: string;
  email: string;
  avatarUrl?: string;
}

/**
 * Kullanıcı profilini getirir
 */
export async function getUserProfile(userId: number): Promise<UserProfile> {
  const response = await axios.get(`${API_BASE}/users/${userId}`);
  return response.data;
}

/**
 * Kullanıcı profilini günceller
 */
export async function updateUserProfile(
  userId: number, 
  data: Partial<UserProfile>
): Promise<UserProfile> {
  const response = await axios.put(`${API_BASE}/users/${userId}`, data);
  return response.data;
}

/**
 * Kullanıcı avatarını yükler
 */
export async function uploadUserAvatar(
  userId: number, 
  file: File
): Promise<{ avatarUrl: string }> {
  const formData = new FormData();
  formData.append('avatar', file);
  
  const response = await axios.post(
    `${API_BASE}/users/${userId}/avatar`,
    formData,
    { headers: { 'Content-Type': 'multipart/form-data' } }
  );
  return response.data;
}

/**
 * Kullanıcıyı siler
 */
export async function deleteUser(userId: number): Promise<void> {
  await axios.delete(`${API_BASE}/users/${userId}`);
}

/**
 * Tüm kullanıcıları listeler
 */
export async function listUsers(): Promise<UserProfile[]> {
  const response = await axios.get(`${API_BASE}/users`);
  return response.data;
}

// React Component örneği
import React, { useState, useEffect } from 'react';

interface UserFormProps {
  userId: number;
}

export const UserForm: React.FC<UserFormProps> = ({ userId }) => {
  const [user, setUser] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      const userData = await getUserProfile(userId);
      setUser(userData);
      setLoading(false);
    }
    load();
  }, [userId]);

  const handleUpdate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (user) {
      const updated = await updateUserProfile(userId, user);
      setUser(updated);
    }
  };

  if (loading) return <div>Loading...</div>;
  if (!user) return <div>User not found</div>;

  return (
    <form onSubmit={handleUpdate}>
      <input
        value={user.username}
        onChange={(e) => setUser({ ...user, username: e.target.value })}
      />
      <input
        value={user.email}
        onChange={(e) => setUser({ ...user, email: e.target.value })}
      />
      <button type="submit">Save Changes</button>
      <button type="button" onClick={() => deleteUser(userId)}>
        Delete Account
      </button>
    </form>
  );
};
