/**
 * 工作台：展示当前账号拿到的权限码与菜单树，用来肉眼验证「后端推导 → 前端渲染」。
 */
import { Card, Col, Row, Space, Tag, Typography } from 'antd';
import { useAuth } from '@/store/auth';
import { hasPermission } from '@/access';
import type { MenuItem } from '@/types/api';

const { Title, Paragraph, Text } = Typography;

const CHECKS = [
  { code: 'user:read', label: '能进用户管理' },
  { code: 'user:delete', label: '能删用户' },
  { code: 'role:read', label: '能看角色' },
  { code: 'menu:read', label: '能看菜单' },
];

/** 菜单树转成缩进列表，比截图直观 */
function renderTree(menus: MenuItem[], depth = 0) {
  if (!menus.length) return <Text type="secondary">（无）</Text>;
  return (
    <ul style={{ listStyle: 'none', paddingLeft: depth ? 18 : 0, margin: 0 }}>
      {menus.map((m) => (
        <li key={m.id} style={{ margin: '2px 0' }}>
          <Space size={4}>
            <Text strong>{m.name}</Text>
            <Text type="secondary" style={{ fontSize: 12 }}>
              {m.path}
            </Text>
            {m.visible === false && <Tag color="default">hidden</Tag>}
            {m.permissions.map((p) => (
              <Tag key={p} color="blue" style={{ fontSize: 11 }}>
                {p}
              </Tag>
            ))}
          </Space>
          {renderTree(m.children, depth + 1)}
        </li>
      ))}
    </ul>
  );
}

export default function Dashboard() {
  const { profile } = useAuth();
  const owned = profile?.permissions ?? [];

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <div>
        <Title level={4} style={{ marginBottom: 4 }}>
          你好，{profile?.nickname || profile?.username}
        </Title>
        <Paragraph type="secondary" style={{ marginBottom: 0 }}>
          菜单和权限都由后端按角色推导下发，不是前端写死的。换账号登录能看到差异。
        </Paragraph>
      </div>

      <Row gutter={16}>
        <Col xs={24} lg={12}>
          <Card title="我的权限码" size="small">
            {owned.length ? (
              <Space wrap size={4}>
                {owned.map((p) => (
                  <Tag key={p} color="green">
                    {p}
                  </Tag>
                ))}
              </Space>
            ) : (
              <Text type="secondary">（无）</Text>
            )}
            <div style={{ marginTop: 16 }}>
              {CHECKS.map((c) => (
                <div key={c.code} style={{ marginBottom: 4 }}>
                  <Text type={hasPermission(owned, c.code) ? 'success' : 'secondary'}>
                    {hasPermission(owned, c.code) ? '✓ 有' : '✗ 无'} {c.label}
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      （{c.code}）
                    </Text>
                  </Text>
                </div>
              ))}
            </div>
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card title="我的菜单树（后端下发）" size="small">
            {renderTree(profile?.menus ?? [])}
          </Card>
        </Col>
      </Row>

      <Card title="接口文档" size="small">
        <Paragraph style={{ marginBottom: 8 }}>
          后端 FastAPI 自带 Swagger：<Text code>http://127.0.0.1:8020/docs</Text>
          ，可以带着 Access Token 点「Authorize」直接试接口。
        </Paragraph>
      </Card>
    </Space>
  );
}
