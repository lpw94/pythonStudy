/**
 * 用户管理页。
 *
 * 这一页是「按钮级权限」的演示重点：
 * - 页面本身需要 user:read 才能进来（其实是后端路由控制，前端只是跟着菜单）
 * - 「新建」「删除」按钮分别按 user:create / user:delete 显隐
 * - 即使前端把按钮藏了，直接打接口后端还会再拦一次（403）——双保险
 */
import { useCallback, useEffect, useState } from 'react';
import { Button, Card, Form, Input, Modal, Popconfirm, Select, Space, Table, Tag, message } from 'antd';
import { DeleteOutlined, PlusOutlined, ReloadOutlined, SearchOutlined } from '@ant-design/icons';
import { usePermission } from '@/access';
import { createUser, deleteUser, fetchRoles, fetchUsers } from '@/services/api';
import { ApiError } from '@/services/request';
import type { RoleItem, UserItem } from '@/types/api';

interface CreateForm {
  username: string;
  password: string;
  nickname?: string;
  email?: string;
  role_codes: string[];
}

export default function UserList() {
  const [list, setList] = useState<UserItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [keyword, setKeyword] = useState('');
  const [loading, setLoading] = useState(false);
  const [roles, setRoles] = useState<RoleItem[]>([]);
  const [modalOpen, setModalOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form] = Form.useForm<CreateForm>();

  const canCreate = usePermission('user:create');
  const canDelete = usePermission('user:delete');

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await fetchUsers({ keyword, page, pageSize });
      setList(data.items);
      setTotal(data.meta.total);
    } catch (e) {
      message.error(e instanceof ApiError ? e.message : '加载失败');
    } finally {
      setLoading(false);
    }
  }, [keyword, page, pageSize]);

  useEffect(() => {
    void load();
  }, [load]);

  // 角色下拉需要 role:read；没有这个权限就拉不到，忽略错误即可
  useEffect(() => {
    fetchRoles()
      .then(setRoles)
      .catch(() => setRoles([]));
  }, []);

  const onCreate = async () => {
    const values = await form.validateFields();
    setSaving(true);
    try {
      await createUser(values);
      message.success('创建成功');
      setModalOpen(false);
      form.resetFields();
      void load();
    } catch (e) {
      message.error(e instanceof ApiError ? e.message : '创建失败');
    } finally {
      setSaving(false);
    }
  };

  const onDelete = async (id: number) => {
    try {
      await deleteUser(id);
      message.success('删除成功');
      void load();
    } catch (e) {
      message.error(e instanceof ApiError ? e.message : '删除失败');
    }
  };

  return (
    <Card
      size="small"
      title="用户管理"
      extra={
        <Space>
          <Input
            placeholder="搜索用户名 / 昵称"
            allowClear
            style={{ width: 200 }}
            prefix={<SearchOutlined />}
            onChange={(e) => {
              setKeyword(e.target.value);
              setPage(1);
            }}
          />
          <Button icon={<ReloadOutlined />} onClick={() => void load()}>
            刷新
          </Button>
          {canCreate && (
            <Button type="primary" icon={<PlusOutlined />} onClick={() => setModalOpen(true)}>
              新建用户
            </Button>
          )}
        </Space>
      }
    >
      <Table<UserItem>
        rowKey="id"
        size="small"
        loading={loading}
        dataSource={list}
        pagination={{
          current: page,
          pageSize,
          total,
          showSizeChanger: true,
          showTotal: (t) => `共 ${t} 条`,
          onChange: (p, ps) => {
            setPage(p);
            setPageSize(ps);
          },
        }}
        columns={[
          { title: 'ID', dataIndex: 'id', width: 60 },
          { title: '用户名', dataIndex: 'username', width: 140 },
          { title: '昵称', dataIndex: 'nickname' },
          { title: '邮箱', dataIndex: 'email' },
          {
            title: '角色',
            dataIndex: 'roles',
            render: (roles: UserItem['roles']) =>
              roles.length ? roles.map((r) => <Tag key={r.id}>{r.name}</Tag>) : '-',
          },
          {
            title: '状态',
            dataIndex: 'is_active',
            width: 80,
            render: (v: boolean) => (v ? <Tag color="green">启用</Tag> : <Tag color="red">禁用</Tag>),
          },
          {
            title: '操作',
            width: 100,
            render: (_: unknown, row: UserItem) =>
              canDelete ? (
                <Popconfirm title="确认删除该用户？" onConfirm={() => onDelete(row.id)}>
                  <Button type="link" danger size="small" icon={<DeleteOutlined />}>
                    删除
                  </Button>
                </Popconfirm>
              ) : (
                <Tag>无 user:delete 权限</Tag>
              ),
          },
        ]}
      />

      <Modal
        title="新建用户"
        open={modalOpen}
        onOk={onCreate}
        onCancel={() => setModalOpen(false)}
        confirmLoading={saving}
        destroyOnClose
      >
        <Form form={form} layout="vertical" preserve={false} initialValues={{ role_codes: [] }}>
          <Form.Item
            name="username"
            label="用户名"
            rules={[
              { required: true, message: '请输入用户名' },
              // 这条 pattern 是后端 UserCreate 的约束，前端同步一份做即时提示
              { pattern: /^[a-zA-Z0-9_.-]+$/, message: '只能包含字母数字 _ . -' },
            ]}
          >
            <Input placeholder="2-64 位，字母数字 _ . -" />
          </Form.Item>
          <Form.Item name="password" label="密码" rules={[{ required: true, min: 6, message: '至少 6 位' }]}>
            <Input.Password placeholder="至少 6 位" />
          </Form.Item>
          <Form.Item name="nickname" label="昵称">
            <Input placeholder="选填" />
          </Form.Item>
          <Form.Item name="email" label="邮箱">
            <Input placeholder="选填" />
          </Form.Item>
          <Form.Item name="role_codes" label="角色">
            <Select mode="multiple" options={roles.map((r) => ({ value: r.code, label: r.name }))} />
          </Form.Item>
        </Form>
      </Modal>
    </Card>
  );
}
