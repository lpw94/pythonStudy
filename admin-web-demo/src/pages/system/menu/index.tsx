/**
 * 菜单管理页：全量菜单 / 我的菜单对比 + 菜单的增删改。
 *
 * GET /api/menus  返回全部菜单（需要 menu:read）
 * GET /api/auth/menus 返回当前用户按角色过滤后的菜单
 *
 * 两边放一起对比，能直观看到权限模型在起作用：
 * operator 拿得到「菜单管理」这一项，但看不到「角色管理」——因为他没有该菜单权限。
 *
 * 菜单是**权限的载体**：菜单上挂的权限码，所有关联这个菜单的角色都会拿到。
 * 所以在这里改权限码，等于批量改了多个角色的权限。
 */
import { useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Button,
  Card,
  Form,
  Input,
  InputNumber,
  Modal,
  Popconfirm,
  Select,
  Space,
  Switch,
  Tag,
  Tree,
} from 'antd';
import type { DataNode } from 'antd/es/tree';
import { createMenu, deleteMenu, fetchAllMenus, fetchMyMenus, fetchPermissions, updateMenu } from '@/services/api';
import { ApiError } from '@/services/request';
import { usePermission } from '@/access';
import { useAuth } from '@/store/auth';
import type { MenuItem, PermissionItem } from '@/types/api';
import { notify } from '@/services/notify';

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

/** 菜单树 → 父级下拉选项（顶级为 0） */
function toParentOptions(menus: MenuItem[]): Array<{ label: string; value: number }> {
  return [
    { label: '顶级菜单', value: 0 },
    ...menus.flatMap((m) => [
      { label: m.name, value: m.id },
      ...toParentOptions(m.children),
    ]),
  ];
}

export default function MenuList() {
  const { profile } = useAuth();
  const canWrite = usePermission('menu:write');
  const [all, setAll] = useState<MenuItem[]>([]);
  const [mine, setMine] = useState<MenuItem[]>([]);
  const [permissions, setPermissions] = useState<PermissionItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [editing, setEditing] = useState<MenuItem | null>(null);
  const [open, setOpen] = useState(false);
  const [form] = Form.useForm();

  const parentOptions = useMemo(() => toParentOptions(all), [all]);
  // 权限码从后端拉，不在前端硬编码——后端加了新码，前端自动能选
  const permissionOptions = useMemo(
    () => permissions.map((p) => ({ label: `${p.group} / ${p.code}`, value: p.code })),
    [permissions],
  );

  const load = () => {
    setLoading(true);
    Promise.all([fetchAllMenus(), fetchMyMenus(), fetchPermissions()])
      .then(([a, m, p]) => {
        setAll(a);
        setMine(m);
        setPermissions(p);
      })
      .catch((e) => notify.error(e instanceof ApiError ? e.message : '加载失败'))
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  const openCreate = () => {
    setEditing(null);
    form.resetFields();
    form.setFieldsValue({
      name: '',
      path: '',
      component: '',
      route_name: '',
      icon: '',
      sort: 0,
      visible: true,
      parent_id: 0,
      permission_codes: [],
    });
    setOpen(true);
  };

  const openEdit = (menu: MenuItem) => {
    setEditing(menu);
    form.setFieldsValue({
      name: menu.name,
      path: menu.path,
      component: menu.component,
      route_name: menu.route_name,
      icon: menu.icon,
      sort: menu.sort,
      visible: menu.visible,
      parent_id: menu.parent_id,
      permission_codes: menu.permissions,
    });
    setOpen(true);
  };

  const submit = async () => {
    const values = await form.validateFields();
    try {
      if (editing) {
        // route_name 不给后端：路由名是前端 addRoute 的标识，改了会破坏已有路由
        await updateMenu(editing.id, {
          name: values.name,
          path: values.path,
          component: values.component,
          icon: values.icon,
          sort: values.sort,
          visible: values.visible,
          parent_id: values.parent_id,
          permission_codes: values.permission_codes ?? [],
        });
        notify.success('菜单已更新');
      } else {
        await createMenu({
          name: values.name,
          path: values.path,
          component: values.component,
          route_name: values.route_name,
          icon: values.icon,
          sort: values.sort,
          visible: values.visible,
          parent_id: values.parent_id,
          permission_codes: values.permission_codes ?? [],
        });
        notify.success('菜单已创建');
      }
      setOpen(false);
      load();
    } catch (e) {
      if (e instanceof ApiError) notify.error(e.message);
    }
  };

  const remove = async (id: number) => {
    try {
      await deleteMenu(id);
      notify.success('菜单已删除');
      load();
    } catch (e) {
      if (e instanceof ApiError) notify.error(e.message);
    }
  };

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <Card
        size="small"
        title="全量菜单（GET /api/menus · 需要 menu:read）"
        loading={loading}
        extra={
          canWrite && (
            <Button type="primary" onClick={openCreate}>
              新建菜单
            </Button>
          )
        }
      >
        <Alert
          type="warning"
          showIcon
          style={{ marginBottom: 12 }}
          message="菜单上的权限码 = 关联角色的权限"
          description="在这里改权限码，所有关联这个菜单的角色都会同步变——这是全局操作，不是只影响一个人。"
        />
        <Tree treeData={toTreeData(all)} defaultExpandAll selectable={false} />
        {canWrite && (
          <Space style={{ marginTop: 12 }} wrap>
            {all.map((m) => (
              <Space key={m.id} size={4}>
                <Button size="small" onClick={() => openEdit(m)}>
                  编辑「{m.name}」
                </Button>
                <Popconfirm title="删除菜单" onConfirm={() => remove(m.id)}>
                  <Button size="small" danger>
                    删除
                  </Button>
                </Popconfirm>
              </Space>
            ))}
          </Space>
        )}
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

      <Modal
        title={editing ? `编辑菜单：${editing.name}` : '新建菜单'}
        open={open}
        onOk={submit}
        onCancel={() => setOpen(false)}
        okText="保存"
        width={560}
        // forceRender：让 Form 常驻 DOM，否则 Modal 关闭时 Form 被卸载，
        // 而 useForm 的实例还在 —— antd 会警告「Instance created by useForm
        // is not connected to any Form element」。
        forceRender
        destroyOnHidden
      >
        <Form form={form} layout="vertical" preserve={false}>
          <Form.Item name="name" label="名称" rules={[{ required: true, message: '请输入名称' }]}>
            <Input placeholder="如 用户管理" />
          </Form.Item>
          <Form.Item name="path" label="路由路径" rules={[{ required: true, message: '请输入路径' }]}>
            <Input placeholder="如 /system/user" />
          </Form.Item>
          {!editing && (
            <Form.Item
              name="route_name"
              label="路由名"
              rules={[{ required: true, message: '请输入路由名' }]}
              extra="全局唯一，前端 addRoute 靠它做标识——创建后不可修改"
            >
              <Input placeholder="如 system-user" />
            </Form.Item>
          )}
          <Form.Item name="component" label="组件标识" extra="对应前端 dynamic import 的键">
            <Input placeholder="如 system/user" />
          </Form.Item>
          <Form.Item name="parent_id" label="父菜单">
            <Select options={parentOptions} />
          </Form.Item>
          <Space size={16}>
            <Form.Item name="sort" label="排序">
              <InputNumber min={0} />
            </Form.Item>
            <Form.Item name="icon" label="图标">
              <Input placeholder="如 user" style={{ width: 160 }} />
            </Form.Item>
            <Form.Item name="visible" label="显示在导航" valuePropName="checked">
              <Switch />
            </Form.Item>
          </Space>
          <Form.Item
            name="permission_codes"
            label="权限码"
            extra="这个菜单带的权限。关联了这个菜单的角色都会拿到这些码。"
          >
            <Select
              mode="multiple"
              allowClear
              placeholder="选择权限码"
              options={permissionOptions}
            />
          </Form.Item>
        </Form>
      </Modal>
    </Space>
  );
}
