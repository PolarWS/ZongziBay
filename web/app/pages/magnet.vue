<template>
  <div class="px-2 md:px-0">
    <div class="flex items-center justify-between mb-4">
      <h1 class="text-lg font-semibold whitespace-nowrap">创建任务</h1>
    </div>
    <div class="space-y-2">
      <div class="rounded-xl border border-border/50 bg-white dark:bg-card shadow-sm p-6 space-y-6">
        <div class="flex flex-col gap-3">
           <div class="font-semibold text-xl break-words flex items-start gap-3 leading-tight text-foreground">
              <div class="p-2 bg-primary/10 rounded-lg shrink-0">
                <Magnet class="w-5 h-5 text-primary" />
              </div>
              <span class="mt-1">{{ info.name || '未命名资源' }}</span>
           </div>
           <div class="text-xs text-muted-foreground break-all pl-4">
              {{ magnet || '无磁力链接' }}
           </div>
        </div>

        <div class="grid grid-cols-2 md:grid-cols-4 gap-6 pt-2 pl-4">
          <!-- Size -->
          <div class="flex flex-col gap-1.5" v-if="info.size">
            <span class="text-muted-foreground font-medium text-xs flex items-center gap-2">
              <HardDrive class="w-3.5 h-3.5" /> 大小
            </span>
            <span class="font-mono text-sm font-medium">{{ info.size }}</span>
          </div>

          <!-- Num Files -->
          <div class="flex flex-col gap-1.5" v-if="info.num_files">
            <span class="text-muted-foreground font-medium text-xs flex items-center gap-2">
              <Files class="w-3.5 h-3.5" /> 文件数
            </span>
            <span class="font-mono text-sm">{{ info.num_files }}</span>
          </div>

          <!-- Seeders -->
          <div class="flex flex-col gap-1.5" v-if="info.seeders">
            <span class="text-muted-foreground font-medium text-xs flex items-center gap-2">
              <ArrowUpCircle class="w-3.5 h-3.5" /> 做种
            </span>
            <span class="font-mono text-sm font-medium">{{ info.seeders }}</span>
          </div>

          <!-- Leechers -->
          <div class="flex flex-col gap-1.5" v-if="info.leechers">
            <span class="text-muted-foreground font-medium text-xs flex items-center gap-2">
              <ArrowDownCircle class="w-3.5 h-3.5" /> 下载
            </span>
            <span class="font-mono text-sm font-medium">{{ info.leechers }}</span>
          </div>

          <!-- User -->
          <div class="flex flex-col gap-1.5" v-if="info.username">
            <span class="text-muted-foreground font-medium text-xs flex items-center gap-2">
              <User class="w-3.5 h-3.5" /> 用户
            </span>
            <span class="font-mono text-sm truncate" :title="info.username">{{ info.username }}</span>
          </div>

          <!-- Time -->
          <div class="flex flex-col gap-1.5" v-if="info.added">
            <span class="text-muted-foreground font-medium text-xs flex items-center gap-2">
              <Clock class="w-3.5 h-3.5" /> 时间
            </span>
            <span class="font-mono text-sm">{{ info.added }}</span>
          </div>

          <!-- Category -->
          <div class="flex flex-col gap-1.5" v-if="info.category">
            <span class="text-muted-foreground font-medium text-xs flex items-center gap-2">
              <Tag class="w-3.5 h-3.5" /> 分类
            </span>
            <span class="font-mono text-sm">{{ info.category }}</span>
          </div>

          <!-- IMDb -->
          <div class="flex flex-col gap-1.5" v-if="info.imdb">
            <span class="text-muted-foreground font-medium text-xs flex items-center gap-2">
              <Film class="w-3.5 h-3.5" /> IMDb
            </span>
            <span class="font-mono text-sm">{{ info.imdb }}</span>
          </div>
        </div>
      </div>

      <div class="rounded-xl border border-border/50 bg-white dark:bg-card shadow-sm p-6">
        <div class="flex flex-col gap-4">
           <div class="font-semibold text-xl break-words flex items-center gap-3 leading-tight text-foreground">
              <div class="p-2 bg-primary/10 rounded-lg shrink-0">
                <Settings class="w-5 h-5 text-primary" />
              </div>
              <span class="mt-0.5">任务设置</span>
           </div>
          
          <div class="flex items-center gap-6 pl-4">
            <label class="text-sm font-medium text-muted-foreground">类型</label>
            <RadioGroup v-model="selectedType" class="flex items-center gap-6">
              <div class="flex items-center space-x-2">
                <RadioGroupItem id="type-movie" value="movie" />
                <Label for="type-movie" class="cursor-pointer font-normal">电影</Label>
              </div>
              <div class="flex items-center space-x-2">
                <RadioGroupItem id="type-tv" value="tv" />
                <Label for="type-tv" class="cursor-pointer font-normal">剧集</Label>
              </div>
              <div class="flex items-center space-x-2">
                <RadioGroupItem id="type-default" value="default" />
                <Label for="type-default" class="cursor-pointer font-normal">默认</Label>
              </div>
            </RadioGroup>
          </div>
          <div class="grid gap-4 pt-2 pl-4">
             <div class="flex flex-col gap-2">
               <span class="text-xs font-medium text-muted-foreground">下载路径</span>
               <Input v-model="customSourcePath" :placeholder="`默认: ${currentPaths.download}`" class="h-9 text-xs bg-muted/20" />
             </div>
             <div class="flex flex-col gap-2">
               <span class="text-xs font-medium text-muted-foreground">归档路径</span>
               <Input v-model="customTargetPath" :placeholder="`默认: ${currentPaths.target}`" class="h-9 text-xs bg-muted/20" />
             </div>
          </div>
        </div>
      </div>

      <div class="rounded-xl border border-border/50 bg-white dark:bg-card shadow-sm p-6 space-y-4">
        <div class="flex items-center justify-between mb-4">
          <div class="flex items-center gap-3">
             <div class="p-2 bg-primary/10 rounded-lg shrink-0">
               <FolderOpen class="w-5 h-5 text-primary" />
             </div>
             <div class="font-semibold text-xl text-foreground mt-0.5">
               文件列表
             </div>
          </div>
          <div class="flex items-center gap-2">
            <div class="flex items-center bg-muted rounded-lg p-1 mr-2">
               <Button 
                 size="sm" 
                 variant="ghost" 
                 class="h-6 w-7 px-0" 
                 :class="{ 'bg-background shadow-sm': viewMode === 'list' }"
                 @click="viewMode = 'list'"
                 title="列表视图"
               >
                 <List class="w-4 h-4" />
               </Button>
               <Button 
                 size="sm" 
                 variant="ghost" 
                 class="h-6 w-7 px-0" 
                 :class="{ 'bg-background shadow-sm': viewMode === 'tree' }"
                 @click="viewMode = 'tree'"
                 title="树形视图"
               >
                 <FolderTree class="w-4 h-4" />
               </Button>
            </div>

            <Button size="sm" variant="outline" class="h-8 text-xs px-3" @click="smartRename">
              智能重命名
            </Button>
            <Button 
              v-if="canUndo"
              size="sm" 
              variant="secondary" 
              class="h-8 text-xs px-3" 
              @click="undo"
            >
              撤销
            </Button>
            <div class="text-xs text-muted-foreground ml-2">
              共 {{ files.length }} 个文件
            </div>
          </div>
        </div>

        <div class="flex flex-wrap gap-2 mb-3" v-if="files.length > 0">
          <Badge 
            v-for="item in extensions" 
            :key="item.ext"
            :variant="item.allChecked ? 'default' : 'outline'"
            class="cursor-pointer hover:opacity-80 select-none"
            :class="{ 'border-green-500 dark:border-green-400': item.allChecked }"
            @click="toggleExtension(item.ext)"
          >
            {{ item.ext }}
            <span class="ml-1 text-[10px] opacity-70">{{ item.checked }}/{{ item.count }}</span>
          </Badge>

          <div v-if="extensions.length > 0 && detectedKeywords.length > 0" class="w-px h-4 bg-border mx-1 self-center"></div>

          <Badge 
            v-for="item in detectedKeywords" 
            :key="item.keyword"
            :variant="item.allChecked ? 'default' : (item.someChecked ? 'secondary' : 'outline')"
            class="cursor-pointer hover:opacity-80 select-none transition-colors duration-200"
            :class="{ 'border-green-500 dark:border-green-400': item.allChecked }"
            @click="toggleKeyword(item.keyword)"
          >
            {{ item.keyword }}
            <span class="ml-1 text-[10px] opacity-70">{{ item.checked }}/{{ item.count }}</span>
            <span 
              v-if="item.isCustom" 
              @click.stop="removeCustomKeyword(item.keyword)" 
              class="ml-1.5 opacity-50 hover:opacity-100 hover:bg-destructive/10 rounded-full w-4 h-4 inline-flex items-center justify-center text-xs"
            >
              ✕
            </span>
          </Badge>

          <div class="flex items-center gap-1 ml-1">
             <Input
               v-model="newKeyword"
               type="text"
               class="h-8 w-24 rounded-md border border-input bg-background px-2 text-xs focus:outline-none focus:ring-1 focus:ring-ring"
               placeholder="自定义标签"
               @keydown.enter="addCustomKeyword"
             />
             <Button
               size="sm"
               variant="ghost"
               class="h-8 w-8 p-0"
               @click="addCustomKeyword"
               :disabled="!newKeyword.trim()"
             >
               <span class="text-lg leading-none mb-0.5">+</span>
             </Button>
          </div>
        </div>

        <div class="relative mb-4 min-h-[200px]">
          <AppLoadingOverlay v-if="loading" />
          <div :class="{ 'opacity-50': loading }">
            <template v-if="files.length > 0">
              <div v-if="viewMode === 'list'" class="rounded-md border border-border max-h-[420px] overflow-auto">
                <ul class="divide-y divide-border">
                  <li
                    v-for="(file, index) in files"
                    :key="file.path"
                    class="p-3 text-xs flex items-center gap-3 sm:gap-4"
                  >
                    <div class="shrink-0 mt-0.5">
                      <Checkbox
                        v-model="file.checked"
                        :id="`file-${index}`"
                      />
                    </div>
                    <div class="flex-1 min-w-0 space-y-1">
                      <Input
                        v-model="file.newName"
                        type="text"
                        class="block w-full h-8 rounded-md border border-input bg-background px-2.5 py-1.5 text-xs"
                      />
                      <div class="text-muted-foreground truncate">
                        {{ file.path }}
                      </div>
                    </div>
                    <div class="shrink-0 text-muted-foreground text-right font-mono tabular-nums w-24">
                      {{ formatFileSize(file.size) }}
                    </div>
                  </li>
                </ul>
              </div>
              <FileTreeView v-else :files="files" />
            </template>
            <AppEmpty
              v-else-if="!loading"
              :title="errMsg ? '解析失败' : '暂无文件'"
              :description="errMsg || '暂未获取到文件列表'"
            />
          </div>
        </div>

        <div class="flex justify-center gap-4 pt-2" v-if="!loading && files.length > 0">
          <Button variant="outline" size="sm" @click="onCancel">
            取消
          </Button>
          <Button size="sm" @click="onConfirm">
            确认
          </Button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { parseMagnetApiV1MagnetParsePost } from '@/api/magnet'
import { addTaskApiV1TasksAddPost } from '@/api/tasks'
import { getPathConfigApiV1SystemPathsGet as getSystemPaths } from '@/api/system'
import AppLoadingOverlay from '@/components/AppLoadingOverlay.vue'
import AppEmpty from '@/components/AppEmpty.vue'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import { 
  ArrowUpCircle, 
  ArrowDownCircle, 
  HardDrive, 
  Files, 
  User, 
  Clock, 
  Tag, 
  Film, 
  Magnet,
  Settings,
  FolderOpen,
  List,
  FolderTree
} from 'lucide-vue-next'

import { performSmartRename, getExt } from '@/lib/renamer'
import FileTreeView from '@/components/FileTreeView.vue'

const route = useRoute()
const router = useRouter()

// ref / reactive 声明
const selectedType = ref('movie')
const customSourcePath = ref('')
const customTargetPath = ref('')
const viewMode = ref<'list' | 'tree'>('list')
const loading = ref(false)
const errMsg = ref<string | null>(null)
const files = ref<(API.MagnetFile & { newName: string; checked: boolean })[]>([])
const systemPaths = ref<any>({})
const history = ref<string[]>([])
const customKeywords = ref<string[]>([])
const newKeyword = ref('')

// 默认勾选的视频扩展名，字幕按单独逻辑处理
const defaultCheckedExts = [
  '.mp4',
  '.mkv',
  '.webm',
  '.mov',
  '.flv',
  '.m4v',
  '.avi',
]

// 常见关键词（用于批量勾选/取消）
const commonKeywords = [
  'Chinese', '中文', 'CHS', 'CHT', 'English', 'Korean', 'Japanese', 
  '1080p', '2160p', '4K', 'HDR', 'HEVC', 'x265', 'x264'
]

// computed
const magnet = computed(() => (route.query.magnet as string) || '')
const tmdbName = computed(() => (route.query.tmdbName as string) || '')
const category = computed(() => (route.query.category as string) || '')
const defaultType = computed(() => {
  // 205 = 剧集, 208 = 高清剧集
  if (['205', '208'].includes(category.value)) {
    return 'tv'
  }
  return 'movie'
})
const info = computed(() => ({
    name: (route.query.name as string) || '',
    size: (route.query.size as string) || '',
    seeders: (route.query.seeders as string) || '',
    leechers: (route.query.leechers as string) || '',
    num_files: (route.query.num_files as string) || '',
    username: (route.query.username as string) || '',
    added: (route.query.added as string) || '',
    category: category.value,
    imdb: (route.query.imdb as string) || '',
  }))
const currentPaths = computed(() => {
    const type = selectedType.value
    if (type === 'tv') {
        return {
            download: systemPaths.value.tv_download_path || systemPaths.value.default_download_path,
            target: systemPaths.value.tv_target_path || systemPaths.value.default_target_path
        }
    } else if (type === 'movie') {
        return {
            download: systemPaths.value.movie_download_path || systemPaths.value.default_download_path,
            target: systemPaths.value.movie_target_path || systemPaths.value.default_target_path
        }
    }
    return {
        download: systemPaths.value.default_download_path,
        target: systemPaths.value.default_target_path
    }
})
const canUndo = computed(() => history.value.length > 0)
const extensions = computed(() => {
  const extMap = new Map<string, { count: number; checked: number }>()
  
  files.value.forEach(f => {
    const ext = getExt(f.name || f.path || '')
    if (!ext) return
    
    const existing = extMap.get(ext) || { count: 0, checked: 0 }
    existing.count++
    if (f.checked) existing.checked++
    extMap.set(ext, existing)
  })

  return Array.from(extMap.entries()).map(([ext, stats]) => ({
    ext,
    ...stats,
    allChecked: stats.checked === stats.count,
    someChecked: stats.checked > 0 && stats.checked < stats.count
  })).sort((a, b) => b.count - a.count)
})
const detectedKeywords = computed(() => {
  const allKeywords = [...new Set([...commonKeywords, ...customKeywords.value])]

  const result = allKeywords.map(k => ({
    keyword: k,
    isCustom: customKeywords.value.includes(k),
    count: 0,
    checked: 0
  }))

  files.value.forEach(f => {
    const name = f.name || f.path || ''
    result.forEach(item => {
      if (name.toLowerCase().includes(item.keyword.toLowerCase())) {
        item.count++
        if (f.checked) item.checked++
      }
    })
  })

  // 仅展示有匹配或用户自定义添加的关键词
  return result.filter(item => item.count > 0 || item.isCustom).map(item => ({
    ...item,
    allChecked: item.checked === item.count && item.count > 0,
    someChecked: item.checked > 0 && item.checked < item.count
  }))
})

// watch
watch(defaultType, (v) => {
  selectedType.value = v
}, { immediate: true })

// 生命周期
onMounted(() => {
  fetchFiles()
  fetchPaths()
})

// 格式化文件大小
const formatFileSize = (size: number) => {
  if (!Number.isFinite(size) || size <= 0) return '—'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let i = 0
  let v = size
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024
    i++
  }
  return `${v.toFixed(2)} ${units[i]}`
}

// 解析磁链获取文件列表
const fetchFiles = async () => {
  const link = magnet.value.trim()
  if (!link) return
  loading.value = true
  errMsg.value = null
  history.value = []
  try {
    const res = await parseMagnetApiV1MagnetParsePost({ magnet_link: link })
    const code = (res as any)?.code ?? 0
    const msg = (res as any)?.message ?? ''
    const data = (res as any)?.data ?? null
    const ok = code === 0 || code === 200
    if (!ok) {
      errMsg.value = msg || '解析失败'
      files.value = []
    } else {
      errMsg.value = null
      const list = Array.isArray((data as any)?.files) ? (data as any).files : []
      
      files.value = list.map((it: API.MagnetFile) => {
        const ext = getExt(it.name || it.path || '')
        const name = it.name || it.path || ''
        
        let checked = defaultCheckedExts.includes(ext)
        
        // 字幕选择逻辑：默认仅勾选中文
        const subExts = ['.srt', '.ass', '.ssa', '.vtt', '.sub', '.idx']
        if (subExts.includes(ext)) {
            if (name.includes('Chinese') || name.includes('中文') || name.includes('CHS') || name.includes('CHT')) {
                checked = true
            } else {
                checked = false
            }
        }
        
        return {
          ...it,
          newName: tmdbName.value ? `${tmdbName.value}/${it.name}` : it.name,
          checked,
        }
      })
    }
  } finally {
    loading.value = false
  }
}

// 获取系统路径配置
const fetchPaths = async () => {
  try {
    const res = await getSystemPaths()
    if (res && res.code === 200) {
      systemPaths.value = res.data || {}
    }
  } catch (e) {
    console.error(e)
  }
}

// 撤销：恢复到上一次重命名前的状态
const saveHistory = () => {
  history.value.push(JSON.stringify(files.value))
}

const undo = () => {
  const last = history.value.pop()
  if (last) {
    const restored = JSON.parse(last)
    if (Array.isArray(restored) && restored.length === files.value.length) {
      files.value.forEach((f, i) => {
        f.newName = restored[i].newName
      })
    } else {
      files.value = restored
    }
  }
}

// 按扩展名批量勾选/取消
const toggleExtension = (ext: string) => {
  const target = extensions.value.find(e => e.ext === ext)
  if (!target) return

  const newValue = !target.allChecked
  
  files.value.forEach(f => {
    if (getExt(f.name || f.path || '') === ext) {
      f.checked = newValue
    }
  })
}

// 自定义关键词管理
const addCustomKeyword = () => {
  const val = newKeyword.value.trim()
  if (!val) return
  if (!commonKeywords.includes(val) && !customKeywords.value.includes(val)) {
    customKeywords.value.push(val)
  }
  newKeyword.value = ''
}

const removeCustomKeyword = (keyword: string) => {
  customKeywords.value = customKeywords.value.filter(k => k !== keyword)
}

// 按关键词批量勾选/取消
const toggleKeyword = (keyword: string) => {
  const target = detectedKeywords.value.find(k => k.keyword === keyword)
  if (!target) return
  
  const newValue = !target.allChecked
  files.value.forEach(f => {
    const name = f.name || f.path || ''
    if (name.toLowerCase().includes(keyword.toLowerCase())) {
      f.checked = newValue
    }
  })
}

// 智能重命名
const smartRename = () => {
  saveHistory()
  performSmartRename(files.value, selectedType.value as 'movie' | 'tv', tmdbName.value || info.value.name)
}

// 确认添加任务
const onConfirm = async () => {
  if (loading.value) return
  const link = magnet.value.trim()
  if (!link) return

  loading.value = true
  errMsg.value = null

  try {
    const selectedFiles = files.value.filter(f => f.checked)
    const fileTasks = selectedFiles.map(f => {
      const newName = f.newName || f.name || ''
      const idx1 = newName.lastIndexOf('/')
      const idx2 = newName.lastIndexOf('\\')
      const idx = Math.max(idx1, idx2)
      const targetPath = idx >= 0 ? newName.slice(0, idx) : ''
      const fileRename = idx >= 0 ? newName.slice(idx + 1) : newName
      return {
        sourcePath: f.path || f.name || '',
        targetPath,
        file_rename: fileRename
      }
    })

    const req: API.AddTaskRequest = {
      taskName: info.value.name || '未命名任务',
      sourceUrl: link,
      file_tasks: fileTasks,
      type: selectedType.value,
      sourcePath: customSourcePath.value || undefined,
      targetPath: customTargetPath.value || undefined
    }

    const res = await addTaskApiV1TasksAddPost(req)
    if (res && (res.code === 0 || res.code === 200)) {
      router.push('/')
    } else {
      errMsg.value = res?.message || '添加任务失败'
    }
  } catch (e: any) {
    errMsg.value = e.message || '添加任务发生错误'
  } finally {
    loading.value = false
  }
}

const onCancel = () => {
  router.back()
}
</script>
