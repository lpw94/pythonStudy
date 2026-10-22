/**
 * 角色管理页：只读展示。
 *
 * 后端目前只提供 GET /api/roles（给用户编辑页的下拉框用），
 * 角色 CRUD 还没做——这里如实展示，不假装有编辑能力。
 */
import { useEffect, useState } from 'react';
import { Alert, Card, Table, Tag, message } from 'antd';
import { fetchRoles } from '@/services/api';
import { ApiError } from '@/services/request';
import type { RoleItem } from '@/types/api';

export default function RoleList() {
  const [list, setList] = useState<RoleItem[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setLoading(true);
    fetchRoles()
      .then(setList)
      .catch((e) => message.error(e instanceof ApiError ? e.message : '加载失败'))
      .finally(() => setLoading(false));
  }, []);

  return (
    <Card size="small" title="角色管理">
      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
        message="后端只实现了角色查询"
        description="角色/菜单的写接口（POST /api/roles 等）还没做，所以这一页是只读的。角色决定用户能看到哪些菜单和权限码。"
      />
      <Table<RoleItem>
        rowKey="id"
        size="small"
        loading={loading}
        dataSource={list}
        pagination={false}
        columns={[
          { title: 'ID', dataIndex: 'id', width: 60 },
          { title: '编码', dataIndex: 'code', width: 140, render: (v: string) => <Tag>{v}</Tag> },
          { title: '名称', dataIndex: 'name' },
          { title: '说明', dataIndex: 'remark' },
        ]}
      />
    </Card>
  );
}
