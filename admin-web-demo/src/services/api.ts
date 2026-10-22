/**
 * 接口层：一个后端路由对应一个函数，页面不直接拼 URL。
 *
 * 对标 admin-web 的 `src/services/*.ts`。
 */
import { http } from './request';
import type { MenuItem, Profile, RoleItem, TokenPair, UserCreate, UserItem, UserPage } from '@/types/api';

/** POST /api/auth/login —— 账号密码换令牌对 */
export function login(username: string, password: string) {
  return http.postAuth<TokenPair>('/api/auth/login', { username, password });
}

/** GET /api/auth/me —— 当前用户 + 权限码 + 菜单树，一次拿全 */
export function fetchProfile() {
  return http.get<Profile>('/api/auth/me');
}

/** GET /api/auth/menus —— 只要菜单树（刷新页面时单独重拉菜单用） */
export function fetchMyMenus() {
  return http.get<MenuItem[]>('/api/auth/menus');
}

/** GET /api/users —— 分页列表 */
export function fetchUsers(params: { keyword?: string; page?: number; pageSize?: number } = {}) {
  const { keyword = '', page = 1, pageSize = 10 } = params;
  const qs = new URLSearchParams({ keyword, page: String(page), page_size: String(pageSize) });
  return http.get<UserPage>(`/api/users?${qs.toString()}`);
}

/** POST /api/users —— 新建用户 */
export function createUser(payload: UserCreate) {
  return http.post<UserItem>('/api/users', payload);
}

/** DELETE /api/users/:id —— 删除用户 */
export function deleteUser(id: number) {
  return http.del<void>(`/api/users/${id}`);
}

/** GET /api/roles —— 角色下拉框数据，需要 menu:read 权限 */
export function fetchRoles() {
  return http.get<RoleItem[]>('/api/roles');
}

/** GET /api/menus —— 全量菜单树（管理端），需要 menu:read 权限 */
export function fetchAllMenus() {
  return http.get<MenuItem[]>('/api/menus');
}
