<script setup lang="ts">
import Search from '@/components/Search.vue'
import { Button } from '@/components/ui/button'
import { Activity, ExternalLink } from 'lucide-vue-next'

// 首页搜索类型：电影 / 剧集，用于搜索框与跳转
const type = ref<'movie' | 'tv'>('tv')
const onChangeType = (v: 'movie' | 'tv') => {
  type.value = v
}
</script>

<template>
    <div class="flex flex-col items-center justify-center pt-10 pb-24 md:pt-20 md:pb-20 relative z-30">
        <!-- 首屏主视觉 -->
        <div class="text-center max-w-4xl mx-auto space-y-4 md:space-y-6 px-4">
            <h1 class="text-4xl md:text-7xl font-bold tracking-tight text-foreground">
                <span class="text-primary">粽子湾</span>
                <span class="block md:inline mt-1 md:mt-0">资源助手</span>
            </h1>
            <p class="text-sm md:text-xl text-muted-foreground max-w-2xl mx-auto mt-2 md:mt-4 leading-relaxed">
                聚合全网磁链搜索，支持 qBittorrent 一键推送与自动重命名，<br class="hidden md:block" />
                为您打造极致流畅的观影体验。
            </p>
            
            <div class="flex flex-col items-center gap-5 md:gap-8 mt-6 md:mt-12 w-full">
                <!-- 类型切换：电影 / 剧集 -->
                <div class="flex flex-wrap gap-3 md:gap-4">
                    <Button 
                        size="lg" 
                        :variant="type === 'movie' ? 'default' : 'outline'"
                        @click="onChangeType('movie')"
                        class="min-w-[100px] md:min-w-[120px] text-base md:text-lg h-10 md:h-12 transition-all duration-300"
                        :class="type === 'movie' ? 'hover:brightness-110 hover:shadow-lg hover:scale-105' : 'hover:bg-primary/20 hover:text-primary hover:border-primary hover:shadow-md hover:scale-105'"
                    >
                        电影
                    </Button>
                    <Button 
                        size="lg" 
                        :variant="type === 'tv' ? 'default' : 'outline'"
                        @click="onChangeType('tv')"
                        class="min-w-[100px] md:min-w-[120px] text-base md:text-lg h-10 md:h-12 transition-all duration-300"
                        :class="type === 'tv' ? 'hover:brightness-110 hover:shadow-lg hover:scale-105' : 'hover:bg-primary/20 hover:text-primary hover:border-primary hover:shadow-md hover:scale-105'"
                    >
                        剧集
                    </Button>
                </div>

                <!-- 搜索框 -->
                <div class="w-full max-w-xl">
                    <Search :type="type" />
                </div>
            </div>
        </div>
    </div>

    <div class="border-t border-border bg-card pt-12 pb-20 relative z-20 shadow-sm overflow-hidden">
        <div class="max-w-7xl mx-auto px-4 md:px-10">
            <div class="grid grid-cols-1 lg:grid-cols-[280px_minmax(0,1fr)] gap-8 lg:gap-12 items-start">
                 <!-- 左侧边栏 -->
                 <div class="space-y-4 lg:sticky lg:top-24">
                     <div class="flex items-center gap-3">
                         <div class="h-10 w-10 rounded-lg bg-primary/10 flex items-center justify-center text-primary">
                             <Activity class="w-6 h-6" />
                         </div>
                         <h2 class="text-2xl font-bold tracking-tight">热门任务</h2>
                     </div>
                     <p class="text-muted-foreground leading-relaxed">
                         监控并管理您的活跃下载任务。实时获取状态更新及媒体代理的资源分配情况。
                     </p>
                     <div class="pt-4 border-t border-border/40">
                        <div class="text-xs font-mono text-muted-foreground mb-2 uppercase tracking-wider">GitHub 项目地址</div>
                        <a href="https://github.com/PolarWS" target="_blank" class="text-sm font-medium hover:underline flex items-center gap-1 text-primary">
                            github.com/ZongziBay <ExternalLink class="w-3 h-3" />
                        </a>
                     </div>
                 </div>
                 
                 <!-- 右侧内容：min-w-0 让 grid 子项可收缩，避免表格撑出横向滚动 -->
                 <div class="w-full min-w-0">
                     <TaskList />
                 </div>
            </div>
        </div>
    </div>
</template>
