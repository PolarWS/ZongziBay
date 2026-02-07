<script setup lang="ts">
import { computed, inject, type Ref } from 'vue'
import { Checkbox } from '@/components/ui/checkbox'
import { Folder, FolderOpen, File as FileIcon, ChevronRight, ChevronDown, Minus } from 'lucide-vue-next'

const props = defineProps<{
  node: any
  level: number
  expandedKeys: Set<string>
}>()

const emit = defineEmits(['toggleExpand', 'toggleCheck'])
const fileTreeFiles = inject<Ref<any[]>>('fileTreeFiles')

const isFolder = computed(() => !props.node.isFile)
const isExpanded = computed(() => props.expandedKeys.has(props.node.key))

const paddingLeft = computed(() => `${props.level * 1.5}rem`)

// Computed state for Folders only
const folderCheckState = computed(() => {
  if (!isFolder.value) return false // Should not be called for files usually
  if (!fileTreeFiles?.value) return false

  const prefix = props.node.key + '/'
  let hasChecked = false
  let hasUnchecked = false
  
  // Use simple for loop for performance
  for (const f of fileTreeFiles.value) {
      const p = f.newName || f.name || f.path || ''
      const normalizedPath = p.split(/[/\\]/).filter(Boolean).join('/')
      
      if (normalizedPath === props.node.key || normalizedPath.startsWith(prefix)) {
          if (f.checked) hasChecked = true
          else hasUnchecked = true
          
          if (hasChecked && hasUnchecked) return 'indeterminate'
      }
  }
  
  if (hasChecked && !hasUnchecked) return true
  if (!hasChecked && hasUnchecked) return false
  return 'indeterminate' // Should not reach here if files exist, but default safe
})

const handleFolderCheck = (v: boolean) => {
    emit('toggleCheck', props.node, folderCheckState.value)
}

const formatSz = (s: number) => {
    if (!Number.isFinite(s) || s <= 0) return ''
    const units = ['B', 'KB', 'MB', 'GB', 'TB']
    let i = 0
    let v = s
    while (v >= 1024 && i < units.length - 1) { v /= 1024; i++ }
    return `${v.toFixed(2)} ${units[i]}`
}

const toggleExpand = () => {
    emit('toggleExpand', props.node.key)
}

const handleNameClick = () => {
    if (isFolder.value) {
        handleFolderCheck(!folderCheckState.value)
    } else {
        if (props.node.file) {
            props.node.file.checked = !props.node.file.checked
        }
    }
}
</script>

<template>
  <div>
    <div 
      class="flex items-center py-1 pr-2 hover:bg-muted/50 rounded group select-none"
    >
      <div :style="{ width: paddingLeft }" class="shrink-0"></div>
      
      <!-- Expand Toggle -->
      <div 
        v-if="isFolder"
        class="cursor-pointer p-0.5 hover:bg-muted rounded mr-1 transition-colors"
        @click.stop="toggleExpand"
      >
        <ChevronDown v-if="isExpanded" class="w-4 h-4 text-muted-foreground" />
        <ChevronRight v-else class="w-4 h-4 text-muted-foreground" />
      </div>
      <div v-else class="w-5 mr-1"></div>

      <!-- Checkbox -->
      <div class="mr-2 flex items-center">
         <!-- FILE: Direct v-model binding -->
         <Checkbox 
           v-if="!isFolder && node.file"
           v-model="node.file.checked"
           class="data-[state=checked]:bg-primary data-[state=checked]:border-primary"
         />
         
         <!-- FOLDER: Computed state -->
         <Checkbox 
           v-else
           :checked="folderCheckState" 
           @update:checked="handleFolderCheck"
           class="data-[state=checked]:bg-primary data-[state=checked]:border-primary"
         >
            <div v-if="folderCheckState === 'indeterminate'" class="flex items-center justify-center text-current">
                <Minus class="h-3.5 w-3.5" />
            </div>
         </Checkbox>
      </div>

      <!-- Icon -->
      <div class="mr-2 shrink-0">
        <FolderOpen v-if="isFolder && isExpanded" class="w-4 h-4 text-blue-500" />
        <Folder v-else-if="isFolder" class="w-4 h-4 text-blue-500" />
        <FileIcon v-else class="w-4 h-4 text-muted-foreground" />
      </div>

      <!-- Name -->
      <span 
        class="text-sm truncate flex-1 cursor-pointer py-0.5" 
        @click.stop="handleNameClick"
      >
        {{ node.name }}
      </span>

      <!-- Size -->
      <span class="text-xs text-muted-foreground font-mono ml-2 shrink-0 tabular-nums">
        {{ formatSz(node.size) }}
      </span>
    </div>

    <!-- Children -->
    <div v-if="isFolder && isExpanded">
      <FileTreeViewItem 
        v-for="child in node.children" 
        :key="child.key" 
        :node="child" 
        :level="level + 1" 
        :expanded-keys="expandedKeys"
        @toggle-expand="$emit('toggleExpand', $event)"
        @toggle-check="(n, v) => $emit('toggleCheck', n, v)"
      />
    </div>
  </div>
</template>
