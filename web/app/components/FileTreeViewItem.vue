<script setup lang="ts">
import { computed, inject, type Ref } from 'vue'
import { Checkbox } from '@/components/ui/checkbox'
import { Folder, FolderOpen, File as FileIcon, ChevronRight, ChevronDown, Minus, Check } from 'lucide-vue-next'

const props = defineProps<{
  node: any
  indentGuides: boolean[] // true = draw vertical line, false = empty space
  isLast: boolean
  collapsedKeys: Set<string>
}>()

const emit = defineEmits(['toggleExpand', 'toggleCheck'])
const fileTreeFiles = inject<Ref<any[]>>('fileTreeFiles')

const isFolder = computed(() => !props.node.isFile)
// Default expanded: isExpanded is true unless key is in collapsedKeys
const isExpanded = computed(() => !props.collapsedKeys.has(props.node.key))

// Computed state for Folders only
const folderCheckState = computed(() => {
  if (!isFolder.value) return false 
  // Read pre-calculated state from parent
  return props.node.checkState ?? false
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
      class="flex hover:bg-muted/50 rounded group select-none relative"
    >
      <!-- Spacer with Indent Guides -->
      <div class="flex shrink-0">
          <!-- Render guides for ancestors -->
          <div 
             v-for="(hasLine, i) in indentGuides" 
             :key="i" 
             class="w-5 relative"
          >
             <div v-if="hasLine" class="absolute left-2.5 top-0 bottom-0 w-px bg-border"></div>
          </div>
          
          <!-- Render connector for current level -->
          <div class="w-5 relative">
             <!-- Vertical part: full height if not last, half height if last -->
             <div 
               class="absolute left-2.5 top-0 w-px bg-border"
               :class="isLast ? 'h-1/2' : 'h-full'"
             ></div>
             <!-- Horizontal connector -->
             <div class="absolute left-2.5 top-1/2 w-2.5 h-px bg-border"></div>
          </div>
      </div>

      <!-- Content Wrapper -->
      <div class="flex items-center py-1 pr-2 flex-1 min-w-0">
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
    </div>

    <!-- Children -->
    <div v-if="isFolder && isExpanded">
      <FileTreeViewItem 
        v-for="(child, index) in node.children" 
        :key="child.key" 
        :node="child" 
        :indent-guides="[...indentGuides, !isLast]"
        :is-last="index === node.children.length - 1"
        :collapsed-keys="collapsedKeys"
        @toggle-expand="$emit('toggleExpand', $event)"
        @toggle-check="(n, v) => $emit('toggleCheck', n, v)"
      />
    </div>
  </div>
</template>
