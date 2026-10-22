/**
 * 按钮级权限判定。
 *
 * 对标 admin-web 的 `src/access.ts`：它从 localStorage 读权限码数组再比对，
 * 这里改成直接读 Context 里的 profile.permissions——
 * 同一套语义，但不用再往 localStorage 里塞一份重复数据。
 *
 * 权限码是从「用户 → 角色 → 菜单 → 权限」推导出来的，
 * 所以前端不需要（也不应该）自己算权限，只负责拿码去比对。
 */
import { useAuth } from '@/store/auth';

/**
 * 是否拥有某个权限码。
 *
 * @param codes 单个或多个权限码；传数组时语义是「任一命中即可」
 */
export function usePermission(codes: string | string[]): boolean {
  const { profile } = useAuth();
  const owned = profile?.permissions ?? [];

  if (Array.isArray(codes)) {
    return codes.some((code) => owned.includes(code));
  }
  return owned.includes(codes);
}

/** 权限码集合的普通函数版本，给路由表这类非组件场景用 */
export function hasPermission(owned: string[], codes: string | string[]): boolean {
  if (Array.isArray(codes)) {
    return codes.some((code) => owned.includes(code));
  }
  return owned.includes(codes);
}
