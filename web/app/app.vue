<script setup lang="ts">
import Sonner from '@/components/ui/sonner/Sonner.vue'

// Title is now managed in nuxt.config.ts to prevent flashing
</script>

<template>
  <NuxtLayout>
    <NuxtPage />
  </NuxtLayout>
  <Sonner />
</template>
<style>
/* Chrome, Safari, Edge */
input[type="search"]::-webkit-search-cancel-button {
  -webkit-appearance: none;
  appearance: none;
  display: none;
}

/* Firefox */
input[type="search"]::-moz-search-clear-button {
  display: none;
}
</style>