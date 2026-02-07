<script setup lang="ts">
import type { HTMLAttributes } from 'vue'
import {
  Pagination,
  PaginationContent,
  PaginationEllipsis,
  PaginationItem,
  PaginationNext,
  PaginationPrevious,
} from '@/components/ui/pagination'
import { cn } from '@/lib/utils'

const props = withDefaults(defineProps<{
  page: number
  total: number
  itemsPerPage: number
  siblingCount?: number
  showEdges?: boolean
  class?: HTMLAttributes['class']
}>(), {
  siblingCount: 1,
  showEdges: true,
})
const emits = defineEmits<{ 'update:page': [value: number] }>()
</script>

<template>
  <div v-if="total > itemsPerPage" :class="cn('flex justify-center mt-6 mb-4', props.class)">
    <Pagination
      v-slot="{ page }"
      :items-per-page="itemsPerPage"
      :total="total"
      :page="props.page"
      @update:page="val => emits('update:page', val)"
      :sibling-count="siblingCount"
      :show-edges="showEdges"
    >
      <PaginationContent v-slot="{ items }">
        <PaginationPrevious />
        <template v-for="(item, index) in items" :key="index">
          <PaginationItem
            v-if="item.type === 'page'"
            :value="item.value"
            :is-active="item.value === page"
          >
            {{ item.value }}
          </PaginationItem>
          <PaginationEllipsis v-else />
        </template>
        <PaginationNext />
      </PaginationContent>
    </Pagination>
  </div>
</template>

<style scoped>
:deep([data-slot="pagination-previous"] span),
:deep([data-slot="pagination-next"] span) {
  display: none;
}
</style>
