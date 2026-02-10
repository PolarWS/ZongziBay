<script setup lang="ts">
import { listTasksApiV1TasksListGet, cancelTaskApiV1TasksCancelTaskIdPost } from '@/api/tasks'
import AppPagination from '@/components/AppPagination.vue'
import { Loader2, Ban, MoreHorizontal, Download, FolderOpen, Play, CheckCircle2, XCircle, Clock, Activity, FileText, ChevronDown, AlertCircle, ArrowRight } from 'lucide-vue-next'
import { formatFileTaskStatus } from '@/lib/status'
import { toast } from 'vue-sonner'
import { Button } from '@/components/ui/button'
import { onClickOutside } from '@vueuse/core'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import AppEmpty from '@/components/AppEmpty.vue'
import { formatTaskStatus } from '@/lib/status'

const tasks = ref<API.DownloadTask[]>([])
const total = ref(0)
const loading = ref(false)
const page = ref(1)
const pageSize = ref(10)
const ROW_HEIGHT = 60
const HEADER_HEIGHT = 41
const listHeight = computed(() => `${10 * ROW_HEIGHT + HEADER_HEIGHT}px`)
let timer: number | undefined
const open = ref(false)
const cancelDialogOpen = ref(false)
const fileTaskDialogOpen = ref(false)
const selected = ref<API.DownloadTask | null>(null)
const selectedFileTask = ref<API.FileTask | null>(null)
const taskToCancel = ref<API.DownloadTask | null>(null)

const isPageSizeOpen = ref(false)
const pageSizeRef = ref<HTMLElement | null>(null)

onClickOutside(pageSizeRef, () => {
  isPageSizeOpen.value = false
})

const setPageSize = (size: number) => {
  pageSize.value = size
  isPageSizeOpen.value = false
}

const loadTasks = async (opts?: { silent?: boolean }) => {
  const silent = !!opts?.silent
  try {
    if (!silent) loading.value = true
    const res = await listTasksApiV1TasksListGet(
      { page: page.value, page_size: pageSize.value },
      silent ? { skipErrorHandler: true } : {}
    )
    const nextItems = res?.data?.items ?? []
    const nextTotal = res?.data?.total ?? 0

    const same =
      tasks.value.length === nextItems.length &&
      tasks.value.every((t, i) => t.id === nextItems[i]?.id && t.updateTime === nextItems[i]?.updateTime)

    if (!same) {
      const oldById = new Map<number, API.DownloadTask>(tasks.value.map(t => [t.id, t]))
      const merged: API.DownloadTask[] = []
      for (const it of nextItems) {
        const old = oldById.get(it.id)
        if (
          old &&
          old.updateTime === it.updateTime &&
          old.taskStatus === it.taskStatus &&
          old.targetPath === it.targetPath &&
          old.sourceUrl === it.sourceUrl &&
          old.sourcePath === it.sourcePath &&
          old.taskName === it.taskName &&
          old.taskInfo === it.taskInfo
        ) {
          merged.push(old)
        } else {
          merged.push(it)
        }
      }
      tasks.value.splice(0, tasks.value.length, ...merged)
    }
    total.value = nextTotal
  } finally {
    if (!silent) loading.value = false
  }
}
const onOpenDetails = (item: API.DownloadTask) => {
  selected.value = item
  open.value = true
}
watch(() => page.value, () => {
  loadTasks()
})
watch(() => pageSize.value, () => {
  page.value = 1
  loadTasks()
})
onMounted(() => {
  loadTasks()
  timer = window.setInterval(() => loadTasks({ silent: true }), 5000)
})
onUnmounted(() => {
  if (timer) clearInterval(timer)
})

const onCancel = async (task: API.DownloadTask) => {
  taskToCancel.value = task
  cancelDialogOpen.value = true
}

const confirmCancel = async () => {
  if (!taskToCancel.value) return
  
  try {
    await cancelTaskApiV1TasksCancelTaskIdPost(taskToCancel.value.id)
    toast.success('任务已取消')
    loadTasks()
    if (selected.value?.id === taskToCancel.value.id) {
      open.value = false
    }
  } catch (e: any) {
    toast.error(e.message || '取消失败')
  } finally {
    cancelDialogOpen.value = false
    taskToCancel.value = null
  }
}
const onOpenFileTaskDetails = (ft: API.FileTask) => {
  selectedFileTask.value = ft
  fileTaskDialogOpen.value = true
}
</script>
<template>
  <div class="w-full">
    <!-- Header Controls -->
    <div class="flex items-center justify-between mb-4 px-1">
       <div class="relative w-full max-w-sm">
         <!-- Placeholder for local search if needed -->
       </div>
       <div class="flex items-center gap-3">
        <span class="text-xs font-medium text-muted-foreground uppercase tracking-wider whitespace-nowrap">每页行数</span>
        <div class="relative" ref="pageSizeRef">
          <button
            type="button"
            class="flex h-8 w-16 items-center justify-between rounded-md border border-input bg-background px-2 py-1 text-xs font-medium shadow-sm transition-colors hover:bg-accent hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50 cursor-pointer"
            @click="isPageSizeOpen = !isPageSizeOpen"
          >
            {{ pageSize }}
            <ChevronDown class="h-3 w-3 opacity-50" />
          </button>
          
          <div v-if="isPageSizeOpen" class="absolute right-0 top-full mt-1 w-20 rounded-md border border-border bg-popover text-popover-foreground shadow-md z-50 animate-in fade-in-0 zoom-in-95">
             <div class="p-1">
                <div 
                  v-for="size in [10, 20, 50]" 
                  :key="size"
                  class="relative flex cursor-default select-none items-center rounded-sm px-2 py-1.5 text-xs outline-none hover:bg-accent hover:text-accent-foreground data-[disabled]:pointer-events-none data-[disabled]:opacity-50 cursor-pointer"
                  :class="{ 'bg-accent text-accent-foreground': pageSize === size }"
                  @click="setPageSize(size)"
                >
                  {{ size }}
                </div>
             </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Table Container -->
    <div class="rounded-xl border border-border overflow-hidden relative z-10">
      <div class="w-full overflow-auto">
        <table class="w-full caption-bottom text-sm">
          <thead class="[&_tr]:border-b">
            <tr class="border-b transition-colors hover:bg-muted/50 data-[state=selected]:bg-muted">
              <th class="h-12 px-4 text-left align-middle font-medium text-muted-foreground [&:has([role=checkbox])]:pr-0 w-[30%] min-w-[200px]">任务名称</th>
              <th class="h-12 px-4 text-left align-middle font-medium text-muted-foreground [&:has([role=checkbox])]:pr-0 min-w-[150px]">来源</th>
              <th class="h-12 px-4 text-left align-middle font-medium text-muted-foreground [&:has([role=checkbox])]:pr-0 min-w-[100px]">目标路径</th>
              <th class="h-12 px-4 text-left align-middle font-medium text-muted-foreground [&:has([role=checkbox])]:pr-0 w-[100px] min-w-[100px]">状态</th>
              <th class="h-12 px-4 text-right align-middle font-medium text-muted-foreground [&:has([role=checkbox])]:pr-0 w-[80px] min-w-[80px]">操作</th>
            </tr>
          </thead>
          <tbody class="[&_tr:last-child]:border-0">
            <tr v-if="loading && tasks.length === 0">
               <td colspan="5" class="h-24 text-center">
                  <div class="flex justify-center items-center">
                    <Loader2 class="w-6 h-6 animate-spin text-muted-foreground" />
                  </div>
               </td>
            </tr>
            <tr v-else-if="tasks.length === 0">
              <td colspan="5" class="h-24 text-center">
                <div class="flex flex-col items-center justify-center text-muted-foreground gap-2">
                   <div class="p-2 rounded-full bg-muted/50">
                     <Download class="w-5 h-5 opacity-50" />
                   </div>
                   <span>暂无任务</span>
                </div>
              </td>
            </tr>
            <tr 
              v-for="item in tasks" 
              :key="item.id"
              class="border-b transition-colors hover:bg-muted/30 data-[state=selected]:bg-muted cursor-pointer group"
              @click="onOpenDetails(item)"
            >
              <td class="p-4 align-middle [&:has([role=checkbox])]:pr-0 font-medium text-foreground">
                {{ item.taskName }}
              </td>
              <td class="p-4 align-middle [&:has([role=checkbox])]:pr-0 text-muted-foreground font-mono text-xs">
                <div class="max-w-[200px] truncate" :title="item.sourceUrl || item.sourcePath">
                  {{ item.sourceUrl || item.sourcePath }}
                </div>
              </td>
              <td class="p-4 align-middle [&:has([role=checkbox])]:pr-0 text-muted-foreground font-mono text-xs">
                <div class="max-w-[150px] truncate" :title="item.targetPath">
                  {{ item.targetPath }}
                </div>
              </td>
              <td class="p-4 align-middle [&:has([role=checkbox])]:pr-0">
                 <div class="flex items-center gap-2">
                    <span class="relative flex h-2 w-2">
                      <span v-if="['downloading', 'moving'].includes(item.taskStatus || '')" class="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-500 opacity-75"></span>
                      <span class="relative inline-flex rounded-full h-2 w-2" 
                        :class="{
                          'bg-blue-500': ['downloading', 'moving'].includes(item.taskStatus || ''),
                          'bg-green-500': item.taskStatus === 'completed',
                          'bg-red-500': ['cancelled', 'error'].includes(item.taskStatus || ''),
                          'bg-yellow-500': item.taskStatus === 'pending'
                        }"
                      ></span>
                    </span>
                    <span class="text-xs font-medium capitalize">{{ formatTaskStatus(item.taskStatus) }}</span>
                 </div>
              </td>
              <td class="p-4 align-middle [&:has([role=checkbox])]:pr-0 text-right">
                <div class="flex items-center justify-end h-8">
                  <Button 
                     v-if="['downloading', 'pending'].includes(item.taskStatus || '')"
                     variant="ghost" 
                     size="sm" 
                     class="h-8 text-xs font-medium text-muted-foreground hover:text-destructive hover:bg-destructive/10 px-2"
                     @click.stop="onCancel(item)"
                  >
                    取消
                  </Button>
                  <span v-else class="text-xs text-muted-foreground/50 select-none px-2">完成</span>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      
      <!-- Loading Overlay for Refresh -->
      <div v-if="loading && tasks.length > 0" class="absolute top-2 right-2 z-20">
          <Loader2 class="w-3 h-3 animate-spin text-muted-foreground" />
      </div>
    </div>
    
    <AppPagination
      v-model:page="page"
      :items-per-page="pageSize"
      :total="total"
      class="mt-4"
    />

    <Dialog v-model:open="open">
      <DialogContent class="max-w-2xl max-h-[85vh] overflow-y-auto w-[90vw] sm:w-full rounded-xl">
        <DialogHeader>
          <DialogTitle class="text-lg font-semibold tracking-tight">{{ selected?.taskName || '任务详情' }}</DialogTitle>
          <DialogDescription>
            任务 ID: {{ selected?.id }}
          </DialogDescription>
        </DialogHeader>
        <div class="mt-4 grid gap-4 text-sm">
           <div class="grid grid-cols-1 sm:grid-cols-[100px_1fr] items-start gap-2 sm:gap-4 p-4 rounded-lg bg-muted/30 border border-border/50">
             <div class="contents sm:hidden">
               <!-- Mobile Layout -->
               <div class="col-span-1 flex flex-col gap-4">
                  <div class="flex flex-col gap-1">
                     <span class="text-muted-foreground font-medium text-xs flex items-center gap-2">
                       <Clock class="w-3 h-3" /> 任务ID
                     </span>
                     <span class="font-mono text-sm pl-5">{{ selected?.id }}</span>
                  </div>

                  <div class="flex flex-col gap-1">
                     <span class="text-muted-foreground font-medium text-xs flex items-center gap-2">
                       <Activity class="w-3 h-3" /> 状态
                     </span>
                     <span class="font-mono text-sm pl-5 flex items-center gap-2">
                        <span class="relative flex h-2.5 w-2.5">
                          <span v-if="['downloading', 'moving'].includes(selected?.taskStatus || '')" class="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-500 opacity-75"></span>
                          <span class="relative inline-flex rounded-full h-2.5 w-2.5" 
                            :class="{
                              'bg-blue-500': ['downloading', 'moving'].includes(selected?.taskStatus || ''),
                              'bg-green-500': selected?.taskStatus === 'completed',
                              'bg-red-500': ['cancelled', 'error'].includes(selected?.taskStatus || ''),
                              'bg-yellow-500': selected?.taskStatus === 'pending'
                            }"
                          ></span>
                        </span>
                        {{ formatTaskStatus(selected?.taskStatus) }}
                     </span>
                  </div>

                  <div class="flex flex-col gap-1">
                     <span class="text-muted-foreground font-medium text-xs flex items-center gap-2">
                       <Clock class="w-3 h-3" /> 更新时间
                     </span>
                     <span class="font-mono text-sm pl-5">{{ selected?.updateTime }}</span>
                  </div>
                  
                  <div class="flex flex-col gap-1">
                     <span class="text-muted-foreground font-medium text-xs flex items-center gap-2">
                       <FolderOpen class="w-3 h-3" /> 目标路径
                     </span>
                     <span class="font-mono text-sm pl-5 break-all">{{ selected?.targetPath }}</span>
                  </div>

                  <div class="flex flex-col gap-1">
                     <span class="text-muted-foreground font-medium text-xs flex items-center gap-2">
                       <Download class="w-3 h-3" /> 来源
                     </span>
                     <span class="font-mono text-xs pl-5 break-all text-muted-foreground">{{ selected?.sourceUrl || selected?.sourcePath }}</span>
                  </div>
               </div>
             </div>

             <!-- Desktop Layout -->
             <div class="hidden sm:contents">
               <span class="text-muted-foreground font-medium flex items-center gap-2">
                 <Clock class="w-4 h-4" /> 任务ID
               </span>
               <span class="font-mono">{{ selected?.id }}</span>

               <span class="text-muted-foreground font-medium flex items-center gap-2">
                 <Clock class="w-4 h-4" /> 更新时间
               </span>
               <span class="font-mono">{{ selected?.updateTime }}</span>
               
               <span class="text-muted-foreground font-medium flex items-center gap-2">
                 <FolderOpen class="w-4 h-4" /> 目标路径
               </span>
               <span class="font-mono break-all">{{ selected?.targetPath }}</span>
               
               <span class="text-muted-foreground font-medium flex items-center gap-2">
                 <Download class="w-4 h-4" /> 来源
               </span>
               <span class="font-mono break-all text-xs">{{ selected?.sourceUrl || selected?.sourcePath }}</span>

               <span class="text-muted-foreground font-medium flex items-center gap-2">
                 <Activity class="w-4 h-4" /> 状态
               </span>
               <span class="font-mono flex items-center gap-2">
                  <span class="relative flex h-2.5 w-2.5">
                    <span v-if="['downloading', 'moving'].includes(selected?.taskStatus || '')" class="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-500 opacity-75"></span>
                    <span class="relative inline-flex rounded-full h-2.5 w-2.5" 
                      :class="{
                        'bg-blue-500': ['downloading', 'moving'].includes(selected?.taskStatus || ''),
                        'bg-green-500': selected?.taskStatus === 'completed',
                        'bg-red-500': ['cancelled', 'error'].includes(selected?.taskStatus || ''),
                        'bg-yellow-500': selected?.taskStatus === 'pending'
                      }"
                    ></span>
                  </span>
                  {{ formatTaskStatus(selected?.taskStatus) }}
               </span>
             </div>
           </div>

           <!-- File Tasks Section -->
           <div v-if="selected?.file_tasks && selected.file_tasks.length > 0" class="space-y-2">
              <h4 class="font-medium text-foreground flex items-center gap-2">
                <FileText class="w-4 h-4" /> 关联文件任务
              </h4>
              <div class="rounded-lg border border-border/50 bg-background overflow-hidden">
                <div class="max-h-[200px] overflow-y-auto">
                   <table class="w-full text-xs">
                      <thead class="bg-muted/50 sticky top-0">
                        <tr class="text-left">
                          <th class="p-2 font-medium text-muted-foreground">源文件</th>
                          <th class="p-2 font-medium text-muted-foreground">重命名</th>
                          <th class="p-2 font-medium text-muted-foreground text-center">状态</th>
                        </tr>
                      </thead>
                      <tbody class="divide-y divide-border/50">
                        <tr v-for="ft in selected.file_tasks" :key="ft.id" 
                            class="hover:bg-muted/50 cursor-pointer transition-colors"
                            @click="onOpenFileTaskDetails(ft)">
                          <td class="p-2 truncate max-w-[150px]" :title="ft.sourcePath">{{ ft.sourcePath }}</td>
                          <td class="p-2 truncate max-w-[150px]" :title="ft.file_rename">{{ ft.file_rename }}</td>
                          <td class="p-2 text-center">
                             <div class="flex justify-center" :title="formatFileTaskStatus(ft.file_status)">
                                <span class="relative flex h-2.5 w-2.5">
                                   <span class="relative inline-flex rounded-full h-2.5 w-2.5" 
                                     :class="{
                                       'bg-green-500': ft.file_status === 'completed',
                                       'bg-yellow-500': ['pending', 'processing'].includes(ft.file_status),
                                       'bg-red-500': ['failed', 'cancelled'].includes(ft.file_status)
                                     }"
                                   ></span>
                                </span>
                             </div>
                          </td>
                        </tr>
                      </tbody>
                   </table>
                </div>
              </div>
           </div>
           
           <div class="space-y-2">
              <h4 class="font-medium text-foreground">任务信息</h4>
              <div class="rounded-md bg-zinc-950 p-4 overflow-x-auto">
                <pre class="text-xs text-zinc-300 font-mono whitespace-pre-wrap">{{ selected?.taskInfo || '无额外信息' }}</pre>
              </div>
           </div>
        </div>
      </DialogContent>
    </Dialog>
    
    <!-- File Task Details Dialog -->
     <Dialog v-model:open="fileTaskDialogOpen">
       <DialogContent class="max-w-2xl max-h-[85vh] overflow-y-auto w-[90vw] sm:w-full rounded-xl">
         <DialogHeader>
           <DialogTitle class="text-lg font-semibold tracking-tight">文件任务详情</DialogTitle>
           <DialogDescription>
             ID: {{ selectedFileTask?.id }}
           </DialogDescription>
         </DialogHeader>
         
         <div class="mt-4 grid gap-4 text-sm">
           <div class="grid grid-cols-[100px_1fr] items-start gap-y-4 gap-x-4 p-4 rounded-lg bg-muted/30 border border-border/50">
             
             <!-- Source File -->
             <span class="text-muted-foreground font-medium flex items-center gap-2">
               <FileText class="w-4 h-4" /> 源文件
             </span>
             <span class="break-all font-mono text-xs">{{ selectedFileTask?.sourcePath }}</span>

             <!-- Rename -->
             <span class="text-muted-foreground font-medium flex items-center gap-2">
               <ArrowRight class="w-4 h-4" /> 重命名
             </span>
             <span class="break-all font-mono text-xs">{{ selectedFileTask?.file_rename }}</span>

             <!-- Target Path -->
             <span class="text-muted-foreground font-medium flex items-center gap-2">
               <FolderOpen class="w-4 h-4" /> 目标路径
             </span>
             <span class="break-all font-mono text-xs">{{ selectedFileTask?.targetPath || '-' }}</span>

             <!-- Status -->
             <span class="text-muted-foreground font-medium flex items-center gap-2">
               <Activity class="w-4 h-4" /> 状态
             </span>
             <span class="flex items-center gap-2">
                <span class="relative flex h-2.5 w-2.5">
                   <span class="relative inline-flex rounded-full h-2.5 w-2.5" 
                     :class="{
                       'bg-green-500': selectedFileTask?.file_status === 'completed',
                       'bg-yellow-500': ['pending', 'processing'].includes(selectedFileTask?.file_status || ''),
                       'bg-red-500': ['failed', 'cancelled'].includes(selectedFileTask?.file_status || '')
                     }"
                   ></span>
                </span>
                <span class="capitalize font-mono">{{ formatFileTaskStatus(selectedFileTask?.file_status) }}</span>
             </span>

             <!-- Update Time -->
             <span class="text-muted-foreground font-medium flex items-center gap-2">
               <Clock class="w-4 h-4" /> 更新时间
             </span>
             <span class="font-mono text-xs">{{ selectedFileTask?.updateTime }}</span>

             <!-- Error Message -->
             <template v-if="selectedFileTask?.errorMessage">
                <span class="text-destructive font-medium flex items-center gap-2">
                  <AlertCircle class="w-4 h-4" /> 错误信息
                </span>
                <span class="text-destructive font-mono text-xs break-all">{{ selectedFileTask?.errorMessage }}</span>
             </template>
           </div>
        </div>
      </DialogContent>
    </Dialog>

    <!-- Cancel Confirmation -->
    <Dialog v-model:open="cancelDialogOpen">
      <DialogContent class="max-w-sm">
        <DialogHeader>
          <DialogTitle>取消任务</DialogTitle>
          <DialogDescription>
            确定要取消该任务吗？此操作无法撤销。
          </DialogDescription>
        </DialogHeader>
        <div class="flex justify-end gap-3 mt-4">
          <Button variant="outline" @click="cancelDialogOpen = false">保留</Button>
          <Button variant="destructive" @click="confirmCancel">确认取消</Button>
        </div>
      </DialogContent>
    </Dialog>
  </div>
</template>
