/**
 * 菜单管理页：展示「全量菜单」与「我的菜单」的差异。
 *
 * GET /api/menus  返回全部菜单（需要 menu:read）
 * GET /api/auth/menus 返回当前用户按角色过滤后的菜单
 *
 * 两边放一起对比，能直观看到权限模型在起作用：
 * operator 拿得到「菜单管理」这一项，但看不到「角色管理」——因为他没有该菜单权限。
 */
import { useEffect, useState } from 'react';
import { Card, Space, Tag, Tree, message } from 'antd';
import type { DataNode } from 'antd/es/tree';
import { fetchAllMenus, fetchMyMenus } from '@/services/api';
import { ApiError } from '@/services/request';
import { useAuth } from '@/store/auth';
import type { MenuItem } from '@/types/api';

/** MenuItem 树 → antd Tree 需要的数据结构 */
function toTreeData(menus: MenuItem[]): DataNode[] {
  return menus.map((m) => ({
    key: m.id,
    title: (
      <Space size={4}>
        <b>{m.name}</b>
        <Tag>{m.path}</Tag>
        {m.component && <Tag color="blue">{m.component}</Tag>}
        {m.permissions.map((p) => (
          <Tag key={p} color="green" style={{ fontSize: 11 }}>
            {p}
          </Tag>
        ))}
      </Space>
    ),
    ...(m.children.length ? { children: toTreeData(m.children) } : {}),
  }));
}

export default function MenuList() {
  const { profile } = useAuth();
  const [all, setAll] = useState<MenuItem[]>([]);
  const [mine, setMine] = useState<MenuItem[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setLoading(true);
    Promise.all([fetchAllMenus(), fetchMyMenus()])
      .then(([a, m]) => {
        setAll(a);
        setMine(m);
      })
      .catch((e) => message.error(e instanceof ApiError ? e.message : '加载失败'))
      .finally(() => setLoading(false));
  }, []);

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <Card size="small" title="全量菜单（GET /api/menus · 需要 menu:read）" loading={loading}>
        <Tree treeData={toTreeData(all)} defaultExpandAll selectable={false} />
      </Card>
      <Card
        size="small"
        title={`我的菜单（GET /api/auth/menus · 角色 ${profile?.roles.join('/') || '-'} 过滤后）`}
        loading={loading}
      >
        {mine.length ? (
          <Tree treeData={toTreeData(mine)} defaultExpandAll selectable={false} />
        ) : (
          <Tag color="red">当前账号没有任何菜单权限</Tag>
        )}
      </Card>
    </Space>
  );
}
