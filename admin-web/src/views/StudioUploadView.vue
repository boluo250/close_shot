<template>
  <div class="studio-upload-page">
    <StudioProfileView />
    <StudioPortfolioView />
  </div>
</template>

<script setup lang="ts">
import StudioProfileView from "./StudioProfileView.vue";
import StudioPortfolioView from "./StudioPortfolioView.vue";
</script>

<style scoped>
.studio-upload-page {
  display: grid;
  gap: 16px;
}
</style>
