/**
 * 动态路由：按后端返回的菜单树注册路由。
 *
 * 对标 admin-web 的 `router.addRoute()` —— Umi 会在运行时把菜单树 patch 进
 * clientRoutes；这里用 react-router 的描述式路由实现：启动时根据
 * profile.menus 动态生成 <Route> 数组，等价于「运行时注册路由」。
 *
 * 为什么权限要由后端下发路由：路由和权限是同一套东西。
 * 菜单没权限 → 路由不该注册 → 地址栏手输也进不去，
 * 而不是进得去然后页面里报 403。
 */
import { useMemo } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';
import { Button, Result, Spin } from 'antd';
import { useNavigate } from 'react-router-dom';
import AppLayout from '@/components/AppLayout';
import { useAuth } from '@/store/auth';
import Forbidden from '@/pages/Forbidden';
import Dashboard from '@/pages/dashboard';
import Login from '@/pages/login';
import MenuList from '@/pages/system/menu';
import RoleList from '@/pages/system/role';
import UserList from '@/pages/system/user';
import type { MenuItem } from '@/types/api';

/** component 字符串 → 本地组件。新增页面时在这里登记一行。 */
const COMPONENT_MAP: Record<string, React.ComponentType> = {
  Dashboard,
  'system/user': UserList,
  'system/role': RoleList,
  'system/menu': MenuList,
};

/**
 * 把一棵菜单树转成 react-router 的 Route 数组。
 *
 * 分组菜单（component 为空或 'Layout'）自己没有页面，
 * 只用它来嵌套子路由。
 */
function buildRoutes(menus: MenuItem[], basePath = ''): React.ReactElement[] {
  const routes: React.ReactElement[] = [];

  for (const menu of menus) {
    if (menu.visible === false) continue;

    const Comp = COMPONENT_MAP[menu.component];
    // 菜单 path 是绝对路径（后端给的就是 /system/user），直接用作 Route path
    const fullPath = menu.path.startsWith('/') ? menu.path : `${basePath}/${menu.path}`.replace(/\/+/g, '/');

    if (Comp) {
      routes.push(<Route key={menu.route_name} path={fullPath} element={<Comp />} />);
    } else if (menu.children.length > 0) {
      routes.push(
        <Route key={menu.route_name} path={fullPath}>
          {buildRoutes(menu.children, fullPath)}
        </Route>,
      );
    }
  }

  return routes;
}

export default function AppRouter() {
  const { profile, initializing } = useAuth();
  const navigate = useNavigate();

  // menus 变了就重建路由数组——这就是 addRoute 的等价物
  const dynamicRoutes = useMemo(() => buildRoutes(profile?.menus ?? []), [profile]);
  const homePath = profile?.menus[0]?.path ?? '/403';

  if (initializing) {
    return (
      <div className="page-center">
        {/* Spin 的 tip 只在 nest / fullscreen 模式下生效。
            这里用 fullscreen——初始化阶段整页都该被遮住，
            等登录态校验完再渲染真实界面，避免闪烁。 */}
        <Spin size="large" fullscreen tip="正在校验登录态…" />
      </div>
    );
  }

  return (
    <Routes>
      <Route path="/login" element={<Login />} />

      {/* 未登录：所有路径一律回登录页，并把来源记在 state 里用于登录后跳回 */}
      {!profile && <Route path="*" element={<Navigate to="/login" replace state={{ from: location.pathname }} />} />}

      {profile && (
        <Route path="/" element={<AppLayout />}>
          <Route index element={<Navigate to={homePath} replace />} />
          <Route path="403" element={<Forbidden />} />
          {dynamicRoutes}
        </Route>
      )}

      {profile && (
        <Route
          path="*"
          element={
            <Result
              status="404"
              title="404"
              subTitle="页面不存在或该路由未在你的权限范围内"
              extra={
                <Button type="primary" onClick={() => navigate(homePath)}>
                  回到首页
                </Button>
              }
            />
          }
        />
      )}
    </Routes>
  );
}
