import { Button, Result } from 'antd';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '@/store/auth';

/** 独立 403 页（在布局之外，全屏展示） */
export default function Forbidden() {
  const navigate = useNavigate();
  const { profile } = useAuth();
  return (
    <Result
      status="403"
      title="403 · 无权限"
      subTitle={`当前账号 ${profile?.username ?? ''} 的角色是 ${profile?.roles.join('/') || '-'}，没有该页面的权限`}
      extra={
        <Button type="primary" onClick={() => navigate('/')}>
          回到首页
        </Button>
      }
    />
  );
}
