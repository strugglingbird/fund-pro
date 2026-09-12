import { Capacitor } from '@capacitor/core'

/**
 * 注册 Android 物理返回键。
 *
 * 背景：Capacitor 的 BridgeActivity 没有覆写 onBackPressed，项目又是纯 activeMenu
 * 状态切换、没有路由，所以不注册监听时按返回键会直接退出 App。
 *
 * @param {() => boolean} handler 返回 true 表示已消费本次返回（例如关闭弹窗/回到首页）
 * @returns {Promise<() => void>} 取消监听的函数；非原生端返回空实现
 */
export async function registerBackButton(handler) {
  if (typeof handler !== 'function' || !Capacitor.isNativePlatform()) return () => {}

  try {
    const { App: NativeApp } = await import('@capacitor/app')
    const listener = await NativeApp.addListener('backButton', () => {
      if (handler()) return
      void NativeApp.exitApp()
    })
    return () => {
      listener.remove()
    }
  } catch {
    return () => {}
  }
}
