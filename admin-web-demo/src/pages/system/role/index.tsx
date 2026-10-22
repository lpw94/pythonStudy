/**
 * 角色管理页：列表 + 新建 + 编辑（勾菜单 = 授权）+ 删除。
 *
 * 关键概念：**权限码不是直接挂在角色上的**，而是挂在菜单上。
 * 所以「给角色授权」这个动作在前端表现为「勾选菜单」，
 * 提交的是 `menu_ids`，后端再从菜单推导出的权限码回传。
 *
 * 这也是为什么这个页面需要 `role:read` / `role:write`，
 * 而不是 `menu:read`——能看角色和能改角色是两种能力。
 */
import { useEffect, useMemo, useState } from 'react';
import { Alert, Button, Card, Form, Input, Modal, Popconfirm, Select, Space, Table, Tag } from 'antd';
import { createRole, deleteRole, fetchFlatMenus, fetchRoles, updateRole } from '@/services/api';
import { ApiError } from '@/services/request';
import { usePermission } from '@/access';
import type { MenuItem, RoleDetail } from '@/types/api';
import { notify } from '@/services/notify';

/** 平铺菜单 → { label, value }，给 antd Select 用 */
function toMenuOptions(menus: MenuItem[]): Array<{ label: string; value: number }> {
  return menus.map((m) => ({
    label: m.parent_id ? `　└ ${m.name}` : m.name,
    value: m.id,
  }));
}

export default function RoleList() {
  const canWrite = usePermission('role:write');
  const [list, setList] = useState<RoleDetail[]>([]);
  const [menus, setMenus] = useState<MenuItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [editing, setEditing] = useState<RoleDetail | null>(null);
  const [open, setOpen] = useState(false);
  const [form] = Form.useForm();

  const menuOptions = useMemo(() => toMenuOptions(menus), [menus]);

  const load = () => {
    setLoading(true);
    Promise.all([fetchRoles(), fetchFlatMenus()])
      .then(([r, m]) => {
        setList(r);
        setMenus(m);
      })
      .catch((e) => notify.error(e instanceof ApiError ? e.message : '加载失败'))
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  const openCreate = () => {
    setEditing(null);
    form.resetFields();
    form.setFieldsValue({ code: '', name: '', remark: '', menu_ids: [] });
    setOpen(true);
  };

  const openEdit = (role: RoleDetail) => {
    setEditing(role);
    form.setFieldsValue({
      code: role.code,
      name: role.name,
      remark: role.remark,
      menu_ids: role.menu_ids,
    });
    setOpen(true);
  };

  const submit = async () => {
    const values = await form.validateFields();
    try {
      if (editing) {
        // code 不给后端：角色 code 创建后不可改（用户身上存的是 code）
        await updateRole(editing.id, {
          name: values.name,
          remark: values.remark,
          menu_ids: values.menu_ids ?? [],
        });
        notify.success('角色已更新');
      } else {
        await createRole({
          code: values.code,
          name: values.name,
          remark: values.remark,
          menu_ids: values.menu_ids ?? [],
        });
        notify.success('角色已创建');
      }
      setOpen(false);
      load();
    } catch (e) {
      if (e instanceof ApiError) notify.error(e.message);
    }
  };

  const remove = async (id: number) => {
    try {
      await deleteRole(id);
      notify.success('角色已删除');
      load();
    } catch (e) {
      if (e instanceof ApiError) notify.error(e.message);
    }
  };

  return (
    <Card
      size="small"
      title="角色管理"
      extra={
        canWrite && (
          <Button type="primary" onClick={openCreate}>
            新建角色
          </Button>
        )
      }
    >
      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
        message="授权 = 勾菜单"
        description="权限码挂在菜单上，不直接挂角色。勾选哪些菜单，就等于给了哪些权限码——后端返回的 permissions 就是推导结果。"
      />
      <Table<RoleDetail>
        rowKey="id"
        size="small"
        loading={loading}
        dataSource={list}
        pagination={false}
        columns={[
          { title: 'ID', dataIndex: 'id', width: 60 },
          { title: '编码', dataIndex: 'code', width: 140, render: (v: string) => <Tag>{v}</Tag> },
          { title: '名称', dataIndex: 'name', width: 120 },
          { title: '说明', dataIndex: 'remark', width: 160 },
          {
            title: '权限码',
            dataIndex: 'permissions',
            render: (perms: string[]) =>
              perms.length ? (
                perms.map((p) => (
                  <Tag key={p} color="green" style={{ fontSize: 11 }}>
                    {p}
                  </Tag>
                ))
              ) : (
                <Tag color="red">无</Tag>
              ),
          },
          { title: '用户数', dataIndex: 'user_count', width: 80 },
          {
            title: '操作',
            key: 'op',
            width: 140,
            render: (_, role) =>
              canWrite && (
                <Space size={4}>
                  <Button type="link" size="small" onClick={() => openEdit(role)}>
                    编辑
                  </Button>
                  <Popconfirm
                    title="删除角色"
                    description={
                      role.user_count > 0
                        ? `该角色下还有 ${role.user_count} 个用户，删除会被拒绝`
                        : '删除后不可恢复'
                    }
                    onConfirm={() => remove(role.id)}
                    disabled={role.user_count > 0}
                  >
                    <Button type="link" size="small" danger disabled={role.user_count > 0}>
                      删除
                    </Button>
                  </Popconfirm>
                </Space>
              ),
          },
        ]}
      />

      <Modal
        title={editing ? `编辑角色：${editing.name}` : '新建角色'}
        open={open}
        onOk={submit}
        onCancel={() => setOpen(false)}
        okText="保存"
        // forceRender：让 Form 常驻 DOM，否则 Modal 关闭时 Form 被卸载，
        // 而 useForm 的实例还在 —— antd 会警告「Instance created by useForm
        // is not connected to any Form element」。
        forceRender
        destroyOnHidden
      >
        <Form form={form} layout="vertical" preserve={false}>
          {!editing && (
            <Form.Item
              name="code"
              label="编码"
              rules={[
                { required: true, message: '请输入编码' },
                { pattern: /^[a-z][a-z0-9_-]*$/, message: '小写字母开头，只能含小写字母/数字/下划线/短横' },
              ]}
              extra="创建后不可修改——用户身上存的是 code 不是 id"
            >
              <Input placeholder="如 auditor" />
            </Form.Item>
          )}
          <Form.Item name="name" label="名称" rules={[{ required: true, message: '请输入名称' }]}>
            <Input placeholder="如 审计员" />
          </Form.Item>
          <Form.Item name="remark" label="说明">
            <Input.TextArea rows={2} placeholder="这个角色能干什么" />
          </Form.Item>
          <Form.Item name="menu_ids" label="可见菜单（即授权）">
            <Select
              mode="multiple"
              allowClear
              placeholder="勾选这个角色能看到的菜单"
              options={menuOptions}
              optionFilterProp="label"
            />
          </Form.Item>
        </Form>
      </Modal>
    </Card>
  );
}
