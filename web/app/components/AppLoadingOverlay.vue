<script setup lang="ts">
import { Loader2 } from 'lucide-vue-next'
</script>

<template>
  <div class="absolute inset-0 flex items-center justify-center z-10 bg-background/50 backdrop-blur-sm transition-all duration-300">
    <div class="relative w-16 h-16">
      <div class="absolute inset-0 rounded-full border-4 border-primary/20"></div>
      <div class="absolute inset-0 rounded-full border-4 border-primary border-t-transparent animate-spin"></div>
      <div class="absolute inset-0 flex items-center justify-center">
        <div class="w-2 h-2 bg-primary rounded-full animate-ping"></div>
      </div>
    </div>
  </div>
</template>
