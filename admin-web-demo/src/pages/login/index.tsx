/**
 * 登录页。
 *
 * 对标 admin-web 的 `src/pages/User/login/index.tsx`，
 * 但砍掉了验证码 / AES 加密 / SSO / 多环境分支那些与权限路由无关的部分，
 * 只保留「提交 → 拿令牌 → 拉档案 → 跳首页」这条主干。
 */
import { useState } from 'react';
import { Alert, Button, Card, Form, Input, Space, Tag, Typography } from 'antd';
import { LockOutlined, UserOutlined } from '@ant-design/icons';
import { Navigate, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '@/store/auth';

const { Title, Paragraph, Text } = Typography;

interface LoginForm {
  username: string;
  password: string;
}

/** 种子账号，摆在页面上省得翻 README */
const DEMO_ACCOUNTS = [
  { username: 'admin', password: 'admin123', role: '全部权限' },
  { username: 'operator', password: 'op123456', role: '无角色管理' },
  { username: 'viewer', password: 'view123', role: '只有工作台' },
];

export default function Login() {
  const { login, profile } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [form] = Form.useForm<LoginForm>();

  // 已登录还停在登录页 → 直接进首页
  if (profile) return <Navigate to="/" replace />;

  const from = (location.state as { from?: string } | null)?.from ?? '/';

  const onFinish = async (values: LoginForm) => {
    setLoading(true);
    setError('');
    try {
      await login(values.username, values.password);
      // 用 replace：登录页不该留在历史里，浏览器后退不该退回登录页
      navigate(from === '/login' ? '/' : from, { replace: true });
    } catch (e) {
      setError(e instanceof Error ? e.message : '登录失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-wrap">
      <Card style={{ width: 400 }}>
        <Title level={3} style={{ textAlign: 'center', marginBottom: 4 }}>
          admin-web demo
        </Title>
        <Paragraph type="secondary" style={{ textAlign: 'center' }}>
          对接 admin-api：登录 → 权限码 → 动态菜单路由
        </Paragraph>

        {error && <Alert type="error" message={error} showIcon style={{ marginBottom: 16 }} />}

        <Form form={form} layout="vertical" onFinish={onFinish} size="large">
          <Form.Item name="username" rules={[{ required: true, message: '请输入用户名' }]}>
            <Input prefix={<UserOutlined />} placeholder="用户名" autoComplete="username" />
          </Form.Item>
          <Form.Item name="password" rules={[{ required: true, message: '请输入密码' }]}>
            <Input.Password
              prefix={<LockOutlined />}
              placeholder="密码"
              autoComplete="current-password"
              onPressEnter={() => form.submit()}
            />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" block loading={loading}>
              登录
            </Button>
          </Form.Item>
        </Form>

        <Space direction="vertical" size={4} style={{ width: '100%' }}>
          <Text type="secondary" style={{ fontSize: 12 }}>
            种子账号（点击填充）：
          </Text>
          <Space wrap size={4}>
            {DEMO_ACCOUNTS.map((a) => (
              <Tag
                key={a.username}
                style={{ cursor: 'pointer' }}
                onClick={() => form.setFieldsValue({ username: a.username, password: a.password })}
              >
                {a.username} / {a.password} · {a.role}
              </Tag>
            ))}
          </Space>
        </Space>
      </Card>
    </div>
  );
}
