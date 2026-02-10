<script setup lang="ts">
import { computed, ref, provide, toRef, watch } from 'vue'
import FileTreeViewItem from './FileTreeViewItem.vue'

const props = defineProps<{
  files: any[]
}>()

provide('fileTreeFiles', toRef(props, 'files'))

const updateTrigger = ref(0)

watch(() => props.files, () => {
  console.log('[FileTreeView] Files changed (deep), incrementing trigger')
  updateTrigger.value++
}, { deep: true })

const normalizePath = (p: string) => {
  // Convert backslashes to slashes, filter empty parts, and join
  return p.split(/[/\\]/).filter(Boolean).join('/')
}

// Helper to format file size if not imported
const formatSize = (size: number) => {
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

type TreeNode = {
  key: string
  name: string
  isFile: boolean
  file?: any
  children: TreeNode[]
  size: number
  checkState?: boolean | 'indeterminate'
}

// Rebuild tree structure manually to ensure reactivity
const tree = ref<TreeNode[]>([])

const rebuildTree = () => {
  const root: TreeNode[] = []

  props.files.forEach(file => {
    // Use newName to reflect current edit state, or fallback to name/path
    const pathStr = file.newName || file.name || file.path || ''
    // Normalize path separators
    const parts = normalizePath(pathStr).split('/')
    
    let currentLevel = root
    let currentPath = ''

    parts.forEach((part: string, index: number) => {
      const isLast = index === parts.length - 1
      currentPath = currentPath ? `${currentPath}/${part}` : part
      
      let node = currentLevel.find(n => n.name === part && n.isFile === isLast)
      
      if (!node) {
        node = {
          key: currentPath,
          name: part,
          isFile: isLast,
          file: isLast ? file : undefined,
          children: [],
          size: 0
        }
        currentLevel.push(node)
      }
      
      // Accumulate size for folders
      if (!isLast) {
        node.size += file.size || 0
      }
      
      currentLevel = node.children
    })
  })

  // Sort: Folders first, then files. Alphabetical within groups.
  const sortNodes = (nodes: TreeNode[]) => {
    nodes.sort((a, b) => {
      if (a.isFile === b.isFile) {
        return a.name.localeCompare(b.name)
      }
      return a.isFile ? 1 : -1
    })
    nodes.forEach(n => {
      if (n.children.length > 0) {
        sortNodes(n.children)
      }
    })
  }

  // Calculate check state via prefix match (centralized)
  const calculateStates = (nodes: TreeNode[]) => {
    nodes.forEach(n => {
       if (n.isFile) {
          n.checkState = n.file ? n.file.checked : false
       } else {
          // Folder: use prefix match logic against the FULL file list
          const prefix = n.key + '/'
          let hasChecked = false
          let hasUnchecked = false
          
          let matchCount = 0
          for (const f of props.files) {
             const p = f.newName || f.name || f.path || ''
             const normalizedPath = normalizePath(p)
             
             if (normalizedPath.startsWith(prefix)) {
                 matchCount++
                 if (f.checked) hasChecked = true
                 else hasUnchecked = true
                 
                 if (hasChecked && hasUnchecked) break
             }
          }
          
          if (hasChecked && !hasUnchecked) n.checkState = true
          else if (!hasChecked && hasUnchecked) n.checkState = false
          else if (hasChecked && hasUnchecked) n.checkState = 'indeterminate'
          else n.checkState = false // Empty folder
          
          // Recurse
          if (n.children.length > 0) {
             calculateStates(n.children)
          }
       }
    })
  }

  sortNodes(root)
  calculateStates(root)
  tree.value = root
}

watch(() => props.files, () => {
  rebuildTree()
}, { deep: true, immediate: true })

// Expanded state (Now using collapsedKeys for "default open" behavior)
const collapsedKeys = ref<Set<string>>(new Set())
const toggleExpand = (key: string) => {
  if (collapsedKeys.value.has(key)) {
    collapsedKeys.value.delete(key)
  } else {
    collapsedKeys.value.add(key)
  }
}

const emit = defineEmits(['update:files'])

const toggleCheck = (node: TreeNode, currentVal: boolean | 'indeterminate') => {
  // Logic: 
  // If current is 'indeterminate' or false -> toggle to TRUE (check all)
  // If current is true -> toggle to FALSE (uncheck all)
  const newVal = currentVal !== true 
  const prefix = node.key + '/'

  let changed = false
  let matchCount = 0

  // Iterate ALL files and check/uncheck based on prefix match
  // This matches the visual logic in FileTreeViewItem.vue
  props.files.forEach(f => {
    const p = f.newName || f.name || f.path || ''
    const normalizedPath = normalizePath(p)
    
    // Debug log for first few files or if matching
    const isMatch = normalizedPath === node.key || normalizedPath.startsWith(prefix)
    
    if (isMatch) {
       matchCount++
       if (f.checked !== newVal) {
         f.checked = newVal
         changed = true
       }
    }
  })
  
  // Force update if changed
  if (changed) {
    rebuildTree()
  }
}

// Default expand root folders if not too many
/*
if (tree.value.length < 5) {
  tree.value.forEach(n => !n.isFile && expandedKeys.value.add(n.key))
}
*/
</script>

<template>
  <div class="border border-border/50 rounded-xl overflow-hidden bg-white dark:bg-card shadow-sm">
    <div class="p-3 bg-muted/30 text-xs font-medium text-muted-foreground border-b border-border/50 flex justify-between items-center">
      <span>目录结构 (基于文件名)</span>
      <span class="bg-primary/10 text-primary px-2 py-0.5 rounded text-[10px]">
        {{ formatSize(files.reduce((acc, f) => acc + (f.checked ? f.size : 0), 0)) }} 已选
      </span>
    </div>
    <div class="p-2 max-h-[500px] overflow-auto">
      <template v-if="tree.length">
        <FileTreeViewItem 
          v-for="(node, index) in tree" 
          :key="node.key"
          :node="node" 
          :indent-guides="[]"
          :is-last="index === tree.length - 1"
          :collapsed-keys="collapsedKeys"
          @toggle-expand="toggleExpand"
          @toggle-check="toggleCheck"
        />
      </template>
      <div v-else class="text-center py-8 text-muted-foreground text-sm">
        暂无文件
      </div>
    </div>
  </div>
</template>

