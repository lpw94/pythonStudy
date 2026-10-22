/**
 * 用户管理页。
 *
 * 这一页是「按钮级权限」的演示重点：
 * - 页面本身需要 user:read 才能进来（其实是后端路由控制，前端只是跟着菜单）
 * - 「新建」「编辑」「删除」按钮分别按 user:create / user:update / user:delete 显隐
 * - 即使前端把按钮藏了，直接打接口后端还会再拦一次（403）——双保险
 *
 * 编辑用**部分更新**（PUT 只传要改的字段），不传的字段保持原样。
 */
import { useCallback, useEffect, useState } from 'react';
import { Button, Card, Form, Input, Modal, Popconfirm, Select, Space, Table, Tag } from 'antd';
import { DeleteOutlined, EditOutlined, PlusOutlined, ReloadOutlined, SearchOutlined } from '@ant-design/icons';
import { usePermission } from '@/access';
import { createUser, deleteUser, fetchRoleOptions, fetchUsers, updateUser } from '@/services/api';
import { ApiError } from '@/services/request';
import type { RoleItem, UserItem } from '@/types/api';
import { notify } from '@/services/notify';

interface CreateForm {
  username: string;
  password: string;
  nickname?: string;
  email?: string;
  role_codes: string[];
}

interface EditForm {
  nickname?: string;
  email?: string;
  password?: string;
  role_codes?: string[];
  is_active?: boolean;
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
  const [editing, setEditing] = useState<UserItem | null>(null);
  const [form] = Form.useForm<CreateForm & EditForm>();

  const canCreate = usePermission('user:create');
  const canUpdate = usePermission('user:update');
  const canDelete = usePermission('user:delete');

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await fetchUsers({ keyword, page, pageSize });
      setList(data.items);
      setTotal(data.meta.total);
    } catch (e) {
      notify.error(e instanceof ApiError ? e.message : '加载失败');
    } finally {
      setLoading(false);
    }
  }, [keyword, page, pageSize]);

  useEffect(() => {
    void load();
  }, [load]);

  // 角色下拉用 /api/roles/options（守卫 menu:read），比完整角色列表权限更宽
  useEffect(() => {
    fetchRoleOptions()
      .then(setRoles)
      .catch(() => setRoles([]));
  }, []);

  const openCreate = () => {
    setEditing(null);
    form.resetFields();
    form.setFieldsValue({ role_codes: [] });
    setModalOpen(true);
  };

  const openEdit = (row: UserItem) => {
    setEditing(row);
    form.resetFields();
    form.setFieldsValue({
      nickname: row.nickname,
      email: row.email,
      role_codes: row.roles.map((r) => r.code),
      is_active: row.is_active,
    });
    setModalOpen(true);
  };

  const onSubmit = async () => {
    const values = await form.validateFields();
    setSaving(true);
    try {
      if (editing) {
        // 部分更新：只传表单里有值的字段
        await updateUser(editing.id, {
          nickname: values.nickname,
          email: values.email,
          role_codes: values.role_codes,
          is_active: values.is_active,
          ...(values.password ? { password: values.password } : {}),
        });
        notify.success('保存成功');
      } else {
        await createUser(values);
        notify.success('创建成功');
      }
      setModalOpen(false);
      form.resetFields();
      void load();
    } catch (e) {
      notify.error(e instanceof ApiError ? e.message : '操作失败');
    } finally {
      setSaving(false);
    }
  };

  const onDelete = async (id: number) => {
    try {
      await deleteUser(id);
      notify.success('删除成功');
      void load();
    } catch (e) {
      notify.error(e instanceof ApiError ? e.message : '删除失败');
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
            <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
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
            width: 140,
            render: (_: unknown, row: UserItem) => (
              <Space size={0}>
                {canUpdate && (
                  <Button type="link" size="small" icon={<EditOutlined />} onClick={() => openEdit(row)}>
                    编辑
                  </Button>
                )}
                {canDelete ? (
                  <Popconfirm title="确认删除该用户？" onConfirm={() => onDelete(row.id)}>
                    <Button type="link" danger size="small" icon={<DeleteOutlined />}>
                      删除
                    </Button>
                  </Popconfirm>
                ) : (
                  <Tag>无 user:delete 权限</Tag>
                )}
              </Space>
            ),
          },
        ]}
      />

      <Modal
        title={editing ? `编辑用户：${editing.username}` : '新建用户'}
        open={modalOpen}
        onOk={onSubmit}
        onCancel={() => setModalOpen(false)}
        confirmLoading={saving}
        // forceRender：让 Form 常驻 DOM，否则 Modal 关闭时 Form 被卸载，
        // 而 useForm 的实例还在 —— antd 会警告「Instance created by useForm
        // is not connected to any Form element」。
        forceRender
        destroyOnHidden
      >
        <Form form={form} layout="vertical" preserve={false} initialValues={{ role_codes: [] }}>
          {!editing && (
            <>
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
              <Form.Item
                name="password"
                label="密码"
                rules={[{ required: true, min: 6, message: '至少 6 位' }]}
              >
                <Input.Password placeholder="至少 6 位" />
              </Form.Item>
            </>
          )}
          <Form.Item name="nickname" label="昵称">
            <Input placeholder="选填" />
          </Form.Item>
          <Form.Item name="email" label="邮箱">
            <Input placeholder="选填" />
          </Form.Item>
          <Form.Item name="role_codes" label="角色" extra="改角色就是改权限——权限由角色推导">
            <Select mode="multiple" options={roles.map((r) => ({ value: r.code, label: r.name }))} />
          </Form.Item>
          {editing && (
            <>
              <Form.Item name="password" label="重置密码" extra="留空表示不改">
                <Input.Password placeholder="至少 6 位" />
              </Form.Item>
              <Form.Item name="is_active" label="启用账号" valuePropName="checked">
                <Select
                  options={[
                    { value: true, label: '启用' },
                    { value: false, label: '禁用（无法登录）' },
                  ]}
                />
              </Form.Item>
            </>
          )}
        </Form>
      </Modal>
    </Card>
  );
}
