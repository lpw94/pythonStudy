/**
 * 受保护布局：左侧菜单由后端返回的菜单树渲染，右侧是路由出口。
 *
 * 菜单渲染做了两件 admin-web 也在做的事：
 * 1. 过滤 visible=false 的菜单（后端可以配隐藏菜单）
 * 2. 父级没有任何可见子菜单时不渲染这一项（避免出现空的可展开分组）
 *
 * 出口用 <Outlet /> 而不是 children —— 这是 react-router 嵌套路由的标准姿势：
 * 父 <Route> 渲染布局，布局里的 Outlet 就是子路由渲染的位置。
 */
import { useMemo, useState } from 'react';
import { Layout, Menu, Tag, Button, Space } from 'antd';
import { Outlet, useLocation, useNavigate } from 'react-router-dom';
import {
  DashboardOutlined,
  SettingOutlined,
  TeamOutlined,
  UserOutlined,
  MenuOutlined,
  LogoutOutlined,
} from '@ant-design/icons';
import { useAuth } from '@/store/auth';
import type { MenuItem } from '@/types/api';

const { Header, Sider, Content } = Layout;

/** 菜单 icon 字段是字符串，映射到真实组件；没配就用默认图标 */
const ICONS: Record<string, React.ReactNode> = {
  dashboard: <DashboardOutlined />,
  setting: <SettingOutlined />,
  team: <TeamOutlined />,
  user: <UserOutlined />,
  menu: <MenuOutlined />,
};

type AntdItem = { key: string; label: string; icon?: React.ReactNode; children?: AntdItem[] };

function toAntdItems(menus: MenuItem[]): AntdItem[] {
  return menus
    .filter((m) => m.visible !== false)
    .map((m) => {
      const children = toAntdItems(m.children ?? []);
      // 有子菜单但子菜单全被 visible=false 过滤掉了 → 这个分组没有意义
      if (m.children.length > 0 && children.length === 0) return null;
      return {
        key: m.path,
        label: m.name,
        icon: ICONS[m.icon] ?? <MenuOutlined />,
        ...(children.length > 0 ? { children } : {}),
      };
    })
    .filter(Boolean) as AntdItem[];
}

export default function AppLayout() {
  const { profile, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(false);

  const items = useMemo(() => toAntdItems(profile?.menus ?? []), [profile]);

  // 当前高亮的菜单项：取最长匹配前缀，子路径也能正确高亮父级
  const selectedKeys = useMemo(() => {
    const paths = items.flatMap((i) => [i.key, ...(i.children ?? []).map((c) => c.key)]);
    const hit = paths.filter((p) => location.pathname === p || location.pathname.startsWith(`${p}/`));
    return hit.sort((a, b) => b.length - a.length).slice(0, 1);
  }, [items, location.pathname]);

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider collapsible collapsed={collapsed} onCollapse={setCollapsed} breakpoint="lg">
        <div className="app-logo">{collapsed ? 'AW' : 'admin-web demo'}</div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={selectedKeys}
          items={items}
          onClick={({ key }) => navigate(key)}
        />
      </Sider>
      <Layout>
        <Header className="app-header">
          <Space>
            <b>权限路由联调</b>
            <Tag color="blue">{profile?.roles.join(' / ') || '-'}</Tag>
            <Tag>{profile?.nickname || profile?.username}</Tag>
          </Space>
          <Button
            icon={<LogoutOutlined />}
            size="small"
            onClick={() => {
              logout();
              navigate('/login');
            }}
          >
            退出
          </Button>
        </Header>
        <Content className="app-content">
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  );
}
