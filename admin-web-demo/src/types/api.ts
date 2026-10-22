/**
 * 与后端 schemas.py 一一对应的类型定义。
 *
 * 手写 TS 类型而不是从 OpenAPI 生成，是这个 demo 的有意取舍：
 * 体量小、看得懂、改起来快；真实项目里应该用 openapi-typescript 自动生成，
 * 免得后端改了字段前端不报错。
 */

/** 令牌对，对应 TokenPair */
export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

/** 菜单项，对应 MenuOut（后端已把平铺数据组装成树） */
export interface MenuItem {
  id: number;
  name: string;
  path: string;
  /** 组件标识，形如 "Dashboard" / "system/user"，用于映射到本地组件 */
  component: string;
  route_name: string;
  icon: string;
  sort: number;
  visible: boolean;
  parent_id: number;
  /** 该菜单关联的权限码 */
  permissions: string[];
  children: MenuItem[];
}

/** 当前用户档案，对应 ProfileOut */
export interface Profile {
  id: number;
  username: string;
  nickname: string;
  email: string;
  roles: string[];
  permissions: string[];
  menus: MenuItem[];
}

export interface RoleRef {
  id: number;
  code: string;
  name: string;
}

export interface UserItem {
  id: number;
  username: string;
  nickname: string;
  email: string;
  is_active: boolean;
  roles: RoleRef[];
  created_at: string | null;
}

export interface PageMeta {
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface UserPage {
  items: UserItem[];
  meta: PageMeta;
}

export interface UserCreate {
  username: string;
  password: string;
  nickname?: string;
  email?: string;
  role_codes?: string[];
}

export interface RoleItem {
  id: number;
  code: string;
  name: string;
  remark: string;
}

/** 角色详情，对应 RoleOut */
export interface RoleDetail extends RoleItem {
  /** 关联的菜单 id */
  menu_ids: number[];
  /** 由关联菜单推导出的权限码 */
  permissions: string[];
  /** 该角色下的用户数 */
  user_count: number;
  created_at: string | null;
}

export interface RoleCreate {
  code: string;
  name: string;
  remark?: string;
  menu_ids?: number[];
}

export interface RoleUpdate {
  name?: string;
  remark?: string;
  menu_ids?: number[];
}

export interface MenuCreate {
  name: string;
  path: string;
  component?: string;
  route_name: string;
  icon?: string;
  sort?: number;
  visible?: boolean;
  parent_id?: number;
  permission_codes?: string[];
}

export interface MenuUpdate {
  name?: string;
  path?: string;
  component?: string;
  icon?: string;
  sort?: number;
  visible?: boolean;
  parent_id?: number;
  permission_codes?: string[];
}

/** 权限码，对应 PermissionOut */
export interface PermissionItem {
  id: number;
  code: string;
  name: string;
  /** 分组名，后端按它分栏 */
  group: string;
}
