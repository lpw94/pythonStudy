/**
 * 令牌存储。
 *
 * 为什么单独抽一层：localStorage 的 key 名是「字符串约定」，
 * 散落在各处写字符串迟早写错。真实项目里通常还会再套一层
 * 加密存储或 httpOnly cookie，这里为了看清流程就用裸的 localStorage。
 */
import type { TokenPair } from '@/types/api';

const ACCESS_KEY = 'admin_web_demo_access_token';
const REFRESH_KEY = 'admin_web_demo_refresh_token';

export function getAccessToken(): string | null {
  return localStorage.getItem(ACCESS_KEY);
}

export function getRefreshToken(): string | null {
  return localStorage.getItem(REFRESH_KEY);
}

export function saveTokens(tokens: TokenPair): void {
  localStorage.setItem(ACCESS_KEY, tokens.access_token);
  localStorage.setItem(REFRESH_KEY, tokens.refresh_token);
}

export function clearTokens(): void {
  localStorage.removeItem(ACCESS_KEY);
  localStorage.removeItem(REFRESH_KEY);
}
