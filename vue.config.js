const isCapacitorBuild = process.env.VUE_APP_TARGET === 'capacitor'

module.exports = {
  publicPath: isCapacitorBuild ? './' : '/',
  devServer: {
    port: 8080,
    client: {
      overlay: {
        // ResizeObserver loop 是浏览器的无害通知（ECharts/Element UI 在弹窗打开、
        // 尺寸变化时触发），不影响功能。过滤掉它，避免 dev overlay 弹红色报错。
        runtimeErrors: (error) => !/ResizeObserver loop/i.test(error.message)
      }
    },
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:5000',
        changeOrigin: true
      }
    }
  }
}
