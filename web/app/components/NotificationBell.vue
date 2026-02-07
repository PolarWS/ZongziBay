<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue'
import { Bell, Check, Trash2, X } from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { onClickOutside } from '@vueuse/core'
import { 
  getNotificationsApiV1NotificationsGet as getNotifications, 
  getUnreadCountApiV1NotificationsUnreadCountGet as getUnreadCount, 
  markReadApiV1NotificationsNotificationIdReadPut as markRead, 
  markAllReadApiV1NotificationsReadAllPut as markAllRead, 
  deleteNotificationApiV1NotificationsNotificationIdDelete as deleteNotification 
} from '@/api/notifications'
import { toast } from 'vue-sonner'

const notifications = ref<API.Notification[]>([])
const unreadCount = ref(0)
const isOpen = ref(false)
const dropdownRef = ref<HTMLElement | null>(null)
const isLoading = ref(false)
let countTimer: number | undefined
let listTimer: number | undefined

onClickOutside(dropdownRef, () => {
  isOpen.value = false
})

const fetchNotifications = async (silent = false) => {
  try {
    if (!silent) isLoading.value = true
    const res = await getNotifications({ page: 1, page_size: 20 }, silent ? { skipErrorHandler: true } : {})
    if (res.code === 200) {
      notifications.value = res.data.items
    }
  } catch (error) {
    console.error(error)
  } finally {
    if (!silent) isLoading.value = false
  }
}

const fetchUnreadCount = async (silent = false) => {
  try {
    const res = await getUnreadCount(silent ? { skipErrorHandler: true } : {})
    if (res.code === 200) {
      unreadCount.value = res.data
    }
  } catch (error) {
    console.error(error)
  }
}

const toggleDropdown = () => {
  isOpen.value = !isOpen.value
}

watch(isOpen, (val) => {
  if (val) {
    fetchNotifications()
    fetchUnreadCount()
    listTimer = window.setInterval(() => fetchNotifications(true), 5000)
  } else {
    if (listTimer) clearInterval(listTimer)
  }
})

const handleMarkRead = async (id: number) => {
  try {
    await markRead({ notification_id: id })
    const item = notifications.value.find(n => n.id === id)
    if (item && item.isRead === 0) {
      item.isRead = 1
      unreadCount.value = Math.max(0, unreadCount.value - 1)
    }
  } catch (error) {
    toast.error('Failed to mark as read')
  }
}

const handleMarkAllRead = async () => {
  try {
    await markAllRead()
    notifications.value.forEach(n => n.isRead = 1)
    unreadCount.value = 0
    toast.success('已全部标记为已读')
  } catch (error) {
    toast.error('标记已读失败')
  }
}

const handleDelete = async (id: number) => {
    try {
        await deleteNotification({ notification_id: id })
        const item = notifications.value.find(n => n.id === id)
        if (item && item.isRead === 0) {
           unreadCount.value = Math.max(0, unreadCount.value - 1)
        }
        notifications.value = notifications.value.filter(n => n.id !== id)
    } catch (e) {
        toast.error('Failed to delete')
    }
}

onMounted(() => {
  fetchUnreadCount()
  // Poll every 5 seconds
  countTimer = window.setInterval(() => fetchUnreadCount(true), 5000)
})

onUnmounted(() => {
  if (countTimer) clearInterval(countTimer)
  if (listTimer) clearInterval(listTimer)
})
</script>

<template>
  <div class="relative" ref="dropdownRef">
    <Button variant="ghost" size="icon" @click="toggleDropdown" class="relative">
      <Bell class="h-5 w-5" />
      <span v-if="unreadCount > 0" class="absolute top-2 right-2 h-2 w-2 rounded-full bg-red-500 ring-2 ring-background"></span>
    </Button>

    <div v-if="isOpen" class="absolute right-0 mt-2 w-80 sm:w-96 rounded-xl border border-border bg-popover text-popover-foreground shadow-2xl z-50 backdrop-blur-sm">
      <div class="flex items-center justify-between p-4 border-b border-border/50">
        <h4 class="font-semibold text-sm">通知</h4>
        <Button variant="ghost" size="sm" class="h-8 text-xs px-2 hover:bg-muted" @click="handleMarkAllRead" v-if="unreadCount > 0">
          全部已读
        </Button>
      </div>
      
      <div class="max-h-[400px] overflow-y-auto p-2 space-y-1">
        <div v-if="isLoading && notifications.length === 0" class="text-center py-4 text-muted-foreground text-sm">
            加载中...
        </div>
        <div v-else-if="notifications.length === 0" class="text-center py-8 text-muted-foreground text-sm">
          暂无通知
        </div>
        
        <div v-for="item in notifications" :key="item.id" 
             class="flex gap-3 p-3 rounded-lg hover:bg-muted/80 transition-all duration-200 relative group cursor-default"
             :class="{ 'bg-muted/30': item.isRead === 1, 'bg-background hover:bg-muted/50': item.isRead === 0 }">
          
          <div class="flex-1 space-y-1.5">
             <div class="flex items-start justify-between">
                <p class="text-sm font-medium leading-none flex items-center gap-2">
                    {{ item.title }}
                    <span v-if="item.isRead === 0" class="h-2 w-2 rounded-full bg-primary shadow-[0_0_8px_rgba(var(--primary),0.5)]"></span>
                </p>
                <span class="text-[10px] text-muted-foreground whitespace-nowrap ml-2 font-mono">{{ item.createTime }}</span>
             </div>
             <p class="text-xs text-muted-foreground line-clamp-2 break-all leading-relaxed">
               {{ item.content }}
             </p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
