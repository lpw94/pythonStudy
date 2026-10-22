import React from 'react';
import ReactDOM from 'react-dom/client';
import { ConfigProvider, App as AntdApp } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import { BrowserRouter } from 'react-router-dom';
import AppRouter from '@/router';
import { AuthProvider } from '@/store/auth';
import { MessageBridge } from '@/services/notify';
import '@/styles/global.css';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ConfigProvider
      locale={zhCN}
      theme={{ token: { colorPrimary: '#2a7e1d', borderRadius: 4 } }}
    >
      {/* antd v5 的 message/notification 等静态方法需要包 <App>，否则拿不到主题 context */}
      <AntdApp>
        {/* MessageBridge 把 App.useApp() 的 message 实例注入到模块级，
            供 request.ts 这类非组件代码使用 */}
        <MessageBridge />
        <BrowserRouter
          // React Router v7 的 future flags：提前开启 v7 行为，避免升级时行为突变。
          // v7_startTransition：状态更新包在 startTransition 里（并发渲染友好）
          // v7_relativeSplatPath：Splat 路由下的相对路径解析改成 v7 规则
          future={{ v7_startTransition: true, v7_relativeSplatPath: true }}
        >
          <AuthProvider>
            <AppRouter />
          </AuthProvider>
        </BrowserRouter>
      </AntdApp>
    </ConfigProvider>
  </React.StrictMode>,
);
