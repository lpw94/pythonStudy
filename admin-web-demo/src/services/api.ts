/**
 * 接口层：一个后端路由对应一个函数，页面不直接拼 URL。
 *
 * 对标 admin-web 的 `src/services/*.ts`。
 */
import { http } from './request';
import type {
  MenuCreate,
  MenuItem,
  MenuUpdate,
  PermissionItem,
  Profile,
  RoleCreate,
  RoleDetail,
  RoleItem,
  RoleUpdate,
  TokenPair,
  UserCreate,
  UserItem,
  UserPage,
} from '@/types/api';

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

/** PUT /api/users/:id —— 更新用户（部分更新，只传要改的字段） */
export function updateUser(id: number, payload: Partial<UserItem> & { role_codes?: string[]; password?: string }) {
  return http.put<UserItem>(`/api/users/${id}`, payload);
}

/**
 * GET /api/roles/options —— 角色下拉框数据，需要 menu:read 权限
 *
 * 注意和 `/api/roles` 的区别：
 * - `/api/roles` 守卫 role:read，返回完整角色（含权限码、用户数）
 * - `/api/roles/options` 守卫 menu:read，只要 id/code/name/remark
 *
 * 「能改用户」和「能管角色」是两种能力，所以分成两个接口。
 */
export function fetchRoleOptions() {
  return http.get<RoleItem[]>('/api/roles/options');
}

/** GET /api/roles —— 完整角色列表，需要 role:read 权限 */
export function fetchRoles() {
  return http.get<RoleDetail[]>('/api/roles');
}

/** POST /api/roles —— 新建角色 */
export function createRole(payload: RoleCreate) {
  return http.post<RoleDetail>('/api/roles', payload);
}

/** PUT /api/roles/:id —— 更新角色（改菜单 = 改权限） */
export function updateRole(id: number, payload: RoleUpdate) {
  return http.put<RoleDetail>(`/api/roles/${id}`, payload);
}

/** DELETE /api/roles/:id —— 删除角色 */
export function deleteRole(id: number) {
  return http.del<void>(`/api/roles/${id}`);
}

/** GET /api/menus —— 全量菜单树（管理端），需要 menu:read 权限 */
export function fetchAllMenus() {
  return http.get<MenuItem[]>('/api/menus');
}

/** GET /api/menus/flat —— 全量菜单（平铺），多选框用 */
export function fetchFlatMenus() {
  return http.get<MenuItem[]>('/api/menus/flat');
}

/** GET /api/permissions —— 全部权限码，菜单编辑页选权限用 */
export function fetchPermissions() {
  return http.get<PermissionItem[]>('/api/permissions');
}

/** POST /api/menus —— 新建菜单 */
export function createMenu(payload: MenuCreate) {
  return http.post<MenuItem>('/api/menus', payload);
}

/** PUT /api/menus/:id —— 更新菜单 */
export function updateMenu(id: number, payload: MenuUpdate) {
  return http.put<MenuItem>(`/api/menus/${id}`, payload);
}

/** DELETE /api/menus/:id —— 删除菜单 */
export function deleteMenu(id: number) {
  return http.del<void>(`/api/menus/${id}`);
}
