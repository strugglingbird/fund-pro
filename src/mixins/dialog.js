/**
 * Shared computed property for Element Plus dialogs that use `v-model` with
 * the parent via `:visible` + `@update:visible`.
 *
 * Usage:
 *   import dialogModel from '../mixins/dialog'
 *   export default { mixins: [dialogModel], props: { visible: Boolean }, emits: ['update:visible'] }
 */
export default {
  computed: {
    dialogVisible: {
      get() {
        return this.visible
      },
      set(value) {
        this.$emit('update:visible', value)
      }
    }
  }
}
