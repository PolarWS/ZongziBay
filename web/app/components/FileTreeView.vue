<script setup lang="ts">
import { computed, ref, provide, toRef } from 'vue'
import FileTreeViewItem from './FileTreeViewItem.vue'

const props = defineProps<{
  files: any[]
}>()

provide('fileTreeFiles', toRef(props, 'files'))

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
}

// Build tree structure
const tree = computed(() => {
  const root: TreeNode[] = []

  props.files.forEach(file => {
    // Use newName to reflect current edit state, or fallback to name/path
    const pathStr = file.newName || file.name || file.path || ''
    // Normalize path separators
    const parts = pathStr.split(/[/\\]/).filter(Boolean)
    
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

  sortNodes(root)
  return root
})

// Expanded state
const expandedKeys = ref<Set<string>>(new Set())
const toggleExpand = (key: string) => {
  if (expandedKeys.value.has(key)) {
    expandedKeys.value.delete(key)
  } else {
    expandedKeys.value.add(key)
  }
}

const toggleCheck = (node: TreeNode, currentVal: boolean | 'indeterminate') => {
  // Logic: 
  // If current is 'indeterminate' or false -> toggle to TRUE (check all)
  // If current is true -> toggle to FALSE (uncheck all)
  const newVal = currentVal !== true 
  const prefix = node.key + '/'

  props.files.forEach(f => {
    const p = f.newName || f.name || f.path || ''
    // Normalize path to match tree key generation
    const normalizedPath = p.split(/[/\\]/).filter(Boolean).join('/')
    
    // Check if file matches the node (exact match) or is a child (prefix match)
    if (normalizedPath === node.key || normalizedPath.startsWith(prefix)) {
      f.checked = newVal
    }
  })
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
          v-for="node in tree" 
          :key="node.key"
          :node="node" 
          :level="0" 
          :expanded-keys="expandedKeys"
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

