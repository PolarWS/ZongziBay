<script setup lang="ts">
import { ArrowRight, Search, Clapperboard, Tv } from 'lucide-vue-next'
import { watchDebounced } from '@vueuse/core'
import { getSuggestionsApiV1TmdbSuggestionsGet } from '@/api/tmdb'

const props = withDefaults(defineProps<{ type: 'movie' | 'tv' }>(), { type: 'movie' })
const searchQuery = ref('')
const isFocused = ref(false)
const router = useRouter()

const suggestions = ref<string[]>([])

const handleSelect = (item: string) => {
  searchQuery.value = item
  isFocused.value = false
  submit()
}

const fetchSuggestions = async () => {
  const q = searchQuery.value.trim()
  if (!q) {
    suggestions.value = []
    return
  }
  try {
    const res = await getSuggestionsApiV1TmdbSuggestionsGet({ query: q, limit: 8, type: props.type } as any)
    suggestions.value = res?.data?.suggestions ?? []
  } catch {
    suggestions.value = []
  }
}

watchDebounced(
  () => searchQuery.value,
  () => {
    fetchSuggestions()
  },
  { debounce: 300, maxWait: 800 }
)

const submit = () => {
  const q = searchQuery.value.trim()
  if (!q) return
  router.push({ path: `/${props.type}`, query: { q } })
}
</script>

<template>
  <div class="space-y-2">
    <form class="relative" @submit.prevent="submit">
      <Input 
        id="input-26" 
        class="peer pe-12 ps-10 h-14 text-lg shadow-sm border-2 border-border/60 hover:border-primary/50 focus-visible:border-primary focus-visible:ring-0 transition-colors bg-background/80 backdrop-blur-sm rounded-xl" 
        placeholder="搜索电影或剧集..." 
        type="search" 
        v-model="searchQuery" 
        @focus="isFocused = true" 
      />
      <div
        class="pointer-events-none absolute inset-y-0 start-0 flex items-center justify-center ps-3 text-muted-foreground/80 peer-disabled:opacity-50"
      >
        <Search :size="20" :stroke-width="2" />
      </div>
      <button
        class="absolute inset-y-1 end-1 flex h-12 w-12 items-center justify-center rounded-lg text-muted-foreground/80 transition-colors hover:bg-primary hover:text-primary-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50 cursor-pointer"
        aria-label="Submit search"
        type="submit"
      >
        <ArrowRight :size="20" :stroke-width="2" aria-hidden="true" />
      </button>
      <div v-if="isFocused && suggestions.length" class="absolute top-full z-[100] mt-1 w-full rounded-xl border border-border/50 bg-popover/95 backdrop-blur-xl text-popover-foreground shadow-2xl animate-in fade-in-0 zoom-in-95 overflow-hidden">
        <div class="p-1">
          <div
            v-for="(item, index) in suggestions"
            :key="index"
            class="flex h-12 cursor-pointer items-center px-4 py-2 text-sm rounded-lg hover:bg-primary/10 hover:text-primary transition-colors"
            @click="handleSelect(item)"
          >
            <Clapperboard v-if="props.type === 'movie'" class="mr-3 h-4 w-4 opacity-50" />
            <Tv v-else class="mr-3 h-4 w-4 opacity-50" />
            {{ item }}
          </div>
        </div>
      </div>
    </form>
  </div>
</template>
