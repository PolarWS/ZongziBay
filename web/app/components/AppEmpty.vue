<script setup lang="ts">
import {
  Empty,
  EmptyContent,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from '@/components/ui/empty'
import { ClipboardX } from 'lucide-vue-next'

const props = withDefaults(defineProps<{
  title: string
  description?: string
  showIcon?: boolean
}>(), {
  description: '',
  showIcon: true,
})
</script>

<template>
  <div class="flex items-center justify-center py-12 w-full">
    <Empty>
      <EmptyHeader>
        <EmptyMedia v-if="showIcon" variant="icon">
          <ClipboardX />
        </EmptyMedia>
      </EmptyHeader>
      <EmptyTitle>{{ title }}</EmptyTitle>
      <EmptyDescription v-if="description">{{ description }}</EmptyDescription>
      <EmptyContent>
        <slot />
      </EmptyContent>
    </Empty>
  </div>
</template>
