/**
 * 登录态 Context。
 *
 * 对标 admin-web 的 `getInitialState()` + redux user model：
 * 页面启动时拉一次 /api/auth/me，把 profile / permissions / menus 塞进全局 store，
 * 之后所有组件从 useAuth() 读，不再重复请求。
 */
import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { fetchProfile, login as loginApi } from '@/services/api';
import { clearTokens, getAccessToken, saveTokens } from '@/services/token';
import type { Profile } from '@/types/api';

interface AuthState {
  profile: Profile | null;
  /** 首次档案加载是否完成（含「未登录」这个结论），用于避免路由闪烁 */
  initializing: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
  /** 重新拉档案，用于角色变更后刷新权限 */
  reload: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [initializing, setInitializing] = useState(true);

  const reload = useCallback(async () => {
    if (!getAccessToken()) {
      setProfile(null);
      return;
    }
    try {
      setProfile(await fetchProfile());
    } catch {
      // 令牌无效且刷新也失败 → request 层已经清过 storage 了，这里只同步状态
      clearTokens();
      setProfile(null);
    }
  }, []);

  // 应用启动：先看有没有令牌，有就拉档案
  useEffect(() => {
    void reload().finally(() => setInitializing(false));
  }, [reload]);

  const login = useCallback(async (username: string, password: string) => {
    const tokens = await loginApi(username, password);
    saveTokens(tokens);
    setProfile(await fetchProfile());
  }, []);

  const logout = useCallback(() => {
    clearTokens();
    setProfile(null);
  }, []);

  const value = useMemo(
    () => ({ profile, initializing, login, logout, reload }),
    [profile, initializing, login, logout, reload],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  // 忘了包 Provider 时给出明确报错，比 undefined.xxx 报错好排查
  if (!ctx) throw new Error('useAuth 必须在 <AuthProvider> 内部使用');
  return ctx;
}
