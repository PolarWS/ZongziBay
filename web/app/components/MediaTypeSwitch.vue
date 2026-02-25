<script setup lang="ts">
import { ref, watch } from 'vue'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'

const selectedValue = ref('on')
const emit = defineEmits(['change'])
watch(selectedValue, (v) => {
  emit('change', v === 'on' ? 'tv' : 'movie')
})
</script>

<template>
  <div class="inline-flex h-12 rounded-lg bg-input/50 p-0.5 text-foreground">
    <RadioGroup
      v-model="selectedValue"
      :data-state="selectedValue"
      class="group relative inline-grid grid-cols-[1fr_1fr] items-center gap-0 text-sm font-medium after:absolute after:inset-y-0 after:w-1/2 after:rounded-md after:bg-background after:shadow-xs after:shadow-black/[.04] after:ring-offset-background after:transition-transform after:duration-300 after:[transition-timing-function:cubic-bezier(0.16,1,0.3,1)] has-focus-visible:after:ring-2 has-focus-visible:after:ring-ring has-focus-visible:after:ring-offset-2 data-[state=off]:after:translate-x-0 data-[state=on]:after:translate-x-full"
    >
      <label
        class="relative z-10 inline-flex h-full min-w-8 cursor-pointer items-center justify-center whitespace-nowrap px-4 group-data-[state=on]:text-muted-foreground/70"
      >
        电影
        <RadioGroupItem value="off" class="sr-only" />
      </label>
      <label
        class="relative z-10 inline-flex h-full min-w-8 cursor-pointer items-center justify-center whitespace-nowrap px-4 group-data-[state=off]:text-muted-foreground/70"
      >
        <span> 剧集 </span>
        <RadioGroupItem value="on" class="sr-only" />
      </label>
    </RadioGroup>
  </div>
</template>
