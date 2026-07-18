<script setup lang="ts">
withDefaults(defineProps<{
  count?: number
  withHeader?: boolean
}>(), {
  count: 10,
  withHeader: false,
})
</script>

<template>
  <div>
    <div v-if="withHeader" class="flex items-center gap-3 mb-4">
      <span class="h-5 w-1.5 rounded-full skeleton-shimmer" />
      <div class="h-5 w-20 rounded-md skeleton-shimmer" />
      <div class="h-5 w-12 rounded-full skeleton-shimmer" />
      <div class="h-px flex-1 bg-gradient-to-r from-border to-transparent" />
    </div>
    <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4">
      <div
        v-for="n in count"
        :key="n"
        class="rounded-xl border border-border bg-card overflow-hidden flex flex-col"
      >
        <div class="aspect-[2/3] skeleton-shimmer" />
        <div class="p-3 sm:p-4 space-y-2">
          <div class="h-4 w-11/12 rounded skeleton-shimmer" />
          <div class="h-4 w-2/3 rounded skeleton-shimmer" />
          <div class="h-3 w-1/3 rounded skeleton-shimmer mt-2" />
        </div>
      </div>
    </div>
  </div>
</template>
