import { createApp } from 'vue'
import ElementPlus, { ElMessage, ElMessageBox } from 'element-plus'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import 'element-plus/dist/index.css'
import App from './App.vue'
import './styles/global.css'
// Panels and dialogs share these global layout styles.
import './styles/workspace.css'

const app = createApp(App)

app.use(ElementPlus, { locale: zhCn })

// Element Plus does not attach these to the global properties the way
// Element UI 2 did, but every error/confirm path in App.vue uses the
// classic `this.$message...` / `await this.$confirm(...)` style.
app.config.globalProperties.$message = ElMessage
app.config.globalProperties.$confirm = ElMessageBox.confirm

app.mount('#app')
