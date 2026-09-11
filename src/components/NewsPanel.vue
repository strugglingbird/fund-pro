<template>
  <div>
    <section>
      <div class="page-heading">
        <div><h2>消息快讯</h2><p>聚合多平台财经快讯，优先展示高影响事件。</p></div><div class="panel-actions">
          <span class="panel-tip">{{ newsFeed.total_count || 0 }} 条重要消息 · {{ newsFeed.generated_at || '--' }} 更新</span><el-button
            size="small"
            :loading="loading"
            @click="loadNews(true)"
          >
            刷新快讯
          </el-button>
        </div>
      </div>
      <el-row
        v-if="loading && !newsFeed.groups.length"
        :gutter="18"
        class="news-grid"
        aria-label="正在加载财经快讯"
      >
        <el-col
          v-for="card in 4"
          :key="card"
          :xs="24"
          :lg="12"
        >
          <el-card
            shadow="never"
            class="panel-card news-source-card news-skeleton-card"
          >
            <template #header>
              <div class="panel-header">
                <i class="news-skeleton-source" /><i class="news-skeleton-count" />
              </div>
            </template><div
              v-for="row in 4"
              :key="row"
              class="news-skeleton-item"
            >
              <i class="news-skeleton-title" /><i class="news-skeleton-time" /><i class="news-skeleton-body" /><i class="news-skeleton-body short" />
            </div>
          </el-card>
        </el-col>
      </el-row>
      <el-row
        v-else
        :gutter="18"
        class="news-grid"
      >
        <el-col
          v-for="group in newsFeed.groups"
          :key="group.source"
          :xs="24"
          :lg="12"
        >
          <el-card
            shadow="never"
            class="panel-card news-source-card"
          >
            <template #header>
              <div class="panel-header">
                <span>{{ group.source }}</span><span class="panel-tip">{{ group.items.length }} 条重点快讯</span>
              </div>
            </template><div
              v-for="item in group.items"
              :key="item.id"
              class="news-item"
            >
              <div class="news-head">
                <span class="news-title">{{ item.title }}</span>
              </div><div class="news-meta">
                {{ item.published_at }}
              </div><div class="news-body">
                {{ item.summary }}
              </div><a
                v-if="item.url"
                class="news-link"
                :href="item.url"
                target="_blank"
                rel="noopener noreferrer"
              >查看原文</a>
            </div>
          </el-card>
        </el-col>
      </el-row>
    </section>
  </div>
</template>

<script>
export default {
  name: 'NewsPanel',
  props: {
    newsFeed: { type: Object, required: true },
    loading: Boolean
  },
  emits: ["reload"],
  methods: {
    loadNews(force) {
      this.$emit('reload', force)
    }
  }
}
</script>
