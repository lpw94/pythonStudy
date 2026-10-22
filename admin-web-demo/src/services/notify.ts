/**
 * 全局消息提示：antd v5 的正确用法。
 *
 * **问题**：antd v5 里 `message.success()` 这类静态方法拿不到主题 context，
 * 控制台会警告「Static function can not consume context like dynamic theme」。
 * 官方解法是用 `App.useApp()` 拿实例。
 *
 * **难点**：`App.useApp()` 只能在组件里调（它是 hook），
 * 而 `services/request.ts` 里的 401 过期提示是模块级函数，不是组件。
 *
 * **解法**：做一个桥接——在组件里调 `App.useApp()` 把实例存到模块级变量，
 * 模块级代码再通过 `notifyError()` 之类的函数使用它。
 *
 * 对标：umi-request 的 errorHandler 配置，或 axios 拦截器里的全局提示。
 */
import { App } from 'antd';
import type { MessageInstance } from 'antd/es/message/interface';

/** antd message 实例，由 <MessageBridge /> 在运行时注入 */
let instance: MessageInstance | null = null;

/** 组件里调用一次，把实例存下来 */
export function setMessageInstance(msg: MessageInstance): void {
  instance = msg;
}

/** 没注入实例时的降级提示（理论上不会走到——MessageBridge 挂在最外层） */
const fallback = (text: string) => {
  // eslint-disable-next-line no-console
  console.warn('[notify] message 实例未注入：', text);
};

export const notify = {
  success(text: string) {
    if (instance) instance.success(text);
    else fallback(text);
  },
  error(text: string) {
    if (instance) instance.error(text);
    else fallback(text);
  },
  warning(text: string) {
    if (instance) instance.warning(text);
    else fallback(text);
  },
  info(text: string) {
    if (instance) instance.info(text);
    else fallback(text);
  },
};

/**
 * 消息桥接组件：放在 <AntdApp> 内部最外层。
 *
 * 它什么 UI 都不渲染，只负责「把 App.useApp() 拿到的实例存进模块」。
 */
export function MessageBridge(): null {
  const { message } = App.useApp();
  setMessageInstance(message);
  return null;
}
