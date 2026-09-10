import Vue from 'vue'
import ElementUI from 'element-ui'
import 'element-ui/lib/theme-chalk/index.css'
import App from './App.vue'
import './styles/global.css'
// Shared workspace stylesheet; kept global because the panels and dialogs share layout classes.
import './styles/workspace.css'

Vue.config.productionTip = false
Vue.use(ElementUI)

new Vue({
  render: h => h(App)
}).$mount('#app')
