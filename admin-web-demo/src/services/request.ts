/**
 * 请求层：统一 baseURL、Bearer 注入、401 自动刷新并重放。
 *
 * 对标 admin-web 的 `src/services/request.ts`（umi-request extend + 拦截器），
 * 这里用原生 fetch 手写一遍，目的是看清「拦截器」到底做了什么。
 */
import { clearTokens, getAccessToken, getRefreshToken, saveTokens } from './token';
import type { TokenPair } from '@/types/api';
import { notify } from '@/services/notify';

const API_BASE = import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8020';

/** 后端统一用 detail 字段放错误文案 */
interface ApiErrorBody {
  detail?: string;
}

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

interface RequestOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'DELETE';
  body?: unknown;
  /** 内部用：标记这是刷新令牌后重放的请求，避免无限递归 */
  _retried?: boolean;
  /** 内部用：刷新请求本身不能再触发刷新 */
  _skipAuth?: boolean;
}

/**
 * 刷新中的单例 Promise。
 *
 * 关键点：页面初始化往往并发发好几个请求，它们会**同时** 401。
 * 如果每个请求各自去刷新，会连打 N 次 /api/auth/refresh，
 * 而后端签发的 refresh_token 是无状态的倒不会失效，但会浪费且可能互相覆盖。
 * 用一个共享的 Promise 让它们等同一次刷新——这就是「令牌刷新锁」。
 */
let refreshPromise: Promise<boolean> | null = null;

async function refreshTokens(): Promise<boolean> {
  if (refreshPromise) return refreshPromise;

  refreshPromise = (async () => {
    const refreshToken = getRefreshToken();
    if (!refreshToken) return false;
    try {
      const res = await fetch(`${API_BASE}/api/auth/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: refreshToken }),
      });
      if (!res.ok) return false;
      const tokens = (await res.json()) as TokenPair;
      saveTokens(tokens);
      return true;
    } catch {
      return false;
    } finally {
      // 无论成败都要解锁，否则后续请求会永远等一个已完成的 Promise
      refreshPromise = null;
    }
  })();

  return refreshPromise;
}

async function rawRequest<T>(url: string, options: RequestOptions = {}): Promise<T> {
  const { method = 'GET', body, _retried, _skipAuth } = options;

  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (!_skipAuth) {
    const token = getAccessToken();
    if (token) headers.Authorization = `Bearer ${token}`;
  }

  const res = await fetch(`${API_BASE}${url}`, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });

  // 204 No Content：没有响应体，不能 json()
  if (res.status === 204) return undefined as T;

  const text = await res.text();
  const data = text ? JSON.parse(text) : null;

  if (!res.ok) {
    // 401 且不是刷新请求 → 先尝试刷新令牌，成功就把原请求重放一次
    if (res.status === 401 && !_skipAuth && !_retried) {
      const ok = await refreshTokens();
      if (ok) return rawRequest<T>(url, { ...options, _retried: true });
      // 刷新失败说明登录态彻底失效，清干净回登录页
      clearTokens();
      notify.error('登录已过期，请重新登录');
      // 用 replace 而不是 push：过期跳转不该在历史里留一条返回记录
      window.location.replace('/login');
      throw new ApiError(401, '登录已过期');
    }

    const detail = (data as ApiErrorBody | null)?.detail;
    throw new ApiError(res.status, detail || `请求失败（HTTP ${res.status}）`);
  }

  return data as T;
}

export const http = {
  get: <T>(url: string) => rawRequest<T>(url),
  post: <T>(url: string, body?: unknown) => rawRequest<T>(url, { method: 'POST', body }),
  put: <T>(url: string, body?: unknown) => rawRequest<T>(url, { method: 'PUT', body }),
  del: <T>(url: string) => rawRequest<T>(url, { method: 'DELETE' }),
  /** 登录接口专用：不能带 Bearer（还没令牌），失败也不能触发刷新 */
  postAuth: <T>(url: string, body?: unknown) =>
    rawRequest<T>(url, { method: 'POST', body, _skipAuth: true }),
};

export { API_BASE };
